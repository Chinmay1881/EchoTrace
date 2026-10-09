from echotrace.detection.debounce import Debouncer

HOP = 0.5
THR = lambda c: (0.30, 0.15)  # noqa: E731


def run(scores, cat="IMPACT", **kw):
    d = Debouncer([cat], HOP, thresholds=THR, **kw)
    events = []
    for i, p in enumerate(scores):
        t = (i + 1) * HOP
        events += d.update(t, {cat: p}, {cat: f"label@{t}"})
    return events + d.flush()


def test_single_hop_opens_and_closes():
    ev = run([0.0, 0.5, 0.0, 0.0])
    assert len(ev) == 1
    e = ev[0]
    assert (e.t_start, e.t_end) == (0.5, 1.0)
    assert e.confidence == 0.5 and e.label == "label@1.0"


def test_hysteresis_merges_dip_between_on_and_off():
    # 0.2 is below ON but above OFF: the event stays open -> one merged event
    ev = run([0.6, 0.2, 0.7, 0.0])
    assert len(ev) == 1
    assert ev[0].confidence == 0.7 and (ev[0].t_start, ev[0].t_end) == (0.0, 1.5)


def test_drop_below_off_splits():
    ev = run([0.6, 0.05, 0.7, 0.0])
    assert len(ev) == 2
    assert [round(e.confidence, 2) for e in ev] == [0.6, 0.7]


def test_below_on_never_opens():
    assert run([0.29, 0.25, 0.2, 0.29]) == []


def test_n_of_m():
    # needs 2 of the last 3 hops >= ON
    assert run([0.4, 0.0, 0.0, 0.0], on_n=2, on_m=3) == []
    ev = run([0.4, 0.0, 0.4, 0.0, 0.0], on_n=2, on_m=3)
    assert len(ev) == 1


def test_long_sound_is_split_into_pieces_without_tail_events():
    # 3 s of footsteps, then a fading tail below ON
    ev = run([0.6] * 6 + [0.2, 0.0], cat="FOOTSTEPS", max_event_s=2.0)
    assert [(e.t_start, e.t_end) for e in ev] == [(0.0, 2.0), (2.0, 3.5)]   # 0.2 >= OFF keeps it open
    # split exactly at 2.0 s, then only a fading tail (never back above ON): no extra event
    ev = run([0.6] * 4 + [0.2, 0.0], cat="FOOTSTEPS", max_event_s=2.0)
    assert [(e.t_start, e.t_end) for e in ev] == [(0.0, 2.0)]


def test_flush_closes_open_event():
    d = Debouncer(["ALARM"], HOP, thresholds=THR)
    assert d.update(0.5, {"ALARM": 0.9}, {"ALARM": "Alarm"}) == []
    ev = d.flush()
    assert len(ev) == 1 and ev[0].category == "ALARM"


def test_per_category_thresholds_from_config():
    d = Debouncer(["IMPACT", "GLASS"], HOP)          # config: IMPACT on 0.20, GLASS 0.30
    out = d.update(0.5, {"IMPACT": 0.22, "GLASS": 0.22}, {}) + d.update(1.0, {"IMPACT": 0.0, "GLASS": 0.0}, {})
    assert [e.category for e in out] == ["IMPACT"]
