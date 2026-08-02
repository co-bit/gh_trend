import json
from datetime import date, timedelta
from pathlib import Path


def load_json(path: Path) -> list[dict]:
    """watchlist・スナップショット共通のローダ。ファイルが無ければ空リスト。"""
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_watchlist(path: Path, watchlist: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_watchlist(watchlist: list[dict], owner: str, repo: str, source: str, today: str) -> list[dict]:
    existing = {(entry["owner"], entry["repo"]) for entry in watchlist}
    if (owner, repo) not in existing:
        watchlist.append({"owner": owner, "repo": repo, "first_seen": today, "source": source})
    return watchlist


def repo_snapshot_path(data_dir: Path, owner: str, repo: str) -> Path:
    return data_dir / "repos" / f"{owner}__{repo}.json"


def append_snapshot(path: Path, snapshot: dict, retention_days: int = 90) -> None:
    snapshots = load_json(path)
    snapshots = [s for s in snapshots if s["date"] != snapshot["date"]]
    snapshots.append(snapshot)

    cutoff = (date.fromisoformat(snapshot["date"]) - timedelta(days=retention_days)).isoformat()
    snapshots = [s for s in snapshots if s["date"] >= cutoff]
    snapshots.sort(key=lambda s: s["date"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8")
