"""Calibrate LEFT/RIGHT for this laptop's mic pair: make sounds on the LEFT, then the RIGHT (then CENTRE).

Saves backend/calibration.json with the sign (which raw lag polarity means LEFT) and the offset
(the midpoint between the two sides, absorbing small channel asymmetries).

  python scripts/calibrate_direction.py                 # LEFT, RIGHT, CENTRE check, 6 s each
  python scripts/calibrate_direction.py --seconds 8 --no-centre

Clap, knock, or play a clip from the phone ~1 m to the side, roughly level with the laptop.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import numpy as np

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.audio.sources import LiveMicSource
from echotrace.localization.gcc_phat import frame_lags, lag_to_angle, max_lag_samples
from echotrace.localization.zones import Calibration, angle_to_zone

MIN_SEPARATION = 4.0      # samples between the LEFT and RIGHT medians for a usable calibration


def capture(src: LiveMicSource, seconds: float) -> np.ndarray:
    target = int(seconds * src.rate)
    chunks, got = [], 0
    while got < target:
        item = src.get(timeout=1.0)
        if item is None:
            continue
        chunks.append(item[0])
        got += len(item[0])
    return np.concatenate(chunks)[:target]


def measure(src: LiveMicSource, side: str, seconds: float) -> tuple[float, float, int]:
    print(f"\n>>> {side}: get ready to clap / knock / play a clip on the {side}, ~1 m away")
    for i in (3, 2, 1):
        print(f"    {i}...", flush=True)
        time.sleep(1)
    while src.get(timeout=0.01) is not None:      # discard audio from the countdown
        pass
    print(f"    GO - make sharp sounds on the {side} for {seconds:.0f} s", flush=True)
    audio = capture(src, seconds)
    lags = frame_lags(audio, src.rate, max_frames=40)
    if not lags:
        print("    no usable sound captured")
        return float("nan"), float("nan"), 0
    raw = np.array([l for l, _ in lags])
    peaks = np.array([p for _, p in lags])
    med = float(np.median(raw))
    print(f"    {len(lags)} loud frames: raw lag median {med:+.2f} samples (sd {raw.std():.2f}), "
          f"mean GCC peak {peaks.mean():.2f}")
    return med, float(raw.std()), len(lags)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", help="input device name substring")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--no-centre", action="store_true", help="skip the CENTRE check")
    ap.add_argument("--force", action="store_true", help="save even if LEFT/RIGHT are poorly separated")
    args = ap.parse_args()

    src = LiveMicSource(args.device)
    print(f"device: {src.dev.label}   {src.rate} Hz x {src.channels} ch   physical max lag +/-{max_lag_samples():.1f}")
    src.start()
    try:
        left, left_sd, nl = measure(src, "LEFT", args.seconds)
        right, right_sd, nr = measure(src, "RIGHT", args.seconds)
        centre = None if args.no_centre else measure(src, "CENTRE (straight in front)", args.seconds)[0]
    finally:
        src.stop()

    if not (nl and nr):
        print("\nCalibration FAILED: no sound captured on one side. Nothing saved.")
        return 1
    sep = abs(left - right)
    sign = -1 if left > right else 1          # corrected positive must mean RIGHT
    cal = Calibration(sign, round((left + right) / 2, 3), "calibrate_direction.py")
    print("\n" + "=" * 70)
    print(f"LEFT {left:+.2f}  RIGHT {right:+.2f}  separation {sep:.2f} samples  -> sign {sign:+d}, "
          f"offset {cal.offset_samples:+.2f}")
    for name, raw in (("LEFT", left), ("RIGHT", right), ("CENTRE", centre)):
        if raw is None or np.isnan(raw):
            continue
        ang = lag_to_angle(cal.correct(raw))
        zone = angle_to_zone(ang)
        ok = "ok" if zone == name else "MISMATCH"
        print(f"  {name:<7} raw {raw:+6.2f} -> {ang:+5.0f} deg -> {zone:<7} {ok}")
    default_sign = config.DEFAULT_CAL_SIGN
    if sign != default_sign:
        print(f"NOTE: sign differs from the default ({default_sign:+d}) measured in the guided runs - double-check sides.")
    if sep < MIN_SEPARATION and not args.force:
        print(f"Separation below {MIN_SEPARATION:.0f} samples: sounds were too close to the centre, too quiet, or the "
              "channels are not distinct. Nothing saved (use --force to save anyway).")
        return 1
    cal.save(left_lag=round(left, 3), right_lag=round(right, 3),
             centre_lag=None if centre is None or np.isnan(centre) else round(centre, 3),
             left_sd=round(left_sd, 3), right_sd=round(right_sd, 3),
             device=src.dev.label, date=datetime.now().isoformat(timespec="seconds"))
    print(f"saved {config.CALIBRATION_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
