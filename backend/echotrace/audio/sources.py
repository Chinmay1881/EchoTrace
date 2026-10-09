"""Input sources. All share: start(), stop(), get(timeout) -> item | None, finished, info, dropped_blocks.

LiveMicSource   (LIVE)      sounddevice on the WDM-KS endpoint; the callback only enqueues and counts drops.
WavReplaySource (RECORDED)  a WAV file, paced in real time or as fast as possible (evaluation).
SimSource       (SIMULATED) a scripted scenario of tagger outputs; no audio, no model.

Audio sources yield (block, capture_time) with block (n, 2) float32 at 48 kHz; SimSource yields SimHop.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from math import gcd
from pathlib import Path
from typing import Iterator

import numpy as np

from echotrace import config
from echotrace.audio.devices import resolve_device


@dataclass
class SourceInfo:
    source: str                  # "LIVE" | "RECORDED" | "SIMULATED"
    device: str
    host_api: str
    sample_rate: int
    channels: int
    extra: dict = field(default_factory=dict)


class LiveMicSource:
    def __init__(self, device_name: str | None = None, host_api: str | None = config.REQUIRED_HOST_API,
                 rate: int = config.CAPTURE_RATE, channels: int = config.CAPTURE_CHANNELS,
                 block: int = config.BLOCK_SIZE, max_queue: int = 200):
        self.dev = resolve_device(device_name, host_api)
        self.rate, self.channels, self.block = rate, channels, block
        self.q: queue.Queue = queue.Queue(maxsize=max_queue)   # 200 x 50 ms = 10 s of slack
        self.dropped_blocks = 0
        self.overflows = 0
        self.stream = None
        self.info = SourceInfo("LIVE", self.dev.name, self.dev.host_api, rate, channels)

    def _callback(self, indata, frames, time_info, status):
        if status and status.input_overflow:
            self.overflows += 1
        try:
            self.q.put_nowait((indata.copy(), time.monotonic()))
        except queue.Full:
            self.dropped_blocks += 1

    def start(self) -> "LiveMicSource":
        import sounddevice as sd
        try:
            self.stream = sd.InputStream(device=self.dev.index, samplerate=self.rate, channels=self.channels,
                                         dtype="float32", blocksize=self.block, callback=self._callback)
            self.stream.start()
        except Exception as e:
            raise RuntimeError(
                f"Could not open {self.dev.label} at {self.rate} Hz x {self.channels} ch: {e}\n"
                "WDM-KS is exclusive: close other apps using the microphone (Teams, Zoom, browser tabs, "
                "Sound settings) and try again."
            ) from e
        return self

    def stop(self) -> None:
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def blocks(self, timeout: float = 1.0) -> Iterator[tuple[np.ndarray, float]]:
        while self.stream is not None:
            try:
                yield self.q.get(timeout=timeout)
            except queue.Empty:
                continue

    def get(self, timeout: float = 1.0) -> tuple[np.ndarray, float] | None:
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def finished(self) -> bool:
        return False

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


class WavReplaySource:
    """Replays a WAV through the same pipeline. realtime=True paces blocks like a microphone."""

    def __init__(self, path: str | Path, realtime: bool = True, block: int = config.BLOCK_SIZE, loop: bool = False):
        import soundfile as sf
        from scipy.signal import resample_poly

        self.path = Path(path)
        data, rate = sf.read(str(self.path), dtype="float32", always_2d=True)
        if rate != config.CAPTURE_RATE:
            g = gcd(config.CAPTURE_RATE, rate)
            data = resample_poly(data, config.CAPTURE_RATE // g, rate // g, axis=0).astype(np.float32)
        file_channels = data.shape[1]
        if file_channels == 1:
            data = np.repeat(data, 2, axis=1)     # mono file: identical channels -> localization OFF
        self.data = np.ascontiguousarray(data[:, :2])
        self.rate, self.block, self.realtime, self.loop = config.CAPTURE_RATE, block, realtime, loop
        self.info = SourceInfo("RECORDED", f"file: {self.path.name}", "file", self.rate, min(file_channels, 2),
                               {"file": str(self.path), "seconds": round(len(self.data) / self.rate, 2)})
        self.pos = 0
        self.dropped_blocks = 0
        self.q: queue.Queue = queue.Queue(maxsize=400)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._done = False

    @property
    def finished(self) -> bool:
        return self._done and self.q.empty()

    def _next_block(self) -> np.ndarray | None:
        if self.pos >= len(self.data):
            if not self.loop:
                return None
            self.pos = 0
        b = self.data[self.pos:self.pos + self.block]
        self.pos += self.block
        return b

    def _pace(self) -> None:
        t0, n = time.monotonic(), 0
        while not self._stop.is_set():
            b = self._next_block()
            if b is None:
                break
            due = t0 + n * self.block / self.rate
            delay = due - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            n += 1
            try:
                self.q.put_nowait((b, time.monotonic()))
            except queue.Full:
                self.dropped_blocks += 1
        self._done = True

    def start(self) -> "WavReplaySource":
        self._stop.clear()
        self._done = False
        if self.realtime:
            self._thread = threading.Thread(target=self._pace, name="wav-replay", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def get(self, timeout: float = 1.0):
        if not self.realtime:
            b = self._next_block()
            if b is None:
                self._done = True
                return None
            return b, time.monotonic()
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None


# --------------------------------------------------------------------------- simulation
@dataclass
class SimHop:
    """One hop of synthetic tagger output (what CNN14 + localization would have produced)."""
    t: float
    capture_time: float
    categories: dict[str, float]
    labels: dict[str, str]
    top: list[tuple[str, float]]
    rms_db: tuple[float, float]
    angle_deg: float | None          # calibrated convention: + = RIGHT


# (start s, duration s, category, label, peak confidence, zone) within one loop of the scenario
SIM_SCRIPT: list[tuple[float, float, str, str, float, str]] = [
    (2.0, 0.5, "DOOR", "Door", 0.55, "CENTRE"),                         # distractor: isolated door sound
    (12.0, 0.4, "IMPACT", "Slam", 0.48, "LEFT"),                        # distractor: lone slam (baseline alerts)
    (23.0, 2.0, "FOOTSTEPS", "Walk, footsteps", 0.62, "LEFT"),          # demo sequence ...
    (25.5, 1.5, "FOOTSTEPS", "Walk, footsteps", 0.58, "CENTRE"),
    (28.2, 0.4, "IMPACT", "Thump, thud", 0.71, "RIGHT"),
    (29.6, 1.0, "DISTRESS", "Screaming", 0.54, "RIGHT"),
]
SIM_LOOP_S = 60.0     # long quiet tail so the risk visibly decays back to GREEN (RISK_DECAY_S) before repeating
ZONE_ANGLE = {"LEFT": -45.0, "CENTRE": 0.0, "RIGHT": 45.0}
BACKGROUND_TOP = [("Inside, small room", 0.12), ("Speech", 0.08), ("Silence", 0.05), ("Music", 0.03), ("Hum", 0.02)]


class SimSource:
    """Scripted scenario (demo sequence + distractors). Clearly SIMULATED; never shown as live."""

    def __init__(self, realtime: bool = True, loops: int | None = None, hop_s: float = config.HOP_S,
                 script=SIM_SCRIPT, loop_s: float = SIM_LOOP_S, seed: int = 7):
        self.realtime, self.loops, self.hop_s = realtime, loops, hop_s
        self.script, self.loop_s = script, loop_s
        self.rng = np.random.default_rng(seed)
        self.info = SourceInfo("SIMULATED", "simulated scenario", "none", config.CAPTURE_RATE, 2,
                               {"script_events": len(script), "loop_s": loop_s})
        self.dropped_blocks = 0
        self.n = 0
        self.t0 = 0.0
        self._running = False
        self._done = False

    @property
    def finished(self) -> bool:
        return self._done

    def start(self) -> "SimSource":
        self.t0, self.n, self._running, self._done = time.monotonic(), 0, True, False
        return self

    def stop(self) -> None:
        self._running = False

    def hop_at(self, t: float) -> SimHop:
        local = t % self.loop_s
        cats = {c: float(self.rng.uniform(0.0, 0.03)) for c in config.CATEGORIES}
        labels = {c: names[0] for c, names in config.CATEGORIES.items()}
        angle, level = None, 0.0
        for start, dur, cat, label, peak, zone in self.script:
            new_overlap = start < local and start + dur > local - self.hop_s       # newest hop of audio
            old_overlap = start < local - self.hop_s and start + dur > local - 2 * self.hop_s
            score = peak if new_overlap else (0.6 * peak if old_overlap else 0.0)
            if score > cats[cat]:
                cats[cat], labels[cat] = round(score, 3), label
                if score > level:
                    level, angle = score, ZONE_ANGLE[zone] + float(self.rng.uniform(-6, 6))
        top = sorted([(labels[c], p) for c, p in cats.items() if p > 0.1] + BACKGROUND_TOP,
                     key=lambda x: -x[1])[: config.TOP_K]
        base = -52.0 + 30.0 * level
        tilt = 0.0 if angle is None else angle / 15.0          # louder on the side the sound is on
        rms = (round(base - tilt + float(self.rng.uniform(-1, 1)), 1), round(base + tilt + float(self.rng.uniform(-1, 1)), 1))
        return SimHop(round(t, 3), time.monotonic(), cats, labels, top, rms, angle)

    def get(self, timeout: float = 1.0) -> SimHop | None:
        if not self._running:
            return None
        t = (self.n + 1) * self.hop_s
        if self.loops is not None and t > self.loops * self.loop_s:
            self._done = True
            return None
        if self.realtime:
            delay = self.t0 + t - time.monotonic()
            if delay > timeout:
                time.sleep(timeout)
                return None
            if delay > 0:
                time.sleep(delay)
        self.n += 1
        return self.hop_at(t)
