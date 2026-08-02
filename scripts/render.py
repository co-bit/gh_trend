#!/usr/bin/env python3
import html
import json
from pathlib import Path

from common import ranking, scoring

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
LATEST_SCORES_PATH = DATA_DIR / "latest_scores.json"
DESCRIPTIONS_PATH = DATA_DIR / "descriptions.json"
OUTPUT_PATH = DOCS_DIR / "index.html"

# 合成スコアの内訳バーで使う3色。dataviz検証済みのカテゴリカル1〜3枠で、
# ライト/ダーク双方で全ペアの色覚多様性コントラストを満たす組み合わせ。
SIGNAL_LABELS = (
    ("star", "スターの勢い"),
    ("hn", "HN言及"),
    ("dependents", "Dependents"),
)

STYLE = """
:root {
  color-scheme: light;
  --paper: #f4f6f9;
  --panel: #ffffff;
  --ink: #10151c;
  --ink-dim: #5a6472;
  --ink-faint: #8f99a8;
  --rule: #dfe4ec;
  --rule-strong: #c6cedb;
  --accent: #2a78d6;
  --sig-star: #2a78d6;
  --sig-hn: #eb6834;
  --sig-dep: #1baf7a;
  --track: #e7ebf2;
  --good: #006300;
  --row-hover: #eef2f8;
  --head-active: #e4ecf8;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --paper: #0b0f14;
    --panel: #141a22;
    --ink: #eef2f7;
    --ink-dim: #98a3b3;
    --ink-faint: #6c7788;
    --rule: #232c37;
    --rule-strong: #38434f;
    --accent: #3987e5;
    --sig-star: #3987e5;
    --sig-hn: #d95926;
    --sig-dep: #199e70;
    --track: #1e2731;
    --good: #0ca30c;
    --row-hover: #1b232c;
    --head-active: #1c2836;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: "M PLUS Rounded 1c", ui-rounded, "Hiragino Maru Gothic ProN", "Yu Gothic", sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 2.5rem clamp(0.75rem, 3vw, 2rem) 4rem;
}

/* ── マストヘッド ───────────────────────────── */
.masthead {
  border-bottom: 2px solid var(--ink);
  padding-bottom: 1rem;
  margin-bottom: 0.75rem;
}

.masthead h1 {
  font-size: clamp(1.5rem, 3.2vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 0.5rem;
}

.thesis {
  margin: 0;
  max-width: 46rem;
  color: var(--ink-dim);
  font-size: 0.9375rem;
}

.status {
  margin: 0.75rem 0 0;
  font-size: 0.8125rem;
  color: var(--ink-faint);
  font-variant-numeric: tabular-nums;
}

.status b {
  color: var(--ink-dim);
  font-weight: 600;
}

/* ── セクション ───────────────────────────── */
.table-section { margin: 2.75rem 0 0; }

.section-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  margin-bottom: 0.625rem;
}

.section-head h2 {
  font-size: 1.0625rem;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
}

.section-note {
  font-size: 0.8125rem;
  color: var(--ink-faint);
  margin: 0;
}

/* 内訳バーの凡例 */
.legend {
  display: flex;
  gap: 0.875rem;
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 0.75rem;
  color: var(--ink-dim);
}

.legend li { display: flex; align-items: center; gap: 0.3125rem; }

.legend i {
  width: 0.625rem;
  height: 0.625rem;
  border-radius: 2px;
  flex: none;
}

.key-star { background: var(--sig-star); }
.key-hn { background: var(--sig-hn); }
.key-dependents { background: var(--sig-dep); }

/* ── テーブル ───────────────────────────── */
.table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--rule);
  border-radius: 10px;
  background: var(--panel);
}

table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.875rem;
  min-width: 860px;
}

th, td {
  padding: 0.5rem 0.625rem;
  text-align: right;
  border-bottom: 1px solid var(--rule);
  white-space: nowrap;
}

th:first-child, td:first-child { text-align: left; }

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--panel);
  border-bottom: 1px solid var(--rule-strong);
  color: var(--ink-dim);
  font-weight: 500;
  font-size: 0.6875rem;
  letter-spacing: 0.04em;
  text-align: left;
  padding: 0;
}

thead th[aria-sort="ascending"],
thead th[aria-sort="descending"] { background: var(--head-active); }

/* 並べ替えボタン: th全体をヒット領域にする */
.sort {
  all: unset;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  width: 100%;
  padding: 0.5rem 0.625rem;
  cursor: pointer;
  color: inherit;
  font: inherit;
  letter-spacing: inherit;
}

th:not(:first-child) .sort { justify-content: flex-end; }
.sort:hover { color: var(--ink); }
.sort:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
  border-radius: 4px;
}

.sort::after {
  content: "";
  width: 0.5rem;
  color: var(--ink-faint);
  font-size: 0.625rem;
  line-height: 1;
}
th[aria-sort="descending"] .sort::after { content: "▾"; color: var(--accent); }
th[aria-sort="ascending"] .sort::after { content: "▴"; color: var(--accent); }

.th-static { display: block; padding: 0.5rem 0.625rem; }

tbody td { font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover { background: var(--row-hover); }

td.repo-name { max-width: 15rem; }
td.repo-name a {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink);
  text-decoration: none;
  font-weight: 500;
  font-variant-numeric: normal;
}
td.repo-name a:hover { color: var(--accent); text-decoration: underline; }

td.description {
  text-align: left;
  white-space: normal;
  max-width: 22rem;
  color: var(--ink-dim);
  font-size: 0.8125rem;
  line-height: 1.45;
  font-variant-numeric: normal;
}

.num-muted { color: var(--ink-faint); }
.num-good { color: var(--good); }

.tint-1 { background: color-mix(in srgb, var(--accent) 7%, transparent); }
.tint-2 { background: color-mix(in srgb, var(--accent) 14%, transparent); }
.tint-3 { background: color-mix(in srgb, var(--accent) 23%, transparent); }
.tint-4 { background: color-mix(in srgb, var(--accent) 34%, transparent); }

/* ── シグネチャ: 合成スコアの内訳バー ───────────── */
td.score {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}

.score-bar {
  display: flex;
  gap: 2px;
  width: 5rem;
  height: 6px;
  border-radius: 3px;
  background: var(--track);
  overflow: hidden;
  flex: none;
}

.score-bar i { display: block; height: 100%; }
.seg-star { background: var(--sig-star); }
.seg-hn { background: var(--sig-hn); }
.seg-dependents { background: var(--sig-dep); }

.score-num { min-width: 2.25rem; font-weight: 500; }

/* ── フッター ───────────────────────────── */
.page-footer {
  margin-top: 3.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--rule);
  color: var(--ink-faint);
  font-size: 0.8125rem;
  max-width: 52rem;
}

.page-footer p { margin: 0 0 0.5rem; }
.page-footer a { color: var(--accent); }

@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
"""

