"""Milestone guide columns must leave room for saves that didn't advance."""

import pytest


def _node(sha, parents, subject):
    return {
        "sha": sha,
        "short": sha,
        "parents": parents,
        "subject": subject,
        "when": 1700000000,
        "is_head": sha == "ep6",
        "is_suspect": False,
    }


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_same_episode_saves_stay_left_of_next_guide(page, ui_server_url):
    """r(ep5) -> a(ep5) -> b(ep5), and r -> c(ep6) on a sibling branch.

    a and b don't advance currentEpisode, so they get no milestone key and just
    take parent+1. The ep6 column is only pushed past them if its target depth
    accounts for that run — otherwise they render on or past the ep6 guide.
    """
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
                        "milestone_vars": ["currentEpisode"],
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
                "head": "ep6",
                "nodes": [
                    _node("r", [], "Episode 5 begins"),
                    _node("a", ["r"], "Still episode 5"),
                    _node("b", ["a"], "Still episode 5, later"),
                    _node("ep6", ["r"], "Episode 6 begins"),
                ],
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/states*",
        lambda route: route.fulfill(
            status=200,
            json={
                "r": {"currentEpisode": 5},
                "a": {"currentEpisode": 5},
                "b": {"currentEpisode": 5},
                "ep6": {"currentEpisode": 6},
            },
        ),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={}),
    )

    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(status=200, json={"tags": {}, "all_tags": []}),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")

    page.click("#btn-alignment-popover")
    page.wait_for_selector("text=Horizontal Alignment Options")
    page.click("div:has-text('Horizontal Alignment Options') button:has-text('currentEpisode')")
    # A vertical <line> has a zero-width bbox, so it is never "visible".
    page.wait_for_selector("g.milestone-guides line.guide-line", state="attached")

    layout = page.evaluate(
        """() => {
          const nodes = {};
          document.querySelectorAll('#graph g.node').forEach(g => {
            nodes[g.__data__.data.sha] = g.transform.baseVal[0].matrix.e;
          });
          const guides = {};
          document.querySelectorAll('#graph text.guide-label-top').forEach(t => {
            guides[t.textContent] = parseFloat(t.getAttribute('x'));
          });
          return { nodes, guides };
        }"""
    )

    nodes, guides = layout["nodes"], layout["guides"]
    ep6_guide = guides["currentEpisode: 6"]

    # The ep6 node itself owns the ep6 column; the guide sits just left of it.
    assert nodes["ep6"] > ep6_guide

    # Every save still in episode 5 must render left of the episode 6 guide.
    for sha in ("r", "a", "b"):
        assert nodes[sha] < ep6_guide, (
            f"{sha} (currentEpisode 5) at x={nodes[sha]} is not left of the "
            f"currentEpisode: 6 guide at x={ep6_guide}"
        )

    assert page_errors == [], f"unexpected page errors: {page_errors}"
