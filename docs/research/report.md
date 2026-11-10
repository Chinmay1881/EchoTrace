# ICIP 2027 Paper 956 — research evaluation status

8 November 2026. Phase 2 environment and framework verification completed; collection of genuine independent recordings is pending. Independent validation and real-time benchmarking remain incomplete. Original evidence in docs/metrics.json and docs/metrics.md remains unchanged. See [source audit](audit.md) for inspected modules, blockers and implementation decisions.

## Evidence and provenance

Ten staged development clips were used during threshold and localization development. The inventory preserves original JSON labels and SHA256 file/PCM identities, recording duration and format. Unknown dates, per-recording device/environment and event timing remain null. No new recordings or research annotations were fabricated. New recordings belong under recordings/test with strict timed annotations and independently reviewed provenance. A separate output hierarchy prevents mixing development and independent results.

| Existing development result | Archived value | Interpretation |
|---|---:|---|
| Clip risk plus pattern agreement | 9/10 | Development fit, not independent validation |
| Direction agreement per emitted event | 46/56 | Repeated emissions share sounds; not 56 independent physical trials |
| Non-incident alert counts | EchoTrace 0; baseline 20 | Five recordings; operator alert burden |
| Total alert counts | EchoTrace 7; baseline 56 | Different alert policies; not incident precision/recall |
| Latency | Unmeasured | No event-timed live evidence |

Failed clip breakin_02 lacks above-threshold GLASS and ALARM detections in archived output. This explains why that required chain cannot form; it does not establish general correctness of correlation. The new CPU reproduction reproduces the reported confidence discrepancy: archived high correct/wrong 40/2, low 6/7, UNKNOWN 1 versus fresh high 40/2, low 6/8, UNKNOWN 0. Category-order alignment identifies the first IMPACT in glass_impact_01 (3.5–4.5 s, confidence .385, label Hammer) as archived UNKNOWN versus fresh low-confidence CENTRE. Both are incorrect against RIGHT ground truth, so overall 46/56 agreement is unchanged. Old timestamps and raw confidence are unavailable; the alignment is not proof of numerical/platform causation. See verification/evidence-differences.json. Do not overwrite either result.

## Implemented protocol

`research_eval.py` validates before loading the model. It freezes code, data and available model/calibration hashes, rejects drift, runs fixed CPU inference through unchanged `run_wav_detailed`, preserves all emitted events and their emission stream times and writes new JSON and Markdown runs under docs/research/runs/independent-test/<run-id>. Existing directories and locks cannot be overwritten. The lock now also captures Python and resolved package versions; freeze rejects missing model/label files. Research results omit nondeterministic host capture_time fields and retain emission stream times. Offline runtime is not reported as latency. No threshold, mapping, localization or correlation production code changed.

A alerts per concerning debounced event. B suppresses all further alerts for 10 seconds after an accepted alert. C suppresses same-category alerts for 10 seconds after an accepted alert of that category. D uses unchanged EchoTrace escalation alerts. Cooldown is fixed provisionally before unseen evaluation, not optimized for test performance. All use the same upstream detections and common emission clock. At exactly 10 seconds the next alert is accepted. B/C are explicitly operational baseline policies, not new detection algorithms.

Incident binary matching ignores severity/category for all systems. Acceptance interval is annotated incident start minus 1 second through end plus 1 second, inclusive. Chronologically process alerts; assign each to the eligible unmatched incident with earliest end. Each alert/incident matches once. Remaining alerts are FP, including duplicate alerts in incident intervals; unmatched incidents are FN. This interval matching maximizes match count for point alerts. Report TP/FP/FN, precision, recall, F1, duplicate counts and FP per recording/hour, per scenario and pooled. Undefined denominators remain null. Severity/pattern agreement is a separate future metric. Test annotations must define incidents independently of predictions; generous long intervals may reward premature alerts, a limitation requiring review before freeze.

## Tests and reproducibility

From repository root:

