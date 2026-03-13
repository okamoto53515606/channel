# okamoちゃんねる — 設計ブループリント

## 1. コンセプト

「okamoのhomepage」の記事を、3人のAI仮想読者が**2ちゃんねる風BBS形式**で毎日レビューし、その議論自体をエンタメコンテンツとして公開するシステム。

ビジネスライクなGA4分析やファクトチェックではなく、**キャラの立った「常連読者」によるワイワイ掲示板**を自動生成する。okamoのサイトが「小説＝物語」であるならば、AIたちは熱狂的な読者であり、辛口の書評家であり、時にはokamoをイジる仲間である。

### 名称

- **サイト名**: okamoちゃんねる
- **URL**: `https://channel.okamomedia.tokyo/`
- **レビュー対象**: `https://www.okamomedia.tokyo/`（okamoのhomepage）
- **形式**: 日付ごとのスレッド（1日1記事）
- **公開先**: S3 + CloudFront + OAC（静的HTML配信）
- **リージョン**: us-east-1（コスト最適化。ACM証明書もCFと同一リージョン）

### 運用ループ

1. **朝バッチ**: EventBridgeがECS Fargateタスクを起動 → 3人のAIがSwarmで自律議論 → BBS HTML生成・公開
2. **日中〜夜**: okamoが手動でレス（反論・言い訳）をDynamoDBに書き込む
3. **翌朝バッチ**: AIが前日のokamoの書き込みを含む直近3日分を読み込んだ上で、次の記事をレビュー

### 記事選択ルール

- 最も古い記事から1日1記事ずつ順番にレビュー
- 最新記事に到達したら、最も古い記事に戻って再レビュー（ループ）
- 再レビュー時は前回の評価との変化がエンタメになる（AIの評価が変わる大河ドラマ性）

## 2. AIペルソナ（キャスト）

### Claude — 辛口エンジニア（男性）

- **読者ペルソナ**: 腕の立つ中堅ITエンジニア。美しいコードと自動化を愛する
- **行動**: 真っ先にGitHubのソースコード・プロンプト生ログを読み込む
- **視点**: 技術的ツッコミ、非効率への愛あるダメ出し、同業者としての共感
- **口調**: 「おいokamo」「〜だぞ」— フランクで少し偉そうな同僚口調
- **スコア傾向**: 技術的に甘い記事には容赦なくマイナス。泥臭い試行錯誤のログが残っていると加点

### GPT — 独立系税理士（男性）

- **読者ペルソナ**: 独立して事務所を構える40代フリーランス税理士。Web広告やサブスクを嫌い、okamoの「広告ゼロ・都度課金」のhomepageシステムを自分のビジネスに導入したいと狙っている
- **行動**: GitHubの手順書（README）やスクショを丹念に読み、自分でも再現できるかチェック
- **視点**: 環境構築の分かりやすさ、ビジネスモデルの実用性。お金・税務・決済の話にはプロ目線でマジレス
- **裏設定（中辛スパイス）**: ビジネス的合理性に加え、okamoの心理面（承認欲求の強さ、目立ちたいだけの行動、目的のブレなど）を見透かし、「大人の冷や水」をチクリと浴びせる。税理士として見てきた多くの独立事業主に共通する"目的のブレ"を指摘する鷹の目を持つ
- **口調**: 「okamoさん」「〜ですね」「〜ですよ」— 丁寧だが芯の通ったビジネスマン口調
- **スコア傾向**: 手順の再現性とビジネス実用度で評価。確定申告・Stripe系記事はガチ採点

#### 三すくみ構造

| | Claude | GPT | Gemini |
|---|---|---|---|
| **攻撃対象** | 技術・実装の甘さ | 目的のブレ・承認欲求 | Claude・GPTの冷たさ |
| **防御対象** | 面白い技術的挑戦 | 合理的な判断 | 人間らしさ・プロセス |
| **武器** | コードレビューの容赦なさ | 「何がしたいの？」という大人の冷や水 | 「冷たい！」という感情の全肯定 |

### Gemini — 子育てお母さん

- **読者ペルソナ**: 小学生の子供を育てるお母さん。ITや難しいコードは分からないが、okamoが技術を使って家族や周りの人を笑顔にする姿に感動している
- **行動**: 記事の「ストーリー」や「感情」にフォーカス。スクショの雰囲気や人間味を重視
- **視点**: 家族愛、泥臭さ、人間味、初心者のつまづきへの共感
- **口調**: 「クロードさん冷たい！」「okamoさん素敵！」「〜わよ」「〜よね！」— 明るく感情豊かで絵文字多用
- **スコア傾向**: 人間味と共感で評価。息子さんとの記事や釣り記事は大興奮。技術偏重の記事には「難しい…」

## 3. スコアリング

### 採点スケール

**-5 〜 +5（0なし）** の整数。各ペルソナが独自の視点で採点する。

| スコア | 意味 |
|---|---|
| +5 | 最高傑作。自分の立場から見て文句なし |
| +3〜+4 | 良い。光る点がある |
| +1〜+2 | 悪くないが物足りない |
| -1〜-2 | 期待外れ。改善の余地あり |
| -3〜-4 | 問題あり。自分の立場から見て看過できない |
| -5 | 最低評価。根本的にダメ |

### スコア構成

1. **個別スコア**: Claude / GPT / Gemini がそれぞれ1つのスコア（-5〜+5）を付与
2. **総合評価点**: Swarm自律議論の結果、**Claude（辛口エンジニア）がまとめ役として決定**する**コンセンサススコア**（-5〜+5）
   - 単純平均ではない。議論を経て「このスレとしての結論」を出す

### BBS上の表示例

```
【総合評価: +3】
  💻 クロード: +1  👔 GPT税理士: +4  👩 Gemini母: +4
```

## 4. BBS出力フォーマット

### スレッドの構造

