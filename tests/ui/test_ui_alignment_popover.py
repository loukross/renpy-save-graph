"""Playwright Web UI tests for Multi-Alignment Popover Box."""

import pytest


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_alignment_popover_toggling(page, ui_server_url):
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
        lambda route: route.fulfill(status=200, json={"sha123": {"currentEpisode": 1}}),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={"sha123": ""}),
    )

    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(
            status=200,
            json={"tags": {"sha123": ["boss-fight"]}, "all_tags": ["boss-fight"]},
        ),
    )

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Navigate to Graph view
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")

    # Open Multi-Alignment Popover
    page.click("#btn-alignment-popover")
    page.wait_for_selector("text=Horizontal Alignment Options")

    # Verify Story Variable button currentEpisode and Tag button #boss-fight exist inside popover
    assert page.is_visible("div:has-text('Horizontal Alignment Options') button:has-text('currentEpisode')")
    assert page.is_visible("div:has-text('Horizontal Alignment Options') button:has-text('#boss-fight')")

    # Toggle currentEpisode ON
    page.click("div:has-text('Horizontal Alignment Options') button:has-text('currentEpisode')")

    # Verify alignment button label updates
    assert "currentEpisode" in page.inner_text("#btn-alignment-popover")

    # Reset alignments
    page.click("button:has-text('Natural Depth (Reset)')")
    assert "None (tree depth)" in page.inner_text("#btn-alignment-popover")

    assert page_errors == [], f"unexpected page errors: {page_errors}"
