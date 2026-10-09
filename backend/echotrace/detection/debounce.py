"""Per-category hysteresis: a stream of per-hop category scores -> discrete events.

An event opens when N of the last M hops score >= on, and closes after OFF_HOPS hops < off.
Events are emitted when they close, or in MAX_EVENT_S pieces while a long sound continues.
Hop times are window END times (stream seconds); the newest hop of audio is [t - hop_s, t].
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from echotrace import config


@dataclass
class RawEvent:
    category: str
    t_start: float
    t_end: float
    confidence: float          # peak category score
    label: str                 # best member label at the peak
    t_peak: float
    capture_time: float        # capture clock of the newest block of the hop that emitted the event


@dataclass
class _State:
    history: deque = field(default_factory=deque)
    active: bool = False
    t_start: float = 0.0
    t_last_on: float = 0.0     # last hop still >= off
    below: int = 0
    peak: float = 0.0
    label: str = ""
    t_peak: float = 0.0
    continuation: bool = False # this piece follows a MAX_EVENT_S split
    piece_on: bool = False     # the piece has at least one hop >= on


class Debouncer:
    def __init__(self, categories: list[str], hop_s: float = config.HOP_S,
                 on_n: int = config.ON_N, on_m: int = config.ON_M, off_hops: int = config.OFF_HOPS,
                 max_event_s: float = config.MAX_EVENT_S, thresholds=config.thresholds):
        self.hop_s = hop_s
        self.on_n, self.on_m, self.off_hops, self.max_event_s = on_n, on_m, off_hops, max_event_s
        self.thr = {c: thresholds(c) for c in categories}
        self.states = {c: _State(history=deque(maxlen=on_m)) for c in categories}

    def update(self, t: float, scores: dict[str, float], labels: dict[str, str],
               capture_time: float = 0.0) -> list[RawEvent]:
        """Feed one hop. scores: category -> score; labels: category -> best member label."""
        out = []
        for cat, st in self.states.items():
            p = scores.get(cat, 0.0)
            on, off = self.thr[cat]
            st.history.append(p >= on)
            if not st.active:
                if sum(st.history) >= self.on_n:
                    st.active, st.below = True, 0
                    st.t_start = t - self.hop_s
                    st.t_last_on = t
                    st.peak, st.label, st.t_peak = p, labels.get(cat, cat), t
                    st.continuation, st.piece_on = False, True
                continue
            if p >= off:
                st.below = 0
                st.t_last_on = t
                st.piece_on |= p >= on
                if p > st.peak:
                    st.peak, st.label, st.t_peak = p, labels.get(cat, cat), t
                if t - st.t_start >= self.max_event_s:      # long sound: emit a piece, keep going
                    out.append(self._emit(cat, st, t, capture_time))
                    st.t_start, st.continuation, st.piece_on = t, True, False
                    st.peak, st.label, st.t_peak = 0.0, labels.get(cat, cat), t
            else:
                st.below += 1
                if st.below >= self.off_hops:
                    # a fading tail after a split (never back above `on`) is not a new event
                    if st.piece_on or not st.continuation:
                        out.append(self._emit(cat, st, st.t_last_on, capture_time))
                    st.active = False
                    st.history.clear()
        return out

    def flush(self, capture_time: float = 0.0) -> list[RawEvent]:
        """Close every open event (end of a replayed file)."""
        out = []
        for cat, st in self.states.items():
            if st.active and (st.piece_on or not st.continuation):
                out.append(self._emit(cat, st, st.t_last_on, capture_time))
            if st.active:
                st.active = False
                st.history.clear()
        return out

    @staticmethod
    def _emit(cat: str, st: _State, t_end: float, capture_time: float) -> RawEvent:
        return RawEvent(cat, round(st.t_start, 3), round(max(t_end, st.t_start), 3), st.peak, st.label,
                        st.t_peak, capture_time)

    def reset(self) -> None:
        for st in self.states.values():
            st.active = False
            st.history.clear()
