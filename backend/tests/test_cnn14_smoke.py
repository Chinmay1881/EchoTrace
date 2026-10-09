"""CNN14 end-to-end smoke test on a generated WAV (skipped if the weights aren't downloaded)."""

import numpy as np
import pytest
import soundfile as sf

from echotrace import config

pytestmark = pytest.mark.skipif(not config.WEIGHTS_FILE.exists(), reason="CNN14 weights not downloaded")

SR = 48000


@pytest.fixture(scope="module")
def tagger():
    from echotrace.tagging.panns_tagger import PannsTagger
    t = PannsTagger(force_cpu=True, gain_db=0)   # CPU: the path that must always work
    t.warmup()
    return t


def write_wav(path, x):
    sf.write(path, x, SR, subtype="PCM_24")
    y, sr = sf.read(path, dtype="float32")
    assert sr == SR and y.shape == x.shape
    return y


def test_tone_wav_is_tagged_as_tone(tagger, tmp_path):
    t = np.arange(SR) / SR
    s = 0.3 * np.sin(2 * np.pi * 1000 * t)
    x = write_wav(tmp_path / "tone.wav", np.stack([s, s], 1))
    probs = tagger.tag(x)
    assert probs.shape == (527,) and np.all(np.isfinite(probs)) and probs.min() >= 0 and probs.max() <= 1
    top = [tagger.labels[i] for i in np.argsort(probs)[::-1][:3]]
    assert "Sine wave" in top, top


def test_noise_and_silence(tagger, tmp_path):
    rng = np.random.default_rng(0)
    n = write_wav(tmp_path / "noise.wav", 0.1 * rng.standard_normal((SR, 2)))
    p = tagger.tag(n)
    top = [tagger.labels[i] for i in np.argsort(p)[::-1][:3]]
    assert {"Noise", "Static", "White noise"} & set(top), top
    silence = tagger.tag(np.zeros((SR, 2), np.float32))
    assert silence[tagger.labels.index("Silence")] > p[tagger.labels.index("Silence")]


def test_tagger_has_device_and_timing(tagger):
    assert tagger.device == "cpu"
    assert tagger.last_ms > 0