SORT_SCRIPT = """
for (const table of document.querySelectorAll('table[data-sortable]')) {
  const tbody = table.tBodies[0];
  const heads = [...table.querySelectorAll('thead th[data-sortable]')];

  for (const th of heads) {
    th.querySelector('.sort').addEventListener('click', () => {
      const index = [...th.parentNode.children].indexOf(th);
      const dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
      for (const other of heads) other.setAttribute('aria-sort', 'none');
      th.setAttribute('aria-sort', dir);

      const sign = dir === 'ascending' ? 1 : -1;
      const rows = [...tbody.rows];
      rows.sort((a, b) => {
        const av = a.cells[index].dataset.v ?? '';
        const bv = b.cells[index].dataset.v ?? '';
        // 欠損値は並び順によらず常に末尾へ送る
        if (av === '' && bv === '') return 0;
        if (av === '') return 1;
        if (bv === '') return -1;
        const an = parseFloat(av), bn = parseFloat(bv);
        if (Number.isNaN(an) || Number.isNaN(bn)) return sign * av.localeCompare(bv, 'ja');
        return sign * (an - bn);
      });
      for (const row of rows) tbody.appendChild(row);
    });
  }
}
"""

# (見出し, ソート種別) — 種別 "text" は文字列比較、"num" は数値比較、None は並べ替え不可
COLUMNS = (
    ("Repo", "text"),
    ("概要", None),
    ("Stars", "num"),
    ("Star増加(7d)", "num"),
    ("成長率(7d)", "num"),
    ("HN言及(7d)", "num"),
    ("Dependents", "num"),
    ("Dependents増加(7d)", "num"),
    ("総合スコア", "num"),
)


