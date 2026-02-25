"""URL detection and content extraction for the Knowledge Base."""

import logging
import re
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

# Regex to detect URLs in message text
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE,
)

# Max characters of extracted content to include in LLM context
MAX_CONTENT_LENGTH = 4000


def extract_urls(text: str) -> List[str]:
    """Find all URLs in a text string."""
    return URL_PATTERN.findall(text)


async def fetch_url_content(url: str, timeout: float = 15.0) -> Optional[str]:
    """Fetch a URL and extract readable text content.

    Returns extracted text, or None if fetch/extraction fails.
    Uses readability + BeautifulSoup for article extraction.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        return _extract_readable_text(response.text)
    except Exception:
        logger.warning("Failed to fetch URL: %s", url, exc_info=True)
        return None


def _extract_readable_text(html: str) -> str:
    """Extract readable article text from HTML.

    Uses readability-lxml for article extraction, falls back to
    BeautifulSoup plain text if readability fails.
    """
    title = ""
    try:
        from readability import Document

        doc = Document(html)
        summary_html = doc.summary()
        title = doc.title()
    except Exception:
        summary_html = html

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(summary_html, "lxml")
    text = soup.get_text(separator="\n", strip=True)

    if title:
        text = f"{title}\n\n{text}"

    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"

    return text
