"""Build the static GitHub Pages snapshot of the dashboard into site/ (measured results, routes, calculator).

    make dashboard (or make demo) running on :8000, then: make site

Every read-only API response is captured from the running dashboard into site/api/..., and the page loads them by
relative path. On github.io the page switches to static mode: live ask and fact-change buttons are disabled and it
links to the live demo instead.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
BASE = "http://127.0.0.1:8000"


BLOG_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Desire Paths: the write-up</title>
<meta name="description" content="Teaching a knowledge graph the routes its agents keep walking. Built on HydraDB and SelfGraph.">
<style>:root{--bg:#fbfbf9;--ink:#1b1d21;--muted:#6b7079;--line:#e3e3df;--accent:#1f9d6b}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--ink:#e8e9eb;--muted:#9aa0a6;--line:#2a2e34}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
main{max-width:760px;margin:auto;padding:32px 16px 80px}h1{font-size:32px;line-height:1.2;letter-spacing:-.02em}
h2{margin-top:2em;font-size:22px}a{color:var(--accent)}code{font-size:.88em;background:rgba(127,127,127,.12);padding:1px 5px;border-radius:4px}
pre{overflow-x:auto;padding:12px;border:1px solid var(--line);border-radius:8px}table{border-collapse:collapse;width:100%;font-size:15px;display:block;overflow-x:auto}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}.top{font-size:14px;color:var(--muted)}</style></head>
<body><main><p class="top"><a href="../">← dashboard snapshot</a> · <a href="https://github.com/Jmohak2004/desire-paths">code</a></p>
{{BODY}}</main></body></html>"""


def get(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.read()


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "api" / "route_example").mkdir(parents=True)
    shutil.copy(ROOT / "dashboard" / "index.html", SITE / "index.html")
    for name in ("status", "results", "examples", "routes"):
        (SITE / "api" / name).write_bytes(get(f"/api/{name}"))
    for rt in json.loads((SITE / "api" / "routes").read_text())["routes"]:
        (SITE / "api" / "route_example" / rt["id"]).write_bytes(get(f"/api/route_example/{rt['id']}"))
    (SITE / ".nojekyll").write_text("")
    blog = ROOT / "docs" / "blog.final.md"
    if blog.exists():  # the hackathon write-up, as a permanent blog page
        import markdown

        body = markdown.markdown(blog.read_text(), extensions=["tables", "fenced_code"])
        (SITE / "blog").mkdir()
        (SITE / "blog" / "index.html").write_text(BLOG_PAGE.replace("{{BODY}}", body))
    arch = ROOT / "docs" / "architecture.html"
    if arch.exists():  # the architecture diagram + talk track
        (SITE / "architecture").mkdir()
        shutil.copy(arch, SITE / "architecture" / "index.html")
    print("site/ built:", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*") if p.is_file()))


if __name__ == "__main__":
    main()
