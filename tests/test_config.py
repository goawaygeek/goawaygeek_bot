import os
from unittest.mock import patch

import pytest

import config


def test_missing_bot_token():
    """validate_config exits when BOT_TOKEN is not set."""
    env = {"AUTHORIZED_USER_ID": "12345"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="BOT_TOKEN is not set"):
            config.validate_config()


def test_missing_authorized_user_id():
    """validate_config exits when AUTHORIZED_USER_ID is not set."""
    env = {"BOT_TOKEN": "fake-token"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="AUTHORIZED_USER_ID is not set"):
            config.validate_config()


def test_non_integer_authorized_user_id():
    """validate_config exits when AUTHORIZED_USER_ID is not a valid integer."""
    env = {"BOT_TOKEN": "fake-token", "AUTHORIZED_USER_ID": "not-a-number"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(SystemExit, match="must be an integer"):
            config.validate_config()


def test_valid_config():
    """validate_config sets module-level variables when all values are valid."""
    env = {
        "BOT_TOKEN": "fake-token-123",
        "AUTHORIZED_USER_ID": "99999",
    }
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert config.BOT_TOKEN == "fake-token-123"
        assert config.AUTHORIZED_USER_ID == 99999


def test_custom_messages_file():
    """validate_config respects a custom MESSAGES_FILE path."""
    env = {
        "BOT_TOKEN": "fake-token",
        "AUTHORIZED_USER_ID": "12345",
        "MESSAGES_FILE": "/tmp/custom.log",
    }
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert str(config.MESSAGES_FILE) == "/tmp/custom.log"


def test_default_messages_file():
    """validate_config uses default MESSAGES_FILE when not specified."""
    env = {
        "BOT_TOKEN": "fake-token",
        "AUTHORIZED_USER_ID": "12345",
    }
    with patch.dict(os.environ, env, clear=True):
        config.validate_config()
        assert str(config.MESSAGES_FILE) == "data/messages.log"
