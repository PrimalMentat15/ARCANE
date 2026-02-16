"""
ARCANE LLM Provider - Google Gemini

Uses the google-generativeai SDK for text generation and embeddings.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

from llm.base_provider import BaseProvider

# Load .env from project root or arcane/ dir
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")          # c:\...\ARCANE\.env
load_dotenv(_project_root / "arcane" / ".env")  # c:\...\ARCANE\arcane\.env (fallback)

logger = logging.getLogger("root.llm.gemini")


class GeminiProvider(BaseProvider):
    """Google Gemini API provider."""

    def __init__(self, model: str = "gemini-2.0-flash",
                 api_key: str | None = None):
        self.model_name = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. LLM calls will fail.")

        # Configure the SDK
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(self.model_name)

    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float = 0.7,
                       max_tokens: int = 1024) -> str:
        """Generate a completion via Gemini."""
        try:
            # Build the prompt from system + messages
            contents = []

            # Add system instruction as first user context
            if system_prompt:
                contents.append({"role": "user", "parts": [system_prompt]})
                contents.append({
                    "role": "model",
                    "parts": ["Understood. I will follow these instructions."]
                })

            # Add conversation messages
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [msg["content"]]})

            response = self._model.generate_content(
                contents,
                generation_config=self._genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

            return response.text

        except Exception as e:
            logger.error(f"Gemini completion error: {e}")
            return f"[LLM Error: {e}]"

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding via Gemini."""
        try:
            result = self._genai.embed_content(
                model="models/text-embedding-004",
                content=text,
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return []

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model_name})"
