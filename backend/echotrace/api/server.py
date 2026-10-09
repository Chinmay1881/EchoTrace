"""EchoTrace server: FastAPI on port 8000.

  WS   /ws           every pipeline message ({type, data}, see schemas.py); a snapshot is sent on connect
  GET  /api/status   current status data (+ mode/error/tagger extras)
  GET  /api/mode     current source mode;  POST /api/mode {source, device?, file?} switches at runtime
  GET  /api/events   array of recent event data objects
  POST /api/reset    clear events, sequences and risk (the source keeps running)
  GET  /api/metrics  docs/metrics.json (evaluation results) or {}
  /                  the built dashboard (frontend/dist), or a placeholder page if it isn't built

The pipeline runs on a worker thread; messages cross into asyncio via loop.call_soon_threadsafe.
latency_ms is measured from the capture of the audio block that triggered an event to its WS send.
Errors are returned as {"error": "..."} (same shape as the frontend's mock server).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from echotrace import config
from echotrace.audio.sources import LiveMicSource, SimSource, WavReplaySource
from echotrace.pipeline import Pipeline

SOURCES = ("LIVE", "RECORDED", "SIMULATED")
FRONTEND_DIST = config.REPO_DIR / "frontend" / "dist"
SNAPSHOT_EVENTS = 50
EVENTS_KEPT = 200


class ModeError(Exception):
    def __init__(self, message: str, code: int = 400):
        super().__init__(message)
        self.code = code


def default_demo_clip() -> Path | None:
    clips = sorted(config.RECORDINGS_DIR.glob("demo*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
    return clips[0] if clips else None


def resolve_wav(file: str | None) -> Path:
    if not file:
        clip = default_demo_clip()
        if clip is None:
            raise ModeError("RECORDED needs a file: none given and no recordings/demo*.wav found")
        return clip
    p = Path(file)
    for cand in (p, config.REPO_DIR / p, config.RECORDINGS_DIR / p):
        if cand.is_file():
            if cand.suffix.lower() != ".wav":
                raise ModeError(f"{cand.name} is not a .wav file")
            return cand.resolve()
    raise ModeError(f"file not found: {file}")


class Engine:
    """Owns the tagger, the running pipeline, the WS clients and the thread -> asyncio bridge."""

    def __init__(self, tagger_factory=None, force_cpu: bool = False, realtime: bool = True):
        self.tagger_factory = tagger_factory
        self.force_cpu = force_cpu
        self.realtime = realtime                       # False: replay/sim as fast as possible (tests)
        self.tagger = None
        self.tagger_state = "not loaded"
        self._tagger_lock = threading.Lock()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.queue: asyncio.Queue | None = None
        self.clients: set[WebSocket] = set()
        self.pipeline: Pipeline | None = None
        self.generation = 0
        self.mode = {"source": "SIMULATED", "device": None, "file": None, "scenario": None}
        self.error: str | None = None
        self._switch_lock = threading.RLock()          # re-entrant: a failed switch restores the previous mode
        self.started_wall = datetime.now()

    # ----------------------------------------------------------------- tagger
    def load_tagger(self):
        """Load CNN14 once (thread-safe, blocking). Used for LIVE and RECORDED."""
        with self._tagger_lock:
            if self.tagger is not None:
                return self.tagger
            self.tagger_state = "loading"
            try:
                if self.tagger_factory is not None:
                    self.tagger = self.tagger_factory()
                else:
                    from echotrace.tagging.panns_tagger import PannsTagger
                    self.tagger = PannsTagger(force_cpu=self.force_cpu)
                    self.tagger.warmup()
                self.tagger_state = f"ready ({self.tagger.device})"
            except Exception as e:
                self.tagger_state = f"error: {e}"
                raise
            return self.tagger

    def preload_tagger(self) -> None:
        threading.Thread(target=self._preload, name="tagger-preload", daemon=True).start()

    def _preload(self) -> None:
        try:
            self.load_tagger()
        except Exception:
            pass                                       # reported in /api/status; LIVE/RECORDED will fail clearly

    # ----------------------------------------------------------------- mode switching (blocking; call in a thread)
    def switch(self, source: str, device: str | None = None, file: str | None = None,
               scenario: str | None = None) -> dict:
        source = (source or "").upper()
        if source not in SOURCES:
            raise ModeError(f"Invalid source {source!r}; use one of {list(SOURCES)}")
        with self._switch_lock:
            tagger = None
            if source in ("LIVE", "RECORDED"):
                try:
                    tagger = self.load_tagger()
                except Exception as e:
                    raise ModeError(f"CNN14 could not be loaded: {e}", 503)
            wav = resolve_wav(file) if source == "RECORDED" else None
            old = self.pipeline
            if old is not None:                        # release the mic before (re)opening it
                old.stop()
                self.pipeline = None
            try:
                if source == "LIVE":
                    src = LiveMicSource(device).start()           # open now so failures are reported here
                elif source == "RECORDED":
                    src = WavReplaySource(wav, realtime=self.realtime).start()
                else:
                    src = SimSource(realtime=self.realtime, scenario=scenario or "all").start()
            except Exception as e:
                msg = f"{source} failed: {str(e).splitlines()[0]}"
                prev = dict(self.mode)
                if old is not None and prev["source"] != source:   # don't leave the dashboard with nothing
                    try:
                        self.switch(prev["source"], prev["device"] if prev["source"] == "LIVE" else None,
                                    prev["file"], prev["scenario"])
                        msg += f" - stayed on {prev['source']}"
                    except Exception:
                        pass
                self.error = msg
                raise ModeError(msg, 409)
            self.generation += 1
            gen = self.generation
            pipe = Pipeline(src, tagger=tagger, emit=self._emitter(gen), id_prefix=f"m{gen}-",
                            start_wall=datetime.now())
            self.pipeline = pipe
            self.mode = {"source": source, "device": src.info.device,
                         "file": str(wav) if wav else None,
                         "scenario": (scenario or "all") if source == "SIMULATED" else None}
            self.error = None
            pipe.start()
            return self.mode_payload()

    def _emitter(self, gen: int):
        def emit(msg: dict, capture: float | None) -> None:
            loop, q = self.loop, self.queue
            if loop is None or q is None or loop.is_closed():
                return
            loop.call_soon_threadsafe(q.put_nowait, (gen, msg, capture))
        return emit

    def stop(self) -> None:
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None

    # ----------------------------------------------------------------- broadcasting
    async def broadcaster(self) -> None:
        assert self.queue is not None
        while True:
            gen, msg, capture = await self.queue.get()
            if gen != self.generation:
                continue                               # stale message from a source we switched away from
            text = json.dumps(msg)
            # latency = capture -> WS send; recorded as the send starts, so a client that has the event
            # never sees a status/REST answer that predates it
            if capture is not None and msg["type"] == "event" and self.pipeline is not None:
                self.pipeline.analyzer.record_latency((time.perf_counter() - capture) * 1000)
            if self.clients:
                await asyncio.gather(*(self._send(ws, text) for ws in list(self.clients)))

    async def _send(self, ws: WebSocket, text: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(text), timeout=2.0)
        except Exception:
            self.clients.discard(ws)                   # slow or gone: drop it, the client reconnects

    def snapshot(self) -> list[dict]:
        """What a newly connected dashboard needs: status, recent events, current sequences."""
        out = [{"type": "status", "data": self.status_data(extras=False)}]
        if self.pipeline is not None:
            an = self.pipeline.analyzer
            for ev in list(an.events)[-SNAPSHOT_EVENTS:]:
                out.append({"type": "event", "data": self.event_data(ev)})
            out += list(an.sequences.values())
        return out

    # ----------------------------------------------------------------- state for REST
    def meta(self) -> dict:
        t = self.pipeline.analyzer.t if self.pipeline is not None else 0.0
        return {"source": self.mode["source"], "t": round(t, 3), "wall": datetime.now().isoformat(timespec="milliseconds")}

    def status_data(self, extras: bool = True) -> dict:
        if self.pipeline is not None:
            data = self.pipeline.analyzer.status(dropped_blocks=self.pipeline.dropped_blocks)["data"]
        else:
            data = {**self.meta(), "risk": "GREEN", "latency_ms": 0.0, "device": "starting...",
                    "host_api": "none", "sample_rate": config.CAPTURE_RATE, "channels": 2,
                    "localization": "OFF", "model_device": "cpu", "dropped_blocks": 0}
        if extras:
            pipe_err = self.pipeline.error if self.pipeline is not None else None
            data = {**data, "mode": self.mode, "error": self.error or pipe_err, "tagger": self.tagger_state,
                    "running": bool(self.pipeline and self.pipeline.running), "clients": len(self.clients),
                    "calibration": self.pipeline.analyzer.localizer.cal.source if self.pipeline else None}
        return data

    def mode_payload(self) -> dict:
        return {**self.meta(), "source": self.mode["source"], "device": self.mode["device"],
                "file": self.mode["file"], "scenario": self.mode["scenario"]}

    def event_data(self, ev) -> dict:
        an = self.pipeline.analyzer
        return {"source": an.source, "t": round(ev.t_end, 3), "wall": an.wall(ev.t_end), "id": ev.id,
                "t_start": ev.t_start, "t_end": ev.t_end, "category": ev.category, "label": ev.label,
                "confidence": ev.confidence, "zone": ev.zone, "angle_deg": ev.angle_deg}

    def events(self) -> list[dict]:
        if self.pipeline is None:
            return []
        return [self.event_data(e) for e in list(self.pipeline.analyzer.events)[-EVENTS_KEPT:]]

    def metrics(self) -> dict:
        path = config.DOCS_DIR / "metrics.json"
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                return {"error": f"docs/metrics.json unreadable: {e}"}
        return {}


PLACEHOLDER = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>EchoTrace backend</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px}
code{background:#161b22;padding:2px 6px;border-radius:4px}a{color:#58a6ff}</style></head><body>
<h1>EchoTrace backend is running</h1>
<p>The dashboard is not built yet (no <code>frontend/dist</code>). Build it in <code>frontend/</code>
(<code>npm run build</code>), then reload this page - no server restart needed.</p>
<p>Meanwhile: <a href="/api/status">/api/status</a> &middot; <a href="/api/mode">/api/mode</a> &middot;
<a href="/api/events">/api/events</a> &middot; <a href="/api/metrics">/api/metrics</a> &middot;
WebSocket <code>/ws</code> (try <code>scripts/ws_print.py</code>)</p></body></html>"""


