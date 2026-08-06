"""Playwright UI test for the invalid-lineage expression feature.

A space-level `lineage_validity_expr` is evaluated per node against its
diff from its parent (same JSEP language/semantics as the graph filter:
true = valid, false = flag). Nodes where it evaluates false should get
the 'suspect' CSS class and a visible warning badge; nodes where it
evaluates true should not.
"""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_lineage_validity_expr_flags_failing_node(page, ui_server_url):
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
                        "lineage_validity_expr": "delta('money') >= 0",
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
                "head": "child_bad",
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
                        "sha": "child_good",
                        "short": "child_good",
                        "parents": ["root1"],
                        "subject": "Good Save",
                        "when": 1700000100,
                        "is_head": False,
                        "is_suspect": False,
                    },
                    {
                        "sha": "child_bad",
                        "short": "child_bad",
                        "parents": ["root1"],
                        "subject": "Bad Save",
                        "when": 1700000200,
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
                "root1": {"money": 100},
                "child_good": {"money": 150},
                "child_bad": {"money": 50},
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(
            status=200, json={"root1": "", "child_good": "", "child_bad": ""}
        ),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")

    # Regression: loadAllStates() must scan lineage_validity_expr for
    # identifiers (not just favorite_vars/filter/order-by), or the server's
    # ?vars= filtering silently drops the variable and every delta()/
    # changed() call in the rule evaluates against undefined forever.
    assert any("money" in url for url in states_requests), (
        f"no /states request requested 'money': {states_requests}"
    )

    # child_bad: money dropped 100 -> 50, delta('money') >= 0 is false -> flagged
    assert page.eval_on_selector(
        "g.node.head", "el => el.classList.contains('suspect')"
    )
    assert page.is_visible("text=Invalid lineage")

    # root1 has no parent (no diff to evaluate against) -> not flagged
    all_suspect = page.eval_on_selector_all(
        "g.node.suspect", "els => els.length"
    )
    assert all_suspect == 1
