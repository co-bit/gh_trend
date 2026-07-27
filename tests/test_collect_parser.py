from pathlib import Path

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
