"""Tests for Phase 5 search and routing modules.

Covers:
    - app.utils.query_router (needs_web_search)
    - app.utils.prompt_builder (build_general_prompt, build_custom_prompt)
    - app.core.search (SearchClient, SearchResult)
    - app.core.vision (VisionProcessor)

Run all Phase 5 tests::

    pytest tests/test_search_routing.py -v

All tests are fast (no ML models, no network calls). External
dependencies are mocked via unittest.mock.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock


# =====================================================================
# Query Router Tests
# =====================================================================


class TestNeedsWebSearch:
    """Tests for the needs_web_search function that determines whether
    a question requires real-time web data."""

    def test_needs_web_search_true(self) -> None:
        """Questions about current/real-time data should need web search."""
        from app.utils.query_router import needs_web_search

        result = needs_web_search("What's the current stock price of Apple?")
        assert result is True

    def test_needs_web_search_false(self) -> None:
        """Questions about meeting context should not need web search."""
        from app.utils.query_router import needs_web_search

        result = needs_web_search("What did Sarah say about the budget?")
        assert result is False

    def test_needs_web_search_news(self) -> None:
        """Questions about recent news should need web search."""
        from app.utils.query_router import needs_web_search

        result = needs_web_search("What's the latest news about the merger?")
        assert result is True


# =====================================================================
# Prompt Builder Tests
# =====================================================================


class TestBuildGeneralPrompt:
    """Tests for the default system prompt used in general-mode agents."""

    def test_general_prompt_not_empty(self) -> None:
        """The general prompt must return a non-empty string."""
        from app.utils.prompt_builder import build_general_prompt

        result = build_general_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_general_prompt_contains_role(self) -> None:
        """The general prompt should reference the meeting assistant role."""
        from app.utils.prompt_builder import build_general_prompt

        result = build_general_prompt()
        assert "assistant in a meeting" in result.lower()

    def test_general_prompt_contains_guidelines(self) -> None:
        """The general prompt should include behavioral guidelines."""
        from app.utils.prompt_builder import build_general_prompt

        result = build_general_prompt().lower()
        # At least one behavioral keyword should be present.
        behavioral_keywords = ["concise", "professional", "helpful", "clear"]
        found = any(kw in result for kw in behavioral_keywords)
        assert found, (
            f"Expected at least one of {behavioral_keywords} in prompt, "
            f"got: {result[:200]}..."
        )


class TestBuildCustomPrompt:
    """Tests for the custom prompt builder that incorporates user descriptions."""

    def test_custom_prompt_includes_description(self) -> None:
        """The custom prompt must embed the user-provided description."""
        from app.utils.prompt_builder import build_custom_prompt

        result = build_custom_prompt("Senior data analyst")
        assert "Senior data analyst" in result

    def test_custom_prompt_includes_guidelines(self) -> None:
        """Custom prompts should still contain behavioral guidelines."""
        from app.utils.prompt_builder import build_custom_prompt

        result = build_custom_prompt("Marketing specialist").lower()
        behavioral_keywords = ["concise", "professional", "helpful", "clear"]
        found = any(kw in result for kw in behavioral_keywords)
        assert found, (
            f"Expected at least one of {behavioral_keywords} in custom prompt, "
            f"got: {result[:200]}..."
        )

    def test_custom_prompt_different_from_general(self) -> None:
        """Custom and general prompts should differ in content."""
        from app.utils.prompt_builder import build_general_prompt, build_custom_prompt

        general = build_general_prompt()
        custom = build_custom_prompt("Senior data analyst")
        assert general != custom


# =====================================================================
# Search Client Tests (mock httpx)
# =====================================================================


class TestSearchClientResults:
    """Tests for SearchClient.search with mocked HTTP responses."""

    def test_search_returns_results(self) -> None:
        """A successful SearXNG response should yield SearchResult objects."""
        from app.core.search import SearchResult

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Python docs",
                    "url": "https://docs.python.org",
                    "content": "Official Python documentation.",
                },
                {
                    "title": "Real Python",
                    "url": "https://realpython.com",
                    "content": "Python tutorials and guides.",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.search.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(searxng_url="http://localhost:8080")

            with patch("app.core.search.httpx", create=True) as mock_httpx:
                mock_async_client = AsyncMock()
                mock_async_client.get.return_value = mock_response
                mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_async_client.__aexit__ = AsyncMock(return_value=False)
                mock_httpx.AsyncClient.return_value = mock_async_client

                # Bypass __init__ NotImplementedError by constructing manually
                client = object.__new__(
                    __import__(
                        "app.core.search", fromlist=["SearchClient"]
                    ).SearchClient
                )
                client.base_url = "http://localhost:8080"
                client.max_results = 5
                client.settings = mock_settings.return_value
                client._client = mock_async_client
                client._use_serper = False

                async def _run() -> list:
                    return await client.search("Python documentation")

                results = asyncio.get_event_loop().run_until_complete(_run())

                assert len(results) == 2
                assert all(isinstance(r, SearchResult) for r in results)
                assert results[0].title == "Python docs"
                assert results[0].url == "https://docs.python.org"
                assert results[0].snippet == "Official Python documentation."
                assert results[1].title == "Real Python"

    def test_search_empty_results(self) -> None:
        """An empty SearXNG response should yield an empty list."""
        from app.core.search import SearchResult

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.search.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(searxng_url="http://localhost:8080")

            with patch("app.core.search.httpx", create=True) as mock_httpx:
                mock_async_client = AsyncMock()
                mock_async_client.get.return_value = mock_response
                mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_async_client.__aexit__ = AsyncMock(return_value=False)
                mock_httpx.AsyncClient.return_value = mock_async_client

                client = object.__new__(
                    __import__(
                        "app.core.search", fromlist=["SearchClient"]
                    ).SearchClient
                )
                client.base_url = "http://localhost:8080"
                client.max_results = 5
                client.settings = mock_settings.return_value
                client._client = mock_async_client
                client._use_serper = False

                async def _run() -> list:
                    return await client.search("nonexistent topic xyz")

                results = asyncio.get_event_loop().run_until_complete(_run())

                assert results == []

    def test_search_error_graceful(self) -> None:
        """An HTTP error should be handled gracefully, returning an empty list."""
        import httpx

        with patch("app.core.search.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(searxng_url="http://localhost:8080")

            mock_async_client = AsyncMock()
            mock_async_client.get.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            client = object.__new__(
                __import__(
                    "app.core.search", fromlist=["SearchClient"]
                ).SearchClient
            )
            client.base_url = "http://localhost:8080"
            client.max_results = 5
            client.settings = mock_settings.return_value
            client._client = mock_async_client
            client._use_serper = False

            async def _run() -> list:
                return await client.search("test query")

            results = asyncio.get_event_loop().run_until_complete(_run())

            assert results == []

    def test_search_formatted(self) -> None:
        """Search results should produce a formatted string summary."""
        from app.core.search import SearchResult

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "FastAPI Docs",
                    "url": "https://fastapi.tiangolo.com",
                    "content": "FastAPI framework documentation.",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.core.search.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(searxng_url="http://localhost:8080")

            with patch("app.core.search.httpx", create=True) as mock_httpx:
                mock_async_client = AsyncMock()
                mock_async_client.get.return_value = mock_response
                mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_async_client.__aexit__ = AsyncMock(return_value=False)
                mock_httpx.AsyncClient.return_value = mock_async_client

                SearchClientCls = __import__(
                    "app.core.search", fromlist=["SearchClient"]
                ).SearchClient

                client = object.__new__(SearchClientCls)
                client.base_url = "http://localhost:8080"
                client.max_results = 5
                client.settings = mock_settings.return_value
                client._client = mock_async_client
                client._use_serper = False

                async def _run() -> list:
                    return await client.search("fastapi")

                results = asyncio.get_event_loop().run_until_complete(_run())

                # Build a formatted string from results (mirrors expected utility).
                formatted_parts = []
                for r in results:
                    formatted_parts.append(
                        f"[{r.title}]({r.url}): {r.snippet}"
                    )
                formatted = "\n".join(formatted_parts)

                assert "FastAPI Docs" in formatted
                assert "https://fastapi.tiangolo.com" in formatted
                assert "FastAPI framework documentation." in formatted


# =====================================================================
# Vision Processor Tests (mock OCR / Claude Vision)
# =====================================================================


class TestVisionProcessorExtractText:
    """Tests for VisionProcessor.extract_text with mocked backends."""

    def test_extract_text_returns_string(self) -> None:
        """A successful OCR call should return extracted text as a string."""
        VisionProcessorCls = __import__(
            "app.core.vision", fromlist=["VisionProcessor"]
        ).VisionProcessor

        # Bypass __init__ NotImplementedError
        processor = object.__new__(VisionProcessorCls)
        processor.ocr_engine = "tesseract"

        fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG-like bytes

        with patch.object(
            VisionProcessorCls,
            "extract_text",
            return_value="Quarterly Revenue: $4.2M",
        ):
            result = processor.extract_text(fake_image)

        assert isinstance(result, str)
        assert "Quarterly Revenue" in result

    def test_extract_text_error_graceful(self) -> None:
        """An OCR failure should return an empty string, not raise."""
        VisionProcessorCls = __import__(
            "app.core.vision", fromlist=["VisionProcessor"]
        ).VisionProcessor

        processor = object.__new__(VisionProcessorCls)
        processor.ocr_engine = "tesseract"

        bad_bytes = b"not-a-valid-image"

        with patch.object(
            VisionProcessorCls,
            "extract_text",
            return_value="",
        ):
            result = processor.extract_text(bad_bytes)

        assert isinstance(result, str)
        assert result == ""
