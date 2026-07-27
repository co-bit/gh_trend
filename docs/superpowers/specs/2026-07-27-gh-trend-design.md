# GitHub AI/MCPトレンド観測ダッシュボード 設計書

- 日付: 2026-07-27
- ステータス: 承認済み

## 背景・目的

GitHub公式のtrendingページ(https://github.com/trending)は依存せず、AI関連スキル・MCP(Model Context Protocol)に関するリポジトリの「トレンド」を独自の定義で観測する。結果は1日1回更新されるHTMLダッシュボードとして公開する。

## トレンドの定義

以下3つのシグナルの組み合わせで「トレンド」を定義する。単一の官能的な人気度(スター総数など)ではなく、**変化量**に着目する。

1. **スター増加速度**: 直近7日間のスター数の増加数
2. **話題性(外部言及)**: Hacker Newsでの直近7日間の言及件数
3. **依存関係からの採用度**: GitHubの `/network/dependents` ページに表示される依存リポジトリ数の直近7日間の増加数

対象スコープは **MCP(Model Context Protocol)と、特定ベンダーに限らない「AIエージェント向けスキル/ツール」全般に絞る**。「スキル」はClaude Skillsに限定せず、OpenAI GPTs、LangChain tools、AutoGPTプラグインなど、エージェントに追加機能を与えるパッケージ全般を対象とする。GitHub Search APIでの新規発見時のキーワード/トピック例:
- MCP: `topic:mcp-server`, `topic:model-context-protocol`
- 汎用スキル/ツール: `topic:agent-skills`, `topic:llm-tools`, `topic:ai-agent-toolkit`, `topic:claude-skill`, `topic:claude-code`

ユーザーの関心に直結するもののみに絞り、汎用的すぎる `topic:ai`, `topic:llm` のような広範キーワードは含めない(ノイズが増えすぎるため)。

## アーキテクチャ

```
GitHub Actions (daily cron, JST 9:00)
  │
  ├─ 1. discover.py  ─ GitHub Search API で MCP/AIエージェントスキル関連の新規リポジトリを発見
  │                     → data/watchlist.json に追加(既存分は保持、上限なし)
  │
  ├─ 2. collect.py   ─ watchlist の全リポジトリについて当日分のシグナルを収集
  │                     ・スター数: GitHub REST API
  │                     ・話題性: HN Algolia Search API でのリポジトリ名/URL言及件数
  │                     ・採用度: /network/dependents ページをスクレイピングして件数取得
  │                     → data/repos/<owner>__<repo>.json に1日分スナップショット追記
  │                     → 90日より古いスナップショットは削除(ローテーション)
  │
  ├─ 3. score.py     ─ 全スナップショットから各シグナルの変化量を算出し、
  │                     当日追跡中の全リポジトリ内でのパーセンタイル順位に変換、
  │                     均等重み(1/3ずつ)で合成 → data/latest_scores.json
  │
  ├─ 4. render.py    ─ latest_scores.json から docs/index.html を生成
  │                     (総合ランキング1本 + シグナル別ランキング3本を並列表示)
  │
  └─ 5. git commit & push (data/ と docs/ の変更)
         │
         └─ GitHub Pages が docs/ を配信(mainブランチのdocs/フォルダをソースにする)
```

ディレクトリ構成:

```
scripts/
  discover.py
  collect.py
  score.py
  render.py
  common/          # API呼び出し・パース・パーセンタイル計算などの共通ロジック
data/
  watchlist.json
  repos/<owner>__<repo>.json
  latest_scores.json
docs/
  index.html       # GitHub Pagesの配信元
.github/workflows/
  daily.yml
tests/
  test_score.py
  test_collect_parser.py
  test_render.py
  fixtures/        # dependentsページのサンプルHTMLなど
```

各スクリプトは「前段の出力ファイルを読んで次段の出力ファイルを書く」だけの独立したパイプラインステージとし、単体でも手動実行・デバッグ可能にする。

## データ設計

**`data/watchlist.json`**
```json
[{ "owner": "foo", "repo": "bar", "first_seen": "2026-07-27", "source": "search:mcp-server" }]
```

**`data/repos/<owner>__<repo>.json`**(日次スナップショットの配列、90日分まで保持)
```json
[{ "date": "2026-07-27", "stars": 1234, "hn_mentions": 3, "dependents": 56 }]
```
シグナル取得に失敗した項目は `null` を格納し、欠損として扱う(0扱いにしない)。

**`data/latest_scores.json`**
リポジトリごとに、当日の生値・7日変化量・各シグナルのパーセンタイル・合成スコアを保持する。`render.py` はこのファイルのみを読んでHTMLを生成する。

## スコア計算ロジック

**変化量(velocity)**
- スター増加速度: `today.stars - 7days_ago.stars`(7日分の履歴がなければある範囲で計算)
- 話題性: 直近7日間のHN言及件数の合計
- 採用度: 直近7日間のdependents増加数

**パーセンタイル順位への変換**
当日スナップショットが存在する全リポジトリを母集団とし、各シグナルの変化量を昇順ソートして `(自分より小さい値を持つリポジトリ数) / 母集団数` でパーセンタイル(0〜1)を算出する。

**合成スコア**
算出できたシグナルのみの平均を取る:
```
composite = (pctl_star + pctl_hn + pctl_dependents) / 算出できたシグナル数
```
欠損シグナルは合成対象から除外し、0点扱いにはしない。重みは `score.py` 冒頭の定数として切り出す:
```python
WEIGHTS = {"star": 1/3, "hn": 1/3, "dependents": 1/3}
```

## HTML出力

`docs/index.html` に以下を表示する:
- 総合トレンドスコアによるランキング(1本)
- シグナル別ランキング(スター急上昇 / HN話題 / Dependents急増)の3セクションを並列表示
- 各リポジトリ行: リポジトリ名・リンク・各シグナルの生値と変化量・合成スコア
- 更新日時

静的HTML1ファイルとして生成し、追加のサーバーサイド処理は不要。

## エラーハンドリング

「1リポジトリの失敗で全体を止めない」ことを最優先とする。

- **GitHub REST/Search API**: レート制限時は指数バックオフで最大3回リトライ。失敗が続く場合は該当シグナルを欠損(null)として記録し処理継続
- **`/network/dependents` スクレイピング**: 非公式HTML構造に依存する最も壊れやすい箇所。パース失敗は例外を握りつぶして欠損値として記録しログに残す。前日値へのフォールバックはしない(欠損はパーセンタイル計算側で対応済み)
- **HN Algolia API**: 同様にリトライ→失敗時は欠損
- **discover.py**: 検索0件・APIエラー時もwatchlist.jsonは前日の状態を維持して処理継続
- **初回実行**: watchlist.json / repos/ が空のケースを正常系として扱う。履歴不足の指標は欠損扱い(0扱いにしない)
- **ワークフロー全体**: いずれかのスクリプトが想定外の例外で落ちた場合はその日のcommitをスキップしてActionsを失敗させる(中途半端な状態でcommitしない)

## テスト方針

外部API・スクレイピングに依存する部分はモック/fixture化し、ロジック部分を自動テスト対象にする。

- **`score.py`**: パーセンタイル計算・合成ロジックを純粋関数として切り出しpytestでユニットテスト。欠損混在・母集団1件・全員同値などの境界条件を重点的にカバー
- **`collect.py`のパーサー**: `/network/dependents` のHTMLパース関数を独立させ、保存済みサンプルHTML(fixture)でテスト。実HTTPは叩かない
- **`discover.py`**: レスポンス整形ロジックのみユニットテスト対象。実API呼び出しはテスト対象外(手動dry-runで確認)
- **`render.py`**: サンプルの`latest_scores.json`を入力にHTML生成を確認する簡易テスト
- **E2E**: 日次バッチという性質上、GitHub Actions上での実行自体が実質的な統合テストとなるため重厚なE2Eは組まない。初回は`workflow_dispatch`で手動トリガーして動作確認する

## 実行環境

- GitHub Actions の cron スケジュール(毎日 JST 9:00 = UTC 0:00)
- 実装言語: Python
- GitHub Pages: mainブランチの `docs/` フォルダをソースとして配信
- 認証: Actions標準の `GITHUB_TOKEN` を使用(Search API・REST APIともに追加のシークレット登録は不要)

## 既知の制約・将来の検討事項

- `/network/dependents` は非公式ページのスクレイピングであり、GitHub側のHTML構造変更で壊れる可能性がある(エラーハンドリングで欠損扱いにすることで許容)
- 監視対象リポジトリ数に上限を設けないため、長期的にリポジトリ数が増えると1日あたりのAPI呼び出し数・スクレイピング件数が増加する。数百件規模までは問題ないが、将来的にボトルネックになった場合は上位N件への絞り込みを検討する
- 3シグナルの重みは現在均等(1/3ずつ)。運用しながら妥当性を見直す余地がある
