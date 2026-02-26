"""Tests for knowledge.brain."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge.brain import KnowledgeBrain
from knowledge.models import ItemType, KnowledgeItem, SearchResult


def _make_mock_store(overview: str = "Current overview."):
    """Create a mock store with sensible defaults."""
    store = MagicMock()
    store.get_overview.return_value = overview
    store.save_item.return_value = 1
    store.search.return_value = []
    store.recent.return_value = []
    store.count.return_value = 0
    return store


def _make_mock_llm(analysis_json: str = None):
    """Create a mock LLM that returns the given JSON from analyze()."""
    if analysis_json is None:
        analysis_json = json.dumps({
            "item_type": "note",
            "tags": ["test"],
            "summary": "A test note",
            "response": "Got it! Saved as a note.",
            "overview_update": None,
        })
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value=analysis_json)
    llm.chat = AsyncMock(return_value="chat response")
    return llm


SAMPLE_LINK_ANALYSIS = json.dumps({
    "item_type": "link",
    "tags": ["eink", "hardware"],
    "summary": "E-ink display controller for Raspberry Pi",
    "response": "Saved! Filed under your eink project.",
    "overview_update": "## Projects\n- eink book — found display controller",
})

SAMPLE_LIST_URL_ANALYSIS = json.dumps({
    "item_type": "link",
    "tags": ["grants", "nsw", "calendar"],
    "summary": "NSW Create funding calendar — 3 grants listed",
    "response": "Saved the funding calendar and extracted 3 individual grants as searchable items.",
    "overview_update": None,
    "capability_request": False,
    "extracted_items": [
        {"summary": "Quick Response Grant — Opens 1 Mar 2025, Closes 15 Mar 2025", "tags": ["quick-response", "deadline"]},
        {"summary": "Regional Arts Fund — Opens 1 Apr 2025, Closes 30 Apr 2025", "tags": ["regional", "deadline"]},
        {"summary": "Infrastructure Grant — Opens 1 May 2025, Closes 31 May 2025", "tags": ["infrastructure", "deadline"]},
    ],
})


# --- capture() tests ---


@pytest.mark.asyncio
async def test_capture_calls_llm_with_overview():
    """capture() includes the overview in the system prompt."""
    store = _make_mock_store(overview="## My Projects\n- Bot")
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("a note about something")

    call_args = llm.analyze.call_args
    system_prompt = call_args.kwargs.get("system") or call_args[1]
    assert "My Projects" in system_prompt


@pytest.mark.asyncio
async def test_capture_saves_item_to_store():
    """capture() saves a KnowledgeItem to the store."""
    store = _make_mock_store()
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("remember this idea")

    store.save_item.assert_called_once()
    saved_item = store.save_item.call_args[0][0]
    assert isinstance(saved_item, KnowledgeItem)
    assert saved_item.content == "remember this idea"
    assert saved_item.item_type == ItemType.NOTE
    assert saved_item.tags == ["test"]


@pytest.mark.asyncio
async def test_capture_returns_llm_response():
    """capture() returns the response text from the LLM analysis."""
    store = _make_mock_store()
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    reply, capability_request = await brain.capture("test message")

    assert reply == "Got it! Saved as a note."
    assert capability_request is False


@pytest.mark.asyncio
@patch("knowledge.brain.fetch_url_content", new_callable=AsyncMock)
@patch("knowledge.brain.extract_urls")
async def test_capture_detects_and_fetches_url(mock_extract, mock_fetch):
    """When message contains a URL, fetch its content and include in LLM call."""
    mock_extract.return_value = ["https://example.com/article"]
    mock_fetch.return_value = "Article title\n\nArticle body text"

    store = _make_mock_store()
    llm = _make_mock_llm(SAMPLE_LINK_ANALYSIS)
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("check this out https://example.com/article")

    # URL was fetched
    mock_fetch.assert_called_once_with("https://example.com/article")

    # LLM received the fetched content
    user_message = llm.analyze.call_args[0][0]
    assert "Article body text" in user_message
    assert "Fetched URL Content" in user_message

    # Item saved with source_url and url_content
    saved_item = store.save_item.call_args[0][0]
    assert saved_item.source_url == "https://example.com/article"
    assert saved_item.url_content == "Article title\n\nArticle body text"


@pytest.mark.asyncio
@patch("knowledge.brain.extract_urls")
async def test_capture_no_url_skips_fetch(mock_extract):
    """Plain text message does not trigger URL fetching."""
    mock_extract.return_value = []

    store = _make_mock_store()
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("just a thought")

    # LLM message should NOT contain fetched content section
    user_message = llm.analyze.call_args[0][0]
    assert "Fetched URL Content" not in user_message


@pytest.mark.asyncio
async def test_capture_updates_overview_when_llm_says_so():
    """When LLM returns overview_update, it gets saved."""
    store = _make_mock_store()
    llm = _make_mock_llm(SAMPLE_LINK_ANALYSIS)
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("important project update")

    store.save_overview.assert_called_once_with(
        "## Projects\n- eink book — found display controller"
    )


@pytest.mark.asyncio
async def test_capture_skips_overview_when_null():
    """When LLM returns overview_update=null, overview is not updated."""
    store = _make_mock_store()
    llm = _make_mock_llm()  # default has overview_update=None
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("minor note")

    store.save_overview.assert_not_called()


@pytest.mark.asyncio
async def test_capture_saves_extracted_items():
    """When LLM returns extracted_items, each is saved as a REFERENCE item."""
    store = _make_mock_store()
    llm = _make_mock_llm(SAMPLE_LIST_URL_ANALYSIS)
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("https://example.com/grants-calendar")

    # save_item called once for the parent link + 3 extracted items = 4 total
    assert store.save_item.call_count == 4

    # Check all extracted items are REFERENCE type with source_url
    calls = store.save_item.call_args_list
    extracted_calls = calls[1:]  # skip the parent item
    for call in extracted_calls:
        item = call[0][0]
        assert item.item_type == ItemType.REFERENCE

    # Check tag merging: parent tags + item-specific tags
    first_extracted = extracted_calls[0][0][0]
    assert "grants" in first_extracted.tags       # from parent
    assert "quick-response" in first_extracted.tags  # from extracted item


@pytest.mark.asyncio
async def test_capture_no_extracted_items_when_empty():
    """When LLM returns extracted_items=[], only the parent item is saved."""
    store = _make_mock_store()
    llm = _make_mock_llm()  # default has extracted_items=[]
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.capture("just a note")

    store.save_item.assert_called_once()


@pytest.mark.asyncio
async def test_capture_fallback_on_llm_error():
    """When LLM raises, message is saved as a plain NOTE."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(side_effect=RuntimeError("API down"))
    brain = KnowledgeBrain(llm=llm, store=store)

    reply, capability_request = await brain.capture("save this anyway")

    assert reply == "Saved to knowledge base."
    assert capability_request is False
    saved_item = store.save_item.call_args[0][0]
    assert saved_item.item_type == ItemType.NOTE
    assert saved_item.tags == []


