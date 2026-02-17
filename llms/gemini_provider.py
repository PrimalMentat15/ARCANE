"""
ARCANE LLM Provider - Google Gemini

Uses the new google-genai SDK (replaces deprecated google-generativeai).
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

from llms.base_provider import BaseProvider

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger("root.llm.gemini")


class GeminiProvider(BaseProvider):
    """Google Gemini API provider (google-genai SDK)."""

    def __init__(self, model: str = "gemini-2.0-flash-lite",
                 api_key: str | None = None):
        self.model_name = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. LLM calls will fail.")

        from google import genai
        self._client = genai.Client(api_key=self.api_key)

    def _build_contents(self, messages: list[dict]):
        """Build genai Content objects from message dicts."""
        from google.genai import types

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])],
                )
            )
        return contents

    def complete_sync(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7,
                      max_tokens: int = 1024) -> str:
        """Generate a completion via Gemini (synchronous — no event loop needed)."""
        try:
            from google.genai import types

            contents = self._build_contents(messages)

            response = self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt or None,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini completion error: {e}")
            return f"[LLM Error: {e}]"

    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float = 0.7,
                       max_tokens: int = 1024) -> str:
        """Generate a completion via Gemini (async)."""
        try:
            from google.genai import types

            contents = self._build_contents(messages)

            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt or None,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini async completion error: {e}")
            return f"[LLM Error: {e}]"

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding via Gemini."""
        try:
            response = self._client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return []

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model_name})"
