"""Playwright UI test for clicking a real graph node.

Regression coverage for a bug where renderGraph() threw a silent
ReferenceError (a stale `g.graph()` reference left over from the
dagre-d3 -> d3.tree() migration) partway through, aborting execution
before the node click handler was ever attached. None of the other UI
tests click an actual graph node or assert on console/page errors, so
this slipped through the test suite undetected.
"""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_graph_node_click_selects_node(page, ui_server_url):
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
                "head": "child1",
                "nodes": [
                    {
                        "sha": "root1",
                        "short": "root1",
                        "parents": [],
                        "subject": "Root Save",
                        "when": 1700000000,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "child1",
                        "short": "child1",
                        "parents": ["root1"],
                        "subject": "Child Save",
                        "when": 1700000100,
                        "is_head": True,
                        "is_suspect": False,
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
        "**/api/spaces/*/slots/*/state/*",
        lambda route: route.fulfill(status=200, json={"money": 1}),
    )

    page.route(
        "**/api/spaces/*/slots/*/diff/*/*",
        lambda route: route.fulfill(status=200, json={"changes": []}),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")

    page.click("g.node.head")
    page.wait_for_selector("#diff-title >> text=child1")

    assert page_errors == [], f"unexpected page errors: {page_errors}"
