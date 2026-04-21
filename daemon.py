"""
daemon.py — Runs refresh_logs.py daily at 22:00 (10 PM).
Launch via start_daemon.bat in the Windows Startup folder.
"""

import subprocess
import sys
import time
from pathlib import Path

import schedule

PROJECT_DIR = Path(__file__).parent
PYTHON = sys.executable
LOG = PROJECT_DIR / "logs" / "refresh_logs.log"


def run_refresh():
    with LOG.open("a") as f:
        subprocess.run(
            [PYTHON, str(PROJECT_DIR / "refresh_logs.py")],
            cwd=str(PROJECT_DIR),
            stdout=f,
            stderr=f,
        )


schedule.every().day.at("22:00").do(run_refresh)

while True:
    schedule.run_pending()
    time.sleep(60)
