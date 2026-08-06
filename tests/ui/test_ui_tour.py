"""Playwright Web UI tests for interactive Driver.js tour."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_interactive_tour(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.route(
        "**/api/examples/reset",
        lambda route: route.fulfill(status=200, json={"ok": True}),
    )

    page.route(
        "**/api/config",
        lambda route: route.fulfill(
            status=200,
            json={
                "spaces": [
                    {
                        "id": "example-space",
                        "label": "Example Game Space",
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
                        "subject": "Crossroads",
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

    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(status=200, json={"tags": {}, "all_tags": []}),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Click 🎓 Tour button in header
    page.click("button:has-text('🎓 Tour')")

    # Verify Driver.js tour popover opens with title
    page.wait_for_selector(".driver-popover")
    assert page.is_visible("text=Welcome to Ren'Py Save Graph!")

    assert page_errors == [], f"unexpected page errors: {page_errors}"
