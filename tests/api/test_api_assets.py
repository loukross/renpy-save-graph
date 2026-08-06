"""REST API contract tests for the static asset endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_api_asset_serves_known_file(test_client: TestClient):
    resp = test_client.get("/assets/Octicons-mark-github.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in resp.content


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
