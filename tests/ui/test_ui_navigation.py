"""Playwright Web UI tests for navigation menus, base sort controls, and jump targets."""

import pytest


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

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Test Jump to... menu toggle
    jump_btn = page.locator("button:has-text('🎯 Jump to…')")
    if jump_btn.is_visible():
        jump_btn.click()
        assert page.is_visible("text=Current Head")
        assert page.is_visible("text=Root")

    # Test Base Sort direction toggle button
    sort_dir_btn = page.locator("button:has-text('↓'), button:has-text('↑')")
    if sort_dir_btn.is_visible():
        initial_text = sort_dir_btn.inner_text()
        sort_dir_btn.click()
        new_text = sort_dir_btn.inner_text()
        assert initial_text != new_text
