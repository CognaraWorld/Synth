"""Tests for Phase 7 — post-meeting summary generation and export."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.meeting.summary import SummaryGenerator
from app.meeting.email_sender import EmailSender


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

SAMPLE_TRANSCRIPT = (
    "Alice: Good morning everyone. Let's discuss the Q4 roadmap.\n"
    "Bob: I think we should prioritize the mobile app rewrite.\n"
    "Alice: Agreed. Bob, can you draft a timeline by Friday?\n"
    "Charlie: We also need to decide on the analytics vendor.\n"
    "Alice: Let's go with Mixpanel. Any objections?\n"
    "Bob: No objections from me.\n"
    "Charlie: Sounds good. I'll set up the Mixpanel account this week.\n"
    "Alice: Great. Let's reconvene next Tuesday for a progress check."
)

SAMPLE_LLM_JSON = json.dumps({
    "content": (
        "The team held a Q4 roadmap discussion. Key topics included "
        "the mobile app rewrite and analytics vendor selection.\n\n"
        "Bob was tasked with drafting a timeline for the mobile rewrite. "
        "The team unanimously chose Mixpanel as the analytics vendor."
    ),
    "key_points": [
        "Q4 roadmap review",
        "Mobile app rewrite prioritization",
        "Analytics vendor selection",
    ],
    "action_items": [
        "Bob to draft mobile rewrite timeline by Friday",
        "Charlie to set up Mixpanel account this week",
    ],
    "decisions": [
        "Prioritize mobile app rewrite for Q4",
        "Use Mixpanel for analytics",
    ],
})

SAMPLE_MEETING_INFO: dict[str, Any] = {
    "date": "2026-04-02",
    "duration": "32 min",
    "platform": "Zoom",
}


@pytest.fixture()
def generator() -> SummaryGenerator:
    """Create a SummaryGenerator instance."""
    return SummaryGenerator()


@pytest.fixture()
def sample_summary() -> dict[str, Any]:
    """Return a realistic summary dict for export tests."""
    return json.loads(SAMPLE_LLM_JSON)


# ------------------------------------------------------------------
# Summary generation
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_without_llm(generator: SummaryGenerator) -> None:
    """Fallback summary is returned when no LLM client is available and
    the default LLMClient cannot be constructed (missing API key)."""
    with patch("app.meeting.summary.LLMClient", side_effect=Exception("no key")):
        result = await generator.generate(SAMPLE_TRANSCRIPT)

    assert isinstance(result, dict)
    assert "content" in result
    assert "key_points" in result
    assert "action_items" in result
    assert "decisions" in result
    # Fallback should mention word count
    assert "words" in result["content"].lower()


@pytest.mark.asyncio
async def test_generate_with_empty_transcript(generator: SummaryGenerator) -> None:
    """An empty transcript still produces a valid summary dict."""
    result = await generator.generate("")
    assert result["content"] is not None
    assert isinstance(result["key_points"], list)


@pytest.mark.asyncio
async def test_generate_with_mock_llm(generator: SummaryGenerator) -> None:
    """When a mock LLM returns valid JSON, the summary is correctly parsed."""
    mock_client = MagicMock()
    mock_client.async_query = AsyncMock(return_value=SAMPLE_LLM_JSON)

    result = await generator.generate(SAMPLE_TRANSCRIPT, llm_client=mock_client)

    assert result["content"].startswith("The team held")
    assert len(result["key_points"]) == 3
    assert len(result["action_items"]) == 2
    assert len(result["decisions"]) == 2
    mock_client.async_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_with_llm_returning_fenced_json(
    generator: SummaryGenerator,
) -> None:
    """LLM responses wrapped in markdown code fences are handled."""
    fenced = f"```json\n{SAMPLE_LLM_JSON}\n```"
    mock_client = MagicMock()
    mock_client.async_query = AsyncMock(return_value=fenced)

    result = await generator.generate(SAMPLE_TRANSCRIPT, llm_client=mock_client)
    assert len(result["key_points"]) == 3


@pytest.mark.asyncio
async def test_generate_with_llm_bad_json(generator: SummaryGenerator) -> None:
    """Non-JSON LLM response triggers the fallback summary."""
    mock_client = MagicMock()
    mock_client.async_query = AsyncMock(return_value="This is not JSON at all.")

    result = await generator.generate(SAMPLE_TRANSCRIPT, llm_client=mock_client)
    assert "words" in result["content"].lower()


def test_summary_dict_keys(generator: SummaryGenerator) -> None:
    """The fallback summary always contains the required four keys."""
    result = generator._fallback_summary(SAMPLE_TRANSCRIPT)
    assert set(result.keys()) == {"content", "key_points", "action_items", "decisions"}
    assert isinstance(result["key_points"], list)
    assert isinstance(result["action_items"], list)
    assert isinstance(result["decisions"], list)


# ------------------------------------------------------------------
# PDF export
# ------------------------------------------------------------------


def test_export_pdf(generator: SummaryGenerator, sample_summary: dict[str, Any]) -> None:
    """PDF output is valid bytes starting with the %PDF magic header."""
    pdf_bytes = generator.export_pdf(sample_summary, meeting_info=SAMPLE_MEETING_INFO)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:5] == b"%PDF-"


def test_export_pdf_without_meeting_info(
    generator: SummaryGenerator, sample_summary: dict[str, Any]
) -> None:
    """PDF generation works when meeting_info is omitted."""
    pdf_bytes = generator.export_pdf(sample_summary)
    assert pdf_bytes[:5] == b"%PDF-"


def test_export_pdf_empty_lists(generator: SummaryGenerator) -> None:
    """PDF handles a summary with all empty lists gracefully."""
    empty_summary = {
        "content": "Short meeting with no outcomes.",
        "key_points": [],
        "action_items": [],
        "decisions": [],
    }
    pdf_bytes = generator.export_pdf(empty_summary)
    assert pdf_bytes[:5] == b"%PDF-"


# ------------------------------------------------------------------
# DOCX export
# ------------------------------------------------------------------


def test_export_docx(
    generator: SummaryGenerator, sample_summary: dict[str, Any]
) -> None:
    """DOCX output is valid bytes (ZIP format, PK header)."""
    docx_bytes = generator.export_docx(sample_summary, meeting_info=SAMPLE_MEETING_INFO)

    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 0
    # DOCX is a ZIP container — starts with PK\x03\x04
    assert docx_bytes[:2] == b"PK"


def test_export_docx_without_meeting_info(
    generator: SummaryGenerator, sample_summary: dict[str, Any]
) -> None:
    """DOCX generation works when meeting_info is omitted."""
    docx_bytes = generator.export_docx(sample_summary)
    assert docx_bytes[:2] == b"PK"


def test_export_docx_empty_lists(generator: SummaryGenerator) -> None:
    """DOCX handles a summary with all empty lists gracefully."""
    empty_summary = {
        "content": "Nothing of note.",
        "key_points": [],
        "action_items": [],
        "decisions": [],
    }
    docx_bytes = generator.export_docx(empty_summary)
    assert docx_bytes[:2] == b"PK"


# ------------------------------------------------------------------
# Email HTML builder
# ------------------------------------------------------------------


def test_email_html_build() -> None:
    """The email HTML builder produces a complete HTML document."""
    summary = json.loads(SAMPLE_LLM_JSON)
    html = EmailSender._build_email_html(SAMPLE_MEETING_INFO, summary)

    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "Meeting Summary" in html
    assert "Key Points" in html
    assert "Action Items" in html
    assert "Decisions" in html
    assert "Zoom" in html
    assert "2026-04-02" in html
    # Verify bullet items are rendered
    assert "Mixpanel" in html
    assert "Bob" in html


def test_email_html_escapes_special_chars() -> None:
    """HTML special characters in summary content are escaped."""
    summary: dict[str, Any] = {
        "content": 'Alert: <script>alert("xss")</script>',
        "key_points": ["Use <b>bold</b> tags"],
        "action_items": [],
        "decisions": [],
    }
    html = EmailSender._build_email_html({"date": "today"}, summary)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;" in html


def test_email_subject_builder() -> None:
    """Subject line includes platform and date."""
    subject = EmailSender._build_subject(SAMPLE_MEETING_INFO)
    assert "Zoom" in subject
    assert "2026-04-02" in subject


# ------------------------------------------------------------------
# EmailSender initialization
# ------------------------------------------------------------------


def test_email_sender_init_no_crash() -> None:
    """EmailSender.__init__ does not raise even with default settings."""
    with patch("app.meeting.email_sender.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            resend_api_key="",
            smtp_host="",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            from_email="test@example.com",
        )
        sender = EmailSender()
        assert sender.from_email == "test@example.com"


@pytest.mark.asyncio
async def test_send_summary_email_no_provider() -> None:
    """send_summary_email returns False when no provider is configured."""
    with patch("app.meeting.email_sender.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            resend_api_key="",
            smtp_host="",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            from_email="test@example.com",
        )
        sender = EmailSender()
        result = await sender.send_summary_email(
            to_email="user@example.com",
            meeting_info=SAMPLE_MEETING_INFO,
            summary=json.loads(SAMPLE_LLM_JSON),
        )
        assert result is False
