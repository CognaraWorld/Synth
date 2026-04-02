"""Focused tests for backend ingress hardening helpers and guards."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.api.routes.auth import create_access_token
from app.utils.meeting_links import detect_meeting_platform
from app.utils.storage import build_agent_upload_path, is_managed_path, sanitize_filename


class TestAuthGuards:
    def test_create_access_token_requires_non_default_secret(self) -> None:
        with patch(
            "app.api.routes.auth.settings",
            MagicMock(
                secret_key="change-me-in-production",
                access_token_expire_minutes=1440,
                algorithm="HS256",
            ),
        ):
            with pytest.raises(RuntimeError, match="BACKEND_SECRET_KEY"):
                create_access_token({"sub": "123"})


class TestMeetingLinks:
    def test_detects_supported_hosts(self) -> None:
        assert detect_meeting_platform("https://meet.google.com/abc-defg-hij") == "meet"
        assert detect_meeting_platform("https://teams.microsoft.com/l/meetup-join/123") == "teams"
        assert detect_meeting_platform("https://acme.zoom.us/j/123456789") == "zoom"

    def test_rejects_misleading_redirect_hosts(self) -> None:
        with pytest.raises(ValueError, match="Unsupported meeting platform"):
            detect_meeting_platform(
                "https://evil.example.com/meet.google.com/abc-defg-hij"
            )


class TestStorageHelpers:
    def test_sanitize_filename_strips_path_segments(self) -> None:
        assert sanitize_filename("../Quarterly Report!!.pdf") == "Quarterly_Report.pdf"

    def test_build_agent_upload_path_stays_under_root(self, monkeypatch) -> None:
        monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None)

        root = Path.cwd() / "storage-root"
        display_name, file_path = build_agent_upload_path(
            root,
            "agent-123",
            "..\\board notes.txt",
        )
        assert display_name == "board notes.txt"
        assert is_managed_path(root, file_path)
        assert file_path.parent == root / "agent-123"
