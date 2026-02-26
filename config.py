import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

ROOT: Path = Path(__file__).parent
DATA_DIR: Path = ROOT / "data"

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
AUTHORIZED_USER_ID: int = 0
MESSAGES_FILE: Path = Path(os.getenv("MESSAGES_FILE", "./data/messages.log"))
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
DB_PATH: Path = Path(os.getenv("DB_PATH", "./data/knowledge.db"))
CONVERSATION_LOG_DB_PATH: Path = Path(os.getenv("CONVERSATION_LOG_DB_PATH", "./data/conversations.db"))
OVERVIEW_MD_PATH: Path = Path(os.getenv("OVERVIEW_MD_PATH", "./data/overview.md"))

# Prompt management
PROMPTS_BASE_DIR: Path = ROOT / "prompts"
PROMPTS_USER_DIR: Path = DATA_DIR / "user_prompts"
PROMPTS_REPO_URL: Optional[str] = os.getenv("PROMPTS_REPO_URL") or None


def validate_config() -> None:
    """Validate that all required config values are present and valid.

    Exits with a clear error message if anything is missing or invalid.
    """
    global BOT_TOKEN, AUTHORIZED_USER_ID, MESSAGES_FILE, ANTHROPIC_API_KEY, LLM_MODEL, DB_PATH, CONVERSATION_LOG_DB_PATH, OVERVIEW_MD_PATH, PROMPTS_REPO_URL

    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    if not BOT_TOKEN:
        sys.exit("Error: BOT_TOKEN is not set in .env file.")

    raw_user_id = os.getenv("AUTHORIZED_USER_ID", "")
    if not raw_user_id:
        sys.exit("Error: AUTHORIZED_USER_ID is not set in .env file.")

    try:
        AUTHORIZED_USER_ID = int(raw_user_id)
    except ValueError:
        sys.exit(
            f"Error: AUTHORIZED_USER_ID must be an integer, got '{raw_user_id}'."
        )

    MESSAGES_FILE = Path(os.getenv("MESSAGES_FILE", "./data/messages.log"))

    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    if not ANTHROPIC_API_KEY:
        sys.exit("Error: ANTHROPIC_API_KEY is not set in .env file.")

    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")

    DB_PATH = Path(os.getenv("DB_PATH", "./data/knowledge.db"))

    CONVERSATION_LOG_DB_PATH = Path(os.getenv("CONVERSATION_LOG_DB_PATH", "./data/conversations.db"))
    OVERVIEW_MD_PATH = Path(os.getenv("OVERVIEW_MD_PATH", "./data/overview.md"))

    PROMPTS_REPO_URL = os.getenv("PROMPTS_REPO_URL") or None
