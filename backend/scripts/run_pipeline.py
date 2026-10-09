"""Run the full EchoTrace pipeline in the terminal (no server): events, sequences and status as they happen.

  python scripts/run_pipeline.py --source sim                 # SIMULATED scenario (no mic, no model)
  python scripts/run_pipeline.py --source live --seconds 60   # LIVE mic + CNN14
  python scripts/run_pipeline.py --source wav --file recordings\\clip.wav [--fast]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.audio.sources import LiveMicSource, SimSource, WavReplaySource
from echotrace.pipeline import Pipeline
from echotrace.schemas import validate

COLOR = {"GREEN": "92", "AMBER": "93", "RED": "91"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["live", "wav", "sim"], default="sim")
    ap.add_argument("--file", help="WAV for --source wav")
    ap.add_argument("--device", help="input device name substring for --source live")
    ap.add_argument("--fast", action="store_true", help="wav/sim: as fast as possible instead of real time")
    ap.add_argument("--seconds", type=float, help="stop after this many seconds of stream time")
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--frames", action="store_true", help="also print every frame")
    ap.add_argument("--sensitivity", choices=list(config.SENSITIVITY_PROFILES), default=config.SENSITIVITY)
    ap.add_argument("--scenario", default="all", help="sim: demo | breakin | all")
    ap.add_argument("--no-log", action="store_true", help="don't write recordings/run_*_events.jsonl")
    args = ap.parse_args()
    config.set_sensitivity(args.sensitivity)

    import os
    os.system("")  # ANSI colours in the Windows console

    tagger = None
    if args.source == "live":
        src = LiveMicSource(args.device)
    elif args.source == "wav":
        if not args.file:
            ap.error("--source wav needs --file")
        src = WavReplaySource(args.file, realtime=not args.fast)
    else:
        src = SimSource(realtime=not args.fast, loops=1 if args.fast else None, scenario=args.scenario)
    if args.source != "sim":
        from echotrace.tagging.panns_tagger import PannsTagger
        print("Loading CNN14 ...", flush=True)
        tagger = PannsTagger(force_cpu=args.cpu)
        tagger.warmup()

    log = None
    if not args.no_log:                                # event metadata only (no audio, no frames)
        config.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = config.RECORDINGS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}_events.jsonl"
        log = open(log_path, "w", encoding="utf-8")
    alerted = [0]

    def emit(msg: dict, capture: float | None) -> None:
        validate(msg)                                  # every message must match the WS contract
        if log is not None and msg["type"] != "frame":
            log.write(json.dumps(msg) + "\n")
            log.flush()
        if capture is not None and msg["type"] == "event":
            p.analyzer.record_latency((time.perf_counter() - capture) * 1000)
        d = msg["data"]
        k = msg["type"]
        if k == "frame" and args.frames:
            top = " | ".join(f"{x['label']} {x['p']:.2f}" for x in d["top"][:3])
            print(f"  [{d['source']}] {d['t']:7.1f}s  L {d['rms_db'][0]:6.1f} R {d['rms_db'][1]:6.1f}  {top}")
        elif k == "event":
            ang = "  -  " if d["angle_deg"] is None else f"{d['angle_deg']:+5.0f}"
            print(f"\033[1m[{d['source']}] EVENT {d['id']:<4} {d['t_start']:7.1f}-{d['t_end']:7.1f}s  {d['category']:<9} "
                  f"{d['label']:<22} {d['confidence']:.0%}  {d['zone']:<7} {ang} deg  "
                  f"(latency {p.analyzer.last_latency:.0f} ms)\033[0m")
        elif k == "sequence":
            c = COLOR[d["risk"]]
            print(f"\033[{c}m  SEQUENCE {d['id']} {d['risk']:<5} {d['pattern']:<26} events {d['event_ids']} "
                  f"trajectory {' -> '.join(d['trajectory']) or '-'}\033[0m")
            escalated = len(p.analyzer.alerts) > alerted[0]
            alerted[0] = len(p.analyzer.alerts)
            if escalated:
                print(f"\033[1;{c}m  >>> ALERT {d['risk']}: {d['pattern']} (sequence {d['id']})\033[0m")
            if escalated or len(d["event_ids"]) == 1:
                print(f"    {d['summary']}")
                for w in d["explanation"]:
                    print(f"      why: {w}")
        elif k == "status" and int(d["t"]) % 10 == 0:
            print(f"  [{d['source']}] status t={d['t']:.0f}s risk {d['risk']} loc {d['localization']} "
                  f"model {d['model_device']} latency {d['latency_ms']:.0f} ms dropped {d['dropped_blocks']}")

    p = Pipeline(src, tagger=tagger, emit=emit)
    info = src.info
    print(f"source {info.source}: {info.device} ({info.host_api}) {info.sample_rate} Hz x {info.channels} ch; "
          f"calibration: {p.analyzer.localizer.cal.source}; Ctrl+C to stop")
    src.start()
    try:
        while p.step():
            if args.seconds and p.analyzer.t >= args.seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        src.stop()
        if log is not None:
            log.close()
            print(f"event log: {log_path}")
    lat = p.analyzer.latencies
    base = len(p.analyzer.baseline.alerts)
    alerts = len(p.analyzer.alerts)
    print(f"\n{len(p.analyzer.events)} events, {len(p.analyzer.sequences)} sequences, EchoTrace alerts {alerts} vs "
          f"baseline alerts {base}" + (f"; latency mean {sum(lat) / len(lat):.0f} ms" if lat else ""))


if __name__ == "__main__":
    main()
