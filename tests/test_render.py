import json
from pathlib import Path

import render

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sample_data():
    return json.loads((FIXTURES / "latest_scores_sample.json").read_text(encoding="utf-8"))


def test_render_html_includes_repo_links():
    html = render.render_html(_sample_data())
    assert 'href="https://github.com/foo/bar"' in html
    assert "foo/bar" in html


def test_render_html_overall_ranking_orders_by_composite_desc():
    html = render.render_html(_sample_data())
    pos_bar = html.index("foo/bar")
    pos_baz = html.index("foo/baz")
    assert pos_bar < pos_baz


def test_render_html_shows_generated_at():
    html = render.render_html(_sample_data())
    assert "2026-07-27" in html


def test_render_html_missing_signal_shown_as_dash():
    html = render.render_html(_sample_data())
    assert ">-<" in html
