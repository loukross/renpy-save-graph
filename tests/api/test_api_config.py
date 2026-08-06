"""REST API contract tests for config endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_api_config(test_client: TestClient):
    resp = test_client.get("/api/config")
    assert resp.status_code == 200
    config_data = resp.json()
    assert "spaces" in config_data
    spaces = config_data["spaces"]
    assert len(spaces) == 1
    assert spaces[0]["id"] == "test-space-id"
