"""Generator script for building custom Ren'Py demo .save files from user PNG drawings and dialogue."""

import io
import json
import pickle
import zipfile
from pathlib import Path


def build_renpy_save(png_bytes: bytes, dialogue_text: str, state_vars: dict) -> bytes:
    """Build a valid Ren'Py save ZIP archive containing json metadata, screenshot, dialogue, and state vars."""
    buf = io.BytesIO()

    # 1. Ren'Py json metadata
    meta = {
        "_save_name": dialogue_text,
        "_renpy_version": [7, 4, 11],
        "_version": "1.0",
    }
    meta_bytes = json.dumps(meta).encode("utf-8")

    # 2. Ren'Py extra_data dictionary
    extra_data = {
        "location_name": dialogue_text,
        "screenshot": png_bytes,
    }
    extra_data_bytes = pickle.dumps(extra_data, protocol=2)

    # 3. Ren'Py log tuple (roots, log) with store. prefix for variables
    roots = {f"store.{k}": v for k, v in state_vars.items()}
    log_bytes = pickle.dumps((roots, None), protocol=2)

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("json", meta_bytes)
        zf.writestr("extra_data", extra_data_bytes)
        zf.writestr("log", log_bytes)
        zf.writestr("screenshot.png", png_bytes)

    return buf.getvalue()


def generate_demo_saves(examples_dir: Path):
    """Generate save_a.save, save_b.save, and save_c.save directly from PNG drawings."""
    examples_dir.mkdir(parents=True, exist_ok=True)

    node_a_png = examples_dir / "node_a.png"
    node_b_png = examples_dir / "node_b.png"
    node_c_png = examples_dir / "node_c.png"

    if not node_a_png.exists() or not node_b_png.exists() or not node_c_png.exists():
        raise FileNotFoundError(
            f"Required PNG drawings missing in {examples_dir}. Expected node_a.png, node_b.png, and node_c.png."
        )

    # Node A (Root / Start)
    save_a = build_renpy_save(
        node_a_png.read_bytes(),
        dialogue_text='Narrator: "You stand at the ancient crossroads..."',
        state_vars={
            "_last_say_who": "Narrator",
            "_last_say_what": "You stand at the ancient crossroads...",
            "chosen_route": "crossroads",
            "courage": 0,
            "wisdom": 0,
            "inventory_item": "none",
            "gold": 100,
            "chapter": 1,
        },
    )
    (examples_dir / "save_a.save").write_bytes(save_a)

    # Node B (Branch 1)
    save_b = build_renpy_save(
        node_b_png.read_bytes(),
        dialogue_text='Narrator: "You chose the misty forest path..."',
        state_vars={
            "_last_say_who": "Narrator",
            "_last_say_what": "You chose the misty forest path...",
            "chosen_route": "forest",
            "courage": 10,
            "wisdom": 0,
            "inventory_item": "elven_lantern",
            "gold": 150,
            "chapter": 2,
        },
    )
    (examples_dir / "save_b.save").write_bytes(save_b)

    # Node C (Branch 2)
    save_c = build_renpy_save(
        node_c_png.read_bytes(),
        dialogue_text='Narrator: "You chose the mountain castle gate..."',
        state_vars={
            "_last_say_who": "Narrator",
            "_last_say_what": "You chose the mountain castle gate...",
            "chosen_route": "mountain",
            "courage": 0,
            "wisdom": 10,
            "inventory_item": "grappling_hook",
            "gold": 80,
            "chapter": 2,
        },
    )
    (examples_dir / "save_c.save").write_bytes(save_c)


if __name__ == "__main__":
    out = Path(__file__).parent
    generate_demo_saves(out)
    print(f"Generated demo saves in {out}")