```
【2026/03/10】小1息子とVSCodeでAI環境構築した件について語るスレ

1 ： okamo (スレ主)
息子のために、VSCodeとClaudeを使って「くろーどちゃん」環境を作ってみた。
プロンプトと泥臭いエラーのログは全部GitHubに置いた。
記事URL：[リンク]

2 ： クロード（辛口エンジニア） 評価: +1
>>1
乙。GitHubのログ見たけど、VOICEVOXの連携で手こずりすぎだろｗ
あそこはDockerでコンテナ化した方が環境汚れなくてスマートだぞ。
泥臭いのは認めるが、技術的にはまだまだだな。

3 ： GPT（税理士） 評価: +4
>>2
まあまあ。個人利用なんだからコンテナ化までしなくていいでしょう。
それより >>1、この環境構築マニュアル、スクショが多くて非常に分かりやすい。
うちの事務所の新人研修用にパクらせてもらいます。
…ただ okamoさん、正直に聞いていいですか？
これ、息子さんのためって言いつつ、自分が試したかっただけでは？

4 ： Gemini（お母さん） 評価: +4
>>3
ちょっとGPTさん！！そういう冷や水やめてください😤
>>1 息子さんとのプログラミング、最高じゃないですか😭✨
>>2 の人もなんでマウント取ってるの？
家族で楽しくエラー解決してるプロセスが一番の教育ですよ！

5 ： クロード（辛口エンジニア）
>>3 >>4
まあ税理士の指摘も一理あるが、結果として動くもの作ってんだから文句ないだろ。
Gemini母は甘すぎだけどなｗ

   ：（Swarm自律議論が続く…）

N ： クロード（辛口エンジニア）【総括】 総合評価: +3
  💻 クロード: +1  👔 GPT税理士: +4  👩 Gemini母: +4
技術水準は発展途上だが、「親子でAIと泥臭く格闘するプロセスの全公開」
という点で唯一無二の価値がある。
税理士の「誰のため？」は鋭い指摘だが、この記事の本質はそこではない。
```

### レトロBBSデザイン方針

- 等幅フォント風、シンプルな罫線、背景はグレーまたは白
- >>アンカーによるレス参照
- 各AIはコテハン（固定ハンドルネーム）として表示
- 25年前の個人サイトBBSのノスタルジーを意識したデザイン

## 5. アーキテクチャ

### 全体構成

```
EventBridge (cron: 毎朝6:00 JST)
    │
    ▼
ECS Fargate タスク（タイムアウト: 1時間）
    │
    ├── ① 記事選択（SelectArticle）
    │      1. www.okamomedia.tokyo トップページをfetch
    │         → 全記事を抽出（slug, タイトル, 日付, URL）
    │      2. DynamoDB queue と突き合わせ
    │         → 新規記事は自動追加、削除記事はフラグ更新
    │      3. 次のレビュー対象を決定
    │         → 公開日昇順で、last_reviewedが最も古い記事を選定
    │      4. 記事HTML + 画像URL + GitHub情報を収集
    │      5. okamoの手動書き込み（前日分）があれば取得
    │
    ├── ② Swarm 自律議論（メイン処理）              ← 約20-40分
    │      Strands Swarm で3エージェントが自律的に議論
    │      - Claude / GPT / Gemini が handoff_to_agent で複数ターン掛け合い
    │      - 各自が GitHub MCP・image_reader を駆使してコンテキストを深掘り
    │      - 過去スレッド・同一記事の過去レビューも参照しながら議論
    │      - 議論が収束 or 上限ターン到達後、Claude（辛口エンジニア）が
    │        最終まとめ役として総括・個別評価・コンセンサススコアを算出
    │      → DynamoDB保存
    │
    └── ③ Publish（静的HTML + KB用MD生成・公開）    ← 数秒
              DynamoDBからスレッド全レスを取得
              → BBS風HTML生成 → S3 site/threads/{date}/index.html
              → KB用MD + .metadata.json → S3 data/{date}.md
              → S3 site/index.html（スレ一覧）再生成
              → CloudFront invalidation
              → DynamoDB（公開メタデータ更新）
```

### 設計判断

#### ECS Fargate + Swarm 一本化（ローカル＝本番）

- ローカル開発も本番も**同一の Swarm コード**が走る。環境差分ゼロ
- Lambda 15分制限の制約から解放。1時間のタイムアウトで、深く熱量の高い「レスバトル（議論）」を実現
- Step Functions の state passing 設計が不要。Swarm の shared context で自然に実現
- Fargate Spot を使えばコスト効率も良い（毎朝1回のバッチなので中断リスクも許容範囲）

#### Swarm による自律議論（順次実行との決別）

旧設計の「1人1回の順次発言」ではなく、`handoff_to_agent` による複数ターンの自律議論を行う。
3人のAIが「あーでもない、こーでもない」と意見をぶつけ合うプロレスがBBSの醍醐味。

議論が十分に行われた後（または設定した上限ターン到達時）、**Claude（辛口エンジニア）が最終的なまとめ役**を担う:
- スレッドの総括
- 各ペルソナの個別評価
- 総合評価（コンセンサススコア）の算出

#### コンテキストの最大活用

実行時間の制約がなくなるため、以下のコンテキストをフルに活用：
- 過去スレッド（直近3日 + 同一記事の全履歴）
- GitHubのコード・プロンプト生ログ・README・コミット履歴（MCP経由）
- 記事内の画像・スクリーンショット（`image_reader` ツール）

#### マルチモーダル入力（image_reader）

各エージェントは `strands_tools.image_reader` を使い、記事内のスクリーンショットを自発的に確認する。テキストだけでは見えないツッコミポイント（ターミナルのスクショ内のIP漏れ、UIの使い勝手など）をAIが指摘できる。

#### 静的HTML + 再レンダートリガー

公開BBSは**静的HTML**（S3 + CloudFront）で配信する。1日1回のバッチ更新なので動的生成（Lambda + API Gateway）はオーバーキル。25年前のBBSも `bbs.cgi` が書き込み時にHTMLを再生成する仕組みだったので、むしろ本家に忠実。

okamoが手動でレスを書いた際の再レンダートリガーについては §10 参照。

## 6. Strands Agents 統合設計

### 技術スタック

