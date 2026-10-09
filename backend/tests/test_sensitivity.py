import pytest

from echotrace import config
from echotrace.audio.sources import SimSource
from echotrace.detection.debounce import Debouncer
from echotrace.pipeline import Pipeline
from echotrace.schemas import validate


def test_profiles():
    assert config.thresholds("GLASS", "normal") == (0.30, 0.15)
    assert config.thresholds("IMPACT", "normal") == (0.20, 0.10)
    for cat in ("GLASS", "ALARM", "FOOTSTEPS", "DISTRESS", "DOOR"):
        assert config.thresholds(cat, "high") == (0.20, 0.10)
    assert config.thresholds("IMPACT", "high") == (0.12, 0.06)
    for mode in config.SENSITIVITY_PROFILES:
        for cat in config.CATEGORIES:
            on, off = config.thresholds(cat, mode)
            assert 0 < off < on < 1
    assert config.tagger_gain_db("high") == config.tagger_gain_db("normal") == config.TAGGER_GAIN_DB


def test_set_sensitivity_validates_and_switches():
    with pytest.raises(ValueError):
        config.set_sensitivity("extreme")
    config.set_sensitivity("high")
    assert config.thresholds("GLASS") == (0.20, 0.10)


def test_high_opens_on_weaker_sounds_but_not_on_speech_level_scores():
    def run(mode, score):
        config.set_sensitivity(mode)
        d = Debouncer(["GLASS"], 0.5)
        return d.update(0.5, {"GLASS": score}, {"GLASS": "Glass"}) + d.update(1.0, {"GLASS": 0.0}, {}) + d.flush()

    assert run("normal", 0.25) == [] and len(run("high", 0.25)) == 1
    assert run("high", 0.03) == []        # max speech/silence category score seen in the logged runs


def test_status_reports_active_sensitivity():
    config.set_sensitivity("high")
    msgs = Pipeline(SimSource(realtime=False, loops=1, scenario="demo")).run_to_end()
    statuses = [m for m in msgs if m["type"] == "status"]
    for m in statuses:
        validate(m)
    assert {m["data"]["sensitivity"] for m in statuses} == {"high"}
