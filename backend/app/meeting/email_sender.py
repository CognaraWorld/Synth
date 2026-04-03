"""Email delivery for post-meeting summaries.

Sends meeting summary emails with optional PDF/DOCX attachments
using Resend (primary) or SMTP (fallback). Designed for graceful
degradation — failures are logged but never crash the caller.

Phase 7 implementation.
"""

from __future__ import annotations

import base64
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Delivers meeting summary emails via Resend or SMTP.

    Prefers the Resend HTTP API when an API key is configured.
    Falls back to SMTP when Resend is unavailable.

    Attributes:
        from_email: Sender address used in outgoing messages.
    """

    def __init__(self) -> None:
        """Initialize the email sender from application settings."""
        settings = get_settings()
        self.resend_api_key: str = settings.resend_api_key
        self.smtp_host: str = settings.smtp_host
        self.smtp_port: int = settings.smtp_port
        self.smtp_user: str = settings.smtp_user
        self.smtp_password: str = settings.smtp_password
        self.from_email: str = settings.from_email

    def is_configured(self) -> bool:
        """Return whether any outbound email transport is configured."""
        return bool(self.resend_api_key or self.smtp_host)

    async def send_summary_email(
        self,
        to_email: str,
        meeting_info: dict[str, Any],
        summary: dict[str, Any],
        pdf_bytes: bytes | None = None,
        docx_bytes: bytes | None = None,
    ) -> bool:
        """Send a meeting summary email with optional attachments.

        Attempts Resend first, then SMTP. Logs errors but never raises.

        Args:
            to_email: Recipient email address.
            meeting_info: Dict with ``date``, ``duration``, ``platform``.
            summary: Summary dict from ``SummaryGenerator.generate()``.
            pdf_bytes: Optional PDF attachment contents.
            docx_bytes: Optional DOCX attachment contents.

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        html_body = self._build_email_html(meeting_info, summary)
        subject = self._build_subject(meeting_info)

        if self.resend_api_key:
            return await self._send_via_resend(
                to_email, subject, html_body, pdf_bytes, docx_bytes
            )

        if self.smtp_host:
            return self._send_via_smtp(
                to_email, subject, html_body, pdf_bytes, docx_bytes
            )

        logger.warning(
            "No email provider configured (set RESEND_API_KEY or SMTP_HOST)"
        )
        return False

    # ------------------------------------------------------------------
    # Resend transport
    # ------------------------------------------------------------------

    async def _send_via_resend(
        self,
        to_email: str,
        subject: str,
        html: str,
        pdf_bytes: bytes | None,
        docx_bytes: bytes | None,
    ) -> bool:
        """Send email using the Resend HTTP API."""
        attachments: list[dict[str, str]] = []
        if pdf_bytes:
            attachments.append({
                "filename": "meeting-summary.pdf",
                "content": base64.b64encode(pdf_bytes).decode(),
            })
        if docx_bytes:
            attachments.append({
                "filename": "meeting-summary.docx",
                "content": base64.b64encode(docx_bytes).decode(),
            })

        payload: dict[str, Any] = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if attachments:
            payload["attachments"] = attachments

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                logger.info("Email sent via Resend to %s", to_email)
                return True
        except Exception:
            logger.error("Failed to send email via Resend", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # SMTP fallback
    # ------------------------------------------------------------------

    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html: str,
        pdf_bytes: bytes | None,
        docx_bytes: bytes | None,
    ) -> bool:
        """Send email using SMTP (synchronous fallback)."""
        msg = MIMEMultipart("mixed")
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html, "html"))

        if pdf_bytes:
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header(
                "Content-Disposition", "attachment",
                filename="meeting-summary.pdf",
            )
            msg.attach(part)

        if docx_bytes:
            part = MIMEApplication(
                docx_bytes,
                _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            part.add_header(
                "Content-Disposition", "attachment",
                filename="meeting-summary.docx",
            )
            msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            logger.info("Email sent via SMTP to %s", to_email)
            return True
        except Exception:
            logger.error("Failed to send email via SMTP", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # HTML template
    # ------------------------------------------------------------------

    @staticmethod
    def _build_subject(meeting_info: dict[str, Any]) -> str:
        """Build the email subject line."""
        date_str = meeting_info.get("date", "")
        platform = meeting_info.get("platform", "Meeting")
        return f"Meeting Summary — {platform} {date_str}".strip()

    @staticmethod
    def _build_email_html(
        meeting_info: dict[str, Any],
        summary: dict[str, Any],
    ) -> str:
        """Build a clean HTML email body for the meeting summary.

        Args:
            meeting_info: Dict with ``date``, ``duration``, ``platform``.
            summary: Summary dict with ``content``, ``key_points``,
                ``action_items``, ``decisions``.

        Returns:
            HTML string for the email body.
        """
        date_str = meeting_info.get("date", "N/A")
        duration = meeting_info.get("duration", "N/A")
        platform = meeting_info.get("platform", "N/A")

        key_points_html = "".join(
            f"<li>{_esc(p)}</li>" for p in summary.get("key_points", [])
        ) or "<li>None recorded.</li>"

        action_items_html = "".join(
            f"<li>{_esc(a)}</li>" for a in summary.get("action_items", [])
        ) or "<li>None recorded.</li>"

        decisions_html = "".join(
            f"<li>{_esc(d)}</li>" for d in summary.get("decisions", [])
        ) or "<li>None recorded.</li>"

        content_paragraphs = "".join(
            f"<p>{_esc(para.strip())}</p>"
            for para in summary.get("content", "").split("\n\n")
            if para.strip()
        ) or "<p>No summary content available.</p>"

        return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont,
  'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#333; line-height:1.6;">
  <div style="max-width:640px; margin:0 auto;">

    <!-- Header -->
    <div style="background:#1e1e2e; color:#fff; padding:24px 32px;">
      <h1 style="margin:0; font-size:22px; font-weight:600;">Meeting Summary</h1>
      <p style="margin:6px 0 0; font-size:13px; color:#ccc;">
        Synth &middot; {_esc(date_str)} &middot; Duration: {_esc(duration)}
        &middot; Platform: {_esc(platform)}
      </p>
    </div>

    <div style="padding:24px 32px;">

      <!-- Summary -->
      <h2 style="font-size:16px; color:#1e1e2e; border-bottom:2px solid #1e1e2e;
        padding-bottom:6px;">Summary</h2>
      {content_paragraphs}

      <!-- Key Points -->
      <h2 style="font-size:16px; color:#1e1e2e; border-bottom:2px solid #1e1e2e;
        padding-bottom:6px; margin-top:24px;">Key Points</h2>
      <ul style="padding-left:20px;">{key_points_html}</ul>

      <!-- Action Items -->
      <h2 style="font-size:16px; color:#1e1e2e; border-bottom:2px solid #1e1e2e;
        padding-bottom:6px; margin-top:24px;">Action Items</h2>
      <ul style="padding-left:20px;">{action_items_html}</ul>

      <!-- Decisions -->
      <h2 style="font-size:16px; color:#1e1e2e; border-bottom:2px solid #1e1e2e;
        padding-bottom:6px; margin-top:24px;">Decisions</h2>
      <ul style="padding-left:20px;">{decisions_html}</ul>

    </div>

    <!-- Footer -->
    <div style="padding:16px 32px; font-size:12px; color:#999; border-top:1px solid #eee;">
      Generated by Synth
    </div>

  </div>
</body>
</html>"""


def _esc(text: str) -> str:
    """Minimal HTML-escape for user content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
