"""SQLite + FTS5 knowledge store."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol

from knowledge.models import ItemType, KnowledgeItem, SearchResult

logger = logging.getLogger(__name__)

OVERVIEW_KEY = "__rolling_overview__"


class StoreProtocol(Protocol):
    """Interface for knowledge storage backends."""

    def save_item(self, item: KnowledgeItem) -> int:
        """Save a knowledge item. Returns the assigned item_id."""
        ...

    def get_item(self, item_id: int) -> Optional[KnowledgeItem]:
        """Retrieve an item by its ID."""
        ...

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Full-text search."""
        ...

    def recent(self, limit: int = 10) -> List[KnowledgeItem]:
        """Return the N most recent items."""
        ...

    def get_overview(self) -> str:
        """Return the current rolling overview text."""
        ...

    def save_overview(self, text: str) -> None:
        """Overwrite the rolling overview."""
        ...

    def count(self) -> int:
        """Return total item count."""
        ...


class SQLiteStore:
    """SQLite + FTS5 knowledge store."""

    def __init__(self, db_path: Path, overview_md_path: Optional[Path] = None):
        self.db_path = db_path
        self.overview_md_path = overview_md_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create tables and FTS5 virtual table if they don't exist."""
        self._conn.execute("PRAGMA journal_mode=WAL")

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                item_type TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                summary TEXT NOT NULL DEFAULT '',
                source_url TEXT,
                url_content TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # FTS5 for full-text search on content, summary, and tags
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS items_fts
                USING fts5(content, summary, tags, content=items, content_rowid=id)
            """)
        except sqlite3.OperationalError:
            logger.error(
                "FTS5 is not available in this SQLite build. "
                "Full-text search will not work."
            )

        # Triggers to keep FTS5 in sync with the items table
        self._conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                INSERT INTO items_fts(rowid, content, summary, tags)
                VALUES (new.id, new.content, new.summary, new.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, content, summary, tags)
                VALUES ('delete', old.id, old.content, old.summary, old.tags);
            END;

            CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
                INSERT INTO items_fts(items_fts, rowid, content, summary, tags)
                VALUES ('delete', old.id, old.content, old.summary, old.tags);
                INSERT INTO items_fts(rowid, content, summary, tags)
                VALUES (new.id, new.content, new.summary, new.tags);
            END;
        """)

        # Overview table — single row key-value store
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS overview (
                key TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        self._conn.commit()

    def save_item(self, item: KnowledgeItem) -> int:
        """Save a knowledge item. Returns the assigned item_id."""
        cursor = self._conn.execute(
            """
            INSERT INTO items (content, item_type, tags, summary,
                               source_url, url_content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.content,
                item.item_type.value,
                json.dumps(item.tags),
                item.summary,
                item.source_url,
                item.url_content,
                item.created_at.isoformat(),
            ),
        )
        self._conn.commit()
        item_id = cursor.lastrowid
        item.item_id = item_id
        return item_id

    def get_item(self, item_id: int) -> Optional[KnowledgeItem]:
        """Retrieve an item by its ID."""
        row = self._conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_item(row)

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Full-text search using FTS5 with bm25 ranking."""
        try:
            rows = self._conn.execute(
                """
                SELECT items.*, bm25(items_fts) AS rank
                FROM items_fts
                JOIN items ON items.id = items_fts.rowid
                WHERE items_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("FTS5 search failed for query: %s", query)
            return []

        results = []
        for row in rows:
            item = self._row_to_item(row)
            results.append(SearchResult(
                item=item,
                rank=row["rank"],
                snippet=item.summary or item.content[:100],
            ))
        return results

    def recent(self, limit: int = 10) -> List[KnowledgeItem]:
        """Return the N most recent items, newest first."""
        rows = self._conn.execute(
            "SELECT * FROM items ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def get_overview(self) -> str:
        """Return the current rolling overview text, or empty string."""
        row = self._conn.execute(
            "SELECT text FROM overview WHERE key = ?", (OVERVIEW_KEY,)
        ).fetchone()
        if row is None:
            return ""
        return row["text"]

    def save_overview(self, text: str) -> None:
        """Insert or replace the rolling overview."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO overview (key, text, updated_at)
            VALUES (?, ?, ?)
            """,
            (OVERVIEW_KEY, text, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        self._export_overview_md(text)

    def _export_overview_md(self, text: str) -> None:
        """Write the overview to a markdown file if path is configured."""
        if self.overview_md_path is None:
            return
        try:
            self.overview_md_path.parent.mkdir(parents=True, exist_ok=True)
            self.overview_md_path.write_text(
                "# Knowledge Base Overview\n\n"
                "_Last updated: {}_\n\n"
                "{}\n".format(
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    text,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.warning(
                "Failed to export overview to %s",
                self.overview_md_path,
                exc_info=True,
            )

    def count(self) -> int:
        """Return total number of knowledge items."""
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM items").fetchone()
        return row["cnt"]

    def _row_to_item(self, row: sqlite3.Row) -> KnowledgeItem:
        """Convert a database row to a KnowledgeItem."""
        return KnowledgeItem(
            content=row["content"],
            item_type=ItemType(row["item_type"]),
            tags=json.loads(row["tags"]),
            summary=row["summary"],
            source_url=row["source_url"],
            url_content=row["url_content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            item_id=row["id"],
        )