def create_app(engine: Engine | None = None, initial: dict | None = None) -> FastAPI:
    engine = engine or Engine()
    initial = initial or {"source": "SIMULATED"}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine.loop = asyncio.get_running_loop()
        engine.queue = asyncio.Queue()
        task = asyncio.create_task(engine.broadcaster())
        if engine.tagger_factory is None:
            engine.preload_tagger()

        def start_initial():
            try:
                engine.switch(**initial)
            except Exception as e:
                want = initial.get("source")
                print(f"[echotrace] could not start {want}: {e}")
                if want != "SIMULATED":
                    print("[echotrace] falling back to SIMULATED (clearly labelled as such)")
                    engine.switch("SIMULATED")
                    engine.error = f"{want} unavailable at startup: {e}"

        threading.Thread(target=start_initial, name="initial-mode", daemon=True).start()
        try:
            yield
        finally:
            task.cancel()
            await asyncio.to_thread(engine.stop)

    app = FastAPI(title="EchoTrace", version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Content-Type"])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse({"error": exc.detail if exc.status_code != 404 else "Not found"}, exc.status_code)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        try:
            for msg in engine.snapshot():
                await ws.send_text(json.dumps(msg))
            engine.clients.add(ws)
            while True:
                await ws.receive_text()               # we don't expect input; this detects disconnects
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            engine.clients.discard(ws)

    @app.get("/api/status")
    async def get_status():
        return engine.status_data()

    @app.get("/api/mode")
    async def get_mode():
        return engine.mode_payload()

    @app.post("/api/mode")
    async def post_mode(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, 400)
        try:
            return await asyncio.to_thread(engine.switch, body.get("source"), body.get("device"),
                                           body.get("file"), body.get("scenario"))
        except ModeError as e:
            return JSONResponse({"error": str(e)}, e.code)

    @app.get("/api/events")
    async def get_events():
        return engine.events()

    @app.post("/api/reset")
    async def post_reset():
        if engine.pipeline is not None:
            engine.pipeline.request_reset()            # applied by the worker thread; it broadcasts a status
        return {**engine.meta(), "ok": True}

    @app.get("/api/metrics")
    async def get_metrics():
        return engine.metrics()

    @app.get("/api/{rest:path}")
    async def api_not_found(rest: str):
        return JSONResponse({"error": "Not found"}, 404)

    @app.get("/{path:path}")
    async def frontend(path: str):
        dist = FRONTEND_DIST.resolve()
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(PLACEHOLDER)
        target = (dist / path).resolve()
        if path and target.is_file() and dist in target.parents:
            return FileResponse(target)
        return FileResponse(index)                     # SPA fallback

    return app
