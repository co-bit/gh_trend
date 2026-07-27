# GitHub AI/MCPトレンドダッシュボード Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GitHub公式のtrendingページに依存せず、独自定義(スター増加速度・HN言及・GitHub Dependents増加数)でMCPおよびAIエージェント向けスキル/ツールのトレンドを算出し、GitHub Actionsで毎日自動更新されるHTMLダッシュボードをGitHub Pagesで公開する。

**Architecture:** `scripts/discover.py`→`collect.py`→`score.py`→`render.py`の4段パイプラインを日次でGitHub Actionsが実行し、`data/`配下のJSONに履歴を蓄積、`docs/index.html`に結果を出力してGitHub Pagesで配信する。各段は独立した純粋関数(`scripts/common/`配下)を呼び出すだけの薄いオーケストレーションとし、外部API呼び出し部分と計算ロジックを分離する。

**Tech Stack:** Python 3.12, requests, beautifulsoup4, pytest, GitHub Actions, GitHub Pages

参照設計書: `docs/superpowers/specs/2026-07-27-gh-trend-design.md`

## Global Constraints

- 実装言語: Python(3.12)
- 実行スケジュール: GitHub Actions cron `0 0 * * *`(UTC 0:00 = JST 9:00)+ `workflow_dispatch`
- 認証: Actions標準の `GITHUB_TOKEN` のみ使用。追加シークレット登録は行わない
- 履歴保持: 各リポジトリのスナップショットは直近90日分のみ保持し、古いものは削除する
- 監視対象リポジトリ数: 上限を設けない
- 欠損値(API失敗・パース失敗)は `null` として記録し、0扱いにしない。パーセンタイル・合成スコア計算は欠損を除外して算出する
- スコア重みは `WEIGHTS = {"star": 1/3, "hn": 1/3, "dependents": 1/3}` を定数として切り出す(均等重み、後で調整可能)
- GitHub Pages: `main`ブランチの `docs/` フォルダをソースとして配信
- GitHubアカウント: `co-bit`(Public リポジトリ)
- 対象スコープ(discover.pyの検索キーワード)は以下に厳密に限定する: `topic:mcp-server`, `topic:model-context-protocol`, `topic:agent-skills`, `topic:llm-tools`, `topic:ai-agent-toolkit`, `topic:claude-skill`, `topic:claude-code`

---

## Task 1: プロジェクト基盤のセットアップ

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/conftest.py`
- Create: `scripts/common/__init__.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: なし(最初のタスク)
- Produces: `pytest`実行時に`scripts/`が`sys.path`に追加され、以降のタスクで`tests/*.py`から`from common import <module>`でインポート可能になる

- [ ] **Step 1: `requirements.txt` を作成**

```
requests>=2.31
beautifulsoup4>=4.12
```

- [ ] **Step 2: `requirements-dev.txt` を作成**

```
-r requirements.txt
pytest>=8.0
pyyaml>=6.0
```

- [ ] **Step 3: `pytest.ini` を作成**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: `scripts/common/__init__.py` を空ファイルとして作成**

```python
```

(空ファイルでよい。`scripts/common/`をPythonパッケージとして認識させるため)

- [ ] **Step 5: `tests/conftest.py` を作成**

```python
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

- [ ] **Step 6: `.gitignore` にPython関連の除外パターンを追記**

既存の`.gitignore`末尾に以下を追記する:

```
# Python
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 7: 依存関係をインストールして`pytest`が正常に動作することを確認**

Run:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
Expected: `no tests ran` に類するメッセージでエラーなく終了する(テストがまだ0件のため)

- [ ] **Step 8: コミット**

```bash
git add requirements.txt requirements-dev.txt pytest.ini tests/conftest.py scripts/common/__init__.py .gitignore
git commit -m "$(cat <<'EOF'
プロジェクト基盤(依存関係・pytest設定)をセットアップ

Python実装のためのrequirements、pytest設定、scripts/common/を
importできるようにするconftest.pyを追加。
EOF
)"
```

---

## Task 2: common/storage.py — watchlist・スナップショットの読み書きとローテーション

**Files:**
- Create: `scripts/common/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: なし(標準ライブラリのみ)
- Produces:
  - `load_watchlist(path: Path) -> list[dict]`
  - `save_watchlist(path: Path, watchlist: list[dict]) -> None`
  - `add_to_watchlist(watchlist: list[dict], owner: str, repo: str, source: str, today: str) -> list[dict]`
  - `repo_snapshot_path(data_dir: Path, owner: str, repo: str) -> Path`
  - `load_snapshots(path: Path) -> list[dict]`
  - `append_snapshot(path: Path, snapshot: dict, retention_days: int = 90) -> None`
  - watchlistエントリの形: `{"owner": str, "repo": str, "first_seen": "YYYY-MM-DD", "source": str}`
  - スナップショットの形: `{"date": "YYYY-MM-DD", "stars": int|None, "hn_mentions": int|None, "dependents": int|None}`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_storage.py`:
