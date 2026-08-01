from common import scoring


def test_compute_percentile_middle_value():
    # 中間順位: 自分より小さい2件 + 自分自身の同値グループの半分(0.5) = 2.5 / 5
    assert scoring.compute_percentile(5, [1, 3, 5, 7, 9]) == 2.5 / 5


def test_compute_percentile_lowest_value():
    assert scoring.compute_percentile(1, [1, 3, 5]) == 0.5 / 3


def test_compute_percentile_highest_value():
    assert scoring.compute_percentile(5, [1, 3, 5]) == 2.5 / 3


def test_compute_percentile_single_population():
    assert scoring.compute_percentile(10, [10]) == 0.5


def test_compute_percentile_all_equal():
    # 全員が同値なら全員が「ちょうど真ん中」であるべき(全員最下位ではない)
    assert scoring.compute_percentile(5, [5, 5, 5]) == 0.5


def test_compute_percentile_empty_population():
    assert scoring.compute_percentile(5, []) == 0.0


def test_compute_percentile_sparse_zero_mass_is_treated_as_typical():
    # 母集団の大半がゼロというスパースなシグナルを想定する。
    # ゼロは「まったく普通の状態」なので中央付近に、非ゼロは上位に来る必要がある。
    population = [0] * 99 + [5]
    assert scoring.compute_percentile(0, population) == 0.495
    assert scoring.compute_percentile(5, population) == 0.995


def test_compute_star_velocity_with_full_week():
    snapshots = [
        {"date": "2026-07-20", "stars": 100},
        {"date": "2026-07-27", "stars": 150},
    ]
    assert scoring.compute_star_velocity(snapshots) == 50


def test_compute_star_velocity_insufficient_history():
    snapshots = [{"date": "2026-07-27", "stars": 150}]
    assert scoring.compute_star_velocity(snapshots) is None


def test_compute_star_velocity_ignores_null_entries():
    snapshots = [
        {"date": "2026-07-20", "stars": None},
        {"date": "2026-07-21", "stars": 90},
        {"date": "2026-07-27", "stars": 150},
    ]
    # baseline is 2026-07-21 (6 days before latest), raw delta 60 over 6 days
    # -> normalized to a 7-day-equivalent rate: (60 / 6) * 7 = 70
    assert scoring.compute_star_velocity(snapshots) == 70


def test_compute_star_velocity_normalizes_short_window_to_seven_days():
    snapshots = [
        {"date": "2026-07-26", "stars": 100},
        {"date": "2026-07-27", "stars": 110},
    ]
    # 10 stars over 1 day -> normalized to a 7-day-equivalent rate of 70,
    # so a 1-day-old repo is comparable to a repo with a full 7-day history
    assert scoring.compute_star_velocity(snapshots) == 70


def test_compute_hn_velocity_sums_last_seven_days():
    snapshots = [
        {"date": "2026-07-21", "hn_mentions": 1},
        {"date": "2026-07-22", "hn_mentions": 2},
        {"date": "2026-07-27", "hn_mentions": 3},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 6


def test_compute_hn_velocity_skips_null_entries():
    snapshots = [
        {"date": "2026-07-26", "hn_mentions": None},
        {"date": "2026-07-27", "hn_mentions": 4},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 4


def test_compute_hn_velocity_no_data_returns_none():
    snapshots = [{"date": "2026-07-27", "hn_mentions": None}]
    assert scoring.compute_hn_velocity(snapshots) is None


def test_compute_hn_velocity_ignores_entries_outside_calendar_window():
    snapshots = [
        {"date": "2026-01-01", "hn_mentions": 100},
        {"date": "2026-07-25", "hn_mentions": 1},
        {"date": "2026-07-26", "hn_mentions": 2},
        {"date": "2026-07-27", "hn_mentions": 3},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 6


def test_compute_dependents_velocity():
    snapshots = [
        {"date": "2026-07-20", "dependents": 10},
        {"date": "2026-07-27", "dependents": 25},
    ]
    assert scoring.compute_dependents_velocity(snapshots) == 15


def test_compute_composite_all_signals_present():
    percentiles = {"star": 0.9, "hn": 0.6, "dependents": 0.3}
    result = scoring.compute_composite(percentiles, scoring.WEIGHTS)
    w = scoring.WEIGHTS
    expected = (0.9 * w["star"] + 0.6 * w["hn"] + 0.3 * w["dependents"]) / sum(w.values())
    assert round(result, 4) == round(expected, 4)


def test_compute_composite_missing_signal_excluded():
    percentiles = {"star": 0.9, "hn": None, "dependents": 0.3}
    result = scoring.compute_composite(percentiles, scoring.WEIGHTS)
    w = scoring.WEIGHTS
    # 欠損シグナルは分子・分母の双方から除外される(0点扱いにしない)
    expected = (0.9 * w["star"] + 0.3 * w["dependents"]) / (w["star"] + w["dependents"])
    assert round(result, 4) == round(expected, 4)


def test_star_weight_dominates_the_sparse_signals_combined():
    # 99%がゼロのスパースなシグナル2つの合計より、スター増加の重みが大きいこと。
    # これを割ると「HN言及を1件獲得したか」という抽選が順位を支配し始める。
    w = scoring.WEIGHTS
    assert w["star"] > w["hn"] + w["dependents"]


def test_compute_composite_all_missing_returns_none():
    percentiles = {"star": None, "hn": None, "dependents": None}
    assert scoring.compute_composite(percentiles, scoring.WEIGHTS) is None
