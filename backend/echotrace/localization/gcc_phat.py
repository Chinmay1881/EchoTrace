"""GCC-PHAT time-difference-of-arrival between two channels, with sub-sample precision.

Sign convention: lag > 0 means channel 1 (right) receives the sound LATER than
channel 0 (left), i.e. the source is towards channel 0. The physical left/right
mapping of the laptop's channels is fixed by calibration (Phase 2), not assumed.
"""

from __future__ import annotations

import numpy as np

from echotrace import config


def max_lag_samples(rate: int = config.CAPTURE_RATE, spacing: float = config.MIC_SPACING_M,
                    c: float = config.SPEED_OF_SOUND) -> float:
    return spacing / c * rate


def gcc_phat(x: np.ndarray, y: np.ndarray, rate: int = config.CAPTURE_RATE,
             max_lag: float | None = None, upsample: int = config.GCC_UPSAMPLE,
             band: tuple[float, float] | None = config.GCC_BAND_HZ) -> tuple[float, float]:
    """Return (lag_samples, peak) of y relative to x.

    Cross-spectrum is PHAT-whitened, optionally band-limited, then inverse-transformed with
    zero-padding (upsample x) and refined with parabolic interpolation around the peak.
    peak is the normalised PHAT coherence at the chosen lag (1.0 = perfect single path).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = len(x) + len(y)
    nfft = 1 << (n - 1).bit_length()
    X = np.fft.rfft(x, nfft)
    Y = np.fft.rfft(y, nfft)
    R = Y * np.conj(X)
    R /= np.abs(R) + 1e-12
    mask = np.ones(len(R))
    if band is not None:
        freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
        mask = ((freqs >= band[0]) & (freqs <= band[1])).astype(float)
        R *= mask
    n_up = upsample * nfft
    cc = np.fft.irfft(R, n=n_up)
    # value an ideal zero-lag impulse would reach, for normalising the peak to ~[0, 1]
    ideal = (mask[0] + 2 * mask[1:-1].sum() + mask[-1]) / n_up
    limit = n_up // 2 if max_lag is None else min(int(np.ceil(max_lag * upsample)) + 1, n_up // 2)
    cc = np.concatenate((cc[-limit:], cc[:limit + 1]))   # lags -limit .. +limit (upsampled units)
    i = int(np.argmax(cc))
    delta = 0.0
    if 0 < i < len(cc) - 1:
        a, b, c = cc[i - 1], cc[i], cc[i + 1]
        denom = a - 2 * b + c
        if denom != 0:
            delta = 0.5 * (a - c) / denom
    lag = (i - limit + delta) / upsample
    if max_lag is not None:
        lag = float(np.clip(lag, -max_lag, max_lag))
    return float(lag), float(cc[i] / ideal) if ideal > 0 else 0.0


def lag_to_angle(lag_samples: float, rate: int = config.CAPTURE_RATE, spacing: float = config.MIC_SPACING_M,
                 c: float = config.SPEED_OF_SOUND) -> float:
    """Broadside angle in degrees (0 = straight ahead; positive towards channel 0)."""
    s = np.clip(c * (lag_samples / rate) / spacing, -1.0, 1.0)
    return float(np.degrees(np.arcsin(s)))


def channel_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64) - np.mean(x)
    y = np.asarray(y, dtype=np.float64) - np.mean(y)
    return float(np.sum(x * y) / (np.sqrt(np.sum(x * x) * np.sum(y * y)) + 1e-20))
