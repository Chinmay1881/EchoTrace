"""EchoTrace pipeline: source -> rolling window -> tagger -> debounce -> localize -> correlate -> risk -> messages.

Analyzer is the synchronous core (no threads, fully testable). Pipeline runs it on a worker thread and hands
each message to an emit callback; the server's callback bridges to asyncio with loop.call_soon_threadsafe.
Every message carries the source mode (LIVE / RECORDED / SIMULATED) of the data it came from.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Callable

import numpy as np

from echotrace import config
from echotrace.audio.devices import channel_report
from echotrace.audio.sources import SimHop, SourceInfo
from echotrace.audio.window import RollingWindow, Window
from echotrace.baseline import BaselineAlerter
from echotrace.correlation.graph import EventGraph
from echotrace.correlation.patterns import PATTERNS, RISK_ORDER, match
from echotrace.detection.debounce import Debouncer, RawEvent
from echotrace.events import Event
from echotrace.localization.zones import Localization, ZoneLocalizer, angle_to_zone
from echotrace.risk.engine import RiskEngine
from echotrace.risk.summary import explain, summarize
from echotrace.tagging.categories import CategoryMap, top_k

Out = tuple[dict, float | None]          # (message, capture time of the triggering audio, for latency)
Emit = Callable[[dict, float | None], None]


def db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))


class AudioRing:
    """The last few seconds of raw stereo audio, addressed by stream time (memory only, never saved)."""

    def __init__(self, seconds: float = config.AUDIO_RING_S, rate: int = config.CAPTURE_RATE):
        self.rate = rate
        self.buf = np.zeros((int(seconds * rate), 2), dtype=np.float32)
        self.total = 0

    def append(self, block: np.ndarray) -> None:
        n = len(block)
        if n >= len(self.buf):
            self.buf[:] = block[-len(self.buf):]
        else:
            self.buf[:-n] = self.buf[n:]
            self.buf[-n:] = block
        self.total += n

    def get(self, t0: float, t1: float) -> np.ndarray:
        first = self.total - len(self.buf)
        a = max(int(t0 * self.rate), first, 0)
        b = min(int(t1 * self.rate), self.total)
        if b <= a:
            return np.zeros((0, 2), dtype=np.float32)
        return self.buf[a - first:b - first].copy()


class Analyzer:
    def __init__(self, info: SourceInfo, tagger=None, model_device: str | None = None,
                 localizer: ZoneLocalizer | None = None, start_wall: datetime | None = None,
                 window_s: float = config.WINDOW_S, hop_s: float = config.HOP_S, id_prefix: str = ""):
        self.info = info
        self.id_prefix = id_prefix           # e.g. "m2-" so ids stay unique across source switches
        self.sensitivity = config.SENSITIVITY  # the profile the debouncer was built with (reported in status)
        self._n_events = 0                   # survive reset, so ids are never reused within a session
        self._n_clusters = 0
        self.source = info.source
        self.tagger = tagger
        self.cmap = CategoryMap(tagger.labels) if tagger is not None else None
        self.model_device = model_device or (tagger.device if tagger is not None else "cpu")
        self.window_s, self.hop_s = window_s, hop_s
        self.hop_n = int(round(hop_s * info.sample_rate))
        self.localizer = localizer or ZoneLocalizer()
        self.start_wall = start_wall or datetime.now()
        self.ring = AudioRing()
        self.reset_state()
        # localization is impossible with one channel; with two it is re-checked as audio arrives
        self.loc_on = info.channels >= 2
        self.loc_reason = "mono input" if info.channels < 2 else "stereo input"
        self._last_loc_check = -1e9

    def reset_state(self) -> None:
        self.debouncer = Debouncer(list(config.CATEGORIES), self.hop_s)
        old_graph = getattr(self, "graph", None)
        self.graph = EventGraph()
        if old_graph is not None:
            self.graph._n = old_graph._n
        self.risk = RiskEngine()
        self.baseline = BaselineAlerter()
        self.events: list[Event] = []
        self.sequences: dict[str, dict] = {}
        # per sequence: (risk, pattern name, id of the event that raised it, number of events at that moment)
        self.fired: dict[str, tuple[str, str, str, int]] = {}
        self.alerts: list[dict] = []     # one entry per risk escalation of a sequence (what an operator sees)
        self.hop_angles: deque = deque(maxlen=200)
        self.latencies: list[float] = []
        self.last_latency = 0.0
        self.dropped_extra = 0
        self.t = getattr(self, "t", 0.0)         # stream time keeps running across a reset
        self._last_status = -1e9
        self.last_frame: dict | None = getattr(self, "last_frame", None)

    # ----------------------------------------------------------------- helpers
    def wall(self, t: float) -> str:
        return (self.start_wall + timedelta(seconds=t)).isoformat(timespec="milliseconds")

    def _base(self, t: float) -> dict:
        return {"source": self.source, "t": round(t, 3), "wall": self.wall(t)}

    def record_latency(self, ms: float) -> None:
        self.last_latency = round(ms, 1)
        self.latencies.append(self.last_latency)

    def status(self, t: float | None = None, dropped_blocks: int = 0) -> dict:
        t = self.t if t is None else t
        return {"type": "status", "data": {
            **self._base(t),
            "risk": self.risk.current(t),
            "latency_ms": self.last_latency,
            "device": self.info.device,
            "host_api": self.info.host_api,
            "sample_rate": self.info.sample_rate,
            "channels": self.info.channels,
            "localization": "ON" if self.loc_on else "OFF",
            "model_device": self.model_device,
            "dropped_blocks": int(dropped_blocks + self.dropped_extra),
            "sensitivity": self.sensitivity,
        }}

    # ----------------------------------------------------------------- inputs
    def feed_block(self, block: np.ndarray) -> None:
        """Every raw block goes into the ring (for localization) whether or not its window is analysed."""
        self.ring.append(block)

    def process_window(self, w: Window, dropped_blocks: int = 0) -> list[Out]:
        """Audio path: tag one analysis window."""
        probs = self.tagger.tag(w.audio)
        scores = self.cmap.scores(probs)
        labels = {c: self.cmap.best_label(probs, c)[0] for c in scores}
        top = top_k(probs, self.cmap.labels)
        newest = w.audio[-self.hop_n:]
        rms = (db(newest[:, 0]), db(newest[:, 1]))
        if self.info.channels >= 2 and w.t_end - self._last_loc_check >= config.LOC_CHECK_EVERY_S:
            self._check_channels(w.audio, w.t_end)
        return self._process(w.t_end, w.capture_time, scores, labels, top, rms, dropped_blocks)

    def process_sim(self, h: SimHop, dropped_blocks: int = 0) -> list[Out]:
        """Simulation path: tagger output and angles come from the script."""
        if h.angle_deg is not None:
            self.hop_angles.append((h.t, h.angle_deg))
        return self._process(h.t, h.capture_time, h.categories, h.labels, h.top, h.rms_db, dropped_blocks)

    def flush(self, dropped_blocks: int = 0) -> list[Out]:
        """End of a finite source: close open events."""
        out: list[Out] = []
        for raw in self.debouncer.flush(time.perf_counter()):
            out += self._on_event(raw)
        out.append((self.status(self.t, dropped_blocks), None))
        return out

    # ----------------------------------------------------------------- core
    def _check_channels(self, audio: np.ndarray, t: float) -> None:
        self._last_loc_check = t
        rep = channel_report(audio)
        if rep.silent:
            return                                  # digital silence says nothing; keep the previous state
        self.loc_on = not rep.identical
        self.loc_reason = "channels identical (mono or processed endpoint)" if rep.identical else "distinct stereo"

    def _process(self, t: float, capture: float, scores: dict[str, float], labels: dict[str, str],
                 top: list[tuple[str, float]], rms: tuple[float, float], dropped_blocks: int) -> list[Out]:
        self.t = t
        frame = {"type": "frame", "data": {
            **self._base(t),
            "top": [{"label": l, "p": round(float(p), 4)} for l, p in top],
            "categories": {c: round(float(p), 4) for c, p in scores.items()},
            "rms_db": [round(float(rms[0]), 1), round(float(rms[1]), 1)],
        }}
        self.last_frame = frame
        out: list[Out] = [(frame, None)]
        for raw in self.debouncer.update(t, scores, labels, capture):
            out += self._on_event(raw)
        if t - self._last_status >= config.STATUS_EVERY_S:
            self._last_status = t
            out.append((self.status(t, dropped_blocks), None))
        return out

    def _localize(self, raw: RawEvent) -> Localization:
        if not self.loc_on:
            return Localization("UNKNOWN", None, 0.0, 0, f"localization OFF ({self.loc_reason})")
        if self.source == "SIMULATED":
            angs = [a for t, a in self.hop_angles if raw.t_start < t <= raw.t_end + self.hop_s]
            if not angs:
                return Localization("UNKNOWN", None, 0.0, 0, "no simulated angle")
            ang = float(np.median(angs))
            return Localization(angle_to_zone(ang), round(ang, 1), 1.0, len(angs), "simulated")
        t0 = raw.t_start - config.LOC_PRE_S
        t1 = min(raw.t_end, t0 + config.LOC_MAX_SPAN_S)
        return self.localizer.localize(self.ring.get(t0, t1))

    def _on_event(self, raw: RawEvent) -> list[Out]:
        loc = self._localize(raw)
        self._n_events += 1
        ev = Event(f"{self.id_prefix}e{self._n_events}", raw.t_start, raw.t_end, raw.category, raw.label,
                   round(float(raw.confidence), 3), loc.zone, loc.angle_deg, self.wall(raw.t_start),
                   raw.capture_time)
        return self.add_event(ev)

    def add_event(self, ev: Event) -> list[Out]:
        """Correlate one localized event (also used to replay logged events in regression tests)."""
        self.t = max(self.t, ev.t_end)
        if not ev.wall:
            ev.wall = self.wall(ev.t_start)
        self.events.append(ev)
        self.baseline.observe(ev)
        cluster = self.graph.add(ev)
        sid = f"{self.id_prefix}{cluster.id}"
        m = match(cluster.events)
        new_risk = m.pattern.risk if m else "GREEN"
        prev = self.fired.get(sid)
        if m and (prev is None or RISK_ORDER[new_risk] > RISK_ORDER[prev[0]]):
            # escalation: alert once, at the event that completed the pattern
            prev = (new_risk, m.pattern.name, m.completed_by.id, len(cluster.events))
            self.fired[sid] = prev
            self.alerts.append({"sequence_id": sid, "risk": new_risk, "pattern": m.pattern.name,
                                "event_id": m.completed_by.id, "t": self.t, "wall": self.wall(self.t)})
        if prev is not None:                     # a sequence never silently downgrades; repeats don't re-alert
            risk, pattern, fired_at, n_at = prev
            if m is None or m.pattern.name != pattern:
                m = match(cluster.events, [p for p in PATTERNS if p.name == pattern])
            later = len(cluster.events) - n_at
        else:
            risk, fired_at, later = "GREEN", None, 0
            pattern = "ISOLATED_EVENT" if len(cluster.events) == 1 else "NONE"
        traj = cluster.trajectory()
        self.risk.update(sid, risk, cluster.last_t)
        seq = {"type": "sequence", "data": {
            **self._base(self.t),
            "id": sid,
            "event_ids": [e.id for e in sorted(cluster.events, key=lambda e: e.t_start)],
            "pattern": pattern,
            "risk": risk,
            "explanation": explain(cluster.events, risk, m, traj, fired_at, later),
            "summary": summarize(cluster.events, risk, m),
            "trajectory": traj,
        }}
        self.sequences[sid] = seq
        event = {"type": "event", "data": {
            **self._base(self.t),
            "id": ev.id, "t_start": ev.t_start, "t_end": ev.t_end, "category": ev.category, "label": ev.label,
            "confidence": ev.confidence, "zone": ev.zone, "angle_deg": ev.angle_deg,
        }}
        return [(event, ev.capture_time), (seq, ev.capture_time), (self.status(self.t), None)]


class Pipeline:
    """Runs a source through an Analyzer on a worker thread. emit(msg, capture_time) gets every message."""

    def __init__(self, source, tagger=None, emit: Emit | None = None, model_device: str | None = None,
                 start_wall: datetime | None = None, window_s: float = config.WINDOW_S, hop_s: float = config.HOP_S,
                 id_prefix: str = "", record_latency: bool = True):
        self.source = source
        self.record_latency = record_latency     # False for offline runs: wall-clock latency is meaningless there
        self.analyzer = Analyzer(source.info, tagger, model_device, start_wall=start_wall,
                                 window_s=window_s, hop_s=hop_s, id_prefix=id_prefix)
        self.rw = RollingWindow(source.info.sample_rate, window_s, hop_s)
        self.emit = emit or self._record_emit
        self.messages: list[dict] = []
        self.keep_messages = emit is None
        self._thread: threading.Thread | None = None
        self._running = False
        self._reset_requested = threading.Event()
        self.error: str | None = None

    def request_reset(self) -> None:
        """Thread-safe: clear events/sequences/risk at the next step (the source keeps running)."""
        self._reset_requested.set()

    def _record_emit(self, msg: dict, capture: float | None) -> None:
        if self.record_latency and capture is not None and msg["type"] == "event":
            self.analyzer.record_latency((time.perf_counter() - capture) * 1000)
        if self.keep_messages:
            self.messages.append(msg)

    @property
    def dropped_blocks(self) -> int:
        return int(getattr(self.source, "dropped_blocks", 0))

    def _backlog_s(self) -> float:
        q = getattr(self.source, "q", None)
        if q is None or not getattr(self.source, "realtime", True):
            return 0.0
        return q.qsize() * config.BLOCK_SIZE / self.source.info.sample_rate

    def step(self, timeout: float = 0.2) -> bool:
        """Process one source item. Returns False when a finite source is exhausted."""
        if self._reset_requested.is_set():
            self._reset_requested.clear()
            self.analyzer.reset_state()
            self.emit(self.analyzer.status(self.analyzer.t, self.dropped_blocks), None)
        item = self.source.get(timeout=timeout)
        if item is None:
            if self.source.finished:
                for msg, cap in self.analyzer.flush(self.dropped_blocks):
                    self.emit(msg, cap)
                return False
            return True
        if isinstance(item, SimHop):
            outs = self.analyzer.process_sim(item, self.dropped_blocks)
        else:
            block, capture = item
            self.analyzer.feed_block(block)
            windows = self.rw.push(block, capture)
            behind = self._backlog_s() > config.MAX_BACKLOG_S
            outs = []
            for w in windows:
                if behind:                       # stale: keep the audio for localization, skip tagging
                    self.analyzer.dropped_extra += 1
                    continue
                outs += self.analyzer.process_window(w, self.dropped_blocks)
        for msg, cap in outs:
            self.emit(msg, cap)
        return True

    def run_to_end(self) -> list[dict]:
        """Synchronous: process a finite source completely (tests, evaluation)."""
        self.source.start()
        try:
            while self.step(timeout=0.5):
                pass
        finally:
            self.source.stop()
        return self.messages

    def _loop(self) -> None:
        try:
            self.source.start()
            while self._running and self.step():
                pass
        except Exception as e:                   # surface to /api/status instead of dying silently
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.source.stop()
            self._running = False

    def start(self) -> "Pipeline":
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="echotrace-pipeline", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._running


# --------------------------------------------------------------------------- offline (evaluation)
_TAGGER_CACHE: dict[bool, object] = {}


def default_tagger(force_cpu: bool = False):
    """CNN14, loaded once per process and reused (loading takes seconds; evaluation runs many clips)."""
    if force_cpu not in _TAGGER_CACHE:
        from echotrace.tagging.panns_tagger import PannsTagger
        t = PannsTagger(force_cpu=force_cpu)
        t.warmup()
        _TAGGER_CACHE[force_cpu] = t
    return _TAGGER_CACHE[force_cpu]


def run_wav_detailed(path, tagger=None, *, force_cpu: bool = False, calibration=None,
                     start_wall: datetime | None = None, keep_frames: bool = True) -> tuple[list[dict], Analyzer]:
    """Run a WAV through the FULL pipeline (same code as LIVE), as fast as possible.

    Returns (messages, analyzer). messages are the {type, data} dicts the WebSocket would carry, in order,
    labelled source="RECORDED". The analyzer gives the rest:
      analyzer.events           every Event (id, t_start, t_end, category, label, confidence, zone, angle_deg)
      analyzer.alerts           EchoTrace alerts: one dict per sequence escalation (sequence_id, risk, pattern, event_id)
      analyzer.baseline.alerts  classification-only baseline alerts (one per concerning event)
      analyzer.sequences        final state of every sequence message, by id
    Latency is NOT measured here (no real-time pacing; latency_ms stays 0.0) - measure it with a real-time
    run (e.g. the server in RECORDED mode, or Pipeline(WavReplaySource(path, realtime=True), ...).run_to_end()
    and analyzer.latencies). Output is deterministic for a given WAV, tagger and calibration.
    tagger: anything with .labels/.device/.tag(window) (default: cached CNN14).
    calibration: a localization.zones.Calibration (default: backend/calibration.json or the built-in default).
    """
    from echotrace.audio.sources import WavReplaySource
    src = WavReplaySource(path, realtime=False)
    pipe = Pipeline(src, tagger=tagger if tagger is not None else default_tagger(force_cpu),
                    start_wall=start_wall or datetime(2000, 1, 1), record_latency=False)
    if calibration is not None:
        pipe.analyzer.localizer = ZoneLocalizer(calibration)
    msgs = pipe.run_to_end()
    if not keep_frames:
        msgs = [m for m in msgs if m["type"] != "frame"]
    return msgs, pipe.analyzer


def run_wav(path, tagger=None, **kw) -> list[dict]:
    """Offline: every message the pipeline produces for a WAV (see run_wav_detailed)."""
    return run_wav_detailed(path, tagger, **kw)[0]
