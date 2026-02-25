"""Tests for bot.py — Telegram handlers and integration."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot
from bot import (
    ask_command,
    handle_message,
    help_command,
    overview_command,
    recent_command,
    refresh_command,
    search_command,
    start_command,
)
from knowledge.models import ItemType, KnowledgeItem, SearchResult


def _make_update(user_id: int, username: str, first_name: str, text: str):
    """Create a mock Telegram Update with the given user and message."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.effective_user.first_name = first_name
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_mock_brain(
    capture_response: str = "Saved!",
    query_response: str = "Answer",
    overview_text: str = "## Overview",
    refresh_result: str = "Overview refreshed.",
):
    """Create a mock KnowledgeBrain."""
    mock_brain = MagicMock()
    mock_brain.capture = AsyncMock(return_value=capture_response)
    mock_brain.query = AsyncMock(return_value=query_response)
    mock_brain.get_overview = AsyncMock(return_value=overview_text)
    mock_brain.refresh_overview = AsyncMock(return_value=refresh_result)
    mock_brain.recent.return_value = []
    mock_brain.search.return_value = []
    return mock_brain


def _inject_brain(mock_brain):
    """Context manager helper to inject a mock brain into bot module."""
    original = bot.brain
    bot.brain = mock_brain
    return original


# --- /start and /help tests ---


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    """The /start handler replies with a welcome message."""
    update = _make_update(123, "scott", "Scott", "/start")
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "knowledge base" in reply.lower()


