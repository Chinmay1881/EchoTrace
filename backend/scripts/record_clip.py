"""Record a test clip from the WDM-KS mic: 48 kHz, stereo, 24-bit WAV.

Raw audio is only ever saved by this script, when you explicitly run it.

  python scripts/record_clip.py --seconds 20 --name demo_sequence
  python scripts/record_clip.py --seconds 10 --out C:\\path\\clip.wav --countdown 3
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.audio.devices import channel_report
from echotrace.audio.sources import LiveMicSource


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--name", default="clip", help="file name stem (saved in recordings/)")
    ap.add_argument("--out", help="explicit output path (overrides --name)")
    ap.add_argument("--device", help="input device name substring")
    ap.add_argument("--countdown", type=int, default=3, help="seconds of countdown before recording")
    args = ap.parse_args()

    if args.out:
        out = Path(args.out)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = config.RECORDINGS_DIR / f"{args.name}_{stamp}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)

    src = LiveMicSource(args.device)
    print(f"device: {src.dev.label}   {src.rate} Hz x {src.channels} ch -> {out} (PCM_24)")
    for i in range(args.countdown, 0, -1):
        print(f"  recording in {i}...", flush=True)
        time.sleep(1)

    target = int(args.seconds * src.rate)
    got = 0
    chunks = []
    src.start()
    print(f"  RECORDING {args.seconds:.0f} s  (Ctrl+C stops early and keeps what was recorded)", flush=True)
    last_print = -1
    try:
        with sf.SoundFile(out, "w", samplerate=src.rate, channels=src.channels, subtype="PCM_24") as f:
            while got < target:
                item = src.get(timeout=1.0)
                if item is None:
                    continue
                block = item[0][: target - got]
                f.write(block)
                chunks.append(block)
                got += len(block)
                sec = got // src.rate
                if sec != last_print:
                    lvl = 20 * np.log10(np.sqrt(np.mean(block.astype(np.float64) ** 2, axis=0)) + 1e-12)
                    print(f"    {sec:3d} s   L {lvl[0]:6.1f}  R {lvl[1]:6.1f} dBFS", flush=True)
                    last_print = sec
    except KeyboardInterrupt:
        print("  stopped early")
    finally:
        src.stop()

    audio = np.concatenate(chunks) if chunks else np.zeros((0, 2), np.float32)
    print(f"saved {got / src.rate:.1f} s to {out}")
    if src.dropped_blocks or src.overflows:
        print(f"WARNING: {src.dropped_blocks} dropped blocks, {src.overflows} overflows - the clip has gaps")
    if len(audio) > src.rate // 2:
        rep = channel_report(audio)
        print(f"channels: corr {rep.corr:+.4f}  lag {rep.lag_samples:+d}  "
              f"rms [{rep.rms_db[0]:.1f}, {rep.rms_db[1]:.1f}] dBFS  peak {np.abs(audio).max():.3f}")
        if rep.silent:
            print("WARNING: the clip is silent - wrong device, or the mic is muted.")
        elif rep.identical:
            print("WARNING: the two channels are IDENTICAL - localization will be OFF for this clip. "
                  "Use the WDM-KS 'Microphone Array' device, not WASAPI/MME.")
        if np.abs(audio).max() >= 0.999:
            print("WARNING: the clip clips (peak at full scale) - move the sound source further away.")


if __name__ == "__main__":
    main()
