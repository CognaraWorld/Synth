"""SearXNG search client.

Provides web search capabilities via a self-hosted SearXNG instance.
Used to augment the LLM's knowledge with real-time information when
answering questions that require up-to-date data.

Phase 4 implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


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
    """Client for querying a SearXNG instance.

    Sends search queries to the configured SearXNG server and returns
    structured results for inclusion in the LLM context window.

    Attributes:
        base_url: URL of the SearXNG instance.
        max_results: Maximum number of results to return per query.
    """

    def __init__(self, max_results: int = 5) -> None:
        """Initialize the SearXNG client.

        Args:
            max_results: Maximum number of results to return per query.
        """
        self.settings = get_settings()
        self.base_url = self.settings.searxng_url.rstrip("/")
        self.max_results = max_results
        self._client = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str) -> list[SearchResult]:
        """Execute a web search query.

        Args:
            query: The search query string.

        Returns:
            A list of SearchResult objects, up to max_results.
        """
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
        }

        try:
            response = await self._client.get(
                f"{self.base_url}/search",
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
            return f'Web Search Results for "{query}":\nNo results found.'

        lines = [f'Web Search Results for "{query}":']
        for idx, result in enumerate(results, start=1):
            lines.append(f"{idx}. [{result.title}]({result.url}) — {result.snippet}")

        return "\n".join(lines)

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()
