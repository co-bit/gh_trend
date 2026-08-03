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


def test_get_repo_stars_batch_maps_results_by_alias(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "r0": {"stargazerCount": 100},
                    "r1": {"stargazerCount": 200},
                }
            }

    captured = {}

    def fake_post(url, headers=None, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["query"] = json["query"]
        return FakeResponse()

    monkeypatch.setattr(github_api.requests, "post", fake_post)

    result = github_api.get_repo_stars_batch([("foo", "bar"), ("baz", "qux")], "test-token")

    assert result == {("foo", "bar"): 100, ("baz", "qux"): 200}
    assert captured["url"] == github_api.GRAPHQL_URL
    assert 'r0: repository(owner: "foo", name: "bar")' in captured["query"]
    assert 'r1: repository(owner: "baz", name: "qux")' in captured["query"]


def test_get_repo_stars_batch_missing_repo_maps_to_none(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            # renamed/deleted repos come back as a null node, not an error
            return {"data": {"r0": None}}

    monkeypatch.setattr(github_api.requests, "post", lambda *a, **kw: FakeResponse())

    result = github_api.get_repo_stars_batch([("ghost", "repo")], "test-token")
    assert result == {("ghost", "repo"): None}


def test_get_repo_stars_batch_splits_into_multiple_requests(monkeypatch):
    call_count = {"n": 0}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": {}}

    def fake_post(*a, **kw):
        call_count["n"] += 1
        return FakeResponse()

    monkeypatch.setattr(github_api.requests, "post", fake_post)

    repos = [(f"o{i}", f"r{i}") for i in range(github_api.GRAPHQL_BATCH_SIZE + 1)]
    github_api.get_repo_stars_batch(repos, "test-token")

    assert call_count["n"] == 2


def test_get_repo_stars_batch_request_failure_maps_batch_to_none(monkeypatch):
    class FakeResponse:
        status_code = 403
        headers = {}

    monkeypatch.setattr(github_api.requests, "post", lambda *a, **kw: FakeResponse())
    monkeypatch.setattr(github_api.time, "sleep", lambda *_: None)

    result = github_api.get_repo_stars_batch([("foo", "bar")], "test-token")
    assert result == {("foo", "bar"): None}
