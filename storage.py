from datetime import datetime, timezone
from pathlib import Path


def ensure_storage_dir(file_path: Path) -> None:
    """Create the parent directory for the storage file if it doesn't exist."""
    file_path.parent.mkdir(parents=True, exist_ok=True)


def save_message(file_path: Path, user_id: int, username: str, text: str) -> None:
    """Append a timestamped message to the storage file.

    Format (one entry per block, separated by blank lines):
        [2026-02-19T14:30:00+00:00] user_id=123456 username=scott
        The actual message text goes here,
        and can span multiple lines.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    header = f"[{timestamp}] user_id={user_id} username={username}"

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write(text + "\n")
        f.write("\n")
