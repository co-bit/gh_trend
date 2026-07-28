from common import github_api


def test_extract_owner_repo_from_search_item_valid():
    item = {"full_name": "modelcontextprotocol/servers"}
    assert github_api.extract_owner_repo_from_search_item(item) == ("modelcontextprotocol", "servers")


def test_extract_owner_repo_from_search_item_missing_full_name():
    assert github_api.extract_owner_repo_from_search_item({}) is None


def test_extract_owner_repo_from_search_item_malformed():
    assert github_api.extract_owner_repo_from_search_item({"full_name": "no-slash"}) is None


def test_rate_limit_wait_seconds_uses_retry_after_header():
    class FakeResponse:
        headers = {"Retry-After": "5"}

    assert github_api._rate_limit_wait_seconds(FakeResponse(), attempt=0) == 5.0


def test_rate_limit_wait_seconds_caps_retry_after_at_65():
    class FakeResponse:
        headers = {"Retry-After": "200"}

    assert github_api._rate_limit_wait_seconds(FakeResponse(), attempt=0) == 65


def test_rate_limit_wait_seconds_uses_ratelimit_reset_header(monkeypatch):
    monkeypatch.setattr(github_api.time, "time", lambda: 1000.0)

    class FakeResponse:
        headers = {"x-ratelimit-reset": "1030"}

    assert github_api._rate_limit_wait_seconds(FakeResponse(), attempt=0) == 30


def test_rate_limit_wait_seconds_falls_back_to_exponential_backoff():
    class FakeResponse:
        headers = {}

    assert github_api._rate_limit_wait_seconds(FakeResponse(), attempt=2) == 4
