from common import ranking


def _repo(name: str, **overrides) -> dict:
    base = {
        "owner": "org",
        "repo": name,
        "composite": 0.5,
        "star_velocity": 10,
        "hn_mentions_7d": 1,
        "dependents_velocity": 2,
    }
    base.update(overrides)
    return base


def test_top_by_sorts_descending_and_truncates():
    repos = [_repo(f"r{i}", composite=i / 10) for i in range(10)]
    result = ranking.top_by(repos, "composite", n=3)
    assert [r["repo"] for r in result] == ["r9", "r8", "r7"]


def test_top_by_excludes_none_values():
    repos = [_repo("a", composite=None), _repo("b", composite=0.5)]
    result = ranking.top_by(repos, "composite")
    assert [r["repo"] for r in result] == ["b"]


def test_ranked_tables_returns_four_tables_with_titles_and_highlights():
    repos = [_repo("a")]
    tables = ranking.ranked_tables(repos)
    assert [(title, highlight) for title, _, highlight in tables] == [
        ("総合トレンドランキング", "composite"),
        ("スター急上昇", "star"),
        ("Hacker News話題", "hn"),
        ("Dependents急増", "dependents"),
    ]


def test_displayed_repo_names_unions_all_four_rankings():
    # 各シグナルで別々のリポジトリが1位になるよう仕込む
    repos = [
        _repo("top-composite", composite=1.0, star_velocity=0, hn_mentions_7d=0, dependents_velocity=0),
        _repo("top-star", composite=0.0, star_velocity=999, hn_mentions_7d=0, dependents_velocity=0),
        _repo("top-hn", composite=0.0, star_velocity=0, hn_mentions_7d=999, dependents_velocity=0),
        _repo("top-dep", composite=0.0, star_velocity=0, hn_mentions_7d=0, dependents_velocity=999),
    ]
    names = ranking.displayed_repo_names(repos, n=1)
    assert names == {"org/top-composite", "org/top-star", "org/top-hn", "org/top-dep"}


def test_displayed_repo_names_excludes_repos_outside_top_n():
    repos = [_repo(f"r{i}", composite=i / 30, star_velocity=i, hn_mentions_7d=i, dependents_velocity=i) for i in range(30)]
    names = ranking.displayed_repo_names(repos, n=20)
    assert "org/r29" in names
    assert "org/r9" not in names
