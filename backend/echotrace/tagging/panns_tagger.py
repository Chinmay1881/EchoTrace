"""PANNs CNN14 audio tagger (AudioSet, 527 classes), local inference only.

Window pipeline: 48 kHz stereo -> downmix -> TAGGER_GAIN_DB -> resample_poly to 32 kHz
(whole window at once, so no block-edge artifacts) -> CNN14 clipwise probabilities.
The gain is for tagging only; localization always uses the raw stereo signal.
"""

from __future__ import annotations

import time
from math import gcd
from typing import Protocol

import numpy as np
from scipy.signal import resample_poly

from echotrace import config
from echotrace.tagging.categories import load_labels


class Tagger(Protocol):
    labels: list[str]
    device: str

    def tag(self, window: np.ndarray) -> np.ndarray:
        """(n, channels) float32 window at config.CAPTURE_RATE -> (527,) probabilities."""
        ...


_dither_cache: dict[int, np.ndarray] = {}


def _dither(n: int) -> np.ndarray:
    """Fixed (deterministic) noise at config.TAGGER_DITHER_DBFS.

    Digitally perfect input (exact silence, pure synthetic tones) has exact-zero spectral bins
    that CNN14 never saw in training; on CPU this collapses the log-mel to its -100 dB floor and
    the output becomes garbage. Real mic audio is never like that, so this changes nothing live.
    """
    if n not in _dither_cache:
        rng = np.random.default_rng(0)
        _dither_cache[n] = (10 ** (config.TAGGER_DITHER_DBFS / 20) * rng.standard_normal(n)).astype(np.float32)
    return _dither_cache[n]


def prepare(window: np.ndarray, gain_db: float, in_rate: int = config.CAPTURE_RATE,
            out_rate: int = config.MODEL_RATE) -> np.ndarray:
    """Stereo/mono window -> gained mono float32 at the model rate (+ tiny fixed dither)."""
    x = np.asarray(window, dtype=np.float32)
    mono = x.mean(axis=1) if x.ndim == 2 else x
    mono = mono * np.float32(10.0 ** (gain_db / 20.0))
    g = gcd(out_rate, in_rate)
    y = resample_poly(mono, out_rate // g, in_rate // g).astype(np.float32)
    return y + _dither(len(y))


def pick_torch_device(force_cpu: bool = False) -> str:
    import torch
    return "cuda" if (not force_cpu and torch.cuda.is_available()) else "cpu"


class PannsTagger:
    def __init__(self, force_cpu: bool = False, gain_db: float | None = None):
        import torch
        from panns_inference.models import Cnn14

        self.gain_db = config.tagger_gain_db() if gain_db is None else gain_db   # per sensitivity profile
        self.labels = load_labels()
        self.device = pick_torch_device(force_cpu)
        if not config.WEIGHTS_FILE.exists():
            raise FileNotFoundError(f"{config.WEIGHTS_FILE} missing - run scripts/download_weights.py")
        self.model = Cnn14(sample_rate=config.MODEL_RATE, window_size=1024, hop_size=320, mel_bins=64,
                           fmin=50, fmax=14000, classes_num=config.LABELS_COUNT)
        ckpt = torch.load(str(config.WEIGHTS_FILE), map_location="cpu", weights_only=False)
        self.model.load_state_dict(ckpt["model"])
        self.model.eval().to(self.device)
        self._torch = torch
        self.last_ms = 0.0

    def warmup(self, seconds: float = config.WINDOW_S, runs: int = 3) -> float:
        """Run a few dummy windows so the first real window isn't slow. Returns ms of the last run."""
        silence = np.zeros((int(seconds * config.CAPTURE_RATE), 2), dtype=np.float32)
        for _ in range(runs):
            self.tag(silence)
        return self.last_ms

    def tag(self, window: np.ndarray) -> np.ndarray:
        x = prepare(window, self.gain_db)
        t0 = time.perf_counter()
        with self._torch.no_grad():
            inp = self._torch.from_numpy(x[None, :]).to(self.device)
            probs = self.model(inp, None)["clipwise_output"][0].float().cpu().numpy()
        self.last_ms = (time.perf_counter() - t0) * 1000
        return probs
