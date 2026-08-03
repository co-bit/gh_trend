from common import storage


def test_load_watchlist_missing_file_returns_empty(tmp_path):
    path = tmp_path / "watchlist.json"
    assert storage.load_json(path) == []


def test_save_and_load_watchlist_roundtrip(tmp_path):
    path = tmp_path / "watchlist.json"
    data = [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-27", "source": "search:mcp-server"}]
    storage.save_watchlist(path, data)
    assert storage.load_json(path) == data


def test_iter_valid_entries_keeps_well_formed_entries():
    watchlist = [{"owner": "foo", "repo": "bar"}, {"owner": "baz", "repo": "qux"}]
    assert storage.iter_valid_entries(watchlist) == watchlist


def test_iter_valid_entries_skips_entries_missing_owner_or_repo(capsys):
    watchlist = [
        {"owner": "foo", "repo": "bar"},
        {"owner": "no-repo-key"},
        {"repo": "no-owner-key"},
    ]
    result = storage.iter_valid_entries(watchlist)
    assert result == [{"owner": "foo", "repo": "bar"}]
    assert "skipping malformed watchlist entry" in capsys.readouterr().out


def test_add_to_watchlist_appends_new_entry():
    watchlist = []
    result = storage.add_to_watchlist(watchlist, "foo", "bar", "search:mcp-server", "2026-07-27")
    assert result == [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-27", "source": "search:mcp-server"}]


def test_add_to_watchlist_skips_duplicate():
    watchlist = [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-01", "source": "search:mcp-server"}]
    result = storage.add_to_watchlist(watchlist, "foo", "bar", "search:agent-skills", "2026-07-27")
    assert len(result) == 1
    assert result[0]["first_seen"] == "2026-07-01"


def test_repo_snapshot_path_uses_double_underscore(tmp_path):
    path = storage.repo_snapshot_path(tmp_path, "foo", "bar")
    assert path == tmp_path / "repos" / "foo__bar.json"


def test_append_snapshot_creates_file(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1})
    assert storage.load_json(path) == [
        {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1}
    ]


def test_append_snapshot_replaces_same_day_entry(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1})
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 15, "hn_mentions": 1, "dependents": 1})
    snapshots = storage.load_json(path)
    assert len(snapshots) == 1
    assert snapshots[0]["stars"] == 15


def test_append_snapshot_prunes_entries_older_than_retention(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(
        path, {"date": "2026-01-01", "stars": 1, "hn_mentions": 0, "dependents": 0}, retention_days=90
    )
    storage.append_snapshot(
        path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1}, retention_days=90
    )
    snapshots = storage.load_json(path)
    assert len(snapshots) == 1
    assert snapshots[0]["date"] == "2026-07-27"
