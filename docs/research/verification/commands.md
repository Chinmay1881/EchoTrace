# Verification command record — 8 November 2026

Run from /workspaces/EchoTrace on research/icip2027-validation. Logs use .txt so repository *.log ignores do not hide reviewable evidence. No benchmark timings below are pipeline latency claims.

## Environment restoration

- `python --version` → 3.14.2; global `python -m pip list` had no scientific backend dependencies. No existing pyvenv.cfg found under /workspaces, /opt or /home/codespace (search depth 4).
- `python3.12 -m venv backend/.venv` → failed: ensurepip unavailable.
- `/usr/local/python/3.13.8/bin/python3 -m venv backend/.venv` → failed while reusing incomplete 3.12 links.
- `/usr/local/python/3.13.8/bin/python3 -m venv --clear backend/.venv` → succeeded; cleared only the environment just created by those failed attempts.
- `backend/.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu` → sandbox DNS failure, then succeeded with network-enabled execution: torch 2.15.0+cpu.
- `backend/.venv/bin/python -m pip install -r backend/requirements.txt` → succeeded with network-enabled execution; [install transcript](install-requirements.txt).
- `python backend/scripts/download_weights.py` → succeeded with network/write access to ~/panns_data; weights 327,428,481 bytes, label CSV 14,675 bytes/527 classes; no existing weights found.
- `sudo apt-get update -qq && sudo apt-get install -y libportaudio2` → succeeded, installing eight required runtime packages (libportaudio2 19.6.0-1.2build3 plus ALSA/JACK/Opus/sample-rate dependencies). Initially sounddevice import failed without this library.
- `backend/.venv/bin/python -m pip check` → no broken requirements.
- `backend/.venv/bin/python -m pip freeze > docs/research/verification/requirements-resolved.txt` → exact installed versions saved. No package pin edits to production requirements.

## Regression and evaluation

Commands used the prefix `MPLCONFIGDIR=/tmp/echotrace-matplotlib OMP_NUM_THREADS=2 MKL_NUM_THREADS=2` unless specified. MPLCONFIGDIR avoids a read-only home cache; OMP/MKL cap CPU workers, not detection settings.

| Command after prefix | Actual outcome | Evidence |
|---|---|---|
| `backend/.venv/bin/python -m pytest -q backend/tests -rs` (while download pending) | 175 passed, 20 skipped, 1 warning, 14 subtests passed | pytest-initial.txt |
| Same full command after model download | Hung in TestClient; interrupted, exit 130; not a pass | pytest-final.txt |
| `timeout 90 backend/.venv/bin/python -m pytest -vv backend/tests/test_server.py -o faulthandler_timeout=20` | Sandbox TestClient first fixture timeout, exit 124; stack in AnyIO portal/thread wakeup | server-diagnostic.txt |
| `backend/.venv/bin/python -m pytest -q backend/tests --ignore=backend/tests/test_server.py -rs` | 187 passed, 14 subtests passed | pytest-without-server.txt |
| `timeout 60 backend/.venv/bin/python -m pytest -q backend/tests/test_server.py -rs -o faulthandler_timeout=15` (normal local networking) | 9 passed, 1 warning | server-network-enabled.txt |
| `timeout 120 backend/.venv/bin/python -m pytest -q backend/tests -rs` (normal local networking) | **196 passed, 0 skipped, 1 warning, 14 subtests passed** | pytest-complete.txt |
| `backend/.venv/bin/python -m pytest -q backend/tests/test_research_comparison.py backend/tests/test_research_cli.py -rs` | 9 passed | comparison-tests.txt |
| `PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/tests -p test_research_infrastructure.py -v` (no prefix needed) | 10 passed | research-unittest.txt |
| `PYTHONPATH=backend backend/.venv/bin/python -m pytest -q backend/tests/test_eval_metrics.py backend/tests/test_research_infrastructure.py` (no prefix needed) | 19 passed, 14 subtests passed | evaluation-tests.txt |
| `backend/.venv/bin/python backend/scripts/eval.py --cpu --no-write --no-compare` | Completed ten clips, archived headlines reproduced; confidence differs | development-eval.txt |
| `backend/.venv/bin/python backend/scripts/research_development.py --output docs/research/verification/development-reproduction.json` | Completed ten clips, full fresh event evidence and archive comparison saved | development-reproduction.json/.txt |
| `backend/.venv/bin/python backend/scripts/research_environment.py` | Initial model/PortAudio failures documented, final all imports OK, CUDA false, no audio devices | environment.json; environment-final.json |
| `backend/.venv/bin/python backend/scripts/download_weights.py --check` | ALL OK | model-check.txt |
| `backend/.venv/bin/python backend/scripts/research_eval.py validate` | Pending independent recordings, count 0 | manifest-check.json |
| `backend/.venv/bin/python backend/scripts/research_inventory.py > /tmp/development-inventory.json` then `cmp /tmp/development-inventory.json docs/research/development-inventory.json` | Equal, exit 0 | development-inventory.json in parent directory |
| `backend/.venv/bin/python backend/scripts/research_integrity.py > /tmp/echotrace-integrity.json` then `cmp /tmp/echotrace-integrity.json docs/research/verification/integrity.json` | Equal, 10 unique file/PCM hashes; original WAVs/labels/metrics/config/pipeline identical to HEAD | integrity.json |
| `backend/.venv/bin/python backend/scripts/research_audio_qc.py recordings/eval/glass_impact_01.wav` | QC/scaffold generated on explicitly development example; no annotation added | qc-development-example.json |

