"""Playwright Web UI tests for floating Auto-select toggle and popovers."""

import pytest
from playwright.sync_api import expect


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_floating_autoselect_button(page, ui_server_url):
    """Test Web UI components using pure Python Playwright network route mocking."""

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
                        "favorite_vars": ["money"],
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
        lambda route: route.fulfill(status=200, json={"sha123": {"money": 100}}),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(
            status=200,
            json={"sha123": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="},
        ),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    expect(page.locator("text=Ren'Py Save Graph").first).to_be_visible()

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")

    autoselect_btn = page.locator("button:has-text('Auto-select on add')")
    expect(autoselect_btn).to_be_visible()
    assert "⚡" not in autoselect_btn.inner_text()

    autoselect_btn.click()
    assert "⚡ Auto-select on add" in autoselect_btn.inner_text()
