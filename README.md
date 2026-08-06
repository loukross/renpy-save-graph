# Ren'Py Save Graph

[![Integration Tests](https://github.com/lucjross/renpy-save-graph/actions/workflows/test.yml/badge.svg)](https://github.com/lucjross/renpy-save-graph/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

**Ren'Py Save Graph** turns a game's flat save slots into a Git-backed tree of playthrough routes, displaying a *Detroit: Become Human*–style interactive flowchart of choices, variable state diffs, and save point screenshots.

---

## 🚀 Quick Start

### Requirements
- **Python 3.11+**
- **Git**

### How to Run

#### Option 1: Desktop Launcher Scripts
Download or clone the repository and run the launcher script for your operating system:
- **Windows**: Double-click `run.bat`
- **macOS / Linux**: Run `./run.sh`

The launcher script installs package dependencies and starts the local web server at `http://localhost:5555/`.

#### Option 2: Package Manager (`pip` / `pipx`)
Install and launch directly using Python package managers:

```bash
# Standard installation
pip install renpy-save-graph
renpy-save-graph

# Isolated environment installation
pipx install renpy-save-graph
renpy-save-graph
```

---

## 🎮 Usage & How It Works

**Ren'Py Save Graph** introduces a streamlined way to play choice-heavy Ren'Py visual novels. Instead of juggling dozens of manual save slots or losing track of decision points, you operate using a **single dedicated save slot** while the app manages your full story flowchart in the background.

### 🎬 Demo Video
[![Ren'Py Save Graph Demo](https://img.youtube.com/vi/i0_DoTWxbf8/maxresdefault.jpg)](https://www.youtube.com/watch?v=i0_DoTWxbf8)

### 1. The Single Dedicated Slot Workflow
- The app runs in parallel with the Ren'Py game.
- Create and select a _Gamespace_ targeting one game installation's saves folder, which is `game/saves/` from the game's root (.exe-containing) folder.
- Select one designated save slot in-game (e.g. Page 1, Slot 1: `1-1-LT1`), or more if you feel like managing multiple story trees. You can start a save graph at any point in the game.
- Every time you save to this dedicated slot in Ren'Py, the app automatically detects the save point, extracts your choice state & screenshot, and records it as a node on your story flowchart.
- This means the standard Quicksave/Quickload is not really of any use as far as this app is concerned. The way that a quick save appends saves to the Q.Save page (looping back to the first slot when full) doesn't accommodate this unique single-slot system. I invite users of the app to think about how the app could support quicksave in an intuitive and reliable manner.

### 2. Branching & Story Exploration
- For 100% completionists wanting to track every choice, start your game session with the app running to build a clean lineage of all decision points. Find a frequency of saving that works for you and the game you're playing - you don't have to save at every decision point.
- To test a different decision or story path, select any previous save point on your flowchart and click **`Restore to Game`**.
- The app swaps that save point into your single managed slot. Return to the game, load that slot, and make your new choice.
- Saving in-game after restoring an older point automatically creates a new branch on your flowchart, preserving your original route.

### 3. What This App Does (and Does NOT Do)
- ✅ **What It Does**: Watches your game's saves folder, tracks an annotated lineage of your choice history, and lets you seamlessly swap save points in and out.
- ❌ **What It Does NOT Do**:
  - Does **not** modify or edit save file contents or game stats
  - Does **not** patch or modify game files or runtime code - I aim to respect intentions of game authors and honor game licenses
  - Does not "insist upon itself" by becoming a necessary adjunct to playing a game, but can be used when desired

---

## ⚠️ Usage Notes

- I recommend against sharing save-graph libraries created by this app (or any `.save` file) with others. [Ren'Py's security documentation](https://www.renpy.org/doc/html/security.html) warns that loading a file in the format used for Ren'Py saves can execute arbitrary code.

---

## ✨ Feature Notes

- **Lineage Validity Checks**: Give a Gamespace an optional expression (like the Graph Filter Expression, e.g. `delta('karma') >= 0`) qualifying a save as valid and/or what a valid difference is between a save and its preceding save. Any node where it evaluates false gets flagged an "Invalid lineage detected" label. This helps to catch accidental saves of "past state" over "future state" (from backtracking in-game or from other save slots). What makes a good check will vary by game title.

---

## 🧪 Developer Setup

### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/lucjross/renpy-save-graph.git
cd renpy-save-graph

# Install dependencies via uv or pip
uv sync --extra dev
```

### 2. Running Test Suite
```bash
# Run pytest integration suite
uv run pytest -v

# Run test coverage report
uv run pytest --cov=renpy_save_graph --cov-report=term-missing
```

### 3. Git Hooks
Tracked hook scripts live in `scripts/` (`pre-commit` runs the test suite; `commit-msg` enforces a [Conventional Commits](https://www.conventionalcommits.org/) prefix — `feat`, `fix`, `perf`, `docs`, `refactor`, `test`, or `chore` — since `CHANGELOG.md` is generated from it). They aren't installed automatically on clone:
```bash
ln -sf ../../scripts/pre-commit .git/hooks/pre-commit
ln -sf ../../scripts/commit-msg .git/hooks/commit-msg
```

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](file:///home/luc/github/lucjross/renpy-save-graph/LICENSE) for details.
