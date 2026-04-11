"""GET /api/health/meeting-latency exposure rules."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_latency_metrics_hidden_in_production_by_default() -> None:
    from app.main import app

    with patch("app.main.get_settings") as gs:
        gs.return_value.environment = "production"
        gs.return_value.expose_meeting_latency_metrics = False
        client = TestClient(app)
        r = client.get("/api/health/meeting-latency")
    assert r.status_code == 404


def test_latency_metrics_visible_in_development() -> None:
    from app.main import app

    with patch("app.main.get_settings") as gs:
        gs.return_value.environment = "development"
        gs.return_value.expose_meeting_latency_metrics = False
        client = TestClient(app)
        r = client.get("/api/health/meeting-latency")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_latency_metrics_visible_when_flag_set_in_production() -> None:
    from app.main import app

    with patch("app.main.get_settings") as gs:
        gs.return_value.environment = "production"
        gs.return_value.expose_meeting_latency_metrics = True
        client = TestClient(app)
        r = client.get("/api/health/meeting-latency")
    assert r.status_code == 200
