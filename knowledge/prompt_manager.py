"""Prompt management: loads templates from file with optional git-versioned user overrides.

Templates use $variable_name substitution syntax (Python string.Template).
User prompt files in user_dir override base files in base_dir when present.
"""

import logging
import subprocess
from pathlib import Path
from string import Template
from typing import Optional

logger = logging.getLogger(__name__)


class PromptManager:
    """Loads system prompt templates from file, with optional user-override repo.

    Two-tier loading:
    - base_dir: prompts/ in the main repo (always present, version-controlled)
    - user_dir: data/user_prompts/ cloned from a private git repo (optional)

    When both exist, user_dir files take priority over base_dir files.

    Templates use Python string.Template syntax: $variable_name or ${variable_name}.
    """

    def __init__(
        self,
        base_dir: Path,
        user_dir: Optional[Path] = None,
        repo_url: Optional[str] = None,
    ):
        self.base_dir = base_dir
        self.user_dir = user_dir
        self.repo_url = repo_url
        if user_dir is not None and repo_url:
            self._sync_user_repo()

    def _sync_user_repo(self) -> None:
        """Clone the user repo on first run, or pull on subsequent runs."""
        git_dir = self.user_dir / ".git"
        if git_dir.exists():
            logger.info("Pulling user prompts repo at %s", self.user_dir)
            result = subprocess.run(
                ["git", "-C", str(self.user_dir), "pull"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning("git pull failed: %s", result.stderr.strip())
        else:
            logger.info("Cloning user prompts repo from %s", self.repo_url)
            self.user_dir.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", self.repo_url, str(self.user_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.warning("git clone failed: %s", result.stderr.strip())

    def load(self, name: str, **kwargs) -> str:
        """Load a prompt template and substitute variables.

        User file in user_dir takes priority over base file in base_dir.

        Args:
            name: Prompt name without extension (e.g., "capture").
            **kwargs: Template variable values for $variable_name substitution.

        Returns:
            The rendered prompt string.
        """
        template_text = self._read_template(name)
        return Template(template_text).safe_substitute(**kwargs)

    def _read_template(self, name: str) -> str:
        """Read raw template text, preferring user_dir over base_dir."""
        filename = f"{name}.md"
        if self.user_dir is not None:
            user_file = self.user_dir / filename
            if user_file.exists():
                logger.debug("Loading prompt '%s' from user_dir", name)
                return user_file.read_text(encoding="utf-8")
        base_file = self.base_dir / filename
        if not base_file.exists():
            raise FileNotFoundError(
                f"No prompt template found for '{name}' "
                f"(checked {self.user_dir} and {self.base_dir})"
            )
        return base_file.read_text(encoding="utf-8")

    def update(self, name: str, new_text: str) -> str:
        """Write new prompt text to user_dir and push to remote repo.

        Args:
            name: Prompt name without extension.
            new_text: New prompt template text.

        Returns:
            The short git commit hash.

        Raises:
            RuntimeError: If user_dir is not configured or git operations fail.
        """
        if self.user_dir is None:
            raise RuntimeError(
                "Cannot update prompts: PROMPTS_USER_DIR not configured."
            )

        self.user_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{name}.md"
        target = self.user_dir / filename
        target.write_text(new_text, encoding="utf-8")

        result = subprocess.run(
            ["git", "-C", str(self.user_dir), "add", filename],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git add failed: {result.stderr.strip()}")

        result = subprocess.run(
            ["git", "-C", str(self.user_dir), "commit", "-m", f"update {name} prompt"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git commit failed: {result.stderr.strip()}")

        hash_result = subprocess.run(
            ["git", "-C", str(self.user_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        commit_hash = hash_result.stdout.strip()

        result = subprocess.run(
            ["git", "-C", str(self.user_dir), "push"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "git push failed for prompt '%s': %s", name, result.stderr.strip()
            )

        logger.info("Prompt '%s' updated, commit %s", name, commit_hash)
        return commit_hash
