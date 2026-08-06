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
from dataclasses import dataclass
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


class Director:
    """Owns a game space's saves directory; gates detection, commit, and restore."""

    def __init__(self, config: SpaceConfig) -> None:
        self.config = config
        self._lib = Library.init(config.library_path)
        self._exclude_re = re.compile(config.slot_exclude) if config.slot_exclude else None

    @property
    def library(self) -> Library:
        return self._lib

    # -- slot discovery ------------------------------------------------------

    def slot_names(self) -> list[str]:
        """Slot names present in the saves dir, filtered by slot_exclude."""
        saves = sorted(
            f.stem for f in Path(self.config.saves_dir).glob("*.save")
        )
        if self._exclude_re:
            saves = [s for s in saves if not self._exclude_re.search(s)]
        return saves

    def slot_path(self, slot_name: str) -> Path:
        return Path(self.config.saves_dir) / f"{slot_name}.save"

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

    def _slot_changed(self, slot_name: str, hashes: dict[str, str]) -> bool:
        sp = self.slot_path(slot_name)
        if not sp.exists():
            return False
        return self._sha256(sp) != hashes.get(slot_name)

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
                hashes[slot_name] = self._sha256(sp)
                self._save_hashes(hashes)
                return None
            raise

        sp.write_bytes(restamp_save(sp.read_bytes(), commit_info.stamp_text()))

        hashes[slot_name] = self._sha256(sp)
        self._save_hashes(hashes)
        return IngestResult(slot_name=slot_name, commit=commit_info)

    def ingest_all(self, note: str | None = None) -> list[IngestResult]:
        """Ingest all changed slots. Returns results only for slots that committed."""
        results = []
        for slot_name in self.slot_names():
            result = self.ingest(slot_name, note=note)
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
        self._lib.materialize(self.slot_path(slot_name), stamp=True, stamp_name=stamp_name)
        hashes = self._load_hashes()
        hashes[slot_name] = self._sha256(self.slot_path(slot_name))
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
            hashes[slot_name] = self._sha256(sp)
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
