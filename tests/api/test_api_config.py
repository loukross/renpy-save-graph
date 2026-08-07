"""REST API contract tests for config endpoints."""

import pytest
from fastapi.testclient import TestClient

from renpy_save_graph.library import Library


@pytest.mark.api
def test_api_config(test_client: TestClient):
    resp = test_client.get("/api/config")
    assert resp.status_code == 200
    config_data = resp.json()
    assert "spaces" in config_data
    spaces = config_data["spaces"]
    assert len(spaces) >= 1
    space_ids = [s["id"] for s in spaces]
    assert "test-space-id" in space_ids


@pytest.mark.api
def test_config_patch_publishes_portable_settings_to_the_library(test_client, tmp_workspace):
    resp = test_client.patch(
        "/api/spaces/test-space-id/config",
        json={"milestone_vars": ["chapter"], "saves_dir": "/somewhere/else",
              "filter_history": ["money > 0"]},
    )
    assert resp.status_code == 200

    manifest = Library.init(tmp_workspace["lib_dir"]).read_manifest()
    assert manifest["space"]["milestone_vars"] == ["chapter"]
    # Per-install and personal settings stay out of the shareable copy.
    assert "saves_dir" not in manifest["space"]
    assert "filter_history" not in manifest["space"]
