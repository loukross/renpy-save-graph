"""Decode a Ren'Py .save into a queryable state.json.

A .save is a ZIP whose `log` member is a Python-2 pickle of ``(roots, RollbackLog)``:

- ``roots``   -- the store: a dict of every game variable (``store.<name>``).
- ``RollbackLog`` -- full rollback history; we read only its current node.

The pickle references Ren'Py runtime classes (RevertableList, RevertableDict,
RevertableSet, RollbackLog, Rollback, Context, Style, ...). Rather than depend on
Ren'Py, we unpickle with tolerant stand-ins: the revertable containers become
plain list/dict/set subclasses (so their items survive), and every other class
becomes a permissive ``_Stub`` that captures its pickled ``__setstate__`` dict.

We then keep only the JSON-serializable game state. That decoded ``state.json`` --
not the opaque blob -- is what the git model diffs and graphs. See docs/DESIGN.md.
"""

from __future__ import annotations

import io
import json
import pickle
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Any

_SCALAR = (str, int, float, bool, type(None))


class _Stub:
    """Permissive stand-in for a non-container Ren'Py class.

    Captures whatever state pickle assigns so attributes (e.g. a Context's
    ``current`` node) remain reachable, without importing Ren'Py.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if args:
            self.__dict__["_args"] = list(args)

    def __setstate__(self, state: Any) -> None:
        # Normal Ren'Py objects pickle a dict here; keep it addressable.
        self.__dict__["_state"] = state


_STDLIB_MODULES = {"__builtin__", "builtins", "collections"}


class _TolerantUnpickler(pickle.Unpickler):
    """Unpickler that manufactures stand-in classes on demand."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._classes: dict[tuple[str, str], type] = {}

    def find_class(self, module: str, name: str) -> Any:  # noqa: D102
        key = (module, name)
        cached = self._classes.get(key)
        if cached is not None:
            return cached
        if module in _STDLIB_MODULES:
            # Real Python/stdlib types (dict, list, set, collections.defaultdict,
            # ...) are already picklable as themselves. Routing them through the
            # name-substring heuristic below (meant for Ren'Py's RevertableDict/
            # List/Set) corrupts their real construction protocol -- e.g. a
            # pickled `defaultdict(dict)` ends up calling the fake stand-in's
            # inherited `dict.keys` descriptor unbound, with no arguments.
            cls = super().find_class(module, name)
            self._classes[key] = cls
            return cls
        low = name.lower()
        if "list" in low:
            base: type = list
        elif "dict" in low:
            base = dict
        elif "set" in low:
            base = set
        else:
            base = _Stub
        if base in (list, dict, set):
            # Revertable containers pass non-dict metadata to __setstate__;
            # their real items arrive via the normal list/dict/set opcodes.
            cls = type(name, (base,), {"__setstate__": lambda self, state: None})
        else:
            cls = type(name, (base,), {})
        self._classes[key] = cls
        return cls


@dataclass
class SaveState:
    """Decoded, queryable view of one save point."""

    save_name: str = ""
    renpy_version: str = ""
    game_version: str = ""
    current_node: dict[str, Any] | None = None  # {"file":..., "line":...}
    variables: dict[str, Any] = field(default_factory=dict)  # all store.* vars incl. _-prefixed

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, ensure_ascii=False)


def _to_json(value: Any) -> Any:
    """Recursively convert any decoded value to a JSON-safe form.

    Never raises or drops a container. Leaves that have no JSON representation
    become the string ``"<ClassName>"`` so they are visibly distinct from null.
    """
    if isinstance(value, _SCALAR):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _to_json(v) for k, v in value.items()
                if isinstance(k, _SCALAR)}
    if isinstance(value, _Stub):
        state = value.__dict__.get("_state")
        if isinstance(state, dict):
            return _to_json(state)
        args = value.__dict__.get("_args")
        if args is not None:
            return _to_json(args)
        return f"<{type(value).__name__}>"
    return f"<{type(value).__name__}>"


def load_log(save_path: str) -> tuple[dict, Any]:
    """Return the decoded ``(roots, rollback_log)`` from a .save file."""
    with zipfile.ZipFile(save_path) as z:
        raw = z.read("log")
    roots, log = _TolerantUnpickler(
        io.BytesIO(raw), encoding="latin-1", errors="replace"
    ).load()
    return roots, log


def read_meta(save_path: str) -> dict[str, Any]:
    """Read the thin `json` metadata member. No unpickling."""
    with zipfile.ZipFile(save_path) as z:
        return json.loads(z.read("json"))


def _current_node(log: Any) -> dict[str, Any] | None:
    """Pull the current script location (file, line) from the RollbackLog."""
    try:
        state = log.__dict__.get("_state", {})
        current = state["current"].__dict__["_state"]["context"]
        ctx = current.__dict__["_state"]
        node = ctx.get("current")
        if isinstance(node, (tuple, list)) and len(node) >= 3:
            return {"file": node[0], "line": node[-1]}
    except (KeyError, AttributeError, TypeError, IndexError):
        pass
    return None


EXCLUDED_STORE_VARS = {"args", "kwargs"}


def extract(save_path: str) -> SaveState:
    """Decode a .save into a SaveState of JSON-serializable game state."""
    meta = read_meta(save_path)
    roots, log = load_log(save_path)

    variables = {
        var_name: _to_json(value)
        for key, value in roots.items()
        if key.startswith("store.") and (var_name := key[len("store."):]) not in EXCLUDED_STORE_VARS
    }

    return SaveState(
        save_name=meta.get("_save_name", ""),
        renpy_version=".".join(str(x) for x in meta.get("_renpy_version", [])),
        game_version=str(meta.get("_version", "")),
        current_node=_current_node(log),
        variables=variables,
    )


def _main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m renpy_save_graph.extractor <save.save> [...]")
        return 2
    for path in argv:
        print(extract(path).to_json())
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))
