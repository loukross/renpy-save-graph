"""Playwright Web UI tests for dynamic JSEP filter expression evaluation."""

import pytest
from playwright.sync_api import expect


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_jsep_expression_evaluator(page, ui_server_url):
    """Test typing valid and invalid JSEP expressions in the filter bar."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

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
        "**/api/spaces/*/slots",
        lambda route: route.fulfill(status=200, json={"slots": ["1-1-LT1"]}),
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

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # The graph filter input only exists in the graph view.
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")

    filter_input = page.locator("input[placeholder*='score >= 5']")
    expect(filter_input).to_be_visible()

    # A valid expression filters without error.
    filter_input.fill("money > 0")
    page.keyboard.press("Enter")
    expect(page.locator("g.node")).to_have_count(1)

    # A malformed expression must be handled, not thrown out of the app.
    filter_input.fill("money > > 0")
    page.keyboard.press("Enter")
    page.wait_for_selector("#graph-canvas")

    assert page_errors == [], f"unexpected page errors: {page_errors}"
