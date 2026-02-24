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
        """Send a message and get a response."""
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
