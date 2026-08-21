"""Playwright UI test for editing a node note.

Saving a note repaints just that node, so the text has to appear without a
graph reload: the graph endpoint is served once and any second call fails the
test.
"""

import pytest
from playwright.sync_api import expect


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_note_shows_without_reload(page, ui_server_url):
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

    graph_calls = []
    page.route(
        "**/api/spaces/*/slots/*/graph*",
        lambda route: graph_calls.append(route.request.url)
        or route.fulfill(
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

    saved_notes = []
    page.route(
        "**/api/spaces/*/slots/*/note/*",
        lambda route: saved_notes.append(route.request.post_data_json)
        or route.fulfill(status=200, json={"ok": True}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node-pencil")
    graphs_before = len(graph_calls)

    page.click("g.node-pencil")
    page.wait_for_selector("#note-overlay textarea")
    page.fill("#note-overlay textarea", "went left at the fork")
    page.keyboard.press("Enter")

    expect(page.locator("foreignObject.node-note")).to_have_text("went left at the fork")
    expect(page.locator("#note-overlay")).to_have_count(0)
    assert saved_notes == [{"text": "went left at the fork"}]
    assert len(graph_calls) == graphs_before, "note edit triggered a graph reload"
    assert page_errors == [], f"unexpected page errors: {page_errors}"
