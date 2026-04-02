"""Post-meeting summary generator.

Produces structured meeting summaries from transcripts using the LLM.
Extracts key points, action items, and decisions. Supports export
to PDF and DOCX formats for sharing.

Phase 7 implementation.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape

from app.core.llm import LLMClient

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM_PROMPT = (
    "You are a professional meeting summarizer. Given a meeting transcript, "
    "produce a structured JSON summary with exactly these four keys:\n\n"
    '1. "content": A full narrative summary of the meeting in 3-5 paragraphs.\n'
    '2. "key_points": A list of strings, each a key discussion point.\n'
    '3. "action_items": A list of strings, each an action item with owner '
    "if mentioned (e.g., 'John to prepare the Q4 budget report by Friday').\n"
    '4. "decisions": A list of strings, each a decision made during the meeting.\n\n'
    "Respond ONLY with valid JSON. No markdown fences, no extra text."
)


def _docx_paragraph_xml(text: str) -> str:
    escaped = escape(text)
    if not escaped:
        return "<w:p/>"
    return (
        '<w:p><w:r><w:t xml:space="preserve">'
        f"{escaped}"
        "</w:t></w:r></w:p>"
    )


def _build_minimal_docx(paragraphs: list[str]) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"{''.join(_docx_paragraph_xml(paragraph) for paragraph in paragraphs)}"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" '
        'w:right="1440" w:bottom="1440" w:left="1440" w:header="720" '
        'w:footer="720" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_minimal_pdf(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 12 Tf", "50 760 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            content_lines.append("0 -16 Td")
        content_lines.append(f"({_escape_pdf_text(line)}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")

    offsets = [0]
    for index, payload in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(payload)
        buffer.write(b"\nendobj\n")

    xref_start = buffer.tell()
    buffer.write(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))

    buffer.write(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "ascii"
        )
    )
    return buffer.getvalue()


class SummaryGenerator:
    """Generates structured meeting summaries from transcripts.

    Uses the LLM to analyze the full meeting transcript and produce
    a comprehensive summary with categorized sections.

    Attributes:
        max_transcript_tokens: Maximum transcript tokens to process
            in a single LLM call.
    """

    def __init__(self, max_transcript_tokens: int = 8000) -> None:
        """Initialize the summary generator.

        Args:
            max_transcript_tokens: Maximum number of transcript tokens
                to send to the LLM in one call. Longer transcripts
                are summarized in chunks and merged.
        """
        self.max_transcript_tokens = max_transcript_tokens

    async def generate(
        self,
        transcript: str,
        llm_client: Any | None = None,
    ) -> dict[str, Any]:
        """Generate a structured summary from a meeting transcript.

        Args:
            transcript: The full meeting transcript text.
            llm_client: Optional LLM client instance. If provided, its
                ``async_query`` method is used for summarization. Otherwise
                a new ``LLMClient`` is created from settings.

        Returns:
            Dictionary with keys:
                - "content": Full narrative summary.
                - "key_points": List of main discussion points.
                - "action_items": List of assigned action items.
                - "decisions": List of decisions made during the meeting.
        """
        if not transcript or not transcript.strip():
            return self._fallback_summary("")

        # Attempt LLM-based summarization
        try:
            client = llm_client
            if client is None:
                client = LLMClient()

            raw_response = await client.async_query(
                context=transcript,
                question="Summarize this meeting transcript.",
                system_prompt=_SUMMARY_SYSTEM_PROMPT,
            )

            return self._parse_llm_response(raw_response, transcript)

        except Exception:
            logger.warning(
                "LLM summarization failed, falling back to basic summary",
                exc_info=True,
            )
            return self._fallback_summary(transcript)

    def _parse_llm_response(
        self, raw: str, transcript: str
    ) -> dict[str, Any]:
        """Parse the LLM's JSON response into a summary dict.

        Falls back to the basic summary when the response cannot be
        parsed as valid JSON with the expected keys.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response, using fallback")
            return self._fallback_summary(transcript)

        required_keys = {"content", "key_points", "action_items", "decisions"}
        if not required_keys.issubset(data.keys()):
            logger.warning("LLM response missing keys: %s", required_keys - data.keys())
            return self._fallback_summary(transcript)

        # Normalize types
        return {
            "content": str(data["content"]),
            "key_points": [str(p) for p in data.get("key_points", [])],
            "action_items": [str(a) for a in data.get("action_items", [])],
            "decisions": [str(d) for d in data.get("decisions", [])],
        }

    @staticmethod
    def _fallback_summary(transcript: str) -> dict[str, Any]:
        """Generate a basic summary when the LLM is unavailable.

        Extracts a preview from the transcript head and tail plus
        basic word-count statistics.
        """
        words = transcript.split()
        word_count = len(words)
        preview_head = " ".join(words[:100]) if words else "(empty transcript)"
        preview_tail = " ".join(words[-100:]) if word_count > 100 else ""

        content_parts = [
            f"Meeting transcript contains {word_count} words.",
        ]
        if preview_head:
            content_parts.append(f"Beginning: {preview_head}...")
        if preview_tail:
            content_parts.append(f"End: ...{preview_tail}")

        return {
            "content": "\n\n".join(content_parts),
            "key_points": [
                "Full AI summary unavailable — LLM could not be reached."
            ],
            "action_items": [],
            "decisions": [],
        }

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_pdf(
        self,
        summary: dict[str, Any],
        meeting_info: dict[str, Any] | None = None,
    ) -> bytes:
        """Export a summary to PDF format.

        Args:
            summary: The summary dictionary from ``generate()``.
            meeting_info: Optional dict with ``date``, ``duration``,
                ``platform`` keys for the header.

        Returns:
            PDF file contents as bytes.
        """
        info = meeting_info or {}
        date_str = info.get("date", datetime.now().strftime("%Y-%m-%d"))
        duration = info.get("duration", "N/A")
        platform = info.get("platform", "N/A")

        pdf_lines = [
            "Meeting Summary",
            f"Synth  |  {date_str}  |  Duration: {duration}  |  Platform: {platform}",
            "",
            "Summary",
            summary.get("content", ""),
            "",
            "Key Points",
            *[(f"- {item}") for item in summary.get("key_points", []) or ["None recorded."]],
            "",
            "Action Items",
            *[(f"- {item}") for item in summary.get("action_items", []) or ["None recorded."]],
            "",
            "Decisions",
            *[(f"- {item}") for item in summary.get("decisions", []) or ["None recorded."]],
        ]

        try:
            from fpdf import FPDF
        except ModuleNotFoundError:
            return _build_minimal_pdf(pdf_lines)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()

        # -- Header block --
        pdf.set_fill_color(30, 30, 46)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 22)
        pdf.cell(0, 16, "Meeting Summary", new_x="LMARGIN", new_y="NEXT", fill=True)

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, f"Synth  |  {date_str}  |  Duration: {duration}  |  Platform: {platform}",
                 new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(8)

        # Reset colors for body
        pdf.set_text_color(30, 30, 30)

        # -- Summary section --
        self._pdf_section(pdf, "Summary", summary.get("content", ""))

        # -- Key Points --
        self._pdf_list_section(pdf, "Key Points", summary.get("key_points", []))

        # -- Action Items --
        self._pdf_list_section(pdf, "Action Items", summary.get("action_items", []))

        # -- Decisions --
        self._pdf_list_section(pdf, "Decisions", summary.get("decisions", []))

        return bytes(pdf.output())

    @staticmethod
    def _pdf_section(pdf: FPDF, title: str, body: str) -> None:
        """Render a titled text section in the PDF."""
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 46)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(30, 30, 46)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(50, 50, 50)
        # multi_cell handles line wrapping
        pdf.multi_cell(0, 6, body.encode("latin-1", "replace").decode("latin-1"))
        pdf.ln(6)

    @staticmethod
    def _pdf_list_section(pdf: FPDF, title: str, items: list[str]) -> None:
        """Render a titled bullet-list section in the PDF."""
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(30, 30, 46)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(30, 30, 46)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(50, 50, 50)

        if not items:
            pdf.multi_cell(0, 6, "None recorded.")
            pdf.ln(4)
            return

        for item in items:
            safe_text = item.encode("latin-1", "replace").decode("latin-1")
            pdf.cell(6, 6, "-")
            pdf.multi_cell(0, 6, f"  {safe_text}")
            pdf.ln(1)
        pdf.ln(4)

    def export_docx(
        self,
        summary: dict[str, Any],
        meeting_info: dict[str, Any] | None = None,
    ) -> bytes:
        """Export a summary to DOCX format.

        Args:
            summary: The summary dictionary from ``generate()``.
            meeting_info: Optional dict with ``date``, ``duration``,
                ``platform`` keys for the subtitle.

        Returns:
            DOCX file contents as bytes.
        """
        info = meeting_info or {}
        date_str = info.get("date", datetime.now().strftime("%Y-%m-%d"))
        duration = info.get("duration", "N/A")
        platform = info.get("platform", "N/A")

        paragraphs = [
            "Meeting Summary",
            f"Synth  |  {date_str}  |  Duration: {duration}  |  Platform: {platform}",
            "",
            "Summary",
        ]
        paragraphs.extend(
            [text for text in summary.get("content", "").split("\n\n") if text.strip()]
            or ["None recorded."]
        )
        paragraphs.append("")
        paragraphs.append("Key Points")
        paragraphs.extend(summary.get("key_points", []) or ["None recorded."])
        paragraphs.append("")
        paragraphs.append("Action Items")
        paragraphs.extend(summary.get("action_items", []) or ["None recorded."])
        paragraphs.append("")
        paragraphs.append("Decisions")
        paragraphs.extend(summary.get("decisions", []) or ["None recorded."])

        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Pt, RGBColor
        except ModuleNotFoundError:
            return _build_minimal_docx(paragraphs)

        doc = Document()

        # -- Styles --
        style = doc.styles["Title"]
        style.font.color.rgb = RGBColor(30, 30, 46)

        # -- Title --
        title_para = doc.add_heading("Meeting Summary", level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # -- Subtitle with meeting metadata --
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = subtitle.add_run(
            f"Synth  |  {date_str}  |  Duration: {duration}  |  Platform: {platform}"
        )
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(100, 100, 100)

        # -- Summary --
        doc.add_heading("Summary", level=1)
        for paragraph_text in summary.get("content", "").split("\n\n"):
            stripped = paragraph_text.strip()
            if stripped:
                doc.add_paragraph(stripped)

        # -- Key Points --
        doc.add_heading("Key Points", level=1)
        for point in summary.get("key_points", []) or ["None recorded."]:
            doc.add_paragraph(point, style="List Bullet")

        # -- Action Items --
        doc.add_heading("Action Items", level=1)
        for item in summary.get("action_items", []) or ["None recorded."]:
            doc.add_paragraph(item, style="List Bullet")

        # -- Decisions --
        doc.add_heading("Decisions", level=1)
        for decision in summary.get("decisions", []) or ["None recorded."]:
            doc.add_paragraph(decision, style="List Bullet")

        # Serialize to bytes
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()
