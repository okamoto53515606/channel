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
- 段階的開発フェーズ（Phase 1〜8）

## 技術スタック

- **Python**: メイン言語
- **Strands Agents SDK**: `Agent()`, `@tool`, `Swarm` クラス
- **strands_tools**: `image_reader`, `http_request`, `current_time`, `batch`
- **MCP**: GitHub（Remote MCP / Streamable HTTP）, Brave Search（stdio）
- **AWS CDK (Python)**: インフラ定義
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
特に `Swarm` クラスのパラメータと `MCPClient` の接続パターンに注意。
