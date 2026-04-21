"""
refresh_logs.py — Local data updater.

Scrapes aggregate stats and all player game logs, then recomputes the
leaderboard totals directly from game logs so they always stay in sync
even if mascac.com's stats page lags behind their game log pages.

Must be run locally (residential IP) — the Sidearm Sports backend blocks
datacenter IPs used by services like GitHub Actions.

Usage:
    python refresh_logs.py
"""

import json
import subprocess
import time
from pathlib import Path

import scraper

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Aggregate computation from game logs
# ---------------------------------------------------------------------------

def _s(rows, field):
    """Sum a field across game log rows, treating None as 0."""
    return sum(r.get(field) or 0 for r in rows)


def _compute_hitter_totals(player, rows):
    """Update hitter counting stats from game logs; scraped avg/obp/slg are kept as-is."""
    go = _s(rows, 'go'); fo = _s(rows, 'fo')
    return {**player,
            'gp': _s(rows, 'gp'),
            'ab': _s(rows, 'ab'), 'h': _s(rows, 'h'), 'rbi': _s(rows, 'rbi'),
            'bb': _s(rows, 'bb'), '2b': _s(rows, '2b'), '3b': _s(rows, '3b'),
            'hr': _s(rows, 'hr'), 'xbh': _s(rows, 'xbh'), 'k': _s(rows, 'k'),
            'hbp': _s(rows, 'hbp'), 'sf': _s(rows, 'sf'), 'sh': _s(rows, 'sh'),
            'hdp': _s(rows, 'hdp'), 'go': go, 'fo': fo,
            'go/fo': round(go / fo, 2) if fo else None,
            'pa': _s(rows, 'pa')}


def _compute_pitcher_totals(player, rows, scraped):
    """Recompute season totals for a pitcher from their per-game log rows.

    Fields absent from game logs (bb, gs, sv, bf, wp, hbp) are kept from
    the scraped aggregate so whip and other derived stats stay accurate.
    """
    ip = _s(rows, 'ip')
    er = _s(rows, 'er')
    k  = _s(rows, 'k')

    return {**player,
            'era':  round(9 * er / ip, 2) if ip else None,
            'w':    _s(rows, 'w'),  'l':  _s(rows, 'l'),
            'app':  len(rows),
            'gs':   scraped.get('gs'),   'sv':  scraped.get('sv'),
            'ip':   ip,
            'h':    _s(rows, 'h'),  'r':  _s(rows, 'r'),  'er': er,
            'bb':   scraped.get('bb'),   'k':   k,
            'k/9':  round(9 * k / ip, 1) if ip else None,
            'hr':   _s(rows, 'hr'),
            'whip': scraped.get('whip'),
            'bf':   scraped.get('bf'),
            'wp':   scraped.get('wp'),
            'hbp':  scraped.get('hbp')}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Scraping aggregate stats...")
    hitters = scraper.scrape_hitters(force=True)
    pitchers = scraper.scrape_pitchers(force=True)
    print(f"  {len(hitters)} hitters, {len(pitchers)} pitchers")

    slugs = {p["slug"] for p in hitters + pitchers if p.get("slug")}
    print(f"Scraping game logs for {len(slugs)} players...")

    def progress(cur, total, slug):
        print(f"  [{cur}/{total}] {slug}")

    scraper.scrape_all_game_logs(hitters, pitchers, force=True, progress_cb=progress)

    # Recompute leaderboard totals from freshly-scraped game logs so they
    # stay current even when mascac.com's stats page lags behind.
    print("\nComputing totals from game logs...")
    scraped_pitchers = {p["slug"]: p for p in pitchers if p.get("slug")}

    computed_hitters = []
    for player in hitters:
        slug = player.get("slug")
        if slug:
            rows, _ = scraper.read_game_log_cache(slug, pos="h")
            if rows:
                player = _compute_hitter_totals(player, rows)
        computed_hitters.append(player)

    computed_pitchers = []
    for player in pitchers:
        slug = player.get("slug")
        if slug:
            rows, _ = scraper.read_game_log_cache(slug, pos="p")
            if rows:
                player = _compute_pitcher_totals(player, rows, scraped_pitchers.get(slug, {}))
        computed_pitchers.append(player)

    now = time.time()
    (DATA_DIR / "hitters.json").write_text(
        json.dumps({"scraped_at": now, "rows": computed_hitters}, indent=2)
    )
    (DATA_DIR / "pitchers.json").write_text(
        json.dumps({"scraped_at": now, "rows": computed_pitchers}, indent=2)
    )
    print(f"  {len(computed_hitters)} hitters, {len(computed_pitchers)} pitchers written")

    print("\nScrape complete. Committing and pushing...")

    subprocess.run(["git", "add", "data/"], check=True)
    staged = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if staged.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "Refresh all MASCAC data (local scrape)"],
            check=True,
        )
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "master"], check=True)
        result = subprocess.run(["git", "push", "origin", "master"], capture_output=True, text=True)
        if result.returncode == 0:
            print("Done — changes pushed to GitHub.")
        else:
            print(f"Warning: push failed. stderr: {result.stderr.strip()}")
    else:
        print("Done — no changes (all data already up to date).")


if __name__ == "__main__":
    main()
