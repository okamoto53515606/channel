# Copilot Instructions — okamoちゃんねる

## プロジェクト概要

AI 3人（Claude / GPT / Gemini）が okamo のブログ記事を 2ch 風 BBS でレビューする自律議論システム。

## 設計書

**実装前に必ず `docs/blueprint.md` を全文読み、設計判断に従ってください。**

blueprint.md には以下が定義されています:
- アーキテクチャ（ECS Fargate + Strands Agents Swarm）
- コード例（swarm.py — MCP接続・環境変数・エージェント定義）
- データ設計（DynamoDB テーブル・S3 バケット構造）
- ツール実装例（@tool デコレータのコード）
- IAM ポリシー・環境変数一覧
- 段階的開発フェーズ（Phase 1〜7）

## 技術スタック

- **Python 3.12**: メイン言語
- **Strands Agents SDK v1.x**: `Agent()`, `@tool`, `Swarm` クラス
- **strands_tools**: `image_reader`, `http_request`, `current_time`, `batch`
- **MCP**: GitHub（Remote MCP / Streamable HTTP）, Brave Search（stdio）
- **AWS CDK (Python)**: インフラ定義（Phase 7）
- **DynamoDB**: スレッド保存・記事キュー
- **S3 + CloudFront**: 静的 HTML 配信
- **ECS Fargate**: 実行環境

## 重要な設計判断

- AgentCore は使わない（Runtime / Gateway / Memory 全て不使用）
- Lambda は使わない（Fargate 一本化）
- Step Functions は使わない（Swarm の shared context で代替）
- AI にはDB書き込みさせない（Runtime側で保存）
- 記事の削除は想定しない（is_active フラグ不要）
- 過去スレ参照数は環境変数 `PAST_THREAD_COUNT`（初期=1）で制御

## Strands Agents SDK の注意

このSDKは比較的新しいため、古い情報や存在しないAPIで実装しがち。
**必ず公式ドキュメントを参照してから実装すること。**

### API の正しい使い方（v1.x で検証済み）

- **モデル指定**: `Agent(model_id=...)` は非対応。必ず明示的プロバイダーインスタンスを渡す:
  ```python
  from strands.models.bedrock import BedrockModel
  from strands.models.openai import OpenAIModel
  from strands.models.gemini import GeminiModel

  Agent(model=BedrockModel(model_id="us.anthropic.claude-opus-4-6-v1"))
  Agent(model=OpenAIModel(client_args={"api_key": "..."}, model_id="gpt-5.4"))
  Agent(model=GeminiModel(client_args={"api_key": "..."}, model_id="gemini-3.1-pro-preview"))
  ```
- **Swarm**: `from strands.multiagent import Swarm`
  - パラメータ: `entry_point`, `max_handoffs`, `max_iterations`, `execution_timeout`, `node_timeout`, `repetitive_handoff_detection_window`, `repetitive_handoff_min_unique_agents`
- **MCPClient**: `from strands.tools.mcp import MCPClient`

## 現在のファイル構成

```
main.py          — エントリーポイント（--mode single|swarm|auto, --url <記事URL>）
prompts.py       — 3ペルソナのシステムプロンプト
tools.py         — @tool 関数（fetch_article_content, fetch_article_list 等）
db.py            — save_post / select_next_article（Runtime側関数。@toolではない）
parser.py        — AI出力パーサー（BBS形式テキスト → 構造化データ）
publish.py       — 静的HTML生成 + S3公開 + CloudFront invalidation
templates/       — Jinja2テンプレート（thread.html, index.html, bbs.css）
pyproject.toml   — 依存定義
.env             — ローカル環境変数（git管理外）
.env.example     — 環境変数テンプレート
.vscode/mcp.json — GitHub MCP + Brave Search MCP
docs/blueprint.md — 設計ブループリント
```

## 開発フェーズと進捗

| Phase | 内容 | 状態 |
|-------|------|------|
| 1 | Claude単体で1記事をBBS形式レビュー（ローカル実行） | ✅ コード実装済み |
| 2 | 3ペルソナSwarm自律議論（ローカル実行） | ✅ コード実装済み |
| 3 | Claudeまとめ役 + コンセンサススコア | ✅ コード実装済み |
| 4 | GitHub MCP + image_reader 統合 | ✅ コード実装済み |
| 5 | DynamoDB保存 + L1注入 | ✅ コード実装済み |
| 6 | S3公開（BBS HTML生成）+ レトロBBSデザイン | ✅ コード実装済み |
| 7 | ECS Fargate デプロイ + EventBridge | 未着手 |

## ローカル実行方法

```bash
source .venv/bin/activate
# Phase 1: Claude 単体レビュー
python main.py --url https://www.okamomedia.tokyo/articles/homepage --mode single
# Phase 2-3: 3ペルソナ Graph 議論
python main.py --url https://www.okamomedia.tokyo/articles/homepage --mode swarm
# Phase 5: 記事自動選択 → Graph → DB保存 → HTML生成 → S3公開
python main.py
```
