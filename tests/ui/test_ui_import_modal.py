"""Playwright Web UI tests for the Import library modal."""

import pytest
from playwright.sync_api import expect

MOCK_CONFIG = {
    "spaces": [
        {
            "id": "mock-space",
            "label": "Mock Game Space",
            "saves_dir": "/mock/saves",
            "library_path": "/mock/lib",
            "favorite_vars": [],
        }
    ]
}


def _open_spaces_view(page, ui_server_url):
    page.route("**/api/config", lambda route: route.fulfill(status=200, json=MOCK_CONFIG))
    page.add_init_script("localStorage.setItem('renpy_save_graph_tour_seen', 'true')")
    page.goto(ui_server_url)
    page.wait_for_selector("#app")


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_import_modal_reports_an_invalid_library(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _open_spaces_view(page, ui_server_url)

    page.route(
        "**/api/library/inspect*",
        lambda route: route.fulfill(
            status=200, json={"ok": False, "error": "Not a git repository."}
        ),
    )

    page.click("button:has-text('Import…')")
    page.wait_for_selector("text=Import library")
    page.fill(".modal input[placeholder='/path/to/cloned-library']", "/not/a/library")
    # Tab out rather than dispatching `change` by hand: a synthetic event leaves
    # the input dirty, so the browser fires a real one later and re-inspects.
    page.press(".modal input[placeholder='/path/to/cloned-library']", "Tab")

    page.wait_for_selector("text=Not a git repository.")
    # Nothing to import, so step 1 will not advance.
    expect(page.locator(".modal-footer button:has-text('Next')")).to_be_disabled()
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_browse_sits_above_import_and_cancels_independently(page, ui_server_url):
    """Both modals share an overlay z-index, so template order alone would put
    Browse behind Import -- and clicks meant for it would hit Import's backdrop
    and dismiss the whole thing."""
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _open_spaces_view(page, ui_server_url)

    page.click("button:has-text('Import…')")
    page.click(".modal button:has-text('Browse…')")
    page.wait_for_selector("text=Select folder")

    picker = page.locator(".picker-overlay")
    expect(picker).to_be_visible()
    # Whatever is under the picker's own area has to be the picker.
    box = picker.locator(".modal").bounding_box()
    topmost = page.evaluate(
        "([x, y]) => document.elementFromPoint(x, y).closest('.modal-overlay').className",
        [box["x"] + box["width"] / 2, box["y"] + 10],
    )
    assert "picker-overlay" in topmost, f"picker is not on top: {topmost}"

    page.click(".picker-overlay .modal-footer button:has-text('Cancel')")
    expect(picker).to_be_hidden()
    expect(page.locator("text=Import library")).to_be_visible()
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_import_modal_asks_for_one_folder_per_save_location(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _open_spaces_view(page, ui_server_url)

    page.route(
        "**/api/library/inspect*",
        lambda route: route.fulfill(status=200, json={
            "ok": True,
            "slots": ["1-1-LT1"],
            "save_dir_count": 2,
            "nodes_per_save_dir": {"0": 216, "1": 108},
            "space": {"label": "Imported Game"},
        }),
    )

    page.click("button:has-text('Import…')")
    page.fill(".modal input[placeholder='/path/to/cloned-library']", "/cloned/lib")
    page.press(".modal input[placeholder='/path/to/cloned-library']", "Tab")

    page.wait_for_selector("text=Uses 2 save locations.")
    assert page.locator(".modal input[placeholder='/path/to/game/saves']").count() == 2
    assert page.locator("text=216 save points").count() == 1
    # The label comes from the library's own manifest.
    assert page.input_value(".modal input[placeholder='My game']") == "Imported Game"

    # Step 1 will not advance until every location has a folder.
    next_btn = page.locator(".modal-footer button:has-text('Next')")
    expect(next_btn).to_be_disabled()
    page.fill(".modal input[placeholder='/path/to/game/saves'] >> nth=0", "/game/s1")
    page.fill(".modal input[placeholder='/path/to/game/saves'] >> nth=1", "/game/s3")
    expect(next_btn).to_be_enabled()

    assert page_errors == [], f"unexpected page errors: {page_errors}"


def _reach_step_two(page, slots):
    """Fill in step 1 with a stubbed library and continue to the review page."""
    page.route(
        "**/api/library/inspect*",
        lambda route: route.fulfill(status=200, json={
            "ok": True, "slots": ["1-1-LT1"], "save_dir_count": 1,
            "nodes_per_save_dir": {"0": 3}, "space": {"label": "Imported Game"},
        }),
    )
    page.route(
        "**/api/library/plan",
        lambda route: route.fulfill(status=200, json={"slots": slots}),
    )
    page.click("button:has-text('Import…')")
    page.fill(".modal input[placeholder='/path/to/cloned-library']", "/cloned/lib")
    page.press(".modal input[placeholder='/path/to/cloned-library']", "Tab")
    page.fill(".modal input[placeholder='/path/to/game/saves']", "/game/s1")
    page.click(".modal-footer button:has-text('Next')")


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_wizard_finishes_straight_away_when_nothing_is_overwritten(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _open_spaces_view(page, ui_server_url)

    _reach_step_two(page, [{"slot": "1-1-LT1", "target": "/game/s1/1-1-LT1.save",
                            "occupied": False}])

    expect(page.locator("text=No existing saves will be overwritten.")).to_be_visible()
    expect(page.locator(".modal-footer button:has-text('Finish')")).to_be_enabled()
    assert page_errors == [], f"unexpected page errors: {page_errors}"


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_wizard_needs_approval_before_overwriting(page, ui_server_url):
    page_errors = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    _open_spaces_view(page, ui_server_url)

    _reach_step_two(page, [{"slot": "1-1-LT1", "target": "/game/s1/1-1-LT1.save",
                            "occupied": True}])

    expect(page.locator(".modal-body")).to_contain_text("/game/s1/1-1-LT1.save")
    finish = page.locator(".modal-footer button:has-text('Finish')")
    expect(finish).to_be_disabled()

    page.check(".modal input[type=checkbox]")
    expect(finish).to_be_enabled()

    # Back returns to step 1 with the folders still filled in.
    page.click(".modal-footer button:has-text('Back')")
    assert page.input_value(".modal input[placeholder='/path/to/game/saves']") == "/game/s1"
    assert page_errors == [], f"unexpected page errors: {page_errors}"
