import numpy as np
import pytest

from echotrace.audio.window import RollingWindow
from echotrace.tagging.panns_tagger import prepare

SR = 48000


def tone(freq, seconds=1.0, amp=0.1, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    return amp * np.sin(2 * np.pi * freq * t)


# ------------------------------------------------------------- resampling / gain
def test_prepare_shape_and_dtype():
    x = np.stack([tone(440), tone(440)], 1).astype(np.float32)
    y = prepare(x, gain_db=0)
    assert y.shape == (32000,) and y.dtype == np.float32
    assert prepare(x[:24000], 0).shape == (16000,)


@pytest.mark.parametrize("freq", [250, 1000, 3150, 9000])
def test_prepare_preserves_frequency(freq):
    x = np.stack([tone(freq), tone(freq)], 1).astype(np.float32)
    y = prepare(x, gain_db=0)
    spec = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    peak_hz = np.argmax(spec) * 32000 / len(y)
    assert abs(peak_hz - freq) <= 2


def test_prepare_applies_gain_and_downmix():
    l, r = tone(1000, amp=0.1), np.zeros(SR)
    y0 = prepare(np.stack([l, r], 1).astype(np.float32), gain_db=0)
    y20 = prepare(np.stack([l, r], 1).astype(np.float32), gain_db=20)
    rms0 = np.sqrt(np.mean(y0[1000:-1000] ** 2))
    assert rms0 == pytest.approx(0.05 / np.sqrt(2), rel=0.02)          # (0.1 + 0) / 2 downmix
    assert np.sqrt(np.mean(y20[1000:-1000] ** 2)) / rms0 == pytest.approx(10.0, rel=0.01)


def test_resample_no_block_edge_artifacts():
    # one window resampled at once has no discontinuity where 50 ms capture blocks met
    x = np.stack([tone(1000), tone(1000)], 1).astype(np.float32)
    y = prepare(x, 0)[2000:-2000]
    ideal = 0.1 * np.sin(2 * np.pi * 1000 * (np.arange(32000) / 32000))[2000:-2000]
    assert np.max(np.abs(y - ideal)) < 2e-3


# ------------------------------------------------------------- rolling window
def stream(n_samples, block):
    ramp = np.arange(n_samples, dtype=np.float32)
    x = np.stack([ramp, -ramp], 1)
    return [x[i:i + block] for i in range(0, n_samples, block)]


@pytest.mark.parametrize("block", [480, 2400, 7000, 30000, 100000])
def test_rolling_window_timing_and_content(block):
    rw = RollingWindow(SR, window_s=1.0, hop_s=0.5)
    wins = []
    for b in stream(SR * 3, block):
        wins.extend(rw.push(b, capture_time=1.0))
    # windows end at 1.0, 1.5, 2.0, 2.5, 3.0 s
    assert [w.t_end for w in wins] == [1.0, 1.5, 2.0, 2.5, 3.0]
    for w in wins:
        end = int(w.t_end * SR)
        assert w.audio.shape == (SR, 2)
        np.testing.assert_array_equal(w.audio[:, 0], np.arange(end - SR, end, dtype=np.float32))
        np.testing.assert_array_equal(w.audio[:, 1], -w.audio[:, 0])


def test_rolling_window_two_second_window():
    rw = RollingWindow(SR, window_s=2.0, hop_s=0.5)
    wins = [w for b in stream(SR * 3, 2400) for w in rw.push(b)]
    assert [w.t_end for w in wins] == [2.0, 2.5, 3.0]
    assert wins[0].audio.shape == (2 * SR, 2)


def test_rolling_window_rejects_bad_hop():
    with pytest.raises(ValueError):
        RollingWindow(SR, 1.0, 1.5)
