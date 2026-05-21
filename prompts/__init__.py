# prompts/__init__.py — 全プロンプトの再エクスポート

from .common import COMMON_PROMPT
from .claude import CLAUDE_SYSTEM_PROMPT
from .gpt import GPT_SYSTEM_PROMPT
from .gemini import GEMINI_SYSTEM_PROMPT
from .summarizer import CLAUDE_SUMMARIZER_PROMPT

__all__ = [
    "COMMON_PROMPT",
    "CLAUDE_SYSTEM_PROMPT",
    "GPT_SYSTEM_PROMPT",
    "GEMINI_SYSTEM_PROMPT",
    "CLAUDE_SUMMARIZER_PROMPT",
]
