"""The library: one git graph per managed save slot.

A library is a git repo whose working tree always holds a single save point as
two tracked files:

- ``save.save``  -- the opaque Ren'Py blob (restored into the slot verbatim).
- ``state.json`` -- the decoded, diffable game state.

Each commit is a save point; each branch is a playthrough route. The slot's
current file corresponds to the working head (git HEAD). A save is therefore
always a commit relative to the current head, and a branch is born only when the
user checks out an earlier commit and then diverges (the explicit round-trip).
See docs/DESIGN.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import extractor
from .thumbnail import optimize_save_thumbnail, restamp_save

BLOB = "save.save"
STATE = "state.json"

_SEP = "\x1f"  # unit separator (fields within a commit)
_REC = "\x1e"  # record separator (between commits)

# Branch identifiers that are never shown as user-visible names.
_UNNAMED_BRANCHES = {"master", "main", "_root", "(detached)", ""}

_DAG_CACHE: dict[str, tuple[str, list[NodeInfo]]] = {}


def clear_dag_cache(lib_path: str | Path | None = None) -> None:
    if lib_path is None:
        _DAG_CACHE.clear()
    else:
        p_str = str(lib_path)
        keys_to_del = [k for k in _DAG_CACHE if k.startswith(p_str)]
        for k in keys_to_del:
            _DAG_CACHE.pop(k, None)


class GitError(RuntimeError):
    pass


@dataclass
class NodeInfo:
    sha: str
    short: str
    parents: list[str]
    subject: str
    when: int
    note: str = ""


@dataclass
class CommitInfo:
    sha: str
    short: str
    branch: str  # current branch name, or "(detached)"
    subject: str
    when: int  # unix timestamp

    def stamp_text(self) -> str:
        """Overlay text: hash alone, plus the branch only if the user named it."""
        if self.branch in _UNNAMED_BRANCHES:
            return f"@{self.short}"
        return f"{self.branch} @{self.short}"


class Library:
    """A single-slot save graph backed by a git repo."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # -- git plumbing --------------------------------------------------------
    def _git(self, *args: str, capture: bool = False) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
        return (result.stdout or "").strip()

    # -- lifecycle -----------------------------------------------------------
    @classmethod
    def init(cls, path: str | Path) -> "Library":
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        lib = cls(p)
        if not (p / ".git").exists():
            lib._git("init", "-q")
            lib._git("config", "user.name", "renpy-save-graph")
            lib._git("config", "user.email", "save-graph@localhost")
        lib._init_root()
        return lib

    def _init_root(self) -> None:
        """Ensure the shared root commit exists and .gitignore ignores graph.sqlite."""
        gitignore = self.path / ".gitignore"
        if not gitignore.exists() or "graph.sqlite" not in gitignore.read_text(encoding="utf-8"):
            gitignore.write_text("graph.sqlite*\n", encoding="utf-8")
        try:
            self._git("rev-parse", "_root", capture=True)
            return  # already initialised
        except GitError:
            pass
        self._git("symbolic-ref", "HEAD", "refs/heads/_root")
        self._git("commit", "--allow-empty", "-q", "-m", "root")

    def _root_sha(self) -> str:
        return self._git("rev-parse", "_root", capture=True)

    def ensure_branch(self, name: str) -> None:
        """Switch to branch `name`, creating it from the root if it doesn't exist."""
        try:
            current = self._git("symbolic-ref", "--short", "HEAD", capture=True)
            if current == name:
                return
        except GitError:
            pass  # detached HEAD
        try:
            self._git("checkout", "-q", name)
        except GitError:
            # Branch doesn't exist — branch off the shared root so every slot
            # starts with an independent, clean history.
            self._git("checkout", "-q", "-b", name, self._root_sha())

    # -- writing save points -------------------------------------------------
    def commit_savepoint(
        self,
        save_path: str | Path,
        note: str | None = None,
        body_extra: str | None = None,
    ) -> CommitInfo:
        """Copy a `.save` into the library, decode it, and commit on the current branch.

        ``body_extra``, if given, is appended as a separate commit-message paragraph
        (used by the director to record suspect-invariant details).
        """
        state = extractor.extract(str(save_path))
        raw_bytes = Path(save_path).read_bytes()
        opt_bytes = optimize_save_thumbnail(raw_bytes)
        (self.path / BLOB).write_bytes(opt_bytes)
        (self.path / STATE).write_text(state.to_json(), encoding="utf-8")

        if not self._git("status", "--porcelain", capture=True):
            raise GitError("nothing to commit — save is identical to the current head")

        node = state.current_node or {}
        location = f"{node.get('file', '?')}:{node.get('line', '?')}"
        fallback = datetime.now().strftime("%Y-%m-%d %H:%M")
        subject = (note or state.save_name or fallback).splitlines()[0][:72]
        args = ["commit", "-q", "-m", subject, "-m", f"node: {location}"]
        if body_extra:
            args += ["-m", body_extra]
        self._git("add", BLOB, STATE)
        self._git(*args)
        clear_dag_cache(self.path)
        return self.head()

    # -- branching / switching ----------------------------------------------
    def branch_from(self, commitish: str, new_branch: str) -> CommitInfo:
        """Start a new route: create and switch to ``new_branch`` at ``commitish``.

        Afterward the working tree (BLOB/STATE) is that commit's, ready to
        materialize into the slot for the player to diverge from.
        """
        try:
            self._git("rev-parse", "--verify", new_branch, capture=True)
            raise GitError(f"branch '{new_branch}' already exists — choose a different name")
        except GitError as e:
            if "already exists" in str(e):
                raise
        self._git("checkout", "-q", "-b", new_branch, commitish)
        return self.head()

    def switch_branch(self, branch: str) -> CommitInfo:
        """Switch to an existing route; working tree becomes its tip."""
        self._git("checkout", "-q", branch)
        return self.head()

    def checkout(self, commitish: str) -> CommitInfo:
        """Checkout any commit or branch by name (may result in detached HEAD)."""
        self._git("checkout", "-q", commitish)
        return self.head()

    # -- graph / diff -------------------------------------------------------

    def dag(self) -> list[NodeInfo]:
        """All slot commits across all branches (excludes the root commit)."""
        root = self._root_sha()
        return self._dag("--all", f"^{root}", exclude_parent=root)

    def dag_for_branch(self, branch: str) -> list[NodeInfo]:
        """Slot commits on branch only, excluding the shared root ancestor."""
        try:
            self._git("rev-parse", "--verify", branch, capture=True)
        except GitError:
            return []
        root = self._root_sha()
        return self._dag(f"{root}..{branch}", exclude_parent=root)

    def fork_branches_of(self, slot_branch: str, all_slot_branches: list[str]) -> list[str]:
        """Non-slot branches that share history with slot_branch beyond the root commit."""
        root = self._root_sha()
        slot_set = set(all_slot_branches) | {"_root"}
        non_slot = [b for b in self._all_branches() if b not in slot_set]
        result = []
        for b in non_slot:
            try:
                merge_base = self._git("merge-base", b, slot_branch, capture=True)
                if merge_base != root:
                    result.append(b)
            except GitError:
                pass
        return result

    def _all_branches(self) -> list[str]:
        try:
            raw = self._git("branch", "--format=%(refname:short)", capture=True)
            return [b for b in raw.splitlines() if b]
        except GitError:
            return []

    def dag_for_slot(self, slot_branch: str, all_slot_branches: list[str]) -> list[NodeInfo]:
        """Commits for this slot and all its fork branches with fast rev-parse cache validation."""
        try:
            head_sha = self._git("rev-parse", f"refs/heads/{slot_branch}", capture=True)
        except GitError:
            try:
                head_sha = self._git("rev-parse", "HEAD", capture=True)
            except GitError:
                head_sha = ""

        cache_key = f"{self.path}:{slot_branch}"
        cached = _DAG_CACHE.get(cache_key)
        if cached and cached[0] == head_sha and head_sha != "":
            return cached[1]

        root = self._root_sha()
        forks = self.fork_branches_of(slot_branch, all_slot_branches)
        nodes = self._dag(slot_branch, *forks, f"^{root}", exclude_parent=root)
        if head_sha:
            _DAG_CACHE[cache_key] = (head_sha, nodes)
        return nodes

    def _dag(self, *rev_args: str, exclude_parent: str = "") -> list[NodeInfo]:
        try:
            raw = self._git(
                "log", *rev_args, "--topo-order",
                f"--format=tformat:%H{_SEP}%P{_SEP}%ct{_SEP}%s{_SEP}%N{_REC}",
                capture=True,
            )
        except GitError:
            return []
        nodes: list[NodeInfo] = []
        for record in filter(None, raw.split(_REC)):
            record = record.strip("\n")
            if not record:
                continue
            parts = record.split(_SEP, 4)
            if len(parts) < 4:
                continue
            sha, parents_raw, when_s, subject = parts[:4]
            note = parts[4].strip() if len(parts) > 4 else ""
            parents = [p for p in parents_raw.split()
                       if p != exclude_parent] if parents_raw.strip() else []
            nodes.append(NodeInfo(sha=sha, short=sha[:7], parents=parents,
                                  subject=subject, when=int(when_s), note=note))
        return nodes

    def all_states_for_slot(self, slot_branch: str, all_slot_branches: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch all variable dictionaries for all slot nodes in a single fast git cat-file binary process."""
        nodes = self.dag_for_slot(slot_branch, all_slot_branches)
        if not nodes:
            return {}
        batch_input = "".join(f"{n.sha}:{STATE}\n" for n in nodes).encode("utf-8")
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=str(self.path),
            input=batch_input,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        result: dict[str, dict[str, Any]] = {}
        raw_bytes = proc.stdout or b""
        offset = 0
        buf_len = len(raw_bytes)
        while offset < buf_len:
            header_end = raw_bytes.find(b"\n", offset)
            if header_end == -1:
                break
            header_line = raw_bytes[offset:header_end].decode("ascii", errors="ignore")
            offset = header_end + 1
            parts = header_line.split()
            if len(parts) == 3 and parts[1] == "blob":
                sha = parts[0].split(":")[0]
                size = int(parts[2])
                content_bytes = raw_bytes[offset:offset + size]
                offset += size + 1
                try:
                    result[sha] = json.loads(content_bytes).get("variables", {})
                except Exception:
                    result[sha] = {}
            else:
                pass
        return result

    def set_note(self, sha: str, text: str) -> None:
        if text.strip():
            self._git("notes", "add", "-f", "-m", text.strip(), sha)
        else:
            try:
                self._git("notes", "remove", sha)
            except GitError:
                pass
        clear_dag_cache(self.path)

    def diff_state(self, sha1: str, sha2: str) -> dict[str, tuple[Any, Any]]:
        """Variables that changed between two commits (sorted by name)."""
        def load(sha: str) -> dict[str, Any]:
            try:
                raw = self._git("show", f"{sha}:{STATE}", capture=True)
                return json.loads(raw).get("variables", {})
            except GitError:
                return {}
        v1, v2 = load(sha1), load(sha2)
        all_keys = set(v1) | set(v2)
        return {k: (v1.get(k), v2.get(k))
                for k in sorted(all_keys) if v1.get(k) != v2.get(k)}

    def branch_tips(self) -> dict[str, list[str]]:
        """Map commit sha → list of user-given branch names at that commit tip."""
        try:
            raw = self._git(
                "branch", "--format=%(objectname) %(refname:short)", capture=True
            )
        except GitError:
            return {}
        result: dict[str, list[str]] = {}
        for line in filter(None, raw.splitlines()):
            sha, name = line.split(None, 1)
            if name not in _UNNAMED_BRANCHES:
                result.setdefault(sha, []).append(name)
        return result

    def blob_bytes(self, sha: str, path: str = BLOB) -> bytes:
        """Return raw bytes of a tracked file at a given commit."""
        result = subprocess.run(
            ["git", "show", f"{sha}:{path}"],
            cwd=str(self.path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise GitError(f"git show {sha}:{path} failed:\n{result.stderr.decode().strip()}")
        return result.stdout

    # -- reading -------------------------------------------------------------
    def current_branch(self) -> str:
        name = self._git("rev-parse", "--abbrev-ref", "HEAD", capture=True)
        return name if name != "HEAD" else "(detached)"

    def head(self) -> CommitInfo:
        raw = self._git("show", "-s", f"--format=%H{_SEP}%h{_SEP}%ct{_SEP}%s", "HEAD", capture=True)
        sha, short, when, subject = raw.split(_SEP, 3)
        return CommitInfo(sha, short, self.current_branch(), subject, int(when))

    def log(self, all_branches: bool = True) -> list[CommitInfo]:
        args = ["log", f"--format=%H{_SEP}%h{_SEP}%ct{_SEP}%s"]
        if all_branches:
            args.append("--all")
        out = self._git(*args, capture=True)
        commits: list[CommitInfo] = []
        for line in filter(None, out.splitlines()):
            sha, short, when, subject = line.split(_SEP, 3)
            commits.append(CommitInfo(sha, short, "", subject, int(when)))
        return commits

    def graph_text(self) -> str:
        """Human-readable route tree, à la ``git log --graph``."""
        return self._git(
            "log", "--all", "--graph", "--date-order",
            "--format=%h %d %s", capture=True,
        )

    # -- materializing into a slot ------------------------------------------
    def materialize(self, dest_slot: str | Path, stamp: bool = True, stamp_name: str | None = None) -> CommitInfo:
        """Write the current working-head blob into a game save slot.

        With ``stamp`` the slot copy's thumbnail is overlaid with ``branch @hash``;
        the library blob itself is never modified.
        """
        head = self.head()
        blob = (self.path / BLOB).read_bytes()
        if stamp:
            if stamp_name:
                stamp_str = f"{stamp_name} @{head.short}"
            else:
                stamp_str = head.stamp_text()
            blob = restamp_save(blob, stamp_str)
        Path(dest_slot).write_bytes(blob)
        return head

    # -- node deletion & reparenting ----------------------------------------
    def delete_node_reparent(self, sha: str) -> set[str]:
        """Delete commit ``sha`` and reparent downstream commits onto its parent.

        Returns the set of old commit SHAs that no longer exist after the rebase
        (the deleted commit itself plus every descendant that was rewritten).
        """
        parents_raw = self._git("log", "-1", "--format=%P", sha, capture=True).strip()
        if not parents_raw:
            raise GitError("Cannot delete root commit")
        parent_sha = parents_raw.split()[0]

        raw_branches = self._git("branch", "--contains", sha, "--format=%(refname:short)", capture=True)
        branches = [b for b in raw_branches.splitlines() if b and b not in _UNNAMED_BRANCHES]

        # Collect every SHA that rebase will rewrite (sha + its descendants on each branch).
        removed: set[str] = {sha}
        for b in branches:
            out = self._git("log", f"{sha}..{b}", "--format=%H", capture=True)
            removed.update(s for s in out.splitlines() if s)

        current = self.current_branch()
        self._git("checkout", "-q", parent_sha)

        for b in branches:
            try:
                self._git("rebase", "-X", "theirs", "--onto", parent_sha, sha, b)
            except GitError:
                self._git("rebase", "--abort")
                raise GitError(f"Failed to reparent branch {b} onto {parent_sha}")

        if current in branches:
            try:
                self._git("checkout", "-q", current)
            except GitError:
                pass
        clear_dag_cache(self.path)
        return removed

    def delete_node_cascade(self, sha: str) -> set[str]:
        """Delete commit ``sha`` and all downstream branches/commits containing it.

        Returns the set of old commit SHAs that no longer exist.
        """
        parents_raw = self._git("log", "-1", "--format=%P", sha, capture=True).strip()
        if not parents_raw:
            raise GitError("Cannot delete root commit")
        parent_sha = parents_raw.split()[0]

        raw_branches = self._git("branch", "--contains", sha, "--format=%(refname:short)", capture=True)
        branches = [b for b in raw_branches.splitlines() if b and b not in _UNNAMED_BRANCHES]

        removed: set[str] = {sha}
        for b in branches:
            out = self._git("log", f"{sha}..{b}", "--format=%H", capture=True)
            removed.update(s for s in out.splitlines() if s)

        self._git("checkout", "-q", parent_sha)

        for b in branches:
            try:
                self._git("branch", "-f", b, parent_sha)
            except GitError:
                pass

        try:
            self._git("reflog", "expire", "--expire=now", "--all")
            self._git("gc", "--prune=now")
        except GitError:
            pass
        clear_dag_cache(self.path)
        return removed
