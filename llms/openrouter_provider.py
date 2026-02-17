"""
ARCANE LLM Provider - OpenRouter

Uses the OpenRouter API for access to many free/open source models
(Mistral, LLaMA, Qwen, Gemma, etc.) under a single API key.
"""

import os
import time
import logging
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv

from llms.base_provider import BaseProvider

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger("root.llm.openrouter")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Retry config for free-tier rate limits
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider for free/OSS models."""

    def __init__(self, model: str = "meta-llama/llama-3.3-70b-instruct:free",
                 api_key: str | None = None):
        self.model_name = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")

        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set. LLM calls will fail.")

    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float = 0.7,
                       max_tokens: int = 1024) -> str:
        """Generate a completion via OpenRouter with retry logic."""
        # Build messages list with system prompt
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://arcane-sim.local",
                            "X-Title": "ARCANE Simulation",
                        },
                        json={
                            "model": self.model_name,
                            "messages": api_messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                        timeout=90.0,  # Free tier can be slow
                    )

                    # Handle rate limits
                    if response.status_code == 429:
                        delay = RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(f"OpenRouter rate limited. "
                                      f"Retrying in {delay}s (attempt {attempt + 1})")
                        await asyncio.sleep(delay)
                        continue

                    response.raise_for_status()
                    data = response.json()

                return data["choices"][0]["message"]["content"]

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"OpenRouter error: {e}. "
                                  f"Retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"OpenRouter completion failed after "
                                f"{MAX_RETRIES} attempts: {e}")

        return f"[LLM Error: {last_error}]"

    async def embed(self, text: str) -> list[float]:
        """
        OpenRouter doesn't provide embeddings directly.
        Falls back to a simple hash-based pseudo-embedding.
        """
        logger.warning("OpenRouter does not support embeddings. "
                       "Using placeholder.")
        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()
        return [int(h[i:i+2], 16) / 255.0 for i in range(0, 64, 2)]

    def __repr__(self) -> str:
        return f"OpenRouterProvider(model={self.model_name})"
