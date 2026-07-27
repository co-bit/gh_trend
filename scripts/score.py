#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

from common import scoring, storage

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
LATEST_SCORES_PATH = DATA_DIR / "latest_scores.json"

SIGNALS = ("star", "hn", "dependents")


def main() -> None:
    watchlist = storage.load_watchlist(WATCHLIST_PATH)
    today = datetime.now(timezone.utc).date().isoformat()

    velocities: dict[tuple[str, str], dict[str, int | None]] = {}
    latest_snapshot: dict[tuple[str, str], dict] = {}

    for entry in watchlist:
        owner, repo = entry["owner"], entry["repo"]
        path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
        snapshots = storage.load_snapshots(path)
        if not snapshots:
            continue

        latest = sorted(snapshots, key=lambda s: s["date"])[-1]
        if latest["date"] != today:
            # 当日分のスナップショットが無いリポジトリは母集団・出力から除外する
            # (collect.pyが正常なら通常発生しないが、古いデータが紛れ込むのを防ぐ)
            continue

        key = (owner, repo)
        latest_snapshot[key] = latest
        velocities[key] = {
            "star": scoring.compute_star_velocity(snapshots),
            "hn": scoring.compute_hn_velocity(snapshots),
            "dependents": scoring.compute_dependents_velocity(snapshots),
        }

    populations: dict[str, list[float]] = {signal: [] for signal in SIGNALS}
    for v in velocities.values():
        for signal in SIGNALS:
            if v[signal] is not None:
                populations[signal].append(v[signal])

    repos_out = []
    for (owner, repo), v in velocities.items():
        percentiles = {
            signal: (
                scoring.compute_percentile(v[signal], populations[signal])
                if v[signal] is not None
                else None
            )
            for signal in SIGNALS
        }
        composite = scoring.compute_composite(percentiles, scoring.WEIGHTS)
        latest = latest_snapshot[(owner, repo)]

        repos_out.append(
            {
                "owner": owner,
                "repo": repo,
                "stars": latest.get("stars"),
                "star_velocity": v["star"],
                "star_percentile": percentiles["star"],
                "hn_mentions_7d": v["hn"],
                "hn_percentile": percentiles["hn"],
                "dependents": latest.get("dependents"),
                "dependents_velocity": v["dependents"],
                "dependents_percentile": percentiles["dependents"],
                "composite": composite,
            }
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos_out,
    }
    LATEST_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_SCORES_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"scored {len(repos_out)} repos")


if __name__ == "__main__":
    main()
