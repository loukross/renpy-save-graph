"""Example Game Space initialization module."""

import shutil
from pathlib import Path
from ..config import AppConfig, GameSpace, default_data_dir
from ..watcher import Director, SpaceConfig

EXAMPLE_SPACE_ID = "example-space"


def ensure_example_space(config_path: Path) -> None:
    """Initialize a default Example Game Space if it does not yet exist."""
    try:
        cfg = AppConfig.load(config_path)
        if any(s.id == EXAMPLE_SPACE_ID for s in cfg.spaces):
            return

        data_dir = default_data_dir()
        demo_dir = data_dir / "demo_space"
        if demo_dir.exists():
            shutil.rmtree(demo_dir)

        saves_dir = demo_dir / "saves"
        lib_dir = demo_dir / "library"
        saves_dir.mkdir(parents=True, exist_ok=True)
        lib_dir.mkdir(parents=True, exist_ok=True)

        pkg_examples_dir = Path(__file__).parent

        space = GameSpace(
            id=EXAMPLE_SPACE_ID,
            label="Example Game Space",
            saves_dir=str(saves_dir),
            library_path=str(lib_dir),
            node_hint_format='{_last_say_who}: "{_last_say_what}"',
            slot_exclude="auto-.*|quick-.*",
            favorite_vars=["chosen_route", "courage", "wisdom", "inventory_item"],
        )

        slot_name = "1-1-LT1"
        slot_file = saves_dir / f"{slot_name}.save"

        director = Director(SpaceConfig(
            saves_dir=saves_dir,
            library_path=lib_dir,
        ))

        # 1. Ingest A (Crossroads) on main slot branch (1-1-LT1)
        save_a = pkg_examples_dir / "save_a.save"
        if save_a.exists():
            slot_file.write_bytes(save_a.read_bytes())
            res_a = director.ingest(slot_name, note='Narrator: "You stand at the ancient crossroads..."')
            sha_a = res_a.commit.sha

            sha_b = None
            # 2. Ingest B (Forest) on fork branch 1-1-LT1-forest_route
            save_b = pkg_examples_dir / "save_b.save"
            if save_b.exists():
                director.library.branch_from(sha_a, f"{slot_name}-forest_route")
                slot_file.write_bytes(save_b.read_bytes())
                commit_b = director.library.commit_savepoint(slot_file, note='Narrator: "You chose the misty forest path..."')
                sha_b = commit_b.sha

            sha_c = None
            # 3. Ingest C (Castle) on main slot branch (1-1-LT1)
            save_c = pkg_examples_dir / "save_c.save"
            if save_c.exists():
                director.library.switch_branch(slot_name)
                slot_file.write_bytes(save_c.read_bytes())
                res_c = director.ingest(slot_name, note='Narrator: "You chose the mountain castle gate..."')
                sha_c = res_c.commit.sha

            from ..db import DatabaseStore
            db = DatabaseStore(lib_dir / "graph.sqlite")
            db.sync_with_git(director.library, slot_name, director.slot_names())
            if sha_b:
                director.library.add_tag(sha_b, "forest-route")
                director.library.add_tag(sha_b, "ch1-milestone")
            if sha_c:
                director.library.add_tag(sha_c, "mountain-gate")

        cfg.spaces.append(space)
        cfg.save(config_path)
    except Exception as e:
        print(f"Warning: Failed to initialize Example Game Space: {e}")
