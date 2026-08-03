import json

import collect
from common import storage


def test_collect_one_uses_prefetched_stars(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "DATA_DIR", tmp_path)
    monkeypatch.setattr(collect, "_safe_call", lambda func, *a, **kw: 0)
    monkeypatch.setattr(collect.dependents, "get_dependents_count", lambda *a, **kw: 0)

    entry = {"owner": "foo", "repo": "bar"}
    result = collect._collect_one(entry, stars=12345, today="2026-08-03")

    assert result is None
    path = storage.repo_snapshot_path(tmp_path, "foo", "bar")
    snapshots = json.loads(path.read_text(encoding="utf-8"))
    assert snapshots == [{"date": "2026-08-03", "stars": 12345, "hn_mentions": 0, "dependents": 0}]


def test_collect_one_handles_missing_stars_as_none(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "DATA_DIR", tmp_path)
    monkeypatch.setattr(collect, "_safe_call", lambda func, *a, **kw: 0)
    monkeypatch.setattr(collect.dependents, "get_dependents_count", lambda *a, **kw: 0)

    collect._collect_one({"owner": "foo", "repo": "bar"}, stars=None, today="2026-08-03")

    path = storage.repo_snapshot_path(tmp_path, "foo", "bar")
    snapshots = json.loads(path.read_text(encoding="utf-8"))
    assert snapshots[0]["stars"] is None


def test_collect_one_returns_owner_repo_when_repo_is_gone(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "DATA_DIR", tmp_path)

    def raise_gone(*a, **kw):
        raise collect.dependents.RepoGoneError("gone")

    monkeypatch.setattr(collect.dependents, "get_dependents_count", raise_gone)

    result = collect._collect_one({"owner": "ghost", "repo": "repo"}, stars=1, today="2026-08-03")

    assert result == ("ghost", "repo")
    # 404の場合はスナップショットも書かないこと
    assert not storage.repo_snapshot_path(tmp_path, "ghost", "repo").exists()


def test_main_fetches_stars_in_one_batch_call(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setattr(collect, "DATA_DIR", tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    watchlist = [{"owner": "foo", "repo": "bar"}, {"owner": "baz", "repo": "qux"}]
    storage.save_watchlist(tmp_path / "watchlist.json", watchlist)

    captured = {}

    def fake_batch(repos, token):
        captured["repos"] = repos
        captured["token"] = token
        return {("foo", "bar"): 10, ("baz", "qux"): 20}

    monkeypatch.setattr(collect.github_api, "get_repo_stars_batch", fake_batch)
    monkeypatch.setattr(collect.hn_api, "count_daily_mentions", lambda *a, **kw: 0)
    monkeypatch.setattr(collect.dependents, "get_dependents_count", lambda *a, **kw: 0)

    collect.main()

    assert captured["repos"] == [("foo", "bar"), ("baz", "qux")]
    assert captured["token"] == "test-token"

    foo_snapshots = json.loads(storage.repo_snapshot_path(tmp_path, "foo", "bar").read_text(encoding="utf-8"))
    assert foo_snapshots[0]["stars"] == 10


def test_main_removes_gone_repos_from_watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "WATCHLIST_PATH", tmp_path / "watchlist.json")
    monkeypatch.setattr(collect, "DATA_DIR", tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    watchlist = [{"owner": "alive", "repo": "one"}, {"owner": "ghost", "repo": "two"}]
    storage.save_watchlist(tmp_path / "watchlist.json", watchlist)

    monkeypatch.setattr(collect.github_api, "get_repo_stars_batch", lambda repos, token: {})
    monkeypatch.setattr(collect.hn_api, "count_daily_mentions", lambda *a, **kw: 0)

    def fake_dependents(owner, repo):
        if owner == "ghost":
            raise collect.dependents.RepoGoneError("gone")
        return 0

    monkeypatch.setattr(collect.dependents, "get_dependents_count", fake_dependents)

    collect.main()

    remaining = storage.load_json(tmp_path / "watchlist.json")
    assert remaining == [{"owner": "alive", "repo": "one"}]
