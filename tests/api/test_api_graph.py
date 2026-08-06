"""REST API contract tests for graph & states endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_api_graph_endpoint(test_client: TestClient):
    space_id = "test-space-id"
    slot = "1-1-LT1"
    resp = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert len(data["nodes"]) == 1


@pytest.mark.api
def test_api_parameterized_states_endpoint(test_client: TestClient):
    space_id = "test-space-id"
    slot = "1-1-LT1"
    resp = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/states?vars=money,karma")
    assert resp.status_code == 200
    all_states = resp.json()
    assert len(all_states) == 1
    sha = list(all_states.keys())[0]
    assert all_states[sha] == {"money": 100, "karma": 0}


@pytest.mark.api
def test_api_batch_screenshots_endpoint(test_client: TestClient):
    space_id = "test-space-id"
    slot = "1-1-LT1"
    resp = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/screenshots")
    assert resp.status_code == 200
    screenshots = resp.json()
    assert len(screenshots) == 1
    sha = list(screenshots.keys())[0]
    assert screenshots[sha].startswith("data:image/png;base64,")
