"""REST API contract tests for importing an existing library."""

import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from renpy_save_graph.library import Library
from renpy_save_graph.watcher import Director, SpaceConfig
from tests.conftest import create_mock_save_zip


def build_library(tmp_path: Path) -> tuple[Path, str]:
    """A two-saves-dir library with a tag, a note and a manifest; returns its tip."""
    lib_dir, ep1, ep9 = tmp_path / "src_lib", tmp_path / "src_ep1", tmp_path / "src_ep9"
    ep1.mkdir()
    ep9.mkdir()
    director = Director(SpaceConfig(
        saves_dir=ep1, library_path=lib_dir, additional_saves_dirs=[ep9]
    ))
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    director.ingest_all()
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 200}, "ep9"))
    tip = director.ingest_all()[0].commit.sha

    director.library.add_tag(tip, "finale")
    director.library.set_note(tip, "the last one")
    director.library.write_manifest(
        {"schema": 1, "space": {"label": "Source Space", "milestone_vars": ["chapter"]}}
    )
    return lib_dir, tip


def clone(src: Path, dest: Path) -> Path:
    subprocess.run(["git", "clone", "--quiet", str(src), str(dest)], check=True)
    return dest


@pytest.mark.api
def test_inspect_reports_slots_and_save_dir_usage(test_client: TestClient, tmp_path: Path):
    lib_dir, _ = build_library(tmp_path)

    data = test_client.get("/api/library/inspect", params={"path": str(lib_dir)}).json()

    assert data["ok"] is True
    assert data["slots"] == ["1-1-LT1"]
    assert data["save_dir_count"] == 2
    assert data["nodes_per_save_dir"] == {"0": 1, "1": 1}
    assert data["space"]["label"] == "Source Space"


@pytest.mark.api
def test_inspect_rejects_a_directory_that_is_not_a_library(test_client: TestClient, tmp_path: Path):
    plain = tmp_path / "not_a_repo"
    plain.mkdir()

    data = test_client.get("/api/library/inspect", params={"path": str(plain)}).json()

    assert data["ok"] is False
    assert "git repository" in data["error"]


@pytest.mark.api
def test_inspect_rejects_a_git_repo_without_our_manifest(test_client: TestClient, tmp_path: Path):
    """A repo can look like a library and not be one; the marker is the check."""
    lib_dir, _ = build_library(tmp_path)
    Library(lib_dir)._git("update-ref", "-d", "refs/heads/_meta")

    data = test_client.get("/api/library/inspect", params={"path": str(lib_dir)}).json()

    assert data["ok"] is False
    assert "manifest" in data["error"]


@pytest.mark.api
def test_viewing_a_graph_backfills_the_manifest(test_client: TestClient, tmp_workspace):
    """Libraries predating the manifest get their marker on first real use."""
    lib = Library.init(tmp_workspace["lib_dir"])
    assert lib.read_manifest() == {}

    test_client.get("/api/spaces/test-space-id/slots/1-1-LT1/graph")

    assert lib.read_manifest()["app"] == "renpy-save-graph"


@pytest.mark.api
def test_import_a_clone_carries_tags_notes_and_settings(test_client: TestClient, tmp_path: Path):
    lib_dir, tip = build_library(tmp_path)
    cloned = clone(lib_dir, tmp_path / "cloned_lib")
    ep1, ep9 = tmp_path / "new_ep1", tmp_path / "new_ep9"
    ep1.mkdir()
    ep9.mkdir()

    resp = test_client.post("/api/spaces/import", json={
        "library_path": str(cloned),
        "saves_dirs": [str(ep1), str(ep9)],
    })
    assert resp.status_code == 200
    space = resp.json()

    # Settings ride in the manifest; the saves dirs are this machine's answer.
    assert space["label"] == "Source Space"
    assert space["milestone_vars"] == ["chapter"]
    assert space["saves_dir"] == str(ep1)
    assert space["additional_saves_dirs"] == [str(ep9)]

    # The clone fetched notes, so tags and note text survived the trip.
    sid, slot = space["id"], "1-1-LT1"
    tags = test_client.get(f"/api/spaces/{sid}/slots/{slot}/tags").json()
    assert tags["tags"][tip] == ["finale"]
    nodes = test_client.get(f"/api/spaces/{sid}/slots/{slot}/graph").json()["nodes"]
    assert next(n for n in nodes if n["sha"] == tip)["note"] == "the last one"

    # save_dir_index resolved against the new machine's dirs, not the old paths.
    assert space["seeded_slots"] == [slot]
    assert (ep9 / f"{slot}.save").exists()
    assert not (ep1 / f"{slot}.save").exists()


