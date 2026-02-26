"""Knowledge Base orchestrator — the single API that bot.py calls.

Wires together the LLM client, SQLite store, URL fetcher, and PromptManager.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from knowledge.conversation_log import ConversationLogProtocol
from knowledge.fetcher import extract_urls, fetch_url_content
from knowledge.llm import LLMProtocol
from knowledge.models import (
    AnalysisResult,
    ConversationRecord,
    ItemType,
    KnowledgeItem,
    SearchResult,
)
from knowledge.prompt_manager import PromptManager
from knowledge.prompts import (
    capture_system_prompt,
    capability_gap_prompt,
    overview_refresh_prompt,
    query_system_prompt,
)
from knowledge.store import StoreProtocol

# Default base prompts directory, relative to this file
_DEFAULT_PROMPTS_BASE = Path(__file__).parent.parent / "prompts"

logger = logging.getLogger(__name__)

# Phrases in an answer that suggest the bot lacks the capability to respond
_INSUFFICIENT_CAPABILITY_SIGNALS = [
    "i don't have",
    "i do not have",
    "no information",
    "not stored",
    "can't find",
    "cannot find",
    "no data",
    "not tracked",
    "don't track",
    "do not track",
    "no record",
    "haven't stored",
    "have not stored",
    "isn't tracked",
    "is not tracked",
]


class KnowledgeBrain:
    """Orchestrator: wires together LLM, store, fetcher, and prompts.

    This is the single API that bot.py calls. All knowledge base
    operations go through this class.
    """

    def __init__(
        self,
        llm: LLMProtocol,
        store: StoreProtocol,
        conversation_log: Optional[ConversationLogProtocol] = None,
        prompt_manager: Optional[PromptManager] = None,
    ):
        self.llm = llm
        self.store = store
        self.conversation_log = conversation_log
        # Auto-create a base-only PromptManager when none is supplied
        if prompt_manager is None and _DEFAULT_PROMPTS_BASE.exists():
            prompt_manager = PromptManager(base_dir=_DEFAULT_PROMPTS_BASE)
        self.pm = prompt_manager

    def _log_conversation(
        self,
        interaction_type: str,
        user_message: str,
        system_prompt: str,
        llm_response: str,
        parsed_type: Optional[str] = None,
        parsed_tags: Optional[List[str]] = None,
        parsed_summary: Optional[str] = None,
    ) -> None:
        """Log an LLM interaction if conversation logging is enabled."""
        if self.conversation_log is None:
            return
        try:
            record = ConversationRecord(
                interaction_type=interaction_type,
                user_message=user_message,
                system_prompt=system_prompt,
                llm_response=llm_response,
                parsed_type=parsed_type,
                parsed_tags=json.dumps(parsed_tags) if parsed_tags else None,
                parsed_summary=parsed_summary,
            )
            self.conversation_log.log(record)
        except Exception:
            logger.warning("Failed to log conversation", exc_info=True)

    async def capture(self, text: str) -> Tuple[str, bool]:
        """Process an incoming message into the knowledge base.

        Steps:
        1. Detect URLs in text
        2. Fetch URL content if links found
        3. Load current rolling overview
        4. Send text + overview + URL content to LLM for analysis
        5. Parse structured JSON response
        6. Save KnowledgeItem to store
        7. Update overview if LLM provided an update
        8. Return (confirmation reply, capability_request flag)

        On LLM failure, falls back to saving as unclassified note.
        """
        # 1-2: URL detection and fetching
        urls = extract_urls(text)
        url_content = None  # type: Optional[str]
        if urls:
            url_content = await fetch_url_content(urls[0])

        # 3: Load overview
        overview = self.store.get_overview()

        # 4: Build message for LLM
        user_message = text
        if url_content:
            user_message += f"\n\n--- Fetched URL Content ---\n{url_content}"

        # 5: Call LLM for analysis
        system = capture_system_prompt(self.pm, overview)
        try:
            raw_response = await self.llm.analyze(user_message, system=system)
            analysis = AnalysisResult.from_llm_json(raw_response)
        except Exception:
            logger.warning("LLM analysis failed, saving as raw note", exc_info=True)
            return self._fallback_save(text, urls), False

        # Log the successful LLM interaction
        self._log_conversation(
            interaction_type="capture",
            user_message=user_message,
            system_prompt=system,
            llm_response=raw_response,
            parsed_type=analysis.item_type.value,
            parsed_tags=analysis.tags,
            parsed_summary=analysis.summary,
        )

        # 6: Save to store
        item = KnowledgeItem(
            content=text,
            item_type=analysis.item_type,
            tags=analysis.tags,
            summary=analysis.summary,
            source_url=urls[0] if urls else None,
            url_content=url_content,
        )
        self.store.save_item(item)

        # 6b: Save any individually extracted items (e.g. events from a calendar URL)
        if analysis.extracted_items:
            self._save_extracted_items(
                analysis.extracted_items,
                source_url=urls[0] if urls else None,
                parent_tags=analysis.tags,
            )

        # 7: Update overview if LLM says so
        if analysis.overview_update:
            self.store.save_overview(analysis.overview_update)

        # 8: Return reply and capability_request flag
        return analysis.response, analysis.capability_request

    def _fallback_save(self, text: str, urls: List[str]) -> str:
        """Save message as unclassified note when LLM is unavailable."""
        item = KnowledgeItem(
            content=text,
            item_type=ItemType.NOTE,
            tags=[],
            summary="",
            source_url=urls[0] if urls else None,
        )
        self.store.save_item(item)
        return "Saved to knowledge base."

    def _save_extracted_items(
        self,
        extracted_items: List[Dict],
        source_url: Optional[str],
        parent_tags: List[str],
    ) -> None:
        """Save individually extracted items (e.g. events from a list URL)."""
        for raw in extracted_items:
            summary = raw.get("summary", "")
            if not summary:
                continue
            # Merge parent tags with item-specific tags, deduplicated
            item_tags = list(dict.fromkeys(parent_tags + raw.get("tags", [])))
            item = KnowledgeItem(
                content=summary,
                item_type=ItemType.REFERENCE,
                tags=item_tags,
                summary=summary,
                source_url=source_url,
            )
            self.store.save_item(item)

    async def query(self, question: str) -> str:
        """Answer a question using the knowledge base.

        Steps:
        1. Load overview
        2. Search store via FTS5
        3. Format results as context
        4. Send question + overview + context to LLM
        5. Return the answer
        """
        overview = self.store.get_overview()
        results = self.store.search(question, limit=10)
        context = self._format_search_context(results)

        system = query_system_prompt(self.pm, overview, context)
        try:
            answer = await self.llm.analyze(question, system=system)
            self._log_conversation(
                interaction_type="query",
                user_message=question,
                system_prompt=system,
                llm_response=answer,
            )
            return answer
        except Exception:
            logger.warning("LLM query failed", exc_info=True)
            if results:
                return self._format_plain_results(results)
            return "I couldn't process that query right now."

    async def check_capability_gap(
        self, question: str, answer: str
    ) -> Optional[Dict]:
        """Check if an answer signals a capability gap and return a gap proposal.

        Only triggers an extra LLM call when the answer contains phrases
        indicating the bot lacks the capability (cheap keyword check first).

        Args:
            question: The original user question.
            answer: The bot's answer to that question.

        Returns:
            A dict with gap fields (can_answer, gap_description, proposal,
            prompt_name, prompt_update), or None if no gap detected.
        """
        if self.pm is None:
            return None
        if not self._signals_insufficient_capability(answer):
            return None

        system = capability_gap_prompt(self.pm)
        user_msg = f"User asked: {question}\n\nBot answered: {answer}"
        try:
            raw = await self.llm.analyze(user_msg, system=system)
            data = json.loads(raw)
            if not data.get("can_answer", True):
                return data
        except Exception:
            logger.warning("Capability gap detection failed", exc_info=True)
        return None

    async def evolve_prompt(self, name: str, new_text: str) -> str:
        """Write an updated prompt and push it to the user's repo.

        Args:
            name: Prompt name without extension (e.g., "query").
            new_text: Full new prompt template text.

        Returns:
            Human-readable confirmation message with commit hash.
        """
        if self.pm is None:
            return "Prompt evolution not available — no user prompts directory configured."
        try:
            commit_hash = self.pm.update(name, new_text)
            return f"Prompt '{name}' updated and pushed. Commit: {commit_hash}"
        except Exception as e:
            logger.warning("Prompt evolution failed: %s", e)
            return f"Failed to update prompt '{name}': {e}"

    async def get_overview(self) -> str:
        """Return the current rolling overview."""
        overview = self.store.get_overview()
        if not overview:
            return "No overview yet. Send me some messages first!"
        return overview

    async def refresh_overview(self) -> str:
        """Trigger a deep LLM-powered overview refresh."""
        overview = self.store.get_overview()
        recent = self.store.recent(limit=50)
        items_text = self._format_items_for_prompt(recent)

        system = overview_refresh_prompt(self.pm, overview, items_text)
        try:
            new_overview = await self.llm.analyze(
                "Please regenerate the rolling overview.",
                system=system,
            )
            self._log_conversation(
                interaction_type="overview_refresh",
                user_message="Please regenerate the rolling overview.",
                system_prompt=system,
                llm_response=new_overview,
            )
            self.store.save_overview(new_overview)
            return "Overview refreshed."
        except Exception:
            logger.warning("Overview refresh failed", exc_info=True)
            return "Couldn't refresh the overview right now."

    def recent(self, limit: int = 10) -> List[KnowledgeItem]:
        """Return recent knowledge items."""
        return self.store.recent(limit=limit)

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Search the knowledge base."""
        return self.store.search(query, limit=limit)

    def _signals_insufficient_capability(self, answer: str) -> bool:
        """Return True if the answer text suggests a capability gap."""
        lower = answer.lower()
        return any(signal in lower for signal in _INSUFFICIENT_CAPABILITY_SIGNALS)

    def _format_search_context(self, results: List[SearchResult]) -> str:
        """Format search results as context text for the LLM."""
        if not results:
            return ""
        lines = []
        for r in results:
            tags = ", ".join(r.item.tags) if r.item.tags else "no tags"
            lines.append(
                f"[{r.item.item_type.value}] {r.item.summary or r.item.content[:100]}\n"
                f"  Tags: {tags}"
            )
        return "\n\n".join(lines)

    def _format_plain_results(self, results: List[SearchResult]) -> str:
        """Format search results as plain text for direct user display."""
        lines = []
        for r in results[:5]:
            lines.append(
                f"[{r.item.item_type.value}] "
                f"{r.item.summary or r.item.content[:80]}"
            )
        return "\n\n".join(lines)

    def _format_items_for_prompt(self, items: List[KnowledgeItem]) -> str:
        """Format knowledge items as text for inclusion in prompts."""
        if not items:
            return ""
        lines = []
        for item in items:
            tags = ", ".join(item.tags) if item.tags else "no tags"
            lines.append(
                f"[{item.item_type.value}] {item.summary or item.content[:100]}\n"
                f"  Tags: {tags}\n"
                f"  Created: {item.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
        return "\n\n".join(lines)
