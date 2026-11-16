"""Record the backup demo: drives the LIVE dashboard (http://127.0.0.1:8000) in Chrome and saves a video.

    make dashboard &      # wait until it serves
    make record           # -> docs/demo.mp4 (+ docs/img/*.png)

Every answer in the video is computed live by the running agents against the graph; nothing is staged.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
IMG = DOCS / "img"
URL = "http://127.0.0.1:8000"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def main() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    vid_dir = ROOT / "scratch" / "video"
    shutil.rmtree(vid_dir, ignore_errors=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME if Path(CHROME).exists() else None, headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(vid_dir),
                                        record_video_size={"width": 1280, "height": 800}, color_scheme="light")
        page = await ctx.new_page()
        await page.goto(URL)
        await page.wait_for_selector("#kpis .kpi", timeout=60000)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(IMG / "results.png"))
        await page.evaluate("document.querySelector('#c0').scrollIntoView({behavior:'smooth',block:'start'})")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(IMG / "curve.png"))

        async def ask(agent_btn: str, shot: str | None = None):
            await page.click(agent_btn)
            await page.wait_for_function("document.querySelector('#askC').disabled === false", timeout=180000)
            await page.wait_for_timeout(1800)
            if shot:
                await page.screenshot(path=str(IMG / shot))

        await page.evaluate("document.querySelector('#q').scrollIntoView({behavior:'smooth',block:'start'})")
        await page.wait_for_timeout(1200)
        chip = page.locator("#ex .chip").first
        await chip.click()
        await page.wait_for_timeout(800)
        await ask("#askB", "ask_b.png")      # graph agent without routes: one LLM call per hop
        await ask("#askC", "ask_c.png")      # same held-out question: known shape -> route, no LLM call
        await page.locator('#ex .chip[data-kind="new phrasing"]').nth(1).click()
        await page.wait_for_timeout(800)
        await ask("#askC", "ask_c_router.png")  # a phrasing never seen in training -> router (1 LLM call) -> route

        await page.locator(".showq").last.scroll_into_view_if_needed()
        await page.wait_for_timeout(800)
        await page.locator(".showq").last.click()   # the learned 4-hop route as ONE Cypher query, run live
        await page.wait_for_selector(".qbox pre", timeout=30000)
        await page.locator(".qbox pre").last.scroll_into_view_if_needed()
        await page.wait_for_timeout(2500)
        await page.evaluate("document.querySelector('#mut').scrollIntoView({behavior:'smooth',block:'start'})")
        await page.wait_for_timeout(1200)
        await page.click("#mut")
        await page.wait_for_selector("#heal div", timeout=60000)
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(IMG / "fact_changed.png"))
        await page.locator(".tryq").last.click()
        await page.wait_for_timeout(1200)
        await ask("#askC", "after_change.png")  # template retired -> fallback walk, still correct
        await page.evaluate("document.querySelector('#reval').scrollIntoView({behavior:'smooth',block:'start'})")
        await page.wait_for_timeout(800)
        await page.click("#reval")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(IMG / "rebuilt.png"))
        await page.evaluate("document.querySelector('#q').scrollIntoView({behavior:'smooth',block:'start'})")
        await page.wait_for_timeout(800)
        await ask("#askC", "after_rebuild.png")  # rebuilt route v2 -> 1 LLM call, new fact

        await page.evaluate("document.querySelector('#calc').scrollIntoView({behavior:'smooth',block:'center'})")
        await page.wait_for_timeout(1000)
        await page.fill("#vol", "1000000")
        await page.dispatch_event("#vol", "input")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(IMG / "calculator.png"))
        await ctx.close()
        await browser.close()
    webm = next(vid_dir.glob("*.webm"))
    out = DOCS / "demo.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    asyncio.run(main())
