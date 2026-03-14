# tools.py — @tool 関数定義

import os
import re

import requests
from bs4 import BeautifulSoup
from strands import tool


@tool
def fetch_article_list() -> list[dict]:
    """www.okamomedia.tokyo のトップページをクロールし、全記事一覧を取得する。
    サイトDBには触れず、公開ページのみを情報源とする。"""
    response = requests.get("https://www.okamomedia.tokyo/", timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    articles = []
    for link in soup.find_all("a", href=re.compile(r"/articles/")):
        href = link.get("href", "")
        slug = href.rstrip("/").split("/articles/")[-1]
        if not slug:
            continue

        text = link.get_text(separator=" ", strip=True)

        # 日付パース: "2026年3月10日" → "2026-03-10"
        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        published_date = (
            f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
            if date_match
            else ""
        )

        # タイトル: テキストの先頭部分
        title = text.split("\n")[0].strip() if "\n" in text else text[:80]

        articles.append(
            {
                "slug": slug,
                "title": title,
                "url": f"https://www.okamomedia.tokyo/articles/{slug}",
                "published_date": published_date,
            }
        )

    # 公開日昇順（古い記事からレビュー）
    articles.sort(key=lambda a: a["published_date"])
    return articles


@tool
def fetch_article_content(article_url: str) -> dict:
    """対象記事のHTMLを取得し、テキストと画像URLを抽出する。"""
    response = requests.get(article_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # 本文テキスト抽出
    article_body = soup.find("article") or soup.find("main") or soup.body
    text = article_body.get_text(separator="\n", strip=True) if article_body else ""

    # 画像URL抽出（マルチモーダル入力用）
    images = [
        img["src"]
        for img in (article_body or soup).find_all("img")
        if img.get("src")
    ]

    # GitHub リンク抽出
    github_links = [
        a["href"]
        for a in (article_body or soup).find_all("a", href=re.compile(r"github\.com"))
        if a.get("href")
    ]

    return {
        "text": text,
        "images": images,
        "github_links": github_links,
        "url": article_url,
    }


@tool
def get_past_threads(count: int = None) -> str:
    """直近N回分のスレッド全文をDynamoDBから取得する。
    Nは環境変数 PAST_THREAD_COUNT（デフォルト=1）。
    N=0 の場合は過去スレを参照しない。
    okamoの手動書き込みも含む。"""
    if count is None:
        count = int(os.getenv("PAST_THREAD_COUNT", "1"))
    if count <= 0:
        return "過去スレッド参照なし（PAST_THREAD_COUNT=0）"

    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    table = dynamodb.Table(os.getenv("DYNAMODB_THREADS_TABLE", "okamo-channel-threads"))

    # thread_date の降順で直近N件のユニークな日付を取得
    response = table.scan(ProjectionExpression="thread_date")
    if not response["Items"]:
        return "過去スレッドなし（初回実行）"

    dates = sorted({item["thread_date"] for item in response["Items"]}, reverse=True)
    recent_dates = dates[:count]

    results = []
    for date in sorted(recent_dates):  # 古い順に並べ直す
        thread_response = table.query(
            KeyConditionExpression="thread_date = :d",
            ExpressionAttributeValues={":d": date},
        )
        if thread_response["Items"]:
            thread_posts = sorted(thread_response["Items"], key=lambda x: x["post_number"])
            thread_text = f"## スレッド: {date} - {thread_posts[0].get('article_title', '不明')}\n"
            for post in thread_posts:
                score_str = f" 評価: {post['score']}" if post.get("score") is not None else ""
                thread_text += f"\n{post['post_number']} ： {post['poster_display']}{score_str}\n{post['post_text']}\n"
            results.append(thread_text)

    return "\n\n---\n\n".join(results) if results else "過去スレッドなし（初回実行）"


@tool
def get_same_article_threads(article_id: str) -> str:
    """同一記事の過去スレッドをGSI経由で全件取得する。
    再レビュー時のスコア変遷比較に使用。"""
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    table = dynamodb.Table(os.getenv("DYNAMODB_THREADS_TABLE", "okamo-channel-threads"))

    response = table.query(
        IndexName="article-index",
        KeyConditionExpression="article_id = :aid",
        ExpressionAttributeValues={":aid": article_id},
    )
    if not response["Items"]:
        return "この記事の過去スレッドなし（初回レビュー）"

    # thread_date でグルーピング
    threads: dict[str, list] = {}
    for item in response["Items"]:
        d = item["thread_date"]
        threads.setdefault(d, []).append(item)

    results = []
    for date in sorted(threads.keys()):
        posts = sorted(threads[date], key=lambda x: x["post_number"])
        title = posts[0].get("article_title", "不明")
        scores = {p["poster_name"]: p["score"] for p in posts if p.get("score") is not None}
        score_line = " / ".join(f"{k}: {v:+d}" for k, v in scores.items())
        thread_text = f"## 過去スレ: {date} - {title}\nスコア: {score_line}\n"
        for post in posts:
            score_str = f" 評価: {post['score']}" if post.get("score") is not None else ""
            thread_text += f"\n{post['post_number']} ： {post['poster_display']}{score_str}\n{post['post_text']}\n"
        results.append(thread_text)

    return "\n\n---\n\n".join(results)
