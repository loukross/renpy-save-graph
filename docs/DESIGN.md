# Design

## Goal

Replace a Ren'Py game's small, unorganized save-slot grid with a git-backed tree
of playthrough routes, and render a Detroit-style flowchart of the choices
leading to any save point.

## Save-file format (verified against real Ren'Py 7.4.x saves)

A `.save` file is a ZIP archive with these members:

| member          | contents                                                        |
| --------------- | --------------------------------------------------------------- |
| `screenshot.png`| save thumbnail (varies byte-for-byte even for "same" state)     |
| `extra_info`    | tiny                                                            |
| `json`          | thin metadata: `_save_name`, `_renpy_version`, `_version`, ...  |
| `renpy_version` | engine version string                                          |
| `log`           | **pickled rollback log** — full state history (the real payload)|

The `json` member is nearly useless for our purposes (just a save name and
versions). Everything queryable — variables, current label, and the sequence of
menu choices actually taken — lives in `log`.

### The `log` decode problem

`log` is a **Python-2 pickle** (engine reports version `7.4.x`) referencing
Ren'Py runtime classes: `RevertableList`, `RevertableDict`, `Style`, etc. A
plain `pickle.load` under Python 3 fails on both the encoding and the missing
classes.

Decode strategy, in preference order:

1. **Run inside the game's bundled Ren'Py/Python.** Ren'Py ships its own
   interpreter and all the classes; load the save there and dump JSON. Most
   robust, zero class-stubbing.
2. **Custom unpickler with stub classes** under Python 3 (`encoding="bytes"`,
   `find_class` returning lightweight stand-ins). Portable but brittle across
   engine versions.

A raw string-scan of `log` already shows legible variable names, labels
(e.g. `*_freeroam_label`), and flags — enough signal to expect a clean decode.

## Architecture

Two distinct repos:

- **This repo** — the application source (never contains real saves).
- **Library repo** — the source of truth for save points and where the
  branch/commit model lives. **One library graph per managed save slot** (see
  below), created at runtime.

### One graph per managed slot

A managed in-game save slot is bound to its own git graph. The slot holds
**exactly one working head** — the tip of that graph's current branch (git HEAD).
This is what keeps every save unambiguous.

- Player saves to the slot → watcher copies it into the library → `git add` the
  `save.save` + decoded `state.json` → `git commit` on the current branch. A save
  is *always* a commit relative to the current head, so it can't be ambiguous.
- **Branch point (explicit round-trip):** the tool checks out an earlier commit
  into the slot → player loads it in-game, diverges, saves → HEAD was not at a
  tip, so git forks a new branch. This is the *only* way a branch is born.
- **Browsing is external.** The route tree is explored in the app's own UI, not
  by projecting nodes across multiple native slots (that would make "save over a
  slot" ambiguous). The native load screen only ever shows the one working head.
- **Multiple managed slots = multiple independent graphs** (opt-in). Lets the
  user run parallel explorations that never interfere. Default: one slot, one
  graph.
- The app *owns* each managed slot and warns if something else overwrites it.

### In-game surface (non-invasive)

Integration works purely by manipulating the `.save` file — no game-code mods:

- **Thumbnail stamp** — when materializing the head into the slot, overlay
  `branch @hash` on the game's screenshot so the load screen shows *where the slot
  currently sits*. Stamp only the slot copy; the committed blob stays pristine
  (parallels "diff on state, not blob"). Requires unsigned saves (true here — no
  `signatures` member; verify per game).
- **Save name** — the player-entered name is read from the `json` member and used
  as the commit's free-form note. Not a structured protocol; structure comes from
  git.

### Commit shape

Each save point = one commit containing:

- `save.save` — opaque blob, used only to restore into the slot.
- `state.json` — decoded state; the basis for all diffs and the graph.

Then:

- `git log --graph --all` renders the route tree.
- `git diff A..B -- state.json` shows which choices/stats/flags changed.

## Constraints / decisions

- **Diff on state, not blobs.** Blobs delta poorly (each re-embeds the full
  rollback log) and thumbnails defeat byte-dedupe. `state.json` is canonical.
- **Commits = explicit saves.** For the target game this is *exact*: player-facing
  rollback is disabled, so there is no in-session divergence — every branch point
  is created deliberately via the explicit round-trip.
- **No merges.** Routes never recombine; git is a branching DAG only.
- **Personal-use scope.** Repo bloat from large blobs is acceptable.

## Correctness: parentage of save points

**Problem.** A `.save` carries no reliable pointer to the save it descends from.
The rollback log *does* encode recent history, but it is a bounded sliding window
(`rollback_limit` 100; observed logs of 82–129 entries), so it cannot link save
points that are far apart, and if the player plays past the window between saves
even a legitimate child shares nothing with its parent. **Ancestry therefore
cannot be inferred from save contents**, and rollback continuity is explicitly
*not* used as a correctness mechanism (non-overlap is ambiguous — long legitimate
play looks identical to a branch swap).

Parentage is instead established by **control, not inference**:

1. **Prevention by directory control (primary guarantee).** The tool is the sole
   gateway to the game's saves directory and keeps only the *current head's
   lineage* present; every other save point is archived out to the library.
   Because no foreign branch state is loadable, any save written to the managed
   slot is necessarily a descendant of the tracked head — no matter how long the
   player played. Parentage = the tool's bookkept head, made sound by what is
   physically in the folder. Forking = the tool archives the slot away and
   materializes commit Z, so Z's lineage becomes the only loadable state and the
   next save is provably Z's child. (This is also the tool's core job: archiving
   saves out of the cramped slot grid into the unlimited library.)