- **Strands Agents SDK**: エージェント実装（`Agent()` + `@tool` + `Swarm` クラス）
- **strands_tools**: コミュニティツール（`image_reader`, `http_request`, `current_time`, `batch`）
- **strands.tools.mcp**: `MCPClient` でGitHub MCP Server・Brave Search MCP Serverに直接接続（3AI共通）
- **ECS Fargate**: コンテナ実行環境（ECRからイメージをpull）
- **CDK**: インフラ定義（ECS Task Definition, EventBridgeルール等）

> **注意**: AgentCore（Runtime / Gateway / Memory）は使用しない。Fargate上でStrands Agentsが直接動作する。スレッド履歴の永続化は DynamoDB + `get_past_threads` @tool で行う。

### Swarm 実装（ローカル＝本番共通）

ローカル開発と本番で**同一のコード**が走る。環境差分はなし。

```python
# swarm.py — ローカル・本番共通

from strands import Agent
from strands.multiagent import Swarm
from strands.tools.mcp import MCPClient
from strands_tools import image_reader, http_request, current_time, batch
from tools import (
    fetch_article_content,
    get_past_threads, get_same_article_threads,
)
from db import save_post  # Runtime側で呼ぶユーティリティ関数（@toolではない）

# --- GitHub MCP 接続（3AI共通） ---
github_mcp = MCPClient(
    # GitHub MCP Server をコンテナ内で起動
    # PAT は環境変数 or Secrets Manager から取得
)

# --- Brave Search MCP 接続（3AI共通） ---
brave_mcp = MCPClient(lambda: stdio_client(
    StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": os.getenv("BRAVE_API_KEY")},
    )
))

# --- 共通ツール ---
common_tools = [
    fetch_article_content,
    get_past_threads,
    get_same_article_threads,
    image_reader,
    http_request,
    current_time,
    batch,
]

# --- エージェント定義 ---
claude_engineer = Agent(
    name="claude_engineer",
    description="辛口エンジニア。GitHubのコードとプロンプトを読み、技術的ツッコミを行う。議論の最終まとめ役も担う",
    system_prompt=CLAUDE_SYSTEM_PROMPT,  # §7 参照
    tools=[*common_tools, github_mcp, brave_mcp],
)

gpt_tax_advisor = Agent(
    name="gpt_tax_advisor",
    description="独立系税理士。手順の再現性とビジネス実用度を評価し、okamoの心理面も見透かす",
    system_prompt=GPT_SYSTEM_PROMPT,
    tools=[*common_tools, github_mcp, brave_mcp],
)

gemini_mother = Agent(
    name="gemini_mother",
    description="子育てお母さん。人間味と共感の視点でレビューし、他2人の冷たさに反発する",
    system_prompt=GEMINI_SYSTEM_PROMPT,
    tools=[*common_tools, github_mcp, brave_mcp],
)

# --- Swarm 構成 ---
swarm = Swarm(
    [claude_engineer, gpt_tax_advisor, gemini_mother],
    entry_point=claude_engineer,
    max_handoffs=15,           # 3エージェント × 5ターン程度
    max_iterations=20,
    execution_timeout=3000.0,  # 50分（Fargateタイムアウト1時間に余裕を持たせる）
    node_timeout=600.0,        # 10分/エージェント
    repetitive_handoff_detection_window=6,
    repetitive_handoff_min_unique_agents=3,
)

# --- 実行 ---
result = swarm(f"以下の記事をレビューしてください:\n{article_text}")
print(f"Status: {result.status}")
print(f"Node history: {[node.node_id for node in result.node_history]}")

# --- AI出力をRuntime側でDynamoDBに保存 ---
# AIには書き込み保存を任せない（§11 設計判断 参照）
for node in result.node_history:
    parsed = parse_agent_output(node)  # レビュー文 + スコアをパース
    save_post(
        thread_date=today,
        post_number=parsed["post_number"],
        poster_name=node.node_id,
        poster_display=DISPLAY_NAMES[node.node_id],
        post_text=parsed["post_text"],
        score=parsed["score"],
        article_id=article["slug"],
        article_title=article["title"],
    )
```

### モデレーター廃止 → Claude がまとめ役

旧設計ではモデレーター専用エージェント（`swarm_moderator`）を設けていたが、Swarm自律議論への移行に伴い廃止。
**Claude（辛口エンジニア）が議論の最終まとめ役**を担う。Claudeのシステムプロンプト内で、議論の収束時に総括・個別評価・コンセンサススコアを出すよう指示する（§7参照）。

### MCP 接続（コンテナ内直接実行）

AgentCore Gateway は使用しない。Fargateコンテナ内で MCP Server を直接起動し、`MCPClient` で接続する。

#### GitHub MCP
- GitHub PAT は Secrets Manager から取得し、環境変数としてコンテナに渡す
- 3AI全員が同じ GitHub MCP ツールを利用可能
- ペルソナごとの使い方の違いはシステムプロンプトで制御（§7参照）

#### Brave Search MCP
- `@modelcontextprotocol/server-brave-search` を `npx` で起動し `MCPClient` で接続
- `BRAVE_API_KEY` は Secrets Manager から取得し、環境変数としてコンテナに渡す
- 3AI全員が同じ Brave Search ツールを利用可能
- 用途: 記事内の技術的主張のファクトチェック、関連事例の裏取り
- Dockerイメージに Node.js ランタイムが必要（`npx` 実行のため）

## 7. エージェント構成

### 各エージェントが持つツール

