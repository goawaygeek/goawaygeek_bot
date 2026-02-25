"""Tests for knowledge.models."""

import json

import pytest

from knowledge.models import AnalysisResult, ItemType, KnowledgeItem, SearchResult


def test_item_type_enum_values():
    """All expected item types exist with lowercase string values."""
    assert ItemType.NOTE.value == "note"
    assert ItemType.IDEA.value == "idea"
    assert ItemType.TASK.value == "task"
    assert ItemType.REFERENCE.value == "reference"
    assert ItemType.LINK.value == "link"
    assert ItemType.JOURNAL.value == "journal"
    assert len(ItemType) == 6


def test_knowledge_item_defaults():
    """KnowledgeItem has sensible defaults for optional fields."""
    item = KnowledgeItem(content="hello", item_type=ItemType.NOTE)
    assert item.content == "hello"
    assert item.item_type == ItemType.NOTE
    assert item.tags == []
    assert item.summary == ""
    assert item.source_url is None
    assert item.url_content is None
    assert item.item_id is None
    assert item.created_at is not None


def test_knowledge_item_to_dict_roundtrip():
    """to_dict() then from_dict() produces an equivalent item."""
    item = KnowledgeItem(
        content="test note",
        item_type=ItemType.IDEA,
        tags=["python", "project"],
        summary="A test idea",
        source_url="https://example.com",
        url_content="Some page content",
        item_id=42,
    )
    d = item.to_dict()
    restored = KnowledgeItem.from_dict(d)

    assert restored.content == item.content
    assert restored.item_type == item.item_type
    assert restored.tags == item.tags
    assert restored.summary == item.summary
    assert restored.source_url == item.source_url
    assert restored.url_content == item.url_content
    assert restored.item_id == item.item_id
    assert restored.created_at == item.created_at


def test_analysis_result_from_llm_json_valid():
    """Parse well-formed JSON into AnalysisResult."""
    raw = json.dumps({
        "item_type": "link",
        "tags": ["eink", "hardware"],
        "summary": "E-ink display controller",
        "response": "Saved! Filed under your eink project.",
        "overview_update": "## Active Projects\n- eink book",
    })
    result = AnalysisResult.from_llm_json(raw)

    assert result.item_type == ItemType.LINK
    assert result.tags == ["eink", "hardware"]
    assert result.summary == "E-ink display controller"
    assert result.response == "Saved! Filed under your eink project."
    assert result.overview_update == "## Active Projects\n- eink book"


def test_analysis_result_from_llm_json_missing_optional():
    """overview_update is optional and defaults to None."""
    raw = json.dumps({
        "item_type": "note",
        "tags": ["misc"],
        "summary": "A quick note",
        "response": "Got it!",
    })
    result = AnalysisResult.from_llm_json(raw)

    assert result.overview_update is None


def test_analysis_result_from_llm_json_null_overview():
    """overview_update explicitly set to null parses as None."""
    raw = json.dumps({
        "item_type": "note",
        "tags": [],
        "summary": "A note",
        "response": "Saved.",
        "overview_update": None,
    })
    result = AnalysisResult.from_llm_json(raw)

    assert result.overview_update is None


def test_analysis_result_from_llm_json_with_code_fences():
    """Strip markdown code fences that Claude sometimes adds."""
    inner = json.dumps({
        "item_type": "task",
        "tags": ["todo"],
        "summary": "Buy milk",
        "response": "Added to your tasks!",
    })
    raw = f"```json\n{inner}\n```"
    result = AnalysisResult.from_llm_json(raw)

    assert result.item_type == ItemType.TASK
    assert result.tags == ["todo"]


def test_analysis_result_from_llm_json_invalid():
    """Raise ValueError on malformed JSON."""
    with pytest.raises(ValueError, match="invalid JSON"):
        AnalysisResult.from_llm_json("this is not json at all")


def test_analysis_result_from_llm_json_missing_required():
    """Raise ValueError when required fields are missing."""
    raw = json.dumps({"item_type": "note"})
    with pytest.raises(ValueError, match="missing required fields"):
        AnalysisResult.from_llm_json(raw)


def test_analysis_result_from_llm_json_invalid_item_type():
    """Raise ValueError for unrecognized item_type."""
    raw = json.dumps({
        "item_type": "banana",
        "tags": [],
        "summary": "x",
        "response": "y",
    })
    with pytest.raises(ValueError, match="Invalid item_type"):
        AnalysisResult.from_llm_json(raw)


def test_search_result_defaults():
    """SearchResult has sensible defaults for rank and snippet."""
    item = KnowledgeItem(content="test", item_type=ItemType.NOTE)
    sr = SearchResult(item=item)
    assert sr.rank == 0.0
    assert sr.snippet == ""
