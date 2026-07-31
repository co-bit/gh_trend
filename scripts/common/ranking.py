"""ランキング選定ロジック。

render.py(HTML出力)とdescribe.py(概要生成)の両方が「どのリポジトリが
実際にダッシュボードに表示されるか」を同じ基準で判定する必要があるため、
ここに集約する。
"""

TOP_N = 20

# (表のタイトル, ソートキー, ハイライト対象のシグナル名)
RANKINGS = (
    ("総合トレンドランキング", "composite", "composite"),
    ("スター急上昇", "star_velocity", "star"),
    ("Hacker News話題", "hn_mentions_7d", "hn"),
    ("Dependents急増", "dependents_velocity", "dependents"),
)


def top_by(repos: list[dict], key: str, n: int = TOP_N) -> list[dict]:
    return sorted(
        (r for r in repos if r.get(key) is not None),
        key=lambda r: r[key],
        reverse=True,
    )[:n]


def ranked_tables(repos: list[dict], n: int = TOP_N) -> list[tuple[str, list[dict], str]]:
    return [(title, top_by(repos, key, n), highlight) for title, key, highlight in RANKINGS]


def displayed_repo_names(repos: list[dict], n: int = TOP_N) -> set[str]:
    """4つの表のいずれかに表示されるリポジトリの `owner/repo` 集合を返す。"""
    names = set()
    for _, ranked, _ in ranked_tables(repos, n):
        for repo in ranked:
            names.add(f"{repo['owner']}/{repo['repo']}")
    return names