2. **Monotonic-invariant check (safety net).** Some variables only increase in
   forward play — cumulative counters, playtime, chapter/episode progression,
   `_seen_*` counts. If an incoming save has a *lower* value on any of these than
   the head it should descend from, it cannot be a natural continuation. This is
   **window-independent** — it catches a foreign overwrite even far past the
   rollback window. The invariant set is game-specific and configured per space.

3. **On a detected anomaly:** stamp a visually distinct **red warning band** on
   the slot thumbnail (e.g. "⚠ discontinuous — overwrote natural storyline"),
   mark the commit *suspect* in the graph, and pause auto-linking so the user
   decides (accept as a deliberate new root, or discard).

**Residual (out of scope):** deliberately bypassing the tool — e.g. hand-copying
an old save into the folder — defeats the guarantee.

This makes the **directory manager / watcher the load-bearing component** (more
than the git layer), since it is what guarantees correctness.

## `persistent` is out of scope for versioning

Ren'Py's `persistent` file (global unlocks, gallery, high scores, and the
engine's `_seen_ever` / `_seen_images` / `_chosen` "have I ever seen this"
bookkeeping) is deliberately **not** tracked by the branch/commit model.

Rationale:

- **Global, not per-branch.** One `persistent` is shared by every route; a
  per-branch copy is a category error — they would all just be the union.
- **Monotonic; never reverted.** It only accumulates, and reverting it would
  *lose* unlocks/seen-flags. Version control's core use (checking out an older
  version) is exactly what must never happen here, so tracking it buys nothing.
- **Doesn't align with commits.** It updates when content is *seen*, not when the
  game is saved, so its changes don't correspond to save points.
- **Safest handling is none.** Because the tool never touches `persistent`, the
  live file stays live and route-switching can't clobber it. Restore writes only
  the `.save` blob into the managed slot.

Notes / non-goals:

- It lives *outside* `game/saves/` — the authoritative copy is in the per-user
  Ren'Py dir (e.g. Windows `AppData/Roaming/RenPy/<game>/persistent`). It decodes
  as a `zlib`-compressed Python-2 pickle of a `Persistent` object (~576 fields).
- Optional future, explicitly outside git: a **monotonic backup** (timestamped
  copies, never auto-restored) as corruption insurance.
- Optional future: **read-only** decoding to show unlocked bonus content in the
  UI. Read, never write/revert.

## Roadmap

1. **Extractor** (`extractor.py`) — `.save` → `state.json`. Linchpin; validates
   that decoded state is legible. *(done)*
2. **Library manager** (`library.py`) — init library repo, commit save points,
   branch/checkout, materialize with stamped thumbnail. *(done)*
3. **Directory manager / watcher** — the load-bearing correctness component (see
   "Correctness"): own the saves dir, keep only the head's lineage loadable,
   detect saves and commit them as children of the tracked head, archive/restore
   on route switch, run the monotonic-invariant check and stamp warnings on
   anomalies. *(next)*
4. Graph/flowchart UI over `git log --graph` + `state.json` diffs.