def _fmt_int(value) -> str:
    return "-" if value is None else f"{value:,}"


def _fmt_pct(value) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def _fmt_rate(value) -> str:
    """相対成長率(すでに%単位)。小さすぎる値は0%に潰さず<0.1%と表示する。"""
    if value is None:
        return "-"
    if 0 < value < 0.1:
        return "<0.1%"
    return f"{value:.1f}%"


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
    """並べ替え用の生値を data-v に持たせたデータセルを返す。"""
    classes = [tint] if tint else []

    if kind == "pct":
        text = _fmt_pct(value)
    elif kind == "rate":
        text = _fmt_rate(value)
        if value is not None and value > 0:
            classes.append("num-good")
    elif kind == "velocity":
        if value is None:
            text = "-"
        elif value > 0:
            classes.append("num-good")
            text = f"+{value:,}"
        else:
            text = f"{value:,}"
    else:
        text = _fmt_int(value)

    if value is None:
        classes.append("num-muted")

    class_attr = f' class="{" ".join(classes)}"' if classes else ""
    sort_value = "" if value is None else repr(float(value))
    return f'<td{class_attr} data-v="{sort_value}">{text}</td>'


def _description_cell(description) -> str:
    if not description:
        return '<td class="description num-muted">-</td>'
    return f'<td class="description">{html.escape(description)}</td>'


def _score_segments(repo: dict) -> list[tuple[str, float]]:
    """合成スコアの内訳(シグナルごとの寄与)を返す。合計は composite に一致する。

    寄与 = 重み × パーセンタイル / 算出できたシグナルの重み合計。
    欠損シグナルは分母から外れるので、バーのセグメント数が減るだけになる。
    """
    parts = [
        ("star", repo.get("star_momentum_percentile")),
        ("hn", repo.get("hn_percentile")),
        ("dependents", repo.get("dependents_percentile")),
    ]
    available = [(name, pctl) for name, pctl in parts if pctl is not None]
    if not available:
        return []
    total_weight = sum(scoring.WEIGHTS[name] for name, _ in available)
    return [(name, scoring.WEIGHTS[name] * pctl / total_weight) for name, pctl in available]


def _score_cell(repo: dict) -> str:
    """内訳バー付きの総合スコアセル。バーの全長がスコア、内訳が根拠を示す。"""
    composite = repo["composite"]
    if composite is None:
        return '<td class="score num-muted" data-v="">-</td>'

    segments = "".join(
        f'<i class="seg-{name}" style="width:{share * 100:.2f}%"></i>'
        for name, share in _score_segments(repo)
        if share > 0
    )
    return (
        f'<td class="score" data-v="{composite!r}">'
        f'<span class="score-bar" aria-hidden="true">{segments}</span>'
        f'<span class="score-num">{_fmt_pct(composite)}</span>'
        "</td>"
    )


def _row(repo: dict, highlight: str, *, show_breakdown: bool) -> str:
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

    score_cell = (
        _score_cell(repo)
        if show_breakdown
        else _cell(
            repo["composite"],
            kind="pct",
            tint=tints["composite"] if highlight == "composite" else "",
        )
    )

    cells = [
        f'<td class="repo-name" data-v="{escaped_name}">'
        f'<a href="{escaped_url}" title="{escaped_name}">{escaped_name}</a></td>',
        _description_cell(repo.get("description")),
        _cell(repo["stars"]),
        _cell(
            repo["star_velocity"],
            kind="velocity",
            tint=tints["star"] if highlight == "star" else "",
        ),
        _cell(repo.get("star_growth_rate"), kind="rate"),
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
        score_cell,
    ]
    return "<tr>" + "".join(cells) + "</tr>"


