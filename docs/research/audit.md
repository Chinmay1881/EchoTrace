# Source audit before implementation — 8 November 2026

Historical audit: missing-environment blockers below describe the initial state. Later restoration/verification and finalized collection preparation are documented in [report.md](report.md) and [collection-workflow.md](collection-workflow.md); original audit observations remain preserved.

Initial worktree clean. Dedicated branch: research/icip2027-validation. No AGENTS.md found.

- `backend/scripts/eval.py`: replays ten legacy labels through `run_wav_detailed`, permits profile/direction comparisons, defaults to overwriting docs/metrics.*. New research outputs must use a separate path. Legacy evidence will remain untouched.
- `echotrace/eval/metrics.py`: sequence score is clip maximum risk plus pattern, not incident recall. Detection checks category presence anywhere in clip. Localization maps category to a single label (last label wins); repeated detections overweight long sounds. Not suitable for multiple same-category physical sounds at different locations.
- `tagging/panns_tagger.py`: pretrained AudioSet CNN14, eval/no-grad, 527 classes; 48 kHz downmix, +20 dB gain, polyphase 32 kHz resampling, deterministic seed-0 dither. `last_ms` excludes preprocessing and includes tensor transfer/output synchronization. Weights and labels external, not in checkout.
- `detection/debounce.py`, `config.py`, `tagging/categories.py`: hysteresis and N-of-M activation; closes after off hops and splits long sounds at MAX_EVENT_S. Category map takes maximum member score. High sensitivity developed on these clips. Source currently overrides DOOR at .08/.04 whereas archived metrics lists .20/.10; capture source/config hashes in future runs rather than assuming exact environment parity.
- `localization/gcc_phat.py`, `zones.py`: PHAT spectrum, 300–8000 Hz band, physically bounded lag, upsample/interpolate; strongest energy frames vote with peak weights, calibration sign/offset, high/low confidence tiers. Default calibration can be replaced by ignored local JSON; identical channels disable localization. No algorithm changes planned.
- `correlation/graph.py`, `patterns.py`: time-linked clusters, priority ordered subsequences, category counts and temporal gaps. Zones affect trajectory summaries, not matching.
- `pipeline.py:add_event`, `risk/engine.py`: sequence alert on first pattern and strictly increasing risk; no ordinary time cooldown switch. Risk decays for display after quiet time, without clearing fired state. Correlation removal is baseline A; localization metadata removal can affect presentation only. A confidence filter on emitted events cannot undo upstream detection thresholds.
- `baseline.py`: one alert per concerning **already debounced** event, using event start time. Long sound splitting and repeated detections create repeats (11 alarm alerts in lone_alarm_01). EchoTrace uses event end/processing stream time. Fair timing comparisons need common emission timestamps; original baseline timestamps are not delivery latency.
- `recordings/eval`: ten WAVs and ten JSON labels. Labels give category/zone, clip pattern/risk, notes; no physical event IDs or times. Provenance is only aggregate narrative (self-recorded staged playback, one laptop/room); recording dates cannot be inferred from Git timestamps. No independent recordings supplied.
- Tests cover debounce, GCC, zones, category maps, correlation, pipeline, API, sensitivity, regression, preprocessing, optional CNN14 smoke. Baseline invocation `python -m pytest -q backend/tests` fails before collection: No module named pytest. numpy/scipy/soundfile/torch/panns_inference also absent; weights absent. Do not claim suite passed or reproduced inference here.

## Evidence discrepancy

Archived docs/metrics.json and .md agree: 46/56 correct, one UNKNOWN, high 40/42, low 6/13. Their confidence strata total 55 known + one UNKNOWN. User reports a one-event confidence discrepancy in a Codespaces reproduction, but no event-level reproduction artifact is supplied. Archived per-clip detail strips confidence and times, so the responsible event cannot be identified from it. Preserve both claims; cause unresolved. Future output must retain per-event confidence, time, IDs, code/config/calibration/model hashes and software versions. Do not relabel old evidence.

## Minimum implementation plan

1. Add dependency-free strict held-out manifest validation, SHA256 file and decoded PCM duplicate checks against development, and an empty pending manifest. Keep original recordings and annotations unchanged. Generate a development inventory honestly marking missing provenance/timing.
2. Freeze protocol and source/config inventory before independent evaluation; reject drift, malformed annotations and non-independent declarations. Write research outputs into separate immutable run directories, never legacy docs/metrics.*. This protects against accidental tuning, not deliberate edits or repeated human inspection.
3. Add independent replay adapter preserving detections and emission times; compare A per-event, B global fixed cooldown, C per-category fixed cooldown, D unchanged correlation. Predefine one-to-one temporal incident matching and separately report duplicate alerts and clip-level outcomes. Test matching and validation with handcrafted fixtures only, not research recordings.
4. Add timing instrumentation/procedure only after infrastructure validation. Do not run expensive experiments without weights/dependencies or genuine test data.

## Genuine blockers / scope status

Independent test collection and verified provenance/timed annotations pending. Legacy annotations cannot support event latency or per-physical-sound localization; manual annotation required. CPU pipeline runtime unavailable in current environment. No raw Codespaces confidence reproduction supplied. No measured new baseline, ablation, benchmark or independent validation result can honestly be reported yet. Existing 90% and 82.1% are development evidence only. Full scientific evaluation remains incomplete.