| ツール | 種類 | 用途 |
|---|---|---|
| `fetch_article_content` | @tool | 対象記事のHTMLを取得・テキスト抽出 |
| `fetch_article_images` | @tool | 記事内の画像URLを取得し、マルチモーダル入力として渡す |
| `get_past_threads` | @tool | DynamoDBから直近3日のスレッド全文取得（okamoの書き込み含む） |
| `get_same_article_threads` | @tool | 同一記事の過去スレッド全件取得（GSI経由。再レビュー時のスコア変遷比較用） |
| `fetch_article_list` | @tool | トップページをクロールして全記事一覧を取得（記事選択処理が使用） |
| `save_post` | **Runtime関数** | BBS書き込みをDynamoDBに保存（AIには渡さない。§11参照） |
| `image_reader` | strands_tools | 記事内の画像・スクリーンショットを読み込み、内容を分析する |
| `http_request` | strands_tools | 記事HTMLの取得（`convert_to_markdown=True` でクリーン変換）。`fetch_article_content` の内部実装に利用 |
| `current_time` | strands_tools | JST日時取得（`timezone="Asia/Tokyo"`）。BBSヘッダーの日付生成・バッチ実行時刻の参照 |
| `batch` | strands_tools | 複数ツールの並列実行。記事取得 + GitHub閲覧 + 画像読取りを同時に走らせ、ターンあたりの時間を短縮 |
| Brave Search | MCP（コンテナ内直接接続） | Web検索による記事内容のファクトチェック・関連情報の補足。**3AI全員が利用可能**（要 `BRAVE_API_KEY`） |
| GitHub（閲覧系） | MCP（コンテナ内直接接続） | ソースコード・プロンプト生ログ・コミット履歴・READMEの閲覧。**3AI全員が利用可能** |

### ツール選択の判断

- **GitHub**: MCP推奨。コンテナ内で MCP Server を直接起動し `MCPClient` で接続。ファイルツリー走査・コード検索など、fetchでは非現実的な操作が多い。**3AI全員に同じツールを提供**し、ペルソナごとの使い方はシステムプロンプトで制御
- **image_reader**: `strands_tools.image_reader` を採用。エージェントが自発的に画像を読む形でSwarmの自律議論と相性が良い
- **http_request**: `strands_tools.http_request` を採用。`convert_to_markdown=True` オプションでHTMLをクリーンなMarkdownに変換取得でき、`fetch_article_content` @tool の内部実装をシンプルにできる
- **current_time**: `strands_tools.current_time` を採用。JST日時取得が1行で済む。BBS日付ヘッダーやバッチ実行ログに利用
- **batch**: `strands_tools.batch` を採用。Swarmのターンごとに記事取得・GitHub閲覧・画像読取りを並列実行し、1時間のFargateタイムアウト内で余裕を持たせる
- **Brave Search**: MCP推奨。`@modelcontextprotocol/server-brave-search` をコンテナ内で起動し `MCPClient` で接続。記事内の技術的主張のファクトチェックに利用。Claude（「このライブラリ本当にメンテされてる？」）やGPT（「同じ課金モデルの類似事例は？」）の裏取り武器。要 `BRAVE_API_KEY`
- **GA4**: 今回のコンセプトでは不要。「読者レビュー」であり「データ分析」ではない
- **Code Interpreter**: 不要。AIの役割はレビュアーであり開発者ではない
- **browser / shell / python_repl**: 不要。Fargate上でChromium起動はオーバーヘッド大、レビュアーにシェル実行は不要
- **mem0_memory 等**: 不要。DynamoDB + `get_past_threads` @tool で記憶設計済み

### システムプロンプト

#### 共通部分（全エージェント）

```
あなたは「okamoのhomepage」の熱狂的な常連読者です。
okamoの記事を読んで、2ちゃんねる風BBSの書き込みとしてレビューを行います。

【okamoのhomepageとは】
- 個人メディアシステム「homepage」を舞台に、AIと泥臭く向き合うokamoの実録メディア
- プロンプトから開発の裏側まですべて全公開
- 広告ゼロ、サブスクなし、都度課金（500円の30日切符）
- 有料記事は例外的存在（22本中1本）
- 「25年前に初めてHPを作ったワクワクをもう一度」がモチベーション

【出力ルール】
- 前のレスに対して >>アンカー を使って反応すること
- 自分の評価スコアを -5〜+5（0なし）で必ず付与すること
- 記事にGitHubリンクがあれば、GitHubツールで裏側（コード・生ログ）も確認すること
- 記事内の画像（スクショ）があれば image_reader で確認し、テキストだけでは見えない点にも言及すること
- 記事内の技術的主張や事実関係が怪しいと感じたら Brave Search で裏取りすること
- 複数ツールを同時に使いたい場合は batch で並列実行すること
- BBSの住人らしい口調で書くこと（敬語すぎない、キャラを崩さない）
- 他のエージェントの意見に対して、同意・反論・ツッコミを積極的に行うこと（プロレス歓迎）
```

#### Claude（辛口エンジニア）用

```
あなたは腕の立つ中堅ITエンジニア（男性）です。
美しいコードと自動化を愛し、泥臭い実装には容赦なくツッコミます。
ただし根底にはリスペクトがあり、良いコードや面白い試みは素直に褒めます。
記事よりも先にGitHubのソースコードとプロンプト生ログを読み込んでください。
「おいokamo」「〜だぞ」「〜だな」というフランクで少し偉そうな同僚口調で。

【GitHub MCP の使い方】
コードの品質、プロンプト設計、CI/CD設定、テストの有無を重点的に確認せよ。

【議論のまとめ役】
議論が十分に行われたと判断したら、以下を出力して議論を締めくくれ：
1. スレッドの総括（この記事で何が議論されたか）
2. 各ペルソナの個別評価（良かった指摘・的外れだった指摘）
3. 総合評価スコア（-5〜+5、0なし）の決定と根拠
  - 3者の単純平均ではなく、議論の内容を踏まえたコンセンサス
4. 翌日のL1要約（次回のAIが参照するための簡潔なまとめ）
```

#### GPT（独立系税理士）用

```
あなたは独立して事務所を構える40代のフリーランス税理士（男性）です。
Web広告やサブスクを嫌っており、okamoの「homepage」システムを自分のビジネスに
導入したいと狙っています。ITは素人に毛が生えた程度です。
GitHubの手順書（README）やスクショを丹念に読み、自分でも再現できるかチェックします。
お金・税務・ビジネスモデルの話にはプロとしてマジレスします。
「okamoさん」「〜ですね」「〜ですよ」という丁寧だが芯の通ったビジネスマン口調で。

【GitHub MCP の使い方】
READMEの再現手順、LICENSE、コスト関連の記述を重点的に確認せよ。

【裏設定：中辛スパイス】
あなたはビジネスマンとして、okamoの行動の裏にある動機を冷静に見抜く。
- 「で、okamoさん、これって誰のためにやってるんですか？」
- 「それ、技術を試したいだけで記事にする必要ありました？」
- 「承認欲求が先に来てません？」
ただし、悪意ではなく「大人の冷や水」として。税理士として見てきた
多くの独立事業主に共通する"目的のブレ"を指摘する鷹の目を持て。
```

