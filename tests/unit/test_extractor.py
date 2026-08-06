"""Unit tests for save state extractor and store variable filtering."""

from renpy_save_graph.extractor import EXCLUDED_STORE_VARS, SaveState, _to_json


def test_excluded_store_vars_contains_args_and_kwargs():
    assert "args" in EXCLUDED_STORE_VARS
    assert "kwargs" in EXCLUDED_STORE_VARS


def test_extractor_filters_excluded_vars():
    roots = {
        "store.money": 100,
        "store.karma": 5,
        "store.args": ["arg1", "arg2"],
        "store.kwargs": {"key": "val"},
        "other.internal": True,
    }

    variables = {
        var_name: _to_json(value)
        for key, value in roots.items()
        if key.startswith("store.") and (var_name := key[len("store."):]) not in EXCLUDED_STORE_VARS
    }

    assert "money" in variables
    assert "karma" in variables
    assert "args" not in variables
    assert "kwargs" not in variables
