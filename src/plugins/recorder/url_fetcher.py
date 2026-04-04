"""Async URL fetching and readable text extraction."""
from __future__ import annotations

import ipaddress
import logging
import re
from urllib.parse import urlparse

import httpx
from readability import Document

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_MAX_TEXT_LENGTH = 3000

# Blocked hosts/patterns to prevent SSRF
_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


def _is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch (not internal/private network)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""

        # Block known local hostnames
        if host.lower() in _BLOCKED_HOSTS:
            return False

        # Block private/reserved IP ranges
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # Not an IP — it's a hostname, that's fine

        # Block cloud metadata endpoints
        if host == "169.254.169.254":
            return False

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            return False

        return True
    except Exception:
        return False


async def fetch_url(url: str) -> str | None:
    """Fetch URL content. Returns HTML string or None on failure."""
    if not _is_safe_url(url):
        logger.warning("Blocked unsafe URL: %s", url)
        return None

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "DailyClaw/1.0"},
        ) as client:
            response = await client.get(url)
            if response.status_code >= 400:
                logger.warning("URL fetch failed: %s -> %d", url, response.status_code)
                return None
            return response.text
    except Exception as exc:
        logger.warning("URL fetch error for %s: %s", url, exc)
        return None


def extract_readable_text(html: str, url: str = "") -> str:
    """Extract main readable text from HTML using readability.

    Returns clean text truncated to _MAX_TEXT_LENGTH chars.
    """
    if not html.strip():
        return ""
    try:
        doc = Document(html, url=url)
        summary_html = doc.summary()
        text = re.sub(r"<[^>]+>", " ", summary_html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:_MAX_TEXT_LENGTH]
    except Exception as exc:
        logger.warning("Readability extraction failed: %s", exc)
        return ""
