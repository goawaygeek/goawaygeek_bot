"""Conversation history log — records all LLM interactions."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Protocol

from knowledge.models import ConversationRecord

logger = logging.getLogger(__name__)


class ConversationLogProtocol(Protocol):
    """Interface for conversation logging backends."""

    def log(self, record: ConversationRecord) -> int:
        """Save a conversation record. Returns the assigned ID."""
        ...

    def recent(self, limit: int = 20) -> List[ConversationRecord]:
        """Return the N most recent conversation records."""
        ...


class SQLiteConversationLog:
    """SQLite-backed conversation history log."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create the conversations table if it doesn't exist."""
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                user_message TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                llm_response TEXT NOT NULL,
                parsed_type TEXT,
                parsed_tags TEXT,
                parsed_summary TEXT
            )
        """)
        self._conn.commit()

    def log(self, record: ConversationRecord) -> int:
        """Save a conversation record. Returns the assigned ID."""
        cursor = self._conn.execute(
            """INSERT INTO conversations
               (timestamp, interaction_type, user_message, system_prompt,
                llm_response, parsed_type, parsed_tags, parsed_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.timestamp.isoformat(),
                record.interaction_type,
                record.user_message,
                record.system_prompt,
                record.llm_response,
                record.parsed_type,
                record.parsed_tags,
                record.parsed_summary,
            ),
        )
        self._conn.commit()
        record.record_id = cursor.lastrowid
        return cursor.lastrowid

    def recent(self, limit: int = 20) -> List[ConversationRecord]:
        """Return the N most recent conversation records, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: sqlite3.Row) -> ConversationRecord:
        """Convert a database row to a ConversationRecord."""
        return ConversationRecord(
            timestamp=datetime.fromisoformat(row["timestamp"]),
            interaction_type=row["interaction_type"],
            user_message=row["user_message"],
            system_prompt=row["system_prompt"],
            llm_response=row["llm_response"],
            parsed_type=row["parsed_type"],
            parsed_tags=row["parsed_tags"],
            parsed_summary=row["parsed_summary"],
            record_id=row["id"],
        )
