# db.py — Runtime側ユーティリティ（@toolではない通常のPython関数）

import os
from datetime import datetime

import boto3


def _get_threads_table():
    table_name = os.getenv("DYNAMODB_THREADS_TABLE", "okamo-channel-threads")
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return dynamodb.Table(table_name)


def _get_queue_table():
    table_name = os.getenv("DYNAMODB_QUEUE_TABLE", "okamo-channel-queue")
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return dynamodb.Table(table_name)


def save_post(
    thread_date: str,
    post_number: str,
    poster_name: str,
    poster_display: str,
    post_text: str,
    score: int = None,
    article_id: str = "",
    article_title: str = "",
    post_type: str = "auto",
) -> dict:
    """BBS書き込みをDynamoDBに保存する。
    AI（@tool）としては公開しない。Runtime側から直接呼ぶ。"""
    table = _get_threads_table()

    item = {
        "thread_date": thread_date,
        "post_number": post_number,
        "poster_name": poster_name,
        "poster_display": poster_display,
        "post_text": post_text,
        "post_type": post_type,
        "created_at": datetime.now().isoformat(),
    }
    if article_id:
        item["article_id"] = article_id
    if article_title:
        item["article_title"] = article_title
    if score is not None:
        item["score"] = score

    table.put_item(Item=item)
    return {"status": "saved", "thread_date": thread_date, "post_number": post_number}


def select_next_article(articles: list[dict]) -> dict | None:
    """記事一覧とqueueを突き合わせ、次のレビュー対象を決定する。

    1. 未登録の記事を queue に追加
    2. 公開日昇順で、last_reviewed が最も古い（or 未レビュー）記事を選定
    """
    table = _get_queue_table()

    # 1. 未登録の記事を queue に追加
    for article in articles:
        existing = table.get_item(
            Key={"queue_id": "article_queue", "article_id": article["slug"]}
        ).get("Item")

        if not existing:
            table.put_item(Item={
                "queue_id": "article_queue",
                "article_id": article["slug"],
                "article_title": article["title"],
                "article_url": article["url"],
                "published_date": article.get("published_date", ""),
                "review_count": 0,
            })

    # 2. 次のレビュー対象を決定
    all_items = table.query(
        KeyConditionExpression="queue_id = :q",
        ExpressionAttributeValues={":q": "article_queue"},
    )["Items"]

    if not all_items:
        return None

    # 未レビュー記事のみ対象（review_count が 0 または last_reviewed が未設定）
    unreviewed = [i for i in all_items if not i.get("last_reviewed")]

    if not unreviewed:
        return None

    unreviewed.sort(key=lambda i: i.get("published_date", ""))
    selected = unreviewed[0]
    return {
        "slug": selected["article_id"],
        "title": selected.get("article_title", ""),
        "url": selected.get("article_url", ""),
        "published_date": selected.get("published_date", ""),
    }


def update_queue_after_review(article_id: str, review_date: str) -> None:
    """レビュー完了後にqueueを更新する。"""
    table = _get_queue_table()
    table.update_item(
        Key={"queue_id": "article_queue", "article_id": article_id},
        UpdateExpression="SET last_reviewed = :d ADD review_count :one",
        ExpressionAttributeValues={":d": review_date, ":one": 1},
    )
