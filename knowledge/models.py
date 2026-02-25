"""Data models for the Personal Knowledge Base."""

import enum
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ItemType(enum.Enum):
    """Classification of a knowledge item."""

    NOTE = "note"
    IDEA = "idea"
    TASK = "task"
    REFERENCE = "reference"
    LINK = "link"
    JOURNAL = "journal"


@dataclass
class KnowledgeItem:
    """A single piece of captured knowledge."""

    content: str
    item_type: ItemType
    tags: List[str] = field(default_factory=list)
    summary: str = ""
    source_url: Optional[str] = None
    url_content: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    item_id: Optional[int] = None

    def to_dict(self) -> Dict:
        """Serialize to a dictionary."""
        return {
            "content": self.content,
            "item_type": self.item_type.value,
            "tags": self.tags,
            "summary": self.summary,
            "source_url": self.source_url,
            "url_content": self.url_content,
            "created_at": self.created_at.isoformat(),
            "item_id": self.item_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeItem":
        """Deserialize from a dictionary."""
        return cls(
            content=data["content"],
            item_type=ItemType(data["item_type"]),
            tags=data.get("tags", []),
            summary=data.get("summary", ""),
            source_url=data.get("source_url"),
            url_content=data.get("url_content"),
            created_at=datetime.fromisoformat(data["created_at"]),
            item_id=data.get("item_id"),
        )


@dataclass
class AnalysisResult:
    """Structured output from LLM analysis of a user message."""

    item_type: ItemType
    tags: List[str]
    summary: str
    response: str
    overview_update: Optional[str] = None

    @classmethod
    def from_llm_json(cls, raw: str) -> "AnalysisResult":
        """Parse the JSON string returned by the LLM.

        Handles markdown code fences and whitespace that Claude
        sometimes wraps around JSON output.

        Raises:
            ValueError: If the JSON is malformed or missing required fields.
        """
        cleaned = raw.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first line (```json or ```) and last line (```)
            end = len(lines) - 1
            while end > 0 and not lines[end].strip().startswith("```"):
                end -= 1
            cleaned = "\n".join(lines[1:end])

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}") from e

        required = ["item_type", "tags", "summary", "response"]
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"LLM JSON missing required fields: {missing}")

        try:
            item_type = ItemType(data["item_type"])
        except ValueError:
            raise ValueError(
                f"Invalid item_type '{data['item_type']}'. "
                f"Must be one of: {[t.value for t in ItemType]}"
            )

        return cls(
            item_type=item_type,
            tags=data["tags"],
            summary=data["summary"],
            response=data["response"],
            overview_update=data.get("overview_update"),
        )


@dataclass
class SearchResult:
    """A knowledge item returned from search, with relevance context."""

    item: KnowledgeItem
    rank: float = 0.0
    snippet: str = ""


@dataclass
class ConversationRecord:
    """A single LLM interaction for audit/debug logging."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    interaction_type: str = ""
    user_message: str = ""
    system_prompt: str = ""
    llm_response: str = ""
    parsed_type: Optional[str] = None
    parsed_tags: Optional[str] = None
    parsed_summary: Optional[str] = None
    record_id: Optional[int] = None
