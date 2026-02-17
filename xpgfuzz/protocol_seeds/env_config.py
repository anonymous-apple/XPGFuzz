"""
Centralized environment/config access for XPGFuzz (anonymous release friendly).

We intentionally avoid hardcoding any API keys or private base URLs in code.

Environment variables (preferred):
  - XPGFUZZ_LLM_API_KEY        (required for any LLM/embedding call)
  - XPGFUZZ_LLM_BASE_URL       (optional; OpenAI-compatible, usually ends with /v1)
  - XPGFUZZ_LLM_MODEL          (optional; default: DeepSeek-V3.1)
  - XPGFUZZ_EMBEDDING_MODEL    (optional; default: text-embedding-3-small)
  - XPGFUZZ_EMBEDDING_BASE_URL (optional; default: XPGFUZZ_LLM_BASE_URL)

Backward-compatible fallbacks (if you already have them):
  - OPENAI_API_KEY
  - OPENAI_BASE_URL
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # python-dotenv is optional; environment variables may already be set.
    pass


def get_llm_api_key() -> Optional[str]:
    return os.getenv("XPGFUZZ_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")


def require_llm_api_key() -> str:
    key = get_llm_api_key()
    if not key:
        raise ValueError(
            "Missing LLM API key. Set XPGFUZZ_LLM_API_KEY (preferred) or OPENAI_API_KEY."
        )
    return key


def get_llm_base_url() -> Optional[str]:
    return os.getenv("XPGFUZZ_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")


def get_llm_model(default: str = "DeepSeek-V3.1") -> str:
    return os.getenv("XPGFUZZ_LLM_MODEL") or default


def get_embedding_model(default: str = "text-embedding-3-small") -> str:
    return os.getenv("XPGFUZZ_EMBEDDING_MODEL") or default


def get_embedding_base_url() -> Optional[str]:
    return os.getenv("XPGFUZZ_EMBEDDING_BASE_URL") or get_llm_base_url()