def _header_row() -> str:
    cells = []
    for label, kind in COLUMNS:
        escaped = html.escape(label)
        if kind is None:
            cells.append(f'<th scope="col"><span class="th-static">{escaped}</span></th>')
        else:
            cells.append(
                f'<th scope="col" data-sortable aria-sort="none">'
                f'<button type="button" class="sort">{escaped}</button></th>'
            )
    return "<tr>" + "".join(cells) + "</tr>"


def _legend() -> str:
    items = "".join(
        f'<li><i class="key-{name}"></i>{html.escape(label)}</li>' for name, label in SIGNAL_LABELS
    )
    return f'<ul class="legend">{items}</ul>'


def _table(title: str, note: str, repos: list[dict], highlight: str, *, show_breakdown: bool) -> str:
    rows = "\n".join(_row(r, highlight, show_breakdown=show_breakdown) for r in repos)
    head_extra = _legend() if show_breakdown else f'<p class="section-note">{html.escape(note)}</p>'
    return (
        '<section class="table-section">\n'
        '<div class="section-head">\n'
        f"<h2>{html.escape(title)}</h2>\n"
        f"{head_extra}\n"
        "</div>\n"
        '<div class="table-scroll">\n'
        '<table data-sortable>\n'
        f"<thead>{_header_row()}</thead>\n"
        f"<tbody>\n{rows}\n</tbody>\n"
        "</table>\n"
        "</div>\n"
        "</section>"
    )


def _format_timestamp(generated_at: str) -> str:
    return generated_at[:16].replace("T", " ") + " UTC"


SECTION_NOTES = {
    "composite": "",
    "star": "この1週間で最も多くスターを集めた順",
    "hn": "この1週間でHacker Newsに登場した回数順",
    "dependents": "この1週間で依存元リポジトリが最も増えた順",
}


def render_html(data: dict) -> str:
    repos = data["repos"]
    generated_at = data["generated_at"]

    tables = "\n".join(
        _table(
            title,
            SECTION_NOTES.get(highlight, ""),
            ranked,
            highlight,
            show_breakdown=(highlight == "composite"),
        )
        for title, ranked, highlight in ranking.ranked_tables(repos)
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
<header class="masthead">
<h1>GitHub AI/MCPトレンド</h1>
<p class="thesis">スター総数の多さではなく、この1週間でどれだけ動いたかで並べています。19万スターのリポジトリが週に1,000増えるのは平常運転で、300スターのリポジトリが240増えるほうが事件です。</p>
<p class="status"><b>{len(repos):,}</b> リポジトリを追跡中 · {_format_timestamp(generated_at)} 更新</p>
</header>
{tables}
<footer class="page-footer">
<p>総合スコアは、スターの勢い(増加数と成長率の幾何平均)・Hacker Newsでの言及数・Dependentsの増加数を、それぞれ全追跡リポジトリ内での順位に変換し、6:2:2で重み付けした値です。スコア列のバーはその内訳を示しています。</p>
<p>列名をクリックすると、その列で表示中の20件を並べ替えられます。</p>
</footer>
</div>
<script>{SORT_SCRIPT}</script>
</body>
</html>"""


def main() -> None:
    data = json.loads(LATEST_SCORES_PATH.read_text(encoding="utf-8"))

    if DESCRIPTIONS_PATH.exists():
        descriptions = json.loads(DESCRIPTIONS_PATH.read_text(encoding="utf-8"))
        for repo in data["repos"]:
            key = f"{repo['owner']}/{repo['repo']}"
            repo["description"] = descriptions.get(key)

    html_output = render_html(data)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html_output, encoding="utf-8")
    print(f"rendered {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
