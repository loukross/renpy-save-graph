"""REST API contract tests for the frontend static asset mount."""

import pytest
from fastapi.testclient import TestClient

from renpy_save_graph.server import _ASSETS_DIR


@pytest.mark.api
def test_api_asset_serves_built_bundle(test_client: TestClient):
    # Vite content-hashes filenames, so discover whatever the current build
    # produced rather than hardcoding one.
    built_files = list(_ASSETS_DIR.glob("*.js")) + list(_ASSETS_DIR.glob("*.css"))
    assert built_files, f"no built frontend assets found in {_ASSETS_DIR} — run `npm run build`"

    for path in built_files:
        resp = test_client.get(f"/assets/{path.name}")
        assert resp.status_code == 200
        expected_type = "text/css" if path.suffix == ".css" else "javascript"
        assert expected_type in resp.headers["content-type"]


@pytest.mark.api
def test_api_asset_unknown_file_404s(test_client: TestClient):
    resp = test_client.get("/assets/does-not-exist.svg")
    assert resp.status_code == 404


@pytest.mark.api
def test_api_asset_rejects_directory_traversal(test_client: TestClient):
    # URL-encoded so the client doesn't collapse the ".." itself before
    # the request ever reaches the server's routing.
    resp = test_client.get("/assets/%2e%2e")
    assert resp.status_code == 404

    resp = test_client.get("/assets/%2e%2e%2fserver.py")
    assert resp.status_code == 404
