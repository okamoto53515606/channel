# main.py — okamoちゃんねる エントリーポイント
#
# Phase 1: python main.py --url <記事URL>                    → Claude単体レビュー
# Phase 2: python main.py --url <記事URL> --mode swarm       → 3ペルソナGraph議論
# 本番:    python main.py                                     → 記事選択→Graph→公開

import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.models.openai import OpenAIModel
from strands.models.gemini import GeminiModel
from strands.multiagent.graph import GraphBuilder
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from strands_tools import image_reader, http_request, current_time

from prompts import (
    CLAUDE_SYSTEM_PROMPT, GPT_SYSTEM_PROMPT, GEMINI_SYSTEM_PROMPT,
    CLAUDE_SUMMARIZER_PROMPT,
)
from tools import fetch_article_content, get_past_threads, get_same_article_threads
from parser import parse_agent_output, parse_swarm_output, DISPLAY_NAMES

# =====================================================================
# ログ設定
# =====================================================================
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# =====================================================================
# 環境変数
# =====================================================================
JST = timezone(timedelta(hours=9))


def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# =====================================================================
# モデル / エージェント生成
# =====================================================================
def create_claude_model() -> BedrockModel:
    return BedrockModel(
        model_id=get_env("BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-6-v1"),
    )


def create_openai_model() -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": get_env("OPENAI_API_KEY")},
        model_id=get_env("OPEN_AI_MODEL_ID", "gpt-5.4"),
    )


def create_gemini_model() -> GeminiModel:
    return GeminiModel(
        client_args={"api_key": get_env("GEMINI_API_KEY")},
        model_id=get_env("GEMINI_MODEL_ID", "gemini-3.1-pro-preview"),
    )


# =====================================================================
# MCP 接続
# =====================================================================
def create_github_mcp() -> MCPClient:
    """GitHub MCP（Remote MCP / Streamable HTTP）"""
    pat = get_env("GITHUB_PAT_READ_ONLY_PUBLIC")
    return MCPClient(
        lambda: streamablehttp_client(
            url="https://api.githubcopilot.com/mcp/",
            headers={"Authorization": f"Bearer {pat}"},
        )
    )


def create_brave_mcp() -> MCPClient:
    """Brave Search MCP（stdio / npx）"""
    return MCPClient(lambda: stdio_client(
        StdioServerParameters(
            command="npx",
            args=["-y", "@brave/brave-search-mcp-server"],
            env={"BRAVE_API_KEY": get_env("BRAVE_API_KEY")},
        )
    ))


def build_common_tools() -> list:
    """全エージェント共通ツール"""
    return [
        fetch_article_content,
        get_past_threads,
        get_same_article_threads,
        image_reader,
        http_request,
        current_time,
    ]


def create_agents() -> dict[str, Agent]:
    """3ペルソナ + まとめ役のエージェントを生成する。"""
    common_tools = build_common_tools()
    github_mcp = create_github_mcp()
    brave_mcp = create_brave_mcp()

    claude_engineer = Agent(
        name="claude_engineer",
        model=create_claude_model(),
        system_prompt=CLAUDE_SYSTEM_PROMPT,
        tools=[*common_tools, github_mcp, brave_mcp],
    )

    gpt_tax_advisor = Agent(
        name="gpt_tax_advisor",
        model=create_openai_model(),
        system_prompt=GPT_SYSTEM_PROMPT,
        tools=[*common_tools, github_mcp, brave_mcp],
    )

    gemini_mother = Agent(
        name="gemini_mother",
        model=create_gemini_model(),
        system_prompt=GEMINI_SYSTEM_PROMPT,
        tools=[*common_tools, github_mcp, brave_mcp],
    )

    claude_summarizer = Agent(
        name="claude_summarizer",
        model=create_claude_model(),
        system_prompt=CLAUDE_SUMMARIZER_PROMPT,
        tools=[],
    )

    return {
        "claude_engineer": claude_engineer,
        "gpt_tax_advisor": gpt_tax_advisor,
        "gemini_mother": gemini_mother,
        "claude_summarizer": claude_summarizer,
    }


