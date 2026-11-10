# Preserved development evidence discrepancies — investigation checklist

No new development replay, counterfactual experiment or held-out inference was run during collection preparation. Original metrics remain immutable. The distinction is **58 total upstream detections** in the fresh reproduction versus **56 in the archive**; the fresh localization denominator is still 56 labelled-category emitted events. Do not subtract events or change thresholds to make totals agree.

## Known observations

- docs/metrics.json: totals.events_detected=56, baseline_alerts=56, echotrace_alerts=7; DOOR thresholds .20/.10; localization UNKNOWN=1, low_wrong=7.
- docs/research/verification/development-reproduction.json: metrics.totals.events_detected=58, baseline_alerts=56, echotrace_alerts=7; profile uses high DOOR .08/.04; UNKNOWN=0, low_wrong=8.
- Extra DOOR events in fresh `per_event`: breakin_02/e1, 3.0–3.5 s, confidence .142; glass_impact_01/e3, 7.0–7.5 s, .135. DOOR is outside baseline concerning categories and original localization labels. Config difference is a concrete investigation lead, not a proved complete causal explanation.
- After excluding the two extra DOOR events solely for category-order alignment, glass_impact_01 first IMPACT (fresh e2, 3.5–4.5 s, confidence .385, Hammer) is low-confidence CENTRE; archived detail says IMPACT@UNKNOWN. Ground truth RIGHT means either output is wrong. Raw archived confidence/timestamps/frame votes/calibration are absent, so one cannot prove identity or cause solely from this alignment. Do not alter its label.

## Exact existing evidence to inspect

1. **docs/metrics.json**: thresholds, sensitivity, gain_db, totals, lcr, per_clip_detail, comparison. Also docs/metrics.md for the original human narrative.
2. **docs/research/verification/development-reproduction.json**: metrics, profile, per_event, sha256, environment, comparison_to_archive. This retains model/config/source identities and exact fresh event times/confidence.
3. **docs/research/verification/evidence-differences.json**: explicit category-order alignment and two added DOOR events.
4. **docs/research/verification/development-eval.txt** and **development-reproduction.txt**: exact CPU replay logs; **commands.md** for commands and --no-write safeguards.
5. **docs/research/verification/environment-final.json**, **requirements-resolved.txt**, **integrity.json**: fresh package versions/model hashes and immutable original audio/labels/config/pipeline checks. **collection-config-check.json** and **collection-integrity.json** capture preparation-time checks.
6. For the October run, recover the original checkout/revision, command line, unrounded per-hop score log (including DOOR), emitted raw events, package freeze, model/label hashes and backend/calibration.json or explicit absence. They are not supplied by current archived summaries. This is an evidence blocker, not a reason to guess a cause.

## Read-only configuration checks (no model loading)

From repository root:

```sh
backend/.venv/bin/python backend/scripts/research_integrity.py
PYTHONPATH=backend backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path
from echotrace import config
old = json.loads(Path('docs/metrics.json').read_text())
new = json.loads(Path('docs/research/verification/development-reproduction.json').read_text())
print('archived thresholds:', old['thresholds'])
print('fresh replay thresholds:', new['profile']['thresholds'])
print('current high thresholds:', {c:config.thresholds(c,'high') for c in config.CATEGORIES})
print('current default profile:', config.SENSITIVITY)
print('calibration file:', config.CALIBRATION_FILE, 'exists:',config.CALIBRATION_FILE.exists())
print('default calibration:',config.DEFAULT_CAL_SIGN, config.DEFAULT_CAL_OFFSET)
print('localization settings:',{k:getattr(config,k) for k in ['GCC_BAND_HZ','LOC_MIN_PEAK','LOC_MIN_VOTE','LOC_LOW_VOTE','LOC_FRAME','LOC_FRAME_HOP','LOC_MAX_FRAMES']})
print('gain:',config.tagger_gain_db('high'))
print('fresh source hashes:',new['sha256'])
PY
git log --oneline -- backend/echotrace/config.py backend/echotrace/detection/debounce.py backend/echotrace/localization/zones.py backend/echotrace/localization/gcc_phat.py backend/echotrace/pipeline.py backend/scripts/eval.py
git diff --exit-code HEAD -- backend/echotrace/config.py backend/echotrace/pipeline.py docs/metrics.json docs/metrics.md recordings/eval
```

After recovering an actual archived revision, inspect it with `git show <archived-revision>:backend/echotrace/config.py` and compare thresholds, category mapping, debounce settings, localization parameters and default calibration to fresh snapshot hashes. Do not assume HEAD is the archived evaluation revision. Confirm calibration-file presence separately: this ignored file cannot be reconstructed from a clean Git checkout. Check identical-channel detection, raw segment bounds, GCC peaks and vote shares if archived event-level evidence is recovered. Check model/label/audio identities and software/CPU configuration before asserting numeric-library effects. These checks distinguish hypotheses; no causal result has been established.

Any future counterfactual replay belongs to explicitly labelled development investigation, with new exclusive output paths and immutable original evidence. It is not part of this collection-preparation task and must never use test data to choose settings.
