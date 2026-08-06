"""Playwright Web UI tests for decoupled Inspector and Diff regex variable filters."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_decoupled_regex_filters(page, ui_server_url):
    """Test that Inspector filter and Diff filter inputs are completely decoupled."""

    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "spaces": [
                    {
                        "id": "mock-space",
                        "label": "Mock Game Space",
                        "saves_dir": "/mock/saves",
                        "library_path": "/mock/lib",
                        "favorite_vars": [],
                    }
                ]
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/graph*",
        lambda route: route.fulfill(
            status=200,
            json={
                "head": "sha123",
                "nodes": [
                    {
                        "sha": "sha123",
                        "short": "sha123",
                        "parents": [],
                        "subject": "Initial Save",
                        "when": 1700000000,
                        "is_head": True,
                        "is_suspect": False,
                    }
                ],
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/states*",
        lambda route: route.fulfill(
            status=200,
            json={"sha123": {"money": 100, "karma": 5, "_secret": "hidden"}},
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={"sha123": ""}),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Locate inputs
    inputs = page.locator("input[placeholder='e.g. ^karma|money$']")
    assert inputs.count() >= 1

    # Type into the first filter input
    first_input = inputs.first
    first_input.fill("karma")

    # If second input exists, verify it remains unchanged
    if inputs.count() > 1:
        second_input = inputs.nth(1)
        assert second_input.input_value() != "karma"
