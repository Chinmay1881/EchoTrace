"""GCC-PHAT core: recovers integer and sub-sample delays. (Zones + gating tests come in Phase 2.)"""

import numpy as np
import pytest

from echotrace.localization.gcc_phat import gcc_phat, lag_to_angle, max_lag_samples

SR = 48000


def frac_delay(x, d):
    """Delay x by d samples (fractional) via a frequency-domain phase shift."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n)
    return np.fft.irfft(X * np.exp(-2j * np.pi * f * d), n)


def noise(n=SR // 2, seed=0):
    return np.random.default_rng(seed).standard_normal(n)


def clicks(n=SR // 2, seed=1):
    rng = np.random.default_rng(seed)
    x = 0.001 * rng.standard_normal(n)
    for pos in (3000, 9000, 15000):
        burst = rng.standard_normal(200) * np.exp(-np.arange(200) / 30)
        x[pos:pos + 200] += burst
    return x


@pytest.mark.parametrize("make", [noise, clicks])
@pytest.mark.parametrize("delay", [0.0, 1.0, -3.0, 5.0, -8.0, 0.4, -1.3, 2.6, 6.75, -9.0])
def test_recovers_delay(make, delay):
    x = make()
    y = frac_delay(x, delay)
    rng = np.random.default_rng(42)
    x = x + 0.05 * np.std(x) * rng.standard_normal(len(x))
    y = y + 0.05 * np.std(y) * rng.standard_normal(len(y))
    lag, peak = gcc_phat(x, y, SR, max_lag=max_lag_samples() + 1)
    assert lag == pytest.approx(delay, abs=0.15), (lag, delay)
    assert peak > 0.3


def test_lag_is_limited():
    x = noise()
    lag, _ = gcc_phat(x, frac_delay(x, 30.0), SR, max_lag=max_lag_samples())
    assert abs(lag) <= max_lag_samples() + 1e-9


def test_geometry():
    assert max_lag_samples() == pytest.approx(0.065 / 343 * 48000, rel=1e-6)   # ~9.1 samples
    assert lag_to_angle(0) == 0
    assert lag_to_angle(max_lag_samples()) == pytest.approx(90)
    assert lag_to_angle(3.11) == pytest.approx(20, abs=0.3)                       # CENTRE edge
    assert lag_to_angle(-50) == pytest.approx(-90)
