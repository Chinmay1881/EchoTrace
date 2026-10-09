"""Graph, patterns, risk engine, baseline and summaries on hand-made events (no audio, no model)."""

import pytest

from echotrace.baseline import BaselineAlerter
from echotrace.correlation.graph import EventGraph
from echotrace.correlation.patterns import match
from echotrace.events import Event
from echotrace.risk.engine import RiskEngine
from echotrace.risk.summary import explain, summarize


def ev(i, cat, t0, t1, zone, conf=0.6, label=None, wall_s=None):
    s = int(t0) if wall_s is None else wall_s
    return Event(f"e{i}", t0, t1, cat, label or cat.title(), conf, zone, None,
                 f"2026-10-09T14:02:{s:02d}.000")


DEMO = [
    ev(1, "FOOTSTEPS", 0.0, 2.0, "LEFT", 0.62, "Walk, footsteps"),
    ev(2, "FOOTSTEPS", 2.0, 4.0, "CENTRE", 0.58, "Walk, footsteps"),
    ev(3, "IMPACT", 5.2, 5.6, "RIGHT", 0.71, "Thump, thud"),
    ev(4, "DISTRESS", 6.4, 7.4, "RIGHT", 0.54, "Screaming"),
]


def build(events):
    g = EventGraph()
    for e in events:
        g.add(e)
    return g


def test_demo_sequence_is_one_red_sequence():
    g = build(DEMO)
    assert len(g.clusters) == 1
    cl = g.clusters[0]
    m = match(cl.events)
    assert m.pattern.name == "MOVEMENT_IMPACT_DISTRESS" and m.pattern.risk == "RED"
    assert [e.id for e in m.events] == ["e1", "e2", "e3", "e4"]
    assert cl.trajectory() == ["LEFT", "CENTRE", "RIGHT"]


def test_demo_explanation_and_summary():
    cl = build(DEMO).clusters[0]
    m = match(cl.events)
    why = explain(cl.events, "RED", m, cl.trajectory())
    assert any("moving towards RIGHT" in w for w in why)
    assert any("MOVEMENT_IMPACT_DISTRESS" in w and "RED" in w for w in why)
    # one line per group of same-category events, each with its confidence
    assert why[:3] == ["Footsteps x2 (Walk, footsteps, max 62%) moving LEFT -> CENTRE",
                       "Impact (Thump, thud) 71% on the RIGHT, 1.2 s after the footsteps",
                       "Distress (Screaming) 54% on the RIGHT, 0.8 s after the impact"]
    s = summarize(cl.events, "RED", m)
    assert s == ("14:02:00 - Footsteps heard moving LEFT -> CENTRE (62%), followed 1.2 s later by an impact on the "
                 "RIGHT (71%) and a possible distress vocalisation on the RIGHT (54%). Pattern: movement -> impact "
                 "-> distress. Status RED: potentially significant sequence - verify.")


def test_summaries_are_deterministic_and_cautious():
    cl = build(DEMO).clusters[0]
    m = match(cl.events)
    runs = {summarize(cl.events, "RED", m) for _ in range(5)}
    assert len(runs) == 1
    text = runs.pop().lower()
    assert "emergency" not in text and "confirmed" not in text and "person" not in text


@pytest.mark.parametrize("cat", ["IMPACT", "DISTRESS", "ALARM", "GLASS", "FOOTSTEPS", "DOOR"])
def test_isolated_single_event_is_green_but_baseline_alerts(cat):
    e = ev(1, cat, 10.0, 10.5, "LEFT")
    cl = build([e]).clusters[0]
    assert match(cl.events) is None
    why = explain(cl.events, "GREEN", None, cl.trajectory())
    assert "Isolated single event" in why[-1]
    base = BaselineAlerter()
    alerted = base.observe(e) is not None
    assert alerted == (cat in ("IMPACT", "DISTRESS", "ALARM", "GLASS"))


def test_false_alert_reduction_on_distractors():
    # lone door slam, lone glass, lone distress far apart in time: baseline 3 alerts, EchoTrace 0
    events = [ev(1, "IMPACT", 0, 0.5, "LEFT"), ev(2, "GLASS", 20, 20.5, "RIGHT"), ev(3, "DISTRESS", 40, 41, "CENTRE")]
    g = build(events)
    assert len(g.clusters) == 3
    assert all(match(c.events) is None for c in g.clusters)
    base = BaselineAlerter()
    assert sum(base.observe(e) is not None for e in events) == 3


def test_gap_longer_than_link_window_starts_new_sequence():
    g = build([ev(1, "FOOTSTEPS", 0, 2, "LEFT"), ev(2, "IMPACT", 11.0, 11.5, "RIGHT")])
    assert len(g.clusters) == 2


