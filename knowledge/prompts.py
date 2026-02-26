"""System prompt builders — thin wrappers that delegate to PromptManager.

All prompts are defined in prompts/*.md template files.
User-specific overrides live in data/user_prompts/*.md (git-versioned).
"""

from knowledge.models import ItemType
from knowledge.prompt_manager import PromptManager

# All valid item type values, passed to templates as $item_types
_ITEM_TYPES = ", ".join(t.value for t in ItemType)


def capture_system_prompt(pm: PromptManager, overview: str) -> str:
    """Build the capture system prompt from template."""
    overview_text = overview if overview else "(No overview yet — this is a new knowledge base.)"
    return pm.load("capture", overview=overview_text, item_types=_ITEM_TYPES)


def query_system_prompt(pm: PromptManager, overview: str, context_items: str) -> str:
    """Build the query system prompt from template."""
    overview_text = overview if overview else "(No overview yet.)"
    context_text = context_items if context_items else "(No matching items found.)"
    return pm.load("query", overview=overview_text, context_items=context_text)


def overview_refresh_prompt(pm: PromptManager, overview: str, recent_items: str) -> str:
    """Build the overview refresh prompt from template."""
    overview_text = overview if overview else "(No existing overview.)"
    items_text = recent_items if recent_items else "(No items stored yet.)"
    return pm.load("overview_refresh", overview=overview_text, recent_items=items_text)


def capability_gap_prompt(pm: PromptManager) -> str:
    """Build the capability gap detection prompt from template."""
    return pm.load("capability_gap")
