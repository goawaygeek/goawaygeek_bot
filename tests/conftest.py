import pytest
from pathlib import Path


@pytest.fixture
def tmp_log_file(tmp_path: Path) -> Path:
    """Return a path to a temporary log file (does not create the file)."""
    return tmp_path / "data" / "messages.log"
