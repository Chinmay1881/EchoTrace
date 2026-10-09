"""Classification-only baseline: raises an alert for EVERY concerning event on its own.

This is what a plain audio tagger does. It sees the same debounced events as EchoTrace, so the
comparison isolates the effect of correlation (EchoTrace only alerts on matched patterns).
"""

from __future__ import annotations

from dataclasses import dataclass

from echotrace import config
from echotrace.events import Event


@dataclass
class BaselineAlert:
    event_id: str
    t: float
    category: str
    confidence: float


class BaselineAlerter:
    def __init__(self, concerning: list[str] = config.CONCERNING):
        self.concerning = set(concerning)
        self.alerts: list[BaselineAlert] = []

    def observe(self, ev: Event) -> BaselineAlert | None:
        if ev.category in self.concerning:
            alert = BaselineAlert(ev.id, ev.t_start, ev.category, ev.confidence)
            self.alerts.append(alert)
            return alert
        return None

    def reset(self) -> None:
        self.alerts.clear()
