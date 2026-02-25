"""Tests for knowledge/conversation_log.py — conversation history logging."""

import time
from datetime import datetime, timezone
from pathlib import Path

from knowledge.conversation_log import SQLiteConversationLog
from knowledge.models import ConversationRecord


def _make_record(
    interaction_type: str = "capture",
    user_message: str = "test message",
    system_prompt: str = "You are a KB assistant.",
    llm_response: str = '{"item_type": "note"}',
    parsed_type: str = None,
    parsed_tags: str = None,
    parsed_summary: str = None,
) -> ConversationRecord:
    """Create a ConversationRecord with sensible defaults."""
    return ConversationRecord(
        interaction_type=interaction_type,
        user_message=user_message,
        system_prompt=system_prompt,
        llm_response=llm_response,
        parsed_type=parsed_type,
        parsed_tags=parsed_tags,
        parsed_summary=parsed_summary,
    )


def test_save_and_retrieve_record(tmp_conversation_db: Path):
    """Saving a record and retrieving it preserves all fields."""
    log = SQLiteConversationLog(db_path=tmp_conversation_db)
    record = _make_record(
        interaction_type="capture",
        user_message="buy groceries",
        system_prompt="You are a KB assistant.\n## Overview:\nNo overview yet.",
        llm_response='{"item_type":"task","tags":["errands"],"summary":"Buy groceries","response":"Got it!"}',
        parsed_type="task",
        parsed_tags='["errands"]',
        parsed_summary="Buy groceries",
    )
    record_id = log.log(record)

    results = log.recent(limit=1)
    assert len(results) == 1
    r = results[0]
    assert r.record_id == record_id
    assert r.interaction_type == "capture"
    assert r.user_message == "buy groceries"
    assert "KB assistant" in r.system_prompt
    assert "task" in r.llm_response
    assert r.parsed_type == "task"
    assert r.parsed_tags == '["errands"]'
    assert r.parsed_summary == "Buy groceries"


def test_log_returns_positive_id(tmp_conversation_db: Path):
    """log() returns a positive integer ID."""
    log = SQLiteConversationLog(db_path=tmp_conversation_db)
    record_id = log.log(_make_record())
    assert record_id > 0


def test_recent_returns_newest_first(tmp_conversation_db: Path):
    """recent() returns records newest-first."""
    log = SQLiteConversationLog(db_path=tmp_conversation_db)

    r1 = ConversationRecord(
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        interaction_type="capture",
        user_message="first",
        system_prompt="sys",
        llm_response="resp1",
    )
    r2 = ConversationRecord(
        timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        interaction_type="query",
        user_message="second",
        system_prompt="sys",
        llm_response="resp2",
    )
    r3 = ConversationRecord(
        timestamp=datetime(2025, 12, 1, tzinfo=timezone.utc),
        interaction_type="capture",
        user_message="third",
        system_prompt="sys",
        llm_response="resp3",
    )

    log.log(r1)
    log.log(r2)
    log.log(r3)

    results = log.recent(limit=10)
    assert len(results) == 3
    assert results[0].user_message == "third"
    assert results[1].user_message == "second"
    assert results[2].user_message == "first"


def test_recent_respects_limit(tmp_conversation_db: Path):
    """recent() respects the limit parameter."""
    log = SQLiteConversationLog(db_path=tmp_conversation_db)
    for i in range(5):
        log.log(_make_record(user_message=f"msg {i}"))

    results = log.recent(limit=2)
    assert len(results) == 2


def test_nullable_parsed_fields(tmp_conversation_db: Path):
    """Query-type records have None for parsed_type/tags/summary."""
    log = SQLiteConversationLog(db_path=tmp_conversation_db)
    record = _make_record(
        interaction_type="query",
        user_message="what am I working on?",
        llm_response="You are working on the bot project.",
    )
    log.log(record)

    results = log.recent(limit=1)
    r = results[0]
    assert r.parsed_type is None
    assert r.parsed_tags is None
    assert r.parsed_summary is None


def test_creates_db_directory(tmp_path: Path):
    """SQLiteConversationLog auto-creates parent directories."""
    nested_path = tmp_path / "deep" / "nested" / "conversations.db"
    log = SQLiteConversationLog(db_path=nested_path)
    log.log(_make_record())

    assert nested_path.exists()
    results = log.recent(limit=1)
    assert len(results) == 1
