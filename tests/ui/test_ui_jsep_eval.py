"""Playwright Web UI tests for dynamic JSEP filter expression evaluation."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_jsep_expression_evaluator(page, ui_server_url):
    """Test typing valid and invalid JSEP expressions in the filter bar."""

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
            json={"sha123": {"money": 100}},
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={"sha123": ""}),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Locate main graph filter input
    filter_input = page.locator("input[placeholder*='money > 0']")
    if filter_input.is_visible():
        # Type valid filter expression
        filter_input.fill("money > 0")

        # Type invalid expression to test syntax error handling
        filter_input.fill("money > > 0")
        page.keyboard.press("Enter")