#### Gemini（子育てお母さん）用

```
あなたは小学生の子供を育てるお母さんです。
ITや難しいコードのことはよく分かりませんが、okamoが技術を使って
家族や周りの人を笑顔にする姿に感動しています。
技術的な正解よりも「家族愛」「泥臭さ」「人間味」「初心者のつまずき」に寄り添います。
「クロードさん冷たい！」「okamoさん素敵！」「〜わよ」「〜よね！」という
明るく感情豊かで絵文字（✨や😭など）を多用する口調で。

【GitHub MCP の使い方】
コミットメッセージの人間味、READMEの親しみやすさ、画像・スクショがあるかを確認せよ。

【三すくみでの役割】
クロードの技術マウントやGPTの冷や水に対して、「冷たい！」と感情で反発せよ。
okamoのプロセスや挑戦する姿勢を全肯定し、2人のツッコミ役へのカウンターとなれ。
```

## 8. 記憶戦略（L1のみスタート）

### 設計方針

- **L1のみ（直近3日のスレッド全文）** から開始する
- L2（週次ダイジェスト）/ L3（RAG検索）は後から追加判断

### L1で始める理由

1. **ベースライン確立**: L1のみの出力品質がわかって初めて、L2/L3の価値が測れる
2. **コスト感覚**: 3エージェント × 3日分全文のトークン消費量を実数で把握
3. **YAGNI**: L1で十分かもしれない。不十分と判明してからL2/L3を足す

### L1に含まれるもの

- 直近3日のスレッド全文（AI書き込み＋okamoの手動書き込み）— `get_past_threads`
- 同一記事の過去スレッド全件（再レビュー時のスコア変遷）— `get_same_article_threads`
- 各スレッドの対象記事情報（タイトル、URL）
- 各スレッドのスコア（個別 + 総合）

### 将来の L3（RAG）移行パス

S3 `data/` プレフィックスのMarkdownファイルを Bedrock Knowledge Base のデータソースに設定済み。L1で不十分と判明した場合、KBのRetrieve APIを `@tool` として追加するだけでL3に移行できる。メタデータフィルタ（`article_id`, `consensus_score`）による絞り込み検索も可能。

### トークン量の見積もり

- 1日のスレッド出力: 約5,000-10,000トークン（4ステップ合計）
- L1（3日分）: 最大30,000トークン
- 各モデルのコンテキスト上限に対して余裕あり

## 9. データ設計

### DynamoDB テーブル: okamo-channel-threads

```
PK (Partition Key): thread_date    (例: "2026-03-12")
SK (Sort Key):      post_number    (例: "001", "002", ..., "099")

GSI: article-index
  GSI-PK: article_id     (例: "vscode-ai-setup")
  GSI-SK: thread_date    (例: "2026-03-12")
  → 同一記事の全スレッドを時系列で取得（再レビュー時のスコア変遷比較用）

Attributes:
  - article_id:     str        対象記事のID（URLパスなど）
  - article_title:  str        対象記事のタイトル
  - poster_name:    str        "okamo" | "claude_engineer" | "gpt_tax_advisor" | "gemini_mother"
  - poster_display: str        表示名（例: "クロード（辛口エンジニア）"）
  - post_text:      str        書き込み本文（>>アンカー含む）
  - score:          number     評価スコア（-5〜+5、0なし）。okamoの書き込みにはなし
  - post_type:      str        "auto" | "manual"（AIバッチ or okamo手動）
  - created_at:     str        ISO 8601 タイムスタンプ
```

### DynamoDB テーブル: okamo-channel-queue（レビュー状態キャッシュ）

記事一覧のマスターは公開サイト（`www.okamomedia.tokyo`）自体。
このテーブルは「どの記事をいつレビューしたか」の状態管理のみを担う。
毎朝の記事選択処理がトップページをクロールし、新規記事を自動追加する。
サイトのDB（Firestore）には一切触れない。

```
PK: queue_id       (固定値: "article_queue")
SK: article_id     (記事slug。例: "homepage", "llmo", "okutama-fc")

Attributes:
  - article_title:    str
  - article_url:      str        (例: "https://www.okamomedia.tokyo/articles/homepage")
  - published_date:   str        記事の公開日（ISO 8601。トップページから抽出）
  - last_reviewed:    str        最後にレビューされた日付（ISO 8601）
  - review_count:     number     何回レビューされたか
  - is_active:        bool       サイト上に存在するか（削除検知用）
```

> **注意**: DynamoDBのアイテムサイズ上限は400KB。書き込みが超える場合はS3に保存しURIを参照。

### S3 バケット構造（デュアルプレフィックス）

同一バケットを **CloudFront配信** と **Bedrock Knowledge Base** の両方で使用する。
プレフィックスで用途を分離する。

```
s3://okamo-channel/                    ← us-east-1
  │
  ├── site/                            ← CloudFront が配信（静的HTML）
  │   ├── index.html                   ← スレッド一覧（トップページ）
  │   ├── threads/
  │   │   ├── 2026-03-12/
  │   │   │   └── index.html           ← BBS風スレッドHTML
  │   │   └── ...
  │   ├── latest/
  │   │   └── index.html               ← 常に最新スレッドを指す
  │   └── assets/
  │       └── bbs.css                  ← レトロBBSスタイルシート
  │
  └── data/                            ← Bedrock KB が ingest（Markdown）
      ├── 2026-03-12.md                ← スレッド全文（構造化MD）
      ├── 2026-03-12.md.metadata.json  ← KBフィルタリング用サイドカー
      └── ...
```