@pytest.mark.parametrize("events,name,risk", [
    ([("IMPACT", 0, 0.5), ("DISTRESS", 1.0, 2.0)], "IMPACT_DISTRESS", "AMBER"),
    ([("ALARM", 0, 2), ("FOOTSTEPS", 3, 5), ("FOOTSTEPS", 5, 7)], "ALARM_EVACUATION", "AMBER"),
    ([("GLASS", 0, 0.5), ("FOOTSTEPS", 2, 4)], "GLASS_INTRUSION", "AMBER"),
    ([("FOOTSTEPS", 0, 2), ("DOOR", 2.5, 3), ("IMPACT", 3.5, 4), ("DISTRESS", 4.5, 5)], "MOVEMENT_IMPACT_DISTRESS", "RED"),
])
def test_patterns(events, name, risk):
    evs = [ev(i, c, a, b, "CENTRE") for i, (c, a, b) in enumerate(events)]
    m = match(evs)
    assert m and m.pattern.name == name and m.pattern.risk == risk


@pytest.mark.parametrize("events", [
    [("ALARM", 0, 2), ("FOOTSTEPS", 3, 5)],                      # only one footsteps event
    [("DISTRESS", 0, 1), ("IMPACT", 2, 2.5)],                    # wrong order
    [("FOOTSTEPS", 0, 2), ("IMPACT", 3, 3.5)],                   # incomplete
    [("IMPACT", 0, 0.5), ("DISTRESS", 9.0, 10)],                 # gap > 8 s
    [("FOOTSTEPS", 0, 2), ("FOOTSTEPS", 2, 4), ("DOOR", 5, 5.5)],
])
def test_non_matches(events):
    assert match([ev(i, c, a, b, "CENTRE") for i, (c, a, b) in enumerate(events)]) is None


def seq_of(*spec):
    return [ev(i + 1, c, a, b, "CENTRE") for i, (c, a, b) in enumerate(spec)]


def test_breakin_alarm_found_inside_long_noisy_sequence():
    evs = seq_of(("ALARM", 0, 1),                       # an alarm BEFORE the glass doesn't count
                 ("GLASS", 3, 4), ("GLASS", 5, 6), ("DOOR", 6.5, 7), ("IMPACT", 8, 8.5), ("GLASS", 9, 9.5),
                 ("IMPACT", 12, 12.5), ("FOOTSTEPS", 13, 14), ("ALARM", 26, 28), ("ALARM", 28, 30))
    m = match(evs)
    assert m.pattern.name == "BREAKIN_ALARM" and m.pattern.risk == "RED"
    assert m.completed_by.id == "e9"                    # the first alarm after glass -> impact
    assert [e.category for e in m.events] == ["GLASS", "GLASS", "IMPACT", "IMPACT", "ALARM"]


def test_breakin_alarm_gap_limit_is_15_s():
    assert match(seq_of(("GLASS", 0, 1), ("IMPACT", 15.9, 16), ("ALARM", 30, 31))).pattern.name == "BREAKIN_ALARM"
    m = match(seq_of(("GLASS", 0, 1), ("IMPACT", 16.5, 17), ("ALARM", 30, 31)))
    assert m is None                                    # glass -> impact gap 15.5 s


def test_glass_impact_is_amber_until_alarm():
    m = match(seq_of(("GLASS", 0, 1), ("IMPACT", 3, 3.5)))
    assert m.pattern.name == "GLASS_IMPACT" and m.pattern.risk == "AMBER"


def test_repeats_do_not_confuse_matching():
    # many repeats of every step, in order, all close: still one clean match ending at the first ALARM
    evs = seq_of(*[("GLASS", t, t + 0.5) for t in range(0, 6)],
                 *[("IMPACT", t, t + 0.5) for t in range(6, 12)],
                 *[("ALARM", t, t + 0.5) for t in range(12, 18)])
    m = match(evs)
    assert m.pattern.name == "BREAKIN_ALARM" and m.completed_by.id == "e13"


def test_pattern_config_is_validated():
    from echotrace.correlation.patterns import load_patterns
    with pytest.raises(ValueError, match="unknown categories"):
        load_patterns([{"name": "X", "steps": [("GLAS", 1)], "risk": "RED", "description": "x"}])
    with pytest.raises(ValueError, match="risk"):
        load_patterns([{"name": "X", "steps": [("GLASS", 1)], "risk": "PURPLE", "description": "x"}])


def test_highest_priority_pattern_wins():
    # FOOTSTEPS -> IMPACT -> DISTRESS contains IMPACT -> DISTRESS; the RED one must win
    assert match(DEMO).pattern.name == "MOVEMENT_IMPACT_DISTRESS"


def test_risk_engine_decay():
    r = RiskEngine(decay_s=20)
    assert r.current(0) == "GREEN"
    r.update("s1", "RED", 2.0)
    r.update("s2", "AMBER", 10.0)
    assert r.current(15) == "RED"
    assert r.current(23) == "AMBER"       # RED's last event 21 s ago -> decayed; AMBER 13 s ago
    assert r.current(31) == "GREEN"


def test_trajectory_skips_unknown_and_repeats():
    g = build([ev(1, "FOOTSTEPS", 0, 1, "LEFT"), ev(2, "FOOTSTEPS", 1, 2, "UNKNOWN"),
               ev(3, "FOOTSTEPS", 2, 3, "LEFT"), ev(4, "IMPACT", 3, 3.5, "RIGHT")])
    assert g.clusters[0].trajectory() == ["LEFT", "RIGHT"]
