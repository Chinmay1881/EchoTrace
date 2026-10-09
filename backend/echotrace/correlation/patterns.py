"""Ordered pattern templates (defined in config.PATTERNS) matched over a sequence of events.

Matching finds an ordered subsequence anywhere inside a long, growing sequence:
- each step is (category, min events); repeats of the current step's category are absorbed into it,
- unrelated events (and repeats of earlier steps) may be interleaved,
- consecutive matched events must be within the pattern's max gap.
It reports the event that COMPLETED the match (the moment the alert fires). The first pattern in
priority order that matches wins. A sequence that matches nothing is GREEN: logged, no alert - this is
EchoTrace's false-alert reduction compared with a classifier that alerts on every concerning label.
"""

from __future__ import annotations

from dataclasses import dataclass

from echotrace import config
from echotrace.events import Event

RISK_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}


@dataclass(frozen=True)
class Pattern:
    name: str
    steps: tuple[tuple[str, int], ...]     # (category, min events)
    risk: str
    description: str                       # plain words, used in summaries
    max_gap_s: float = config.PATTERN_MAX_GAP_S


def load_patterns(spec: list[dict] = config.PATTERNS,
                  categories: dict[str, list[str]] = config.CATEGORIES) -> list[Pattern]:
    """Build and validate the editable pattern list from config (fails loudly on typos)."""
    out = []
    for p in spec:
        steps = tuple((c, int(n)) for c, n in p["steps"])
        bad = [c for c, _ in steps if c not in categories]
        if bad:
            raise ValueError(f"pattern {p['name']}: unknown categories {bad}; known: {list(categories)}")
        if p["risk"] not in ("AMBER", "RED"):
            raise ValueError(f"pattern {p['name']}: risk must be AMBER or RED")
        if not steps or any(n < 1 for _, n in steps):
            raise ValueError(f"pattern {p['name']}: needs steps with min count >= 1")
        out.append(Pattern(p["name"], steps, p["risk"], p["description"],
                           float(p.get("max_gap_s", config.PATTERN_MAX_GAP_S))))
    return out


PATTERNS: list[Pattern] = load_patterns()


@dataclass
class Match:
    pattern: Pattern
    events: list[Event]                    # the matched chain, in time order, ending at the completing event

    @property
    def completed_by(self) -> Event:
        return self.events[-1]


@dataclass
class _Partial:
    step: int
    count: int
    last_end: float
    chain: list[Event]


def match_pattern(events: list[Event], pat: Pattern) -> Match | None:
    """Earliest completion of `pat` in the time-ordered events, or None."""
    evs = sorted(events, key=lambda e: (e.t_start, e.t_end))
    last = len(pat.steps) - 1
    partials: list[_Partial] = []
    for ev in evs:
        nxt: list[_Partial] = []
        for s in partials:
            if ev.t_start - s.last_end > pat.max_gap_s:
                continue                                    # chain went cold; it can never resume
            cat, need = pat.steps[s.step]
            if ev.category == cat:                          # repeat of the current step: absorb it
                nxt.append(_Partial(s.step, s.count + 1, max(s.last_end, ev.t_end), s.chain + [ev]))
            elif s.count >= need and s.step < last and ev.category == pat.steps[s.step + 1][0]:
                nxt.append(_Partial(s.step + 1, 1, ev.t_end, s.chain + [ev]))
                nxt.append(s)                               # also keep waiting at this step
            else:
                nxt.append(s)                               # unrelated / earlier-step event: ignore
        if ev.category == pat.steps[0][0]:
            nxt.append(_Partial(0, 1, ev.t_end, [ev]))
        for s in nxt:
            if s.step == last and s.count >= pat.steps[last][1] and s.chain[-1] is ev:
                return Match(pat, s.chain)
        # keep the most permissive partial per (step, satisfied-count) so repeats can't blow up the search
        best: dict[tuple[int, int], _Partial] = {}
        for s in nxt:
            key = (s.step, min(s.count, pat.steps[s.step][1]))
            if key not in best or s.last_end > best[key].last_end:
                best[key] = s
        partials = list(best.values())
    return None


def match(events: list[Event], patterns: list[Pattern] | None = None) -> Match | None:
    """Highest-priority pattern that occurs anywhere in the sequence."""
    for pat in (patterns if patterns is not None else PATTERNS):
        m = match_pattern(events, pat)
        if m:
            return m
    return None
