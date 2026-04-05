from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from app.utils.filler import FillerManager
from app.utils.query_router import QueryCategory, classify_query, needs_web_search
from app.utils.report_data import (
    build_embedded_summary_payload,
    build_report_preview,
    deserialize_summary_items,
    serialize_summary_items,
)
from app.utils.wake_word import _build_pattern, detect


class TestReportDataHelpers:
    def test_serialize_summary_items_handles_none(self) -> None:
        assert serialize_summary_items(None) == "[]"

    def test_deserialize_summary_items_handles_json_and_fallbacks(self) -> None:
        assert deserialize_summary_items(None) == []
        assert deserialize_summary_items([" a ", "", "b"]) == [" a ", "b"]
        assert deserialize_summary_items('["x", "", "y"]') == ["x", "y"]
        assert deserialize_summary_items('"single"') == ["single"]
        assert deserialize_summary_items("- item one\n- item two") == ["item one", "item two"]
        assert deserialize_summary_items("not-json") == ["not-json"]

    def test_build_report_preview_truncates_when_needed(self) -> None:
        assert build_report_preview("short text", limit=20) == "short text"
        preview = build_report_preview("word " * 20, limit=25)
        assert preview.endswith("...")
        assert len(preview) <= 28

    def test_build_embedded_summary_payload_hides_filesystem_paths(self) -> None:
        summary = SimpleNamespace(
            id="sum-1",
            content="Summary",
            key_points=["k1"],
            action_items=["a1"],
            decisions=["d1"],
            email_delivery_status="sent",
            email_delivered_at="2026-01-01",
            pdf_path="/srv/private/file.pdf",
            docx_path=None,
            created_at="2026-01-01",
        )
        payload = build_embedded_summary_payload(summary)

        assert payload["has_pdf"] is True
        assert payload["has_docx"] is False
        assert payload["pdf_download_path"] == "/api/reports/sum-1/download/pdf"
        assert payload["docx_download_path"] is None
        assert "/srv/private/file.pdf" not in str(payload)


class TestQueryRouterCoverage:
    def test_classify_query_prioritizes_meeting_recap(self) -> None:
        result = classify_query("What did we discuss about the latest market update?")
        assert result == QueryCategory.MEETING_RECAP

    def test_classify_query_prioritizes_document_over_technical(self) -> None:
        result = classify_query("According to the pdf, how to implement this API?")
        assert result == QueryCategory.DOCUMENT

    def test_classify_query_technical_opinion_web_and_general(self) -> None:
        assert classify_query("How do I debug this function?") == QueryCategory.TECHNICAL
        assert classify_query("What do you think we should do?") == QueryCategory.OPINION
        assert classify_query("What is the current stock price?") == QueryCategory.WEB_SEARCH
        assert classify_query("Nice to meet everyone") == QueryCategory.GENERAL

    def test_needs_web_search_true_false_and_default_false(self) -> None:
        assert needs_web_search("What's the latest weather update?") is True
        assert needs_web_search("What did Sarah say earlier in the meeting?") is False
        assert needs_web_search("Can you help summarize this thought?") is False


class TestFillerManagerCoverage:
    def test_preload_caches_phrase_and_voice_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_module = types.SimpleNamespace(
            RecallClient=type(
                "RecallClient",
                (),
                {"pcm_to_mp3_b64": staticmethod(lambda pcm: f"mp3:{pcm.decode('utf-8')}")},
            )
        )
        monkeypatch.setitem(sys.modules, "app.meeting.recall_client", fake_module)

        class FakeTTS:
            voice = "voice-a"

            def __init__(self) -> None:
                self.calls: list[str] = []

            def synthesize(self, phrase: str) -> bytes:
                self.calls.append(phrase)
                return phrase.encode("utf-8")

        manager = FillerManager()
        tts = FakeTTS()

        manager.preload(tts)
        first_call_count = len(tts.calls)
        manager.preload(tts)

        assert first_call_count > 0
        assert len(tts.calls) == first_call_count

        phrase = manager.get_filler_for_category(QueryCategory.GENERAL)
        assert manager._cache[f"{phrase}:voice-a"] == phrase.encode("utf-8")
        assert manager._cache[phrase] == phrase.encode("utf-8")
        assert manager._mp3_cache[f"{phrase}:voice-a"] == f"mp3:{phrase}"

    def test_getters_handle_empty_cache_and_voice_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        manager = FillerManager()
        assert manager.get_filler_mp3_b64(QueryCategory.GENERAL, voice="x") == ""
        assert manager.get_filler_audio(QueryCategory.GENERAL, voice="x") == b""

        monkeypatch.setattr("app.utils.filler.random.choice", lambda phrases: phrases[0])
        phrase = manager.get_filler_for_category(QueryCategory.GENERAL)
        manager._mp3_cache[phrase] = "plain-mp3"
        manager._cache[phrase] = b"plain-pcm"

        assert manager.get_filler_mp3_b64(QueryCategory.GENERAL, voice="missing") == "plain-mp3"
        assert manager.get_filler_audio(QueryCategory.GENERAL, voice="missing") == b"plain-pcm"
        assert manager.get_random_filler_mp3_b64() == "plain-mp3"
        assert manager.get_random_filler_audio() == b"plain-pcm"


class TestWakeWordCoverage:
    def test_detect_handles_stt_variants_and_cleanup_words(self) -> None:
        detected, question = detect("He sint, what changed?", wake_word="hey synth")
        assert detected is True
        assert question == "what changed?"

        detected2, question2 = detect("hey assist ten what now", wake_word="hey assistant")
        assert detected2 is True
        assert question2 == "what now"

    def test_detect_custom_hey_name_and_word_boundaries(self) -> None:
        detected, question = detect("Atlas, status update", wake_word="hey atlas")
        assert detected is True
        assert question == "status update"

        assert detect("supernova events are rare", wake_word="nova") == (False, "")
        assert detect("innova platform", wake_word="nova") == (False, "")

    def test_build_pattern_custom_phrase_branch(self) -> None:
        pattern = _build_pattern("custom phrase")
        assert pattern.search("This CUSTOM PHRASE should match") is not None