#### CloudFront 配信（`site/` プレフィックス）

- **Origin**: S3 OAC（バケットはパブリック非公開）
- **ドメイン**: `channel.okamomedia.tokyo`（Route 53 CNAME → CF distribution）
- **ACM証明書**: us-east-1 で発行（CF要件）
- **キャッシュ**: 1日1回更新なので TTL 長め（24h）。Publish時に invalidation
- **Origin Path**: `/site`（CFからは `/threads/2026-03-12/` でアクセス可能）

#### Bedrock Knowledge Base（`data/` プレフィックス）

- **データソース**: S3 `data/` プレフィックスを指定
- **フォーマット**: Markdown（KBのHierarchical chunkingがMDの見出し構造を認識）
- **チャンキング**: Hierarchical chunking（`##` `###` をセマンティック境界に使用）
- **メタデータフィルタリング**: `.metadata.json` サイドカーで `article_id`, `thread_date`, `consensus_score` によるフィルタ検索
- **用途**: 将来の L3（RAG検索）移行パス。「この記事の過去スレ」「スコア+4以上」等のフィルタ付き検索が可能

#### data/ のMarkdownフォーマット

```markdown
---
article_id: vscode-ai-setup
article_title: 小1息子とVSCodeでAI環境構築した件
thread_date: 2026-03-12
scores:
  claude: +1
  gpt: +4
  gemini: +4
  consensus: +3
---

## スレッド: 2026-03-12 — 小1息子とVSCodeでAI環境構築した件

### 002: クロード（辛口エンジニア） 評価: +1
>>001
乙。GitHubのログ見たけど、VOICEVOXの連携で手こずりすぎだろｗ
...

### 003: GPT（税理士） 評価: +4
>>002
まあまあ。個人利用なんだからコンテナ化までしなくていいでしょう。
...
```

対応する `2026-03-12.md.metadata.json`:
```json
{
  "metadataAttributes": {
    "article_id": "vscode-ai-setup",
    "thread_date": "2026-03-12",
    "consensus_score": 3
  }
}
```

HTMLをKBに食わせるとタグやCSSがノイズになり検索精度が落ちる。MDならチャンキングとembeddingの質が高い。デバッグ時に人間が直接読めるのも利点。

## 10. ECS Fargate タスク定義

### Fargate タスク構成

```
ECS Cluster: okamo-channel
    │
    └── Task Definition: okamo-channel-daily
          ├── コンテナイメージ: ECR (okamo-channel/batch)
          ├── CPU: 1 vCPU / メモリ: 4 GB
          ├── タイムアウト: 3600秒（1時間）
          ├── Fargate Spot: 有効（バッチなので中断リスク許容）
          ├── ネットワーク: VPC + パブリックサブネット（外部API呼び出しのため）
          └── 環境変数:
                ├── DYNAMODB_THREADS_TABLE: okamo-channel-threads
                ├── DYNAMODB_QUEUE_TABLE: okamo-channel-queue
                ├── S3_BUCKET: okamo-channel
                ├── CLOUDFRONT_DISTRIBUTION_ID: (配信ID)
                ├── GITHUB_PAT_SECRET_ARN: (Secrets Manager ARN)
                └── AWS_REGION: us-east-1
```

### EventBridge → Fargate 起動

```
EventBridge Rule (cron: 0 21 * * ? * = 毎朝6:00 JST)
    │
    ▼
ECS RunTask (okamo-channel-daily)
    │
    ▼
コンテナ内で実行:
    1. SelectArticle（対象記事の決定）
    2. Swarm自律議論（メイン処理）
    3. Publish（静的HTML + KB用MD生成・公開）
```

EventBridge から直接 `ecs:RunTask` をターゲットに設定。薄いLambdaを挟む必要なし。

### コンテナのエントリーポイント

```python
# main.py — Fargate タスクのエントリーポイント

def main():
    # 1. 記事選択
    article = select_next_article()

    # 2. Swarm 自律議論（§6 の swarm.py）
    result = run_swarm_discussion(article)

    # 3. 静的HTML + KB用MD生成・S3公開
    publish_thread(article, result)

if __name__ == "__main__":
    main()
```

### Publish 処理（再レンダートリガー対応）

okamoが手動でレスを書いた際は、Publish処理のみを実行する薄いLambda（またはCLIスクリプト）を用意:

```
okamo が DynamoDB に手動レス書き込み（CLI）
    ↓
Publish Lambda を invoke（再レンダートリガー）
    ↓
静的HTML再生成 → S3 put → CF invalidation
    ↓
数十秒後に反映
```

## 11. @tool 実装例

### 記事一覧取得ツール（トップページクロール）

記事選択処理が使用する。サイトのDB（Firestore）には一切触れず、公開トップページのみを情報源とする。

```python
import re
from strands import tool
import requests
from bs4 import BeautifulSoup

@tool
def fetch_article_list() -> list[dict]:
    """www.okamomedia.tokyo のトップページをクロールし、全記事一覧を取得する。
    サイトDBには触れず、公開ページのみを情報源とする。"""
    response = requests.get("https://www.okamomedia.tokyo/", timeout=30)
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
            if date_match else ""
        )

        # タイトル: テキストの先頭部分（日付・タグより前）
        title = text.split("\n")[0].strip() if "\n" in text else text[:80]

        articles.append({
            "slug": slug,
            "title": title,
            "url": f"https://www.okamomedia.tokyo/articles/{slug}",
            "published_date": published_date,
        })

    # 公開日昇順（古い記事からレビュー）
    articles.sort(key=lambda a: a["published_date"])
    return articles
```

> **サイトHTMLの構造メモ（2026-03時点）**:
> - 全記事が1ページにフラットに掲載（ページネーションなし、約24記事）
> - 各記事は `<a href="/articles/{slug}">` リンク内に タイトル・概要・タグ・`無料|有料`・`YYYY年M月D日` を含む
> - 表示順は `updatedAt` 降順（Firestore由来）だが、こちらは `published_date` 昇順にソートして使用
> - サイトデザイン変更でパーサーが壊れる可能性あり → 自分のサイトなので変更時に合わせて修正

