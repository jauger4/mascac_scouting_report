"""
scraper.py — MASCAC Baseball data scraper with local disk caching.

Aggregate stats (hitters.json, pitchers.json) are scraped once and cached.
Game logs are scraped on demand per player and cached individually.
Call refresh_aggregate() to force-update season totals.
"""

import datetime
import json
import subprocess
import sys
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE_URL = "https://mascac.com"
SEASON = "2025-26"
HITTER_URL = f"{BASE_URL}/sports/bsb/{SEASON}/players?pos=h&sort=avg&jsRendering=true"
PITCHER_URL = f"{BASE_URL}/sports/bsb/{SEASON}/players?pos=p&sort=era&jsRendering=true"

DATA_DIR = Path("data")
GAME_LOGS_DIR = DATA_DIR / "game_logs"

CACHE_TTL_HOURS = 6       # hours before a game log is re-scraped
AGGREGATE_TTL_HOURS = 6   # hours before hitters.json / pitchers.json is re-scraped

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

def _is_stale(path: Path, max_age_hours: float) -> bool:
    """Return True if path does not exist or its scraped_at timestamp is older than max_age_hours."""
    if not path.exists():
        return True
    try:
        data = json.loads(path.read_text())
        scraped_at = data.get("scraped_at", 0)
    except Exception:
        return True  # unreadable or old-format file → treat as stale
    age = datetime.datetime.now() - datetime.datetime.fromtimestamp(scraped_at)
    return age > datetime.timedelta(hours=max_age_hours)


def _read_cache(path: Path) -> list[dict]:
    """Read a cache file, handling both old bare-array and new envelope formats."""
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("rows", [])


def _write_cache(path: Path, rows: list[dict]) -> None:
    """Write rows to a cache file with an embedded scrape timestamp."""
    path.write_text(json.dumps({"scraped_at": time.time(), "rows": rows}, indent=2))


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

    if path.exists() and not force and not _is_stale(path, AGGREGATE_TTL_HOURS):
        return _read_cache(path)

    try:
        soup = _fetch_soup_playwright(HITTER_URL, wait_col="avg")
        table, headers = _find_table_by_header(soup, "avg")
        if table is None:
            raise RuntimeError("Could not find hitters table on page.")
        rows = _parse_table(table, headers)
        _write_cache(path, rows)
        return rows
    except Exception:
        if path.exists():
            return _read_cache(path)
        raise


def scrape_pitchers(force: bool = False) -> list[dict]:
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / "pitchers.json"

    if path.exists() and not force and not _is_stale(path, AGGREGATE_TTL_HOURS):
        return _read_cache(path)

    try:
        soup = _fetch_soup_playwright(PITCHER_URL, wait_col="era")
        table, headers = _find_table_by_header(soup, "era")
        if table is None:
            raise RuntimeError("Could not find pitchers table on page.")
        rows = _parse_table(table, headers)
        _write_cache(path, rows)
        return rows
    except Exception:
        if path.exists():
            return _read_cache(path)
        raise


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
        timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(f"scrape_worker failed: {result.stderr[:500]}")
    return json.loads(result.stdout)


def _fetch_soup_playwright(url: str, wait_col: str = "", wait_networkidle: bool = False) -> BeautifulSoup:
    """Render a JS-heavy page via the subprocess worker and return parsed soup."""
    results = _run_worker([{"slug": "_single", "url": url, "wait_col": wait_col, "wait_networkidle": wait_networkidle}])
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


def _game_log_path(slug: str, pos: str = "h") -> Path:
    """Return the cache file path for a player's game log."""
    suffix = "_p" if pos == "p" else ""
    return GAME_LOGS_DIR / f"{slug}{suffix}.json"


def read_game_log_cache(slug: str, pos: str = "h") -> tuple[list[dict], float | None]:
    """
    Read a player's game log from cache only — never triggers a scrape.
    pos="h" reads {slug}.json; pos="p" reads {slug}_p.json.
    Returns (rows, scraped_at_timestamp) or ([], None) if no cache file exists.
    """
    path = _game_log_path(slug, pos)
    if not path.exists():
        return [], None
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data, None
        return data.get("rows", []), data.get("scraped_at")
    except Exception:
        return [], None


def scrape_game_log(slug: str, pos: str = "h", force: bool = False) -> list[dict]:
    """
    Fetch and cache a player's game log.
    pos="h" for hitters (looks for batting table with 'ab' column).
    pos="p" for pitchers (looks for pitching table with 'ip' column).
    """
    GAME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = _game_log_path(slug, pos)

    if path.exists() and not force and not _is_stale(path, CACHE_TTL_HOURS):
        return _read_cache(path)

    url = f"{BASE_URL}/sports/bsb/{SEASON}/players/{slug}?view=gamelog"
    wait_col = "ab" if pos == "h" else "ip"

    try:
        soup = _fetch_soup_playwright(url, wait_col=wait_col, wait_networkidle=True)
    except Exception:
        if path.exists():
            return _read_cache(path)
        return []

    rows = _parse_game_log_soup(soup, pos)
    _write_cache(path, rows)
    return rows


def scrape_all_game_logs(
    hitters: list,
    pitchers: list,
    force: bool = False,
    progress_cb=None,
) -> None:
    """
    Bulk-scrape game logs for all players using a single shared Playwright browser.
    Hitters and pitchers use separate seen sets so two-way players get both logs.
    Hitter logs → {slug}.json; pitcher logs → {slug}_p.json.
    progress_cb(current, total, slug) is called before each fetch.
    """
    GAME_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    tasks: list[tuple[str, str]] = []
    seen_h: set[str] = set()
    seen_p: set[str] = set()
    for player, pos in [(p, "h") for p in hitters] + [(p, "p") for p in pitchers]:
        slug = player.get("slug")
        if not slug:
            continue
        seen = seen_h if pos == "h" else seen_p
        if slug in seen:
            continue
        seen.add(slug)
        if force or _is_stale(_game_log_path(slug, pos), CACHE_TTL_HOURS):
            tasks.append((slug, pos))

    if not tasks:
        return

    if progress_cb:
        progress_cb(0, len(tasks), tasks[0][0])

    # Encode pos into the slug field so two-way players can appear twice in worker results
    worker_tasks = [
        {
            "slug": f"{slug}|{pos}",
            "url": f"{BASE_URL}/sports/bsb/{SEASON}/players/{slug}?view=gamelog",
            "wait_col": "ab" if pos == "h" else "ip",
            "wait_networkidle": True,
        }
        for slug, pos in tasks
    ]

    results = _run_worker(worker_tasks)

    for i, result in enumerate(results):
        slug_pos = result["slug"]
        slug, pos = slug_pos.rsplit("|", 1)
        html = result.get("html", "")
        if progress_cb:
            progress_cb(i + 1, len(tasks), slug)
        if not html:
            continue
        try:
            soup = BeautifulSoup(html, "lxml")
            rows = _parse_game_log_soup(soup, pos)
            path = _game_log_path(slug, pos)
            if rows:
                _write_cache(path, rows)
            elif not path.exists():
                _write_cache(path, rows)
            # If rows is empty and an old file exists, keep the old data
        except Exception:
            continue
