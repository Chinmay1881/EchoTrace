"""End-to-end pipeline: SIMULATED scenario, and RECORDED WAVs through the real audio path with a fake tagger."""

from datetime import datetime

import numpy as np
import pytest
import soundfile as sf

from echotrace import config
from echotrace.audio.sources import SimSource, WavReplaySource
from echotrace.localization.zones import Calibration, ZoneLocalizer
from echotrace.pipeline import Pipeline
from echotrace.schemas import validate

SR = 48000
START = datetime(2026, 10, 9, 14, 2, 0)


def by_type(msgs, kind):
    return [m["data"] for m in msgs if m["type"] == kind]


def final_sequences(msgs):
    out = {}
    for s in by_type(msgs, "sequence"):
        out[s["id"]] = s
    return out


# ------------------------------------------------------------------ SIMULATED
@pytest.fixture(scope="module")
def sim_msgs():
    return Pipeline(SimSource(realtime=False, loops=1, scenario="demo"), start_wall=START).run_to_end()


def test_sim_messages_follow_contract_and_are_labelled(sim_msgs):
    for m in sim_msgs:
        validate(m)
        assert m["data"]["source"] == "SIMULATED"
    kinds = {m["type"] for m in sim_msgs}
    assert kinds == {"frame", "event", "sequence", "status"}


def test_sim_demo_is_one_red_sequence_and_distractors_green(sim_msgs):
    seqs = final_sequences(sim_msgs)
    red = [s for s in seqs.values() if s["risk"] == "RED"]
    assert len(red) == 1
    s = red[0]
    assert s["pattern"] == "MOVEMENT_IMPACT_DISTRESS"
    assert s["trajectory"] == ["LEFT", "CENTRE", "RIGHT"]
    assert "moving towards RIGHT" in " ".join(s["explanation"])
    assert s["summary"].startswith("14:02:23 - Footsteps heard moving LEFT -> CENTRE")
    greens = [x for x in seqs.values() if x["risk"] == "GREEN"]
    assert {x["pattern"] for x in greens} == {"ISOLATED_EVENT"} and len(greens) == 2


def test_sim_status_reports_red_then_decays():
    src = SimSource(realtime=False, loops=2, scenario="demo")
    msgs = Pipeline(src, start_wall=START).run_to_end()
    risks = [(s["t"], s["risk"]) for s in by_type(msgs, "status")]
    red_end = max(t for t, r in risks if r == "RED" and t < src.loop_s)
    # quiet tail of the loop: back to GREEN after RISK_DECAY_S, before the scenario repeats
    assert red_end < 31.5 + config.RISK_DECAY_S + 1.5
    assert any(r == "GREEN" for t, r in risks if red_end < t < src.loop_s)
    assert any(r == "RED" for t, r in risks if t > src.loop_s)        # and the second loop goes RED again


def test_sim_baseline_alerts_more_than_echotrace():
    p = Pipeline(SimSource(realtime=False, loops=1, scenario="demo"), start_wall=START)
    msgs = p.run_to_end()
    echo_alerts = [s for s in final_sequences(msgs).values() if s["risk"] != "GREEN"]
    assert len(p.analyzer.baseline.alerts) > len(echo_alerts) == 1


def test_sim_breakin_scenario_amber_then_red():
    p = Pipeline(SimSource(realtime=False, loops=1, scenario="breakin"), start_wall=START)
    msgs = p.run_to_end()
    seqs = final_sequences(msgs)
    assert len(seqs) == 1
    s = next(iter(seqs.values()))
    assert (s["risk"], s["pattern"]) == ("RED", "BREAKIN_ALARM")
    assert s["trajectory"] == ["LEFT", "RIGHT", "CENTRE"]
    assert [(a["risk"], a["pattern"]) for a in p.analyzer.alerts] == [("AMBER", "GLASS_IMPACT"), ("RED", "BREAKIN_ALARM")]
    first_alarm = next(e for e in by_type(msgs, "event") if e["category"] == "ALARM")
    assert p.analyzer.alerts[-1]["event_id"] == first_alarm["id"]
    assert any("alert raised at" in w for w in s["explanation"])


def test_sim_all_plays_both_scenarios_with_decay_between():
    src = SimSource(realtime=False, loops=1)                  # default scenario "all"
    msgs = Pipeline(src, start_wall=START).run_to_end()
    reds = {s["pattern"] for s in final_sequences(msgs).values() if s["risk"] == "RED"}
    assert reds == {"MOVEMENT_IMPACT_DISTRESS", "BREAKIN_ALARM"}
    risks = [(s["t"], s["risk"]) for s in by_type(msgs, "status")]
    assert any(r == "GREEN" for t, r in risks if 55 < t < 62)  # demo RED has decayed before break-in starts


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        SimSource(scenario="nope")


