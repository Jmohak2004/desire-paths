"""Fill the {{PLACEHOLDERS}} in docs/blog.md and docs/social_posts.md from results/ (no hand-copied numbers).

Writes docs/blog.final.md and docs/social_posts.final.md, ready to paste.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
LIVE = "https://desire-paths-qhfa.onrender.com"


def main() -> None:
    s = json.loads((R / "summary.json").read_text())
    meta, sm = s["meta"], s["summary"]
    rounds = str(meta["rounds"])
    a, b, c = sm["A_vector"][rounds], sm["B_graph"][rounds], sm["C_desire"][rounds]
    c0 = sm["C_desire"]["0"]
    tok = lambda x: x["input_tokens"]["mean"] + x["output_tokens"]["mean"]
    values = {
        "B1": f"{b['acc_at_1']['mean']:.2f}",
        "A1": f"{a['acc_at_1']['mean']:.2f}",
        "C1_START": f"{c0['acc_at_1']['mean']:.2f}",
        "C1_END": f"{c['acc_at_1']['mean']:.2f}",
        "ROUNDS": rounds,
        "C_ACC": f"{c['accuracy']['mean']:.2f}",
        "A_ACC": f"{a['accuracy']['mean']:.2f}",
        "CUT": f"{1 - c['llm_calls']['mean'] / b['llm_calls']['mean']:.0%}",
        "TOKCUT": f"{1 - tok(c) / tok(b):.0%}",
        "LIVE": LIVE,
    }
    curve = " → ".join(f"{sm['C_desire'][str(r)]['acc_at_1']['mean']:.2f}" for r in range(int(rounds) + 1))
    values["RESULTS"] = "\n".join([
        f"Model `{meta['model']}` (temperature 0) for every agent; backend **{meta['backend']}**; seeds {meta['seeds']}.",
        "",
        "| | accuracy | accuracy within 1 LLM call | LLM calls / task | tokens / task |",
        "|---|---|---|---|---|",
        f"| A · vector RAG | {a['accuracy']['mean']:.2f} | {a['acc_at_1']['mean']:.2f} | {a['llm_calls']['mean']:.2f} | {tok(a):.0f} |",
        f"| B · graph agent | {b['accuracy']['mean']:.2f} | {b['acc_at_1']['mean']:.2f} | {b['llm_calls']['mean']:.2f} | {tok(b):.0f} |",
        f"| C · Desire Paths (after {rounds} rounds) | {c['accuracy']['mean']:.2f} | {c['acc_at_1']['mean']:.2f} | "
        f"{c['llm_calls']['mean']:.2f} | {tok(c):.0f} |",
        "",
        f"C's accuracy within one LLM call, by learning round: {curve}.",
    ])
    for name in ("blog.md", "social_posts.md"):
        text = (ROOT / "docs" / name).read_text()
        out = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)
        left = re.findall(r"\{\{\w+\}\}", out)
        (ROOT / "docs" / name.replace(".md", ".final.md")).write_text(out)
        print(f"docs/{name.replace('.md', '.final.md')} written; unfilled placeholders: {left or 'none'}")


if __name__ == "__main__":
    main()
