"""Deterministic, template-based plain-language summaries and "why" lists. No generative model.

Wording rules: RED is a "potentially significant sequence", never a confirmed emergency; movement is a
"possible acoustic trajectory", never a tracked person; every event carries its confidence.
"""

from __future__ import annotations

from echotrace.correlation.patterns import Match
from echotrace.events import Event

PHRASE = {
    "FOOTSTEPS": "footsteps",
    "IMPACT": "an impact",
    "DISTRESS": "a possible distress vocalisation",
    "ALARM": "an alarm",
    "GLASS": "breaking glass",
    "DOOR": "a door sound",
}
LEAD = {   # sentence-initial form
    "IMPACT": "Impact",
    "DISTRESS": "Possible distress vocalisation",
    "ALARM": "Alarm",
    "GLASS": "Breaking glass",
    "DOOR": "Door sound",
}
STATUS = {
    "RED": "Status RED: potentially significant sequence - verify.",
    "AMBER": "Status AMBER: possible correlated sequence - monitor and verify.",
    "GREEN": "Status GREEN: no correlated pattern - logged, no alert.",
}


def where(zone: str) -> str:
    return {"LEFT": "on the LEFT", "RIGHT": "on the RIGHT", "CENTRE": "in the CENTRE"}.get(zone, "(direction unknown)")


def pct(p: float) -> str:
    return f"{round(p * 100)}%"


def clock(wall: str) -> str:
    """'2026-10-09T14:02:11.250000' -> '14:02:11'."""
    return wall[11:19] if len(wall) >= 19 else wall


def _groups(events: list[Event]) -> list[list[Event]]:
    """Consecutive events of the same category form one group (e.g. a run of footsteps)."""
    out: list[list[Event]] = []
    for e in events:
        if out and out[-1][0].category == e.category:
            out[-1].append(e)
        else:
            out.append([e])
    return out


def _zones(group: list[Event]) -> list[str]:
    z: list[str] = []
    for e in group:
        if e.zone != "UNKNOWN" and (not z or z[-1] != e.zone):
            z.append(e.zone)
    return z


def _describe(group: list[Event], first: bool) -> str:
    """'Footsteps heard moving LEFT -> CENTRE (62%)' / 'an impact on the RIGHT (71%)'."""
    cat = group[0].category
    conf = pct(max(e.confidence for e in group))
    zones = _zones(group)
    if cat == "FOOTSTEPS":
        motion = f"moving {' -> '.join(zones)}" if len(zones) >= 2 else where(zones[0] if zones else "UNKNOWN")
        text = f"footsteps heard {motion} ({conf})"
        return text[0].upper() + text[1:] if first else text
    zone = zones[-1] if zones else "UNKNOWN"
    if first:
        return f"{LEAD.get(cat, cat.title())} heard {where(zone)} ({conf})"
    return f"{PHRASE.get(cat, cat.lower())} {where(zone)} ({conf})"


def summarize(events: list[Event], risk: str, match: Match | None) -> str:
    """One deterministic sentence block for a sequence."""
    evs = sorted(events, key=lambda e: (e.t_start, e.t_end))
    if not evs:
        return ""
    groups = _groups(evs)
    parts = [_describe(groups[0], first=True)]
    if len(groups) > 1:
        gap = max(0.0, groups[1][0].t_start - groups[0][-1].t_end)
        rest = [_describe(g, first=False) for g in groups[1:]]
        follow = rest[0] if len(rest) == 1 else ", ".join(rest[:-1]) + " and " + rest[-1]
        parts.append(f", followed {gap:.1f} s later by {follow}")
    text = f"{clock(evs[0].wall)} - {''.join(parts)}."
    text += f" Pattern: {match.pattern.description}." if match else " Pattern: none."
    return f"{text} {STATUS[risk]}"


def explain(events: list[Event], risk: str, match: Match | None, trajectory: list[str]) -> list[str]:
    """The 'why' list shown next to every sequence."""
    evs = sorted(events, key=lambda e: (e.t_start, e.t_end))
    why: list[str] = []
    for i, e in enumerate(evs):
        gap = "" if i == 0 else f", {max(0.0, e.t_start - evs[i - 1].t_end):.1f} s after the previous event"
        why.append(f"{e.category.title()} ({e.label}) {pct(e.confidence)} {where(e.zone)}{gap}")
    if len(trajectory) >= 2:
        why.append(f"Possible correlated acoustic sequence, moving towards {trajectory[-1]} "
                   f"(possible acoustic trajectory {' -> '.join(trajectory)})")
    if match:
        gaps = f"each step within {match.pattern.max_gap_s:.0f} s"
        why.append(f"Matches pattern {match.pattern.name} ({match.pattern.description}; {gaps}) -> {risk}")
    elif len(evs) == 1:
        why.append("Isolated single event: no correlated pattern, so it is logged without an alert")
    else:
        why.append("Events are close in time but match no known pattern: logged without an alert")
    return why
