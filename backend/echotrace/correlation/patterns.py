"""Ordered pattern templates over a cluster of events.

Each step is (category, min_count); other events may be interleaved; consecutive matched events must be
within PATTERN_MAX_GAP_S. The first (highest-priority) matching template wins. A cluster that matches
nothing is GREEN: it is logged but raises no alert - this is EchoTrace's false-alert reduction compared
with a classifier that alerts on every concerning label.
"""

from __future__ import annotations

from dataclasses import dataclass

from echotrace import config
from echotrace.events import Event


@dataclass(frozen=True)
class Pattern:
    name: str
    steps: tuple[tuple[str, int], ...]     # (category, min events)
    risk: str
    description: str                       # plain words, used in summaries
    max_gap_s: float = config.PATTERN_MAX_GAP_S


PATTERNS: list[Pattern] = [
    Pattern("MOVEMENT_IMPACT_DISTRESS", (("FOOTSTEPS", 1), ("IMPACT", 1), ("DISTRESS", 1)), "RED",
            "movement -> impact -> distress"),
    Pattern("IMPACT_DISTRESS", (("IMPACT", 1), ("DISTRESS", 1)), "AMBER", "impact -> distress"),
    Pattern("ALARM_EVACUATION", (("ALARM", 1), ("FOOTSTEPS", 2)), "AMBER", "alarm -> movement (possible evacuation)"),
    Pattern("GLASS_INTRUSION", (("GLASS", 1), ("FOOTSTEPS", 1)), "AMBER", "breaking glass -> movement"),
]
RISK_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}


@dataclass
class Match:
    pattern: Pattern
    events: list[Event]                    # the events that matched, in time order


def _match_from(events: list[Event], start: int, pat: Pattern) -> list[Event] | None:
    step, count, picked = 0, 0, []
    for ev in events[start:]:
        if picked and ev.t_start - picked[-1].t_end > pat.max_gap_s:
            break
        cat, need = pat.steps[step]
        if ev.category == cat:
            picked.append(ev)
            count += 1
        elif count >= need and step + 1 < len(pat.steps) and ev.category == pat.steps[step + 1][0]:
            step, count = step + 1, 1
            picked.append(ev)
        elif not picked:
            return None
    last_cat, last_need = pat.steps[-1]
    if step == len(pat.steps) - 1 and count >= last_need:
        return picked
    return None


def match(events: list[Event], patterns: list[Pattern] = PATTERNS) -> Match | None:
    """Highest-priority pattern found anywhere in the cluster (events in any order)."""
    evs = sorted(events, key=lambda e: (e.t_start, e.t_end))
    for pat in patterns:
        first = pat.steps[0][0]
        for i, ev in enumerate(evs):
            if ev.category != first:
                continue
            got = _match_from(evs, i, pat)
            if got:
                return Match(pat, got)
    return None
