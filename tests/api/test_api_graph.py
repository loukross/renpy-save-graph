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


@pytest.mark.api
def test_api_tags_endpoints(test_client: TestClient):
    space_id = "test-space-id"
    slot = "1-1-LT1"

    graph_resp = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/graph")
    sha = graph_resp.json()["nodes"][0]["sha"]

    add_resp = test_client.post(f"/api/spaces/{space_id}/slots/{slot}/nodes/{sha}/tags", json={"tag": "boss-fight"})
    assert add_resp.status_code == 200
    assert add_resp.json() == {"ok": True}

    get_resp = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/tags")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert sha in data["tags"]
    assert "boss-fight" in data["tags"][sha]
    assert "boss-fight" in data["all_tags"]

    del_resp = test_client.delete(f"/api/spaces/{space_id}/slots/{slot}/nodes/{sha}/tags/boss-fight")
    assert del_resp.status_code == 200

    get_resp2 = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/tags")
    assert "boss-fight" not in get_resp2.json()["tags"].get(sha, [])
