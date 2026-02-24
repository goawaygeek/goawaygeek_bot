import os
from unittest.mock import patch

import pytest

import config

# Base env with all required fields for tests that don't test missing fields
_VALID_ENV = {
    "BOT_TOKEN": "fake-token",
    "AUTHORIZED_USER_ID": "12345",
    "ANTHROPIC_API_KEY": "fake-api-key",
}


def test_missing_bot_token():
    """validate_config exits when BOT_TOKEN is not set."""
    env = {"AUTHORIZED_USER_ID": "12345", "ANTHROPIC_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="BOT_TOKEN is not set"):
            config.validate_config()


def test_missing_authorized_user_id():
    """validate_config exits when AUTHORIZED_USER_ID is not set."""
    env = {"BOT_TOKEN": "fake-token", "ANTHROPIC_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="AUTHORIZED_USER_ID is not set"):
            config.validate_config()


def test_non_integer_authorized_user_id():
    """validate_config exits when AUTHORIZED_USER_ID is not a valid integer."""
    env = {"BOT_TOKEN": "fake-token", "AUTHORIZED_USER_ID": "not-a-number", "ANTHROPIC_API_KEY": "key"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="must be an integer"):
            config.validate_config()


def test_missing_anthropic_api_key():
    """validate_config exits when ANTHROPIC_API_KEY is not set."""
    env = {"BOT_TOKEN": "fake-token", "AUTHORIZED_USER_ID": "12345"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY is not set"):
            config.validate_config()


def test_valid_config():
    """validate_config sets module-level variables when all values are valid."""
    env = {
        "BOT_TOKEN": "fake-token-123",
        "AUTHORIZED_USER_ID": "99999",
        "ANTHROPIC_API_KEY": "sk-ant-test",
    }
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert config.BOT_TOKEN == "fake-token-123"
        assert config.AUTHORIZED_USER_ID == 99999
        assert config.ANTHROPIC_API_KEY == "sk-ant-test"


def test_default_llm_model():
    """validate_config uses default LLM_MODEL when not specified."""
    with patch.dict(os.environ, _VALID_ENV, clear=True):
        config.validate_config()
        assert config.LLM_MODEL == "claude-sonnet-4-20250514"


def test_custom_llm_model():
    """validate_config respects a custom LLM_MODEL."""
    env = {**_VALID_ENV, "LLM_MODEL": "claude-haiku-4-5-20251001"}
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert config.LLM_MODEL == "claude-haiku-4-5-20251001"


def test_custom_messages_file():
    """validate_config respects a custom MESSAGES_FILE path."""
    env = {**_VALID_ENV, "MESSAGES_FILE": "/tmp/custom.log"}
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert str(config.MESSAGES_FILE) == "/tmp/custom.log"


def test_default_messages_file():
    """validate_config uses default MESSAGES_FILE when not specified."""
    with patch.dict(os.environ, _VALID_ENV, clear=True):
        config.validate_config()
        assert str(config.MESSAGES_FILE) == "data/messages.log"