# ------------------------------------------------------------------ RECORDED (real audio path, fake tagger)
class FakeTagger:
    """Swappable Tagger: 'hears' a thud whenever the window is loud. Proves the interface + audio path."""
    device = "cpu"

    def __init__(self):
        from echotrace.tagging.categories import load_labels
        self.labels = load_labels()
        self.i = self.labels.index("Thump, thud")
        self.last_ms = 0.1

    def tag(self, window):
        probs = np.full(len(self.labels), 0.01, dtype=np.float32)
        newest = window[-SR // 2:]
        rms_db = 20 * np.log10(np.sqrt(np.mean(newest.astype(np.float64) ** 2)) + 1e-12)
        if rms_db > -30:
            probs[self.i] = 0.8
        return probs


def frac_delay(x, d):
    X = np.fft.rfft(x)
    return np.fft.irfft(X * np.exp(-2j * np.pi * np.fft.rfftfreq(len(x)) * d), len(x))


def write_clip(path, raw_lag, mono=False, seed=0):
    rng = np.random.default_rng(seed)
    n = 4 * SR
    src = np.zeros(n)
    a = int(1.6 * SR)
    src[a:a + int(0.25 * SR)] = 0.3 * rng.standard_normal(int(0.25 * SR))
    noise = 0.001 * rng.standard_normal((n, 2))
    x = np.stack([src, frac_delay(src, raw_lag)], 1) + noise
    sf.write(path, x[:, :1] if mono else x, SR, subtype="PCM_24")


needs_labels = pytest.mark.skipif(not config.LABELS_FILE.exists(), reason="label CSV missing")


@needs_labels
@pytest.mark.parametrize("raw_lag,zone", [(7.0, "LEFT"), (0.0, "CENTRE"), (-7.0, "RIGHT")])
def test_wav_replay_localizes_event(tmp_path, monkeypatch, raw_lag, zone):
    path = tmp_path / "clip.wav"
    write_clip(path, raw_lag)
    p = Pipeline(WavReplaySource(path, realtime=False), tagger=FakeTagger(), start_wall=START)
    p.analyzer.localizer = ZoneLocalizer(Calibration(-1, 0.0))
    msgs = p.run_to_end()
    for m in msgs:
        validate(m)
        assert m["data"]["source"] == "RECORDED"
    events = by_type(msgs, "event")
    assert len(events) == 1
    e = events[0]
    assert e["category"] == "IMPACT" and e["label"] == "Thump, thud" and e["zone"] == zone
    assert 1.0 <= e["t_start"] <= 2.0
    assert by_type(msgs, "status")[-1]["localization"] == "ON"
    seq = final_sequences(msgs)
    assert [s["risk"] for s in seq.values()] == ["GREEN"]           # isolated impact: logged, no alert
    assert len(p.analyzer.baseline.alerts) == 1                     # ...but the baseline alerts


@needs_labels
def test_mono_wav_turns_localization_off(tmp_path):
    path = tmp_path / "mono.wav"
    write_clip(path, 0.0, mono=True)
    p = Pipeline(WavReplaySource(path, realtime=False), tagger=FakeTagger(), start_wall=START)
    msgs = p.run_to_end()
    statuses = by_type(msgs, "status")
    assert statuses[-1]["localization"] == "OFF" and statuses[-1]["channels"] == 1
    events = by_type(msgs, "event")
    assert len(events) == 1 and events[0]["zone"] == "UNKNOWN" and events[0]["angle_deg"] is None
    assert events[0]["category"] == "IMPACT"                        # classification still works


@needs_labels
def test_identical_stereo_channels_turn_localization_off(tmp_path):
    path = tmp_path / "dual_mono.wav"
    rng = np.random.default_rng(0)
    m = 0.02 * rng.standard_normal(4 * SR)
    m[int(1.6 * SR):int(1.85 * SR)] *= 15
    sf.write(path, np.stack([m, m], 1), SR, subtype="PCM_24")       # what WASAPI/MME voice processing gives
    p = Pipeline(WavReplaySource(path, realtime=False), tagger=FakeTagger(), start_wall=START)
    msgs = p.run_to_end()
    assert by_type(msgs, "status")[-1]["localization"] == "OFF"
    assert all(e["zone"] == "UNKNOWN" for e in by_type(msgs, "event"))


@needs_labels
def test_realtime_replay_paces_and_reports_latency(tmp_path):
    path = tmp_path / "clip.wav"
    write_clip(path, 7.0)
    p = Pipeline(WavReplaySource(path, realtime=True), tagger=FakeTagger(), start_wall=START)
    import time
    t0 = time.monotonic()
    msgs = p.run_to_end()
    took = time.monotonic() - t0
    assert 3.5 < took < 6.0                                          # 4 s file, real-time paced
    assert p.analyzer.latencies and all(0 <= l < 500 for l in p.analyzer.latencies)
    assert by_type(msgs, "status")[-1]["latency_ms"] == p.analyzer.last_latency
