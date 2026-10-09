import numpy as np

from echotrace.audio import devices as dv

HOSTAPIS = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}, {"name": "Windows WDM-KS"}]


def dev(name, api, ch=2):
    return {"name": name, "hostapi": api, "max_input_channels": ch, "default_samplerate": 48000.0}


DEVICES = [
    dev("Microphone Array 2 (Intel)", 0),           # 0 MME
    dev("Stereo Mix (Realtek)", 3),                 # 1 loopback
    dev("Microphone Array 2 (Intel)", 2),           # 2 WASAPI
    dev("Headset Microphone (BT)", 3, ch=1),        # 3
    dev("Microphone Array 1 (Intel Smart)", 3),     # 4 WDM-KS
    dev("Microphone Array 2 (Intel Smart)", 3),     # 5 WDM-KS
    {"name": "Speakers", "hostapi": 3, "max_input_channels": 0},
]


def test_wdmks_first_and_loopbacks_hidden():
    inputs = dv.enumerate_inputs(DEVICES, HOSTAPIS)
    assert inputs[0].host_api == "Windows WDM-KS"
    assert all("Stereo Mix" not in d.name for d in inputs)
    assert all(d.name != "Speakers" for d in inputs)
    assert any("Stereo Mix" in d.name for d in dv.enumerate_inputs(DEVICES, HOSTAPIS, include_loopback=True))


def test_pick_prefers_array2_on_wdmks():
    inputs = dv.enumerate_inputs(DEVICES, HOSTAPIS)
    assert dv.pick_device(inputs).index == 5


def test_pick_falls_back_to_array1():
    inputs = dv.enumerate_inputs([d for i, d in enumerate(DEVICES) if i != 5], HOSTAPIS)
    picked = dv.pick_device(inputs)
    assert picked.index == 4 and "Array 1" in picked.name


def test_pick_by_substring_survives_index_shift():
    shifted = [dev("Bluetooth Hands-Free", 3, ch=1)] + DEVICES  # all indices shift by one
    picked = dv.pick_device(dv.enumerate_inputs(shifted, HOSTAPIS), ["array 2"])
    assert picked.index == 6 and picked.host_api == "Windows WDM-KS"


def test_pick_none_when_no_wdmks_match():
    inputs = dv.enumerate_inputs(DEVICES[:3], HOSTAPIS)
    assert dv.pick_device(inputs) is None
    assert dv.pick_device(inputs, host_api=None).host_api == "Windows WASAPI"


def test_channel_report_identical_vs_distinct():
    rng = np.random.default_rng(0)
    s = rng.standard_normal(48000).astype(np.float32)
    same = np.stack([s, s], axis=1)
    assert dv.channel_report(same).identical

    delayed = np.stack([s, np.roll(s, 5)], axis=1) + 0.3 * rng.standard_normal((48000, 2)).astype(np.float32)
    rep = dv.channel_report(delayed)
    assert not rep.identical
    assert rep.lag_samples == 5   # right channel delayed by 5 samples
