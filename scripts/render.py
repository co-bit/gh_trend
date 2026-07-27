#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
LATEST_SCORES_PATH = DATA_DIR / "latest_scores.json"
OUTPUT_PATH = DOCS_DIR / "index.html"


def _fmt(value) -> str:
    return "-" if value is None else str(value)


def _fmt_pct(value) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def _row(repo: dict) -> str:
    full_name = f"{repo['owner']}/{repo['repo']}"
    url = f"https://github.com/{full_name}"
    return (
        "<tr>"
        f'<td><a href="{url}">{full_name}</a></td>'
        f"<td>{_fmt(repo['stars'])}</td>"
        f"<td>{_fmt(repo['star_velocity'])}</td>"
        f"<td>{_fmt(repo['hn_mentions_7d'])}</td>"
        f"<td>{_fmt(repo['dependents'])}</td>"
        f"<td>{_fmt(repo['dependents_velocity'])}</td>"
        f"<td>{_fmt_pct(repo['composite'])}</td>"
        "</tr>"
    )


def _table(title: str, repos: list[dict]) -> str:
    rows = "\n".join(_row(r) for r in repos)
    return (
        f"<h2>{title}</h2>\n"
        "<table>\n"
        "<tr><th>Repo</th><th>Stars</th><th>Star増加(7d)</th>"
        "<th>HN言及(7d)</th><th>Dependents</th><th>Dependents増加(7d)</th>"
        "<th>総合スコア</th></tr>\n"
        f"{rows}\n"
        "</table>"
    )


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

    body = "\n".join(
        [
            f"<p>更新日時: {generated_at}</p>",
            _table("総合トレンドランキング", overall),
            _table("スター急上昇", by_star),
            _table("Hacker News話題", by_hn),
            _table("Dependents急増", by_dependents),
        ]
    )

    return (
        "<!doctype html>\n"
        '<html lang="ja"><head><meta charset="utf-8">'
        "<title>GitHub AI/MCPトレンド</title></head><body>\n"
        "<h1>GitHub AI/MCPトレンド</h1>\n"
        f"{body}\n"
        "</body></html>"
    )


def main() -> None:
    data = json.loads(LATEST_SCORES_PATH.read_text(encoding="utf-8"))
    html = render_html(data)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"rendered {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
