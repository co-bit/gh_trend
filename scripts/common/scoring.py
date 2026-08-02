import math
from datetime import date, timedelta

# スター増加を主シグナルとし、HN言及とDependents増加は補助的な重みにする。
# 後者2つは母集団の99%がゼロ(=非ゼロが極めて稀)で情報量が乏しく、均等重みだと
# 「1件でも獲得したか」という抽選結果が順位を支配してしまうため。
WEIGHTS = {"star": 0.6, "hn": 0.2, "dependents": 0.2}


def compute_percentile(value: float, population: list[float]) -> float:
    """母集団内でのパーセンタイル順位を中間順位(midrank)で返す。

    同値のリポジトリには、その同値グループが占める順位範囲の中央値を与える。
    単純な「自分より小さい値の数 / 母集団」だと、母集団の99%がゼロであるような
    スパースなシグナルで、ゼロ(=まったく普通の状態)のリポジトリ全員が
    「全体最下位」と評価されてしまうため。
    """
    if not population:
        return 0.0
    less = sum(1 for x in population if x < value)
    equal = sum(1 for x in population if x == value)
    return (less + equal / 2) / len(population)


def _velocity_by_delta(snapshots: list[dict], field: str, window_days: int = 7) -> int | None:
    dated = [s for s in snapshots if s.get(field) is not None]
    if len(dated) < 2:
        return None

    dated_sorted = sorted(dated, key=lambda s: s["date"])
    latest = dated_sorted[-1]
    cutoff = (date.fromisoformat(latest["date"]) - timedelta(days=window_days)).isoformat()
    candidates = [s for s in dated_sorted if s["date"] <= cutoff]
    baseline = candidates[-1] if candidates else dated_sorted[0]

    if baseline is latest:
        return None

    days_between = (date.fromisoformat(latest["date"]) - date.fromisoformat(baseline["date"])).days
    if days_between <= 0:
        return None

    raw_delta = latest[field] - baseline[field]
    return round((raw_delta / days_between) * window_days)


def compute_star_velocity(snapshots: list[dict]) -> int | None:
    return _velocity_by_delta(snapshots, "stars")


def compute_dependents_velocity(snapshots: list[dict]) -> int | None:
    return _velocity_by_delta(snapshots, "dependents")


def compute_hn_velocity(snapshots: list[dict], window_days: int = 7) -> int | None:
    dated = [s for s in snapshots if s.get("hn_mentions") is not None]
    if not dated:
        return None

    dated_sorted = sorted(dated, key=lambda s: s["date"])
    latest_date = dated_sorted[-1]["date"]
    cutoff = (date.fromisoformat(latest_date) - timedelta(days=window_days)).isoformat()
    windowed = [s for s in dated_sorted if s["date"] >= cutoff]
    return sum(s["hn_mentions"] for s in windowed)


def compute_star_momentum(velocity: int | None, stars: int | None) -> float | None:
    """絶対増加数と相対成長率の幾何平均を返す(合成スコア用)。

    `velocity / sqrt(stars)` は `sqrt(velocity × (velocity / stars))` と等しく、
    「絶対的な動きの大きさ」と「相対的な勢い」の幾何平均になる。

    絶対増加数のみだと大規模リポジトリが構造的に有利になり(198,894スターの
    リポジトリの週+987は平常運転でニュース性がない)、相対成長率のみだと
    小規模リポジトリのノイズが支配する(5スターが4増えて80%成長)。
    幾何平均は両者の中間を取り、恣意的なパラメータを持たない。
    """
    if velocity is None or stars is None:
        return None
    return velocity / math.sqrt(max(stars, 1))


def compute_composite(percentiles: dict[str, float | None], weights: dict[str, float]) -> float | None:
    available = {k: v for k, v in percentiles.items() if v is not None}
    if not available:
        return None
    weight_sum = sum(weights[k] for k in available)
    weighted = sum(percentiles[k] * weights[k] for k in available)
    return weighted / weight_sum
