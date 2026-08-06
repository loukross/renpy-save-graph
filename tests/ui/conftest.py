"""Shared fixtures for Playwright UI tests."""

import threading
import time

import pytest
from uvicorn import Config, Server

from renpy_save_graph.server import create_app


@pytest.fixture(scope="module")
def ui_server_url(tmp_path_factory, free_tcp_port_factory):
    """Fixture to launch a lightweight background server serving the built frontend."""
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

    port = free_tcp_port_factory()
    config = Config(app, host="127.0.0.1", port=port, log_level="error")
    server = Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.5)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
