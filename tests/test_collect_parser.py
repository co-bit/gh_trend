from pathlib import Path

from common import dependents

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_dependents_count_with_comma_and_used_by():
    html = (FIXTURES / "dependents_sample.html").read_text(encoding="utf-8")
    assert dependents.parse_dependents_count(html) == 1234


def test_parse_dependents_count_with_k_suffix():
    html = '<a href="/x/y/network/dependents">2.5k Used by</a>'
    assert dependents.parse_dependents_count(html) == 2500


def test_parse_dependents_count_missing_returns_none():
    html = "<html><body>No dependents info here</body></html>"
    assert dependents.parse_dependents_count(html) is None
