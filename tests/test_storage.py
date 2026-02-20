import re
from pathlib import Path

from storage import ensure_storage_dir, save_message


def test_ensure_storage_dir_creates_nested_dirs(tmp_path: Path):
    """ensure_storage_dir creates the full parent directory tree."""
    file_path = tmp_path / "a" / "b" / "c" / "messages.log"
    ensure_storage_dir(file_path)
    assert file_path.parent.is_dir()


def test_ensure_storage_dir_idempotent(tmp_path: Path):
    """ensure_storage_dir can be called multiple times without error."""
    file_path = tmp_path / "data" / "messages.log"
    ensure_storage_dir(file_path)
    ensure_storage_dir(file_path)
    assert file_path.parent.is_dir()


def test_save_message_creates_file(tmp_log_file: Path):
    """save_message creates the file on first write."""
    ensure_storage_dir(tmp_log_file)
    save_message(tmp_log_file, user_id=123, username="testuser", text="hello")
    assert tmp_log_file.exists()


def test_save_message_format(tmp_log_file: Path):
    """save_message writes the correct header and text format."""
    ensure_storage_dir(tmp_log_file)
    save_message(tmp_log_file, user_id=42, username="scott", text="test message")

    content = tmp_log_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Header line: [ISO-timestamp] user_id=42 username=scott
    assert re.match(
        r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*\] user_id=42 username=scott",
        lines[0],
    )
    # Message text
    assert lines[1] == "test message"
    # Blank separator line
    assert lines[2] == ""


def test_save_message_multiline(tmp_log_file: Path):
    """save_message preserves multi-line messages."""
    ensure_storage_dir(tmp_log_file)
    save_message(
        tmp_log_file,
        user_id=1,
        username="user",
        text="line one\nline two\nline three",
    )

    content = tmp_log_file.read_text(encoding="utf-8")
    assert "line one\nline two\nline three" in content


def test_save_message_appends(tmp_log_file: Path):
    """Multiple save_message calls append to the same file."""
    ensure_storage_dir(tmp_log_file)
    save_message(tmp_log_file, user_id=1, username="a", text="first")
    save_message(tmp_log_file, user_id=2, username="b", text="second")

    content = tmp_log_file.read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content
    # Two entries means two header lines
    assert content.count("user_id=") == 2


def test_save_message_utf8(tmp_log_file: Path):
    """save_message handles unicode text correctly."""
    ensure_storage_dir(tmp_log_file)
    save_message(tmp_log_file, user_id=1, username="user", text="Hello 🌍 café")

    content = tmp_log_file.read_text(encoding="utf-8")
    assert "Hello 🌍 café" in content
