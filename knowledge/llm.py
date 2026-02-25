import json
import logging
from typing import Optional, Protocol

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful personal assistant integrated into a Telegram bot. "
    "You receive messages from your user and respond conversationally. "
    "Keep responses concise and useful — this is a chat interface on a phone, "
    "not an essay. Be direct."
)


class LLMProtocol(Protocol):
    """Interface for LLM clients. Allows swapping Claude for Ollama later."""

    async def chat(self, message: str, system: Optional[str] = None) -> str:
        """Send a message and get a plain text response.

        Catches errors and returns user-friendly error strings.
        Used for simple conversational exchanges.
        """
        ...

    async def analyze(
        self,
        message: str,
        system: str,
        max_tokens: int = 2048,
    ) -> str:
        """Send a structured analysis request and get raw text back.

        Unlike chat(), this RAISES on errors so the caller can
        handle fallback logic. Used for KB capture/query where
        brain.py needs to know if the LLM failed.
        """
        ...


class ClaudeLLMClient:
    """Claude API client via the Anthropic SDK."""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(self, message: str, system: Optional[str] = None) -> str:
        """Send a message to Claude and return the response text."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system or SYSTEM_PROMPT,
                messages=[{"role": "user", "content": message}],
            )
            return response.content[0].text
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", e)
            return "Sorry, I couldn't process that right now. (API error)"
        except Exception as e:
            logger.exception("Unexpected error calling Claude")
            return "Sorry, something went wrong. (Unexpected error)"

    async def analyze(
        self,
        message: str,
        system: str,
        max_tokens: int = 2048,
    ) -> str:
        """Send a structured analysis request to Claude.

        Returns raw response text. The caller (brain.py) is responsible
        for parsing. Raises on API errors so the brain can fall back.
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": message}],
            )
            return response.content[0].text
        except anthropic.APIError as e:
            logger.error("Claude API error during analysis: %s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error during analysis")
            raise
