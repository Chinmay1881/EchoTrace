"""Audio sources. Every source yields (block, capture_time) with block shaped (n, 2) float32 at 48 kHz.

LiveMicSource: sounddevice on the WDM-KS endpoint. The callback only enqueues and counts drops.
(WavReplaySource and SimSource arrive in Phase 2.)
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
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

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