@pytest.mark.asyncio
async def test_capture_fallback_on_json_parse_error():
    """When LLM returns invalid JSON, message is saved as a plain NOTE."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="This is not valid JSON at all")
    brain = KnowledgeBrain(llm=llm, store=store)

    reply, capability_request = await brain.capture("save this too")

    assert reply == "Saved to knowledge base."
    assert capability_request is False
    saved_item = store.save_item.call_args[0][0]
    assert saved_item.item_type == ItemType.NOTE


# --- query() tests ---


@pytest.mark.asyncio
async def test_query_searches_store():
    """query() calls store.search with the question."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="Here's what I found...")
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.query("what projects am I working on?")

    store.search.assert_called_once_with("what projects am I working on?", limit=10)


@pytest.mark.asyncio
async def test_query_sends_results_to_llm():
    """query() includes search results in the LLM system prompt."""
    item = KnowledgeItem(
        content="Bot project notes",
        item_type=ItemType.NOTE,
        tags=["bot"],
        summary="Notes about the bot project",
    )
    store = _make_mock_store()
    store.search.return_value = [SearchResult(item=item, rank=1.0, snippet="Bot")]

    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="You're working on a bot project.")
    brain = KnowledgeBrain(llm=llm, store=store)

    await brain.query("what am I working on?")

    system_prompt = llm.analyze.call_args.kwargs.get("system") or llm.analyze.call_args[1]
    assert "Notes about the bot project" in system_prompt


@pytest.mark.asyncio
async def test_query_returns_llm_answer():
    """query() returns the LLM's response."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="You have 3 active projects.")
    brain = KnowledgeBrain(llm=llm, store=store)

    answer = await brain.query("how many projects?")

    assert answer == "You have 3 active projects."


@pytest.mark.asyncio
async def test_query_fallback_on_llm_error_with_results():
    """When LLM fails but search has results, return formatted results."""
    item = KnowledgeItem(
        content="test",
        item_type=ItemType.NOTE,
        summary="A saved note",
    )
    store = _make_mock_store()
    store.search.return_value = [SearchResult(item=item)]

    llm = MagicMock()
    llm.analyze = AsyncMock(side_effect=RuntimeError("API down"))
    brain = KnowledgeBrain(llm=llm, store=store)

    answer = await brain.query("find something")

    assert "A saved note" in answer


@pytest.mark.asyncio
async def test_query_fallback_on_llm_error_no_results():
    """When LLM fails and no search results, return error message."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(side_effect=RuntimeError("API down"))
    brain = KnowledgeBrain(llm=llm, store=store)

    answer = await brain.query("find something")

    assert "couldn't process" in answer


# --- overview tests ---


@pytest.mark.asyncio
async def test_get_overview_returns_store_overview():
    """get_overview() returns the overview from the store."""
    store = _make_mock_store(overview="## My overview")
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    overview = await brain.get_overview()

    assert overview == "## My overview"


