# Feature Inventory — Ren'Py Save Graph

A comprehensive breakdown of all features, architecture components, and design contracts in `renpy-save-graph`.

---

## 1. Storage & Persistence Engine

### Git-Backed DAG (Directed Acyclic Graph)
- **Repo Isolation**: Each game space maintains its own isolated Git repository inside system app data (`platformdirs`).
- **Commit Payload**: Every save point stores two files:
  - `save.save`: The binary Ren'Py pickle snapshot (used to restore into the active game slot).
  - `state.json`: Decoded game variables, choices, and current label string (used for queries, sorting, and diffing).
- **Straight-Line Restores**: Restoring to a previous save point uses `git checkout -B <active_branch> <commitish>` to prevent detached HEAD states and avoid sprouting synthetic visual branches.
- **Node Deletion & Reparenting**:
  - `reparent`: Deletes a commit and rebases all downstream commits onto its parent using `git rebase --onto parent_sha deleted_sha branch`, updating all affected commit SHAs cleanly.
  - `cascade`: Deletes a commit and all downstream descendant branches containing it.

### SQLite Metadata Cache (`DatabaseStore`)
- **Fast Cold Queries**: Sub-2ms response times for node metadata, variable values, and base64 thumbnails.
- **Concurrent WAL Mode**: Configured with `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=30000;` to handle concurrent reads/writes without database locks.
- **Lock-Free Subprocessing**: Git subprocesses and ZIP screenshot extractions execute outside SQLite transactions to keep transaction durations under 2ms.
- **Self-Healing Sync**: `sync_with_git()` automatically syncs SQLite with the Git repository and purges deleted or stale commit SHAs resulting from git rewrites or hard resets.

---

## 2. API & Server Infrastructure

### FastAPI REST Service
- **`GET /api/spaces`**: Lists available game spaces and global configurations.
- **`GET /api/spaces/{space_id}/slots/{slot}/graph`**: Returns DAG structure with node hints parsed dynamically from `node_hint_format` template strings.
- **`GET /api/spaces/{space_id}/slots/{slot}/states?vars=...`**: Returns variable states for all nodes in <110ms, accepting parameterized variable lists (`?vars=karma,money`) to reduce network payload size by 99.9%.
- **`GET /api/spaces/{space_id}/slots/{slot}/screenshots`**: Returns all node thumbnails in a single base64 JSON payload in <200ms.
- **`GET /api/spaces/{space_id}/slots/{slot}/diff/{shaA}/{shaB}`**: Calculates variable additions, deletions, changes, and numerical deltas between two save points.
- **`POST /api/spaces/{space_id}/slots/{slot}/restore`**: Restores game slot to target commit.
- **`DELETE /api/spaces/{space_id}/slots/{slot}/nodes/{sha}`**: Deletes node using specified strategy (`reparent` or `cascade`) and purges rewritten SHAs.

### Real-Time Live Watcher
- **Server-Sent Events (`GET /api/spaces/{space_id}/watch`)**: Monitors game save directories for file modifications via SHA256 file hashing.
- **Auto-Ingest**: Automatically commits new saves when the game creates a save file in the monitored slot.

---

## 3. Web User Interface (Vue.js + D3.js)

### Flowchart Canvas
- **D3 Directed Graph**: Renders nodes, branch connections, head indicators, and suspect flags.
- **Floating Auto-Select Toggle**: `⚡ Auto-select on add` floating button in the top right corner of the canvas. When enabled, newly committed save points are automatically selected, immediately populating the Diff and Inspector panels.
- **Base Sort Controls**: Chronological or Jaccard Leaf Similarity sorting with toggleable direction (`↓` Ascending / Oldest First, `↑` Descending / Newest First).
- **Date Range & Jump-to Navigation**: Quick jump options for Active Head, Root, Today, 3 Days, 7 Days, or custom date ranges.

### Inspection & Filtering
- **Dynamic Expression Filtering (`jsep` + `evalJsep`)**: JS expression evaluator supporting comparisons (`money > 0`, `karma == 5`).
- **Decoupled Regex Variable Filters**: Independent `🔍 Variable Filter Regex` input fields for Inspector and Diff panels with `Game vars` (`^[^_]`) fast toggles.
- **Shared Help Popover**: Single floating help popover (`?` buttons) anchoring dynamically via `getBoundingClientRect()`.
