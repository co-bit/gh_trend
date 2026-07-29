#!/usr/bin/env python3
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
LATEST_SCORES_PATH = DATA_DIR / "latest_scores.json"
OUTPUT_PATH = DOCS_DIR / "index.html"

STYLE = """
:root {
  color-scheme: light;
  --page: #f9f9f7;
  --surface: #fcfcfb;
  --ink-primary: #0b0b0b;
  --ink-secondary: #52514e;
  --ink-muted: #898781;
  --gridline: #e1e0d9;
  --border: rgba(11, 11, 11, 0.10);
  --good: #006300;
  --blue: #2a78d6;
  --tint-1: rgba(42, 120, 214, 0.08);
  --tint-2: rgba(42, 120, 214, 0.16);
  --tint-3: rgba(42, 120, 214, 0.26);
  --tint-4: rgba(42, 120, 214, 0.38);
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d;
    --surface: #1a1a19;
    --ink-primary: #ffffff;
    --ink-secondary: #c3c2b7;
    --ink-muted: #898781;
    --gridline: #2c2c2a;
    --border: rgba(255, 255, 255, 0.10);
    --good: #0ca30c;
    --blue: #3987e5;
    --tint-1: rgba(57, 135, 229, 0.10);
    --tint-2: rgba(57, 135, 229, 0.18);
    --tint-3: rgba(57, 135, 229, 0.28);
    --tint-4: rgba(57, 135, 229, 0.40);
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--page);
  color: var(--ink-primary);
  font-family: "M PLUS Rounded 1c", ui-rounded, "Hiragino Maru Gothic ProN", "Yu Gothic", sans-serif;
  line-height: 1.5;
}

.page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2rem clamp(0.75rem, 3vw, 2rem) 4rem;
}

.page-header h1 {
  font-size: 1.5rem;
  margin: 0 0 0.375rem;
}

.subtitle {
  color: var(--ink-secondary);
  margin: 0;
  font-size: 0.9375rem;
}

.kpi-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 1.5rem 0 2rem;
}

.stat-tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.875rem 1.125rem;
  min-width: 10rem;
}

.stat-label {
  color: var(--ink-secondary);
  font-size: 0.8125rem;
  margin-bottom: 0.25rem;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.stat-value--small {
  font-size: 1.0625rem;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.table-section {
  margin: 2.5rem 0;
}

.table-section h2 {
  font-size: 1.125rem;
  margin: 0 0 0.75rem;
}

.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.875rem;
  min-width: 480px;
}

th, td {
  padding: 0.5rem 0.625rem;
  text-align: right;
  border-bottom: 1px solid var(--gridline);
  white-space: nowrap;
}

th:first-child, td:first-child {
  text-align: left;
}

td.repo-name {
  max-width: 260px;
}

td.repo-name a {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

th {
  color: var(--ink-secondary);
  font-weight: 500;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

td {
  font-variant-numeric: tabular-nums;
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr:hover {
  background: var(--gridline);
}

td a {
  color: var(--blue);
  text-decoration: none;
  font-variant-numeric: normal;
}

td a:hover {
  text-decoration: underline;
}

.num-muted {
  color: var(--ink-muted);
}

.num-good {
  color: var(--good);
}

.tint-1 { background: var(--tint-1); }
.tint-2 { background: var(--tint-2); }
.tint-3 { background: var(--tint-3); }
.tint-4 { background: var(--tint-4); }

.page-footer {
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--gridline);
  color: var(--ink-muted);
  font-size: 0.8125rem;
}
"""


def _fmt(value) -> str:
    return "-" if value is None else str(value)


def _fmt_pct(value) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def _tint_class(percentile) -> str:
    if percentile is None:
        return ""
    if percentile >= 0.8:
        return "tint-4"
    if percentile >= 0.6:
        return "tint-3"
    if percentile >= 0.4:
        return "tint-2"
    if percentile >= 0.2:
        return "tint-1"
    return ""


def _cell(value, *, kind: str = "plain", tint: str = "") -> str:
    classes = [tint] if tint else []

    if kind == "pct":
        text = _fmt_pct(value)
        if value is None:
            classes.append("num-muted")
    elif kind == "velocity":
        if value is None:
            classes.append("num-muted")
            text = "-"
        elif value > 0:
            classes.append("num-good")
            text = f"+{value}"
        else:
            text = str(value)
    else:
        text = _fmt(value)
        if value is None:
            classes.append("num-muted")

    class_attr = f' class="{" ".join(classes)}"' if classes else ""
    return f"<td{class_attr}>{text}</td>"


