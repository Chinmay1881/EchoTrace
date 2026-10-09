"""GCC-PHAT zones at d = 6.5 cm: synthetic events with known delays -> LEFT / CENTRE / RIGHT."""

import json

import numpy as np
import pytest

from echotrace.localization.gcc_phat import frame_lags, lag_to_angle, max_lag_samples
from echotrace.localization.zones import Calibration, ZoneLocalizer, angle_to_zone, load_calibration

SR = 48000
RNG = np.random.default_rng(3)


def frac_delay(x, d):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x))
    return np.fft.irfft(X * np.exp(-2j * np.pi * f * d), len(x))


def event_audio(raw_lag, kind="burst", seconds=1.5, snr_db=25, seed=0):
    """Quiet independent room noise + a loud event whose right channel lags the left by raw_lag samples."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    src = np.zeros(n)
    if kind == "burst":
        a, b = int(0.5 * SR), int(0.8 * SR)
        src[a:b] = rng.standard_normal(b - a)
    else:  # clicks (knocks)
        for pos in (0.4, 0.7, 1.0):
            i = int(pos * SR)
            src[i:i + 300] = rng.standard_normal(300) * np.exp(-np.arange(300) / 40)
    left, right = src, frac_delay(src, raw_lag)
    noise = 10 ** (-snr_db / 20) * np.std(src[src != 0]) * rng.standard_normal((n, 2))
    return (np.stack([left, right], 1) + noise).astype(np.float32)


# Default calibration: raw positive lag (right channel later) = LEFT (measured in guided runs)
CAL = Calibration(sign=-1, offset_samples=0.0)


@pytest.mark.parametrize("kind", ["burst", "clicks"])
@pytest.mark.parametrize("raw_lag,zone", [(7.0, "LEFT"), (5.3, "LEFT"), (0.0, "CENTRE"), (1.4, "CENTRE"),
                                          (-2.2, "CENTRE"), (-4.6, "RIGHT"), (-8.1, "RIGHT")])
def test_zone_from_known_delay(kind, raw_lag, zone):
    loc = ZoneLocalizer(CAL).localize(event_audio(raw_lag, kind))
    assert loc.zone == zone, loc
    expected = lag_to_angle(CAL.correct(raw_lag))
    assert loc.angle_deg == pytest.approx(expected, abs=4.0)


def test_energy_gating_ignores_quiet_background_source():
    # a steady quiet talker on the LEFT, a loud event on the RIGHT -> RIGHT wins
    rng = np.random.default_rng(9)
    n = int(1.5 * SR)
    bg = 0.05 * rng.standard_normal(n)
    audio = event_audio(-7.0, "burst", snr_db=40)
    audio += np.stack([bg, frac_delay(bg, 7.0)], 1).astype(np.float32)
    assert ZoneLocalizer(CAL).localize(audio).zone == "RIGHT"


def test_identical_channels_are_centre_not_side():
    x = event_audio(0.0)
    x[:, 1] = x[:, 0]
    loc = ZoneLocalizer(CAL).localize(x)
    assert loc.zone in ("CENTRE", "UNKNOWN")


def test_uncorrelated_channels_give_unknown():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((int(1.5 * SR), 2)).astype(np.float32)
    x[int(0.5 * SR):int(0.8 * SR)] *= 20      # loud but incoherent between channels
    assert ZoneLocalizer(CAL).localize(x).zone == "UNKNOWN"


@pytest.mark.parametrize("seed", range(12))
def test_incoherent_noise_is_unknown_for_any_seed(seed):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((int(1.5 * SR), 2)).astype(np.float32)
    x[int(0.5 * SR):int(0.8 * SR)] *= 20
    loc = ZoneLocalizer(CAL).localize(x)
    assert loc.zone == "UNKNOWN" and loc.zone_confidence is None


@pytest.mark.parametrize("votes,expect", [
    ([(7.0, 0.5)] * 10, ("LEFT", "high")),                                   # unanimous
    ([(7.0, 0.5)] * 5 + [(-7.0, 0.5)] * 4 + [(0.0, 0.5)], ("LEFT", "low")),  # 50% LEFT: best guess
    ([(7.0, 0.5)] * 3 + [(-7.0, 0.5)] * 4 + [(0.0, 0.5)] * 3, ("RIGHT", "low")),  # 40%: still a guess
    ([(7.0, 0.5)] * 3 + [(-7.0, 0.5)] * 3 + [(0.0, 0.5)] * 3, ("UNKNOWN", None)),  # 33%: no usable majority
    ([(7.0, 0.15)] * 10, ("UNKNOWN", None)),                                 # unanimous but noise-level peaks
])
def test_confidence_tiers(monkeypatch, votes, expect):
    from echotrace.localization import zones
    monkeypatch.setattr(zones, "frame_lags", lambda *a, **k: votes)
    loc = ZoneLocalizer(CAL).localize(np.zeros((SR, 2), np.float32))
    assert (loc.zone, loc.zone_confidence) == expect, loc


def test_low_tier_can_be_disabled(monkeypatch):
    from echotrace import config
    from echotrace.localization import zones
    monkeypatch.setattr(zones, "frame_lags", lambda *a, **k: [(7.0, 0.5)] * 5 + [(-7.0, 0.5)] * 5)
    monkeypatch.setattr(config, "LOC_LOW_VOTE", None)
    assert ZoneLocalizer(CAL).localize(np.zeros((SR, 2), np.float32)).zone == "UNKNOWN"


def test_clear_event_is_high_confidence():
    loc = ZoneLocalizer(CAL).localize(event_audio(-7.0))
    assert (loc.zone, loc.zone_confidence) == ("RIGHT", "high")


def test_silence_gives_unknown():
    loc = ZoneLocalizer(CAL).localize(np.zeros((SR, 2), np.float32))
    assert loc.zone == "UNKNOWN" and loc.angle_deg is None


def test_frame_lags_respect_physical_limit():
    lags = frame_lags(event_audio(7.0), SR)
    assert lags and all(abs(l) <= max_lag_samples() + 1e-9 for l, _ in lags)


def test_angle_to_zone_boundaries():
    assert angle_to_zone(0) == "CENTRE"
    assert angle_to_zone(19.9) == "CENTRE" and angle_to_zone(-19.9) == "CENTRE"
    assert angle_to_zone(20.1) == "RIGHT" and angle_to_zone(-20.1) == "LEFT"


def test_calibration_sign_and_offset(tmp_path):
    cal = Calibration(sign=1, offset_samples=1.0)
    assert cal.correct(4.0) == 3.0
    p = tmp_path / "cal.json"
    cal.save(p, left_lag=-6.0)
    assert json.loads(p.read_text())["left_lag"] == -6.0
    back = load_calibration(p)
    assert (back.sign, back.offset_samples) == (1, 1.0)
    # flipped sign flips the zone
    audio = event_audio(-7.0)
    assert ZoneLocalizer(Calibration(-1, 0)).localize(audio).zone == "RIGHT"
    assert ZoneLocalizer(Calibration(1, 0)).localize(audio).zone == "LEFT"


def test_good_calibration_accepted():
    from echotrace.localization.zones import calibration_from_measurements
    cal, problems = calibration_from_measurements(7.2, 0.6, -7.8, 0.5, centre=-0.4, centre_sd=0.8)
    assert problems == [] and cal.sign == -1 and cal.offset_samples == pytest.approx(-0.3)


@pytest.mark.parametrize("args,reason", [
    ((8.134, 7.716, -8.601, 6.58, -0.552, None), "spread too much"),   # the 12:30 calibration.json
    ((6.0, 0.5, 2.0, 0.5, None, None), "not on opposite sides"),
    ((1.5, 0.5, -1.0, 0.5, None, None), "separation"),
    ((8.0, 0.5, -3.0, 0.5, None, None), "offset"),
    ((7.0, 0.5, -7.0, 0.5, 4.5, 0.5), "CENTRE check reads LEFT"),
])
def test_bad_calibration_refused(args, reason):
    from echotrace.localization.zones import calibration_from_measurements
    _, problems = calibration_from_measurements(*args)
    assert any(reason in p for p in problems), problems


def test_missing_calibration_file_uses_default(tmp_path):
    cal = load_calibration(tmp_path / "nope.json")
    assert cal.sign == -1 and "default" in cal.source


def test_bad_calibration_sign_rejected(tmp_path):
    p = tmp_path / "cal.json"
    p.write_text('{"sign": 0}')
    with pytest.raises(ValueError):
        load_calibration(p)
