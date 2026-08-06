"""Unit tests for configuration serialization and defaults."""

import pytest
from pathlib import Path
from renpy_save_graph.config import AppConfig, GameSpace, default_config_path, default_data_dir, default_library_path


@pytest.mark.unit
def test_default_paths():
    data_dir = default_data_dir()
    assert isinstance(data_dir, Path)
    assert "renpy-save-graph" in str(data_dir)

    cfg_path = default_config_path()
    assert cfg_path.name == "config.json"

    lib_path = default_library_path("space-123")
    assert lib_path.name == "space-123"


@pytest.mark.unit
def test_game_space_defaults():
    space = GameSpace(
        id="space-1",
        label="Test Space",
        saves_dir="/path/to/saves",
        library_path="/path/to/lib",
    )
    assert space.id == "space-1"
    assert space.label == "Test Space"
    assert space.favorite_vars == []
    assert space.node_hint_format == ""


@pytest.mark.unit
def test_app_config_save_and_load(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    space = GameSpace(
        id="s1",
        label="Space 1",
        saves_dir=str(tmp_path / "saves"),
        library_path=str(tmp_path / "lib"),
        favorite_vars=["karma"],
    )
    config = AppConfig(spaces=[space])
    config.save(cfg_file)

    loaded = AppConfig.load(cfg_file)
    assert len(loaded.spaces) == 1
    assert loaded.spaces[0].id == "s1"
    assert loaded.spaces[0].favorite_vars == ["karma"]
