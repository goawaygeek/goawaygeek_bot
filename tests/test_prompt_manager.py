"""Tests for PromptManager: template loading, user-override priority, and git operations."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from knowledge.prompt_manager import PromptManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    """Base prompts directory with a sample capture.md template."""
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "capture.md").write_text(
        "Base capture: $overview, types=$item_types", encoding="utf-8"
    )
    (d / "query.md").write_text(
        "Base query: $overview context=$context_items", encoding="utf-8"
    )
    return d


@pytest.fixture()
def user_dir(tmp_path: Path) -> Path:
    """User prompts directory (not a real git repo, just a directory)."""
    d = tmp_path / "user_prompts"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# load() — base-only
# ---------------------------------------------------------------------------


def test_load_from_base_dir(base_dir: Path) -> None:
    """load() renders a base template when no user_dir is configured."""
    pm = PromptManager(base_dir=base_dir)
    result = pm.load("capture", overview="my notes", item_types="note, link")
    assert "my notes" in result
    assert "note, link" in result


def test_load_substitutes_all_variables(base_dir: Path) -> None:
    """load() substitutes every provided variable."""
    pm = PromptManager(base_dir=base_dir)
    result = pm.load("query", overview="OV", context_items="CTX")
    assert "OV" in result
    assert "CTX" in result


def test_load_missing_prompt_raises(base_dir: Path) -> None:
    """load() raises FileNotFoundError for an unknown prompt name."""
    pm = PromptManager(base_dir=base_dir)
    with pytest.raises(FileNotFoundError):
        pm.load("nonexistent")


# ---------------------------------------------------------------------------
# load() — user override
# ---------------------------------------------------------------------------


def test_load_prefers_user_dir_over_base(base_dir: Path, user_dir: Path) -> None:
    """User file takes priority over the base file when both exist."""
    (user_dir / "capture.md").write_text(
        "User capture: $overview", encoding="utf-8"
    )
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)
    result = pm.load("capture", overview="OVERRIDE")
    assert result == "User capture: OVERRIDE"


def test_load_falls_back_to_base_when_user_file_absent(
    base_dir: Path, user_dir: Path
) -> None:
    """load() uses the base file when user_dir exists but lacks that prompt."""
    # user_dir has no capture.md
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)
    result = pm.load("capture", overview="fallback", item_types="note")
    assert "Base capture" in result
    assert "fallback" in result


def test_load_safe_substitute_leaves_missing_vars(base_dir: Path) -> None:
    """safe_substitute leaves unresolved $variables intact (no KeyError)."""
    pm = PromptManager(base_dir=base_dir)
    # Don't pass item_types — safe_substitute should leave $item_types in place
    result = pm.load("capture", overview="X")
    assert "X" in result
    assert "$item_types" in result  # not substituted, not an error


# ---------------------------------------------------------------------------
# update() — git operations
# ---------------------------------------------------------------------------


def _make_ok(stdout: str = "") -> MagicMock:
    """Helper: subprocess.run return value with returncode=0."""
    m = MagicMock()
    m.returncode = 0
    m.stdout = stdout
    m.stderr = ""
    return m


def test_update_raises_without_user_dir(base_dir: Path) -> None:
    """update() raises RuntimeError when user_dir is not configured."""
    pm = PromptManager(base_dir=base_dir)
    with pytest.raises(RuntimeError, match="PROMPTS_USER_DIR"):
        pm.update("capture", "new text")


def test_update_writes_file_and_calls_git(base_dir: Path, user_dir: Path) -> None:
    """update() writes the file and calls git add → commit → push in order."""
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)

    with patch("knowledge.prompt_manager.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_ok(),           # git add
            _make_ok(),           # git commit
            _make_ok("abc1234"),  # git rev-parse
            _make_ok(),           # git push
        ]
        commit_hash = pm.update("capture", "new prompt text")

    written = (user_dir / "capture.md").read_text(encoding="utf-8")
    assert written == "new prompt text"
    assert commit_hash == "abc1234"

    calls = mock_run.call_args_list
    assert calls[0] == call(
        ["git", "-C", str(user_dir), "add", "capture.md"],
        capture_output=True,
        text=True,
    )
    assert calls[1][0][0][:4] == ["git", "-C", str(user_dir), "commit"]
    assert calls[2] == call(
        ["git", "-C", str(user_dir), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    assert calls[3][0][0][:3] == ["git", "-C", str(user_dir)]
    assert "push" in calls[3][0][0]


def test_update_raises_on_git_add_failure(base_dir: Path, user_dir: Path) -> None:
    """update() raises RuntimeError when git add fails."""
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)
    fail = MagicMock()
    fail.returncode = 1
    fail.stderr = "not a git repo"

    with patch("knowledge.prompt_manager.subprocess.run", return_value=fail):
        with pytest.raises(RuntimeError, match="git add failed"):
            pm.update("capture", "text")


def test_update_raises_on_git_commit_failure(base_dir: Path, user_dir: Path) -> None:
    """update() raises RuntimeError when git commit fails."""
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)
    fail = MagicMock()
    fail.returncode = 1
    fail.stderr = "nothing to commit"

    with patch("knowledge.prompt_manager.subprocess.run") as mock_run:
        mock_run.side_effect = [_make_ok(), fail]
        with pytest.raises(RuntimeError, match="git commit failed"):
            pm.update("capture", "text")


def test_update_warns_but_does_not_raise_on_push_failure(
    base_dir: Path, user_dir: Path
) -> None:
    """update() logs a warning but returns the commit hash even if push fails."""
    pm = PromptManager(base_dir=base_dir, user_dir=user_dir)
    push_fail = MagicMock()
    push_fail.returncode = 1
    push_fail.stderr = "remote: error"

    with patch("knowledge.prompt_manager.subprocess.run") as mock_run:
        mock_run.side_effect = [
            _make_ok(),          # add
            _make_ok(),          # commit
            _make_ok("deadbeef"),  # rev-parse
            push_fail,           # push (fails)
        ]
        result = pm.update("capture", "text")

    assert result == "deadbeef"


# ---------------------------------------------------------------------------
# _sync_user_repo — clone vs pull
# ---------------------------------------------------------------------------


def test_sync_clones_when_no_git_dir(tmp_path: Path) -> None:
    """_sync_user_repo runs git clone when .git does not exist."""
    base_dir = tmp_path / "prompts"
    base_dir.mkdir()
    user_dir = tmp_path / "user_prompts"  # does not exist yet

    with patch("knowledge.prompt_manager.subprocess.run") as mock_run:
        mock_run.return_value = _make_ok()
        PromptManager(
            base_dir=base_dir,
            user_dir=user_dir,
            repo_url="git@github.com:example/prompts.git",
        )

    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert "clone" in args


def test_sync_pulls_when_git_dir_exists(tmp_path: Path) -> None:
    """_sync_user_repo runs git pull when .git already exists."""
    base_dir = tmp_path / "prompts"
    base_dir.mkdir()
    user_dir = tmp_path / "user_prompts"
    user_dir.mkdir()
    (user_dir / ".git").mkdir()  # simulate existing clone

    with patch("knowledge.prompt_manager.subprocess.run") as mock_run:
        mock_run.return_value = _make_ok()
        PromptManager(
            base_dir=base_dir,
            user_dir=user_dir,
            repo_url="git@github.com:example/prompts.git",
        )

    args = mock_run.call_args[0][0]
    assert args[0] == "git"
    assert "pull" in args
