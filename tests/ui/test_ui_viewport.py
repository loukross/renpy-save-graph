"""Playwright UI test for graph viewport persistence.

The camera used to be re-applied on every render, so any refresh — a new save
point, a filter toggle — snapped the view back to fit-to-screen and cut short
any centre-on-node animation. Panning must survive a re-render.
"""

import re

import pytest
from playwright.sync_api import expect


def _mock_api(page):
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
                "head": "child1",
                "nodes": [
                    {
                        "sha": "root1", "short": "root1", "parents": [],
                        "subject": "Root Save", "when": 1700000000,
                        "is_head": False, "is_suspect": False,
                    },
                    {
                        "sha": "child1", "short": "child1", "parents": ["root1"],
                        "subject": "Child Save", "when": 1700000100,
                        "is_head": True, "is_suspect": False,
                    },
                ],
            },
        ),
    )
    page.route(
        "**/api/spaces/*/slots/*/states*",
        lambda route: route.fulfill(
            status=200, json={"root1": {"money": 1}, "child1": {"money": 2}}
        ),
    )
    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={"root1": "", "child1": ""}),
    )
    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(status=200, json={"tags": {}, "all_tags": []}),
    )


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_viewport_survives_rerender(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _mock_api(page)

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node")

    container = page.locator("g.graph-container")
    expect(container).to_have_attribute("transform", re.compile(r".+"))
    initial = container.get_attribute("transform")

    # Pan away from the initial fit.
    box = page.locator("#graph-canvas").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 - 120, box["y"] + box["height"] / 2 - 80)
    page.mouse.up()

    panned = container.get_attribute("transform")
    assert panned != initial, "drag did not pan the graph; the test would prove nothing"

    # Force a re-render the way a new save point or filter change would.
    filter_input = page.locator("input[placeholder*='score >= 5']")
    filter_input.fill("money > 0")
    page.keyboard.press("Enter")
    page.wait_for_selector("g.node")

    assert container.get_attribute("transform") == panned, (
        "re-render moved the camera; it must stay where the user left it"
    )
    assert page_errors == [], f"unexpected page errors: {page_errors}"
