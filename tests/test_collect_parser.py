import time
from pathlib import Path

import pytest

from common import dependents

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_dependents_count_with_comma_and_repositories_label():
    html = (FIXTURES / "dependents_sample.html").read_text(encoding="utf-8")
    assert dependents.parse_dependents_count(html) == 1234


def test_parse_dependents_count_with_k_suffix():
    html = '<a href="/x/y/network/dependents">2.5k Repositories</a>'
    assert dependents.parse_dependents_count(html) == 2500


def test_parse_dependents_count_supports_legacy_used_by_label():
    html = '<a href="/x/y/network/dependents">3,000 Used by</a>'
    assert dependents.parse_dependents_count(html) == 3000


def test_parse_dependents_count_missing_returns_none():
    html = "<html><body>No dependents info here</body></html>"
    assert dependents.parse_dependents_count(html) is None


def test_parse_dependents_count_ignores_bare_comma_before_repositories_word():
    html = (
        "<html><body>"
        "<p>Search code, repositories, users, issues, pull requests...</p>"
        '<a href="/x/y/network/dependents">1,234 Repositories</a>'
        "</body></html>"
    )
    assert dependents.parse_dependents_count(html) == 1234


def test_get_dependents_count_honors_retry_after_header_on_429(monkeypatch):
    sleeps = []
    monkeypatch.setattr(dependents.time, "sleep", lambda s: sleeps.append(s))

    class RateLimitedResponse:
        status_code = 429
        headers = {"Retry-After": "3"}

    monkeypatch.setattr(dependents.requests, "get", lambda *a, **kw: RateLimitedResponse())

    result = dependents.get_dependents_count("foo", "bar", max_retries=2)

    assert result is None
    # 固定の指数バックオフ(1, 2)ではなく、Retry-Afterの3秒が使われること
    assert sleeps == [3.0, 3.0]


def test_get_dependents_count_raises_repo_gone_error_on_404_without_retry(monkeypatch):
    calls = []

    class NotFoundResponse:
        status_code = 404
        headers = {}

    def fake_get(*a, **kw):
        calls.append(1)
        return NotFoundResponse()

    monkeypatch.setattr(dependents.requests, "get", fake_get)

    with pytest.raises(dependents.RepoGoneError):
        dependents.get_dependents_count("ghost", "repo", max_retries=3)

    # 404は復活しないので、max_retriesに関わらず1回しか叩かないこと
    assert len(calls) == 1


def test_get_dependents_count_limits_concurrent_requests(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    state = {"current": 0, "peak": 0}

    class FakeResponse:
        status_code = 200

        @property
        def text(self):
            return "1 Repositories"

    def fake_get(*a, **kw):
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        return FakeResponse()

    monkeypatch.setattr(dependents.requests, "get", fake_get)

    with ThreadPoolExecutor(max_workers=dependents.MAX_CONCURRENT_REQUESTS * 3) as executor:
        list(executor.map(lambda i: dependents.get_dependents_count(f"o{i}", f"r{i}"), range(dependents.MAX_CONCURRENT_REQUESTS * 3)))

    assert state["peak"] <= dependents.MAX_CONCURRENT_REQUESTS
