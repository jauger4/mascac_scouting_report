"""
scrape_worker.py — Playwright subprocess worker (async, concurrent).

Reads a JSON array of {"slug": str, "url": str} from stdin.
Navigates each URL with a shared Chromium browser, up to 5 pages concurrently.
Writes a JSON array of {"slug": str, "html": str} to stdout.

Run via scraper.py only — not intended to be invoked directly.
"""

import asyncio
import json
import sys

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

_CONCURRENCY = 5

_WAIT_JS_GENERIC = """() => {
    const tables = document.querySelectorAll('table');
    for (const t of tables) {
        if (t.querySelectorAll('tbody tr').length > 0) return true;
    }
    return false;
}"""


def _wait_js_for_col(col):
    return f"""() => {{
        for (const t of document.querySelectorAll('table')) {{
            const thead = t.querySelector('thead');
            if (!thead) continue;
            const hdrs = Array.from(thead.querySelectorAll('th')).map(h => h.textContent.trim().toLowerCase());
            if (hdrs.includes('{col}') && t.querySelectorAll('tbody tr').length > 0) return true;
        }}
        return false;
    }}"""


async def _fetch_one(browser, sem, task):
    wait_col = task.get("wait_col", "")
    wait_js = _wait_js_for_col(wait_col) if wait_col else _WAIT_JS_GENERIC
    async with sem:
        page = await browser.new_page()
        try:
            await page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            if task.get("wait_networkidle"):
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    pass
            try:
                await page.wait_for_function(wait_js, timeout=15000)
            except PWTimeout:
                pass
            html = await page.content()
        except Exception:
            html = ""
        finally:
            await page.close()
    return {"slug": task["slug"], "html": html}


async def main():
    tasks = json.load(sys.stdin)
    sem = asyncio.Semaphore(_CONCURRENCY)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        results = await asyncio.gather(*[_fetch_one(browser, sem, t) for t in tasks])
        await browser.close()
    json.dump(list(results), sys.stdout)


asyncio.run(main())
