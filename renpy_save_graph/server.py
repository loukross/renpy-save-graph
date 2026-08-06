"""Local web server for the save-graph flowchart UI."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import uuid
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from dataclasses import asdict
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .config import AppConfig, GameSpace, default_config_path, default_library_path
from .db import DatabaseStore
from .library import Library, STATE
from .thumbnail import stamp_png
from .watcher import Director, SpaceConfig

_HTML_PATH = Path(__file__).parent / "static" / "index.html"
_ASSETS_DIR = Path(__file__).parent / "static" / "assets"
_SPACE_PATCHABLE = {"label", "saves_dir", "additional_saves_dirs", "node_hint_format", "slot_exclude", "lineage_validity_expr", "milestone_vars", "route_targets", "favorite_vars", "filter_history", "sort_history"}


class _SortVal:
    def __init__(self, val: Any, desc: bool) -> None:
        self.val = val
        self.desc = desc

    def __lt__(self, other: "_SortVal") -> bool:
        if self.val is None and other.val is None:
            return False
        if self.val is None:
            return False if self.desc else True
        if other.val is None:
            return True if self.desc else False
        try:
            v1, v2 = float(self.val), float(other.val)
            return (v1 > v2) if self.desc else (v1 < v2)
        except (TypeError, ValueError):
            pass
        return (str(self.val) > str(other.val)) if self.desc else (str(self.val) < str(other.val))


def create_app(config_path: Path) -> FastAPI:
    app = FastAPI()
    app.state.shutdown_event = asyncio.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.shutdown_event.set()

    app.router.lifespan_context = lifespan
    html = _HTML_PATH.read_text(encoding="utf-8")

    def load() -> AppConfig:
        from .examples.init_example import ensure_example_space
        ensure_example_space(config_path)
        return AppConfig.load(config_path)

    def save(cfg: AppConfig) -> None:
        cfg.save(config_path)

    def get_space_or_404(space_id: str) -> GameSpace:
        space = load().space_by_id(space_id)
        if space is None:
            raise HTTPException(404, f"space {space_id!r} not found")
        return space

    def make_library(space: GameSpace) -> Library:
        return Library.init(space.library_path)

    def make_director(space: GameSpace) -> Director:
        return Director(SpaceConfig(
            saves_dir=Path(space.saves_dir),
            library_path=Path(space.library_path),
            slot_exclude=space.slot_exclude,
            additional_saves_dirs=[Path(d) for d in space.additional_saves_dirs if d],
        ))

    def make_db(space: GameSpace) -> DatabaseStore:
        lib_path = Path(space.library_path)
        return DatabaseStore(lib_path / "graph.sqlite")

    @app.get("/", response_class=HTMLResponse)
    def index() -> Response:
        return HTMLResponse(content=html)

    app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    # -- config --------------------------------------------------------------

    @app.get("/api/config")
    def api_config() -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(load())

    @app.get("/api/defaults")
    def api_defaults() -> dict[str, str]:
        from .config import default_data_dir
        return {"data_dir": str(default_data_dir())}

    # -- filesystem browser --------------------------------------------------

    @app.get("/api/browse")
    def api_browse(path: str = "/") -> dict[str, Any]:
        try:
            p = Path(path).expanduser().resolve() if path else Path("/")
        except Exception:
            p = Path("/")
        if not p.exists() or not p.is_dir():
            p = Path("/")
        try:
            entries = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            entries = []
        return {
            "path": str(p),
            "parent": str(p.parent) if p.parent != p else None,
            "dirs": [e.name for e in entries if e.is_dir() and not e.name.startswith(".")],
        }

    # -- space CRUD ----------------------------------------------------------

    @app.post("/api/spaces")
    def api_add_space(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
        from dataclasses import asdict
        cfg = load()
        space_id = uuid.uuid4().hex[:8]
        space = GameSpace(
            id=space_id,
            label=body.get("label", ""),
            saves_dir=body["saves_dir"],
            additional_saves_dirs=body.get("additional_saves_dirs", []),
            library_path=body.get("library_path") or str(default_library_path(space_id)),
            node_hint_format=body.get("node_hint_format", ""),
            slot_exclude=body.get("slot_exclude", ""),
            lineage_validity_expr=body.get("lineage_validity_expr", ""),
            milestone_vars=body.get("milestone_vars", []),
            route_targets=body.get("route_targets", []),
        )
        cfg.spaces.append(space)
        save(cfg)
        return asdict(space)

    @app.delete("/api/spaces/{space_id}")
    def api_delete_space(space_id: str, delete_library: bool = False) -> dict[str, bool]:
        cfg = load()
        if delete_library:
            space = cfg.space_by_id(space_id)
            if space:
                lib_path = Path(space.library_path)
                if lib_path.exists():
                    shutil.rmtree(lib_path)
        cfg.spaces = [s for s in cfg.spaces if s.id != space_id]
        save(cfg)
        return {"ok": True}

    @app.patch("/api/spaces/{space_id}/config")
    def api_patch_space(
        space_id: str, patch: dict[str, Any] = Body(...)
    ) -> dict[str, bool]:
        get_space_or_404(space_id)
        cfg = load()
        for s in cfg.spaces:
            if s.id == space_id:
                for k, v in patch.items():
                    if k in _SPACE_PATCHABLE:
                        setattr(s, k, v)
                break
        save(cfg)
        return {"ok": True}

    # -- slot list -----------------------------------------------------------

    @app.get("/api/spaces/{space_id}/slots")
    def api_slots(space_id: str) -> dict[str, list[str]]:
        space = get_space_or_404(space_id)
        director = make_director(space)
        return {"slots": director.slot_names()}

    # -- graph ---------------------------------------------------------------

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/graph")
    def api_graph(
        space_id: str,
        slot_name: str,
        base_sort: str = "chrono",
        base_dir: str = "asc",
        order_by: str = "",
    ) -> dict[str, Any]:
        space = get_space_or_404(space_id)
        director = make_director(space)
        lib = director.library
        # Switch to the active branch (fork branch after restore+fork, else slot branch).
        active = director._active_branch(slot_name)
        lib.ensure_branch(active)
        nodes = lib.dag_for_slot(slot_name, director.slot_names())
        try:
            head_sha: str | None = lib.head().sha
        except Exception:
            head_sha = None
        tips = lib.branch_tips()
        fmt = space.node_hint_format
        needed_vars: set[str] | None = set()
        if fmt:
            import string
            for _, field_name, _, _ in string.Formatter().parse(fmt):
                if field_name:
                    needed_vars.add(field_name)

        if order_by.strip():
            import re
            for v in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", order_by):
                if v.upper() not in ("ASC", "DESC"):
                    needed_vars.add(v)

        if base_sort == "jaccard":
            needed_vars = None

        db = make_db(space)
        db.sync_with_git(lib, slot_name, director.slot_names())
        all_states = db.get_all_states([n.sha for n in nodes], var_names=needed_vars)

        def hint(sha: str) -> str:
            if not fmt:
                return ""
            try:
                variables = all_states.get(sha, {})
                return fmt.format_map(defaultdict(str, variables))
            except Exception:
                return ""

        # Identify leaf nodes (commits with no child nodes in the DAG)
        all_parents = {p for n in nodes for p in n.parents}
        leaf_nodes = [n for n in nodes if n.sha not in all_parents]

        # Step 1: Compute base sort order
        leaf_vars: dict[str, dict[str, Any]] = {}
        if base_sort == "jaccard" and len(leaf_nodes) > 1:
            for n in leaf_nodes:
                leaf_vars[n.sha] = all_states.get(n.sha, {})

            def _sim(s1: str, s2: str) -> float:
                v1, v2 = leaf_vars.get(s1, {}), leaf_vars.get(s2, {})
                k1 = {k for k in v1.keys() if not k.startswith("_")}
                k2 = {k for k in v2.keys() if not k.startswith("_")}
                all_k = k1 | k2
                if not all_k:
                    return 1.0
                matches = sum(1 for k in all_k if k in v1 and k in v2 and v1[k] == v2[k])
                return matches / len(all_k)

            leaf_shas = [n.sha for n in leaf_nodes]
            unvisited = set(leaf_shas[1:])
            base_order = [leaf_shas[0]]
            while unvisited:
                last = base_order[-1]
                best = max(unvisited, key=lambda cand: _sim(last, cand))
                base_order.append(best)
                unvisited.remove(best)
            if base_dir.lower() == "desc":
                base_order = list(reversed(base_order))
        else:  # "chrono" (default)
            is_desc = (base_dir.lower() == "desc")
            base_order = [n.sha for n in sorted(leaf_nodes, key=lambda x: x.when, reverse=is_desc)]

        base_rank = {sha: idx for idx, sha in enumerate(base_order)}

        # Step 2: Apply SQL ORDER BY clause if provided, using base_rank as fallback/tie-breaker
        if order_by.strip() and len(leaf_nodes) > 1:
            terms: list[tuple[str, bool]] = []
            for part in order_by.split(","):
                part = part.strip()
                if not part:
                    continue
                tokens = part.split()
                if len(tokens) >= 2 and tokens[-1].upper() in ("ASC", "DESC"):
                    is_desc = (tokens[-1].upper() == "DESC")
                    var_name = " ".join(tokens[:-1])
                else:
                    is_desc = False
                    var_name = part
                terms.append((var_name, is_desc))

            # Ensure leaf_vars are populated for ORDER BY evaluation
            for n in leaf_nodes:
                if n.sha not in leaf_vars:
                    try:
                        raw = lib._git("show", f"{n.sha}:{STATE}", capture=True)
                        leaf_vars[n.sha] = json.loads(raw).get("variables", {})
                    except Exception:
                        leaf_vars[n.sha] = {}

            def _sort_key(node):
                v = leaf_vars.get(node.sha, {})
                order_vals = tuple(_SortVal(v.get(var_name), is_desc) for var_name, is_desc in terms)
                return order_vals + (base_rank.get(node.sha, 0),)

            leaf_order = [n.sha for n in sorted(leaf_nodes, key=_sort_key)]
        else:
            leaf_order = base_order

        return {
            "nodes": [
                {
                    "sha": n.sha,
                    "short": n.short,
                    "parents": n.parents,
                    "subject": n.subject,
                    "when": n.when,
                    "branch": ", ".join(tips.get(n.sha, [])),
                    "branches": tips.get(n.sha, []),
                    "is_head": n.sha == head_sha,
                    "is_suspect": n.subject.startswith("[SUSPECT]"),
                    "hint": hint(n.sha),
                    "note": n.note,
                }
                for n in nodes
            ],
            "head": head_sha,
            "leaf_order": leaf_order,
            "base_sort": base_sort,
            "order_by": order_by,
        }

    @app.put("/api/spaces/{space_id}/slots/{slot_name}/note/{sha}")
    def api_set_note(space_id: str, slot_name: str, sha: str, body: dict[str, Any] = Body(...)) -> dict[str, bool]:
        lib = make_library(get_space_or_404(space_id))
        lib.set_note(sha, body.get("text", ""))
        return {"ok": True}

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/diff/{sha1}/{sha2}")
    def api_diff(space_id: str, slot_name: str, sha1: str, sha2: str) -> dict[str, Any]:
        space = get_space_or_404(space_id)
        db = make_db(space)
        states = db.get_all_states([sha1, sha2])
        v1, v2 = states.get(sha1, {}), states.get(sha2, {})
        all_keys = sorted(set(v1) | set(v2))
        # `removed` distinguishes a variable the game dropped from one merely
        # set to None — both read back as None through .get().
        changes = [
            {"var": k, "old": v1.get(k), "new": v2.get(k), "removed": k not in v2}
            for k in all_keys if v1.get(k) != v2.get(k)
        ]
        return {"changes": changes}

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/state/{sha}")
    def api_state(space_id: str, slot_name: str, sha: str) -> dict[str, Any]:
        space = get_space_or_404(space_id)
        db = make_db(space)
        states = db.get_all_states([sha])
        return {"variables": states.get(sha, {})}

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/states")
    def api_all_states(space_id: str, slot_name: str, vars: str = "") -> dict[str, Any]:
        space = get_space_or_404(space_id)
        director = make_director(space)
        db = make_db(space)
        db.sync_with_git(director.library, slot_name, director.slot_names())
        nodes = director.library.dag_for_slot(slot_name, director.slot_names())
        var_set = {v.strip() for v in vars.split(",") if v.strip()} if vars else None
        return db.get_all_states([n.sha for n in nodes], var_names=var_set)

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/screenshot/{sha}")
    def api_screenshot(space_id: str, slot_name: str, sha: str):
        space = get_space_or_404(space_id)
        db = make_db(space)
        png_bytes = db.get_thumbnail(sha)
        if not png_bytes:
            lib = make_library(space)
            try:
                blob = lib.blob_bytes(sha)
                with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                    png_bytes = zf.read("screenshot.png")
            except Exception:
                png_bytes = b""
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "max-age=3600"},
        )

    # -- director actions ----------------------------------------------------

    @app.post("/api/spaces/{space_id}/ingest")
    def api_ingest_space(space_id: str, note: str = "") -> dict[str, Any]:
        director = make_director(get_space_or_404(space_id))
        results = director.ingest_all(note=note or None)
        return {
            "count": len(results),
            "results": [
                {
                    "slot": r.slot_name,
                    "sha": r.commit.sha,
                    "short": r.commit.short,
                    "subject": r.commit.subject,
                }
                for r in results
            ],
        }

    @app.post("/api/spaces/{space_id}/slots/{slot_name}/ingest")
    def api_ingest(space_id: str, slot_name: str, note: str = "") -> dict[str, Any]:
        director = make_director(get_space_or_404(space_id))
        result = director.ingest(slot_name, note=note or None)
        if result is None:
            return {"committed": False}
        return {
            "committed": True,
            "slot": result.slot_name,
            "sha": result.commit.sha,
            "short": result.commit.short,
            "subject": result.commit.subject,
        }

    @app.post("/api/spaces/{space_id}/slots/{slot_name}/restore")
    def api_restore(
        space_id: str, slot_name: str, body: dict[str, Any] = Body(...)
    ) -> dict[str, Any]:
        from .library import GitError
        director = make_director(get_space_or_404(space_id))
        sha = body["sha"]
        new_branch = body.get("branch_name", "").strip() or None
        try:
            info = director.switch_to(slot_name, sha, new_branch=new_branch)
        except GitError as e:
            raise HTTPException(400, str(e))
        return {"sha": info.sha, "short": info.short, "branch": info.branch}

    @app.delete("/api/spaces/{space_id}/slots/{slot_name}/nodes/{sha}")
    def api_delete_node(
        space_id: str, slot_name: str, sha: str, strategy: str = "reparent"
    ) -> dict[str, bool]:
        from .library import GitError
        space = get_space_or_404(space_id)
        director = make_director(space)
        try:
            removed_shas = director.delete_node(slot_name, sha, strategy=strategy)
        except GitError as e:
            raise HTTPException(400, str(e))
        db = make_db(space)
        for old_sha in removed_shas:
            db.delete_node(old_sha)
        return {"ok": True}

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/screenshots")
    def api_batch_screenshots(space_id: str, slot_name: str) -> dict[str, str]:
        space = get_space_or_404(space_id)
        director = make_director(space)
        db = make_db(space)
        db.sync_with_git(director.library, slot_name, director.slot_names())
        nodes = director.library.dag_for_slot(slot_name, director.slot_names())
        shas = [n.sha for n in nodes]
        if not shas:
            return {}
        with db._get_conn() as conn:
            placeholders = ",".join("?" * len(shas))
            rows = conn.execute(
                f"SELECT sha, thumbnail FROM nodes WHERE sha IN ({placeholders}) AND thumbnail IS NOT NULL",
                shas,
            ).fetchall()
        return {
            row["sha"]: f"data:image/png;base64,{base64.b64encode(row['thumbnail']).decode('ascii')}"
            for row in rows
        }

    @app.get("/api/spaces/{space_id}/slots/{slot_name}/tags")
    def api_get_tags(space_id: str, slot_name: str) -> dict[str, Any]:
        space = get_space_or_404(space_id)
        director = make_director(space)
        db = make_db(space)
        nodes = director.library.dag_for_slot(slot_name, director.slot_names())
        shas = [n.sha for n in nodes]
        return {
            "tags": db.get_tags(shas),
            "all_tags": db.get_all_tags(),
        }

    @app.post("/api/spaces/{space_id}/slots/{slot_name}/nodes/{sha}/tags")
    def api_add_node_tag(space_id: str, slot_name: str, sha: str, body: dict[str, Any] = Body(...)) -> dict[str, bool]:
        space = get_space_or_404(space_id)
        db = make_db(space)
        tag = body.get("tag", "").strip()
        if tag:
            db.add_tag(sha, tag)
        return {"ok": True}

    @app.delete("/api/spaces/{space_id}/slots/{slot_name}/nodes/{sha}/tags/{tag}")
    def api_delete_node_tag(space_id: str, slot_name: str, sha: str, tag: str) -> dict[str, bool]:
        space = get_space_or_404(space_id)
        db = make_db(space)
        db.remove_tag(sha, tag)
        return {"ok": True}

    @app.post("/api/examples/reset")
    def api_reset_example_space() -> dict[str, bool]:
        import shutil
        from .examples.init_example import EXAMPLE_SPACE_ID, ensure_example_space
        from .config import AppConfig, default_config_path, default_data_dir

        config_path = default_config_path()
        cfg = AppConfig.load(config_path)
        data_dir = default_data_dir()
        demo_dir = data_dir / "demo_space"
        if demo_dir.exists():
            shutil.rmtree(demo_dir, ignore_errors=True)
        cfg.spaces = [s for s in cfg.spaces if s.id != EXAMPLE_SPACE_ID]
        cfg.save(config_path)
        ensure_example_space(config_path)
        return {"ok": True}

    # -- file watcher (SSE) --------------------------------------------------

    @app.get("/api/spaces/{space_id}/watch")
    async def api_watch(request: Request, space_id: str):
        loop = asyncio.get_running_loop()
        shutdown_event: asyncio.Event = request.app.state.shutdown_event

        async def event_stream():
            try:
                while not shutdown_event.is_set():
                    if await request.is_disconnected():
                        break
                    try:
                        space = get_space_or_404(space_id)
                        director = make_director(space)
                        results = await loop.run_in_executor(None, director.ingest_all)
                        for result in results:
                            yield {
                                "data": json.dumps({
                                    "committed": True,
                                    "slot": result.slot_name,
                                    "sha": result.commit.sha,
                                    "short": result.commit.short,
                                    "subject": result.commit.subject,
                                })
                            }
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        import traceback
                        print(f"[watch:{space_id}] unhandled error:", file=sys.stderr)
                        traceback.print_exc()
                        yield {"data": json.dumps({"error": str(exc)})}

                    if shutdown_event.is_set():
                        break

                    try:
                        await asyncio.wait_for(shutdown_event.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
            except asyncio.CancelledError:
                pass

        return EventSourceResponse(event_stream())

    return app


class _Server(uvicorn.Server):
    def handle_exit(self, sig: int, frame: Any) -> None:
        app = getattr(self.config, "loaded_app", None) or self.config.app
        if hasattr(app, "state") and hasattr(app.state, "shutdown_event"):
            app.state.shutdown_event.set()
        super().handle_exit(sig, frame)


def serve(
    config_path: Path | None = None,
    host: str = "0.0.0.0",
    port: int = 5555,
) -> None:
    if config_path is None:
        config_path = default_config_path()
    app = create_app(config_path)
    print(f"open http://localhost:{port}/ in your browser")
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=1)
    _Server(config).run()


def _main(argv: list[str]) -> int:
    config_path = Path(argv[0]) if argv else None
    port = int(argv[1]) if len(argv) > 1 else 5555
    try:
        serve(config_path, port=port)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
