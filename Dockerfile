# okamoちゃんねる — Fargate batch container
# Python 3.12 + Node.js (Brave Search MCP の npx 実行用)

FROM python:3.12-slim AS base

# Node.js 22.x (npx for Brave Search MCP stdio)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存インストール（キャッシュ活用）
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir \
    "strands-agents[bedrock,openai,gemini]" \
    strands-agents-tools \
    python-dotenv \
    requests \
    beautifulsoup4 \
    boto3 \
    jinja2

# アプリケーションコード
COPY main.py prompts.py tools.py db.py parser.py publish.py ./
COPY templates/ ./templates/

# npx の @anthropic-ai/brave-search-mcp を事前キャッシュ
RUN npx -y @anthropic-ai/brave-search-mcp --help 2>/dev/null || true

# Fargate は .env 不要（環境変数＋Secrets Manager）
# ローカルでは .env をマウント or --env-file で渡す

ENTRYPOINT ["python", "main.py"]
