"""Test client: connect to the EchoTrace WebSocket, validate every message against the contract, print it.

  python scripts/ws_print.py                       # events, sequences, status changes (Ctrl+C to stop)
  python scripts/ws_print.py --frames --seconds 10
  python scripts/ws_print.py --url ws://127.0.0.1:8000/ws --raw

Exit code 1 if any message violated the contract.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter

import _bootstrap  # noqa: F401
from websockets.sync.client import connect

from echotrace.schemas import validate


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws")
    ap.add_argument("--seconds", type=float, help="stop after this long")
    ap.add_argument("--frames", action="store_true", help="also print frames")
    ap.add_argument("--raw", action="store_true", help="print the raw JSON")
    args = ap.parse_args()

    counts: Counter = Counter()
    bad = 0
    last_status = None
    t0 = time.monotonic()
    print(f"connecting to {args.url} ...")
    try:
        with connect(args.url, open_timeout=5) as ws:
            print("connected\n")
            while args.seconds is None or time.monotonic() - t0 < args.seconds:
                try:
                    text = ws.recv(timeout=1.0)
                except TimeoutError:
                    continue
                msg = json.loads(text)
                kind = msg.get("type")
                counts[kind] += 1
                try:
                    validate(msg)
                except Exception as e:
                    bad += 1
                    print(f"CONTRACT VIOLATION in {kind}: {e}\n  {text[:300]}")
                    continue
                d = msg["data"]
                if args.raw and (kind != "frame" or args.frames):
                    print(text)
                    continue
                if kind == "frame" and args.frames:
                    top = ", ".join(f"{x['label']} {x['p']:.2f}" for x in d["top"][:3])
                    print(f"[{d['source']}] frame  t={d['t']:.1f}  L {d['rms_db'][0]:.1f} R {d['rms_db'][1]:.1f}  {top}")
                elif kind == "event":
                    print(f"[{d['source']}] EVENT  {d['id']} {d['category']} '{d['label']}' {d['confidence']:.0%} "
                          f"{d['zone']} {d['angle_deg']} deg  t {d['t_start']:.1f}-{d['t_end']:.1f}")
                elif kind == "sequence":
                    print(f"[{d['source']}] SEQ    {d['id']} {d['risk']} {d['pattern']} {d['event_ids']} "
                          f"{' -> '.join(d['trajectory'])}\n         {d['summary']}")
                elif kind == "status":
                    key = (d["source"], d["risk"], d["localization"], d["device"])
                    if key != last_status:
                        print(f"[{d['source']}] STATUS risk {d['risk']}  device {d['device']} ({d['host_api']})  "
                              f"loc {d['localization']}  model {d['model_device']}  latency {d['latency_ms']} ms  "
                              f"dropped {d['dropped_blocks']}")
                        last_status = key
    except KeyboardInterrupt:
        pass
    except OSError as e:
        print(f"could not connect: {e}\nIs the server running?  backend\\.venv\\Scripts\\python.exe backend\\scripts\\serve.py")
        return 1
    print(f"\nreceived {dict(counts)}; contract violations: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
