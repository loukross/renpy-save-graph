"""Shared pytest fixtures for renpy-save-graph behavioral and integration tests."""

from __future__ import annotations

import io
import json
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from renpy_save_graph.config import AppConfig, GameSpace
from renpy_save_graph.library import Library
from renpy_save_graph.db import DatabaseStore
from renpy_save_graph.extractor import SaveState
from renpy_save_graph.server import create_app
from renpy_save_graph.watcher import Director


from PIL import Image


def create_mock_save_zip(vars_dict: dict, label: str = "start") -> bytes:
    """Helper to generate a mock Ren'Py .save zip blob containing screenshot.png and state.json."""
    img = Image.new("RGBA", (10, 10), color="blue")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    png_bytes = img_buf.getvalue()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("screenshot.png", png_bytes)
        state_data = {
            "version": "1.0",
            "label": label,
            "variables": vars_dict,
        }
        zf.writestr("state.json", json.dumps(state_data))
    return buf.getvalue()


@pytest.fixture(autouse=True)
def mock_extractor_for_tests(monkeypatch):
    from renpy_save_graph import extractor
    orig_extract = extractor.extract

    def mock_extract(save_path: str):
        try:
            with zipfile.ZipFile(save_path) as z:
                if "state.json" in z.namelist():
                    data = json.loads(z.read("state.json"))
                    return SaveState(
                        save_name="test_save",
                        renpy_version="7.4",
                        game_version="1.0",
                        variables=data.get("variables", {}),
                    )
        except Exception:
            pass
        return orig_extract(save_path)

    monkeypatch.setattr(extractor, "extract", mock_extract)


@pytest.fixture
def tmp_workspace(tmp_path: Path):
    """Fixture providing temporary directories for library, saves_dir, and config."""
    lib_dir = tmp_path / "lib_repo"
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = tmp_path / "config.json"

    # Initialize a Git Library
    lib = Library.init(lib_dir)

    space = GameSpace(
        id="test-space-id",
        label="Test Space",
        saves_dir=str(saves_dir),
        library_path=str(lib_dir),
        favorite_vars=["money", "karma"],
    )

    config = AppConfig(spaces=[space])
    config.save(cfg_file)

    # Initialize slot directory & commit initial root save
    slot_file = saves_dir / "1-1-LT1.save"
    slot_file.write_bytes(create_mock_save_zip({"money": 100, "karma": 0}, "root_label"))

    director = Director(space)
    director.ingest("1-1-LT1", note="Initial Root Save")

    return {
        "tmp_path": tmp_path,
        "lib_dir": lib_dir,
        "saves_dir": saves_dir,
        "cfg_file": cfg_file,
        "space": space,
        "config": config,
        "library": lib,
        "slot_file": slot_file,
    }


@pytest.fixture
def test_client(tmp_workspace):
    """FastAPI TestClient fixture."""
    app = create_app(tmp_workspace["cfg_file"])
    return TestClient(app)
