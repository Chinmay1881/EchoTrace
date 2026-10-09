"""List audio input devices for EchoTrace.

WDM-KS devices are listed first. Each device is marked if it accepts 48 kHz x 2 ch.
Speaker loopbacks (Stereo Mix, PC Speaker) are hidden unless --all.
By default the 48 kHz x 2 ch devices are probed for ~1.5 s to check whether the
two channels are genuinely distinct (needed for localization).

  python scripts/list_devices.py            # list + probe capable devices
  python scripts/list_devices.py --no-probe # list only
  python scripts/list_devices.py --all      # include loopback endpoints
"""

import argparse

import _bootstrap  # noqa: F401
from echotrace import config
from echotrace.audio import devices as dv


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-probe", action="store_true", help="do not record from devices")
    ap.add_argument("--all", action="store_true", help="include speaker loopback endpoints")
    ap.add_argument("--seconds", type=float, default=1.5)
    args = ap.parse_args()

    inputs = dv.query_inputs(include_loopback=args.all)
    pick = dv.pick_device(inputs)
    rate, ch = config.CAPTURE_RATE, config.CAPTURE_CHANNELS

    print(f"Input devices (host API preference: {' > '.join(config.HOST_API_PREFS)})")
    print(f"  ok = accepts {rate} Hz x {ch} ch;  >> = EchoTrace default pick\n")
    current_api = None
    for dev in inputs:
        if dev.host_api != current_api:
            current_api = dev.host_api
            note = "  <- required for EchoTrace" if current_api == config.REQUIRED_HOST_API else ""
            print(f"== {current_api}{note}")
        ok = dv.supports(dev.index, rate, ch)
        mark = ">>" if pick and dev.index == pick.index else "  "
        line = f"{mark} [{dev.index:>3}] {dev.name[:52]:<52} in={dev.max_input_channels} " \
               f"def={dev.default_rate:.0f}  {'ok' if ok else '--'}"
        if ok and not args.no_probe:
            try:
                rep = dv.probe(dev.index, args.seconds, rate)
                if rep.silent:
                    verdict = "SILENT (no signal; unplugged or muted)"
                elif rep.identical:
                    verdict = "IDENTICAL (no localization)"
                else:
                    verdict = "distinct stereo"
                line += (f"  corr={rep.corr:+.4f} lag={rep.lag_samples:+d} "
                         f"rms=[{rep.rms_db[0]:.1f},{rep.rms_db[1]:.1f}] dBFS  {verdict}")
            except Exception as e:  # WDM-KS is exclusive; busy devices fail to open
                line += f"  probe failed: {str(e).splitlines()[0][:60]}"
        print(line)

    print()
    if pick:
        print(f"EchoTrace will use: {pick.label}")
    else:
        print(f"WARNING: no device matching {config.DEVICE_NAME_PREFS} on {config.REQUIRED_HOST_API}.")
        print("Pass --device <name substring> to the other scripts.")
    print("Tip: WDM-KS is exclusive. Close Teams/Zoom/browser tabs using the mic if a probe fails.")


if __name__ == "__main__":
    main()
