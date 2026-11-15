"""Savings calculator: cost per 1,000 agent tasks for A, B and C from MEASURED per-task tokens.

Token counts and LLM calls come from results/summary.json (held-out, final learning round, mean over seeds).
Prices are inputs, not measurements. The presets are list prices per 1M tokens (input / output); the model we
measured with (poolside/laguna-xs-2.1 on NVIDIA's API) has no published per-token price, so the presets show what
the same token volumes cost at common price points. C's one-time learning cost (its train rounds) is reported
separately and amortised over the monthly volume.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"

PRESETS = {  # $ per 1M tokens: (input, output)
    "small-open-model (0.10 / 0.40)": (0.10, 0.40),
    "claude-haiku-5-5 list (0.10 / 0.50)": (0.10, 0.50),
    "claude-sonnet-5-5 list (2.00 / 10.00)": (2.00, 10.00),
    "claude-opus-5-5 list (4.00 / 20.00)": (4.00, 20.00),
}


def per_task(summary: dict) -> dict:
    s = summary["summary"]
    rounds = summary["meta"]["rounds"]
    out = {}
    for agent, by in s.items():
        c = by[str(rounds)] if str(rounds) in by else by[rounds]
        out[agent] = {k: c[k]["mean"] for k in ("input_tokens", "output_tokens", "llm_calls", "graph_calls", "accuracy", "latency_s")}
    return out


def learning_cost(rows_path: Path) -> dict:
    """Mean tokens spent per seed on C's train rounds (the one-time cost of learning the routes)."""
    per_seed: dict[int, dict] = {}
    if not rows_path.exists():
        return {}
    for line in rows_path.open():
        r = json.loads(line)
        if r["agent"] != "C_desire_train":
            continue
        d = per_seed.setdefault(r["seed"], {"input_tokens": 0, "output_tokens": 0, "tasks": 0})
        d["input_tokens"] += r["input_tokens"]
        d["output_tokens"] += r["output_tokens"]
        d["tasks"] += 1
    if not per_seed:
        return {}
    n = len(per_seed)
    return {k: sum(d[k] for d in per_seed.values()) / n for k in ("input_tokens", "output_tokens", "tasks")}


def cost_per_1k(t: dict, pin: float, pout: float) -> float:
    return 1000 * (t["input_tokens"] * pin + t["output_tokens"] * pout) / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume", type=int, default=100_000, help="agent tasks per month")
    args = ap.parse_args()
    summary = json.loads((RESULTS / "summary.json").read_text())
    pt = per_task(summary)
    learn = learning_cost(RESULTS / "per_question.jsonl")
    table = {}
    for name, (pin, pout) in PRESETS.items():
        row = {a: round(cost_per_1k(t, pin, pout), 4) for a, t in pt.items()}
        if learn:
            row["C_learning_one_time"] = round((learn["input_tokens"] * pin + learn["output_tokens"] * pout) / 1e6, 4)
        table[name] = row
    out = {"volume_per_month": args.volume, "per_task_measured": pt, "learning_one_time": learn,
           "cost_per_1000_tasks_usd": table, "source": "results/summary.json (held-out, final round, mean over seeds)"}
    (RESULTS / "savings.json").write_text(json.dumps(out, indent=1))
    agents = [a for a in ("A_vector", "B_graph", "C_desire") if a in pt]
    md = ["# Savings calculator\n",
          "Per-task tokens are measured (held-out, final learning round, mean over seeds). Prices are inputs.\n",
          "| agent | accuracy | LLM calls / task | input tok / task | output tok / task |", "|---|---|---|---|---|"]
    for a in agents:
        t = pt[a]
        md.append(f"| {a} | {t['accuracy']:.2f} | {t['llm_calls']:.2f} | {t['input_tokens']:.0f} | {t['output_tokens']:.0f} |")
    md += ["", f"Cost per 1,000 tasks (USD), and per month at {args.volume:,} tasks:", "",
           "| price point ($/1M in / out) | " + " | ".join(agents) + " | C vs B saving | C one-time learning |",
           "|---|" + "---|" * (len(agents) + 2)]
    for name, row in table.items():
        cells = " | ".join(f"${row[a]:.3f} (${row[a] * args.volume / 1000:,.0f}/mo)" for a in agents)
        sav = 1 - row["C_desire"] / row["B_graph"] if row.get("B_graph") else 0
        md.append(f"| {name} | {cells} | {sav:.0%} | ${row.get('C_learning_one_time', 0):.3f} |")
    (RESULTS / "savings.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
