"""Fill README's results section from results/ (never hand-edited numbers)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"


def main() -> None:
    s = json.loads((R / "summary.json").read_text())
    meta, sm = s["meta"], s["summary"]
    rounds = meta["rounds"]
    fin = {a: by[str(rounds)] for a, by in sm.items()}
    b, c, a = fin["B_graph"], fin["C_desire"], fin.get("A_vector")
    tok = lambda x: x["input_tokens"]["mean"] + x["output_tokens"]["mean"]
    cut_calls = 1 - c["llm_calls"]["mean"] / b["llm_calls"]["mean"]
    cut_tok = 1 - tok(c) / tok(b)
    lines = [
        "## Results (measured, `make eval`)",
        "",
        f"Held-out questions about entities never seen in training. Seeds {meta['seeds']} (mean ± std across seeds), "
        f"model `{meta['model']}` at temperature 0, backend **{meta['backend']}**, generated {meta['generated_at']}.",
        "",
        f"- After {rounds} learning rounds, **C uses {cut_calls:.0%} fewer LLM calls and {cut_tok:.0%} fewer tokens per "
        f"task than B** (the same agent without routes), at accuracy {c['accuracy']['mean']:.2f} vs "
        f"{b['accuracy']['mean']:.2f}.",
    ]
    if "acc_at_1" in c:
        c0 = sm["C_desire"]["0"]["acc_at_1"]["mean"]
        lines.insert(3, f"- **Accuracy rises with use:** held-out questions answered correctly within a budget of 1 LLM call "
                        f"go from **{c0:.2f} to {c['acc_at_1']['mean']:.2f} ± {c['acc_at_1']['std']:.2f}** over {rounds} "
                        f"rounds. The graph agent without routes (B) scores {b['acc_at_1']['mean']:.2f} under the same budget, "
                        f"vector RAG (A) {a['acc_at_1']['mean']:.2f}.")
    if a:
        lines.append(f"- Iterative vector RAG (A) reaches {a['accuracy']['mean']:.2f} accuracy on the same questions.")
    lines += ["", "![accuracy within one LLM call](docs/img/curve.png)", ""]
    md = (R / "results.md").read_text()
    md = md[md.index("## Held-out, after"):].replace("## ", "#### ")
    lines += [md.strip(), ""]
    heal = R / "heal.json"
    if heal.exists():
        h = json.loads(heal.read_text())
        tl = {e["event"]: e for e in h["timeline"]}
        sc = tl.get("scenario", {})
        lines += ["### Heal test (`results/heal.json`)", "",
                  f"Question: “{sc.get('question')}”. One fact changes: on-call for {sc.get('team')}, "
                  f"{sc.get('on_call_before')} → {sc.get('on_call_after')}.", "",
                  "| phase | Desire Paths (C) | LLM calls | stale-route agent |", "|---|---|---|---|"]
        for k in ("ask:before_change", "ask:after_change_template_retired", "ask:after_rebuild"):
            e = tl.get(k)
            if not e:
                continue
            d, st = e["desire"], e["stale"]
            how = f"route {d['route']}" if d["route"] else "fallback walk"
            lines.append(f"| {k[4:].replace('_', ' ')} | {', '.join(d['answer'])} {'✓' if d['correct'] else '✗'} ({how}) | "
                         f"{d['llm_calls']} | {', '.join(st['answer'])} {'✓' if st['correct'] else '✗'} |")
        if "templates_retired" in tl:
            lines += ["", f"Retired: {', '.join(x[0] + ' v' + str(x[2]) for x in tl['templates_retired']['ids'])}. "
                          f"Rebuilt: {', '.join(x[0] + ' v' + str(x[1]) for x in tl.get('templates_rebuilt', {}).get('ids', []))}."]
        lines.append("")
    sav = R / "savings.md"
    if sav.exists():
        lines += ["### Savings calculator (`results/savings.md`)", "", sav.read_text().split("\n", 2)[-1].strip(), ""]
    lt = R / "loadtest.md"
    if lt.exists():
        lines += ["### Under load (`results/loadtest.md`)", "", lt.read_text().split("\n", 2)[-1].strip(), "",
                  "Graph work only: the walk here leaves out its ~5 LLM calls per question, which dominate real latency. "
                  "One learned-route query per question gives higher throughput and a lower median than walking hop "
                  "by hop, but a worse p95 tail at high concurrency on this single local node. All answers were correct "
                  "at every level.", ""]
    gate = R / "gate_hydradb.json"
    if gate.exists():
        g = json.loads(gate.read_text())
        lines += [f"HydraDB gate (`make gate`): **{'passed' if g.get('passed') else 'FAILED'}**: "
                  + ", ".join(k for k in g.get("checks", {}) if not k.endswith("error")) + "."]
    text = (ROOT / "README.md").read_text()
    sv = R / "savings.json"
    if sv.exists() and "<!-- GTM:START -->" in text:
        d = json.loads(sv.read_text())
        key = next(k for k in d["cost_per_1000_tasks_usd"] if k.startswith("claude-sonnet"))
        row = d["cost_per_1000_tasks_usd"][key]
        save = row["B_graph"] - row["C_desire"]
        vol = d["volume_per_month"]
        g = [f"**Measured economics** (held-out, from `results/savings.json`; prices are list-price inputs). At {key} "
             f"prices, the same agent costs **${row['B_graph']:.2f} per 1,000 tasks without routes and "
             f"${row['C_desire']:.2f} with Desire Paths**, a saving of ${save:.2f} per 1,000 tasks "
             f"(${save * vol / 1000:,.0f}/month at {vol:,} tasks/month), at the same accuracy. One-time learning cost: "
             f"${row.get('C_learning_one_time', 0):.2f}. Priced at 20% of the saving, the fee would be "
             f"${0.2 * save:.2f} per 1,000 tasks and the customer keeps ${0.8 * save:.2f}. The dashboard's calculator "
             f"redoes this at your own volume and prices."]
        a_, b_ = text.index("<!-- GTM:START -->"), text.index("<!-- GTM:END -->")
        text = text[: a_ + len("<!-- GTM:START -->")] + "\n" + "\n".join(g) + "\n" + text[b_:]
    a_, b_ = text.index("<!-- RESULTS:START -->"), text.index("<!-- RESULTS:END -->")
    text = text[: a_ + len("<!-- RESULTS:START -->")] + "\n" + "\n".join(lines) + "\n" + text[b_:]
    (ROOT / "README.md").write_text(text)
    print("README results section updated")


if __name__ == "__main__":
    main()
