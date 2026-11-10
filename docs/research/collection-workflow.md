# Practical collection workflow and current capability verification

Verified 8 November 2026 on research/icip2027-validation. Preparation only. No microphone capture, synthesized research audio, CNN14 replay, dependency installation, or held-out experiment was performed in this preparation step.

## Confirmed Codespace capabilities

`backend/.venv/bin/python backend/scripts/list_devices.py --all --no-probe` found no input devices. Direct PortAudio enumeration reports PortAudio V19.6.0-devel (revision 396fe4b…), ALSA and OSS host APIs with empty device lists, and default input/output -1/-1. [Raw read-only inventory](verification/collection-devices.json) and [project utility output](verification/collection-list-devices.txt).

| Environment | Device names | Input channels | Verified sample rates | Physical stereo |
|---|---|---|---|---|
| This Codespace | None enumerated | None available | None testable | Unavailable |
| Local laptop / USB recorder | Not accessible from this session | Must be checked locally | Must verify 48,000 Hz × 2 | Not yet confirmed |

**There is no working recording command for this Codespace.** A `--device` name cannot expose a missing microphone. Linux ALSA/OSS also cannot satisfy record_clip.py's configured Windows WDM-KS host requirement. No rate or device capability is inferred from the historical laptop description.

On the local recording machine run these commands first; they do not start a recording stream:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\research_devices.py
backend\.venv\Scripts\python.exe backend\scripts\list_devices.py --all --no-probe
```

research_devices.py checks two-channel float32 input settings at 16, 32, 44.1, 48 and 96 kHz for each input endpoint, retaining rejection errors and default sample rate. These are specific tested settings, not an exhaustive supported-rate list or proof the stream will open. Use an endpoint accepting 48 kHz × 2. A device's max_input_channels describes capability, not independent physical microphones. Confirm routing/specs and inspect separate practice LEFT/CENTRE/RIGHT takes; do not use test predictions to qualify hardware. Bare list_devices.py probes by recording about 1.5 seconds; it was intentionally **not** run without --no-probe here.

## Exact local recording command (conditional on verified WDM-KS device)

Current record_clip.py explicitly constructs LiveMicSource with host_api='Windows WDM-KS', rate=48000 and channels=2, and writes PCM_24 WAV. It accepts --device as a name substring, not an index or host override. Get the **actual local name** from the inventory; replace the example substring below if necessary. The script's --help was executed safely: [captured help](verification/collection-record-help.txt). No stream was opened.

From the repository root on the local Windows laptop, after hardware/practice qualification:

```powershell
$takePath = 'recordings/test/s01_take01_gi_l.wav'
if (Test-Path -LiteralPath $takePath) { throw "Take exists; choose a new ID and log the replacement." }
backend\.venv\Scripts\python.exe backend\scripts\record_clip.py --seconds 30 --out $takePath --device "Microphone Array" --countdown 5
```

The guard is required because the existing recorder overwrites a destination. Run one take at a time with the operator present, following the [ordered checklist](collection-checklist.md); the command itself does not enact sounds. Capture console output in the private session log, including actual endpoint, RMS, dropped blocks and overflows. WDM-KS is exclusive; close apps using the mic. Stop on gaps/clipping/mono duplication and document/reject a take before model output. Do not modify production host API rules to make a different local endpoint fit. If WDM-KS is absent, an external recorder app may export an original 48 kHz two-microphone PCM_24 file, but record app/settings/routing and require documented capture-integrity diagnostics. Unknown counters must not be replaced with zero. This alternative has not been verified here.

Before held-out collection, the operator may manually record practice audio outside recordings/test to qualify settings. No automated practice or held-out recording is launched by the supplied preparation/validation commands.

## Non-destructive file and manifest validation

Use the local environment's Python (Windows path above, or backend/.venv/bin/python on Linux). These commands only read files and print JSON, and never import the tagger/pipeline or write annotations:

```sh
# One existing take: format and signal checks only, before its human annotation is complete.
backend/.venv/bin/python backend/scripts/research_validate.py --wav recordings/test/s01_take01_gi_l.wav
# During collection: validates all files in the current manifest and lists missing planned IDs.
backend/.venv/bin/python backend/scripts/research_validate.py
# Complete admission gate: every one of the 36 planned IDs must be present.
backend/.venv/bin/python backend/scripts/research_validate.py --require-complete
# Optional measured metadata / explicitly incomplete annotation scaffold:
backend/.venv/bin/python backend/scripts/research_audio_qc.py recordings/test/s01_take01_gi_l.wav
```

Exit 0 means the requested checks passed, not independent scientific validation. Exit 2 means not ready/error; an empty manifest is **pending**, exit 2. File-only validation does not check labels. Full manifest validation checks actual 48 kHz stereo PCM_24 WAV, 25–35 s, finite decoded samples, nontruncated payload, peak < .999, no duplicated non-silent channels; IDs, durations, SHA256, exact byte/PCM duplicates against development/within test, all timed events, incident risk and causal endpoints, prescribed scenario/session/proxy risk, required human provenance and counters. Silence is allowed for quiet takes but cannot qualify stereo hardware. It reports 36 missing IDs as appropriate. The underlying generic manifest loader rejects any unannotated WAV in the manifest directory; keep incoming/unannotated/rejected files outside that directory until each file and its annotation can be admitted together. For a complete batch it is fine to place all WAVs and finish the manifest before validation; no inference should be run during this work.

The validator deliberately requires the finalized collection rubric; generic `research_eval.py validate` remains a separate schema-only check. Run the strict complete preflight before any later protocol lock/inference. It cannot verify semantic category truth, source rights, geometry or contextual intent; human blind review and session logs supply those facts.

## Transfer original WAVs without changing samples

Record on the local machine. Do not re-export, resample, normalize, compress to a lossy format, email through a transcoding service, or upload audio/weights to Git. Use a private transfer method such as the Codespaces VS Code file explorer Upload into a **new staging directory** outside recordings/test, e.g. recordings/incoming/session01-batch01/. Never overwrite existing takes. Transfer source WAVs, console/capture metadata, manifest drafts and a checksum inventory together. Keep consent/context video privately if sensitive; provide a traceable reference.

Create an ASCII SHA256SUMS on the local Windows laptop from actual captured files (new output name):

```powershell
$sumPath = 'recordings/test/SHA256SUMS'
if (Test-Path -LiteralPath $sumPath) { throw "Checksum inventory exists; use a new batch folder." }
Get-ChildItem -LiteralPath 'recordings/test' -Filter '*.wav' |
  Get-FileHash -Algorithm SHA256 |
  ForEach-Object { '{0}  {1}' -f $_.Hash.ToLower(), (Split-Path $_.Path -Leaf) } |
  Set-Content -LiteralPath $sumPath -Encoding ascii
