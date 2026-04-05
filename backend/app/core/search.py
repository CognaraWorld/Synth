"""Web search client.

Provides web search via Serper (Google SERP API) as primary,
with SearXNG self-hosted as fallback. Used to augment the LLM's
knowledge with real-time information during meetings.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_SERPER_URL = "https://google.serper.dev/search"


@dataclass
class SearchResult:
    """A single web search result.

    Attributes:
        title: The title of the search result page.
        url: The URL of the result.
        snippet: A brief text excerpt from the page content.
    """

    title: str
    url: str
    snippet: str


class SearchClient:
    """Web search client with Serper (primary) and SearXNG (fallback).

    Uses Serper API when a key is configured, otherwise falls back
    to a local SearXNG instance.

    Attributes:
        max_results: Maximum number of results to return per query.
    """

    def __init__(self, max_results: int = 5) -> None:
        """Initialize the search client.

        Args:
            max_results: Maximum number of results to return per query.
        """
        self.settings = get_settings()
        self.max_results = max_results
        self._client = httpx.AsyncClient(timeout=10.0)

        # Determine which backend to use
        self._use_serper = bool(self.settings.serper_api_key)
        if self._use_serper:
            logger.info("Search client using Serper API")
        else:
            logger.info("Search client using SearXNG at %s", self.settings.searxng_url)

    async def __aenter__(self) -> SearchClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def search(self, query: str) -> list[SearchResult]:
        """Execute a web search query.

        Routes to Serper or SearXNG based on configuration.

        Args:
            query: The search query string.

        Returns:
            A list of SearchResult objects, up to max_results.
        """
        if self._use_serper:
            return await self._search_serper(query)
        return await self._search_searxng(query)

    async def _search_serper(self, query: str) -> list[SearchResult]:
        """Search via Serper (Google SERP API)."""
        headers = {
            "X-API-KEY": self.settings.serper_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": self.max_results,
        }

        try:
            response = await self._client.post(
                _SERPER_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Serper search failed for query %r: %s", query, exc)
            # Fall back to SearXNG if Serper fails
            return await self._search_searxng(query)

        results: list[SearchResult] = []
        for item in data.get("organic", []):
            if len(results) >= self.max_results:
                break
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                )
            )

        return results

    async def _search_searxng(self, query: str) -> list[SearchResult]:
        """Search via self-hosted SearXNG instance."""
        base_url = self.settings.searxng_url.rstrip("/")
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
        }

        try:
            response = await self._client.get(
                f"{base_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("SearXNG search failed for query %r: %s", query, exc)
            return []

        results: list[SearchResult] = []
        for item in data.get("results", []):
            if len(results) >= self.max_results:
                break
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", item.get("snippet", "")),
                )
            )

        return results

    async def search_formatted(self, query: str) -> str:
        """Execute a search and return results as a formatted string.

        Produces a numbered, markdown-style list suitable for injection
        into an LLM context window.

        Args:
            query: The search query string.

        Returns:
            A formatted string containing the search results, or an
            empty-results message if no results were found.
        """
        results = await self.search(query)

        if not results:
            return ""

        lines = [f'Web Search Results for "{query}":']
        for idx, result in enumerate(results, start=1):
            lines.append(f"{idx}. {result.title}: {result.snippet}")

        return "\n".join(lines)

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()