def _row(repo: dict, highlight: str) -> str:
    full_name = f"{repo['owner']}/{repo['repo']}"
    url = f"https://github.com/{full_name}"
    escaped_name = html.escape(full_name)
    escaped_url = html.escape(url)

    tints = {
        "composite": _tint_class(repo["composite"]),
        "star": _tint_class(repo["star_percentile"]),
        "hn": _tint_class(repo["hn_percentile"]),
        "dependents": _tint_class(repo["dependents_percentile"]),
    }

    cells = [
        f'<td class="repo-name"><a href="{escaped_url}" title="{escaped_name}">{escaped_name}</a></td>',
        _cell(repo["stars"]),
        _cell(
            repo["star_velocity"],
            kind="velocity",
            tint=tints["star"] if highlight == "star" else "",
        ),
        _cell(
            repo["hn_mentions_7d"],
            tint=tints["hn"] if highlight == "hn" else "",
        ),
        _cell(repo["dependents"]),
        _cell(
            repo["dependents_velocity"],
            kind="velocity",
            tint=tints["dependents"] if highlight == "dependents" else "",
        ),
        _cell(
            repo["composite"],
            kind="pct",
            tint=tints["composite"] if highlight == "composite" else "",
        ),
    ]
    return "<tr>" + "".join(cells) + "</tr>"


def _table(title: str, repos: list[dict], highlight: str) -> str:
    rows = "\n".join(_row(r, highlight) for r in repos)
    return (
        '<section class="table-section">\n'
        f"<h2>{html.escape(title)}</h2>\n"
        '<div class="table-scroll">\n'
        "<table>\n"
        "<thead><tr><th>Repo</th><th>Stars</th><th>Star増加(7d)</th>"
        "<th>HN言及(7d)</th><th>Dependents</th><th>Dependents増加(7d)</th>"
        "<th>総合スコア</th></tr></thead>\n"
        f"<tbody>\n{rows}\n</tbody>\n"
        "</table>\n"
        "</div>\n"
        "</section>"
    )


def _format_timestamp(generated_at: str) -> str:
    return generated_at[:16].replace("T", " ") + " UTC"


def render_html(data: dict) -> str:
    repos = data["repos"]
    generated_at = data["generated_at"]

    overall = sorted(
        (r for r in repos if r["composite"] is not None),
        key=lambda r: r["composite"],
        reverse=True,
    )
    by_star = sorted(
        (r for r in repos if r["star_velocity"] is not None),
        key=lambda r: r["star_velocity"],
        reverse=True,
    )
    by_hn = sorted(
        (r for r in repos if r["hn_mentions_7d"] is not None),
        key=lambda r: r["hn_mentions_7d"],
        reverse=True,
    )
    by_dependents = sorted(
        (r for r in repos if r["dependents_velocity"] is not None),
        key=lambda r: r["dependents_velocity"],
        reverse=True,
    )

    tables = "\n".join(
        [
            _table("総合トレンドランキング", overall, "composite"),
            _table("スター急上昇", by_star, "star"),
            _table("Hacker News話題", by_hn, "hn"),
            _table("Dependents急増", by_dependents, "dependents"),
        ]
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GitHub AI/MCPトレンド</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{STYLE}</style>
</head>
<body>
<div class="page">
<header class="page-header">
<h1>GitHub AI/MCPトレンド</h1>
<p class="subtitle">GitHub公式のtrendingページに依存しない、独自定義によるMCP・AIエージェントスキルのトレンド観測。毎日自動更新。</p>
</header>
<section class="kpi-row">
<div class="stat-tile">
<div class="stat-label">追跡中のリポジトリ</div>
<div class="stat-value">{len(repos)}</div>
</div>
<div class="stat-tile">
<div class="stat-label">更新日時</div>
<div class="stat-value stat-value--small">{_format_timestamp(generated_at)}</div>
</div>
</section>
{tables}
<footer class="page-footer">
<p>スター増加速度・Hacker News言及・GitHub Dependents増加の3シグナルから算出した独自のトレンドスコア。</p>
</footer>
</div>
</body>
</html>"""


def main() -> None:
    data = json.loads(LATEST_SCORES_PATH.read_text(encoding="utf-8"))
    html_output = render_html(data)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html_output, encoding="utf-8")
    print(f"rendered {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
