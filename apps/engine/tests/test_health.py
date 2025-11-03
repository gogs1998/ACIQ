"""Smoke tests for the AccountantIQ engine."""

from accountantiq_engine.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
