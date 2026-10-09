## Running EchoTrace (Windows)

Everything runs locally: no cloud API, no generative model. Commands are for PowerShell from the repo root.

### 1. Set up (once)

Needs **Python 3.12** (not 3.13/3.14: PyTorch wheels) and **Node.js 18+**.

```powershell
py -3.12 -m venv backend\.venv
# NVIDIA GPU (CUDA 12.8):
backend\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
# ...or CPU only:
# backend\.venv\Scripts\python.exe -m pip install torch
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Download the PANNs CNN14 weights (~327 MB, CC BY 4.0, Zenodo) and the AudioSet label list into `~\panns_data`.
No `wget` needed. Existing valid files are detected and skipped, and interrupted downloads resume:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\download_weights.py          # --check to only verify
```

Build the dashboard (once, and after any frontend change):

```powershell
cd frontend; npm install; npm run build; cd ..
```

### 2. Pick and calibrate the microphone

```powershell
backend\.venv\Scripts\python.exe backend\scripts\list_devices.py
```

EchoTrace uses the laptop's built-in mic array through the **Windows WDM-KS** host API (48 kHz, 2 channels).
It is chosen by name ("Microphone Array 2", then "Microphone Array 1"), so changing device indices don't matter.
The listing marks each device and checks whether its two channels are genuinely different, which localization needs.

Calibrate LEFT/RIGHT once per laptop:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\calibrate_direction.py
```

Clap in the air, or play a sharp clip from a phone, about 1 m to the LEFT, then the RIGHT, then straight ahead.
**Don't knock on the table the laptop stands on**: the vibration reaches both mics at once and measures nothing.
The result is saved only if it's consistent; otherwise the script explains why and says REDO.

### 3. Run

```powershell
backend\.venv\Scripts\python.exe backend\scripts\serve.py                                     # LIVE microphone
backend\.venv\Scripts\python.exe backend\scripts\serve.py --source sim                        # SIMULATED scenario
backend\.venv\Scripts\python.exe backend\scripts\serve.py --source recorded                         # RECORDED backup clip
```

Open **http://localhost:8000/**. The Live / Recorded / Simulation buttons switch sources at runtime.
Every screen and message carries its source, and simulated or recorded data is never shown as live.
RECORDED loops the clip in real time with 10 s of silence between loops. By default it plays
`recordings/eval/demo_fallback.wav` (a demo-only clip with no label, so not part of the evaluation), or `breakin_01.wav`
if that file is missing. `--file <name>` picks another clip; a bare file name is looked up in `recordings/eval/`. If the microphone can't be opened at startup, the server falls back to SIMULATED, clearly
labelled, and shows the error in `/api/status`.

Other tools: `scripts/live_topk.py` (what CNN14 hears, with a guided test), `scripts/record_clip.py`
(record a 48 kHz stereo test clip), `scripts/run_pipeline.py` (full pipeline in the terminal; writes an event
log used for latency), `scripts/ws_print.py` (WebSocket client that checks every message against the contract).

### 4. Evaluate

```powershell
backend\.venv\Scripts\python.exe backend\scripts\eval.py
```

Replays every labelled clip in `recordings/eval/` (labels in `recordings/eval/labels/*.json`) through the same
pipeline as live, faster than real time. It compares against a classification-only baseline that alerts on every
concerning sound, and writes `docs/metrics.json` (shown in the dashboard) and `docs/metrics.md`. Latency comes only
from live runs: run `scripts/run_pipeline.py --source live` while making sounds, then re-run `eval.py`.

Tests: `cd backend; .venv\Scripts\python.exe -m pytest -q`

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Could not open ... WDM-KS" or a probe fails | WDM-KS gives one program **exclusive** use of the mic. Close Teams, Zoom, Discord, browser tabs using the mic, Windows Sound settings, and any other EchoTrace window. |
| Localization OFF, or every event CENTRE/UNKNOWN | A WASAPI/MME version of the mic was used. Windows voice processing **merges the two channels**. Use the WDM-KS "Microphone Array" device (the default). Turning off "Audio enhancements" for the mic also helps. |
| The device disappears or the wrong mic is used after connecting a Bluetooth headset | Headsets change device indices. EchoTrace selects by name; check with `list_devices.py` or pass `--device "Microphone Array 1"`. |
| `serve.py` fails with "address already in use" | Port 8000 is taken, usually by another `serve.py` still running. Close it, or `Get-NetTCPConnection -LocalPort 8000` to find it. |
| Dashboard says "backend is running ... not built" | Run `npm run build` in `frontend/`, then reload. |
| No events although the meters move | The sound didn't reach the event threshold. The live panel shows each category's score against its threshold line: move the source closer or make it louder. |
| CNN14 on CPU is slow | Install the CUDA torch wheel. CPU still works (about 50 to 110 ms per window). |