```python
from common import storage


def test_load_watchlist_missing_file_returns_empty(tmp_path):
    path = tmp_path / "watchlist.json"
    assert storage.load_watchlist(path) == []


def test_save_and_load_watchlist_roundtrip(tmp_path):
    path = tmp_path / "watchlist.json"
    data = [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-27", "source": "search:mcp-server"}]
    storage.save_watchlist(path, data)
    assert storage.load_watchlist(path) == data


def test_add_to_watchlist_appends_new_entry():
    watchlist = []
    result = storage.add_to_watchlist(watchlist, "foo", "bar", "search:mcp-server", "2026-07-27")
    assert result == [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-27", "source": "search:mcp-server"}]


def test_add_to_watchlist_skips_duplicate():
    watchlist = [{"owner": "foo", "repo": "bar", "first_seen": "2026-07-01", "source": "search:mcp-server"}]
    result = storage.add_to_watchlist(watchlist, "foo", "bar", "search:agent-skills", "2026-07-27")
    assert len(result) == 1
    assert result[0]["first_seen"] == "2026-07-01"


def test_repo_snapshot_path_uses_double_underscore(tmp_path):
    path = storage.repo_snapshot_path(tmp_path, "foo", "bar")
    assert path == tmp_path / "repos" / "foo__bar.json"


def test_append_snapshot_creates_file(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1})
    assert storage.load_snapshots(path) == [
        {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1}
    ]


def test_append_snapshot_replaces_same_day_entry(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1})
    storage.append_snapshot(path, {"date": "2026-07-27", "stars": 15, "hn_mentions": 1, "dependents": 1})
    snapshots = storage.load_snapshots(path)
    assert len(snapshots) == 1
    assert snapshots[0]["stars"] == 15


def test_append_snapshot_prunes_entries_older_than_retention(tmp_path):
    path = tmp_path / "repos" / "foo__bar.json"
    storage.append_snapshot(
        path, {"date": "2026-01-01", "stars": 1, "hn_mentions": 0, "dependents": 0}, retention_days=90
    )
    storage.append_snapshot(
        path, {"date": "2026-07-27", "stars": 10, "hn_mentions": 0, "dependents": 1}, retention_days=90
    )
    snapshots = storage.load_snapshots(path)
    assert len(snapshots) == 1
    assert snapshots[0]["date"] == "2026-07-27"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest tests/test_storage.py -v`
Expected: `ModuleNotFoundError: No module named 'common'`(まだ`storage.py`が存在しないため)

- [ ] **Step 3: `scripts/common/storage.py` を実装**

```python
import json
from datetime import date, timedelta
from pathlib import Path


def load_watchlist(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_watchlist(path: Path, watchlist: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_watchlist(watchlist: list[dict], owner: str, repo: str, source: str, today: str) -> list[dict]:
    existing = {(entry["owner"], entry["repo"]) for entry in watchlist}
    if (owner, repo) not in existing:
        watchlist.append({"owner": owner, "repo": repo, "first_seen": today, "source": source})
    return watchlist


def repo_snapshot_path(data_dir: Path, owner: str, repo: str) -> Path:
    return data_dir / "repos" / f"{owner}__{repo}.json"


def load_snapshots(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_snapshot(path: Path, snapshot: dict, retention_days: int = 90) -> None:
    snapshots = load_snapshots(path)
    snapshots = [s for s in snapshots if s["date"] != snapshot["date"]]
    snapshots.append(snapshot)

    cutoff = (date.fromisoformat(snapshot["date"]) - timedelta(days=retention_days)).isoformat()
    snapshots = [s for s in snapshots if s["date"] >= cutoff]
    snapshots.sort(key=lambda s: s["date"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest tests/test_storage.py -v`
Expected: 8 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/common/storage.py tests/test_storage.py
git commit -m "$(cat <<'EOF'
common/storage.py: watchlistとスナップショットの読み書きを実装

90日ローテーション・同日再実行時の上書き・重複追加防止を含む
純粋なファイルI/O層をTDDで実装。
EOF
)"
```

---

## Task 3: common/scoring.py — パーセンタイル・変化量・合成スコア計算

**Files:**
- Create: `scripts/common/scoring.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: なし(標準ライブラリのみ)
- Produces:
  - `WEIGHTS: dict[str, float]`(`{"star": 1/3, "hn": 1/3, "dependents": 1/3}`)
  - `compute_percentile(value: float, population: list[float]) -> float`
  - `compute_star_velocity(snapshots: list[dict]) -> int | None`
  - `compute_hn_velocity(snapshots: list[dict], window_days: int = 7) -> int | None`
  - `compute_dependents_velocity(snapshots: list[dict]) -> int | None`
  - `compute_composite(percentiles: dict[str, float | None], weights: dict[str, float]) -> float | None`
  - `snapshots`は Task 2 で定義したスナップショット形式のリスト(`date`昇順である必要はない)

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_score.py`:
```python
from common import scoring


def test_compute_percentile_middle_value():
    assert scoring.compute_percentile(5, [1, 3, 5, 7, 9]) == 2 / 5


def test_compute_percentile_lowest_value():
    assert scoring.compute_percentile(1, [1, 3, 5]) == 0.0


def test_compute_percentile_single_population():
    assert scoring.compute_percentile(10, [10]) == 0.0


def test_compute_percentile_all_equal():
    assert scoring.compute_percentile(5, [5, 5, 5]) == 0.0


def test_compute_percentile_empty_population():
    assert scoring.compute_percentile(5, []) == 0.0


