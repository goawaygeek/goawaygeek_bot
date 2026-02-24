import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot
from bot import handle_message, start_command


def _make_update(user_id: int, username: str, first_name: str, text: str):
    """Create a mock Telegram Update with the given user and message."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = first_name
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_mock_llm(response: str = "LLM response"):
    """Create a mock LLM client."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=response)
    return mock_llm


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    """The /start handler replies with a welcome message."""
    update = _make_update(123, "scott", "Scott", "/start")
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "knowledge base" in reply_text.lower() or "llm" in reply_text.lower()


@pytest.mark.asyncio
async def test_handle_message_calls_llm_and_replies(tmp_path: Path):
    """handle_message sends text to LLM and replies with the response."""
    log_file = tmp_path / "messages.log"
    mock_llm = _make_mock_llm("That's a great idea!")

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        # Inject mock LLM
        original_llm = bot.llm
        bot.llm = mock_llm
        try:
            update = _make_update(42, "scott", "Scott", "remember to buy milk")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.llm = original_llm

    # LLM was called with the message text
    mock_llm.chat.assert_called_once_with("remember to buy milk")

    # Bot replied with LLM's response
    update.message.reply_text.assert_called_once_with("That's a great idea!")

    # Message was also saved to legacy log
    content = log_file.read_text(encoding="utf-8")
    assert "remember to buy milk" in content


@pytest.mark.asyncio
async def test_handle_message_saves_to_legacy_log(tmp_path: Path):
    """handle_message still writes to the legacy log file."""
    log_file = tmp_path / "messages.log"
    mock_llm = _make_mock_llm()

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        original_llm = bot.llm
        bot.llm = mock_llm
        try:
            update = _make_update(42, "scott", "Scott", "a note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.llm = original_llm

    content = log_file.read_text(encoding="utf-8")
    assert "user_id=42" in content
    assert "username=scott" in content
    assert "a note" in content


@pytest.mark.asyncio
async def test_handle_message_uses_first_name_when_no_username(tmp_path: Path):
    """handle_message falls back to first_name when username is None."""
    log_file = tmp_path / "messages.log"
    mock_llm = _make_mock_llm()

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        original_llm = bot.llm
        bot.llm = mock_llm
        try:
            update = _make_update(42, None, "Scott", "a note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.llm = original_llm

    content = log_file.read_text(encoding="utf-8")
    assert "username=Scott" in content


@pytest.mark.asyncio
async def test_integration_message_flow(tmp_path: Path):
    """Integration test: message in -> LLM processes -> reply sent + log written."""
    log_file = tmp_path / "data" / "messages.log"
    mock_llm = _make_mock_llm("Got it, noted!")

    env = {
        "BOT_TOKEN": "fake-token-for-test",
        "AUTHORIZED_USER_ID": "12345",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }

    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        from storage import ensure_storage_dir
        ensure_storage_dir(config.MESSAGES_FILE)

        original_llm = bot.llm
        bot.llm = mock_llm
        try:
            update = _make_update(12345, "testuser", "Test", "integration test note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.llm = original_llm

    # Verify storage
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "integration test note" in content
    assert "user_id=12345" in content

    # Verify LLM was called
    mock_llm.chat.assert_called_once_with("integration test note")

    # Verify reply is from LLM
    update.message.reply_text.assert_called_once_with("Got it, noted!")
