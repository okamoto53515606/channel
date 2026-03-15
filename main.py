# main.py — okamoちゃんねる エントリーポイント
#
# Phase 1: python main.py --url <記事URL> --mode single      → Claude単体レビュー
# Phase 2: python main.py --url <記事URL> --mode swarm       → 3ペルソナGraph議論
# Phase 5: python main.py                                     → 記事自動選択→Graph→DB保存
# Phase 5: python main.py --url <記事URL>                     → 指定記事→Graph→DB保存

import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from strands import Agent
from strands.models.anthropic import AnthropicModel
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
from tools import fetch_article_content, fetch_article_list, get_past_threads, get_same_article_threads
from parser import parse_agent_output, parse_graph_output, DISPLAY_NAMES
from db import save_post, select_next_article, update_queue_after_review
from publish import publish_thread

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
def create_claude_model() -> AnthropicModel:
    return AnthropicModel(
        client_args={"api_key": get_env("CLAUDE_API_KEY")},
        model_id=get_env("CLAUDE_MODEL_ID", "claude-opus-4-6"),
        max_tokens=16384,
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
    slug = article_url.rstrip("/").split("/")[-1]
    opener = make_thread_opener(article)
    thread_date = datetime.now(JST).strftime("%Y-%m-%d")

    builder = GraphBuilder()
    n_claude = builder.add_node(agents["claude_engineer"], "claude_engineer")
    n_gpt = builder.add_node(agents["gpt_tax_advisor"], "gpt_tax_advisor")
    n_gemini = builder.add_node(agents["gemini_mother"], "gemini_mother")
    n_summary = builder.add_node(agents["claude_summarizer"], "claude_summarizer")

    builder.add_edge(n_claude, n_gpt)
    builder.add_edge(n_gpt, n_gemini)
    builder.add_edge(n_gemini, n_summary)

    builder.set_execution_timeout(3000.0)   # 50分
    builder.set_node_timeout(1200.0)        # 20分/ノード

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

    # --- DynamoDB保存 ---
    # >>1 スレ主(okamo) を保存
    save_post(
        thread_date=thread_date,
        post_number="001",
        poster_name="okamo",
        poster_display="okamo（スレ主）",
        post_text=opener,
        article_id=slug,
        article_title=article.get("title", ""),
        post_type="opener",
    )
    logger.info("Saved opener as post 001")

    # 各AIの書き込みを保存
    posts = parse_graph_output(result)
    for post in posts:
        save_post(
            thread_date=thread_date,
            post_number=post["post_number"],
            poster_name=post["poster_name"],
            poster_display=post["poster_display"],
            post_text=post["post_text"],
            score=post.get("score"),
            article_id=slug,
            article_title=article.get("title", ""),
        )
        logger.info(f"Saved post {post['post_number']} by {post['poster_name']}")

    # queue更新
    update_queue_after_review(slug, thread_date)
    logger.info(f"Updated queue for article: {slug}")

    # --- 静的HTML生成 + S3公開 ---
    publish_thread(thread_date)

    return result


# =====================================================================
# Auto モード: 記事自動選択 → Graph → 保存
# =====================================================================
def run_auto():
    """記事一覧から次の対象を自動選択し、Graph議論→DB保存する。"""
    logger.info("=== Auto モード: 記事自動選択 ===")

    articles = fetch_article_list()
    logger.info(f"記事一覧: {len(articles)}件取得")

    selected = select_next_article(articles)
    if not selected:
        logger.error("レビュー対象の記事が見つかりません")
        sys.exit(1)

    logger.info(f"選択記事: {selected['title']} ({selected['url']})")
    print(f"📰 次の記事: {selected['title']}")
    print(f"   URL: {selected['url']}")
    print()

    run_swarm(selected["url"])


# =====================================================================
# エントリーポイント
# =====================================================================
def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="okamoちゃんねる — AI BBS レビューシステム")
    ap.add_argument("--url", help="レビュー対象の記事URL（省略時は自動選択）")
    ap.add_argument(
        "--mode",
        choices=["single", "swarm", "auto"],
        default="auto",
        help="single: Claude単体(Phase1), swarm: 3ペルソナ議論(Phase2-3), auto: 記事自動選択(Phase5)",
    )
    args = ap.parse_args()

    if args.mode == "single":
        if not args.url:
            print("--mode single では --url が必要です", file=sys.stderr)
            sys.exit(1)
        run_single_agent(args.url)
    elif args.mode == "swarm":
        if not args.url:
            print("--mode swarm では --url が必要です", file=sys.stderr)
            sys.exit(1)
        run_swarm(args.url)
    else:
        # auto モード
        if args.url:
            run_swarm(args.url)
        else:
            run_auto()


if __name__ == "__main__":
    main()
