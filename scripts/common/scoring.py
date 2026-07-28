from datetime import date, timedelta

WEIGHTS = {"star": 1 / 3, "hn": 1 / 3, "dependents": 1 / 3}


def compute_percentile(value: float, population: list[float]) -> float:
    if not population:
        return 0.0
    less = sum(1 for x in population if x < value)
    return less / len(population)


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


def compute_composite(percentiles: dict[str, float | None], weights: dict[str, float]) -> float | None:
    available = {k: v for k, v in percentiles.items() if v is not None}
    if not available:
        return None
    weight_sum = sum(weights[k] for k in available)
    weighted = sum(percentiles[k] * weights[k] for k in available)
    return weighted / weight_sum
