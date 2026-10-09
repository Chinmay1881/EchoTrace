"""TDOA lag -> angle -> LEFT / CENTRE / RIGHT zone, using the calibration (sign/offset) for this laptop.

Approximate zones only: a 2-mic array cannot tell front from back, and 6.5 cm spacing gives coarse angles.
Convention for everything after calibration: corrected lag > 0 and angle_deg > 0 mean RIGHT.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from echotrace import config
from echotrace.localization.gcc_phat import frame_lags, lag_to_angle


@dataclass
class Calibration:
    sign: int = config.DEFAULT_CAL_SIGN
    offset_samples: float = config.DEFAULT_CAL_OFFSET
    source: str = "default (guided runs #2/#3)"

    def correct(self, raw_lag: float) -> float:
        return self.sign * (raw_lag - self.offset_samples)

    def save(self, path: Path = config.CALIBRATION_FILE, **extra) -> None:
        path.write_text(json.dumps({**asdict(self), **extra}, indent=2), encoding="utf-8")


def load_calibration(path: Path = config.CALIBRATION_FILE) -> Calibration:
    if not path.exists():
        return Calibration()
    d = json.loads(path.read_text(encoding="utf-8"))
    sign = int(d.get("sign", config.DEFAULT_CAL_SIGN))
    if sign not in (-1, 1):
        raise ValueError(f"{path}: sign must be -1 or +1, got {sign}")
    return Calibration(sign, float(d.get("offset_samples", 0.0)), f"calibration file {path.name}")


def angle_to_zone(angle_deg: float, centre_half: float = config.CENTRE_HALF_ANGLE_DEG) -> str:
    if abs(angle_deg) < centre_half:
        return "CENTRE"
    return "RIGHT" if angle_deg > 0 else "LEFT"


@dataclass
class Localization:
    zone: str                  # LEFT | CENTRE | RIGHT | UNKNOWN
    angle_deg: float | None
    confidence: float          # winning vote share x mean GCC peak, 0..1
    frames: int
    reason: str = ""


class ZoneLocalizer:
    """Swappable localizer interface: localize(stereo segment) -> Localization."""

    def __init__(self, calibration: Calibration | None = None, rate: int = config.CAPTURE_RATE):
        self.cal = calibration or load_calibration()
        self.rate = rate

    def localize(self, stereo: np.ndarray) -> Localization:
        lags = frame_lags(stereo, self.rate)
        if not lags:
            return Localization("UNKNOWN", None, 0.0, 0, "no usable audio frames")
        votes: dict[str, float] = {}
        per_zone: dict[str, list[tuple[float, float]]] = {}
        for raw, peak in lags:
            ang = lag_to_angle(self.cal.correct(raw), self.rate)
            z = angle_to_zone(ang)
            votes[z] = votes.get(z, 0.0) + max(peak, 1e-6)
            per_zone.setdefault(z, []).append((ang, peak))
        total = sum(votes.values())
        zone = max(votes, key=votes.get)
        share = votes[zone] / total
        angs = [a for a, _ in per_zone[zone]]
        mean_peak = float(np.mean([p for _, p in per_zone[zone]]))
        angle = float(np.median(angs))
        conf = float(share * min(1.0, mean_peak))
        if share < config.LOC_MIN_VOTE:
            return Localization("UNKNOWN", angle, conf, len(lags), f"frames disagree ({share:.0%} for {zone})")
        if mean_peak < config.LOC_MIN_PEAK:
            return Localization("UNKNOWN", angle, conf, len(lags), f"weak GCC-PHAT peak ({mean_peak:.2f})")
        return Localization(zone, round(angle, 1), round(conf, 3), len(lags),
                            f"{len(per_zone[zone])}/{len(lags)} frames vote {zone}")