@pytest.mark.asyncio
async def test_help_command_lists_commands():
    """The /help handler lists available commands."""
    update = _make_update(123, "scott", "Scott", "/help")
    context = MagicMock()

    await help_command(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "/ask" in reply
    assert "/search" in reply
    assert "/recent" in reply
    assert "/overview" in reply
    assert "/refresh" in reply


# --- handle_message tests ---


@pytest.mark.asyncio
async def test_handle_message_calls_brain_capture(tmp_path: Path):
    """handle_message routes text through brain.capture()."""
    log_file = tmp_path / "messages.log"
    mock_brain = _make_mock_brain(capture_response="Got it! Filed as a note.")

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        original = _inject_brain(mock_brain)
        try:
            update = _make_update(42, "scott", "Scott", "remember to buy milk")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.brain = original

    mock_brain.capture.assert_called_once_with("remember to buy milk")
    update.message.reply_text.assert_called_once_with("Got it! Filed as a note.")


@pytest.mark.asyncio
async def test_handle_message_still_saves_to_legacy_log(tmp_path: Path):
    """handle_message writes to the legacy log file alongside KB capture."""
    log_file = tmp_path / "messages.log"
    mock_brain = _make_mock_brain()

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        original = _inject_brain(mock_brain)
        try:
            update = _make_update(42, "scott", "Scott", "a note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.brain = original

    content = log_file.read_text(encoding="utf-8")
    assert "user_id=42" in content
    assert "username=scott" in content
    assert "a note" in content


@pytest.mark.asyncio
async def test_handle_message_uses_first_name_when_no_username(tmp_path: Path):
    """handle_message falls back to first_name when username is None."""
    log_file = tmp_path / "messages.log"
    mock_brain = _make_mock_brain()

    env = {
        "BOT_TOKEN": "fake",
        "AUTHORIZED_USER_ID": "42",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }
    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        original = _inject_brain(mock_brain)
        try:
            update = _make_update(42, None, "Scott", "a note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.brain = original

    content = log_file.read_text(encoding="utf-8")
    assert "username=Scott" in content


# --- /ask tests ---


@pytest.mark.asyncio
async def test_ask_command_calls_brain_query():
    """/ask routes the question through brain.query()."""
    mock_brain = _make_mock_brain(query_response="You have 3 projects.")
    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/ask what am I working on")
        context = MagicMock()
        context.args = ["what", "am", "I", "working", "on"]

        await ask_command(update, context)
    finally:
        bot.brain = original

    mock_brain.query.assert_called_once_with("what am I working on")
    update.message.reply_text.assert_called_once_with("You have 3 projects.")


@pytest.mark.asyncio
async def test_ask_command_no_args_shows_usage():
    """/ask with no arguments shows usage instructions."""
    mock_brain = _make_mock_brain()
    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/ask")
        context = MagicMock()
        context.args = []

        await ask_command(update, context)
    finally:
        bot.brain = original

    reply = update.message.reply_text.call_args[0][0]
    assert "Usage" in reply
    mock_brain.query.assert_not_called()


# --- /search tests ---


@pytest.mark.asyncio
async def test_search_command_shows_results():
    """/search shows formatted results."""
    item = KnowledgeItem(
        content="test", item_type=ItemType.LINK,
        tags=["python"], summary="Python tutorial",
    )
    mock_brain = _make_mock_brain()
    mock_brain.search.return_value = [SearchResult(item=item, rank=1.0)]

    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/search python")
        context = MagicMock()
        context.args = ["python"]

        await search_command(update, context)
    finally:
        bot.brain = original

    reply = update.message.reply_text.call_args[0][0]
    assert "Python tutorial" in reply
    assert "link" in reply


@pytest.mark.asyncio
async def test_search_command_no_results():
    """/search with no results shows a message."""
    mock_brain = _make_mock_brain()
    mock_brain.search.return_value = []

    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/search nothing")
        context = MagicMock()
        context.args = ["nothing"]

        await search_command(update, context)
    finally:
        bot.brain = original

    reply = update.message.reply_text.call_args[0][0]
    assert "No results" in reply


# --- /recent tests ---


@pytest.mark.asyncio
async def test_recent_command_shows_items():
    """/recent shows formatted items."""
    item = KnowledgeItem(
        content="test", item_type=ItemType.NOTE,
        tags=["misc"], summary="A saved note",
    )
    mock_brain = _make_mock_brain()
    mock_brain.recent.return_value = [item]

    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/recent")
        context = MagicMock()

        await recent_command(update, context)
    finally:
        bot.brain = original

    reply = update.message.reply_text.call_args[0][0]
    assert "A saved note" in reply
    assert "misc" in reply


@pytest.mark.asyncio
async def test_recent_command_no_items():
    """/recent with no items shows a message."""
    mock_brain = _make_mock_brain()
    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/recent")
        context = MagicMock()

        await recent_command(update, context)
    finally:
        bot.brain = original

    reply = update.message.reply_text.call_args[0][0]
    assert "No items" in reply


# --- /overview tests ---


@pytest.mark.asyncio
async def test_overview_command():
    """/overview returns the brain's overview."""
    mock_brain = _make_mock_brain(overview_text="## My Projects\n- Bot")
    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/overview")
        context = MagicMock()

        await overview_command(update, context)
    finally:
        bot.brain = original

    mock_brain.get_overview.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "My Projects" in reply


# --- /refresh tests ---


@pytest.mark.asyncio
async def test_refresh_command():
    """/refresh triggers overview refresh and shows result."""
    mock_brain = _make_mock_brain(refresh_result="Overview refreshed.")
    original = _inject_brain(mock_brain)
    try:
        update = _make_update(42, "scott", "Scott", "/refresh")
        context = MagicMock()

        await refresh_command(update, context)
    finally:
        bot.brain = original

    mock_brain.refresh_overview.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "refreshed" in reply.lower()


# --- Integration test ---


@pytest.mark.asyncio
async def test_integration_message_flow(tmp_path: Path):
    """Integration: message in -> brain captures -> reply sent + log written."""
    log_file = tmp_path / "data" / "messages.log"
    mock_brain = _make_mock_brain(capture_response="Filed as a note!")

    env = {
        "BOT_TOKEN": "fake-token",
        "AUTHORIZED_USER_ID": "12345",
        "MESSAGES_FILE": str(log_file),
        "ANTHROPIC_API_KEY": "fake-key",
    }

    with patch.dict(os.environ, env, clear=True):
        import config
        config.validate_config()

        from storage import ensure_storage_dir
        ensure_storage_dir(config.MESSAGES_FILE)

        original = _inject_brain(mock_brain)
        try:
            update = _make_update(12345, "testuser", "Test", "integration test note")
            context = MagicMock()
            await handle_message(update, context)
        finally:
            bot.brain = original

    # Verify legacy storage
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "integration test note" in content
    assert "user_id=12345" in content

    # Verify brain was called
    mock_brain.capture.assert_called_once_with("integration test note")

    # Verify reply is from brain
    update.message.reply_text.assert_called_once_with("Filed as a note!")
