"""
refresh_logs.py — Local game log updater.

Run this script on your local machine to scrape all player game logs
and push the updated data to GitHub. Must be run locally (residential IP)
because the Sidearm Sports backend blocks datacenter IPs used by GitHub Actions.

Usage:
    python refresh_logs.py

Schedule with Windows Task Scheduler for automatic updates:
    Action: python "C:\\path\\to\\mascac\\refresh_logs.py"
    Start in: C:\\path\\to\\mascac
"""

import subprocess
import sys
import scraper


def main():
    print("Loading rosters...")
    hitters = scraper.scrape_hitters()
    pitchers = scraper.scrape_pitchers()

    slugs = {p["slug"] for p in hitters + pitchers if p.get("slug")}
    print(f"Scraping game logs for {len(slugs)} players...")

    counts = {"ok": 0, "skipped": 0}

    def progress(cur, total, slug):
        if cur > 0:
            counts["ok"] += 1
        print(f"  [{cur}/{total}] {slug}")

    scraper.scrape_all_game_logs(hitters, pitchers, force=True, progress_cb=progress)

    print(f"\nScrape complete. Committing and pushing...")

    subprocess.run(["git", "add", "data/game_logs/"], check=True)
    staged = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if staged.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", "Refresh game logs (local scrape)"],
            check=True,
        )
        subprocess.run(["git", "pull", "--rebase", "origin", "master"], check=True)
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("Done — changes pushed to GitHub.")
    else:
        print("Done — no changes (all logs already up to date).")


if __name__ == "__main__":
    main()
