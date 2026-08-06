"""Playwright Web UI tests for tag creation, tag pills, and tag deletion."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_tag_creation_and_deletion(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    tags_db = {"sha123": ["boss-fight"]}
    all_tags = ["boss-fight"]

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

    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(
            status=200,
            json={"tags": tags_db, "all_tags": all_tags},
        ),
    )

    added_tags = []
    page.route(
        "**/api/spaces/*/slots/*/nodes/*/tags",
        lambda route: added_tags.append(route.request.post_data_json) or route.fulfill(status=200, json={"ok": True}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Navigate to Graph view
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector(".node-tag-manager")

    # Verify existing tag pill #boss-fight is rendered
    assert page.is_visible("text=#boss-fight")

    # Click +tag pill to create new tag
    page.click(".node-tag-manager >> text=+tag")
    page.wait_for_selector(".node-tag-manager input")

    # Type new tag name and press Enter
    page.fill(".node-tag-manager input", "ending-a")
    page.keyboard.press("Enter")

    # Verify POST request payload
    assert any(req and req.get("tag") == "ending-a" for req in added_tags)
    assert page_errors == [], f"unexpected page errors: {page_errors}"
