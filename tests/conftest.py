import pytest
from pathlib import Path


@pytest.fixture
def tmp_log_file(tmp_path: Path) -> Path:
    """Return a path to a temporary log file (does not create the file)."""
    return tmp_path / "data" / "messages.log"


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return a path to a temporary SQLite database."""
    return tmp_path / "test_knowledge.db"


@pytest.fixture
def tmp_conversation_db(tmp_path: Path) -> Path:
    """Return a path to a temporary conversation log database."""
    return tmp_path / "test_conversations.db"
