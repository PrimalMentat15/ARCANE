"""
ARCANE LLM Provider - Local (OpenAI-Compatible)

Connects to any local inference server that exposes an OpenAI-compatible
chat completions API, such as LM Studio, Ollama, vLLM, or llama.cpp.

Default: LM Studio on http://localhost:1234/v1
"""

import os
import logging
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv

from backend.llms.base_provider import BaseProvider

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger("root.llm.local")

# Retry config for local server hiccups
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0  # seconds


class LocalLLMProvider(BaseProvider):
    """Local LLM provider via OpenAI-compatible API (LM Studio, Ollama, etc.)."""

    def __init__(self, model: str = "llama-3.1-8b-instruct",
                 base_url: str = "http://localhost:1234/v1",
                 timeout: float = 120.0,
                 embedding_model: str | None = None):
        """
        Args:
            model: Model identifier as shown in the local server
            base_url: OpenAI-compatible API base URL (e.g. http://localhost:1234/v1)
            timeout: Request timeout in seconds (local models can be slow)
            embedding_model: Optional dedicated embedding model name
        """
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.embedding_model = embedding_model

        logger.info(f"LocalLLMProvider initialized: model={model}, "
                    f"base_url={self.base_url}, timeout={timeout}s")

    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float = 0.7,
                       max_tokens: int = 1024) -> str:
        """Generate a completion via the local OpenAI-compatible API (async)."""
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
                        f"{self.base_url}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json={
                            "model": self.model_name,
                            "messages": api_messages,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                            "stream": False,
                        },
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                return data["choices"][0]["message"]["content"]

            except httpx.ConnectError as e:
                logger.error(
                    f"Cannot connect to local LLM server at {self.base_url}. "
                    f"Is LM Studio running with the server started? Error: {e}"
                )
                return (
                    f"[LLM Error: Cannot connect to local server at "
                    f"{self.base_url}. Make sure LM Studio is running and "
                    f"the server is started.]"
                )
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Local LLM request timed out after {self.timeout}s. "
                        f"Retrying in {delay}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Local LLM timed out after {MAX_RETRIES} attempts. "
                        f"Consider increasing timeout or using a smaller model."
                    )
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Local LLM error: {e}. "
                        f"Retrying in {delay}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Local LLM completion failed after "
                        f"{MAX_RETRIES} attempts: {e}"
                    )

        return f"[LLM Error: {last_error}]"

    def complete_sync(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7,
                      max_tokens: int = 1024) -> str:
        """Generate a completion via the local API (synchronous)."""
        # Build messages list with system prompt
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.model_name,
                        "messages": api_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": False,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            return data["choices"][0]["message"]["content"]

        except httpx.ConnectError as e:
            logger.error(
                f"Cannot connect to local LLM server at {self.base_url}. "
                f"Is LM Studio running? Error: {e}"
            )
            return (
                f"[LLM Error: Cannot connect to local server at "
                f"{self.base_url}. Make sure LM Studio is running.]"
            )
        except Exception as e:
            logger.error(f"Local LLM sync completion error: {e}")
            return f"[LLM Error: {e}]"

    async def embed(self, text: str) -> list[float]:
        """
        Generate an embedding via the local server.

        Most local servers support the /v1/embeddings endpoint, but it
        requires a model loaded with embedding support. Falls back to
        a hash-based placeholder if no embedding model is configured.
        """
        if not self.embedding_model:
            logger.warning(
                "No embedding model configured for local provider. "
                "Using hash-based placeholder. Pull an embedding model "
                "and set 'embedding_model' in settings.yaml for real embeddings."
            )
            import hashlib
            h = hashlib.sha256(text.encode()).hexdigest()
            return [int(h[i:i+2], 16) / 255.0 for i in range(0, 64, 2)]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.embedding_model,
                        "input": text,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

            return data["data"][0]["embedding"]

        except Exception as e:
            logger.error(f"Local embedding error: {e}")
            return []

    def __repr__(self) -> str:
        return f"LocalLLMProvider(model={self.model_name}, url={self.base_url})"
