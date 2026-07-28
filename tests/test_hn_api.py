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


def test_count_daily_mentions_uses_exact_phrase_query(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"nbHits": 3}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return FakeResponse()

    monkeypatch.setattr(hn_api.requests, "get", fake_get)
    result = hn_api.count_daily_mentions("foo/bar")

    assert result == 3
    assert captured["params"]["query"] == '"foo/bar"'
    assert captured["params"]["advancedSyntax"] == "true"
