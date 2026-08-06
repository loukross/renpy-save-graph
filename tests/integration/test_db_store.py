"""Integration tests for DatabaseStore (SQLite index)."""

import pytest
from pathlib import Path
from renpy_save_graph.db import DatabaseStore
from renpy_save_graph.library import Library


@pytest.mark.integration
def test_db_init_and_sync(tmp_workspace):
    lib: Library = tmp_workspace["library"]
    db_path = tmp_workspace["lib_dir"] / "graph.sqlite"
    db = DatabaseStore(db_path)

    # Sync with Git
    db.sync_with_git(lib, "1-1-LT1", ["1-1-LT1"])

    nodes = lib.dag()
    assert len(nodes) == 1
    sha = nodes[0].sha

    # Test get_nodes
    db_nodes = db.get_nodes([sha])
    assert sha in db_nodes
    assert db_nodes[sha]["subject"] == "Initial Root Save"

    # Test get_all_states
    states = db.get_all_states([sha])
    assert sha in states
    assert states[sha]["money"] == 100
    assert states[sha]["karma"] == 0

    # Test parameterized get_all_states
    param_states = db.get_all_states([sha], var_names={"money"})
    assert param_states[sha] == {"money": 100}


@pytest.mark.integration
def test_db_self_healing_stale_purge(tmp_workspace):
    lib: Library = tmp_workspace["library"]
    db_path = tmp_workspace["lib_dir"] / "graph.sqlite"
    db = DatabaseStore(db_path)

    db.sync_with_git(lib, "1-1-LT1", ["1-1-LT1"])
    nodes = lib.dag()
    sha = nodes[0].sha

    # Verify sha is in DB
    assert sha in db.get_nodes([sha])

    # Delete sha directly from DB
    db.delete_node(sha)
    assert sha not in db.get_nodes([sha])

    # Re-sync should re-populate
    db.sync_with_git(lib, "1-1-LT1", ["1-1-LT1"])
    assert sha in db.get_nodes([sha])
