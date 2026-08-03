#!/usr/bin/env python3
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from common import dependents, github_api, hn_api, storage

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
MAX_WORKERS = 30  # I/O-bound network calls (HN・dependents); star数はGraphQLで別途一括取得


def _safe_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        print(f"signal collection failed: {func.__name__}{args}: {exc}")
        return None


def _collect_one(entry: dict, stars: int | None, today: str) -> None:
    owner, repo = entry["owner"], entry["repo"]
    try:
        snapshot = {
            "date": today,
            "stars": stars,
            "hn_mentions": _safe_call(hn_api.count_daily_mentions, f"{owner}/{repo}"),
            "dependents": _safe_call(dependents.get_dependents_count, owner, repo),
        }
        path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
        storage.append_snapshot(path, snapshot)
        print(f"{owner}/{repo}: {snapshot}")
    except Exception as exc:
        print(f"{owner}/{repo}: skipped due to unexpected error: {exc}")


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    watchlist = storage.iter_valid_entries(storage.load_json(WATCHLIST_PATH))
    today = datetime.now(timezone.utc).date().isoformat()

    # star数はリポジトリ1件ごとのREST呼び出しではなく、事前にGraphQLで
    # 一括取得する(数千件をREST 1件ずつ叩くとレート制限に達し欠損する)。
    repo_keys = [(entry["owner"], entry["repo"]) for entry in watchlist]
    stars_by_repo = github_api.get_repo_stars_batch(repo_keys, token) if token else {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                _collect_one, entry, stars_by_repo.get((entry["owner"], entry["repo"])), today
            )
            for entry in watchlist
        ]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