@pytest.mark.api
def test_import_seeds_the_newest_save_point_from_any_route(test_client: TestClient, tmp_path: Path):
    """The newest node may sit on a fork; the main line's tip can be far older."""
    lib_dir, ep1, ep9 = tmp_path / "fork_lib", tmp_path / "fork_ep1", tmp_path / "fork_ep9"
    ep1.mkdir()
    ep9.mkdir()
    director = Director(SpaceConfig(
        saves_dir=ep1, library_path=lib_dir, additional_saves_dirs=[ep9]
    ))
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "start"))
    start = director.ingest_all()[0].commit.sha
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 200}, "main"))
    main_tip = director.ingest_all()[0].commit.sha

    # Fork off the start and save again: newer than the main line's tip.
    # Git commit times are whole seconds, so the gap has to be a real one.
    time.sleep(1.1)
    director.switch_to("1-1-LT1", start, new_branch="1-1-LT1-alt")
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 300}, "alt"))
    alt_tip = director.ingest_all()[0].commit.sha
    director.library.write_manifest({"space": {"label": "Forked"}})

    target = tmp_path / "fork_target"
    target.mkdir()
    space = test_client.post("/api/spaces/import", json={
        "library_path": str(lib_dir), "saves_dirs": [str(target)],
    }).json()

    graph = test_client.get(
        f"/api/spaces/{space['id']}/slots/1-1-LT1/graph"
    ).json()
    assert graph["head"] == alt_tip, "should have landed on the newest node, not the main tip"
    assert graph["head"] != main_tip
    assert (target / "1-1-LT1.save").exists()


@pytest.mark.api
def test_plan_reports_which_slots_would_be_overwritten(test_client: TestClient, tmp_path: Path):
    lib_dir, _ = build_library(tmp_path)
    ep1, ep9 = tmp_path / "plan_ep1", tmp_path / "plan_ep9"
    ep1.mkdir()
    ep9.mkdir()

    def plan():
        return test_client.post("/api/library/plan", json={
            "library_path": str(lib_dir), "saves_dirs": [str(ep1), str(ep9)],
        }).json()["slots"]

    [entry] = plan()
    assert entry["slot"] == "1-1-LT1"
    assert entry["target"] == str(ep9 / "1-1-LT1.save")  # newest node's install
    assert entry["occupied"] is False

    (ep9 / "1-1-LT1.save").write_bytes(b"player's own save")
    assert plan()[0]["occupied"] is True
    # A dry run writes nothing.
    assert (ep9 / "1-1-LT1.save").read_bytes() == b"player's own save"


@pytest.mark.api
def test_import_refuses_to_overwrite_without_approval(test_client: TestClient, tmp_path: Path):
    """The wizard asks; the API insists, so no caller can clobber saves silently."""
    lib_dir, _ = build_library(tmp_path)
    ep1, ep9 = tmp_path / "keep_ep1", tmp_path / "keep_ep9"
    ep1.mkdir()
    ep9.mkdir()
    occupied = ep9 / "1-1-LT1.save"
    occupied.write_bytes(b"player's own save")

    resp = test_client.post("/api/spaces/import", json={
        "library_path": str(lib_dir), "saves_dirs": [str(ep1), str(ep9)],
    })

    assert resp.status_code == 409
    assert resp.json()["detail"]["slots"] == ["1-1-LT1"]
    assert occupied.read_bytes() == b"player's own save"

    approved = test_client.post("/api/spaces/import", json={
        "library_path": str(lib_dir), "saves_dirs": [str(ep1), str(ep9)],
        "overwrite": True,
    })

    assert approved.json()["seeded_slots"] == ["1-1-LT1"]
    assert occupied.read_bytes() != b"player's own save"
