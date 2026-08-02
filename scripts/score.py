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
    watchlist = storage.load_json(WATCHLIST_PATH)

    all_snapshots: dict[tuple[str, str], list[dict]] = {}
    newest: dict[tuple[str, str], dict] = {}

    for entry in watchlist:
        owner, repo = entry["owner"], entry["repo"]
        path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
        snapshots = storage.load_json(path)
        if not snapshots:
            continue
        all_snapshots[(owner, repo)] = snapshots
        newest[(owner, repo)] = max(snapshots, key=lambda s: s["date"])

    if not newest:
        if watchlist:
            raise SystemExit("no snapshots found for any watchlist repo; refusing to publish an empty dashboard")
        print("scored 0 repos (empty watchlist)")
        return

    # "today" はwall clockではなく、実際に収集された最新スナップショットの日付から
    # 導出する。collect.pyとscore.pyが別々にwall clockのtodayを計算すると、UTC
    # 深夜をまたぐ実行で日付がずれ、母集団が0件になり得るため。
    today = max(s["date"] for s in newest.values())

    velocities: dict[tuple[str, str], dict[str, int | None]] = {}
    latest_snapshot: dict[tuple[str, str], dict] = {}

    for key, snapshots in all_snapshots.items():
        latest = newest[key]
        if latest["date"] != today:
            # 当日分のスナップショットが無いリポジトリは母集団・出力から除外する
            continue

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

    # 合成スコアのスター成分には、絶対増加数そのものではなく「勢い」
    # (絶対増加数と相対成長率の幾何平均)を使う。絶対増加数だけだと大規模
    # リポジトリの平常運転が上位を占めてしまうため。「スター急上昇」表の
    # 並び順とタイントには従来どおり絶対増加数のパーセンタイルを使う。
    momentums: dict[tuple[str, str], float | None] = {}
    for key, v in velocities.items():
        momentums[key] = scoring.compute_star_momentum(
            v["star"], latest_snapshot[key].get("stars")
        )
    momentum_population = [m for m in momentums.values() if m is not None]

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

        momentum = momentums[(owner, repo)]
        momentum_percentile = (
            scoring.compute_percentile(momentum, momentum_population)
            if momentum is not None
            else None
        )

        composite = scoring.compute_composite(
            {**percentiles, "star": momentum_percentile}, scoring.WEIGHTS
        )
        latest = latest_snapshot[(owner, repo)]
        stars = latest.get("stars")

        repos_out.append(
            {
                "owner": owner,
                "repo": repo,
                "stars": stars,
                "star_velocity": v["star"],
                "star_percentile": percentiles["star"],
                "star_growth_rate": v["star"] / stars * 100 if v["star"] is not None and stars else None,
                "star_momentum_percentile": momentum_percentile,
                "hn_mentions_7d": v["hn"],
                "hn_percentile": percentiles["hn"],
                "dependents": latest.get("dependents"),
                "dependents_velocity": v["dependents"],
                "dependents_percentile": percentiles["dependents"],
                "composite": composite,
            }
        )

    if watchlist and not repos_out:
        raise SystemExit("no same-day snapshots after filtering; refusing to publish an empty dashboard")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos_out,
    }
    LATEST_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_SCORES_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"scored {len(repos_out)} repos")


if __name__ == "__main__":
    main()
