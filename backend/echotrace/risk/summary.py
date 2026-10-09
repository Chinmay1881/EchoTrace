"""Deterministic, template-based plain-language summaries and "why" lists. No generative model.

Wording rules: RED is a "potentially significant sequence", never a confirmed emergency; movement is a
"possible acoustic trajectory", never a tracked person; every event carries its confidence.
"""

from __future__ import annotations

from echotrace.correlation.graph import group_zone_is_low, group_zones, groups
from echotrace.correlation.patterns import Match
from echotrace.events import Event

PHRASE = {   # mid-sentence form
    "FOOTSTEPS": "footsteps",
    "IMPACT": "an impact",
    "DISTRESS": "a possible distress vocalisation",
    "ALARM": "an alarm",
    "GLASS": "breaking glass",
    "DOOR": "a door sound",
}
LEAD = {     # sentence-initial form
    "IMPACT": "Impact",
    "DISTRESS": "Possible distress vocalisation",
    "ALARM": "Alarm",
    "GLASS": "Breaking glass",
    "DOOR": "Door sound",
}
NOUN = {     # short name used in "x s after the ..."
    "FOOTSTEPS": "footsteps", "IMPACT": "impact", "DISTRESS": "distress", "ALARM": "alarm",
    "GLASS": "glass", "DOOR": "door sound",
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
    """'2026-10-09T14:02:11.250' -> '14:02:11'."""
    return wall[11:19] if len(wall) >= 19 else wall


def _place(group: list[Event]) -> str:
    zones = group_zones(group)
    if group[0].category == "FOOTSTEPS" and len(zones) >= 2:
        return f"moving {' -> '.join(zones)}"
    text = where(zones[0] if zones else "UNKNOWN")
    if zones and group[0].category != "FOOTSTEPS" and group_zone_is_low(group):
        text += " (low-confidence direction)"
    return text


def _describe(group: list[Event], first: bool) -> str:
    """'Footsteps heard moving LEFT -> CENTRE (62%)' / 'an impact on the RIGHT (71%)'."""
    cat = group[0].category
    conf = pct(max(e.confidence for e in group))
    if cat == "FOOTSTEPS":
        return f"{'Footsteps' if first else 'footsteps'} heard {_place(group)} ({conf})"
    if first:
        return f"{LEAD.get(cat, cat.title())} heard {_place(group)} ({conf})"
    return f"{PHRASE.get(cat, cat.lower())} {_place(group)} ({conf})"


def summarize(events: list[Event], risk: str, match: Match | None) -> str:
    """One deterministic sentence block for a sequence."""
    gs = groups(events)
    if not gs:
        return ""
    parts = [_describe(gs[0], first=True)]
    if len(gs) > 1:
        gap = max(0.0, gs[1][0].t_start - gs[0][-1].t_end)
        rest = [_describe(g, first=False) for g in gs[1:]]
        follow = rest[0] if len(rest) == 1 else ", ".join(rest[:-1]) + " and " + rest[-1]
        parts.append(f", followed {gap:.1f} s later by {follow}")
    text = f"{clock(gs[0][0].wall)} - {''.join(parts)}."
    text += f" Pattern: {match.pattern.description}." if match else " Pattern: none."
    return f"{text} {STATUS[risk]}"


def _why_group(group: list[Event], prev: list[Event] | None) -> str:
    cat = group[0].category
    best = max(group, key=lambda e: e.confidence)
    name = cat.title()
    if len(group) == 1:
        line = f"{name} ({best.label}) {pct(best.confidence)} {_place(group)}"
    else:
        line = f"{name} x{len(group)} ({best.label}, max {pct(best.confidence)}) {_place(group)}"
    if prev is not None:
        gap = max(0.0, group[0].t_start - prev[-1].t_end)
        line += f", {gap:.1f} s after the {NOUN.get(prev[0].category, prev[0].category.lower())}"
    return line


def explain(events: list[Event], risk: str, match: Match | None, trajectory: list[str],
            fired_at: str | None = None, later_events: int = 0) -> list[str]:
    """The 'why' list shown next to every sequence: what was heard, where, how it links, why this risk."""
    gs = groups(events)
    why = [_why_group(g, gs[i - 1] if i else None) for i, g in enumerate(gs)]
    if len(trajectory) >= 2:
        why.append(f"Possible correlated acoustic sequence, moving towards {trajectory[-1]} "
                   f"(possible acoustic trajectory {' -> '.join(trajectory)})")
    if match:
        line = (f"Matches pattern {match.pattern.name} ({match.pattern.description}; each step within "
                f"{match.pattern.max_gap_s:.0f} s) -> {risk}")
        if fired_at:
            line += f", alert raised at {fired_at}"
        why.append(line)
        if later_events:
            why.append(f"{later_events} later event(s) added to this sequence without a new alert")
    elif len(events) == 1:
        why.append("Isolated single event: no correlated pattern, so it is logged without an alert")
    else:
        why.append("Events are close in time but match no known pattern: logged without an alert")
    return why
