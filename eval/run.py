"""`make eval`: A vs B vs C on held-out questions, per learning round, over several seeds.

Protocol (per seed):
  1. Generate the graph and questions from the seed; load the graph into SelfGraph (HydraDB if configured, else Kuzu).
  2. Round 0: score A, B and C on all held-out questions. C has no routes yet.
  3. Rounds 1..R: C answers one slice of TRAIN questions with learning on (gold says whether its answer was right),
     the route library promotes templates, then C is scored on all HELD-OUT questions with learning frozen.
  A and B hold no learning state, so their numbers cannot change between rounds; they are measured once per seed
  and drawn flat (labelled as such). Held-out start entities never appear in train.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics as st
import time
from pathlib import Path

from bench.gen import generate, make_questions
from desirepaths.agents import DesirePaths, GraphAgent, VectorRAG, correct
from desirepaths.backend import GraphBackend, make_selfgraph, selfgraph_schema
from desirepaths.llm import LLM, MODEL, EMBED_MODEL, Embedder
from desirepaths.routes import RouteLibrary

RESULTS = Path(__file__).resolve().parent.parent / "results"
METRICS = ["accuracy", "llm_calls", "input_tokens", "output_tokens", "latency_s", "graph_calls"]


def record(agent, rnd, q, res) -> dict:
    m = res.metrics()
    return dict(agent=agent, round=rnd, qid=q.qid, template=q.template, question=q.text, gold=q.gold_names,
                answer=res.answer, correct=correct(res.answer, q.gold_names), **m)


def agg(rows: list[dict]) -> dict:
    n = len(rows) or 1
    out = {"n": len(rows), "accuracy": sum(r["correct"] for r in rows) / n}
    for k in METRICS[1:]:
        out[k] = sum(r[k] for r in rows) / n
    out["route_rate"] = sum(1 for r in rows if r.get("route")) / n
    out["errors"] = sum(1 for r in rows if r.get("error"))
    return out


async def run_seed(seed: int, args, llm: LLM, emb: Embedder) -> list[dict]:
    g = generate(seed)
    train, test = make_questions(g, args.train_per_template, args.test_per_template, seed)
    kpath = str(RESULTS / "graphs" / f"seed{seed}.kuzu")
    Path(kpath).parent.mkdir(parents=True, exist_ok=True)
    sg, dialect = make_selfgraph(kpath, selfgraph_schema(), fresh=True, namespace=f"seed{seed}")
    rows: list[dict] = []
    async with sg:
        backend = GraphBackend(sg, dialect, namespace=f"seed{seed}")
        t0 = time.time()
        await backend.load(g)
        print(f"[seed {seed}] backend={dialect.name} loaded {len(g.nodes)} nodes / {len(g.edges)} edges in {time.time()-t0:.1f}s; "
              f"{len(train)} train, {len(test)} held-out", flush=True)
        A = VectorRAG(llm, emb, rounds=3)
        B = GraphAgent(llm)
        lib = RouteLibrary(min_support=args.min_support)
        C = DesirePaths(llm, lib, B)
        if "A" in args.agents:
            await A.index(g, f"seed{seed}")

        async def score(agent_name, fn, rnd):
            res = await asyncio.gather(*[fn(q) for q in test])
            out = [record(agent_name, rnd, q, r) | {"seed": seed} for q, r in zip(test, res)]
            a = agg(out)
            print(f"[seed {seed}] round {rnd} {agent_name}: acc={a['accuracy']:.2f} calls={a['llm_calls']:.2f} "
                  f"in_tok={a['input_tokens']:.0f} graph={a['graph_calls']:.1f} routed={a['route_rate']:.2f} err={a['errors']}", flush=True)
            return out

        if "A" in args.agents:
            rows += await score("A_vector", lambda q: A.answer(q.text), 0)
        rows += await score("B_graph", lambda q: B.answer(q.text, backend), 0)
        C.learning = False
        rows += await score("C_desire", lambda q: C.answer(q.text, backend), 0)

        R = args.rounds
        chunk = (len(train) + R - 1) // R
        for r in range(1, R + 1):
            lib.clock = r
            C.learning = True
            batch = train[(r - 1) * chunk: r * chunk]
            tr = await asyncio.gather(*[C.answer(q.text, backend, gold_names=q.gold_names) for q in batch])
            rows += [record("C_desire_train", r, q, x) | {"seed": seed} for q, x in zip(batch, tr)]
            promoted = lib.promote()
            print(f"[seed {seed}] round {r} learned on {len(batch)} train q; promoted {[p.id for p in promoted]}; "
                  f"active={[(t.id, t.signature()) for t in lib.active()]}", flush=True)
            C.learning = False
            rows += await score("C_desire", lambda q: C.answer(q.text, backend), r)
        lib.save(str(RESULTS / f"routes_seed{seed}.json"))
    emb.flush()
    return rows


def summarise(rows: list[dict], seeds: list[int], rounds: int) -> dict:
    """Per agent and round: mean and std across seeds of the per-seed held-out averages."""
    out: dict = {}
    agents = sorted({r["agent"] for r in rows if not r["agent"].endswith("_train")})
    for a in agents:
        for rnd in range(rounds + 1):
            src_rnd = rnd if a == "C_desire" else 0  # A and B: no learning state, measured once per seed
            per_seed = []
            for s in seeds:
                sel = [r for r in rows if r["agent"] == a and r["round"] == src_rnd and r["seed"] == s]
                if sel:
                    per_seed.append(agg(sel))
            if not per_seed:
                continue
            cell = {"measured_round": src_rnd, "seeds": len(per_seed)}
            for k in METRICS + ["route_rate"]:
                vals = [p[k] for p in per_seed]
                cell[k] = {"mean": st.mean(vals), "std": st.pstdev(vals) if len(vals) > 1 else 0.0}
            cell["errors"] = sum(p["errors"] for p in per_seed)
            out.setdefault(a, {})[rnd] = cell
    return out


def table(summary: dict, rnd: int) -> str:
    hdr = "| agent | accuracy | LLM calls / q | input tok / q | output tok / q | latency s / q | graph calls / q |\n|---|---|---|---|---|---|---|\n"
    lines = []
    for a, by in summary.items():
        c = by.get(rnd)
        if not c:
            continue
        f = lambda k, p=2: f"{c[k]['mean']:.{p}f} ± {c[k]['std']:.{p}f}"
        lines.append(f"| {a} | {f('accuracy')} | {f('llm_calls')} | {f('input_tokens', 0)} | {f('output_tokens', 0)} | "
                     f"{f('latency_s')} | {f('graph_calls', 1)} |")
    return hdr + "\n".join(lines) + "\n"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=os.environ.get("DP_SEEDS", "0,1,2"))
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--train-per-template", type=int, default=8)
    ap.add_argument("--test-per-template", type=int, default=4)
    ap.add_argument("--min-support", type=int, default=3)
    ap.add_argument("--agents", default="A,B,C")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]
    RESULTS.mkdir(exist_ok=True)
    llm, emb = LLM(), Embedder()
    rows: list[dict] = []
    for s in seeds:
        rows += await run_seed(s, args, llm, emb)
    with open(RESULTS / "per_question.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    summary = summarise(rows, seeds, args.rounds)
    from desirepaths.backend import hydradb_settings

    meta = dict(model=MODEL, temperature=0.0, embed_model=EMBED_MODEL, seeds=seeds, rounds=args.rounds,
                backend="hydradb" if hydradb_settings() else "kuzu (embedded SelfGraph store; HydraDB not configured)",
                train_per_template=args.train_per_template, test_per_template=args.test_per_template,
                min_support=args.min_support, generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                note="A and B hold no learning state: measured once per seed (round 0) and drawn flat across rounds.")
    (RESULTS / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary}, indent=1))
    md = [f"# Results\n\nModel `{MODEL}` (temperature 0), embeddings `{EMBED_MODEL}`, backend: {meta['backend']}.",
          f"Seeds {seeds}; mean ± std across seeds of per-question averages on HELD-OUT questions.\n",
          f"## Held-out, after {args.rounds} learning rounds\n", table(summary, args.rounds),
          "\n## Held-out, round 0 (before any learning)\n", table(summary, 0),
          "\n## C learning curve (held-out, per round)\n",
          "| round | accuracy | LLM calls / q | input tok / q | routed share |\n|---|---|---|---|---|"]
    for rnd, c in summary.get("C_desire", {}).items():
        md.append(f"| {rnd} | {c['accuracy']['mean']:.2f} ± {c['accuracy']['std']:.2f} | {c['llm_calls']['mean']:.2f} ± "
                  f"{c['llm_calls']['std']:.2f} | {c['input_tokens']['mean']:.0f} | {c['route_rate']['mean']:.2f} |")
    md.append("\n" + meta["note"])
    (RESULTS / "results.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    asyncio.run(main())
