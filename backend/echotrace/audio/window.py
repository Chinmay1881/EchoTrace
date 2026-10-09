"""Rolling analysis window over a stream of (n, channels) audio blocks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Window:
    audio: np.ndarray        # (window_samples, channels) float32 at the capture rate
    t_end: float             # stream time (s) of the last sample, from the sample count
    capture_time: float      # monotonic clock when the newest block arrived (latency reference)


class RollingWindow:
    """Emits a full window every `hop_s` once `window_s` of audio has been seen.

    Timing comes from the sample count, so it is exact regardless of block size.
    """

    def __init__(self, rate: int, window_s: float, hop_s: float, channels: int = 2):
        self.rate = rate
        self.win = int(round(window_s * rate))
        self.hop = int(round(hop_s * rate))
        if self.hop <= 0 or self.hop > self.win:
            raise ValueError("hop must be > 0 and <= window")
        self.buf = np.zeros((self.win, channels), dtype=np.float32)
        self.total = 0           # samples seen since start
        self.next_emit = self.win

    def push(self, block: np.ndarray, capture_time: float = 0.0) -> list[Window]:
        out = []
        block = np.asarray(block, dtype=np.float32)
        pos = 0
        while pos < len(block):
            # copy at most up to the next emission point so overlapping hops inside one big block are exact
            take = min(len(block) - pos, self.next_emit - self.total)
            chunk = block[pos:pos + take]
            if take >= self.win:
                self.buf[:] = chunk[-self.win:]
            else:
                self.buf[:-take] = self.buf[take:]   # numpy handles the overlapping copy
                self.buf[-take:] = chunk
            self.total += take
            pos += take
            if self.total == self.next_emit:
                out.append(Window(self.buf.copy(), self.total / self.rate, capture_time))
                self.next_emit += self.hop
        return out
