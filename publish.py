# publish.py — 静的HTML生成 + S3公開 + CloudFront invalidation
#
# DynamoDBからスレッドデータを取得 → BBS風HTML生成 → S3アップロード
# Blueprint §5 ③ Publish ステップの実装

import html
import logging
import os
import re
from pathlib import Path

import boto3
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
S3_BUCKET = os.getenv("S3_BUCKET", "okamo-channel")
CF_DISTRIBUTION_ID = os.getenv("CLOUDFRONT_DISTRIBUTION_ID", "")


def _get_s3():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))


def _get_cf():
    return boto3.client("cloudfront", region_name=os.getenv("AWS_REGION", "us-east-1"))


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
    )


# =====================================================================
# DynamoDB → 構造化データ取得
# =====================================================================
def fetch_thread_posts(thread_date: str) -> list[dict]:
    """指定日のスレッド全レスをDynamoDBから取得する。"""
    from db import _get_threads_table

    table = _get_threads_table()
    resp = table.query(
        KeyConditionExpression="thread_date = :d",
        ExpressionAttributeValues={":d": thread_date},
    )
    posts = sorted(resp["Items"], key=lambda x: x["post_number"])
    return posts


def fetch_all_threads() -> list[dict]:
    """全スレッド一覧（日付ごとの要約）を取得する。"""
    from db import _get_threads_table

    table = _get_threads_table()
    resp = table.scan()
    items = resp["Items"]

    # 日付ごとにグループ化
    threads_map: dict[str, dict] = {}
    for item in items:
        d = item["thread_date"]
        if d not in threads_map:
            threads_map[d] = {
                "thread_date": d,
                "title": "",
                "post_count": 0,
                "score": 0,
                "article_id": item.get("article_id", ""),
            }
        threads_map[d]["post_count"] += 1

        # openerからタイトル取得
        if item.get("post_type") == "opener":
            text = item.get("post_text", "")
            title_match = re.search(r"【.+?】(.+?)について語るスレ", text)
            if title_match:
                threads_map[d]["title"] = title_match.group(1).strip() + " について語るスレ"
            else:
                threads_map[d]["title"] = item.get("article_title", d)

        # まとめ役のスコアを総合評価として使う
        if item.get("poster_name") == "claude_summarizer":
            score = item.get("score")
            if score is not None:
                threads_map[d]["score"] = int(score)

    threads = sorted(threads_map.values(), key=lambda t: t["thread_date"], reverse=True)
    return threads


# =====================================================================
# テキスト → HTML変換
# =====================================================================
def _text_to_html(text: str) -> str:
    """BBSのプレーンテキストをHTMLに変換する。
    - HTMLエスケープ
    - >>N アンカーをリンク化
    - URLをリンク化
    - **太字** をstrongに変換
    """
    escaped = html.escape(text)

    # >>N アンカー → リンク
    escaped = re.sub(
        r"&gt;&gt;(\d+)",
        r'<a class="anchor" href="#post\1">&gt;&gt;\1</a>',
        escaped,
    )

    # URL → リンク
    escaped = re.sub(
        r"(https?://[^\s<>&]+)",
        r'<a href="\1" target="_blank" rel="noopener">\1</a>',
        escaped,
    )

    # **太字** → <strong>
    escaped = re.sub(
        r"\*\*(.+?)\*\*",
        r"<strong>\1</strong>",
        escaped,
    )

    return escaped


def _prepare_posts_for_html(posts: list[dict]) -> list[dict]:
    """DynamoDBのpostデータをHTML表示用に整形する。"""
    result = []
    for p in posts:
        score = p.get("score")
        if score is not None:
            score = int(score)
        result.append({
            "post_number": p["post_number"],
            "poster_name": p.get("poster_name", ""),
            "poster_display": p.get("poster_display", ""),
            "post_html": _text_to_html(p.get("post_text", "")),
            "score": score,
            "thread_date": p["thread_date"],
        })
    return result


# =====================================================================
# HTML生成
# =====================================================================
def generate_thread_html(thread_date: str, posts: list[dict]) -> str:
    """スレッドHTMLを生成する。"""
    env = _get_jinja_env()
    template = env.get_template("thread.html")

    html_posts = _prepare_posts_for_html(posts)

    # スレッドタイトル: openerから取得
    thread_title = thread_date
    for p in posts:
        if p.get("post_type") == "opener":
            text = p.get("post_text", "")
            title_match = re.search(r"【.+?】(.+?)$", text.split("\n")[0])
            if title_match:
                thread_title = title_match.group(1).strip()
            break

    return template.render(
        thread_title=thread_title,
        posts=html_posts,
    )