The only final suite warning is Starlette's deprecation of httpx TestClient integration. It does not fail tests; no unrelated web dependency changes made. Normal local networking is required here for the existing TestClient thread bridge; no production server changes made to hide that restriction. Initial skipped tests are enumerated in pytest-initial.txt; the completed final suite skipped none.

Fresh development output uses exclusive file creation. To repeat the JSON reproduction choose a **new** output path; do not overwrite archived or this run's evidence. Compare numeric/event payloads separately from generated timestamps and provenance snapshots. The standalone legacy command writes nothing with --no-write.

## Subsequent collection preparation (no inference)

- `backend/.venv/bin/python backend/scripts/list_devices.py --all --no-probe` → no input devices; collection-list-devices.txt.
- `backend/.venv/bin/python backend/scripts/research_devices.py` → ALSA/OSS with no devices, defaults -1/-1, capture_performed=false; collection-devices.json. No settings probes possible without endpoints.
- `backend/.venv/bin/python backend/scripts/record_clip.py --help` → parser help, no capture; collection-record-help.txt.
- `backend/.venv/bin/python backend/scripts/research_validate.py` → exit 2, pending no recordings; collection-pending.json. No model imports or inference.
- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python -m pytest -q backend/tests/test_collection_workflow.py backend/tests/test_research_infrastructure.py` → initial 23 passed/14 subtests; after adding causal endpoint/truncation checks **25 passed/14 subtests**; collection-tests.txt, collection-tests-final.txt. Generated signals exist only as temporary infrastructure fixtures.
- `backend/.venv/bin/python backend/scripts/research_integrity.py > docs/research/verification/collection-integrity.json` followed by `cmp docs/research/verification/collection-integrity.json docs/research/verification/integrity.json` → equal, exit 0.
- Read-only Python configuration inspection saved collection-config-check.json: current high DOOR .08/.04 versus archived .20/.10; no local calibration file, default sign -1/offset 0. No causality claimed.

See ../collection-workflow.md and ../discrepancy-investigation.md for exact operator instructions and proposed read-only follow-up checks. No repeated installation, full suite, development experiment, held-out replay or microphone capture occurred during preparation.

- `OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 backend/.venv/bin/python -m pytest -q backend/tests/test_research_cli.py backend/tests/test_research_comparison.py` → **9 passed**, collection-lock-regression.txt, after including rubric/checklist/validator in future lock snapshots. Scripted fixtures only; no CNN14 execution.
- `git diff --check` and protected-path `git diff --exit-code HEAD -- backend/echotrace/config.py backend/echotrace/pipeline.py docs/metrics.json docs/metrics.md recordings/eval` → exit 0.
