"""
scraper.py — MASCAC Baseball data scraper with local disk caching.

Aggregate stats (hitters.json, pitchers.json) are scraped once and cached.
Game logs are scraped on demand per player and cached individually.
Call refresh_aggregate() to force-update season totals.
"""

import json
import subprocess
import sys
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://mascac.com"
SEASON = "2025-26"
HITTER_URL = f"{BASE_URL}/sports/bsb/{SEASON}/players?pos=h&sort=avg&jsRendering=true"
PITCHER_URL = f"{BASE_URL}/sports/bsb/{SEASON}/players?pos=p&sort=era&jsRendering=true"

DATA_DIR = Path("data")
GAME_LOGS_DIR = DATA_DIR / "game_logs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(val):
    """Normalize empty/dash cells to None; coerce numbers."""
    if val in ("-", "–", "—", "", None):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return val.strip()


def _fetch_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def _find_table_by_header(soup: BeautifulSoup, marker: str, secondary: str = ""):
    """
    Return the <table> whose <thead> contains `marker`.
    When `secondary` is provided, also require that column to be present
    (used to distinguish the batting/pitching game log from a bare schedule table).
    Among all matches, return the one with the most columns.
    """
    best_table, best_headers, best_len = None, [], 0
    for table in soup.find_all("table"):
        thead = table.find("thead")
        if not thead:
            continue
        headers = [th.get_text(strip=True).lower() for th in thead.find_all("th")]
        if marker not in headers:
            continue
        if secondary and secondary not in headers:
            continue
        if len(headers) > best_len:
            best_table, best_headers, best_len = table, headers, len(headers)
    return best_table, best_headers


def _parse_table(table, headers: list) -> list[dict]:
    """Convert an HTML table body into a list of row dicts."""
    tbody = table.find("tbody")
    if not tbody:
        return []

    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue

        row = {}
        for i, cell in enumerate(cells):
            col = headers[i] if i < len(headers) else f"col{i}"

            # Extract player slug + name from any player profile link
            a = cell.find("a", href=True)
            if a and "/players/" in a["href"]:
                href = a["href"].split("?")[0].rstrip("/")
                row["slug"] = href.split("/")[-1]
                row["name"] = " ".join(a.get_text().split())
                row[col] = row["name"]
            else:
                row[col] = _clean(" ".join(cell.get_text().split()))

        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Aggregate stats
# ---------------------------------------------------------------------------

def scrape_hitters(force: bool = False) -> list[dict]:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / "hitters.json"

    if path.exists() and not force:
        return json.loads(path.read_text())

    soup = _fetch_soup(HITTER_URL)
    table, headers = _find_table_by_header(soup, "avg")
    if table is None:
        raise RuntimeError("Could not find hitters table on page.")

    rows = _parse_table(table, headers)
    path.write_text(json.dumps(rows, indent=2))
    return rows


def scrape_pitchers(force: bool = False) -> list[dict]:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / "pitchers.json"

    if path.exists() and not force:
        return json.loads(path.read_text())

    soup = _fetch_soup(PITCHER_URL)
    table, headers = _find_table_by_header(soup, "era")
    if table is None:
        raise RuntimeError("Could not find pitchers table on page.")

    rows = _parse_table(table, headers)
    path.write_text(json.dumps(rows, indent=2))
    return rows


def refresh_aggregate():
    """Force re-scrape of season totals (not game logs)."""
    scrape_hitters(force=True)
    scrape_pitchers(force=True)


# ---------------------------------------------------------------------------
# Game logs (on-demand, cached per player — requires Playwright for JS render)
# ---------------------------------------------------------------------------

_WORKER = Path(__file__).parent / "scrape_worker.py"


def _run_worker(tasks: list[dict]) -> list[dict]:
    """
    Launch scrape_worker.py in a subprocess with its own event loop.
    tasks: [{"slug": str, "url": str}, ...]
    returns: [{"slug": str, "html": str}, ...]
    """
    result = subprocess.run(
        [sys.executable, str(_WORKER)],
        input=json.dumps(tasks),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"scrape_worker failed: {result.stderr[:500]}")
    return json.loads(result.stdout)


def _fetch_soup_playwright(url: str) -> BeautifulSoup:
    """Render a JS-heavy page via the subprocess worker and return parsed soup."""
    results = _run_worker([{"slug": "_single", "url": url}])
    html = results[0]["html"] if results else ""
    return BeautifulSoup(html, "lxml")


def _parse_game_log_soup(soup: BeautifulSoup, pos: str) -> list[dict]:
    """Extract and clean game log rows from an already-rendered page soup."""
    secondary = "ab" if pos == "h" else "ip"
    table, headers = _find_table_by_header(soup, "date", secondary=secondary)
    if table is None:
        return []

    rows = _parse_table(table, headers)

    stat_col = "ab" if pos == "h" else "ip"
    rows = [r for r in rows if r.get(stat_col) is not None]

    for r in rows:
        if "opponent" in r and isinstance(r["opponent"], str):
            r["opponent"] = " ".join(r["opponent"].split())

    return rows


def scrape_game_log(slug: str, pos: str = "h", force: bool = False) -> list[dict]:
    """
    Fetch and cache a player's game log.
    pos="h" for hitters (looks for batting table with 'ab' column).
    pos="p" for pitchers (looks for pitching table with 'ip' column).
    """
    GAME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = GAME_LOGS_DIR / f"{slug}.json"

    if path.exists() and not force:
        return json.loads(path.read_text())

    url = f"{BASE_URL}/sports/bsb/{SEASON}/players/{slug}?view=gamelog"

    try:
        soup = _fetch_soup_playwright(url)
    except Exception:
        return []

    rows = _parse_game_log_soup(soup, pos)
    if rows:
        path.write_text(json.dumps(rows, indent=2))
    return rows


def scrape_all_game_logs(
    hitters: list,
    pitchers: list,
    force: bool = False,
    progress_cb=None,
) -> None:
    """
    Bulk-scrape game logs for all players using a single shared Playwright browser.
    Skips players whose cache file already exists (unless force=True).
    progress_cb(current, total, slug) is called before each fetch.
    """
    GAME_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, str]] = []
    seen: set[str] = set()
    for player, pos in [(p, "h") for p in hitters] + [(p, "p") for p in pitchers]:
        slug = player.get("slug")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        if force or not (GAME_LOGS_DIR / f"{slug}.json").exists():
            tasks.append((slug, pos))

    if not tasks:
        return

    if progress_cb:
        progress_cb(0, len(tasks), tasks[0][0])

    worker_tasks = [
        {"slug": slug, "url": f"{BASE_URL}/sports/bsb/{SEASON}/players/{slug}?view=gamelog"}
        for slug, _ in tasks
    ]
    pos_map = {slug: pos for slug, pos in tasks}

    results = _run_worker(worker_tasks)

    for i, result in enumerate(results):
        slug = result["slug"]
        html = result.get("html", "")
        if progress_cb:
            progress_cb(i + 1, len(tasks), slug)
        if not html:
            continue
        try:
            soup = BeautifulSoup(html, "lxml")
            rows = _parse_game_log_soup(soup, pos_map[slug])
            if rows:
                (GAME_LOGS_DIR / f"{slug}.json").write_text(json.dumps(rows, indent=2))
        except Exception:
            continue
