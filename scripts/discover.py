#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pathlib import Path

from common import github_api, storage

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"

KEYWORDS = [
    "topic:mcp-server",
    "topic:model-context-protocol",
    "topic:agent-skills",
    "topic:llm-tools",
    "topic:ai-agent-toolkit",
    "topic:claude-skill",
    "topic:claude-code",
]


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    watchlist = storage.iter_valid_entries(storage.load_json(WATCHLIST_PATH))
    today = datetime.now(timezone.utc).date().isoformat()
    before = len(watchlist)

    for keyword in KEYWORDS:
        for hit in github_api.search_repos(keyword, token=token):
            watchlist = storage.add_to_watchlist(
                watchlist, hit["owner"], hit["repo"], f"search:{keyword}", today
            )

    storage.save_watchlist(WATCHLIST_PATH, watchlist)
    print(f"watchlist: {before} -> {len(watchlist)} repos")


if __name__ == "__main__":
    main()
