"""Playwright Web UI tests for navigation menus, base sort controls, and jump targets."""

import pytest
from playwright.sync_api import expect


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_navigation_controls(page, ui_server_url):
    """Test clicking Jump to... menu and Base sort direction toggle button."""

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
        "**/api/spaces/*/slots",
        lambda route: route.fulfill(status=200, json={"slots": ["1-1-LT1"]}),
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
        lambda route: route.fulfill(status=200, json={"sha123": {}}),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={"sha123": ""}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Both controls live in the graph view, so get there first.
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")

    # Test Jump to... menu toggle
    jump_btn = page.locator("button:has-text('🎯 Jump to…')")
    expect(jump_btn).to_be_visible()
    jump_btn.click()
    expect(page.locator("text=Current Head").first).to_be_visible()
    expect(page.locator("text=Root").first).to_be_visible()
    page.keyboard.press("Escape")

    # Test Base Sort direction toggle button
    sort_dir_btn = page.locator("button:has-text('↓'), button:has-text('↑')").first
    expect(sort_dir_btn).to_be_visible()
    initial_text = sort_dir_btn.inner_text()
    sort_dir_btn.click()
    expect(sort_dir_btn).not_to_have_text(initial_text)
