"""Current risk state: the highest risk among sequences that were active recently, decaying back to GREEN."""

from __future__ import annotations

from echotrace import config
from echotrace.correlation.patterns import RISK_ORDER


class RiskEngine:
    def __init__(self, decay_s: float = config.RISK_DECAY_S):
        self.decay_s = decay_s
        self.seq: dict[str, tuple[str, float]] = {}     # sequence id -> (risk, time of its last event)

    def update(self, seq_id: str, risk: str, last_event_t: float) -> None:
        self.seq[seq_id] = (risk, last_event_t)

    def current(self, t: float) -> str:
        live = [r for r, last in self.seq.values() if t - last <= self.decay_s]
        return max(live, key=RISK_ORDER.get, default="GREEN")

    def reset(self) -> None:
        self.seq.clear()