def test_compute_star_velocity_with_full_week():
    snapshots = [
        {"date": "2026-07-20", "stars": 100},
        {"date": "2026-07-27", "stars": 150},
    ]
    assert scoring.compute_star_velocity(snapshots) == 50


def test_compute_star_velocity_insufficient_history():
    snapshots = [{"date": "2026-07-27", "stars": 150}]
    assert scoring.compute_star_velocity(snapshots) is None


def test_compute_star_velocity_ignores_null_entries():
    snapshots = [
        {"date": "2026-07-20", "stars": None},
        {"date": "2026-07-21", "stars": 90},
        {"date": "2026-07-27", "stars": 150},
    ]
    assert scoring.compute_star_velocity(snapshots) == 60


def test_compute_hn_velocity_sums_last_seven_days():
    snapshots = [
        {"date": "2026-07-21", "hn_mentions": 1},
        {"date": "2026-07-22", "hn_mentions": 2},
        {"date": "2026-07-27", "hn_mentions": 3},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 6


def test_compute_hn_velocity_skips_null_entries():
    snapshots = [
        {"date": "2026-07-26", "hn_mentions": None},
        {"date": "2026-07-27", "hn_mentions": 4},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 4


def test_compute_hn_velocity_no_data_returns_none():
    snapshots = [{"date": "2026-07-27", "hn_mentions": None}]
    assert scoring.compute_hn_velocity(snapshots) is None


def test_compute_hn_velocity_ignores_entries_outside_calendar_window():
    snapshots = [
        {"date": "2026-01-01", "hn_mentions": 100},
        {"date": "2026-07-25", "hn_mentions": 1},
        {"date": "2026-07-26", "hn_mentions": 2},
        {"date": "2026-07-27", "hn_mentions": 3},
    ]
    assert scoring.compute_hn_velocity(snapshots) == 6


def test_compute_dependents_velocity():
    snapshots = [
        {"date": "2026-07-20", "dependents": 10},
        {"date": "2026-07-27", "dependents": 25},
    ]
    assert scoring.compute_dependents_velocity(snapshots) == 15


def test_compute_composite_all_signals_present():
    percentiles = {"star": 0.9, "hn": 0.6, "dependents": 0.3}
    result = scoring.compute_composite(percentiles, scoring.WEIGHTS)
    assert round(result, 4) == round((0.9 + 0.6 + 0.3) / 3, 4)


def test_compute_composite_missing_signal_excluded():
    percentiles = {"star": 0.9, "hn": None, "dependents": 0.3}
    result = scoring.compute_composite(percentiles, scoring.WEIGHTS)
    assert round(result, 4) == round((0.9 + 0.3) / 2, 4)


def test_compute_composite_all_missing_returns_none():
    percentiles = {"star": None, "hn": None, "dependents": None}
    assert scoring.compute_composite(percentiles, scoring.WEIGHTS) is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest tests/test_score.py -v`
Expected: `ModuleNotFoundError: No module named 'common'`(まだ`scoring.py`が存在しないため)

- [ ] **Step 3: `scripts/common/scoring.py` を実装**

```python
from datetime import date, timedelta

WEIGHTS = {"star": 1 / 3, "hn": 1 / 3, "dependents": 1 / 3}


def compute_percentile(value: float, population: list[float]) -> float:
    if not population:
        return 0.0
    less = sum(1 for x in population if x < value)
    return less / len(population)


def _velocity_by_delta(snapshots: list[dict], field: str, window_days: int = 7) -> int | None:
    dated = [s for s in snapshots if s.get(field) is not None]
    if len(dated) < 2:
        return None

    dated_sorted = sorted(dated, key=lambda s: s["date"])
    latest = dated_sorted[-1]
    cutoff = (date.fromisoformat(latest["date"]) - timedelta(days=window_days)).isoformat()
    candidates = [s for s in dated_sorted if s["date"] <= cutoff]
    baseline = candidates[-1] if candidates else dated_sorted[0]

    if baseline is latest:
        return None
    return latest[field] - baseline[field]


def compute_star_velocity(snapshots: list[dict]) -> int | None:
    return _velocity_by_delta(snapshots, "stars")


def compute_dependents_velocity(snapshots: list[dict]) -> int | None:
    return _velocity_by_delta(snapshots, "dependents")


def compute_hn_velocity(snapshots: list[dict], window_days: int = 7) -> int | None:
    dated = [s for s in snapshots if s.get("hn_mentions") is not None]
    if not dated:
        return None

    dated_sorted = sorted(dated, key=lambda s: s["date"])
    latest_date = dated_sorted[-1]["date"]
    cutoff = (date.fromisoformat(latest_date) - timedelta(days=window_days)).isoformat()
    windowed = [s for s in dated_sorted if s["date"] >= cutoff]
    return sum(s["hn_mentions"] for s in windowed)


def compute_composite(percentiles: dict[str, float | None], weights: dict[str, float]) -> float | None:
    available = {k: v for k, v in percentiles.items() if v is not None}
    if not available:
        return None
    weight_sum = sum(weights[k] for k in available)
    weighted = sum(percentiles[k] * weights[k] for k in available)
    return weighted / weight_sum
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest tests/test_score.py -v`
Expected: 16 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/common/scoring.py tests/test_score.py
git commit -m "$(cat <<'EOF'
common/scoring.py: パーセンタイル・変化量・合成スコア計算を実装

星増加速度/HN言及/Dependents増加の変化量算出、母集団内での
パーセンタイル順位への変換、欠損シグナルを除外した合成スコア
計算をTDDで実装。境界条件(欠損混在・母集団1件・全員同値)を
テストでカバー。
EOF
)"
```

---

## Task 4: common/dependents.py — Dependentsページの取得とパース

**Files:**
- Create: `scripts/common/dependents.py`
- Create: `tests/fixtures/dependents_sample.html`
- Test: `tests/test_collect_parser.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `parse_dependents_count(html: str) -> int | None`(純粋関数、テスト対象)
  - `get_dependents_count(owner: str, repo: str, max_retries: int = 3) -> int | None`(ネットワークI/O、自動テスト対象外)

- [ ] **Step 1: フィクスチャHTMLを作成**

`tests/fixtures/dependents_sample.html`(GitHubの現在のUI構造に合わせたもの。"Repositories"タブと"Packages"タブが並ぶため、最初の"Repositories"の数値だけを正しく拾えるかも検証する):
```html
<html>
<body>
<div class="Box-header clearfix">
  <div class="table-list-header-toggle states flex-auto pl-0">
    <a class="btn-link selected" href="/octocat/example/network/dependents?dependent_type=REPOSITORY">
      1,234
      Repositories
    </a>
    <a class="btn-link" href="/octocat/example/network/dependents?dependent_type=PACKAGE">
      56
      Packages
    </a>
  </div>
</div>
</body>
</html>
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_collect_parser.py`:
```python
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
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `pytest tests/test_collect_parser.py -v`
Expected: `ModuleNotFoundError: No module named 'common'`(まだ`dependents.py`が存在しないため)

- [ ] **Step 4: `scripts/common/dependents.py` を実装**

```python
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"(\d[\d,.]*)\s*(k)?\s*(?:Repositories|Used by)", re.IGNORECASE)


def parse_dependents_count(html: str) -> int | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = _NUMBER_RE.search(text)
    if not match:
        return None

    number_str, k_suffix = match.groups()
    number_str = number_str.replace(",", "")
    try:
        value = float(number_str)
    except ValueError:
        return None

    if k_suffix:
        value *= 1000
    return int(value)


def get_dependents_count(owner: str, repo: str, max_retries: int = 3) -> int | None:
    url = f"https://github.com/{owner}/{repo}/network/dependents"
    headers = {"User-Agent": "gh-trend-dashboard-bot/1.0"}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
        except requests.RequestException as exc:
            logger.warning("dependents fetch failed for %s/%s: %s", owner, repo, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            count = parse_dependents_count(resp.text)
            if count is None:
                logger.warning("dependents parse failed for %s/%s", owner, repo)
            return count

        logger.warning("dependents fetch got status %s for %s/%s", resp.status_code, owner, repo)
        time.sleep(2 ** attempt)

    return None
```

- [ ] **Step 5: テストが通ることを確認**

Run: `pytest tests/test_collect_parser.py -v`
Expected: 5 passed

- [ ] **Step 6: コミット**

```bash
git add scripts/common/dependents.py tests/test_collect_parser.py tests/fixtures/dependents_sample.html
git commit -m "$(cat <<'EOF'
common/dependents.py: /network/dependentsの取得とパースを実装

GitHub非公式のDependentsページから件数を抽出する純粋関数を
フィクスチャHTMLでテスト。取得側はリトライ付きで失敗時null。
EOF
)"
```

---

## Task 5: common/github_api.py — GitHub REST/Search APIラッパー

**Files:**
- Create: `scripts/common/github_api.py`
- Test: `tests/test_github_api.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `extract_owner_repo_from_search_item(item: dict) -> tuple[str, str] | None`(純粋関数、テスト対象)
  - `get_repo_stars(owner: str, repo: str, token: str | None = None) -> int | None`(ネットワークI/O、自動テスト対象外)
  - `search_repos(query: str, token: str | None = None, per_page: int = 100) -> list[dict]`(戻り値は`{"owner": str, "repo": str}`のリスト。ネットワークI/O、自動テスト対象外)

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_github_api.py`:
```python
from common import github_api


def test_extract_owner_repo_from_search_item_valid():
    item = {"full_name": "modelcontextprotocol/servers"}
    assert github_api.extract_owner_repo_from_search_item(item) == ("modelcontextprotocol", "servers")


def test_extract_owner_repo_from_search_item_missing_full_name():
    assert github_api.extract_owner_repo_from_search_item({}) is None


def test_extract_owner_repo_from_search_item_malformed():
    assert github_api.extract_owner_repo_from_search_item({"full_name": "no-slash"}) is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest tests/test_github_api.py -v`
Expected: `ModuleNotFoundError: No module named 'common'`(まだ`github_api.py`が存在しないため)

- [ ] **Step 3: `scripts/common/github_api.py` を実装**

```python
import time

import requests

API_BASE = "https://api.github.com"


def extract_owner_repo_from_search_item(item: dict) -> tuple[str, str] | None:
    full_name = item.get("full_name", "")
    if "/" not in full_name:
        return None
    owner, repo = full_name.split("/", 1)
    if not owner or not repo:
        return None
    return owner, repo


def _headers(token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request_with_retry(url: str, headers: dict, params: dict | None = None, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return resp
        if resp.status_code in (403, 429):
            time.sleep(2 ** attempt)
            continue
        return None

    return None


def get_repo_stars(owner: str, repo: str, token: str | None = None) -> int | None:
    resp = _request_with_retry(f"{API_BASE}/repos/{owner}/{repo}", _headers(token))
    if resp is None:
        return None
    return resp.json().get("stargazers_count")


def search_repos(query: str, token: str | None = None, per_page: int = 100) -> list[dict]:
    resp = _request_with_retry(
        f"{API_BASE}/search/repositories",
        _headers(token),
        params={"q": query, "per_page": per_page},
    )
    if resp is None:
        return []

    results = []
    for item in resp.json().get("items", []):
        parsed = extract_owner_repo_from_search_item(item)
        if parsed is not None:
            results.append({"owner": parsed[0], "repo": parsed[1]})
    return results
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest tests/test_github_api.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/common/github_api.py tests/test_github_api.py
git commit -m "$(cat <<'EOF'
common/github_api.py: GitHub REST/Search APIラッパーを実装

スター数取得・リポジトリ検索・レート制限時のリトライを実装。
検索結果からowner/repoを抽出する純粋関数のみユニットテスト。
EOF
)"
```

---

## Task 6: common/hn_api.py — Hacker News (Algolia) 連携

**Files:**
- Create: `scripts/common/hn_api.py`
- Test: `tests/test_hn_api.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `since_timestamp(reference: datetime, days_back: int = 1) -> int`(純粋関数、テスト対象)
  - `count_daily_mentions(repo_full_name: str, reference: datetime | None = None, max_retries: int = 3) -> int | None`(ネットワークI/O、自動テスト対象外)

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_hn_api.py`:
```python
from datetime import datetime, timezone

from common import hn_api


def test_since_timestamp_one_day_back():
    reference = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    expected = int(datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc).timestamp())
    assert hn_api.since_timestamp(reference, days_back=1) == expected


def test_since_timestamp_custom_window():
    reference = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
    expected = int(datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc).timestamp())
    assert hn_api.since_timestamp(reference, days_back=7) == expected
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest tests/test_hn_api.py -v`
Expected: `ModuleNotFoundError: No module named 'common'`(まだ`hn_api.py`が存在しないため)

- [ ] **Step 3: `scripts/common/hn_api.py` を実装**

```python
import time
from datetime import datetime, timedelta, timezone

import requests

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"


def since_timestamp(reference: datetime, days_back: int = 1) -> int:
    since = reference - timedelta(days=days_back)
    return int(since.timestamp())


def count_daily_mentions(
    repo_full_name: str, reference: datetime | None = None, max_retries: int = 3
) -> int | None:
    if reference is None:
        reference = datetime.now(timezone.utc)

    params = {
        "query": repo_full_name,
        "numericFilters": f"created_at_i>{since_timestamp(reference)}",
    }

    for attempt in range(max_retries):
        try:
            resp = requests.get(ALGOLIA_URL, params=params, timeout=10)
        except requests.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return len(resp.json().get("hits", []))
        time.sleep(2 ** attempt)

    return None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest tests/test_hn_api.py -v`
Expected: 2 passed

- [ ] **Step 5: コミット**

```bash
git add scripts/common/hn_api.py tests/test_hn_api.py
git commit -m "$(cat <<'EOF'
common/hn_api.py: Hacker News Algolia APIとの連携を実装

直近24時間のリポジトリ言及件数を取得。日時計算部分を純粋関数
として切り出しテスト、HTTP呼び出しはリトライ付きで失敗時null。
EOF
)"
```

---

## Task 7: scripts/discover.py — 新規リポジトリ発見スクリプト

**Files:**
- Create: `scripts/discover.py`

**Interfaces:**
- Consumes:
  - `github_api.search_repos(query: str, token: str | None, per_page: int) -> list[dict]`(Task 5)
  - `storage.load_watchlist(path: Path) -> list[dict]` / `storage.save_watchlist(path, watchlist)` / `storage.add_to_watchlist(...)`(Task 2)
- Produces: `data/watchlist.json` の更新(実行するとファイルが作成・追記される)

このタスクは複数の既存モジュールを組み合わせるオーケストレーションのみで、新規ロジックを持たないため自動テストは追加しない(設計書のテスト方針に準拠。手動実行で確認する)。

- [ ] **Step 1: `scripts/discover.py` を実装**

```python
#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pathlib import Path

from common import github_api, storage

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST_PATH = ROOT / "data" / "watchlist.json"

KEYWORDS = [
    "topic:mcp-server",
    "topic:model-context-protocol",
    "topic:agent-skills",
    "topic:llm-tools",
    "topic:ai-agent-toolkit",
    "topic:claude-skill",
    "topic:claude-code",
]


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    watchlist = storage.load_watchlist(WATCHLIST_PATH)
    today = datetime.now(timezone.utc).date().isoformat()
    before = len(watchlist)

    for keyword in KEYWORDS:
        for hit in github_api.search_repos(keyword, token=token):
            watchlist = storage.add_to_watchlist(
                watchlist, hit["owner"], hit["repo"], f"search:{keyword}", today
            )

    storage.save_watchlist(WATCHLIST_PATH, watchlist)
    print(f"watchlist: {before} -> {len(watchlist)} repos")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 手動実行して動作確認**

Run:
```bash
python scripts/discover.py
```
Expected: `watchlist: 0 -> N repos`(Nは1以上)のように出力され、`data/watchlist.json`が生成される。`cat data/watchlist.json`で中身がowner/repo/first_seen/sourceを持つ配列であることを目視確認する

- [ ] **Step 3: コミット(スクリプトと、動作確認で生成された`data/watchlist.json`を合わせてコミットする)**

```bash
git add scripts/discover.py data/watchlist.json
git commit -m "$(cat <<'EOF'
scripts/discover.py: 新規リポジトリ発見スクリプトを実装

MCPとAIエージェント向けスキル/ツールに厳密に絞った検索キーワードで
GitHub Search APIを呼び出し、新規発見分をwatchlist.jsonに追加。
EOF
)"
```

---

## Task 8: scripts/collect.py — 日次シグナル収集スクリプト

**Files:**
- Create: `scripts/collect.py`

**Interfaces:**
- Consumes:
  - `github_api.get_repo_stars(owner, repo, token) -> int | None`(Task 5)
  - `hn_api.count_daily_mentions(repo_full_name) -> int | None`(Task 6)
  - `dependents.get_dependents_count(owner, repo) -> int | None`(Task 4)
  - `storage.load_watchlist(path) -> list[dict]` / `storage.repo_snapshot_path(...)` / `storage.append_snapshot(...)`(Task 2)
- Produces: `data/repos/<owner>__<repo>.json` へのスナップショット追記

オーケストレーションのみのため自動テストは追加しない(Task 7と同様の方針)。

- [ ] **Step 1: `scripts/collect.py` を実装**

```python
#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from pathlib import Path

from common import dependents, github_api, hn_api, storage

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    watchlist = storage.load_watchlist(WATCHLIST_PATH)
    today = datetime.now(timezone.utc).date().isoformat()

    for entry in watchlist:
        owner, repo = entry["owner"], entry["repo"]
        snapshot = {
            "date": today,
            "stars": github_api.get_repo_stars(owner, repo, token=token),
            "hn_mentions": hn_api.count_daily_mentions(f"{owner}/{repo}"),
            "dependents": dependents.get_dependents_count(owner, repo),
        }
        path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
        storage.append_snapshot(path, snapshot)
        print(f"{owner}/{repo}: {snapshot}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 手動実行して動作確認**

Run:
```bash
python scripts/collect.py
```
Expected: watchlist内の各リポジトリについて `owner/repo: {...}` の形式で1行ずつ出力され、`data/repos/<owner>__<repo>.json`が生成される

- [ ] **Step 3: コミット(スクリプトと、動作確認で生成された`data/repos/`を合わせてコミットする)**

```bash
git add scripts/collect.py data/repos/
git commit -m "$(cat <<'EOF'
scripts/collect.py: 日次シグナル収集スクリプトを実装

watchlist内の全リポジトリについてスター数・HN言及数・Dependents数
を取得し、日次スナップショットとして追記する。
EOF
)"
```

---

## Task 9: scripts/score.py — スコア計算オーケストレーション

**Files:**
- Create: `scripts/score.py`

**Interfaces:**
- Consumes:
  - `storage.load_watchlist`, `storage.repo_snapshot_path`, `storage.load_snapshots`(Task 2)
  - `scoring.compute_star_velocity`, `scoring.compute_hn_velocity`, `scoring.compute_dependents_velocity`, `scoring.compute_percentile`, `scoring.compute_composite`, `scoring.WEIGHTS`(Task 3)
- Produces: `data/latest_scores.json`(形式は下記)。Task 10 の `render.py` がこのファイルを読む

`data/latest_scores.json` の形式:
```json
{
  "generated_at": "2026-07-27T00:00:00+00:00",
  "repos": [
    {
      "owner": "foo",
      "repo": "bar",
      "stars": 500,
      "star_velocity": 80,
      "star_percentile": 0.9,
      "hn_mentions_7d": 5,
      "hn_percentile": 0.7,
      "dependents": 20,
      "dependents_velocity": 5,
      "dependents_percentile": 0.6,
      "composite": 0.73
    }
  ]
}
```

コアロジック(`scoring.py`)はTask 3で既にテスト済みのため、このタスクではオーケストレーションのみを実装し新規の自動テストは追加しない。

- [ ] **Step 1: `scripts/score.py` を実装**

```python
#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

from common import scoring, storage

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
LATEST_SCORES_PATH = DATA_DIR / "latest_scores.json"

SIGNALS = ("star", "hn", "dependents")


def main() -> None:
    watchlist = storage.load_watchlist(WATCHLIST_PATH)
    today = datetime.now(timezone.utc).date().isoformat()

    velocities: dict[tuple[str, str], dict[str, int | None]] = {}
    latest_snapshot: dict[tuple[str, str], dict] = {}

    for entry in watchlist:
        owner, repo = entry["owner"], entry["repo"]
        path = storage.repo_snapshot_path(DATA_DIR, owner, repo)
        snapshots = storage.load_snapshots(path)
        if not snapshots:
            continue

        latest = sorted(snapshots, key=lambda s: s["date"])[-1]
        if latest["date"] != today:
            # 当日分のスナップショットが無いリポジトリは母集団・出力から除外する
            # (collect.pyが正常なら通常発生しないが、古いデータが紛れ込むのを防ぐ)
            continue

        key = (owner, repo)
        latest_snapshot[key] = latest
        velocities[key] = {
            "star": scoring.compute_star_velocity(snapshots),
            "hn": scoring.compute_hn_velocity(snapshots),
            "dependents": scoring.compute_dependents_velocity(snapshots),
        }

    populations: dict[str, list[float]] = {signal: [] for signal in SIGNALS}
    for v in velocities.values():
        for signal in SIGNALS:
            if v[signal] is not None:
                populations[signal].append(v[signal])

    repos_out = []
    for (owner, repo), v in velocities.items():
        percentiles = {
            signal: (
                scoring.compute_percentile(v[signal], populations[signal])
                if v[signal] is not None
                else None
            )
            for signal in SIGNALS
        }
        composite = scoring.compute_composite(percentiles, scoring.WEIGHTS)
        latest = latest_snapshot[(owner, repo)]

        repos_out.append(
            {
                "owner": owner,
                "repo": repo,
                "stars": latest.get("stars"),
                "star_velocity": v["star"],
                "star_percentile": percentiles["star"],
                "hn_mentions_7d": v["hn"],
                "hn_percentile": percentiles["hn"],
                "dependents": latest.get("dependents"),
                "dependents_velocity": v["dependents"],
                "dependents_percentile": percentiles["dependents"],
                "composite": composite,
            }
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repos": repos_out,
    }
    LATEST_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_SCORES_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"scored {len(repos_out)} repos")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 手動実行して動作確認**

Run:
```bash
python scripts/score.py
```
Expected: `scored N repos` と出力され、`data/latest_scores.json`が生成される。`cat data/latest_scores.json`で`generated_at`と`repos`配列(各要素にcompositeを含む)が確認できる

- [ ] **Step 3: コミット(スクリプトと、動作確認で生成された`data/latest_scores.json`を合わせてコミットする)**

```bash
git add scripts/score.py data/latest_scores.json
git commit -m "$(cat <<'EOF'
scripts/score.py: スコア計算オーケストレーションを実装

全リポジトリのスナップショットから変化量・パーセンタイル・合成
スコアを算出し、latest_scores.jsonに出力する。
EOF
)"
```

---

## Task 10: scripts/render.py — HTML生成

**Files:**
- Create: `scripts/render.py`
- Create: `tests/fixtures/latest_scores_sample.json`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `data/latest_scores.json`(Task 9が出力する形式)
- Produces:
  - `render_html(data: dict) -> str`(純粋関数、テスト対象)
  - `docs/index.html`(`main()`実行時に生成)

- [ ] **Step 1: フィクスチャJSONを作成**

`tests/fixtures/latest_scores_sample.json`:
```json
{
  "generated_at": "2026-07-27T00:00:00+00:00",
  "repos": [
    {
      "owner": "foo",
      "repo": "bar",
      "stars": 500,
      "star_velocity": 80,
      "star_percentile": 0.9,
      "hn_mentions_7d": 5,
      "hn_percentile": 0.7,
      "dependents": 20,
      "dependents_velocity": 5,
      "dependents_percentile": 0.6,
      "composite": 0.7333333333333333
    },
    {
      "owner": "foo",
      "repo": "baz",
      "stars": 100,
      "star_velocity": 10,
      "star_percentile": 0.3,
      "hn_mentions_7d": null,
      "hn_percentile": null,
      "dependents": 2,
      "dependents_velocity": 1,
      "dependents_percentile": 0.2,
      "composite": 0.25
    }
  ]
}
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_render.py`:
```python
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
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `pytest tests/test_render.py -v`
Expected: `ModuleNotFoundError: No module named 'render'`(まだ`scripts/render.py`が存在しないため)

- [ ] **Step 4: `scripts/render.py` を実装**

```python
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
```

- [ ] **Step 5: テストが通ることを確認**

Run: `pytest tests/test_render.py -v`
Expected: 4 passed

- [ ] **Step 6: 手動実行して動作確認**

Run:
```bash
python scripts/render.py
open docs/index.html
```
Expected: ブラウザで4つの表(総合・スター・HN・Dependents)が表示される

- [ ] **Step 7: コミット(スクリプト・テストと、動作確認で生成された`docs/index.html`を合わせてコミットする)**

```bash
git add scripts/render.py tests/test_render.py tests/fixtures/latest_scores_sample.json docs/index.html
git commit -m "$(cat <<'EOF'
scripts/render.py: HTMLダッシュボード生成を実装

総合ランキングとシグナル別3ランキングを表形式で出力。
欠損値は"-"表示、compositeの降順ソートをテストで検証。
EOF
)"
```

---

## Task 11: .github/workflows/daily.yml — 日次実行ワークフロー

**Files:**
- Create: `.github/workflows/daily.yml`
- Test: `tests/test_workflow_syntax.py`

**Interfaces:**
- Consumes: `scripts/discover.py`, `scripts/collect.py`, `scripts/score.py`, `scripts/render.py`(Task 7-10、すべて`python <path>`で直接実行可能)
- Produces: 毎日UTC 0:00(JST 9:00)に実行され、`data/`と`docs/`の変更を`main`ブランチにコミット・プッシュするGitHub Actionsワークフロー

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_workflow_syntax.py`:
```python
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "daily.yml"


def _load():
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_workflow_yaml_is_valid():
    assert _load() is not None


def test_workflow_has_daily_cron_schedule():
    data = _load()
    triggers = data.get("on") or data.get(True)
    assert triggers["schedule"][0]["cron"] == "0 0 * * *"


def test_workflow_supports_manual_dispatch():
    data = _load()
    triggers = data.get("on") or data.get(True)
    assert "workflow_dispatch" in triggers


def test_workflow_grants_contents_write_permission():
    data = _load()
    assert data["permissions"]["contents"] == "write"


def test_workflow_runs_all_four_pipeline_scripts():
    data = _load()
    steps = data["jobs"]["update"]["steps"]
    run_commands = " ".join(step.get("run", "") for step in steps)
    for script in ("discover.py", "collect.py", "score.py", "render.py"):
        assert script in run_commands
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest tests/test_workflow_syntax.py -v`
Expected: `FileNotFoundError`(まだ`daily.yml`が存在しないため)

- [ ] **Step 3: `.github/workflows/daily.yml` を作成**

```yaml
name: Daily Trend Update

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Discover new repositories
        run: python scripts/discover.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Collect daily signals
        run: python scripts/collect.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Compute scores
        run: python scripts/score.py

      - name: Render dashboard
        run: python scripts/render.py

      - name: Commit and push updates
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ docs/
          git diff --staged --quiet || git commit -m "chore: 日次トレンド更新 $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest tests/test_workflow_syntax.py -v`
Expected: 5 passed

- [ ] **Step 5: コミット**

```bash
git add .github/workflows/daily.yml tests/test_workflow_syntax.py
git commit -m "$(cat <<'EOF'
daily.yml: 日次トレンド更新ワークフローを追加

毎日UTC 0:00(JST 9:00)にdiscover→collect→score→renderを実行し、
data/とdocs/の変更をmainブランチにコミット・プッシュする。
YAML構文と主要フィールドをpytestで検証。
EOF
)"
```

---

## Task 12: GitHubリポジトリ作成・Pages有効化・初回動作確認

**Files:**
- Create: `docs/.nojekyll`

**Interfaces:**
- Consumes: Task 1-11 で作成した全ファイル
- Produces: `co-bit`アカウント配下のPublicリポジトリ、GitHub Pagesで公開されたダッシュボードURL

- [ ] **Step 1: `docs/.nojekyll` を作成(空ファイル)**

GitHub PagesのデフォルトJekyll処理を無効化し、生成された`index.html`をそのまま配信させるため。

```bash
touch docs/.nojekyll
```

- [ ] **Step 2: アクティブなgh CLIアカウントが`co-bit`であることを確認**

Run:
```bash
gh auth status
```
Expected: `co-bit`の行に `Active account: true` と表示されている。もし異なる場合は `gh auth switch --hostname github.com --user co-bit` を実行する

- [ ] **Step 3: `.nojekyll`をコミット**

```bash
git add docs/.nojekyll
git commit -m "$(cat <<'EOF'
GitHub PagesのJekyll処理を無効化

生成済みの静的HTMLをそのまま配信するため.nojekyllを追加。
EOF
)"
```

- [ ] **Step 4: GitHubリポジトリを作成してpush**

Run:
```bash
gh repo create co-bit/gh_trend --public --source=. --remote=origin --push
```
Expected: `co-bit/gh_trend` がPublicリポジトリとして作成され、現在の`main`ブランチの全コミットがpushされる

- [ ] **Step 5: GitHub Pagesを有効化**

Run:
```bash
gh api -X POST repos/co-bit/gh_trend/pages -f "source[branch]=main" -f "source[path]=/docs"
```
Expected: JSONレスポンスが返り、`status`が`building`または`built`になる。もし422エラー等で失敗する場合は、ブラウザで `https://github.com/co-bit/gh_trend/settings/pages` を開き、Source: Deploy from a branch / Branch: main / Folder: /docs を手動設定する

- [ ] **Step 6: ワークフローを手動トリガーして動作確認**

Run:
```bash
gh workflow run daily.yml --repo co-bit/gh_trend
gh run watch --repo co-bit/gh_trend
```
Expected: ワークフローが成功(`✓`)で完了する。失敗した場合は `gh run view --repo co-bit/gh_trend --log-failed` でログを確認する

- [ ] **Step 7: 公開URLを確認して開く**

Run:
```bash
gh api repos/co-bit/gh_trend/pages --jq .html_url
```
Expected: `https://co-bit.github.io/gh_trend/` のようなURLが表示される。ブラウザでアクセスし、総合ランキング・スター急上昇・Hacker News話題・Dependents急増の4表が表示されることを確認する

---

## 完了条件

- [ ] 全12タスクのコミットが完了している
- [ ] `pytest` がすべてグリーンである
- [ ] `co-bit/gh_trend` がPublicリポジトリとして存在し、GitHub Pagesが有効になっている
- [ ] `workflow_dispatch`での手動実行が成功し、`https://co-bit.github.io/gh_trend/` でダッシュボードが閲覧できる
- [ ] 翌日以降、cronによる自動実行で`data/`と`docs/index.html`が更新されることを確認する(初回実装完了後の運用確認事項)
