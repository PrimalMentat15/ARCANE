"""
ARCANE LLM Provider - Base Interface

Abstract interface for LLM providers (Gemini, OpenRouter, OpenAI).
All agent reasoning goes through this abstraction.
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float = 0.7,
                       max_tokens: int = 1024) -> str:
        """
        Generate a text completion.

        Args:
            system_prompt: The system-level instruction
            messages: List of {"role": "user"|"assistant", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Maximum response length

        Returns:
            The generated text response
        """
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding
        """
        ...

    def complete_sync(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7,
                      max_tokens: int = 1024) -> str:
        """Synchronous wrapper for complete(). Used in Mesa's step()."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, use nest_asyncio pattern
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.complete(system_prompt, messages,
                                      temperature, max_tokens)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.complete(system_prompt, messages,
                                 temperature, max_tokens)
                )
        except RuntimeError:
            return asyncio.run(
                self.complete(system_prompt, messages,
                              temperature, max_tokens)
            )
