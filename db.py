# db.py — Runtime側ユーティリティ（@toolではない通常のPython関数）

import os
from datetime import datetime

import boto3


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
    table_name = os.getenv("DYNAMODB_THREADS_TABLE", "okamo-channel-threads")
    dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
    table = dynamodb.Table(table_name)

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