@pytest.mark.asyncio
async def test_get_overview_empty_message():
    """get_overview() returns a helpful message when overview is empty."""
    store = _make_mock_store(overview="")
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    overview = await brain.get_overview()

    assert "No overview yet" in overview


@pytest.mark.asyncio
async def test_refresh_overview_calls_llm_and_saves():
    """refresh_overview() calls LLM and saves the new overview."""
    store = _make_mock_store(overview="old overview")
    store.recent.return_value = [
        KnowledgeItem(content="item1", item_type=ItemType.NOTE, summary="First item"),
    ]

    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="## Refreshed Overview\n- Updated")
    brain = KnowledgeBrain(llm=llm, store=store)

    result = await brain.refresh_overview()

    assert result == "Overview refreshed."
    store.save_overview.assert_called_once_with("## Refreshed Overview\n- Updated")


@pytest.mark.asyncio
async def test_refresh_overview_handles_llm_failure():
    """refresh_overview() returns error message when LLM fails."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(side_effect=RuntimeError("API down"))
    brain = KnowledgeBrain(llm=llm, store=store)

    result = await brain.refresh_overview()

    assert "Couldn't refresh" in result
    store.save_overview.assert_not_called()


# --- delegation tests ---


def test_recent_delegates_to_store():
    """recent() delegates to store.recent()."""
    item = KnowledgeItem(content="test", item_type=ItemType.NOTE)
    store = _make_mock_store()
    store.recent.return_value = [item]
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    items = brain.recent(limit=5)

    store.recent.assert_called_once_with(limit=5)
    assert items == [item]


def test_search_delegates_to_store():
    """search() delegates to store.search()."""
    store = _make_mock_store()
    store.search.return_value = []
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store)

    results = brain.search("test query", limit=3)

    store.search.assert_called_once_with("test query", limit=3)
    assert results == []


# --- conversation logging tests ---


def _make_mock_conversation_log():
    """Create a mock conversation log."""
    log = MagicMock()
    log.log.return_value = 1
    return log


@pytest.mark.asyncio
async def test_capture_logs_conversation():
    """capture() logs the LLM interaction when conversation_log is set."""
    store = _make_mock_store()
    llm = _make_mock_llm()
    conv_log = _make_mock_conversation_log()
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=conv_log)

    await brain.capture("remember to buy milk")

    conv_log.log.assert_called_once()
    record = conv_log.log.call_args[0][0]
    assert record.interaction_type == "capture"
    assert record.user_message == "remember to buy milk"
    assert record.system_prompt != ""
    assert record.llm_response != ""
    assert record.parsed_type == "note"
    assert record.parsed_tags == '["test"]'
    assert record.parsed_summary == "A test note"


@pytest.mark.asyncio
async def test_capture_no_log_when_none():
    """capture() works fine when conversation_log is None."""
    store = _make_mock_store()
    llm = _make_mock_llm()
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=None)

    reply, _ = await brain.capture("a note")

    assert reply == "Got it! Saved as a note."


@pytest.mark.asyncio
async def test_query_logs_conversation():
    """query() logs the LLM interaction."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="You have 3 projects.")
    conv_log = _make_mock_conversation_log()
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=conv_log)

    await brain.query("what am I working on?")

    conv_log.log.assert_called_once()
    record = conv_log.log.call_args[0][0]
    assert record.interaction_type == "query"
    assert record.user_message == "what am I working on?"
    assert record.llm_response == "You have 3 projects."
    assert record.parsed_type is None
    assert record.parsed_tags is None


@pytest.mark.asyncio
async def test_refresh_logs_conversation():
    """refresh_overview() logs the LLM interaction."""
    store = _make_mock_store()
    store.recent.return_value = []
    llm = MagicMock()
    llm.analyze = AsyncMock(return_value="## New Overview")
    conv_log = _make_mock_conversation_log()
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=conv_log)

    await brain.refresh_overview()

    conv_log.log.assert_called_once()
    record = conv_log.log.call_args[0][0]
    assert record.interaction_type == "overview_refresh"
    assert record.llm_response == "## New Overview"


@pytest.mark.asyncio
async def test_capture_no_log_on_llm_failure():
    """conversation_log.log() is NOT called when LLM fails."""
    store = _make_mock_store()
    llm = MagicMock()
    llm.analyze = AsyncMock(side_effect=RuntimeError("API down"))
    conv_log = _make_mock_conversation_log()
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=conv_log)

    await brain.capture("test")

    conv_log.log.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_log_failure_does_not_break_capture():
    """If conversation_log.log() raises, capture() still succeeds."""
    store = _make_mock_store()
    llm = _make_mock_llm()
    conv_log = MagicMock()
    conv_log.log.side_effect = RuntimeError("DB write failed")
    brain = KnowledgeBrain(llm=llm, store=store, conversation_log=conv_log)

    reply, _ = await brain.capture("save this")

    # Should still return the LLM response despite logging failure
    assert reply == "Got it! Saved as a note."
    store.save_item.assert_called_once()
