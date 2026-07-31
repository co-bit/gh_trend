import describe


def test_build_prompt_includes_repo_name_and_description():
    prompt = describe.build_prompt("foo/bar", "A tool for doing things")
    assert "foo/bar" in prompt
    assert "A tool for doing things" in prompt


def test_parse_gemini_response_extracts_text():
    payload = {"candidates": [{"content": {"parts": [{"text": "  概要文  "}]}}]}
    assert describe.parse_gemini_response(payload) == "概要文"


def test_parse_gemini_response_skips_empty_parts():
    payload = {"candidates": [{"content": {"parts": [{"text": "   "}, {"text": "本文"}]}}]}
    assert describe.parse_gemini_response(payload) == "本文"


def test_parse_gemini_response_returns_none_when_blocked():
    # safety filter などで candidates が空のケース
    payload = {"candidates": []}
    assert describe.parse_gemini_response(payload) is None


def test_parse_gemini_response_returns_none_on_unexpected_shape():
    assert describe.parse_gemini_response({}) is None
    assert describe.parse_gemini_response({"candidates": [{"content": {}}]}) is None


def test_summarize_returns_text_on_success(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "要約結果"}]}}]}

    def fake_post(url, params=None, json=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(describe.requests, "post", fake_post)
    result = describe.summarize("foo/bar", "some description", "test-key")

    assert result == "要約結果"
    assert captured["params"] == {"key": "test-key"}
    assert "foo/bar" in captured["json"]["contents"][0]["parts"][0]["text"]


def test_summarize_returns_none_on_error_status(monkeypatch):
    class FakeResponse:
        status_code = 400

        def json(self):
            return {}

    monkeypatch.setattr(
        describe.requests, "post", lambda *a, **kw: FakeResponse()
    )
    assert describe.summarize("foo/bar", "desc", "test-key") is None
