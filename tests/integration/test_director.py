"""Director tests for watching a game split across several saves dirs."""

import hashlib
import json
import pytest
from pathlib import Path

from renpy_save_graph.watcher import Director, SpaceConfig
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