```sh
python -m pytest -q backend/tests
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_research_infrastructure.py -v
python backend/scripts/research_eval.py validate
python backend/scripts/research_inventory.py > /tmp/development-inventory.json
cmp /tmp/development-inventory.json docs/research/development-inventory.json
```

The initial pre-restoration failure (`No module named pytest`) is historical. The restored environment now passes **196 tests, zero skips, one deprecation warning, plus 14 pytest subtests**. The original ten research tests also passed independently under unittest; nine additional comparison/CLI tests passed. Existing evaluation metrics plus the ten research tests passed as a focused group (19 tests, 14 subtests). The final suite includes real CNN14 smoke tests with downloaded weights and all previously skipped label-dependent tests.

The first restored run while downloads were pending passed 175 and skipped 20; a subsequent sandbox run hung at the existing FastAPI TestClient fixture and was interrupted. A 90-second diagnostic timed out (not a pass). The 187 non-server tests passed in the sandbox; all nine server tests and the complete 196-test suite then passed with normal local networking. The sole completed-suite warning is Starlette's httpx TestClient deprecation. No server code was changed. Exact commands, outcomes, intermediate errors and links to transcripts: [verification command record](verification/commands.md).

## Verified research environment

No functioning pre-existing venv was found. The global interpreter is Python 3.14.2. Python 3.12 venv creation failed because ensurepip was missing; a project-specific **Python 3.13.8** environment was created at backend/.venv using installed /usr/local/python/3.13.8. Requirements were installed from backend/requirements.txt after CPU-only torch from its official CPU index. Missing libportaudio2 was installed for sounddevice. No threshold or production inference changes were made. The environment is ignored by Git.

Verified: NumPy **2.5.4**, SciPy **1.18.1**, PyTorch **2.15.0+cpu**, soundfile **0.14.0**, sounddevice **0.5.6**, librosa **1.0.0**, torchlibrosa **0.1.0**, panns_inference **0.1.1**, pytest **9.2.0**. All scientific/evaluation imports passed; pip check found no broken requirements. CUDA is unavailable, torch has no CUDA runtime. CPU reports AMD EPYC 7763; this container exposes two logical CPUs. No local PortAudio devices are enumerated, so physical collection must occur on the local laptop/recorder, not Codespaces. Full environment and package versions: [environment-final.json](verification/environment-final.json), [resolved requirements](verification/requirements-resolved.txt).

The repository's official download_weights.py downloaded and verified CNN14 (**327,428,481 bytes**) and AudioSet labels (**527 classes**), stored outside Git at ~/panns_data. CNN14 SHA256: `0dc499e40e9761ef5ea061ffc77697697f277f6a960894903df3ada000e34b31`. This is the locally measured identity, not an independently signed vendor checksum. Real model loading/inference passed in the smoke tests and development replay. No weights or virtual environment added to Git.

## Fresh development reproduction (measured)

| Metric | Archived | Fresh CPU reproduction |
|---|---:|---:|
| Clip risk/pattern agreement | 9/10 | 9/10 |
| Correct direction / labelled emitted events | 46/56 | 46/56 |
| High-confidence correct/wrong | 40/2 | 40/2 |
| Low-confidence correct/wrong | 6/7 | 6/8 |
| UNKNOWN | 1 | 0 |
| All upstream detections | 56 | 58 |
| EchoTrace / per-event baseline alerts | 7/56 | 7/56 |
| Non-incident EchoTrace / baseline alerts | 0/20 | 0/20 |
| Failed clip | breakin_02 | breakin_02 |

Fresh detections include two DOOR events: breakin_02 at 3.0–3.5 s and glass_impact_01 at 7.0–7.5 s. Current source already has high-profile DOOR thresholds .08/.04 whereas archived configuration says .20/.10. No settings were changed during this task. This pre-existing source/archive difference is consistent with extra DOOR detections but does not establish the cause of the localization change. DOOR is outside the concerning-alert categories and legacy labelled localization denominator. Therefore 58 total detections and 56 direction-scored detections are distinct denominators. Detection category counts and all per-clip pattern/risk outcomes match the archive. This is headline reproduction, **not exact evidence reproduction or independent validation**.

