"""Director tests for watching a game split across several saves dirs."""

import hashlib
import json
import pytest
from pathlib import Path

from renpy_save_graph.watcher import Director, SpaceConfig, SaveDirRequiredError
from tests.conftest import create_mock_save_zip


@pytest.fixture
def dirs(tmp_path: Path):
    """(library, primary saves dir, additional saves dir)."""
    ep1, ep9 = tmp_path / "ep1-8", tmp_path / "ep9"
    ep1.mkdir()
    ep9.mkdir()
    return tmp_path / "lib", ep1, ep9


def make_director(lib, ep1, ep9) -> Director:
    return Director(SpaceConfig(
        saves_dir=ep1, library_path=lib, additional_saves_dirs=[ep9]
    ))


@pytest.mark.integration
def test_slots_span_all_saves_dirs(dirs):
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    (ep9 / "1-2-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9"))
    director = make_director(lib, ep1, ep9)

    assert director.slot_names() == ["1-1-LT1", "1-2-LT1"]
    assert director.slot_path("1-1-LT1") == ep1 / "1-1-LT1.save"
    assert director.slot_path("1-2-LT1") == ep9 / "1-2-LT1.save"


@pytest.mark.integration
def test_slot_exclude_applies_to_every_saves_dir(dirs):
    lib, ep1, ep9 = dirs
    for d in (ep1, ep9):
        (d / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 1}, "manual"))
        (d / "auto-1-LT1.save").write_bytes(create_mock_save_zip({"money": 2}, "auto"))
    director = Director(SpaceConfig(
        saves_dir=ep1, library_path=lib,
        additional_saves_dirs=[ep9], slot_exclude=r"^auto-",
    ))

    assert director.slot_names() == ["1-1-LT1"]


@pytest.mark.integration
def test_both_dirs_changing_at_once_starves_neither(dirs):
    """Only one file per slot is ingested per poll; the other must not be lost."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9"))
    director = make_director(lib, ep1, ep9)

    committed = []
    for _ in range(3):
        committed += director.ingest_all()

    assert len(committed) == 2
    assert len({r.commit.sha for r in committed}) == 2
    assert director.ingest_all() == []


@pytest.mark.integration
def test_survives_an_unavailable_additional_dir(dirs):
    """An unmounted drive or deleted folder must not stall the whole space."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    director = Director(SpaceConfig(
        saves_dir=ep1, library_path=lib,
        additional_saves_dirs=[ep9 / "not-mounted"],
    ))

    assert director.slot_names() == ["1-1-LT1"]
    assert len(director.ingest_all()) == 1


@pytest.mark.integration
def test_same_dir_listed_twice_ingests_once(dirs):
    """The picker opens on saves_dir, so re-adding it as 'additional' is easy."""
    lib, ep1, _ = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    director = Director(SpaceConfig(
        saves_dir=ep1, library_path=lib, additional_saves_dirs=[ep1],
    ))

    assert director.slot_names() == ["1-1-LT1"]
    assert len(director.ingest_all()) == 1
    assert director.ingest_all() == []


@pytest.mark.integration
def test_ingests_the_dir_that_changed_when_slot_name_is_shared(dirs):
    """A split install reuses slot names; the changed file is the one to commit."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    director = make_director(lib, ep1, ep9)
    assert [r.commit.subject for r in director.ingest_all(note="ep1")] == ["ep1"]

    # Player continues in the Episode 9 install, same slot name.
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9"))
    assert director.slot_path("1-1-LT1") == ep9 / "1-1-LT1.save"
    assert [r.commit.subject for r in director.ingest_all(note="ep9")] == ["ep9"]

    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 600}, "ep9_later"))
    assert [r.commit.subject for r in director.ingest_all(note="ep9_later")] == ["ep9_later"]

    assert director.ingest_all() == []


@pytest.mark.integration
def test_additional_dir_added_to_an_existing_space(dirs):
    """Upgrading a space whose hash file predates additional saves dirs.

    Those files are keyed by slot name only.  The new dir's save must still be
    seen, and the already-committed primary file must not be re-ingested.
    """
    lib, ep1, ep9 = dirs
    primary = ep1 / "1-1-LT1.save"
    primary.write_bytes(create_mock_save_zip({"money": 100}, "ep1"))
    Director(SpaceConfig(saves_dir=ep1, library_path=lib)).ingest_all()

    # Rewrite the hash file the way the pre-feature release left it.
    (lib / ".slot_hashes.json").write_text(json.dumps(
        {"1-1-LT1": hashlib.sha256(primary.read_bytes()).hexdigest()}
    ))

    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9"))
    director = make_director(lib, ep1, ep9)

    assert [r.commit.subject for r in director.ingest_all(note="ep9")] == ["ep9"]
    assert director.ingest_all() == []


@pytest.mark.integration
def test_restore_does_not_trigger_a_phantom_commit(dirs):
    """After switch_to, an idle watcher poll must not commit or fork a branch."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "A"))
    director = make_director(lib, ep1, ep9)
    first = director.ingest_all()[0]
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 200}, "B"))
    director.ingest_all()

    director.switch_to("1-1-LT1", first.commit.sha)
    after_restore = director.library.branch_tips()

    # Idle polls: nothing changed on disk, so no commit and no auto-fork branch.
    assert director.ingest_all() == []
    assert director.ingest_all() == []
    assert director.library.branch_tips() == after_restore


