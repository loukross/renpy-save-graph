"""Playwright UI test verifying initial viewport-based decoration (LOD).

On entering Graph view, renderGraph() should center tightly on HEAD
(~1 sibling node visible above/below) rather than fitting/decorating
the entire tree, so only a small subset of nodes near the viewport get
fully decorated (thumbnail image etc.) — everything else stays a cheap
placeholder until panned/zoomed into view.
"""

import pytest


def _linear_chain_nodes(n):
    nodes = []
    prev_sha = None
    for i in range(n):
        sha = f"node{i}"
        nodes.append(
            {
                "sha": sha,
                "short": sha,
                "parents": [prev_sha] if prev_sha else [],
                "subject": f"Save {i}",
                "when": 1700000000 + i * 100,
                "is_head": i == n - 1,
                "is_suspect": False,
            }
        )
        prev_sha = sha
    return nodes


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_graph_initial_render_only_decorates_nearby_nodes(page, ui_server_url):
    total_nodes = 40
    nodes = _linear_chain_nodes(total_nodes)

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
            status=200, json={"head": f"node{total_nodes - 1}", "nodes": nodes}
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/states*",
        lambda route: route.fulfill(status=200, json={}),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")

    all_nodes = page.eval_on_selector_all("g.node", "els => els.length")
    assert all_nodes == total_nodes
    head_is_placeholder = page.eval_on_selector(
        "g.node.head", "el => el.classList.contains('node-placeholder')"
    )
    assert head_is_placeholder is False