The legacy evaluation ran with --cpu --no-write --no-compare. A separate reproducible research wrapper saved metrics, per-event IDs/categories/times/confidence/zones, model/config/source hashes and software metadata in [development-reproduction.json](verification/development-reproduction.json). No latency was measured. Original ten WAVs, original JSON labels, docs/metrics.*, config.py and pipeline.py match HEAD byte-for-byte; inventory matches, all ten file and PCM identities are unique. See [integrity.json](verification/integrity.json).

## Baseline framework validation (software fixtures)

A single unchanged pipeline replay supplies D and the shared event list for A/B/C. All four use emission stream timestamps and the same annotated incidents/tolerance/assignment function. Unit tests check accepted alert event IDs against shared detections, escalation duplicates as FP, exact tolerance boundaries, benign GLASS+ALARM with zero incidents, and invariance to host capture clock. A full simulated pipeline fixture is replayed twice with equal results.

An end-to-end CLI integration test uses a temporary deterministic noise WAV and scripted tagger, **explicitly software-test fixtures, not collected scientific audio**. It executes freeze→replay twice, verifies byte-equal JSON, verifies all four systems and benign negatives, rejects source drift, existing output directories and lock replacement. No fabricated independent-study scores are reported. Resolved packages are part of the protocol lock. Sensitivity, mappings and algorithms remain unchanged. Publication summaries and machine-readable outputs are supported, but real incident precision/recall cannot be computed from the untimed legacy annotations.

## Collecting unseen recordings and next commands

Use the [36-clip recording protocol](collection-protocol.md): 12 staged positive acoustic sequences, 8 isolated sounds, 8 benign multi-event negatives, 4 quiet/background clips and 4 speech/household clips, each 25–35 seconds across at least three sessions. Capture genuine new takes with independently sourced stimuli and actual provenance. Balance LEFT/CENTRE/RIGHT where measurable; no development audio or playback excerpt reuse. Staged/playback proxies must remain explicitly labelled as such. The collection rubric is now finalized as `echotrace-contextual-proxy-v1`: staged contextual-proxy labels from the prespecified script/context log, with both routine kitchen takes GREEN even when the acoustic chain is present. These are proxy outcomes, not verified real-world incident safety. See the finalized protocol for limitations and blind annotation rules.

The protocol provides local capture commands, quality checks, incomplete annotation templates, actual timing instructions and freeze/run commands. `research_audio_qc.py` supplies observed duration/hash/quality data without classifier output; all human ground-truth fields remain incomplete until reviewed. Record on the physical laptop/recorder because this container exposes no audio devices. Freeze code/environment/annotation decisions before inspecting held-out results; never tune thresholds on them.

```sh
backend/.venv/bin/python backend/scripts/list_devices.py
# Run on the local compatible WDM-KS recording laptop:
python backend/scripts/record_clip.py --seconds 30 --out recordings/test/s01_take01_gi_l.wav --device "Microphone Array" --countdown 5
python backend/scripts/research_audio_qc.py recordings/test/s01_take01_gi_l.wav
# After all genuine recordings and blind annotations have been transferred/reviewed:
backend/.venv/bin/python backend/scripts/research_eval.py validate
backend/.venv/bin/python backend/scripts/download_weights.py --check
backend/.venv/bin/python backend/scripts/research_eval.py freeze
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLCONFIGDIR=/tmp/echotrace-matplotlib backend/.venv/bin/python backend/scripts/research_eval.py run --run-id initial-independent-test
```

Current admission result remains `pending independent recordings`, count 0. No empty-dataset success metric or protocol lock was generated. Remaining blockers are genuine unseen audio and blind timed/provenance annotations, confirmed local stereo recording hardware. The contextual-proxy rubric and ordered 36-take schedule have now been finalized before collection; no held-out predictions were inspected. The cause of the preserved localization discrepancy remains unresolved. Later phases still require per-physical-sound localization scoring, measured ablations and real-time benchmarking; none are claimed complete here.

## Collection preparation verification — 8 November 2026