def generate_index_html(threads: list[dict]) -> str:
    """スレッド一覧HTMLを生成する。"""
    env = _get_jinja_env()
    template = env.get_template("index.html")
    return template.render(
        threads=threads,
        thread_count=len(threads),
    )


# =====================================================================
# KB用Markdown生成
# =====================================================================
def generate_thread_markdown(thread_date: str, posts: list[dict]) -> str:
    """Bedrock KB用のMarkdownを生成する。"""
    lines = []

    # ヘッダー
    article_id = ""
    article_title = ""
    for p in posts:
        if p.get("article_id"):
            article_id = p["article_id"]
        if p.get("article_title"):
            article_title = p["article_title"]
        if article_id and article_title:
            break

    lines.append(f"# スレッド: {thread_date}")
    if article_title:
        lines.append(f"## 記事: {article_title}")
    lines.append("")

    for p in posts:
        num = p["post_number"]
        display = p.get("poster_display", p.get("poster_name", ""))
        score_str = f" 評価: {int(p['score']):+d}" if p.get("score") is not None else ""
        lines.append(f"### {num} ： {display}{score_str}")
        lines.append("")
        lines.append(p.get("post_text", ""))
        lines.append("")

    return "\n".join(lines)


def generate_metadata_json(thread_date: str, article_id: str) -> str:
    """Bedrock KB用の .metadata.json を生成する。"""
    import json
    return json.dumps({
        "metadataAttributes": {
            "thread_date": thread_date,
            "article_id": article_id,
        }
    }, ensure_ascii=False)


# =====================================================================
# S3 アップロード
# =====================================================================
def upload_to_s3(key: str, body: str, content_type: str = "text/html; charset=utf-8"):
    """S3にファイルをアップロードする。"""
    s3 = _get_s3()
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType=content_type,
    )
    logger.info(f"Uploaded s3://{S3_BUCKET}/{key}")


def upload_css():
    """bbs.css を S3にアップロードする。"""
    css_path = TEMPLATES_DIR / "bbs.css"
    css_content = css_path.read_text(encoding="utf-8")
    upload_to_s3("site/assets/bbs.css", css_content, "text/css; charset=utf-8")


# =====================================================================
# CloudFront invalidation
# =====================================================================
def invalidate_cloudfront(paths: list[str] | None = None):
    """CloudFrontキャッシュを無効化する。"""
    dist_id = CF_DISTRIBUTION_ID
    if not dist_id:
        logger.warning("CLOUDFRONT_DISTRIBUTION_ID not set, skipping invalidation")
        return

    if paths is None:
        paths = ["/*"]

    cf = _get_cf()
    import time
    cf.create_invalidation(
        DistributionId=dist_id,
        InvalidationBatch={
            "Paths": {"Quantity": len(paths), "Items": paths},
            "CallerReference": str(int(time.time())),
        },
    )
    logger.info(f"CloudFront invalidation created for {paths}")


# =====================================================================
# メイン公開関数
# =====================================================================
def publish_thread(thread_date: str):
    """指定スレッドのHTML生成→S3アップロード→一覧再生成→CF invalidation。"""
    logger.info(f"Publishing thread: {thread_date}")

    # 1. スレッドデータ取得
    posts = fetch_thread_posts(thread_date)
    if not posts:
        logger.error(f"No posts found for {thread_date}")
        return

    # 2. article_id取得（KB用）
    article_id = ""
    for p in posts:
        if p.get("article_id"):
            article_id = p["article_id"]
            break

    # 3. スレッドHTML生成 → S3
    thread_html = generate_thread_html(thread_date, posts)
    upload_to_s3(f"site/threads/{thread_date}/index.html", thread_html)

    # 4. latest/ にも同じHTMLを配置
    upload_to_s3("site/latest/index.html", thread_html)

    # 5. KB用Markdown生成 → S3
    md = generate_thread_markdown(thread_date, posts)
    upload_to_s3(f"data/{thread_date}.md", md, "text/markdown; charset=utf-8")

    # 6. KB用メタデータ → S3
    metadata = generate_metadata_json(thread_date, article_id)
    upload_to_s3(
        f"data/{thread_date}.md.metadata.json",
        metadata,
        "application/json",
    )

    # 7. CSS アップロード
    upload_css()

    # 8. スレッド一覧（index.html）再生成 → S3
    threads = fetch_all_threads()
    index_html = generate_index_html(threads)
    upload_to_s3("site/index.html", index_html)

    # 9. CloudFront invalidation
    invalidate_cloudfront([
        f"/threads/{thread_date}/*",
        "/latest/*",
        "/index.html",
        "/",
    ])

    logger.info(f"Published thread {thread_date} ({len(posts)} posts)")
