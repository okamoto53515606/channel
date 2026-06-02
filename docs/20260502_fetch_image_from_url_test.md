# fetch_image_from_url 単体テスト — 2026-06-02

## 背景

`strands_tools.image_reader` はローカルファイルパスのみ対応であり、
Web上の画像URL（CloudFront配信）を渡しても読み込めないことが判明。
代替として `fetch_image_from_url` を `tools.py` に追加し、動作確認を行った。

## テストコマンド

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
    model_id='claude-opus-4-6',
    max_tokens=1024,
)
agent = Agent(model=model, tools=[fetch_image_from_url])

result = agent('fetch_image_from_url で https://www.okamomedia.tokyo/media/articles/97f4aa48-50a1-7086-ea85-55d87a93e1cd/1780317827443-202605_aws_graph.png を取得して、何が写っているか日本語で説明してください。')
print(str(result))
"
```

## テスト結果

### 使用モデル
- `claude-opus-4-6`（Anthropic Direct API）

### 呼び出されたツール
- Tool #1: `fetch_image_from_url`

### Claudeの回答

> この画像は、**AWSの利用料金（コスト）の推移を示す折れ線グラフ**です。
>
> ### グラフの概要
> - **横軸（X軸）**：月（時間の経過を表す。2024年6月頃から2025年5月頃までの約1年間が表示されています）
> - **縦軸（Y軸）**：金額（米ドル $）で、AWSの利用コストを示しています
> - **タイトル**：「AWSコスト推移」と記載されています
>
> ### グラフの特徴
> - **オレンジ色の折れ線**が月ごとのAWS利用コストの変動を示しています
> - 全体的に**右肩上がりの傾向**が見られ、AWSの利用料金が月を追うごとに増加していることがわかります
> - 初期（左側）は比較的低い金額から始まり、後半（右側）に向かって金額が大きく上昇しています
> - 途中でいくつかの**急激な上昇ポイント**があり、特に後半に入ってからのコスト増加が顕著です
>
> ### 推測される用途
> クラウドインフラ（AWS）の月次コストをモニタリング・分析するためのグラフで、**コスト管理やコスト最適化の検討資料**として使われているものと考えられます。AWSのサービス利用拡大やトラフィック増加に伴い、料金が上がっていく様子が視覚的に表現されています。

## 判定

✅ **PASS** — URLから画像を取得し、グラフの内容（軸・タイトル・傾向）を正確に認識・説明できた。

## 補足

- `PydanticSerializationUnexpectedValue` の警告が出るが、strands SDK の既知の軽微な警告であり動作に影響なし
- 戻り値形式は `image_reader` と同一（`{"image": {"format": ..., "source": {"bytes": ...}}}`）
- Fargate上のエージェントはローカルファイルにアクセスできないため、`image_reader` は `build_common_tools()` から削除済み
