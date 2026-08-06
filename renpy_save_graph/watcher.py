"""Directory manager: owns a game space's save folder and gates all writes.

The *Director* ties a game saves directory to a Library (git graph).  Its job:

- Detect when the player writes a new save into any managed slot and commit it.
- Materialize any library commit back into a slot (for route switching).
- Apply a slot exclude regex to ignore unwanted slots (e.g. autosaves).

Each save slot maps to a git branch of the same name.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .library import CommitInfo, GitError, Library
from .thumbnail import restamp_save

_SLOT_HASHES_FILE = ".slot_hashes.json"
_SLOT_BRANCHES_FILE = ".slot_branches.json"


@dataclass
class IngestResult:
    slot_name: str
    commit: CommitInfo


@dataclass
class SpaceConfig:
    saves_dir: Path
    library_path: Path
    slot_exclude: str = ""  # regex; matching slot names are ignored
    additional_saves_dirs: list[Path] = field(default_factory=list)


class Director:
    """Owns a game space's saves directory; gates detection, commit, and restore."""

    def __init__(self, config: SpaceConfig) -> None:
        self.config = config
        self._lib = Library.init(config.library_path)
        self._exclude_re = re.compile(config.slot_exclude) if config.slot_exclude else None

    @property
    def library(self) -> Library:
        return self._lib

    @property
    def all_saves_dirs(self) -> list[Path]:
        """Primary saves dir first, then the additional ones, deduplicated."""
        dirs: list[Path] = []
        seen: set[Path] = set()
        for d in [self.config.saves_dir, *self.config.additional_saves_dirs]:
            p = Path(d).expanduser()
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                dirs.append(p)
        return dirs

    # -- slot discovery ------------------------------------------------------

    def _slot_files(self, slot_name: str | None = None) -> list[Path]:
        """Every ``.save`` file across the watched dirs, optionally for one slot."""
        files = []
        for d in self.all_saves_dirs:
            if not d.is_dir():
                continue
            for f in sorted(d.iterdir()):
                if not f.is_file() or not f.name.lower().endswith(".save"):
                    continue
                if slot_name is None or f.stem == slot_name:
                    files.append(f)
        return files

    def slot_names(self) -> list[str]:
        """Slot names present in the saves dirs, filtered by slot_exclude."""
        saves = sorted({f.stem for f in self._slot_files()})
        if self._exclude_re:
            saves = [s for s in saves if not self._exclude_re.search(s)]
        return saves

    def slot_path(self, slot_name: str) -> Path:
        """The file to ingest for this slot.

        A slot name can exist in more than one watched dir (a game split across
        installs reuses the same slot names).  Prefer a file that actually
        changed since we last recorded it; among equals take the newest.  If two
        changed at once the other one is picked up on the next poll.
        """
        candidates = self._slot_files(slot_name)
        if not candidates:
            return self.all_saves_dirs[0] / f"{slot_name}.save"
        hashes = self._load_hashes()
        changed = [c for c in candidates if self._file_changed(c, slot_name, hashes)]
        return max(changed or candidates, key=lambda p: p.stat().st_mtime)

    # -- hash tracking -------------------------------------------------------

    def _load_hashes(self) -> dict[str, str]:
        p = Path(self.config.library_path) / _SLOT_HASHES_FILE
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_hashes(self, hashes: dict[str, str]) -> None:
        p = Path(self.config.library_path) / _SLOT_HASHES_FILE
        p.write_text(json.dumps(hashes), encoding="utf-8")

    def _load_branches(self) -> dict[str, str]:
        """Maps slot_name → active branch (defaults to slot_name if absent)."""
        p = Path(self.config.library_path) / _SLOT_BRANCHES_FILE
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_branches(self, branches: dict[str, str]) -> None:
        p = Path(self.config.library_path) / _SLOT_BRANCHES_FILE
        p.write_text(json.dumps(branches), encoding="utf-8")

    def _active_branch(self, slot_name: str) -> str:
        return self._load_branches().get(slot_name, slot_name)

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _file_changed(self, path: Path, slot_name: str, hashes: dict[str, str]) -> bool:
        """True if `path` differs from the hash last recorded *for that file*.

        Hashes are keyed by absolute path so the same slot name in two watched
        dirs is tracked separately.  Spaces created before additional saves dirs
        existed only have a slot-name key, which described the primary dir's
        file — honour it there so upgrading a space doesn't re-ingest everything.
        A file we have never hashed counts as changed, so a newly watched dir can
        never be skipped forever.
        """
        key = str(path.resolve())
        if key in hashes:
            return self._sha256(path) != hashes[key]
        if slot_name in hashes and path.parent.resolve() == self.all_saves_dirs[0].resolve():
            return self._sha256(path) != hashes[slot_name]
        return True

    def _record_hash(self, hashes: dict[str, str], slot_name: str, sp: Path) -> None:
        """Record `sp`'s hash under its path.

        The legacy slot-name key is deliberately left untouched: it describes
        the primary dir's file at upgrade time, and overwriting it with another
        dir's hash would make that file look changed and re-ingest it.
        """
        hashes[str(sp.resolve())] = self._sha256(sp)

    def _slot_changed(self, slot_name: str, hashes: dict[str, str]) -> bool:
        sp = self.slot_path(slot_name)
        return sp.exists() and self._file_changed(sp, slot_name, hashes)

    def _ensure_active_branch_for_ingest(self, slot_name: str) -> str:
        """Ensure the slot is on an active branch, auto-forking if at a historical commit."""
        active = self._active_branch(slot_name)
        is_sha = len(active) >= 7 and all(c in "0123456789abcdefABCDEF" for c in active)
        if not is_sha:
            self._lib.ensure_branch(active)
            return active

        all_tips = self._lib.branch_tips()
        all_branches = set()
        for b_list in all_tips.values():
            all_branches.update(b_list)

        short_sha = active[:7]
        num = 1
        while f"{slot_name}-{short_sha}-{num}" in all_branches:
            num += 1

        new_branch = f"{slot_name}-{short_sha}-{num}"
        self._lib.branch_from(active, new_branch)

        branches = self._load_branches()
        branches[slot_name] = new_branch
        self._save_branches(branches)
        return new_branch

    # -- ingest --------------------------------------------------------------

    def ingest(self, slot_name: str, note: str | None = None) -> IngestResult | None:
        """Commit slot_name if it changed. Returns None if nothing new."""
        hashes = self._load_hashes()
        if not self._slot_changed(slot_name, hashes):
            return None

        sp = self.slot_path(slot_name)
        # Auto-fork if sitting at a historical commit SHA from a restore
        self._ensure_active_branch_for_ingest(slot_name)

        try:
            commit_info = self._lib.commit_savepoint(sp, note=note)
        except GitError as exc:
            if "nothing to commit" in str(exc):
                self._record_hash(hashes, slot_name, sp)
                self._save_hashes(hashes)
                return None
            raise

        sp.write_bytes(restamp_save(sp.read_bytes(), commit_info.stamp_text()))

        self._record_hash(hashes, slot_name, sp)
        self._save_hashes(hashes)
        return IngestResult(slot_name=slot_name, commit=commit_info)

    def ingest_all(self, note: str | None = None) -> list[IngestResult]:
        """Ingest all changed slots. Returns results only for slots that committed.

        A single slot's ingest failure (e.g. a save file caught mid-write, or a
        one-off decode error) is logged and skipped rather than aborting the
        whole pass — otherwise one bad slot would block every other slot in the
        space from ever being watched again until its file changed.
        """
        results = []
        for slot_name in self.slot_names():
            try:
                result = self.ingest(slot_name, note=note)
            except Exception:
                import traceback
                print(f"[watcher] ingest failed for slot {slot_name!r}:", file=sys.stderr)
                traceback.print_exc()
                continue
            if result is not None:
                results.append(result)
        return results

    # -- route switching -----------------------------------------------------

    def switch_to(
        self, slot_name: str, commitish: str, new_branch: str | None = None
    ) -> CommitInfo:
        """Materialize a commit into a slot file."""
        if new_branch is not None:
            self._lib.ensure_branch(self._active_branch(slot_name))
            info = self._lib.branch_from(commitish, new_branch)
            target_branch = new_branch
        else:
            try:
                self._lib._git("rev-parse", "--verify", f"refs/heads/{commitish}", capture=True)
                info = self._lib.checkout(commitish)
                target_branch = commitish
            except GitError:
                info = self._lib.checkout(commitish)
                target_branch = commitish

        if info.branch in ("(detached)", ""):
            info = CommitInfo(sha=info.sha, short=info.short, branch=slot_name, subject=info.subject, when=info.when)

        stamp_name = target_branch if target_branch and len(target_branch) < 40 else slot_name
        sp = self.slot_path(slot_name)
        self._lib.materialize(sp, stamp=True, stamp_name=stamp_name)
        hashes = self._load_hashes()
        self._record_hash(hashes, slot_name, sp)
        self._save_hashes(hashes)

        branches = self._load_branches()
        branches[slot_name] = target_branch
        self._save_branches(branches)
        return info

    def delete_node(self, slot_name: str, sha: str, strategy: str = "reparent") -> set[str]:
        """Delete node `sha` using `strategy` ('reparent' or 'cascade').

        Returns the set of old commit SHAs that no longer exist in git history.
        """
        try:
            head_sha = self._lib.head().sha
        except GitError:
            head_sha = None
        if sha == head_sha:
            raise GitError("Cannot delete the current active save point")

        if strategy == "cascade":
            removed = self._lib.delete_node_cascade(sha)
        else:
            removed = self._lib.delete_node_reparent(sha)

        active = self._active_branch(slot_name)
        try:
            self._lib.ensure_branch(active)
            sp = self.slot_path(slot_name)
            self._lib.materialize(sp, stamp=True, stamp_name=active)
            hashes = self._load_hashes()
            self._record_hash(hashes, slot_name, sp)
            self._save_hashes(hashes)
        except Exception:
            pass
        return removed


# -- CLI --------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python -m renpy_save_graph.watcher <library> <saves_dir> <slot> [note]")
        return 2
    from .watcher import SpaceConfig, Director
    config = SpaceConfig(saves_dir=Path(argv[1]), library_path=Path(argv[0]))
    d = Director(config)
    result = d.ingest(argv[2], note=argv[3] if len(argv) > 3 else None)
    if result is None:
        print("nothing new")
    else:
        print(f"committed {result.commit.short}  {result.commit.subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
