"""System prompts and templates for Knowledge Base LLM interactions.

All prompts instruct the LLM to return structured JSON so that
brain.py can parse the response deterministically.
"""

from knowledge.models import ItemType

# All valid item type values, for inclusion in prompts
_ITEM_TYPES = ", ".join(t.value for t in ItemType)


def capture_system_prompt(overview: str) -> str:
    """Build the system prompt for analyzing/capturing a new message.

    The prompt instructs the LLM to:
    1. Classify the message using the overview for context
    2. Generate relevant tags
    3. Summarize the content
    4. Compose a brief confirmation reply for the user
    5. Optionally update the rolling overview

    Args:
        overview: The current rolling overview text (may be empty).

    Returns:
        The complete system prompt string.
    """
    overview_section = overview if overview else "(No overview yet — this is a new knowledge base.)"

    return f"""\
You are a personal knowledge base assistant managing a user's "second brain."

You will receive a message the user sent via Telegram. Your job is to:
1. Understand what the user is telling you, using their knowledge base overview \
below for context
2. Classify the message as one of: {_ITEM_TYPES}
3. Generate 2-5 relevant lowercase tags
4. Write a 1-2 sentence summary
5. Write a short conversational reply confirming what you understood and stored
6. Decide whether the rolling overview needs updating — if this message changes \
the user's projects, interests, or priorities, provide the FULL updated overview \
text. Otherwise set overview_update to null. Most messages don't need an overview \
update.

## The user's current knowledge base overview:

{overview_section}

## Response format:
Respond ONLY with a JSON object. No markdown fences, no preamble, no explanation.

{{"item_type": "<{_ITEM_TYPES}>", "tags": ["tag1", "tag2"], \
"summary": "brief summary of what was captured", \
"response": "conversational reply to the user", \
"overview_update": "full updated overview text, or null if no update needed"}}"""


def query_system_prompt(overview: str, context_items: str) -> str:
    """Build the system prompt for answering a user question.

    Args:
        overview: The current rolling overview text.
        context_items: Formatted string of relevant knowledge items
                       found via search.

    Returns:
        The complete system prompt string.
    """
    overview_section = overview if overview else "(No overview yet.)"
    context_section = context_items if context_items else "(No matching items found.)"

    return f"""\
You are a personal knowledge base assistant. The user is asking a question \
about their stored knowledge.

## Knowledge base overview:

{overview_section}

## Relevant items from search:

{context_section}

Answer the user's question based on the overview and search results above. \
Be conversational and concise — this is a phone chat interface, not an essay. \
If you don't have enough information to answer, say so honestly."""


def overview_refresh_prompt(overview: str, recent_items: str) -> str:
    """Build the prompt for a deep overview refresh.

    Used for periodic full-overview regeneration from recent activity.

    Args:
        overview: The current rolling overview text.
        recent_items: Formatted string of recent knowledge items.

    Returns:
        The complete system prompt string.
    """
    overview_section = overview if overview else "(No existing overview.)"
    items_section = recent_items if recent_items else "(No items stored yet.)"

    return f"""\
You are a personal knowledge base assistant. Review the current overview and \
recent items below. Regenerate the overview to reflect the current state of \
the user's projects, interests, and priorities. Keep it concise — aim for a \
document that fits on one screen.

## Current overview:

{overview_section}

## Recent items (newest first):

{items_section}

Respond with ONLY the new overview text. No JSON, no preamble. Use markdown \
headings and bullet points."""
