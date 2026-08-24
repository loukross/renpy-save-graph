"""Reloading the graph must only re-scan the saves dirs when it could help.

Scanning and hashing every save file across the watched dirs is the slowest
thing the app does. Doing it on a pure view change, or on a reload triggered by
work we just did ourselves, is pure latency — the watcher's own commit
notification is exactly that case: it fires *because* the ingest already ran.
"""

import pytest
from playwright.sync_api import expect


# The app opens a real EventSource; swap it for one the test can drive.
FAKE_SSE = """
window.__es = null;
class FakeEventSource {
  constructor(url) { this.url = url; this.onmessage = null; window.__es = this; }
  close() {}
}
window.EventSource = FakeEventSource;
"""

NODES = [
    {
        "sha": "sha123",
        "short": "sha123",
        "parents": [],
        "subject": "Initial Save",
        "when": 1700000000,
        "is_head": True,
        "is_suspect": False,
    },
]


def _setup(page):
    """Wire up the mock API and return the list that records ingest POSTs."""
    ingests = []

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
                        "milestone_vars": [],
                        "favorite_vars": [],
                    }
                ]
            },
        ),
    )

    def ingest(route):
        ingests.append(route.request.method)
        route.fulfill(status=200, json={"count": 0})

    page.route("**/api/spaces/*/ingest", ingest)
    page.route(
        "**/api/spaces/*/slots",
        lambda route: route.fulfill(status=200, json={"slots": ["1-1-LT1"]}),
    )
    page.route(
        "**/api/spaces/*/slots/*/graph*",
        lambda route: route.fulfill(status=200, json={"head": "sha123", "nodes": NODES}),
    )
    page.route(
        "**/api/spaces/*/slots/*/states*",
        lambda route: route.fulfill(status=200, json={}),
    )
    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(status=200, json={}),
    )
    page.route(
        "**/api/spaces/*/slots/*/tags",
        lambda route: route.fulfill(status=200, json={"tags": {}, "all_tags": []}),
    )
    return ingests


def _open_graph(page, ui_server_url):
    page.add_init_script(FAKE_SSE)
    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    expect(page.locator("#graph g.node")).to_have_count(1)


@pytest.mark.ui
@pytest.mark.playwright
def test_watcher_commit_reload_does_not_re_ingest(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    ingests = _setup(page)

    _open_graph(page, ui_server_url)
    # Opening a graph does scan: it catches saves made while the app was closed.
    assert len(ingests) == 1
    page.wait_for_function("window.__es !== null")

    ingests.clear()
    page.evaluate(
        """() => window.__es.onmessage({ data: JSON.stringify({
             committed: true, slot: '1-1-LT1', sha: 'sha123',
             short: 'sha123', subject: 'Initial Save',
           }) })"""
    )
    expect(page.locator(".toast")).to_contain_text("Auto-committed")
    expect(page.locator("#graph g.node")).to_have_count(1)

    assert ingests == [], f"watcher-driven reload re-ingested: {ingests}"
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_view_only_changes_do_not_re_ingest(page, ui_server_url):
    """Sorting and filtering re-fetch the graph; no save file can have changed."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    ingests = _setup(page)

    _open_graph(page, ui_server_url)
    ingests.clear()

    sort_dir = page.locator(
        "#sort-filter-bar button[title='Ascending'], #sort-filter-bar button[title='Descending']"
    )
    starting = sort_dir.get_attribute("title")
    sort_dir.click()
    expect(sort_dir).to_have_attribute(
        "title", "Descending" if starting == "Ascending" else "Ascending"
    )

    page.click("#btn-alignment-popover")
    page.wait_for_selector("text=Horizontal Alignment Options")
    page.click("button:has-text('Natural Depth (Reset)')")
    expect(page.locator("#graph g.node")).to_have_count(1)

    assert ingests == [], f"view-only change re-ingested: {ingests}"
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_refresh_button_still_ingests(page, ui_server_url):
    """The explicit go-look button must keep scanning."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    ingests = _setup(page)

    _open_graph(page, ui_server_url)
    ingests.clear()

    page.click("button:has-text('Refresh')")
    expect(page.locator("#graph g.node")).to_have_count(1)

    assert ingests == ["POST"], f"Refresh should scan, got {ingests}"
    assert page_errors == [], f"unexpected page errors: {page_errors}"
