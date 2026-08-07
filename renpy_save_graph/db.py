"""Database Store: SQLite metadata & thumbnail index alongside Git.

Provides fast <2ms cold queries for graph structure, variable states,
and thumbnail PNG bytes. Derived from Git and self-healing.
"""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, TYPE_CHECKING
from .thumbnail import stamp_png

if TYPE_CHECKING:
    from .library import Library


class DatabaseStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    sha TEXT PRIMARY KEY,
                    parents TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    when_ts INTEGER NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    thumbnail BLOB
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS variables (
                    sha TEXT NOT NULL,
                    var_name TEXT NOT NULL,
                    var_value TEXT NOT NULL,
                    PRIMARY KEY (sha, var_name)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vars_sha ON variables(sha);")

    def sync_with_git(self, lib: "Library", slot_branch: str, all_slot_branches: list[str]) -> None:
        """Self-healing sync: compares SQLite against Git DAG, populates missing nodes, and purges deleted/stale nodes."""
        nodes = lib.dag_for_slot(slot_branch, all_slot_branches)

        with self._get_conn() as conn:
            existing_shas = {
                row["sha"] for row in conn.execute("SELECT sha FROM nodes").fetchall()
            }

        git_shas = {n.sha for n in nodes} if nodes else set()
        stale_shas = existing_shas - git_shas
        if stale_shas:
            with self._get_conn() as conn:
                placeholders = ",".join("?" for _ in stale_shas)
                conn.execute(f"DELETE FROM nodes WHERE sha IN ({placeholders})", tuple(stale_shas))
                conn.execute(f"DELETE FROM variables WHERE sha IN ({placeholders})", tuple(stale_shas))

        if not nodes:
            return

        missing_nodes = [n for n in nodes if n.sha not in existing_shas]
        if not missing_nodes:
            return

        # Extract Git blobs OUTSIDE the SQLite transaction to avoid holding write locks
        payloads = []
        for n in missing_nodes:
            try:
                blob = lib.blob_bytes(n.sha, "save.save")
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    raw_png = zf.read("screenshot.png")
                    png_bytes = stamp_png(raw_png, f"@{n.short}")
            except Exception:
                png_bytes = None

            try:
                raw_state = lib._git("show", f"{n.sha}:state.json", capture=True)
                vars_dict = json.loads(raw_state).get("variables", {})
            except Exception:
                vars_dict = {}

            payloads.append((n, png_bytes, vars_dict))

        # Fast batch insert inside a short <2ms transaction
        with self._get_conn() as conn:
            node_rows = [
                (n.sha, json.dumps(n.parents), n.subject, n.when, n.note, png_bytes)
                for n, png_bytes, _ in payloads
            ]
            conn.executemany(
                "INSERT OR REPLACE INTO nodes (sha, parents, subject, when_ts, note, thumbnail) VALUES (?, ?, ?, ?, ?, ?)",
                node_rows,
            )

            var_rows = [
                (n.sha, k, json.dumps(v))
                for n, _, vars_dict in payloads
                for k, v in vars_dict.items()
            ]
            if var_rows:
                conn.executemany(
                    "INSERT OR REPLACE INTO variables (sha, var_name, var_value) VALUES (?, ?, ?)",
                    var_rows,
                )

    def get_nodes(self, shas: list[str]) -> dict[str, dict[str, Any]]:
        if not shas:
            return {}
        placeholders = ",".join("?" for _ in shas)
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT sha, parents, subject, when_ts, note FROM nodes WHERE sha IN ({placeholders})",
                shas,
            ).fetchall()
            result = {}
            for r in rows:
                result[r["sha"]] = {
                    "sha": r["sha"],
                    "parents": json.loads(r["parents"]),
                    "subject": r["subject"],
                    "when": r["when_ts"],
                    "note": r["note"],
                }
            return result

    def get_all_states(
        self, shas: list[str], var_names: list[str] | set[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        if not shas:
            return {}
        sha_placeholders = ",".join("?" for _ in shas)
        if var_names:
            v_list = list(var_names)
            var_placeholders = ",".join("?" for _ in v_list)
            query = f"SELECT sha, var_name, var_value FROM variables WHERE sha IN ({sha_placeholders}) AND var_name IN ({var_placeholders})"
            params = (*shas, *v_list)
        else:
            query = f"SELECT sha, var_name, var_value FROM variables WHERE sha IN ({sha_placeholders})"
            params = tuple(shas)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            result: dict[str, dict[str, Any]] = {s: {} for s in shas}
            for r in rows:
                sha = r["sha"]
                if sha in result:
                    try:
                        result[sha][r["var_name"]] = json.loads(r["var_value"])
                    except Exception:
                        result[sha][r["var_name"]] = r["var_value"]
            return result

    def get_thumbnail(self, sha: str) -> bytes | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT thumbnail FROM nodes WHERE sha = ?", (sha,)).fetchone()
            if row and row["thumbnail"]:
                return bytes(row["thumbnail"])
            return None

    def update_note(self, sha: str, note: str) -> None:
        with self._get_conn() as conn:
            conn.execute("UPDATE nodes SET note = ? WHERE sha = ?", (note, sha))

    def delete_node(self, sha: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM nodes WHERE sha = ?", (sha,))
            conn.execute("DELETE FROM variables WHERE sha = ?", (sha,))