PortAudio inspection in this turn confirms **no devices** in Codespaces: ALSA and OSS APIs have empty device lists, default input/output -1/-1. No device names, input channels or sample rates can be confirmed for local hardware from this environment. The read-only `research_devices.py` utility inventories endpoints and checks stereo settings at specified common rates without capture. No recording command can work here; local Windows WDM-KS capture is conditional on an actual qualified endpoint. See [workflow and exact local commands](collection-workflow.md), [device evidence](verification/collection-devices.json), [ordered 36-clip checklist](collection-checklist.md) and [CSV](collection-checklist.csv).

Final rubric: 6 AMBER staged GLASS→IMPACT proxies, 6 RED staged GLASS→IMPACT→ALARM proxies, 24 GREEN routine/isolated/background cases. Both routine kitchen negatives explicitly have no incidents; their target sounds remain annotated. Positive scripts have exactly one incident with causal event_ids and boundaries copied from actual first/last causal sounds. Physical directions come from logged geometry, not predictions. See the finalized protocol for sound identity, timing, provenance, source independence, and collection-deviation rules. Scripts establish contextual-proxy labels before inference; they cannot demonstrate recognition of actual emergencies.

`research_validate.py --wav <path>` validates format/QC only; `research_validate.py` validates the current annotated collection; `--require-complete` enforces all 36 scheduled IDs. These commands are non-destructive and do not load CNN14. Checks include 48 kHz two-channel PCM_24 WAV, 25–35 s, finite/clipping/truncation/channel duplication, hashes/duplicates, required provenance and zero capture loss counters, prescribed risk/session/scenario and causal annotation endpoints. Partial collections explicitly list missing IDs; the current empty manifest returns exit 2/pending. Human semantic/provenance/hardware review is still required. Generic research_eval.py validation is less strict; run the complete collection preflight before any future inference.

Executed focused checks: **25 tests passed plus 14 subtests**, including the original ten research tests and fifteen new collection checks; [transcript](verification/collection-tests-final.txt). Temporary fixtures are labelled software tests and were never added as scientific audio. The historical 196-test backend pass was not rerun, no dependencies were reinstalled, and no model/research replay ran in this preparation turn. Recorder --help, read-only device listing and integrity checks were executed. Original recordings/labels/metrics/config/pipeline match the prior integrity evidence byte-for-byte; see verification/collection-integrity.json.

The 58-versus-56 and confidence discrepancies remain preserved. [Investigation checklist](discrepancy-investigation.md) identifies the exact existing logs, threshold/calibration/source/package checks and missing archived raw evidence required to assess causes, without forcing agreement or changing results. Remaining blockers: qualified local microphone access, genuine unseen recordings and blind annotation/provenance. Preparation stops here; independent evaluation is not complete.

## Remaining experiments and measurement method (proposed, not measured)

Correlation disabled corresponds to A; B isolates operational cooldown from A; C assesses category suppression. D already suppresses repeated sequence risk: a time cooldown is not its existing mechanism, so avoid calling B/D a single-factor cooldown ablation. Confidence filtering requires a development-selected explicit threshold and replay from stored detections; current adapter does not implement it. Localization metadata removal should be tested as prediction invariance, not an incident-recognition benefit: category/time matcher never consumes zones.

For localization, timed physical event IDs enable one-to-one category/time assignment with a predeclared tolerance. Report emission-weighted results and physical-sound results separately, unmatched physical sounds, UNKNOWN coverage, high/low accuracy and accuracy versus retained coverage. Do not collapse repeated categories to one location. Current independent adapter preserves events for this analysis but does not yet calculate physical-sound scores.

