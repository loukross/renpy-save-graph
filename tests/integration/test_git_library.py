"""Integration tests for Library Git DAG operations."""

import pytest
from renpy_save_graph.library import Library
from renpy_save_graph.watcher import Director
from tests.conftest import create_mock_save_zip


@pytest.mark.integration
def test_git_straight_line_restore(tmp_workspace):
    space = tmp_workspace["space"]
    slot_file = tmp_workspace["slot_file"]
    director = Director(space)

    # Ingest 2nd commit
    slot_file.write_bytes(create_mock_save_zip({"money": 200, "karma": 10}, "chapter_1"))
    res2 = director.ingest("1-1-LT1", note="Chapter 1")
    sha2 = res2.commit.sha

    # Ingest 3rd commit
    slot_file.write_bytes(create_mock_save_zip({"money": 300, "karma": 20}, "chapter_2"))
    res3 = director.ingest("1-1-LT1", note="Chapter 2")
    sha3 = res3.commit.sha

    nodes = director.library.dag()
    assert len(nodes) == 3

    # Straight-line restore to chapter 1 (sha2)
    info = director.switch_to("1-1-LT1", sha2)
    assert info.sha == sha2
    assert info.branch == "1-1-LT1"

    # Play on from chapter 1 (sha2) -> commit chapter 1b (sha4)
    slot_file.write_bytes(create_mock_save_zip({"money": 250, "karma": 15}, "chapter_1b"))
    res4 = director.ingest("1-1-LT1", note="Chapter 1b")
    sha4 = res4.commit.sha

    # Verify active branch tip updated cleanly
    head_sha = director.library.head().sha
    assert head_sha == sha4


@pytest.mark.integration
def test_git_node_deletion_reparent(tmp_workspace):
    space = tmp_workspace["space"]
    slot_file = tmp_workspace["slot_file"]
    director = Director(space)

    # Ingest 2nd commit
    slot_file.write_bytes(create_mock_save_zip({"money": 200, "karma": 10}, "chapter_1"))
    res2 = director.ingest("1-1-LT1", note="Chapter 1")
    sha2 = res2.commit.sha

    # Ingest 3rd commit
    slot_file.write_bytes(create_mock_save_zip({"money": 300, "karma": 20}, "chapter_2"))
    res3 = director.ingest("1-1-LT1", note="Chapter 2")
    sha3 = res3.commit.sha

    # Delete middle commit sha2 using reparent
    removed_shas = director.delete_node("1-1-LT1", sha2, strategy="reparent")
    assert sha2 in removed_shas

    nodes = director.library.dag()
    remaining_shas = {n.sha for n in nodes}
    assert sha2 not in remaining_shas


@pytest.mark.integration
def test_reparent_delete_keeps_descendant_notes(tmp_workspace):
    """Reparenting rebases descendants; their notes must ride along to the new SHAs."""
    space = tmp_workspace["space"]
    slot_file = tmp_workspace["slot_file"]
    director = Director(space)

    slot_file.write_bytes(create_mock_save_zip({"money": 200}, "chapter_1"))
    sha2 = director.ingest("1-1-LT1").commit.sha

    slot_file.write_bytes(create_mock_save_zip({"money": 300}, "chapter_2"))
    sha3 = director.ingest("1-1-LT1").commit.sha
    director.library.set_note(sha3, "keep me")

    director.delete_node("1-1-LT1", sha2, strategy="reparent")

    tip = director.library.head()
    assert tip.sha != sha3, "descendant should have been rewritten"
    notes = {n.sha: n.note for n in director.library.dag()}
    assert notes[tip.sha] == "keep me"


@pytest.mark.integration
def test_git_multiple_restores_preserve_history(tmp_workspace):
    space = tmp_workspace["space"]
    slot_file = tmp_workspace["slot_file"]
    director = Director(space)

    # Ingest 2nd and 3rd commits
    slot_file.write_bytes(create_mock_save_zip({"money": 200}, "ch1"))
    sha2 = director.ingest("1-1-LT1", note="ch1").commit.sha

    slot_file.write_bytes(create_mock_save_zip({"money": 300}, "ch2"))
    sha3 = director.ingest("1-1-LT1", note="ch2").commit.sha

    # 1st Restore to sha2 and save ch2b
    director.switch_to("1-1-LT1", sha2)
    slot_file.write_bytes(create_mock_save_zip({"money": 250}, "ch2b"))
    sha2b = director.ingest("1-1-LT1", note="ch2b").commit.sha

    # 2nd Restore to sha2 and save ch2c
    director.switch_to("1-1-LT1", sha2)
    slot_file.write_bytes(create_mock_save_zip({"money": 270}, "ch2c"))
    sha2c = director.ingest("1-1-LT1", note="ch2c").commit.sha

    # Verify all commits (sha2, sha3, sha2b, sha2c) exist in slot DAG
    nodes = director.library.dag_for_slot("1-1-LT1", ["1-1-LT1"])
    shas = {n.sha for n in nodes}
    assert sha2 in shas
    assert sha3 in shas
    assert sha2b in shas
    assert sha2c in shas
