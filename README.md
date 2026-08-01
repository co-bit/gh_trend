# gh_trend

GitHub公式のtrendingページ(https://github.com/trending)には依存せず、独自定義でMCP(Model Context Protocol)およびAIエージェント向けスキル/ツールのトレンドを観測するダッシュボード。GitHub Actionsで毎日自動更新され、GitHub Pagesで公開される。

**公開ダッシュボード:** https://co-bit.github.io/gh_trend/

## トレンドの定義

以下3つのシグナルを均等重みで合成した「総合トレンドスコア」でランキングし、各ランキングの上位20件を表示する。

1. **スター増加速度** — 直近7日間のスター数の増加を1日あたりの増加率に換算し、7日分に正規化した値
2. **話題性** — Hacker Newsでの直近7日間の言及件数(完全一致のフレーズ検索)
3. **依存関係からの採用度** — GitHubの`/network/dependents`ページに表示される依存リポジトリ数の増加を、スター増加速度と同様に7日分に正規化した値

各シグナルは母集団内でのパーセンタイル順位に変換してから合成する(外れ値に強く、桁違いのスケール差を吸収するため)。履歴の長さが異なるリポジトリでも公平に比較できるよう、変化量は7日分に正規化している。詳細は設計書を参照。

## アーキテクチャ

```
GitHub Actions (daily cron, JST 9:00)
  discover.py  → GitHub Search APIで新規リポジトリを発見し watchlist.json に追加(ページネーション対応)
  collect.py   → 各リポジトリのスター数・HN言及数・dependents数を日次スナップショットとして記録(30並列)
  score.py     → スナップショットから変化量・パーセンタイル・合成スコアを算出
  describe.py  → 上位20件のうち概要が未登録のリポジトリをGemini APIで日本語1行要約(GEMINI_API_KEY未設定時はスキップ)
  render.py    → docs/index.html を生成
  → git commit & push → GitHub Pagesが配信
```

## ローカルでの実行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest                        # テスト実行

python scripts/discover.py    # 新規リポジトリ発見
python scripts/collect.py     # 当日分シグナル収集
python scripts/score.py       # スコア計算
GEMINI_API_KEY=xxx python scripts/describe.py  # 日本語概要生成(任意、鍵なしでもスキップされるだけ)
python scripts/render.py      # HTML生成 (docs/index.html)
```

## ドキュメント

- 設計書: [`docs/superpowers/specs/2026-07-27-gh-trend-design.md`](docs/superpowers/specs/2026-07-27-gh-trend-design.md)
- 実装計画: [`docs/superpowers/plans/2026-07-27-gh-trend-dashboard.md`](docs/superpowers/plans/2026-07-27-gh-trend-dashboard.md)
