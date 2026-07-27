from datetime import datetime, timezone

from common import hn_api


def test_since_timestamp_one_day_back():
    reference = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    expected = int(datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    assert hn_api.since_timestamp(reference, days_back=1) == expected


def test_since_timestamp_custom_window():
    reference = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
    expected = int(datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc).timestamp())
    assert hn_api.since_timestamp(reference, days_back=7) == expected
