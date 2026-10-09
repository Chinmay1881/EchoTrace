"""The localized acoustic event shared by correlation, risk, summaries and the baseline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Event:
    id: str
    t_start: float
    t_end: float
    category: str
    label: str
    confidence: float
    zone: str                       # LEFT | CENTRE | RIGHT | UNKNOWN
    angle_deg: float | None
    wall: str = ""                  # ISO wall time of t_start
    capture_time: float = 0.0       # capture clock of the block that triggered emission (latency)
