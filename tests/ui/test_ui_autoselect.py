"""Playwright Web UI tests for floating Auto-select toggle and popovers."""

import threading
import time
import pytest
from uvicorn import Config, Server
from renpy_save_graph.server import create_app


@pytest.fixture(scope="module")
def ui_server_url(tmp_path_factory):
    """Fixture to launch a lightweight background server serving ui.html."""
    tmp_path = tmp_path_factory.mktemp("ui_server_test")
    cfg_file = tmp_path / "config.json"

    from renpy_save_graph.config import AppConfig, GameSpace

    space = GameSpace(
        id="mock-space",
        label="Mock Game Space",
        saves_dir=str(tmp_path / "saves"),
        library_path=str(tmp_path / "lib"),
        favorite_vars=["money"],
    )
    AppConfig(spaces=[space]).save(cfg_file)

    app = create_app(cfg_file)

    port = 5558
    config = Config(app, host="127.0.0.1", port=port, log_level="error")
    server = Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True


@pytest.mark.ui
@pytest.mark.playwright
def test_ui_floating_autoselect_button(page, ui_server_url):
    """Test Web UI components using pure Python Playwright network route mocking."""

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
                        "favorite_vars": ["money"],
                    }
                ]
            },
        ),
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
        lambda route: route.fulfill(status=200, json={"sha123": {"money": 100}}),
    )

    page.route(
        "**/api/spaces/*/slots/*/screenshots*",
        lambda route: route.fulfill(
            status=200,
            json={"sha123": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="},
        ),
    )

    page.goto(ui_server_url)
    page.wait_for_selector("#app")

    assert page.is_visible("text=Ren'Py Save Graph")

    autoselect_btn = page.locator("button:has-text('Auto-select on add')")
    assert autoselect_btn.is_visible()
    assert "⚡" not in autoselect_btn.inner_text()

    autoselect_btn.click()
    assert "⚡ Auto-select on add" in autoselect_btn.inner_text()
