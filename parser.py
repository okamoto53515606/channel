# parser.py — AI出力のパース

import re

# poster_name → poster_display のマッピング
DISPLAY_NAMES = {
    "claude_engineer": "クロード（辛口エンジニア）",
    "gpt_tax_advisor": "GPT（税理士）",
    "gemini_mother": "Gemini（お母さん）",
    "claude_summarizer": "クロード（まとめ役）",
}


def parse_agent_output(text: str, agent_name: str) -> list[dict]:
    """エージェントの出力テキストからレス（書き込み）をパースする。

    返り値: [{"post_number": "002", "post_text": "...", "score": 3}, ...]
    """
    posts = []

    # パターン: "N ： 表示名 評価: +X" or "N ： 表示名 評価: -X"
    pattern = re.compile(
        r"^(\d+)\s*[：:]\s*(.+?)\s+評価:\s*([+-]?\d+)\s*$",
        re.MULTILINE,
    )

    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        post_number = match.group(1).zfill(3)
        score = int(match.group(2 + 1))  # group(3)

        # 本文: このマッチの終わりから次のマッチの始まりまで
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        post_text = text[start:end].strip()

        posts.append(
            {
                "post_number": post_number,
                "post_text": post_text,
                "score": score,
                "poster_name": agent_name,
                "poster_display": DISPLAY_NAMES.get(agent_name, agent_name),
            }
        )

    # マッチしなかった場合: 全体を1つのポストとして扱う
    if not posts:
        score = _extract_score(text)
        posts.append(
            {
                "post_number": "002",
                "post_text": text.strip(),
                "score": score,
                "poster_name": agent_name,
                "poster_display": DISPLAY_NAMES.get(agent_name, agent_name),
            }
        )

    return posts


def parse_swarm_output(result) -> list[dict]:
    """Swarm実行結果からレス一覧をパースする。

    result: SwarmResult (result.node_history, result.results)
    """
    all_posts = []
    post_counter = 2  # レス番号は002から（001はokamoスレ主）

    for node in result.node_history:
        agent_name = node.node_id
        agent_result = result.results.get(agent_name)
        if not agent_result:
            continue

        text = str(agent_result.result)
        posts = parse_agent_output(text, agent_name)

        # レス番号を連番で振り直す
        for post in posts:
            post["post_number"] = str(post_counter).zfill(3)
            post_counter += 1
            all_posts.append(post)

    return all_posts


def parse_graph_output(result) -> list[dict]:
    """Graph実行結果からレス一覧をパースする。

    result: GraphResult (result.execution_order, result.results)
    """
    all_posts = []
    post_counter = 2  # レス番号は002から（001はokamoスレ主）

    for node in result.execution_order:
        agent_name = node.node_id
        node_result = result.results.get(agent_name)
        if not node_result or not node_result.result:
            continue

        text = str(node_result.result)
        posts = parse_agent_output(text, agent_name)

        for post in posts:
            post["post_number"] = str(post_counter).zfill(3)
            post_counter += 1
            all_posts.append(post)

    return all_posts


def _extract_score(text: str) -> int | None:
    """テキストからスコアを抽出する。見つからない場合はNone。"""
    # "評価: +3" or "評価: -2" パターン
    match = re.search(r"評価:\s*([+-]?\d+)", text)
    if match:
        return int(match.group(1))
    return None
