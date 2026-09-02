#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  Ren'Py Save Graph — Interactive Flowchart App"
echo "==================================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH!"
    echo "Please install Python 3.10+ from https://www.python.org/ or via your package manager."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js / npm is not installed or not in PATH!"
    echo "Please install Node.js 18+ from https://nodejs.org/ or via your package manager."
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "[ERROR] Git is not installed or not in PATH!"
    echo "Please install Git from https://git-scm.com/downloads or via your package manager."
    exit 1
fi

echo "Installing / Updating renpy-save-graph..."
python3 -m pip install --quiet --upgrade .

echo "Installing / building the web UI..."
npm install --silent
npm run build --silent

echo ""
echo "Starting web server on http://localhost:5555/"
echo "Press Ctrl+C in this window to stop."
echo ""
python3 -m renpy_save_graph.server
