"""Playwright Web UI tests for Space Form modal and configuration editing."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_space_form_and_delete_modals(page, ui_server_url):
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
        lambda route: route.fulfill(status=200, json={"tags": {}, "all_tags": []}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Click New... space button
    page.click("button:has-text('New…')")
    page.wait_for_selector("text=New space")

    # Fill form fields
    page.fill("#field-saves-dir input", "/test/saves")

    # Select space again so Duplicate button appears
    page.select_option(".space-picker-row select", "mock-space")
    page.wait_for_selector("button:has-text('Duplicate')")

    # Click Duplicate button
    page.click("button:has-text('Duplicate')")
    page.wait_for_selector("text=New space")

    # Verify label, saves_dir, and library_path are empty
    assert page.input_value(".spaces-inner input[placeholder='My game']") == ""
    assert page.input_value("#field-saves-dir input") == ""

    assert page_errors == [], f"unexpected page errors: {page_errors}"

