"""Meeting link validation helpers."""

from __future__ import annotations

from urllib.parse import urlparse


_SUPPORTED_HOSTS: dict[str, tuple[str, ...]] = {
    "zoom": ("zoom.us", "zoom.com"),
    "teams": ("teams.microsoft.com", "teams.live.com"),
    "meet": ("meet.google.com",),
}


def _matches_host(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def detect_meeting_platform(meeting_link: str) -> str:
    """Return the supported meeting platform for *meeting_link*."""
    raw_link = meeting_link.strip()
    parsed = urlparse(raw_link)
    host = (parsed.hostname or "").strip(".").lower()

    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Meeting link must be a valid http(s) URL.")

    for platform, domains in _SUPPORTED_HOSTS.items():
        if any(_matches_host(host, domain) for domain in domains):
            return platform

    raise ValueError(
        "Unsupported meeting platform. Provide a Zoom, Teams, or Google Meet link."
    )