@pytest.mark.integration
def test_restore_targets_correct_saves_dir_for_earlier_save(dirs):
    """Restoring an earlier commit made in primary dir restores to primary dir even if secondary dir has newer saves."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "ep1_save"))
    director = make_director(lib, ep1, ep9)
    first_commit = director.ingest_all()[0].commit.sha

    # Player makes a save in Episode 9 (secondary dir)
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9_save"))
    second_commit = director.ingest_all()[0].commit.sha
    ep9_bytes = (ep9 / "1-1-LT1.save").read_bytes()

    # Restore to first commit (made in ep1)
    director.switch_to("1-1-LT1", first_commit)

    # Verify ep1 file was restored to first_commit contents (money=100)
    # and ep9 file was left untouched
    assert director.restore_path("1-1-LT1", first_commit) == ep1 / "1-1-LT1.save"
    assert (ep9 / "1-1-LT1.save").read_bytes() == ep9_bytes


@pytest.mark.integration
def test_restore_legacy_save_predating_multiple_saves(dirs):
    """Restoring a commit with recorded save_dir metadata targets that dir even when additional save dirs are configured later."""
    lib, ep1, ep9 = dirs
    primary_save = ep1 / "1-1-LT1.save"
    primary_save.write_bytes(create_mock_save_zip({"money": 100}, "legacy"))

    # Initial space before additional saves dirs were configured
    single_dir_director = Director(SpaceConfig(saves_dir=ep1, library_path=lib))
    first_commit = single_dir_director.ingest_all()[0].commit.sha

    # Player later configures additional_saves_dirs and saves in ep9
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9"))
    multi_dir_director = make_director(lib, ep1, ep9)
    multi_dir_director.ingest_all()

    # The commit records ep1 as save_dir, so restore_path resolves to ep1
    assert multi_dir_director.restore_path("1-1-LT1", first_commit) == ep1 / "1-1-LT1.save"
    multi_dir_director.switch_to("1-1-LT1", first_commit)
    assert (ep1 / "1-1-LT1.save").read_bytes() != b""


@pytest.mark.integration
def test_restore_legacy_commit_without_save_dir_metadata(dirs):
    """Commits without save_dir metadata line raise SaveDirRequiredError when multiple dirs exist."""
    lib, ep1, ep9 = dirs
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "old_ver"))
    director = make_director(lib, ep1, ep9)
    res = director.ingest_all()[0]

    # Amend the commit message to strip save_dir metadata (simulating old version ingest)
    director.library._git("commit", "--amend", "-m", "legacy commit without save_dir")
    legacy_sha = director.library.head().sha

    # Ingest a newer save in ep9
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 500}, "ep9_save"))
    director.ingest_all()

    # Verify SaveDirRequiredError is raised unless target_save_dir is provided
    with pytest.raises(SaveDirRequiredError):
        director.restore_path("1-1-LT1", legacy_sha)

    assert director.restore_path("1-1-LT1", legacy_sha, target_save_dir=ep9) == ep9 / "1-1-LT1.save"


@pytest.mark.integration
def test_ingest_records_which_saves_dir_a_commit_came_from(dirs):
    lib, ep1, ep9 = dirs
    director = make_director(lib, ep1, ep9)
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "c1"))
    sha1 = director.ingest_all()[0].commit.sha
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 200}, "c2"))
    sha2 = director.ingest_all()[0].commit.sha

    assert director.node_save_dir("1-1-LT1", sha1) == str(ep1)
    assert director.node_save_dir("1-1-LT1", sha2) == str(ep9)


@pytest.mark.integration
def test_setting_a_save_dir_fills_in_unrecorded_descendants(dirs):
    lib, ep1, ep9 = dirs
    director = make_director(lib, ep1, ep9)
    shas = []
    for money in (100, 200, 300):
        (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": money}, f"c{money}"))
        shas.append(director.ingest_all()[0].commit.sha)

    # A library from before save dirs were recorded has no entries at all.
    (lib / ".slot_save_dirs.json").write_text("{}")

    director.set_save_dir_subtree("1-1-LT1", shas[1], str(ep9))

    assert director.node_save_dir("1-1-LT1", shas[1]) == str(ep9)
    assert director.node_save_dir("1-1-LT1", shas[2]) == str(ep9)
    # Upstream of the change, so still nothing to inherit.
    assert director.node_save_dir("1-1-LT1", shas[0]) is None


@pytest.mark.integration
def test_setting_a_save_dir_overwrites_recorded_descendants(dirs):
    """Bulk correction: the whole subtree takes the new directory."""
    lib, ep1, ep9 = dirs
    director = make_director(lib, ep1, ep9)
    (ep1 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 100}, "c1"))
    parent = director.ingest_all()[0].commit.sha
    (ep9 / "1-1-LT1.save").write_bytes(create_mock_save_zip({"money": 200}, "c2"))
    child = director.ingest_all()[0].commit.sha
    assert director.node_save_dir("1-1-LT1", child) == str(ep9)

    director.set_save_dir_subtree("1-1-LT1", parent, str(ep1))

    assert director.node_save_dir("1-1-LT1", parent) == str(ep1)
    assert director.node_save_dir("1-1-LT1", child) == str(ep1)

