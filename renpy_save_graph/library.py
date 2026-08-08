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
from .config import APP_NAME
from .thumbnail import optimize_save_thumbnail, restamp_save

BLOB = "save.save"
STATE = "state.json"

# Per-node metadata the app owns, kept in its own notes ref so `notes.rewriteRef`
# carries it across the rebase in `delete_node_reparent`, and so user note text
# stays readable inline as %N in the DAG walk.  Unlike the working tree, it is
# keyed by commit and travels with a clone.
META_REF = "refs/notes/meta"


_SEP = "\x1f"  # unit separator (fields within a commit)
_REC = "\x1e"  # record separator (between commits)

# Space-level metadata that isn't keyed by commit, so it has no place in a note.
# Its own branch, holding one file, never merged into a slot's history.
# Tells git to copy notes onto commits rewritten by a rebase, which is how a
# reparenting delete keeps them.  Git has no default for it.
_NOTES_REWRITE_REF = "refs/notes/*"

MANIFEST_BRANCH = "_meta"
MANIFEST = "manifest.json"
MANIFEST_SCHEMA = 1

# Branch identifiers that are never shown as user-visible names.
_UNNAMED_BRANCHES = {"master", "main", "_root", MANIFEST_BRANCH, "(detached)", ""}

def clear_dag_cache(lib_path: str | Path | None = None) -> None:
    pass


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
    def _git(self, *args: str, capture: bool = False, stdin: str | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            text=True,
            input=stdin,
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
        # Git only carries notes onto rewritten commits when this is set, and it
        # has no default.  Without it, deleting a node with the reparent strategy
        # rebases every descendant and silently drops their notes.  Set outside
        # the init branch above so libraries created before this also get it.
        try:
            already = lib._git("config", "--get", "notes.rewriteRef", capture=True)
        except GitError:
            already = ""
        if already != _NOTES_REWRITE_REF:
            try:
                lib._git("config", "notes.rewriteRef", _NOTES_REWRITE_REF)
            except GitError:
                # Every request opens the library, and the watch poll opens it
                # on a timer, so two can reach for .git/config.lock at once.
                # Losing that race must not fail the request -- reading the
                # config takes no lock, so the next opener sets it.
                pass
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
        # A clone keeps _root under refs/remotes until it is adopted.  Minting a
        # second root here would leave the cloned history hanging off a commit
        # nothing else descends from, and every walk excludes only the new one --
        # so the real root shows up as a stray node with no state or screenshot.
        for remote_root in self._remote_refs("refs/remotes/*/_root"):
            try:
                self._git("branch", "_root", remote_root)
                return
            except GitError:
                continue
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
    ) -> CommitInfo:
        """Copy a `.save` into the library, decode it, and commit on the current branch."""
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
        """All slot commits across all branches (excludes the root commit).

        Not `--all`, which also walks refs/notes/*, and not the manifest
        branch: neither holds save points.
        """
        root = self._root_sha()
        return self._dag(f"--exclude={MANIFEST_BRANCH}", "--branches",
                         f"^{root}", exclude_parent=root)

    def dag_for_branch(self, branch: str) -> list[NodeInfo]:
        """Slot commits on branch only, excluding the shared root ancestor."""
        try:
            self._git("rev-parse", "--verify", branch, capture=True)
        except GitError:
            return []
        root = self._root_sha()
        return self._dag(f"{root}..{branch}", exclude_parent=root)

    def fork_branches_of(self, slot_branch: str, all_slot_branches: list[str]) -> list[str]:
        """All fork branches belonging to slot_branch (named slot_branch-...)."""
        prefix = f"{slot_branch}-"
        return [b for b in self._all_branches() if b.startswith(prefix)]

    def sha_of(self, rev: str) -> str:
        return self._git("rev-parse", rev, capture=True)

    def slot_branches(self) -> list[str]:
        """The branches that name a slot, as opposed to a route forked off one.

        A fork is named `<slot>-<something>`, so a branch with a prefix-parent
        among the others is a route.  A game whose own slot names nest that way
        (`1-1-LT1` and `1-1-LT1-2`) is indistinguishable here -- the same
        ambiguity `fork_branches_of` already lives with.
        """
        named = [b for b in self._all_branches() if b not in _UNNAMED_BRANCHES]
        return sorted(
            b for b in named
            if not any(b.startswith(f"{other}-") for other in named if other != b)
        )

    def _remote_refs(self, pattern: str = "refs/remotes") -> list[str]:
        """Remote-tracking refs as `<remote>/<branch>`, minus the HEAD pointers."""
        try:
            raw = self._git("for-each-ref", "--format=%(refname:short)", pattern, capture=True)
        except GitError:
            return []
        return [r for r in raw.splitlines() if r and r.partition("/")[2] not in ("", "HEAD")]

    def adopt_remote_branches(self) -> list[str]:
        """Give a clone's remote-tracking refs local branches of the same name.

        `git clone` checks out one branch and leaves the rest -- `_root` and
        every route included -- under refs/remotes.  Everything here walks local
        branches, so a freshly cloned library reads as almost empty until this
        runs.  A no-op on a library with no remote.
        """
        local = set(self._all_branches())
        adopted = []
        for remote_ref in self._remote_refs():
            name = remote_ref.partition("/")[2]
            if name in local:
                continue
            try:
                self._git("branch", name, remote_ref)
                adopted.append(name)
            except GitError:
                continue
        return adopted

    def fetch_notes(self) -> None:
        """Pull note refs from the remote, which `git clone` skips by default."""
        try:
            remotes = self._git("remote", capture=True).splitlines()
            if not remotes:
                return
            self._git("fetch", "--quiet", remotes[0], "+refs/notes/*:refs/notes/*")
        except GitError:
            pass  # offline, or the remote has no notes; the graph still opens

    def _all_branches(self) -> list[str]:
        try:
            raw = self._git("branch", "--format=%(refname:short)", capture=True)
            return [b for b in raw.splitlines() if b]
        except GitError:
            return []

    def dag_for_slot(self, slot_branch: str, all_slot_branches: list[str]) -> list[NodeInfo]:
        """Commits for this slot and all its fork branches."""
        root = self._root_sha()
        forks = self.fork_branches_of(slot_branch, all_slot_branches)
        all_branches = [b for b in [slot_branch] + forks if b]
        return self._dag(*all_branches, f"^{root}", exclude_parent=root)

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

    # -- portable per-node metadata ------------------------------------------

    def meta_all(self) -> dict[str, dict[str, Any]]:
        """sha → meta dict for every branch commit, in one git call.

        Scoped the same way as `dag`: refs/notes/* and the manifest branch are
        bookkeeping, not save points.
        """
        try:
            raw = self._git(
                "log", f"--exclude={MANIFEST_BRANCH}", "--branches",
                "--no-notes", f"--notes={META_REF}",
                f"--format=tformat:%H{_SEP}%N{_REC}", capture=True,
            )
        except GitError:
            return {}
        out: dict[str, dict[str, Any]] = {}
        for record in filter(None, raw.split(_REC)):
            sha, _, note = record.strip("\n").partition(_SEP)
            if not note.strip():
                continue
            try:
                out[sha.strip()] = json.loads(note)
            except ValueError:
                continue  # hand-edited or from a newer schema; ignore
        return out

    def get_meta(self, sha: str) -> dict[str, Any]:
        try:
            return json.loads(self._git("notes", f"--ref={META_REF}", "show", sha, capture=True))
        except (GitError, ValueError):
            return {}

    def set_meta(self, sha: str, **fields: Any) -> None:
        """Merge `fields` into sha's meta note; a None value drops that key."""
        data = {**self.get_meta(sha), **fields}
        data = {k: v for k, v in data.items() if v is not None}
        if data:
            self._git("notes", f"--ref={META_REF}", "add", "-f", "-m",
                      json.dumps(data, separators=(",", ":")), sha)
        else:
            try:
                self._git("notes", f"--ref={META_REF}", "remove", sha)
            except GitError:
                pass

    # -- space manifest ------------------------------------------------------

    def read_manifest(self) -> dict[str, Any]:
        """The space-level settings a clone of this library carries with it."""
        try:
            return json.loads(self._git("show", f"{MANIFEST_BRANCH}:{MANIFEST}", capture=True))
        except (GitError, ValueError):
            return {}

    def write_manifest(self, data: dict[str, Any]) -> None:
        """Stamp `data` as this app's and commit it to the manifest branch.

        The app/schema keys are added here rather than by callers so every
        library carries the same marker, which is what import validates
        against.  Identical content is skipped, so republishing on startup
        doesn't pile up commits.

        Builds the commit out of git objects directly instead of checking the
        branch out: the working tree holds the save point currently materialized
        into the player's slot, and HEAD is the branch ingest commits onto.  A
        branch switch would swap that file out mid-session, and a watcher poll
        landing in the same window would commit a save point onto _meta.  This
        way touches no index, no working tree, and no HEAD.
        """
        payload = {"app": APP_NAME, "schema": MANIFEST_SCHEMA, **data}
        if payload == self.read_manifest():
            return
        blob = self._git("hash-object", "-w", "--stdin", capture=True,
                         stdin=json.dumps(payload, indent=2, sort_keys=True))
        tree = self._git("mktree", capture=True, stdin=f"100644 blob {blob}\t{MANIFEST}\n")
        parent: list[str] = []
        try:
            parent = ["-p", self._git("rev-parse", f"refs/heads/{MANIFEST_BRANCH}", capture=True)]
        except GitError:
            pass  # first write; the branch is born here
        commit = self._git("commit-tree", tree, *parent, "-m", "update manifest", capture=True)
        self._git("update-ref", f"refs/heads/{MANIFEST_BRANCH}", commit)

    # -- tags ----------------------------------------------------------------

    @staticmethod
    def _clean_tag(tag_name: str) -> str:
        return tag_name.strip().lstrip("#").lower()

    def tags_all(self) -> dict[str, list[str]]:
        """sha → its tags, for every commit that has any."""
        return {
            sha: sorted(meta["tags"])
            for sha, meta in self.meta_all().items()
            if meta.get("tags")
        }

    def add_tag(self, sha: str, tag_name: str) -> None:
        tag = self._clean_tag(tag_name)
        if not tag:
            return
        tags = set(self.get_meta(sha).get("tags", []))
        tags.add(tag)
        self.set_meta(sha, tags=sorted(tags))

    def remove_tag(self, sha: str, tag_name: str) -> None:
        tags = set(self.get_meta(sha).get("tags", []))
        tags.discard(self._clean_tag(tag_name))
        # An empty list would linger as an empty note; None drops the key.
        self.set_meta(sha, tags=sorted(tags) or None)

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
