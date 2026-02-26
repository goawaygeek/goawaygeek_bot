"""Tests for knowledge.store."""

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowledge.models import ItemType, KnowledgeItem
from knowledge.store import SQLiteStore


def _make_item(
    content: str = "test content",
    item_type: ItemType = ItemType.NOTE,
    tags: list = None,
    summary: str = "",
    source_url: str = None,
) -> KnowledgeItem:
    """Create a KnowledgeItem with sensible defaults for testing."""
    return KnowledgeItem(
        content=content,
        item_type=item_type,
        tags=tags or [],
        summary=summary,
        source_url=source_url,
    )


def test_fts5_available():
    """Verify SQLite FTS5 extension is available."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
    conn.close()


def test_save_and_get_item(tmp_db: Path):
    """Save an item and retrieve it by ID."""
    store = SQLiteStore(tmp_db)
    item = _make_item(
        content="Buy groceries",
        item_type=ItemType.TASK,
        tags=["shopping", "errands"],
        summary="Weekly grocery run",
    )
    item_id = store.save_item(item)
    retrieved = store.get_item(item_id)

    assert retrieved is not None
    assert retrieved.content == "Buy groceries"
    assert retrieved.item_type == ItemType.TASK
    assert retrieved.tags == ["shopping", "errands"]
    assert retrieved.summary == "Weekly grocery run"
    assert retrieved.item_id == item_id


def test_save_item_assigns_id(tmp_db: Path):
    """Saving an item returns a positive integer ID."""
    store = SQLiteStore(tmp_db)
    item_id = store.save_item(_make_item())
    assert isinstance(item_id, int)
    assert item_id > 0


def test_get_item_nonexistent(tmp_db: Path):
    """Getting a nonexistent item returns None."""
    store = SQLiteStore(tmp_db)
    assert store.get_item(9999) is None


def test_search_finds_matching_content(tmp_db: Path):
    """FTS5 search finds items by content."""
    store = SQLiteStore(tmp_db)
    store.save_item(_make_item(content="Python async tutorial"))
    store.save_item(_make_item(content="Grocery shopping list"))
    store.save_item(_make_item(content="Python web scraping guide"))

    results = store.search("Python")
    assert len(results) == 2
    contents = [r.item.content for r in results]
    assert "Python async tutorial" in contents
    assert "Python web scraping guide" in contents


def test_search_returns_empty_on_no_match(tmp_db: Path):
    """Search for nonexistent term returns empty list."""
    store = SQLiteStore(tmp_db)
    store.save_item(_make_item(content="Nothing relevant here"))
    results = store.search("xyznonexistent")
    assert results == []


def test_search_respects_limit(tmp_db: Path):
    """Search returns at most `limit` results."""
    store = SQLiteStore(tmp_db)
    for i in range(5):
        store.save_item(_make_item(content=f"Python tip number {i}"))

    results = store.search("Python", limit=2)
    assert len(results) == 2


def test_search_strips_punctuation_from_query(tmp_db: Path):
    """Natural-language questions with punctuation still find matching items."""
    store = SQLiteStore(tmp_db)
    store.save_item(_make_item(content="NSW Create grants open March 2025", summary="grants"))

    # A natural question with a trailing ? should still find the item
    results = store.search("what grants are open in March?")
    assert len(results) >= 1


def test_search_uses_or_matching(tmp_db: Path):
    """Multi-word queries match documents containing ANY of the terms."""
    store = SQLiteStore(tmp_db)
    store.save_item(_make_item(content="grant funding deadline", summary="NSW grant"))
    store.save_item(_make_item(content="totally unrelated content", summary="nothing"))

    # "grants" and "funding" are OR'd; first item has both, second has neither
    results = store.search("grants funding deadline")
    assert len(results) == 1
    assert "grant" in results[0].item.content


def test_recent_returns_newest_first(tmp_db: Path):
    """Recent items are returned newest first."""
    store = SQLiteStore(tmp_db)
    store.save_item(_make_item(content="first"))
    time.sleep(0.01)  # Ensure distinct timestamps
    store.save_item(_make_item(content="second"))
    time.sleep(0.01)
    store.save_item(_make_item(content="third"))

    items = store.recent(limit=3)
    assert items[0].content == "third"
    assert items[1].content == "second"
    assert items[2].content == "first"


def test_recent_respects_limit(tmp_db: Path):
    """Recent returns at most `limit` items."""
    store = SQLiteStore(tmp_db)
    for i in range(5):
        store.save_item(_make_item(content=f"item {i}"))

    items = store.recent(limit=3)
    assert len(items) == 3


def test_overview_empty_initially(tmp_db: Path):
    """Fresh database returns empty string for overview."""
    store = SQLiteStore(tmp_db)
    assert store.get_overview() == ""


def test_save_and_get_overview(tmp_db: Path):
    """Save overview text and retrieve it."""
    store = SQLiteStore(tmp_db)
    store.save_overview("## Projects\n- Bot project")
    assert store.get_overview() == "## Projects\n- Bot project"


def test_save_overview_overwrites(tmp_db: Path):
    """Saving overview twice keeps only the latest version."""
    store = SQLiteStore(tmp_db)
    store.save_overview("version 1")
    store.save_overview("version 2")
    assert store.get_overview() == "version 2"


def test_tags_stored_as_list(tmp_db: Path):
    """Tags survive the JSON serialization roundtrip."""
    store = SQLiteStore(tmp_db)
    item_id = store.save_item(_make_item(tags=["alpha", "beta", "gamma"]))
    retrieved = store.get_item(item_id)
    assert retrieved.tags == ["alpha", "beta", "gamma"]


def test_item_type_preserved(tmp_db: Path):
    """ItemType enum survives storage and retrieval."""
    store = SQLiteStore(tmp_db)
    for t in ItemType:
        item_id = store.save_item(_make_item(item_type=t))
        retrieved = store.get_item(item_id)
        assert retrieved.item_type == t


def test_count_tracks_items(tmp_db: Path):
    """count() returns the total number of stored items."""
    store = SQLiteStore(tmp_db)
    assert store.count() == 0
    store.save_item(_make_item())
    store.save_item(_make_item())
    store.save_item(_make_item())
    assert store.count() == 3


# --- Overview markdown export tests ---


def test_save_overview_exports_markdown(tmp_path: Path):
    """save_overview writes a markdown file when overview_md_path is set."""
    db_path = tmp_path / "test.db"
    md_path = tmp_path / "overview.md"
    store = SQLiteStore(db_path, overview_md_path=md_path)
    store.save_overview("## My Projects\n- Bot project")

    assert md_path.exists()
    content = md_path.read_text(encoding="utf-8")
    assert "## My Projects" in content
    assert "Bot project" in content


def test_save_overview_markdown_has_header(tmp_path: Path):
    """Exported markdown has a header and timestamp."""
    db_path = tmp_path / "test.db"
    md_path = tmp_path / "overview.md"
    store = SQLiteStore(db_path, overview_md_path=md_path)
    store.save_overview("Some overview text")

    content = md_path.read_text(encoding="utf-8")
    assert "# Knowledge Base Overview" in content
    assert "Last updated:" in content
    assert "UTC" in content


def test_save_overview_markdown_updates_on_each_save(tmp_path: Path):
    """Each save_overview call updates the markdown file."""
    db_path = tmp_path / "test.db"
    md_path = tmp_path / "overview.md"
    store = SQLiteStore(db_path, overview_md_path=md_path)
    store.save_overview("version 1")
    store.save_overview("version 2")

    content = md_path.read_text(encoding="utf-8")
    assert "version 2" in content
    assert "version 1" not in content


def test_save_overview_no_markdown_when_path_is_none(tmp_db: Path, tmp_path: Path):
    """No markdown file is created when overview_md_path is None."""
    store = SQLiteStore(tmp_db)
    store.save_overview("Some text")

    # Verify no .md files were created in the temp directory
    md_files = list(tmp_path.glob("**/*.md"))
    assert len(md_files) == 0
    # But overview is still saved to DB
    assert store.get_overview() == "Some text"


def test_save_overview_markdown_failure_does_not_break_save(
    tmp_path: Path,
):
    """If markdown export fails, overview is still saved to SQLite."""
    db_path = tmp_path / "test.db"
    # Point to a path we can't write to (a file as a "directory")
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory")
    md_path = blocker / "overview.md"  # Can't create file inside a file

    store = SQLiteStore(db_path, overview_md_path=md_path)
    store.save_overview("Important overview")

    # DB save should still succeed
    assert store.get_overview() == "Important overview"
