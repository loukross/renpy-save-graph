"""Playwright UI test for the Route Targets graph feature.

A space-level `route_targets` list ({"name", "expr"}) is evaluated
root-to-leaf per selected target (same JSEP language as the graph filter).
The first node along a branch whose own diff breaks a selected target is
the divergence point: it stays visible with a "Suboptimal for <name>"
badge. With "Hide off-track subtrees" on (the default), every descendant
of that node is pruned from the rendered graph and the divergence node
gets a "(suboptimal tree hidden)" stub; with hiding off, all nodes stay
visible and no stub is drawn.
"""

import pytest
from playwright.sync_api import expect


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_route_target_prunes_and_toggles(page, ui_server_url):
    states_requests = []
    page.on(
        "request",
        lambda req: states_requests.append(req.url) if "/states" in req.url else None,
    )

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
                        "route_targets": [
                            {"name": "Route A", "expr": "delta('points') >= 0"}
                        ],
                    }
                ]
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots",
        lambda route: route.fulfill(status=200, json={"slots": ["1-1-LT1"]}),
    )

    # root -> A (points +10, ok) -> B (points -5, BREAKS) -> C -> D (head)
    page.route(
        "**/api/spaces/*/slots/*/graph*",
        lambda route: route.fulfill(
            status=200,
            json={
                "head": "D",
                "nodes": [
                    {
                        "sha": "root",
                        "short": "root",
                        "parents": [],
                        "subject": "Root",
                        "when": 1700000000,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "A",
                        "short": "A",
                        "parents": ["root"],
                        "subject": "A",
                        "when": 1700000100,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "B",
                        "short": "B",
                        "parents": ["A"],
                        "subject": "B",
                        "when": 1700000200,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "C",
                        "short": "C",
                        "parents": ["B"],
                        "subject": "C",
                        "when": 1700000300,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "D",
                        "short": "D",
                        "parents": ["C"],
                        "subject": "D",
                        "when": 1700000400,
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
            status=200,
            json={
                "root": {"points": 0},
                "A": {"points": 10},
                "B": {"points": 5},
                "C": {"points": 6},
                "D": {"points": 20},
            },
        ),
    )

    # Empty screenshots map forces every node to fall back to fetching the
    # singular per-sha screenshot route, which also needs mocking or it
    # would hit the real (unmocked) backend.
    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={}),
    )
    page.route(
        "**/api/spaces/*/slots/*/screenshot/*",
        lambda route: route.fulfill(status=200, body=b"", content_type="image/png"),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")

    # Initial state: no route target selected, nothing pruned or badged.
    assert page.eval_on_selector_all("g.node", "els => els.length") == 5
    assert page.eval_on_selector_all(".route-target-badge", "els => els.length") == 0
    assert page.eval_on_selector_all(".hidden-subtree-stub", "els => els.length") == 0

    # Select "Route A".
    page.click("#btn-route-target-popover")
    page.click(".popover-option-btn:has-text('Route A')")
    page.wait_for_function("document.querySelectorAll('g.node').length === 3")

    # root, A, B remain; C and D (descendants of the divergence point) are pruned.
    assert page.eval_on_selector_all("g.node", "els => els.length") == 3

    badge_text = page.eval_on_selector(".route-target-badge", "el => el.textContent")
    assert "Suboptimal for" in badge_text
    assert "Route A" in badge_text

    assert page.eval_on_selector_all(".hidden-subtree-stub", "els => els.length") == 1
    expect(page.locator("text=(suboptimal tree hidden)").first).to_be_visible()

    # Regression guard: loadAllStates() must scan route_targets expressions
    # for identifiers too, or the server's ?vars= filtering silently drops
    # the variable and delta('points') evaluates against undefined forever
    # — meaning nothing ever diverges and this whole feature no-ops.
    assert any("points" in url for url in states_requests), (
        f"no /states request requested 'points': {states_requests}"
    )

    # Uncheck "Hide off-track subtrees" — pruning turns off, everything
    # renders again, but only B (the divergence point) still carries the
    # badge, and the hidden-subtree stub disappears since nothing is hidden.
    page.click("label:has-text('Hide off-track subtrees') input[type=checkbox]")
    page.wait_for_function("document.querySelectorAll('g.node').length === 5")

    assert page.eval_on_selector_all("g.node", "els => els.length") == 5
    assert page.eval_on_selector_all(".route-target-badge", "els => els.length") == 1
    assert page.eval_on_selector_all(".hidden-subtree-stub", "els => els.length") == 0
