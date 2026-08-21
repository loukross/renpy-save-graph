"""Graph view alignment/sort/filter choices survive an app reload."""

import pytest
from playwright.sync_api import expect


def _routes(page):
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
        lambda route: route.fulfill(status=200, json={}),
    )
    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(
            status=200,
            json={"tags": {"sha123": ["boss-fight"]}, "all_tags": ["boss-fight"]},
        ),
    )


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_view_prefs_resume_after_reload(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _routes(page)

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#sort-filter-bar")

    sort_dir = page.locator("#sort-filter-bar button[title='Ascending'], #sort-filter-bar button[title='Descending']")
    filter_input = page.locator("#sort-filter-bar input[placeholder^='e.g. score >=']")

    starting_dir = sort_dir.get_attribute("title")

    # Alignment on, sort direction flipped, filter applied.
    page.click("#btn-alignment-popover")
    page.wait_for_selector("text=Horizontal Alignment Options")
    page.click("div:has-text('Horizontal Alignment Options') button:has-text('currentEpisode')")
    page.click("#btn-alignment-popover")  # close the popover

    sort_dir.click()
    flipped_dir = "Descending" if starting_dir == "Ascending" else "Ascending"
    expect(sort_dir).to_have_attribute("title", flipped_dir)

    filter_input.fill("currentEpisode >= 1")
    page.click("#sort-filter-bar button:has-text('Filter')")
    expect(page.locator("#sort-filter-bar button:has-text('Clear')")).to_be_visible()

    # Reload the app and walk back into the graph.
    page.reload()
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#sort-filter-bar")

    assert "currentEpisode" in page.inner_text("#btn-alignment-popover")
    expect(
        page.locator("#sort-filter-bar button[title='Ascending'], #sort-filter-bar button[title='Descending']")
    ).to_have_attribute("title", flipped_dir)
    expect(page.locator("#sort-filter-bar input[placeholder^='e.g. score >=']")).to_have_value(
        "currentEpisode >= 1"
    )
    # An applied filter stays applied, not just typed into the box.
    expect(page.locator("#sort-filter-bar button:has-text('Clear')")).to_be_visible()

    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_view_prefs_do_not_leak_between_spaces(page, ui_server_url):
    """Prefs name a space's own variables, so they must be keyed per space."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _routes(page)
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
                    },
                    {
                        "id": "other-space",
                        "label": "Other Game Space",
                        "saves_dir": "/mock/saves2",
                        "library_path": "/mock/lib2",
                        "milestone_vars": ["chapter"],
                        "favorite_vars": [],
                    },
                ]
            },
        ),
    )

    page.add_init_script(
        "localStorage.setItem('renpy_save_graph_view_prefs', JSON.stringify({"
        "'mock-space': {selectedAlignments: ['currentEpisode'],"
        " filterExpr: 'currentEpisode >= 1', appliedFilterExpr: 'currentEpisode >= 1',"
        " filterActive: true}}))"
    )
    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    # Visit the space that has prefs, so they are live in the session...
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#sort-filter-bar")
    assert "currentEpisode" in page.inner_text("#btn-alignment-popover")

    # ...then switch to a space that has none. Its view must come up clean.
    page.click("button:has-text('Spaces')")
    page.wait_for_selector("#spaces-view select")
    page.select_option("#spaces-view select", "other-space")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#sort-filter-bar")

    assert "None (tree depth)" in page.inner_text("#btn-alignment-popover")
    expect(page.locator("#sort-filter-bar input[placeholder^='e.g. score >=']")).to_have_value("")
    expect(page.locator("#sort-filter-bar button:has-text('Clear')")).to_have_count(0)

    assert page_errors == [], f"unexpected page errors: {page_errors}"