# =====================================================================
# スレ主（okamo）の >>1 を生成
# =====================================================================
def make_thread_opener(article: dict) -> str:
    """スレ主(okamo)の >>1 書き込みを生成する。"""
    today = datetime.now(JST).strftime("%Y/%m/%d")
    title = article.get("title", article.get("url", "不明"))
    url = article.get("url", "")

    return (
        f"【{today}】{title} について語るスレ\n\n"
        f"1 ： okamo (スレ主)\n"
        f"記事書いたから読んでくれ。\n"
        f"記事URL：{url}\n"
    )


# =====================================================================
# Phase 1: Claude 単体レビュー
# =====================================================================
def run_single_agent(article_url: str):
    """Claude単体で1記事をBBS形式レビュー。"""
    logger.info("=== Phase 1: Claude 単体レビュー ===")

    agents = create_agents()
    claude = agents["claude_engineer"]

    article = {"url": article_url, "title": article_url.split("/")[-1]}
    opener = make_thread_opener(article)

    prompt = (
        f"以下の記事をレビューしてください。\n"
        f"まず fetch_article_content ツールで記事の内容を取得し、\n"
        f"その後 BBS形式でレビューを書いてください。\n\n"
        f"スレ主（okamo）の書き込み:\n{opener}\n\n"
        f"あなたはレス番号 2 から書き始めてください。"
    )

    print("=" * 60)
    print(opener)
    print("-" * 60)

    result = claude(prompt)

    print(str(result))
    print("=" * 60)


# =====================================================================
# Phase 2-3: Graph 自律議論
# =====================================================================
def run_swarm(article_url: str):
    """4ノードGraphで決定論的議論（claude→gpt→gemini→まとめ）。"""
    logger.info("=== Phase 2-3: Graph 自律議論 ===")

    agents = create_agents()

    article = {"url": article_url, "title": article_url.split("/")[-1]}
    opener = make_thread_opener(article)

    builder = GraphBuilder()
    n_claude = builder.add_node(agents["claude_engineer"], "claude_engineer")
    n_gpt = builder.add_node(agents["gpt_tax_advisor"], "gpt_tax_advisor")
    n_gemini = builder.add_node(agents["gemini_mother"], "gemini_mother")
    n_summary = builder.add_node(agents["claude_summarizer"], "claude_summarizer")

    builder.add_edge(n_claude, n_gpt)
    builder.add_edge(n_gpt, n_gemini)
    builder.add_edge(n_gemini, n_summary)

    builder.set_execution_timeout(3000.0)   # 50分
    builder.set_node_timeout(600.0)         # 10分/ノード

    graph = builder.build()

    prompt = (
        f"以下の記事をレビューしてください。\n"
        f"まず fetch_article_content ツールで記事の内容を取得し、\n"
        f"BBS形式でレビューを書いてください。\n\n"
        f"スレ主（okamo）の書き込み:\n{opener}\n\n"
        f"レス番号 2 から書き始めてください。"
    )

    print("=" * 60)
    print(opener)
    print("-" * 60)

    result = graph(prompt)

    print(f"\nStatus: {result.status}")
    print(f"Execution order: {[node.node_id for node in result.execution_order]}")
    print(f"Completed: {result.completed_nodes}/{result.total_nodes}")
    print("=" * 60)


# =====================================================================
# エントリーポイント
# =====================================================================
def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="okamoちゃんねる — AI BBS レビューシステム")
    ap.add_argument("--url", help="レビュー対象の記事URL")
    ap.add_argument(
        "--mode",
        choices=["single", "swarm"],
        default="single",
        help="single: Claude単体(Phase1), swarm: 3ペルソナ議論(Phase2-3)",
    )
    args = ap.parse_args()

    if not args.url:
        print("--url で記事URLを指定してください", file=sys.stderr)
        print("例: python main.py --url https://www.okamomedia.tokyo/articles/homepage", file=sys.stderr)
        sys.exit(1)

    if args.mode == "single":
        run_single_agent(args.url)
    else:
        run_swarm(args.url)


if __name__ == "__main__":
    main()
