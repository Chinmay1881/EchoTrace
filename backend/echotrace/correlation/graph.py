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
        return trajectory(self.events)


def groups(events: list[Event]) -> list[list[Event]]:
    """Time-ordered runs of consecutive same-category events (e.g. 5 impacts in a row = one group)."""
    out: list[list[Event]] = []
    for e in sorted(events, key=lambda e: (e.t_start, e.t_end)):
        if out and out[-1][0].category == e.category:
            out[-1].append(e)
        else:
            out.append([e])
    return out


def group_zone(group: list[Event]) -> str:
    """Confidence-weighted majority zone of a group (UNKNOWN ignored), so one stray reading can't flip it."""
    votes: dict[str, float] = {}
    for e in group:
        if e.zone != "UNKNOWN":
            votes[e.zone] = votes.get(e.zone, 0.0) + e.confidence
    return max(votes, key=votes.get) if votes else "UNKNOWN"


def group_zones(group: list[Event]) -> list[str]:
    """Footsteps keep their movement (zone per event); any other sound counts as one place."""
    if group[0].category != "FOOTSTEPS":
        z = group_zone(group)
        return [] if z == "UNKNOWN" else [z]
    out: list[str] = []
    for e in group:
        if e.zone != "UNKNOWN" and (not out or out[-1] != e.zone):
            out.append(e.zone)
    return out


def trajectory(events: list[Event]) -> list[str]:
    """The possible acoustic trajectory: zones in time order, repeats and UNKNOWN collapsed."""
    out: list[str] = []
    for g in groups(events):
        for z in group_zones(g):
            if not out or out[-1] != z:
                out.append(z)
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
