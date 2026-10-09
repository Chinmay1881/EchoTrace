# EchoTrace

**PANNs hears. EchoTrace connects.**

Open-weight, fully local AI that turns environmental sound into situational awareness for
emergency responders, industrial-safety teams and smart-building operators when cameras can't see
(smoke, darkness, blind spots). It detects acoustic events with PANNs CNN14, places each one
approximately LEFT / CENTRE / RIGHT with GCC-PHAT on a 2-mic array, correlates events into
sequences, and raises explainable GREEN / AMBER / RED alerts. It complements CCTV; it never replaces it.

> Work in progress (Hack Day build). Full documentation lands in the final phase.

## Quick setup (Windows, PowerShell)

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe backend\scripts\download_weights.py
backend\.venv\Scripts\python.exe backend\scripts\list_devices.py
```

## Licence and attribution

Code: MIT. Model weights: PANNs CNN14 (Kong et al., 2020), CC BY 4.0, downloaded from Zenodo; not included in this repo.
