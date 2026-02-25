"""Tests for knowledge.prompts."""

from knowledge.models import ItemType
from knowledge.prompts import (
    capture_system_prompt,
    overview_refresh_prompt,
    query_system_prompt,
)


def test_capture_prompt_includes_overview():
    """The capture prompt includes the provided overview text."""
    prompt = capture_system_prompt("## Projects\n- My cool project")
    assert "## Projects" in prompt
    assert "My cool project" in prompt


def test_capture_prompt_handles_empty_overview():
    """Empty overview produces a helpful placeholder."""
    prompt = capture_system_prompt("")
    assert "No overview yet" in prompt


def test_capture_prompt_requests_json():
    """The capture prompt instructs JSON output format."""
    prompt = capture_system_prompt("")
    assert "JSON" in prompt
    assert "item_type" in prompt
    assert "tags" in prompt
    assert "summary" in prompt
    assert "response" in prompt
    assert "overview_update" in prompt


def test_capture_prompt_lists_all_item_types():
    """All ItemType enum values appear in the capture prompt."""
    prompt = capture_system_prompt("")
    for t in ItemType:
        assert t.value in prompt, f"Missing item type: {t.value}"


def test_query_prompt_includes_overview_and_context():
    """The query prompt includes both overview and search context."""
    prompt = query_system_prompt(
        overview="## Active Projects\n- Bot",
        context_items="[note] A saved note about bots",
    )
    assert "Active Projects" in prompt
    assert "A saved note about bots" in prompt


def test_query_prompt_handles_empty_inputs():
    """Query prompt works with empty overview and context."""
    prompt = query_system_prompt(overview="", context_items="")
    assert "No overview yet" in prompt
    assert "No matching items" in prompt


def test_overview_refresh_prompt_includes_items():
    """The refresh prompt includes recent items."""
    prompt = overview_refresh_prompt(
        overview="## Old overview",
        recent_items="[link] Some saved link\n[note] A note",
    )
    assert "Old overview" in prompt
    assert "Some saved link" in prompt
    assert "A note" in prompt


def test_overview_refresh_prompt_handles_empty():
    """Refresh prompt works with no existing overview or items."""
    prompt = overview_refresh_prompt(overview="", recent_items="")
    assert "No existing overview" in prompt
    assert "No items stored" in prompt


def test_all_prompts_are_nonempty():
    """All prompt functions return non-empty strings."""
    assert len(capture_system_prompt("")) > 100
    assert len(query_system_prompt("", "")) > 50
    assert len(overview_refresh_prompt("", "")) > 50
