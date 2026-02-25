"""Knowledge Base orchestrator — the single API that bot.py calls.

Wires together the LLM client, SQLite store, and URL fetcher.
"""

import json
import logging
from typing import List, Optional

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
from knowledge.prompts import (
    capture_system_prompt,
    overview_refresh_prompt,
    query_system_prompt,
)
from knowledge.store import StoreProtocol

logger = logging.getLogger(__name__)


class KnowledgeBrain:
    """Orchestrator: wires together LLM, store, and fetcher.

    This is the single API that bot.py calls. All knowledge base
    operations go through this class.
    """

    def __init__(
        self,
        llm: LLMProtocol,
        store: StoreProtocol,
        conversation_log: Optional[ConversationLogProtocol] = None,
    ):
        self.llm = llm
        self.store = store
        self.conversation_log = conversation_log

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

    async def capture(self, text: str) -> str:
        """Process an incoming message into the knowledge base.

        Steps:
        1. Detect URLs in text
        2. Fetch URL content if links found
        3. Load current rolling overview
        4. Send text + overview + URL content to LLM for analysis
        5. Parse structured JSON response
        6. Save KnowledgeItem to store
        7. Update overview if LLM provided an update
        8. Return the confirmation reply

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
        system = capture_system_prompt(overview)
        try:
            raw_response = await self.llm.analyze(user_message, system=system)
            analysis = AnalysisResult.from_llm_json(raw_response)
        except Exception:
            logger.warning("LLM analysis failed, saving as raw note", exc_info=True)
            return self._fallback_save(text, urls)

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

        # 7: Update overview if LLM says so
        if analysis.overview_update:
            self.store.save_overview(analysis.overview_update)

        # 8: Return reply
        return analysis.response

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

        system = query_system_prompt(overview, context)
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

        system = overview_refresh_prompt(overview, items_text)
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
