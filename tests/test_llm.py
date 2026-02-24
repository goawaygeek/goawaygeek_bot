from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge.llm import ClaudeLLMClient, SYSTEM_PROMPT


def _make_mock_response(text: str):
    """Create a mock Anthropic API response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


@pytest.mark.asyncio
async def test_chat_returns_response():
    """chat() returns the text from Claude's response."""
    client = ClaudeLLMClient(api_key="fake-key", model="claude-test")

    mock_response = _make_mock_response("Hello! How can I help?")
    client.client.messages.create = AsyncMock(return_value=mock_response)

    result = await client.chat("Hi there")

    assert result == "Hello! How can I help?"
    client.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_chat_sends_correct_params():
    """chat() sends the message with the right model and system prompt."""
    client = ClaudeLLMClient(api_key="fake-key", model="claude-test-model")

    mock_response = _make_mock_response("response")
    client.client.messages.create = AsyncMock(return_value=mock_response)

    await client.chat("test message")

    call_kwargs = client.client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-test-model"
    assert call_kwargs["system"] == SYSTEM_PROMPT
    assert call_kwargs["messages"] == [{"role": "user", "content": "test message"}]
    assert call_kwargs["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_chat_custom_system_prompt():
    """chat() uses a custom system prompt when provided."""
    client = ClaudeLLMClient(api_key="fake-key", model="claude-test")

    mock_response = _make_mock_response("response")
    client.client.messages.create = AsyncMock(return_value=mock_response)

    await client.chat("test", system="Custom system prompt")

    call_kwargs = client.client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "Custom system prompt"


@pytest.mark.asyncio
async def test_chat_handles_api_error():
    """chat() returns an error message when the API fails."""
    import anthropic

    client = ClaudeLLMClient(api_key="fake-key", model="claude-test")
    client.client.messages.create = AsyncMock(
        side_effect=anthropic.APIError(
            message="rate limited",
            request=MagicMock(),
            body=None,
        )
    )

    result = await client.chat("test")

    assert "API error" in result


@pytest.mark.asyncio
async def test_chat_handles_unexpected_error():
    """chat() returns an error message on unexpected exceptions."""
    client = ClaudeLLMClient(api_key="fake-key", model="claude-test")
    client.client.messages.create = AsyncMock(
        side_effect=RuntimeError("connection lost")
    )

    result = await client.chat("test")

    assert "something went wrong" in result
