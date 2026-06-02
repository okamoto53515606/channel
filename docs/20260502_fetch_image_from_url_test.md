# fetch_image_from_url テスト記録 — 2026-06-02

## 最終テストコマンド

```bash
cd /home/workspace/channel && source .venv/bin/activate && python3 -c "
from dotenv import load_dotenv
load_dotenv()

from strands import Agent
from strands.models.anthropic import AnthropicModel
import os

from tools import fetch_image_from_url

model = AnthropicModel(
    client_args={'api_key': os.getenv('CLAUDE_API_KEY')},
    model_id='claude-sonnet-4-6',
    max_tokens=1024,
)
agent = Agent(model=model, tools=[fetch_image_from_url])

result = agent('fetch_image_from_url で https://www.okamomedia.tokyo/media/articles/97f4aa48-50a1-7086-ea85-55d87a93e1cd/1780317825066-202605_aws_table.png を取得して、何が写っているか日本語で説明してください。特に金額・サービス名・日付などの具体的な数値を読み取ってください。')
print(str(result))
"
```

## テスト結果

- **モデル**: `claude-sonnet-4-6`
- **ツール**: Tool #1: `fetch_image_from_url`
- **判定**: ✅ PASS

### Claudeの回答（抜粋）

> **AWSのコストエクスプローラー（Cost Explorer）** のサービス別・日別コスト一覧テーブルです。
>
> | サービス名 | 合計 | 5/1 | 5/2 | 5/3 | 5/4 | 5/5 |
> |---|---|---|---|---|---|---|
> | **合計コスト** | **$7.22** | $0.24 | $0.24 | $0.27 | $0.28 | $0.28 |
> | **WAF** | **$4.73** | $0.20 | $0.19 | $0.19 | $0.20 | $0.19 |
> | **Secrets Manager** | **$2.32** | $0.04 | $0.04 | $0.07 | $0.08 | $0.08 |
> | **ECR** | $0.10 | … | … | … | … | … |
> | **DynamoDB** | $0.07 | … | … | … | … | … |
>
> - 月間合計 $7.22、WAF と Secrets Manager で全体の約97%
> - 日付範囲: 2026年5月1日〜31日、フィルター: グローバル・アジアパシフィック（東京）

金額・サービス名・日別内訳すべて正確に読み取れた。

---

## 紆余曲折した経緯と教訓

### 問題①: image_reader は Web URL を受け付けない

`strands_tools.image_reader` はローカルファイルパス専用。内部で `os.path.exists()` と `PIL.Image.open()` を使っておりURLを渡すと即エラー。

→ `fetch_image_from_url` を独自実装することにした。

### 問題②: 最初の実装は戻り値の形式が間違っていた

最初は `{"image": {"format": "png", "source": {"bytes": response.content}}}` を返す実装にした。一見 `image_reader` と同じ形式に見えたが、**`status` / `content` キーがない**ことが問題だった。

`@tool` デコレータの内部処理 (`_wrap_tool_result`) は以下の振り分けをしている：

```python
if isinstance(result, dict) and "status" in result and "content" in result:
    # そのまま通す（画像バイナリが正しくモデルに届く）
else:
    # json.dumps() → 失敗すれば str() でテキスト化して送る
    # bytes は JSON 非対応 → str(result) になり、モデルには文字列が届く
```

`bytes` は `json.dumps` できないため `str(result)` に変換され、モデルには
`"{'image': {'format': 'png', 'source': {'bytes': b'...'}}}"` という文字列が届いていた。
**モデルが「画像の説明」と言いながら全く関係ない内容を返していたのはこれが原因。**
（最初のテストで「1年間のコスト推移グラフ」「右肩上がり」などの誤認識が発生した理由）

### 問題③: import がモジュールを返していた

```python
from strands_tools import image_reader  # これはモジュール（関数ではない）
```

呼び出し可能な関数は `image_reader.image_reader`。そのまま呼ぶと `TypeError: 'module' object is not callable` が発生。

```python
from strands_tools import image_reader as _image_reader_module
_image_reader = _image_reader_module.image_reader  # これが正しい関数
```

### 最終実装の方針

URL から一時ファイルにダウンロードし、`image_reader` 関数に渡す。
`image_reader` が `ToolResult` 形式（`status`/`content` 付き）で返すため、
`@tool` デコレータがバイナリを正しく通してモデルに届く。
Docker 環境では `tempfile` が `/tmp/` 以下を使うため特別な対応不要。
