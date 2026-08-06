"""Persistent configuration for renpy-save-graph."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "renpy-save-graph"


def default_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME))


def default_config_path() -> Path:
    return default_data_dir() / "config.json"


def default_library_path(space_id: str) -> Path:
    return default_data_dir() / "libs" / space_id


@dataclass
class GameSpace:
    id: str
    label: str
    saves_dir: str
    library_path: str
    node_hint_format: str = ""
    slot_exclude: str = ""  # regex; matching slot names are ignored
    favorite_vars: list[str] = field(default_factory=list)
    filter_history: list[str] = field(default_factory=list)
    sort_history: list[str] = field(default_factory=list)
    lineage_validity_expr: str = ""


@dataclass
class AppConfig:
    spaces: list[GameSpace] = field(default_factory=list)

    def space_by_id(self, space_id: str) -> GameSpace | None:
        return next((s for s in self.spaces if s.id == space_id), None)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        known_fields = {f.name for f in fields(GameSpace)}
        spaces = [
            GameSpace(**{k: v for k, v in s.items() if k in known_fields})
            for s in data.get("spaces", [])
        ]
        return cls(spaces=spaces)
