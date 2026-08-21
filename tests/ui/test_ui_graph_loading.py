"""The graph canvas must not claim a space is empty while it is still loading."""

import pytest
from playwright.sync_api import expect


# Hold the ingest call open from inside the page. Blocking a Playwright route
# handler instead would stall the driver's own dispatcher, not just the request.
HOLD_INGEST = """
const orig = window.fetch;
window.__releaseIngest = null;
window.fetch = function (url, opts) {
  if (String(url).includes('/ingest')) {
    return new Promise(resolve => {
      window.__releaseIngest = () => resolve(orig(url, opts));
    });
  }
  return orig(url, opts);
};
"""

NODE = {
    "sha": "sha123",
    "short": "sha123",
    "parents": [],
    "subject": "Initial Save",
    "when": 1700000000,
    "is_head": True,
    "is_suspect": False,
}


def _routes(page, nodes):
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

    page.route(
        "**/api/spaces/*/ingest",
        lambda route: route.fulfill(status=200, json={"ok": True}),
    )
    page.route(
        "**/api/spaces/*/slots",
        lambda route: route.fulfill(status=200, json={"slots": ["1-1-LT1"]}),
    )
    page.route(
        "**/api/spaces/*/slots/*/graph*",
        lambda route: route.fulfill(status=200, json={"head": "sha123", "nodes": nodes}),
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


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_no_empty_message_while_loading(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    _routes(page, [NODE])

    page.add_init_script(HOLD_INGEST)
    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")
    page.wait_for_selector("#graph-canvas")
    page.wait_for_function("window.__releaseIngest !== null")

    # Held inside the ingest, so the graph has not arrived: the canvas must not
    # claim the space is empty, and the wait must read as a wait.
    assert "No saves yet" not in page.inner_text("#graph-canvas")
    expect(page.locator(".loading")).to_be_visible()

    page.evaluate("window.__releaseIngest()")
    expect(page.locator("#graph g.node")).to_have_count(1)
    assert "No saves yet" not in page.inner_text("#graph-canvas")

    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_empty_message_still_shows_for_a_genuinely_empty_space(page, ui_server_url):
    """The message must still appear once an empty graph has actually loaded."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    _routes(page, [])

    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")
    page.click("button:has-text('Graph')")

    expect(page.locator("#graph-canvas")).to_contain_text("No saves yet")

    assert page_errors == [], f"unexpected page errors: {page_errors}"
