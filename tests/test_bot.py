import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    """The /start handler replies with a welcome message."""
    update = _make_update(123, "scott", "Scott", "/start")
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    reply_text = update.message.reply_text.call_args[0][0]
    assert "note-taking bot" in reply_text.lower() or "save" in reply_text.lower()


@pytest.mark.asyncio
async def test_handle_message_saves_and_replies(tmp_path: Path):
    """handle_message writes to storage and replies 'Saved.'"""
    log_file = tmp_path / "messages.log"

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
    }
    with patch.dict(os.environ, env, clear=True):
        import config

        config.validate_config()

        update = _make_update(42, "scott", "Scott", "remember to buy milk")
        context = MagicMock()

        await handle_message(update, context)

    update.message.reply_text.assert_called_once_with("Saved.")
    content = log_file.read_text(encoding="utf-8")
    assert "remember to buy milk" in content
    assert "user_id=42" in content
    assert "username=scott" in content


@pytest.mark.asyncio
async def test_handle_message_uses_first_name_when_no_username(tmp_path: Path):
    """handle_message falls back to first_name when username is None."""
    log_file = tmp_path / "messages.log"

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
    }
    with patch.dict(os.environ, env, clear=True):
        import config

        config.validate_config()

        update = _make_update(42, None, "Scott", "a note")
        context = MagicMock()

        await handle_message(update, context)

    content = log_file.read_text(encoding="utf-8")
    assert "username=Scott" in content


@pytest.mark.asyncio
async def test_integration_message_flow(tmp_path: Path):
    """Integration test: build the full handler pipeline and process a message."""
    log_file = tmp_path / "data" / "messages.log"

    env = {
        "BOT_TOKEN": "fake-token-for-test",
        "AUTHORIZED_USER_ID": "12345",
        "MESSAGES_FILE": str(log_file),
    }

    with patch.dict(os.environ, env, clear=True):
        import config

        config.validate_config()

        from storage import ensure_storage_dir

        ensure_storage_dir(config.MESSAGES_FILE)

        # Simulate the full flow: authorized user sends a message
        update = _make_update(12345, "testuser", "Test", "integration test note")
        context = MagicMock()

        await handle_message(update, context)

    # Verify storage
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "integration test note" in content
    assert "user_id=12345" in content
    assert "username=testuser" in content

    # Verify reply
    update.message.reply_text.assert_called_once_with("Saved.")
