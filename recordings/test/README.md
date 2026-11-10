# Independent test admission

No independent recordings are supplied. Empty manifest means **pending**, never 0% or 100% accuracy.

Place genuine unseen PCM WAV files here (ignored by Git). Annotate every WAV in manifest.json; validation rejects unlisted WAVs, missing labels, unsafe paths, inconsistent durations/risks, tuning declarations and exact development/within-test duplicates. Container and decoded PCM SHA256 detect exact copies including metadata-only changes; re-encoded, cropped or acoustically similar recordings need manual provenance review. No synthetic research samples are supplied.

Each recording requires: recording_id, relative wav, sha256, source, ISO date (YYYY-MM-DD), device, environment, annotator, duration_s, used_for_tuning:false, category_labels, ground_truth_risk, events, incidents.

Each physical event requires id, start_s, end_s, category (existing EchoTrace category), zone (LEFT/CENTRE/RIGHT). Each incident requires id, start_s, end_s, risk (AMBER/RED). Times are seconds from the WAV start and must fall within its duration. Category labels must equal the categories of annotated physical events. GREEN clips have no incidents; benign combinations may contain multiple timed events. Recording risk is maximum incident risk. Incident intervals should span the genuine incident, independently of model predictions. Keep annotation decisions blind to model output; document ambiguous cases before freezing.

Collect new sources/sessions/devices/environments, including benign multi-event combinations, without tuning on them. Verify source rights and record actual provenance. Do not copy old clips or infer date from filenames or Git history. Do not add audio or model weights to Git.

From repository root:

```sh
python backend/scripts/research_eval.py validate
# After annotation review, installing existing requirements and supplying existing weights/labels:
python backend/scripts/research_eval.py freeze
python backend/scripts/research_eval.py run --run-id initial-independent-test
```

Review/freeze the protocol before observing test predictions. Lock hashes include model/labels if present, source, calibration if present, development inventory inputs and test data. Run requires weights/labels; adding them after freezing produces drift. Freeze after they are available. Never re-freeze in response to results. The lock prevents accidental drift, not deliberate tampering or human test-set leakage. Archive it with the paper.

The finalized collection uses `echotrace-contextual-proxy-v1`. Follow [the ordered 36-take checklist](../../docs/research/collection-checklist.md) and [local capture/transfer workflow](../../docs/research/collection-workflow.md). Both routine kitchen scenarios are GREEN even when their acoustic chain matches a positive; these are explicitly contextual-proxy labels, not actual hazard truth.

Before any future dataset freeze or inference, use the stricter, read-only collection preflight:

```sh
backend/.venv/bin/python backend/scripts/research_validate.py --require-complete
```

This enforces collection format/provenance/scenario rules beyond generic manifest validation. Empty/incomplete collection is not ready. No recordings have been collected as part of preparation.

Research format amendment: original PCM_16 and PCM_24 at 48 kHz are accepted.
Each record defaults to evaluation_mode=localization; explicit non-spatial mode
allows mono/dual-mono with null or omitted event zones. Pilot/development records
remain excluded. See docs/research/collection-workflow.md for exact eligibility,
provenance, format and directional-scoring limitations.
