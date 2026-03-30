"""
scrape_worker.py — Playwright subprocess worker.

Reads a JSON array of {"slug": str, "url": str} from stdin.
Navigates each URL with a single shared Chromium browser.
Writes a JSON array of {"slug": str, "html": str} to stdout.

Run via scraper.py only — not intended to be invoked directly.
"""

import json
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

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


tasks = json.load(sys.stdin)
results = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    for task in tasks:
        wait_col = task.get("wait_col", "")
        wait_js = _wait_js_for_col(wait_col) if wait_col else _WAIT_JS_GENERIC
        try:
            page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_function(wait_js, timeout=15000)
            except PWTimeout:
                pass
            html = page.content()
        except Exception:
            html = ""
        results.append({"slug": task["slug"], "html": html})

    browser.close()

json.dump(results, sys.stdout)
