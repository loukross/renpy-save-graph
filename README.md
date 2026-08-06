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

## ✨ Features

- **Interactive Route Flowchart**: View your entire game playthrough history as a branching flowchart, showing choices, save points, active heads, and save thumbnails.
- **Variable Diffing & Inspection**: Compare any two save points to see exactly which stats, flags, or choices changed, or inspect all variables at a single save point.
- **Save Point Search & Expression Filtering**: Filter the flowchart by custom conditions (e.g. `money > 0`, `karma == 5`) or search specific variables using regex.
- **One-Click Route Restores**: Instantly restore any previous save point back into your game slot to jump to different choice paths.
- **Safe Branching & Deletion**: Reparent or clean up unwanted save points without breaking your playthrough routes.

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

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](file:///home/luc/github/lucjross/renpy-save-graph/LICENSE) for details.
