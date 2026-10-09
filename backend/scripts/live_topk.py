"""Live PANNs tagging from the WDM-KS mic: meters, top-5 labels, category scores every hop.

  python scripts/live_topk.py                      # free run, Ctrl+C for the summary
  python scripts/live_topk.py --guided             # guided test script (logs CSV automatically)
  python scripts/live_topk.py --log --gain 26      # free run with CSV log and a different tagger gain

Keys (in an interactive terminal): n = skip to the next step, q = finish now.
Every hop also measures channel correlation and the GCC-PHAT lag of the newest hop of
audio, so real sounds can be compared with room noise for localization.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime

import numpy as np

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.audio.sources import LiveMicSource
from echotrace.audio.window import RollingWindow
from echotrace.localization.gcc_phat import channel_corr, gcc_phat, lag_to_angle, max_lag_samples
from echotrace.tagging.categories import CategoryMap, top_k
from echotrace.tagging.panns_tagger import PannsTagger

try:
    import msvcrt  # Windows console keys
except ImportError:  # pragma: no cover
    msvcrt = None

GET_READY_S = 5.0


class GuidedDone(Exception):
    pass

# Search lags up to 2x the physical maximum so implausible (non-acoustic) lags stay visible.
DIAG_MAX_LAG = 2.0 * max_lag_samples()


@dataclass
class Step:
    name: str
    seconds: float
    expect: str | None      # category that should fire (None = nothing should)
    where: str              # where to make the sound (for the lag diagnostic)
    how: str


STEPS = [
    Step("BACKGROUND", 20, None, "-", "Stay silent. Don't touch the laptop or the table."),
    Step("FOOTSTEPS", 15, "FOOTSTEPS", "LEFT",
         "Walk on the LEFT of the laptop (~1 m), or play a footsteps clip from the phone held on the LEFT."),
    Step("IMPACT", 15, "IMPACT", "RIGHT",
         "On the RIGHT: thud the table / drop a book every ~2 s."),
    Step("DISTRESS", 15, "DISTRESS", "RIGHT",
         "Play a scream clip from the phone held ~1 m to the RIGHT."),
    Step("ALARM", 15, "ALARM", "CENTRE",
         "Play a smoke/fire-alarm clip from the phone ~1 m straight in FRONT."),
    Step("GLASS", 15, "GLASS", "LEFT",
         "Play a glass-breaking clip from the phone ~1 m to the LEFT."),
    Step("KNOCK", 10, "IMPACT", "RIGHT",
         "Knock on the table / a door on the RIGHT, a few knocks at a time."),
    Step("CHATTER", 20, None, "CENTRE",
         "Talk normally in FRONT of the laptop (or play people chatting). Should trigger nothing."),
]


@dataclass
class Hop:
    t: float
    step: str
    counted: bool
    probs: np.ndarray
    rms: tuple[float, float]
    corr: float
    lag: float
    peak: float
    ms: float


# ------------------------------------------------------------------ formatting
class Style:
    def __init__(self, color: bool):
        self.on = color
        if color and os.name == "nt":
            os.system("")  # enables ANSI escape processing in the Windows console

    def __call__(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text


def db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))


def meter(level_db: float, width: int = 12, lo: float = -70.0, hi: float = -10.0) -> str:
    n = int(round(np.clip((level_db - lo) / (hi - lo), 0, 1) * width))
    return "#" * n + "." * (width - n)


SHORT = {"FOOTSTEPS": "FOOT", "IMPACT": "IMP", "DISTRESS": "DIST", "ALARM": "ALARM", "GLASS": "GLASS", "DOOR": "DOOR"}


def cat_line(scores: dict[str, float], thr: float, st: Style) -> str:
    parts = []
    for cat, p in scores.items():
        s = f"{SHORT.get(cat, cat)} {p:.2f}{'*' if p >= thr else ' '}"
        parts.append(st(s, "1;92") if p >= thr else s)
    return "  ".join(parts)


# ------------------------------------------------------------------ summary
def summarize(hops: list[Hop], labels: list[str], cmap: CategoryMap, thr: float, guided: bool) -> list[str]:
    out: list[str] = []
    counted = [h for h in hops if h.counted]
    if not counted:
        return ["No hops recorded."]
    P = np.stack([h.probs for h in counted])
    cats = {c: np.array([cmap.scores(h.probs)[c] for h in counted]) for c in cmap.names}

    out.append("=" * 78)
    out.append(f"SUMMARY  ({len(counted)} hops counted, threshold {thr:.2f})")
    out.append("-" * 78)
    out.append(f"{'category':<11}{'max':>7}{'mean':>7}{'hops>=thr':>11}")
    for c, v in cats.items():
        out.append(f"{c:<11}{v.max():>7.2f}{v.mean():>7.3f}{int((v >= thr).sum()):>11}")

    out.append("-" * 78)
    out.append("Top 10 labels overall (by max probability):")
    mx, mean = P.max(axis=0), P.mean(axis=0)
    for i in np.argsort(mx)[::-1][:10]:
        out.append(f"  {labels[i]:<40} max {mx[i]:.2f}  mean {mean[i]:.3f}")

    if guided:
        out.append("-" * 78)
        out.append("Per-step breakdown")
        bg = [h for h in counted if h.step == "BACKGROUND"]
        bg_db = float(np.median([max(h.rms) for h in bg])) if bg else None
        for step in STEPS:
            sh = [h for h in counted if h.step == step.name]
            if not sh:
                out.append(f"\n[{step.name}] skipped")
                continue
            sp = np.stack([h.probs for h in sh])
            smx = sp.max(axis=0)
            sc = {c: np.array([cmap.scores(h.probs)[c] for h in sh]) for c in cmap.names}
            exp = f"expect {step.expect}" if step.expect else "expect nothing"
            out.append(f"\n[{step.name}] {len(sh)} hops, {exp}, sound at {step.where}")
            if step.expect:
                v = sc[step.expect]
                verdict = "OK" if (v >= thr).any() else "MISSED"
                out.append(f"  {step.expect}: max {v.max():.2f}  mean {v.mean():.3f}  "
                           f"hops>=thr {int((v >= thr).sum())}/{len(sh)}  -> {verdict}")
            false = [f"{c} {sc[c].max():.2f} ({int((sc[c] >= thr).sum())} hops)"
                     for c in cmap.names if c != step.expect and (sc[c] >= thr).any()]
            out.append("  other categories >= thr: " + (", ".join(false) if false else "none"))
            out.append("  category max: " + "  ".join(f"{SHORT[c]} {sc[c].max():.2f}" for c in cmap.names))
            out.append("  top labels:   " + " | ".join(f"{labels[i]} {smx[i]:.2f}"
                                                       for i in np.argsort(smx)[::-1][:5]))
            # channel diagnostics: all hops vs the loudest quarter (the actual sounds)
            loud_db = np.array([max(h.rms) for h in sh])
            k = max(1, len(sh) // 4)
            loud = [sh[i] for i in np.argsort(loud_db)[::-1][:k]]
            lags_all = np.array([h.lag for h in sh])
            lags_loud = np.array([h.lag for h in loud])
            med_loud = float(np.median(lags_loud))
            rel = f" ({float(np.median([max(h.rms) for h in loud])) - bg_db:+.1f} dB vs background)" \
                if bg_db is not None else ""
            out.append(f"  level: median {np.median(loud_db):.1f} dBFS, loudest-quarter "
                       f"{np.median([max(h.rms) for h in loud]):.1f} dBFS{rel}")
            out.append(f"  channels: corr all {np.mean([h.corr for h in sh]):+.3f}  "
                       f"loud {np.mean([h.corr for h in loud]):+.3f}")
            out.append(f"  GCC-PHAT lag (samples, + = right ch. later): all median {np.median(lags_all):+.2f} "
                       f"(sd {lags_all.std():.2f})  loud median {med_loud:+.2f} "
                       f"(sd {lags_loud.std():.2f}, values {', '.join(f'{x:+.1f}' for x in lags_loud[:6])})  "
                       f"peak {np.mean([h.peak for h in loud]):.2f}  ~{lag_to_angle(med_loud):+.0f} deg")
        out.append("\nLag guide: physical max is +/-%.1f samples; |lag| < ~3.1 is CENTRE. The sign for LEFT/RIGHT"
                   % max_lag_samples())
        out.append("is fixed later by calibrate_direction.py - here, check LEFT and RIGHT steps have opposite signs.")
    out.append("=" * 78)
    return out


# ------------------------------------------------------------------ main
def read_key() -> str | None:
    if msvcrt is None:
        return None
    try:
        if msvcrt.kbhit():
            return msvcrt.getwch().lower()
    except Exception:
        return None
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", help="input device name substring (default: config.DEVICE_NAME_PREFS)")
    ap.add_argument("--window", type=float, default=config.WINDOW_S, help="analysis window, s")
    ap.add_argument("--hop", type=float, default=config.HOP_S, help="hop, s")
    ap.add_argument("--gain", type=float, default=config.TAGGER_GAIN_DB, help="tagger gain, dB")
    ap.add_argument("--threshold", type=float, default=config.ON_THRESHOLD)
    ap.add_argument("--cpu", action="store_true", help="force CPU inference")
    ap.add_argument("--log", action="store_true", help="write all 527 probabilities per hop to recordings/")
    ap.add_argument("--guided", action="store_true", help="walk through the test script (implies --log)")
    ap.add_argument("--step-seconds", type=float, help="override every guided step's duration (testing)")
    ap.add_argument("--seconds", type=float, help="free run: stop automatically after this many seconds")
    ap.add_argument("--quiet", action="store_true", help="don't print every hop")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    st = Style(not args.no_color and sys.stdout.isatty())

    print("Loading CNN14 ...", flush=True)
    tagger = PannsTagger(force_cpu=args.cpu, gain_db=args.gain)
    warm_ms = tagger.warmup(args.window)
    labels = tagger.labels
    cmap = CategoryMap(labels)

    src = LiveMicSource(args.device)
    rw = RollingWindow(src.rate, args.window, args.hop, src.channels)
    hop_n = rw.hop

    print("=" * 78)
    print(f"EchoTrace live_topk   source: LIVE")
    print(f"device   : {src.dev.label}")
    print(f"host API : {src.dev.host_api}   rate: {src.rate} Hz   channels: {src.channels}")
    print(f"model    : CNN14 on {tagger.device} (warm-up {warm_ms:.0f} ms/window)   "
          f"window {args.window:.2f} s   hop {args.hop:.2f} s   gain {args.gain:+.1f} dB   thr {args.threshold:.2f}")
    print("keys     : n = next step, q = finish   (Ctrl+C also finishes)")
    print("=" * 78)

    log_path = None
    writer = log_f = None
    if args.log or args.guided:
        config.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = config.RECORDINGS_DIR / f"topk_{stamp}.csv"
        log_f = open(log_path, "w", newline="", encoding="utf-8")
        writer = csv.writer(log_f)
        writer.writerow(["t", "step", "counted", "rms_l", "rms_r", "corr", "lag", "peak", "ms",
                         "gain_db", "window_s"] + labels)
        print(f"logging  : {log_path}")

    steps = [Step(s.name, args.step_seconds or s.seconds, s.expect, s.where, s.how) for s in STEPS]
    step_i, phase, phase_end = 0, "READY", None   # phases: READY (not counted) -> RUN
    hops: list[Hop] = []
    t_now = 0.0

    def announce(i: int) -> None:
        s = steps[i]
        print()
        print(st(f">>> STEP {i + 1}/{len(steps)}: {s.name} ({s.seconds:.0f} s, sound at {s.where})", "1;96"))
        print(st(f"    {s.how}", "96"))
        print(st(f"    get ready... starts in {GET_READY_S:.0f} s (n = skip this step)", "2"))

    if args.guided:
        announce(0)
        phase_end = GET_READY_S
    last_countdown = None

    src.start()
    try:
        while True:
            key = read_key()
            if key == "q":
                print("\n[q] finishing")
                break
            if key == "n" and args.guided:
                print(f"\n[n] skipping {steps[step_i].name}")
                step_i += 1
                if step_i >= len(steps):
                    break
                announce(step_i)
                phase, phase_end = "READY", t_now + GET_READY_S
            if args.seconds and not args.guided and t_now >= args.seconds:
                break

            item = src.get(timeout=0.2)
            if item is None:
                continue
            block, cap_t = item
            for w in rw.push(block, cap_t):
                t_now = w.t_end
                # guided phase transitions are driven by stream time (sample count)
                if args.guided:
                    if phase == "READY" and t_now >= phase_end:
                        phase, phase_end = "RUN", t_now + steps[step_i].seconds
                        print(st(f"    >>> GO: {steps[step_i].name} now", "1;93"))
                    elif phase == "RUN" and t_now >= phase_end:
                        step_i += 1
                        if step_i >= len(steps):
                            raise GuidedDone
                        announce(step_i)
                        phase, phase_end = "READY", t_now + GET_READY_S
                    if phase == "READY":
                        left = int(np.ceil(phase_end - t_now))
                        if left != last_countdown:
                            print(st(f"    ... {left}", "2"), flush=True)
                            last_countdown = left

                counted = (not args.guided) or phase == "RUN"
                step_name = steps[step_i].name if args.guided else ""
                probs = tagger.tag(w.audio)
                newest = w.audio[-hop_n:]
                rms = (db(newest[:, 0]), db(newest[:, 1]))
                corr = channel_corr(newest[:, 0], newest[:, 1])
                lag, peak = gcc_phat(newest[:, 0], newest[:, 1], src.rate, max_lag=DIAG_MAX_LAG)
                hop = Hop(t_now, step_name, counted, probs, rms, corr, lag, peak, tagger.last_ms)
                hops.append(hop)
                if writer:
                    writer.writerow([f"{t_now:.2f}", step_name, int(counted), f"{rms[0]:.1f}", f"{rms[1]:.1f}",
                                     f"{corr:.4f}", f"{lag:.3f}", f"{peak:.3f}", f"{tagger.last_ms:.1f}",
                                     args.gain, args.window] + [f"{p:.4f}" for p in probs])
                    log_f.flush()
                if counted and not args.quiet:
                    scores = cmap.scores(probs)
                    drops = src.dropped_blocks + src.overflows
                    tag = f"{step_name:<10} " if args.guided else ""
                    print(f"{t_now:7.1f}s {tag}L {rms[0]:6.1f} [{meter(rms[0])}] R {rms[1]:6.1f} [{meter(rms[1])}]"
                          f"  corr {corr:+.2f} lag {lag:+5.1f}  {tagger.last_ms:4.0f} ms"
                          + (st(f"  DROPS {drops}", "91") if drops else ""))
                    print("         " + " | ".join(f"{l} {p:.2f}" for l, p in top_k(probs, labels)))
                    print("         " + cat_line(scores, args.threshold, st), flush=True)
    except GuidedDone:
        print("\nGuided test complete.")
    except KeyboardInterrupt:
        print("\n[Ctrl+C] finishing")
    finally:
        src.stop()
        if log_f:
            log_f.close()

    lines = summarize(hops, labels, cmap, args.threshold, args.guided)
    if src.dropped_blocks or src.overflows:
        lines.append(f"WARNING: {src.dropped_blocks} dropped blocks, {src.overflows} input overflows")
    print("\n".join(lines))
    if log_path:
        summary_path = log_path.with_name(log_path.stem + "_summary.txt")
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"CSV log : {log_path}\nsummary : {summary_path}")


if __name__ == "__main__":
    main()
