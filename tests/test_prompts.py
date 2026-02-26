"""Tests for knowledge.prompts — verifies templates render correctly."""

from pathlib import Path

import pytest

from knowledge.models import ItemType
from knowledge.prompt_manager import PromptManager
from knowledge.prompts import (
    capture_system_prompt,
    overview_refresh_prompt,
    query_system_prompt,
)

# Point at the actual base prompts directory so tests use real templates
_PROMPTS_BASE = Path(__file__).parent.parent / "prompts"


@pytest.fixture()
def pm() -> PromptManager:
    return PromptManager(base_dir=_PROMPTS_BASE)


def test_capture_prompt_includes_overview(pm: PromptManager):
    """The capture prompt includes the provided overview text."""
    prompt = capture_system_prompt(pm, "## Projects\n- My cool project")
    assert "## Projects" in prompt
    assert "My cool project" in prompt


def test_capture_prompt_handles_empty_overview(pm: PromptManager):
    """Empty overview produces a helpful placeholder."""
    prompt = capture_system_prompt(pm, "")
    assert "No overview yet" in prompt


def test_capture_prompt_requests_json(pm: PromptManager):
    """The capture prompt instructs JSON output format."""
    prompt = capture_system_prompt(pm, "")
    assert "JSON" in prompt
    assert "item_type" in prompt
    assert "tags" in prompt
    assert "summary" in prompt
    assert "response" in prompt
    assert "overview_update" in prompt


def test_capture_prompt_lists_all_item_types(pm: PromptManager):
    """All ItemType enum values appear in the capture prompt."""
    prompt = capture_system_prompt(pm, "")
    for t in ItemType:
        assert t.value in prompt, f"Missing item type: {t.value}"


def test_query_prompt_includes_overview_and_context(pm: PromptManager):
    """The query prompt includes both overview and search context."""
    prompt = query_system_prompt(
        pm,
        overview="## Active Projects\n- Bot",
        context_items="[note] A saved note about bots",
    )
    assert "Active Projects" in prompt
    assert "A saved note about bots" in prompt


def test_query_prompt_handles_empty_inputs(pm: PromptManager):
    """Query prompt works with empty overview and context."""
    prompt = query_system_prompt(pm, overview="", context_items="")
    assert "No overview yet" in prompt
    assert "No matching items" in prompt


def test_overview_refresh_prompt_includes_items(pm: PromptManager):
    """The refresh prompt includes recent items."""
    prompt = overview_refresh_prompt(
        pm,
        overview="## Old overview",
        recent_items="[link] Some saved link\n[note] A note",
    )
    assert "Old overview" in prompt
    assert "Some saved link" in prompt
    assert "A note" in prompt


def test_overview_refresh_prompt_handles_empty(pm: PromptManager):
    """Refresh prompt works with no existing overview or items."""
    prompt = overview_refresh_prompt(pm, overview="", recent_items="")
    assert "No existing overview" in prompt
    assert "No items stored" in prompt


def test_all_prompts_are_nonempty(pm: PromptManager):
    """All prompt functions return non-empty strings."""
    assert len(capture_system_prompt(pm, "")) > 100
    assert len(query_system_prompt(pm, "", "")) > 50
    assert len(overview_refresh_prompt(pm, "", "")) > 50
