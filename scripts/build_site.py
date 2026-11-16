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
    print("site/ built:", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*") if p.is_file()))


if __name__ == "__main__":
    main()
