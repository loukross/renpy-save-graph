"""Playwright UI tests for how often, and how much, the graph redraws.

Rebuilding every node is the dominant interaction cost, so these pin down that
the camera survives a redraw, that selecting restyles instead of rebuilding,
and that opening a graph draws it once rather than once per response.
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


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_selecting_a_node_does_not_redraw_the_graph(page, ui_server_url):
    """Selection is a restyle, not a rebuild.

    Selecting used to sit in the render watcher, so one click tore down and
    rebuilt every node — the dominant cost in Interaction to Next Paint.
    """
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _mock_api(page)
    page.route(
        "**/api/spaces/*/slots/*/state/*",
        lambda route: route.fulfill(status=200, json={"variables": {"money": 1}}),
    )
    page.route(
        "**/api/spaces/*/slots/*/diff/*/*",
        lambda route: route.fulfill(status=200, json={"changes": []}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")

    mark = """() => {
        const ns = document.querySelectorAll('g.node');
        ns.forEach(n => n.setAttribute('data-probe', '1'));
        return ns.length;
    }"""
    probed = "g.node[data-probe='1']"

    # The states and tags fetches each redraw once on load. Re-mark until the
    # marks survive, so a load-time redraw can't be mistaken for the click's.
    for _ in range(20):
        assert page.evaluate(mark) == 2
        page.wait_for_timeout(100)
        if page.locator(probed).count() == 2:
            break
    else:
        pytest.fail("graph never stopped redrawing after load")

    page.click("g.node.head")
    page.wait_for_selector("g.node.selected")

    assert page.locator(probed).count() == 2, (
        "selecting a node rebuilt the graph; it should only restyle"
    )
    expect(page.locator("g.node.selected")).to_have_count(1)
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_opening_a_graph_draws_it_once(page, ui_server_url):
    """Opening a graph fetches it once and draws it a bounded number of times.

    Graph, states and tags used to be assigned as each response landed, and
    openGraph raced the selectedSlot watcher into loading everything twice —
    together four rebuilds of every node on the Spaces -> Graph transition.
    """
    _mock_api(page)
    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Count every <g class="node"> ever added, across component remounts.
    page.evaluate(
        """() => {
            window.__nodesDrawn = 0;
            new MutationObserver(muts => {
                for (const m of muts) {
                    for (const n of m.addedNodes) {
                        if (n.tagName === 'g' && n.classList.contains('node')) {
                            window.__nodesDrawn++;
                        }
                    }
                }
            }).observe(document.body, { childList: true, subtree: true });
        }"""
    )

    graph_reqs = []
    page.on("request", lambda r: graph_reqs.append(r.url) if "/graph?" in r.url else None)

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_selector("g.node.head")
    page.wait_for_timeout(600)

    assert len(graph_reqs) == 1, f"graph fetched {len(graph_reqs)}x, expected once"

    # 2 nodes per draw: one draw commits the data, one comes from the remount
    # GraphCanvas does when its space+slot :key changes. Anything beyond that
    # means a response is redrawing the graph on its own again.
    drawn = page.evaluate("window.__nodesDrawn")
    assert drawn <= 4, f"expected at most 2 draws, got {drawn / 2}"