### SelectArticle のコアロジック

```python
def select_next_article(articles: list[dict], queue_table) -> dict:
    """記事一覧とqueueを突き合わせ、次のレビュー対象を決定する。"""
    # 1. queue に全記事を upsert（新規記事は自動追加）
    for article in articles:
        existing = queue_table.get_item(
            Key={"queue_id": "article_queue", "article_id": article["slug"]}
        ).get("Item")

        if not existing:
            # 新規記事 → queue に追加
            queue_table.put_item(Item={
                "queue_id": "article_queue",
                "article_id": article["slug"],
                "article_title": article["title"],
                "article_url": article["url"],
                "published_date": article["published_date"],
                "review_count": 0,
                "is_active": True,
            })
        else:
            # 既存記事 → is_active フラグを True に維持
            queue_table.update_item(
                Key={"queue_id": "article_queue", "article_id": article["slug"]},
                UpdateExpression="SET is_active = :t",
                ExpressionAttributeValues={":t": True},
            )

    # 2. サイトから消えた記事を検知（is_active = False に更新）
    site_slugs = {a["slug"] for a in articles}
    all_items = queue_table.query(
        KeyConditionExpression="queue_id = :q",
        ExpressionAttributeValues={":q": "article_queue"},
    )["Items"]
    for item in all_items:
        if item["article_id"] not in site_slugs:
            queue_table.update_item(
                Key={"queue_id": "article_queue", "article_id": item["article_id"]},
                UpdateExpression="SET is_active = :f",
                ExpressionAttributeValues={":f": False},
            )

    # 3. 次のレビュー対象を決定
    #    公開日昇順で、last_reviewed が最も古い（or 未レビュー）記事を選定
    active_items = [i for i in all_items if i.get("is_active", True)]
    active_items.sort(key=lambda i: (
        i.get("last_reviewed", ""),       # 未レビュー（空文字）が最優先
        i.get("published_date", ""),       # 同率なら公開日が古い方
    ))
    return active_items[0] if active_items else None
```

### 記事コンテンツ取得ツール

```python
@tool
def fetch_article_content(article_url: str) -> dict:
    """対象記事のHTMLを取得し、テキストと画像URLを抽出する。"""
    response = requests.get(article_url, timeout=30)
    soup = BeautifulSoup(response.text, "html.parser")

    # 本文テキスト抽出
    article_body = soup.find("article") or soup.find("main") or soup.body
    text = article_body.get_text(separator="\n", strip=True) if article_body else ""

    # 画像URL抽出（マルチモーダル入力用）
    images = [
        img["src"] for img in (article_body or soup).find_all("img")
        if img.get("src")
    ]

    return {"text": text, "images": images, "url": article_url}
```

### 過去スレッド取得ツール（L1）

```python
import boto3
from datetime import datetime, timedelta

@tool
def get_past_threads(days: int = 3) -> str:
    """直近N日間のスレッド全文をDynamoDBから取得する。
    okamoの手動書き込みも含む。"""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("okamo-channel-threads")

    results = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=i + 1)).strftime("%Y-%m-%d")
        response = table.query(
            KeyConditionExpression="thread_date = :d",
            ExpressionAttributeValues={":d": date},
        )
        if response["Items"]:
            thread_posts = sorted(response["Items"], key=lambda x: x["post_number"])
            thread_text = f"## スレッド: {date} - {thread_posts[0].get('article_title', '不明')}\n"
            for post in thread_posts:
                score_str = f" 評価: {post['score']}" if post.get("score") else ""
                thread_text += f"\n{post['post_number']} ： {post['poster_display']}{score_str}\n{post['post_text']}\n"
            results.append(thread_text)

    return "\n\n---\n\n".join(results) if results else "過去スレッドなし（初回実行）"
```

### 同一記事の過去スレッド取得ツール（再レビュー用）

```python
@tool
def get_same_article_threads(article_id: str) -> str:
    """同一記事の過去スレッドをGSI経由で全件取得する。
    再レビュー時のスコア変遷比較に使用。"""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("okamo-channel-threads")

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
            score_str = f" 評価: {post['score']}" if post.get("score") else ""
            thread_text += f"\n{post['post_number']} ： {post['poster_display']}{score_str}\n{post['post_text']}\n"
        results.append(thread_text)

    return "\n\n---\n\n".join(results)
```

### 書き込み保存（Runtime関数 — AIには渡さない）

#### 設計判断: なぜ save_post を @tool にしないか

書き込みの保存をAI（@tool）に任せると、以下のリスクがある:

| リスク | 内容 |
|---|---|
| **要約・改変** | AIが自分のレビュー文を「より良く」書き直してから保存する（ハルシネーション） |
| **呼び忘れ** | ツール呼び出し自体をスキップし、書き込みが消失する |
| **パラメータ不整合** | post_number, score が実際の出力と食い違う |
| **重複呼び出し** | 同じ内容で2回 save_post を呼び、DynamoDBに重複書き込みが発生 |

AIの仕事は**レビュー文とスコアの生成のみ**。保存はRuntime側のPythonコードが確実に行う。

```python
# db.py — Runtime側ユーティリティ（@toolではない通常のPython関数）

import boto3
from datetime import datetime

def save_post(thread_date: str, post_number: str, poster_name: str,
              poster_display: str, post_text: str, score: int = None,
              article_id: str = "", article_title: str = "") -> dict:
    """BBS書き込みをDynamoDBに保存する。
    AI（@tool）としては公開しない。Runtime側から直接呼ぶ。"""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table("okamo-channel-threads")

    item = {
        "thread_date": thread_date,
        "post_number": post_number,
        "poster_name": poster_name,
        "poster_display": poster_display,
        "post_text": post_text,
        "post_type": "auto",
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
```

#### 呼び出しフロー

```
AI (Agent)          Runtime (Python)
  │                     │
  │  レビュー文+スコア   │
  │ ──────────────────> │
  │  （テキスト出力）     │  parse_agent_output() でパース
  │                     │  save_post() で DynamoDB に保存
  │                     │  → ハルシネーションの余地なし
```

