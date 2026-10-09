"""Temporal event graph: events are nodes, linked to recent events within LINK_WINDOW_S.

Connected events form one candidate sequence ("cluster"). The zone progression of a cluster is
reported as a *possible acoustic trajectory* - it never claims the sounds came from one person.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from echotrace import config
from echotrace.events import Event


@dataclass
class Cluster:
    id: str
    events: list[Event] = field(default_factory=list)
    edges: list[tuple[str, str, float]] = field(default_factory=list)   # (from_id, to_id, gap_s)

    @property
    def last_t(self) -> float:
        return max(e.t_end for e in self.events)

    def trajectory(self) -> list[str]:
        """Zones in time order, consecutive repeats and UNKNOWN collapsed."""
        out: list[str] = []
        for e in sorted(self.events, key=lambda e: e.t_start):
            if e.zone != "UNKNOWN" and (not out or out[-1] != e.zone):
                out.append(e.zone)
        return out


class EventGraph:
    def __init__(self, link_window_s: float = config.LINK_WINDOW_S):
        self.link_window_s = link_window_s
        self.clusters: list[Cluster] = []
        self._n = 0

    def add(self, ev: Event) -> Cluster:
        """Attach an event to the active cluster if it is close enough in time, else start a new one."""
        cur = self.clusters[-1] if self.clusters else None
        if cur is not None and ev.t_start - cur.last_t <= self.link_window_s:
            for prev in cur.events:
                gap = ev.t_start - prev.t_end
                if gap <= self.link_window_s:
                    cur.edges.append((prev.id, ev.id, round(max(gap, 0.0), 2)))
            cur.events.append(ev)
            return cur
        self._n += 1
        cl = Cluster(f"s{self._n}", [ev])
        self.clusters.append(cl)
        return cl

    def reset(self) -> None:
        self.clusters.clear()
        self._n = 0