```

In the fresh incoming directory in Codespaces run:

```sh
sha256sum --check SHA256SUMS
```

All entries must say OK and expected filenames/counts must match that session's capture log. A checksum proves byte preservation, not genuine acquisition. Inspect and complete blind annotation drafts; update their relative paths for final manifest location. Only then copy each admitted original into recordings/test **with exclusive creation** and recheck SHA256 at its final path; never overwrite a development/test file. Example for one manually selected take (no classifier or sound generation):

```sh
backend/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib
import shutil
src = Path('recordings/incoming/session01-batch01/s01_take01_gi_l.wav')
dst = Path('recordings/test/s01_take01_gi_l.wav')
expected = hashlib.sha256(src.read_bytes()).hexdigest()  # first verify against supplied SHA256SUMS
with src.open('rb') as incoming, dst.open('xb') as outgoing:
    shutil.copyfileobj(incoming, outgoing)
assert hashlib.sha256(dst.read_bytes()).hexdigest() == expected
print('Original bytes preserved; finish manifest admission before any inference.')
PY
```

Interrupted transfer/copy remains inadmissible and must be investigated, not silently overwritten. Keep the incoming original and checksum until the final admission checks pass. Store dataset originals/backups outside Git; `*.wav` is ignored, and the original ten development WAV exceptions must remain untouched. Manual source-asset comparison is still necessary: exact duplicates do not detect crops, re-encodings or different captures of the same playback.

## Verification performed in this preparation turn

- Read-only device enumeration and supported-settings utility executed; zero devices, no captures.
- Recorder --help executed; parser/host API/PCM write path inspected.
- Empty strict collection admission executed: exit 2, pending, no recordings; evidence collection-pending.json.
- Focused tests: `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python -m pytest -q backend/tests/test_collection_workflow.py backend/tests/test_research_infrastructure.py` → **25 passed, 14 subtests passed** ([transcript](verification/collection-tests-final.txt)). All generated waveforms are temporary labelled software fixtures, not research data. Checks cover bad formats, clipping, mono duplication, truncation, annotations/provenance, causal endpoints, checklist quotas, read-only behavior and incomplete admission.
- Historical 196-test full-suite pass remains documented separately; it was not rerun in this preparation step, nor was inference/setup repeated.

Remaining blockers: accessible qualified local stereo hardware, human collection of genuinely new takes, complete blind annotations/provenance, and unresolved historical evidence discrepancies. The rubric and schedule are now finalized for this collection; do not choose between conflicting label definitions after observing predictions. Stop after preparation until genuine data and its provenance exist.

Additional collection-lock verification: future evaluation snapshots now include collection-protocol.md, collection-checklist.csv and research_validate.py. The existing comparison/CLI lock regressions were executed again and passed **9 tests** (verification/collection-lock-regression.txt). No model inference was performed: scripted tagger/software fixtures only. A collection-plan-snapshot.json records preparation-time hashes; it is not an evaluated-dataset protocol lock.
