#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pathlib import Path

from common import dependents, github_api, hn_api, storage

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"


def _safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        print(f"signal collection failed: {func.__name__}{args}: {exc}")
        return None


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    watchlist = storage.load_watchlist(WATCHLIST_PATH)
    today = datetime.now(timezone.utc).date().isoformat()

    for entry in watchlist:
        owner, repo = entry["owner"], entry["repo"]
        try:
            snapshot = {
                "date": today,
                "stars": _safe_call(github_api.get_repo_stars, owner, repo, token=token),
                "hn_mentions": _safe_call(hn_api.count_daily_mentions, f"{owner}/{repo}"),
                "dependents": _safe_call(dependents.get_dependents_count, owner, repo),
            }
            path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
            storage.append_snapshot(path, snapshot)
            print(f"{owner}/{repo}: {snapshot}")
        except Exception as exc:
            print(f"{owner}/{repo}: skipped due to unexpected error: {exc}")


if __name__ == "__main__":
    main()
