"""Start EchoTrace: pipeline + FastAPI + WebSocket + dashboard, on http://127.0.0.1:8000 by default.

  python scripts/serve.py                         # LIVE mic (falls back to SIMULATED, labelled, if it can't open)
  python scripts/serve.py --source sim            # SIMULATED scenario (demo + break-in)
  python scripts/serve.py --source recorded --file demo_backup.wav   # backup demo (loops, labelled RECORDED)
  python scripts/serve.py --host 0.0.0.0          # reachable from other devices on the network

Switch sources at runtime from the dashboard or with POST /api/mode.
"""

from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401
import uvicorn

from echotrace import config
from echotrace.api.server import FRONTEND_DIST, Engine, create_app

SOURCE = {"live": "LIVE", "recorded": "RECORDED", "wav": "RECORDED", "sim": "SIMULATED"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=list(SOURCE), default="live")
    ap.add_argument("--file", help="WAV for --source recorded: a path or a name in recordings/eval/ "
                                   "(default: recordings/eval/demo_backup.wav)")
    ap.add_argument("--device", help="input device name substring for LIVE")
    ap.add_argument("--scenario", default="all", help="SIMULATED scenario: demo | breakin | all")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--cpu", action="store_true", help="run CNN14 on the CPU")
    ap.add_argument("--sensitivity", choices=list(config.SENSITIVITY_PROFILES), default=config.SENSITIVITY,
                    help="detection threshold profile (default: %(default)s)")
    args = ap.parse_args()
    config.set_sensitivity(args.sensitivity)

    initial = {"source": SOURCE[args.source], "device": args.device, "file": args.file,
               "scenario": args.scenario if args.source == "sim" else None}
    app = create_app(Engine(force_cpu=args.cpu), initial)
    shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print("=" * 70)
    print(f"EchoTrace  starting {initial['source']}  ->  dashboard  http://{shown}:{args.port}/   "
          f"sensitivity {config.SENSITIVITY} (gain {config.tagger_gain_db():+.0f} dB)")
    print(f"           WebSocket ws://{shown}:{args.port}/ws    status http://{shown}:{args.port}/api/status")
    if not (FRONTEND_DIST / "index.html").is_file():
        print("           (frontend/dist not built yet: / shows a placeholder until it is)")
    print("           LIVE needs exclusive mic access (WDM-KS): close Teams/Zoom/browser mic tabs.")
    print("=" * 70, flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