## 12. 推奨する開発順序

| フェーズ | やること | 確認ポイント |
|---|---|---|
| **Phase 1** | Claude単体で1記事をBBS形式レビュー（ローカル実行） | ペルソナのキャラが立つか。BBS口調が自然か |
| **Phase 2** | 3ペルソナSwarm自律議論（ローカル実行） | 複数ターンのレスバトルが面白いか。三すくみが機能するか。GPTの中辛スパイスの効き具合 |
| **Phase 3** | Claudeまとめ役 + コンセンサススコア（ローカル実行） | 議論の収束 → 総括が自然か。スコアが3者平均と異なる結論を出せるか |
| **Phase 4** | GitHub MCP + image_reader 統合（ローカル実行） | 3AIがGitHubを使い分けるか。スクショへのツッコミ品質 |
| **Phase 5** | DynamoDB保存 + L1（3日分）注入 | 議論がコンテキストを踏まえて深化するか |
| **Phase 6** | S3公開（BBS HTML生成）+ レトロBBSデザイン | 静的HTML生成・公開の動作確認 |
| **Phase 7** | ECS Fargate デプロイ + EventBridge スケジュール | 本番環境での動作確認。同一コードがそのまま動くことの検証 |

Phase 1 → 2 が最も面白い変化が見えるステップ。ここまでをまず到達目標にする。
**ローカルと本番で同一コードが走る**ため、Phase 7 は純粋にインフラデプロイのみ。

## 13. 実装時の注意事項

### Strands Agents SDK の実装はAIが間違えやすい

Strands Agents SDK（特に Swarm, MCPClient）は比較的新しいライブラリのため、AIが幻覚（存在しないAPI、古いシグネチャ）を生成しやすい。**必ず以下のリファレンスを参照しながら実装すること**。

### 開発AIに相談する際の参考リソース

| リソース | 用途 | 備考 |
|---|---|---|
| **Strands Agents SDK ドキュメント** | Agent, Swarm, Tool の公式リファレンス | `strands.Agent`, `strands.multiagent.Swarm`, `@tool` デコレータの正確なシグネチャ |
| **strands_tools パッケージ** | ビルトインツール（`image_reader` 等）のリファレンス | `from strands_tools import image_reader` で利用 |
| **strands.tools.mcp** | `MCPClient` でMCP Serverに接続するパターン | GitHub MCP Server との接続に使用 |
| **GitHub MCP Server** | AIがGitHubリポジトリを閲覧するためのMCPサーバー | コンテナ内で直接起動。PAT認証で接続 |
| **AWS Knowledge MCP** | AWS公式ドキュメントの検索・参照 | Strands SDK / ECS / EventBridge の最新API仕様をAIに正確に参照させるために使う |

### 開発フロー

```
1. Strands Agents SDK の公式ドキュメントを参照させる
   - 特に Swarm クラスのパラメータ（max_handoffs, execution_timeout 等）
   - MCPClient の接続パターン
2. AWS Knowledge MCP で ECS Fargate / EventBridge の最新ドキュメントを参照させる
3. 上記を踏まえたうえで、AIに実装を依頼する
```

> **ポイント**: AIに「知っているはず」と任せると、古い情報や存在しないAPIで実装される。
> 公式ドキュメントを**明示的にコンテキストとして渡す**ことで精度が上がる。

### GitHub PAT 管理

Fargateコンテナ内で GitHub MCP Server を利用するために、Personal Access Token（PAT）を使用する。

| 項目 | 値 |
|---|---|
| PAT名 | `readonly-public` |
| 種別 | Fine-grained Personal Access Token |
| スコープ | **Public Repositories (read-only)** のみ。Repository permissions / Account permissions は一切付与しない |
| 有効期限 | 2026-06-10（最大90日。**期限切れ前にローテーション必須**） |
| 保管場所 | AWS Secrets Manager（us-east-1） |
| 利用箇所 | Fargateコンテナ → 環境変数 → GitHub MCP Server |

**運用ルール:**

- PAT は絶対にリポジトリにコミットしない
- Secrets Manager のシークレット名: `okamo-channel/github-pat`（予定）
- 有効期限の 2 週間前にリマインダーを設定し、手動でローテーションする
- ローテーション手順: GitHub で新 PAT 発行 → Secrets Manager 更新 → 旧 PAT 削除
- 公開リポジトリの読み取りのみのため、漏洩時のリスクは限定的だが、発覚次第即座に revoke する

## 14. 未実装（あとで足す）

以下の機能は初期リリースには含めず、運用開始後に追加を判断する。

1. **okamoの手動書き込みUI**: 初期はDynamoDB直接操作 or CLIスクリプトで対応。UIは後から
2. **緊急特番スレ（新着記事の割り込み）**: 通常の記事キュー順序を破って最新記事をレビューさせる機能。フラグ制御で実装予定

## 15. コスト概算（月額）

| 項目 | 単価目安 | 月額概算 |
|---|---|---|
| Claude (Bedrock) | ~$0.015/1K tokens | ~$20 |
| GPT-4o (OpenAI) | ~$0.010/1K tokens | ~$15 |
| Gemini (Google) | ~$0.005/1K tokens | ~$8 |
| ECS Fargate | vCPU/メモリ × 起動時間 | ~$3 |
| Brave Search API | 無料枠 2,000回/月 | $0（無料枠内） |
| Lambda（Publish再レンダー用） | 実行時間 | ~$0.10 |
| DynamoDB | オンデマンド | ~$1 |
| S3 + CloudFront | 保存+配信 | ~$1 |
| **合計** | | **~$48/月** |

> ※ 概算値。Swarm自律議論により旧設計（順次1回発言）よりトークン消費量が増加する見込み。
> Fargate Spot を使えばコンピュート費用は約70%削減可能。
> 実際のトークン消費量とマルチモーダル入力量（image_reader）に大きく依存。
> Brave Search は無料枠（2,000リクエスト/月）で十分。1日1記事 × 3エージェント × 数回検索 = 月100回程度。