Benchmark only after a verified pipeline run: instrument preprocessing around `prepare`, synchronized CNN14 inference excluding preprocessing, `_localize`, and correlation `add_event` excluding localization. Measure perf_counter_ns wall durations; do not interpret nested totals as disjoint. Record cold process startup/model load/first inference separately from warm runs (at least three warmups followed by a predeclared five replay trials initially). Record CPU process-time/wall-time percentage with core normalization stated and peak process RSS including platform units. Capture CPU model, cores, RAM, OS, Python, package versions, model hash, device, threads, calibration and power mode. Report median, p95, count per stage/trial and trial variability. Offline replay wall time/audio duration is throughput; it is not live onset-to-alert latency. A paced run must log monotonic capture/emission clocks, dropped blocks, event completion and true sound timing; existing status latency references newest triggering block and omits prior acoustic/context delay. No numeric latency is inferred here. No benchmark harness or new timings are claimed.

## Uncertainty and threats to validity

Ten staged clips from one room/device and playback sounds do not establish field generalization. Detection fragments are correlated; confidence strata are selected subsets. No confidence interval computed from 56 emissions would represent independent physical trials. Future independent study should report recording/session-level uncertainty with a preregistered resampling plan and seed (e.g. 0), enough independent sessions, and disclose small strata. No significance, confidence intervals or improved accuracy claimed. Publication-ready baseline table generation is implemented for future runs; no new empirical figures exist to reproduce yet. The scientific evaluation remains incomplete until independent collection, model integration checks, localization analysis, ablations and benchmarking are performed.

Additional collection-lock verification: future evaluation snapshots now include collection-protocol.md, collection-checklist.csv and research_validate.py. The existing comparison/CLI lock regressions were executed again and passed **9 tests** (verification/collection-lock-regression.txt). No model inference was performed: scripted tagger/software fixtures only. A collection-plan-snapshot.json records preparation-time hashes; it is not an evaluated-dataset protocol lock.

## Research format and modality amendment — 10 November 2026

Research-only admission now accepts original signed PCM_16 or PCM_24 WAV/WAVEX
at 48 kHz with one or two channels. The collection duration remains 25–35 s.
Explicit evaluation_mode=non-spatial accepts mono and dual-mono for classification
and temporal correlation with null/omitted ground-truth zones. Localization remains
the default and requires two channels, rejects exact dual-mono and non-silent
near-identical channel diagnostics, and still requires human hardware/geometry
qualification. Distinct channels are reported as stereo-candidate, never proven
physical stereo. File QC alone leaves spatial_eligible false.

Both actual Audacity pilot files passed non-spatial QC unchanged (exit 0):
pilot_background_01.wav (PCM_16) and pilot_background_01_24bit.wav (PCM_24), each
26.17 s, 48 kHz, two identical channels, peak .08306884765625. Both remain rejected
for localization (exit 2). No model inference or independent evaluation ran.
These pilot files count as zero independent takes; original acquisition provenance
is operator-reported and conversion does not create an independent recording.

Research outputs preserve source hash/encoding/channels and suppress spatial
predictions for non-spatial records. Directional scoring remains unimplemented,
with denominator explicitly zero. Production inference, preprocessing, weights,
thresholds, category mappings and temporal rules are unchanged. Independent
manifest role/annotation/independence checks and frozen-input protection remain;
additional decoded identities catch lossless bit-depth and duplicated-channel
variants without changing historical hashes or results. Prior locks would reject
source drift. All 36 independent recordings, blind timed annotations, provenance,
capture-integrity evidence and verified physical stereo for localization remain
pending. Exact commands, schema and limitations: [workflow amendment](collection-workflow.md#research-format-and-modality-amendment--10-november-2026).

Verification for this amendment: full `backend/tests` suite **226 passed, 15
subtests passed, zero skips, one existing Starlette TestClient deprecation warning**
in 29.60 s, with OMP/OPENBLAS/MKL threads capped at 2 and normal local networking.
Both pilot formats are included as optional read-only local-asset regressions;
portable synthetic software fixtures also cover both bit depths, mono/dual-mono,
stereo admission, unchanged sources, spatial exclusion, replay/freeze behavior
and lossless-conversion leakage. No synthetic research recordings were added.
Protected development audio/labels, docs/metrics.*, config.py and pipeline.py
match HEAD byte-for-byte. Complete collection preflight remains exit 2: pending
no independent recordings. No commit or push was performed.
