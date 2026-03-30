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

_WAIT_JS = """() => {
    const tables = document.querySelectorAll('table');
    for (const t of tables) {
        if (t.querySelectorAll('tbody tr').length > 0) return true;
    }
    return false;
}"""

tasks = json.load(sys.stdin)
results = []

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    for task in tasks:
        try:
            page.goto(task["url"], wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_function(_WAIT_JS, timeout=15000)
            except PWTimeout:
                pass
            html = page.content()
        except Exception:
            html = ""
        results.append({"slug": task["slug"], "html": html})

    browser.close()

json.dump(results, sys.stdout)
