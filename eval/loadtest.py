"""Load test on HydraDB: learned routes (one query) vs hop-by-hop walking (one query per hop), no LLM involved.

    make loadtest        # -> results/loadtest.json, results/loadtest.md

For every held-out question of a seed, we know the learned route (results/routes_seed{seed}.json) and the start
entity. Two workloads answer the same questions:
  route  one compiled Cypher query per question (what Desire Paths does once a route is learned)
  walk   one neighbors() query per hop, following the same typed path (the graph work the walking agent does,
         with the LLM calls removed so only graph cost is compared)
Each runs at several concurrency levels; we report throughput, latency percentiles, errors, and correctness.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
import time
from pathlib import Path

from bench.gen import QTEMPLATES, generate, make_questions
from desirepaths.backend import GraphBackend, hydradb_settings, make_selfgraph, selfgraph_schema
from desirepaths.routes import RouteLibrary

RESULTS = Path(__file__).resolve().parent.parent / "results"


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


async def run(workload, jobs, conc: int) -> dict:
    sem = asyncio.Semaphore(conc)
    lat: list[float] = []
    errors = 0
    correct = 0

    async def one(job):
        nonlocal errors, correct
        async with sem:
            t = time.perf_counter()
            try:
                ok = await workload(job)
                correct += int(ok)
            except Exception:
                errors += 1
            lat.append(time.perf_counter() - t)

    t0 = time.perf_counter()
    await asyncio.gather(*[one(j) for j in jobs])
    wall = time.perf_counter() - t0
    return {"concurrency": conc, "requests": len(jobs), "qps": round(len(jobs) / wall, 1),
            "p50_ms": round(pct(lat, 50) * 1000, 1), "p95_ms": round(pct(lat, 95) * 1000, 1),
            "p99_ms": round(pct(lat, 99) * 1000, 1), "mean_ms": round(st.mean(lat) * 1000, 1),
            "errors": errors, "correct": correct}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--repeat", type=int, default=10, help="passes over the held-out questions per level")
    ap.add_argument("--levels", default="1,8,32,64")
    args = ap.parse_args()
    g = generate(args.seed)
    _, test = make_questions(g, 8, 6, args.seed)
    lib = RouteLibrary.load(str(RESULTS / f"routes_seed{args.seed}.json"))
    sg, dialect, ns = make_selfgraph(str(RESULTS / "graphs" / "load.kuzu"), selfgraph_schema(), fresh=True, namespace="load")
    out = {"backend": dialect.name, "seed": args.seed, "levels": {}}
    async with sg:
        b = GraphBackend(sg, dialect, namespace=ns)
        await b.load(g)
        jobs = []
        for q in test:
            hops = [tuple(h) for h in QTEMPLATES[q.template]["hops"]]
            rt = next((r for r in lib.active() if r.hops == hops), None)
            if rt is not None:
                jobs.append((q, rt.hops))
        jobs = jobs * args.repeat

        async def route(job):
            q, hops = job
            rows = await b.run_route(hops, q.start)
            return sorted(r["answer"] for r in rows) == q.gold

        async def walk(job):
            q, hops = job
            frontier = [q.start]
            for rel, d in hops:
                nxt = []
                for n in frontier:
                    nxt += [nb.id for nb in await b.neighbors(n) if nb.rel_type == rel and nb.direction == d]
                frontier = sorted(set(nxt))
            return frontier == q.gold

        for c in [int(x) for x in args.levels.split(",")]:
            for name, fn in (("route", route), ("walk", walk)):
                r = await run(fn, jobs, c)
                out["levels"].setdefault(name, []).append(r)
                print(f"{name:5s} c={c:<3} qps={r['qps']:7.1f} p50={r['p50_ms']:7.1f}ms p95={r['p95_ms']:7.1f}ms "
                      f"p99={r['p99_ms']:7.1f}ms errors={r['errors']} correct={r['correct']}/{r['requests']}", flush=True)
    out["questions"] = len(jobs) // args.repeat
    out["hydradb"] = bool(hydradb_settings())
    (RESULTS / "loadtest.json").write_text(json.dumps(out, indent=1))
    md = ["# Load test (graph only, no LLM)", "",
          f"Backend **{out['backend']}**, seed {args.seed}: {out['questions']} held-out questions × {args.repeat} passes "
          "per level. `route` = one learned-route query per question; `walk` = one neighbors query per hop along the "
          "same path.", "",
          "| workload | concurrency | throughput (q/s) | p50 ms | p95 ms | p99 ms | errors | correct |",
          "|---|---|---|---|---|---|---|---|"]
    for name in ("route", "walk"):
        for r in out["levels"][name]:
            md.append(f"| {name} | {r['concurrency']} | {r['qps']} | {r['p50_ms']} | {r['p95_ms']} | {r['p99_ms']} | "
                      f"{r['errors']} | {r['correct']}/{r['requests']} |")
    (RESULTS / "loadtest.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    asyncio.run(main())
