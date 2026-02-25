"""Tests for knowledge.fetcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from knowledge.fetcher import (
    MAX_CONTENT_LENGTH,
    _extract_readable_text,
    extract_urls,
    fetch_url_content,
)


# --- extract_urls tests ---


def test_extract_urls_single():
    """Find a single URL in text."""
    urls = extract_urls("check https://example.com please")
    assert urls == ["https://example.com"]


def test_extract_urls_multiple():
    """Find multiple URLs in text."""
    text = "see https://one.com and http://two.org/page for details"
    urls = extract_urls(text)
    assert len(urls) == 2
    assert "https://one.com" in urls
    assert "http://two.org/page" in urls


def test_extract_urls_none():
    """Return empty list when no URLs present."""
    assert extract_urls("no links here at all") == []


def test_extract_urls_with_query_params():
    """URLs with query parameters are captured correctly."""
    urls = extract_urls("link: https://news.ycombinator.com/item?id=47141797")
    assert urls == ["https://news.ycombinator.com/item?id=47141797"]


def test_extract_urls_complex():
    """URLs with paths and fragments are captured."""
    urls = extract_urls("see https://example.com/path/to/page#section")
    assert urls == ["https://example.com/path/to/page#section"]


# --- _extract_readable_text tests ---


def test_extract_readable_text_strips_html():
    """HTML tags are stripped, text content preserved."""
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    text = _extract_readable_text(html)
    assert "Hello" in text
    assert "world" in text
    assert "<p>" not in text
    assert "<b>" not in text


def test_extract_readable_text_truncates_long_content():
    """Content longer than MAX_CONTENT_LENGTH is truncated."""
    long_text = "x" * (MAX_CONTENT_LENGTH + 1000)
    html = f"<html><body><p>{long_text}</p></body></html>"
    text = _extract_readable_text(html)
    assert len(text) <= MAX_CONTENT_LENGTH + 50  # Allow for truncation message
    assert "[Content truncated]" in text


def test_extract_readable_text_short_content_not_truncated():
    """Short content is returned without truncation marker."""
    html = "<html><body><p>Short text</p></body></html>"
    text = _extract_readable_text(html)
    assert "[Content truncated]" not in text


# --- fetch_url_content tests (mocked HTTP) ---


@pytest.mark.asyncio
async def test_fetch_url_content_success():
    """Successful fetch returns extracted text."""
    mock_response = MagicMock()
    mock_response.text = "<html><body><p>Article content here</p></body></html>"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge.fetcher.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_url_content("https://example.com")

    assert result is not None
    assert "Article content" in result


@pytest.mark.asyncio
async def test_fetch_url_content_http_error():
    """HTTP error returns None."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
    )

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge.fetcher.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_url_content("https://example.com/404")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_url_content_timeout():
    """Timeout returns None."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge.fetcher.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_url_content("https://slow.example.com")

    assert result is None
