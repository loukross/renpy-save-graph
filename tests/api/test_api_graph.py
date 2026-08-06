"""REST API contract tests for graph & states endpoints."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_mock_save_zip


@pytest.mark.api
def test_api_diff_flags_removed_vars_apart_from_null_ones(tmp_workspace, test_client: TestClient):
    """`removed` must distinguish a dropped variable from one set to None.

    Both read back as None through .get(), so the flag is the only way the UI
    can tell "the game stopped tracking this" from "its value is now null".
    """
    space_id, slot = "test-space-id", "1-1-LT1"
    # Root save is {"money": 100, "karma": 0}.  Drop karma, null out money.
    tmp_workspace["slot_file"].write_bytes(create_mock_save_zip({"money": None}, "ch2"))
    assert test_client.post(f"/api/spaces/{space_id}/slots/{slot}/ingest").json()["committed"]

    nodes = test_client.get(f"/api/spaces/{space_id}/slots/{slot}/graph").json()["nodes"]
    child = next(n for n in nodes if n["parents"])
    resp = test_client.get(
        f"/api/spaces/{space_id}/slots/{slot}/diff/{child['parents'][0]}/{child['sha']}"
    )
    assert resp.status_code == 200

    changes = {c["var"]: c for c in resp.json()["changes"]}
    assert changes["karma"]["removed"] is True
    assert changes["money"]["removed"] is False
    assert changes["money"]["new"] is None


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
