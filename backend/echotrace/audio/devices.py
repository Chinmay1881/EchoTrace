"""Input-device discovery and selection by name substring + host-API preference.

Device indices change when e.g. a Bluetooth headset connects, so EchoTrace never
stores an index: it resolves (name substring, host API) to an index at startup.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from echotrace import config


@dataclass
class InputDevice:
    index: int
    name: str
    host_api: str
    max_input_channels: int
    default_rate: float

    @property
    def label(self) -> str:
        return f"[{self.index}] {self.name} ({self.host_api})"


def is_loopback(name: str) -> bool:
    low = name.lower()
    return any(hint in low for hint in config.LOOPBACK_NAME_HINTS)


def host_api_rank(host_api: str) -> int:
    try:
        return config.HOST_API_PREFS.index(host_api)
    except ValueError:
        return len(config.HOST_API_PREFS)


def enumerate_inputs(devices: list[dict], hostapis: list[dict], include_loopback: bool = False) -> list[InputDevice]:
    """Input devices sorted by host-API preference (WDM-KS first), then index."""
    out = []
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) <= 0:
            continue
        if not include_loopback and is_loopback(d["name"]):
            continue
        out.append(InputDevice(
            index=d.get("index", i),
            name=d["name"],
            host_api=hostapis[d["hostapi"]]["name"],
            max_input_channels=d["max_input_channels"],
            default_rate=d.get("default_samplerate", 0.0),
        ))
    out.sort(key=lambda x: (host_api_rank(x.host_api), x.index))
    return out


def pick_device(
    inputs: list[InputDevice],
    name_prefs: list[str] | None = None,
    host_api: str | None = config.REQUIRED_HOST_API,
) -> InputDevice | None:
    """First device matching the name preferences (in order), restricted to host_api if given.

    With host_api=None, ties are broken by host-API preference order.
    """
    prefs = name_prefs if name_prefs is not None else config.DEVICE_NAME_PREFS
    for pref in prefs:
        p = pref.lower()
        for dev in inputs:  # already sorted by host-API preference
            if p in dev.name.lower() and (host_api is None or dev.host_api == host_api):
                return dev
    return None


def query_inputs(include_loopback: bool = False) -> list[InputDevice]:
    import sounddevice as sd
    return enumerate_inputs(list(sd.query_devices()), list(sd.query_hostapis()), include_loopback)


def resolve_device(name: str | None = None, host_api: str | None = config.REQUIRED_HOST_API) -> InputDevice:
    """Resolve a name substring (or the configured preferences) to a device; raise with a helpful list."""
    inputs = query_inputs()
    dev = pick_device(inputs, [name] if name else None, host_api)
    if dev is None:
        listing = "\n  ".join(d.label for d in inputs) or "(none)"
        wanted = name or " / ".join(config.DEVICE_NAME_PREFS)
        raise RuntimeError(
            f"No input device matching '{wanted}' on host API '{host_api or 'any'}'.\n"
            f"Available inputs:\n  {listing}\nRun scripts/list_devices.py for details."
        )
    return dev


def supports(dev_index: int, rate: int = config.CAPTURE_RATE, channels: int = config.CAPTURE_CHANNELS) -> bool:
    import sounddevice as sd
    try:
        sd.check_input_settings(device=dev_index, samplerate=rate, channels=channels, dtype="float32")
        return True
    except Exception:
        return False


@dataclass
class ChannelReport:
    corr: float
    lag_samples: int
    max_abs_diff: float
    rms_db: tuple[float, float]

    @property
    def silent(self) -> bool:
        return max(self.rms_db) < -120.0

    @property
    def identical(self) -> bool:
        return self.max_abs_diff == 0.0 or (self.corr > config.IDENTICAL_CHANNEL_CORR and self.lag_samples == 0)


def channel_report(x: np.ndarray, max_lag: int = 20) -> ChannelReport:
    """Compare the two channels of an (n, 2) block: correlation, best integer lag, difference."""
    left = x[:, 0].astype(np.float64)
    right = x[:, 1].astype(np.float64)
    rms = tuple(float(20 * np.log10(np.sqrt(np.mean(c ** 2)) + 1e-12)) for c in (left, right))
    l0, r0 = left - left.mean(), right - right.mean()
    denom = np.sqrt(np.sum(l0 ** 2) * np.sum(r0 ** 2)) + 1e-20
    corr = float(np.sum(l0 * r0) / denom)
    n = len(l0)
    best_lag, best = 0, -np.inf
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            v = np.dot(l0[lag:], r0[: n - lag])
        else:
            v = np.dot(l0[: n + lag], r0[-lag:])
        if v > best:
            best, best_lag = v, lag
    return ChannelReport(corr, best_lag, float(np.max(np.abs(left - right))), rms)  # type: ignore[arg-type]


def probe(dev_index: int, seconds: float = 1.5, rate: int = config.CAPTURE_RATE) -> ChannelReport:
    """Record a short stereo snippet from a device and compare its channels."""
    import sounddevice as sd
    x = sd.rec(int(seconds * rate), samplerate=rate, channels=2, dtype="float32", device=dev_index)
    sd.wait()
    return channel_report(x[int(0.2 * rate):])  # skip start-up transient
