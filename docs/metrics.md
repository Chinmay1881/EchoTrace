# EchoTrace evaluation

Generated 2026-10-09T15:15:12 by `backend/scripts/eval.py` on 10 labelled clips (`recordings/eval/`), replayed through the same pipeline as live mode.

**Sensitivity profile: `high`** (detection thresholds; see the disclosure section below). Tagger gain +20 dB.

**Across 10 self-recorded clips, EchoTrace raised 7 alerts vs 56 for a classification-only baseline; on the 5 no-incident clips, 0 vs 20. Every miss was a detection miss; the correlation logic was correct on everything detected.**

Sequence recognition accuracy 90% (9/10 clips); L/C/R accuracy 71%; latency not measured yet (no live-run log).

| Metric | EchoTrace | Classification-only baseline |
|---|---|---|
| Sequence recognition accuracy (risk + pattern) | 90% | n/a (no sequences) |
| False alerts on 5 non-incident clips | 0 | 20 |
| False-alert reduction | 100.0% | |
| Total alerts, all clips | 7 | 56 |
| L/C/R accuracy (56 events, 14 UNKNOWN counted wrong) | 71% | n/a |
| Latency mean / p95 | not measured | |

## Sensitivity: thresholds were changed after the first evaluation (disclosure)

The first evaluation used the `normal` profile. Because real sounds in the room were often recognised below threshold in live use, the detection thresholds were then lowered (`high` profile, used for the demo). Before adopting it, `high` was checked on speech and silence only: 0 events on the background and chatter clips, and 0 new events in the BACKGROUND/CHATTER steps of three logged guided runs (the highest speech/silence category score was 0.03). The `high` thresholds were nevertheless chosen after seeing the `normal` results on these clips, so these 10 clips are no longer a fully independent test. Both results are shown.

| | `high` (demo) | `normal` |
|---|---|---|
| on/off thresholds | IMPACT 0.12/0.06, others 0.20/0.10 | IMPACT 0.20/0.10, others 0.30/0.15 |
| tagger gain | +20 dB | +20 dB |
| Sequence accuracy | 90% (9/10) | 70% (7/10) |
| L/C/R accuracy | 71% (40/56, 14 UNKNOWN) | 76% (37/49, 10 UNKNOWN) |
| Detection GLASS | 5/6 | 5/6 |
| Detection IMPACT | 6/6 | 5/6 |
| Detection ALARM | 4/5 | 4/5 |
| Alerts on no-incident clips (EchoTrace vs baseline) | 0 vs 20 | 0 vs 19 |
| Alerts on all clips (EchoTrace vs baseline) | 7 vs 56 | 3 vs 49 |
| Clips that fail | breakin_02 | breakin_02, breakin_03, breakin_04 |

## Per clip

| Clip | Expected | Got | Events (category@zone) | EchoTrace alerts | Baseline alerts | OK |
|---|---|---|---|---|---|---|
| background_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| breakin_01 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, IMPACT@UNKNOWN, GLASS@UNKNOWN, IMPACT@RIGHT, ALARM@CENTRE, ALARM@CENTRE | 2 | 8 | yes |
| breakin_02 | BREAKIN_ALARM/RED | NONE/GREEN | IMPACT@UNKNOWN, IMPACT@CENTRE, IMPACT@UNKNOWN, IMPACT@UNKNOWN, IMPACT@UNKNOWN, IMPACT@CENTRE, IMPACT@UNKNOWN | 0 | 7 | **no** |
| breakin_03 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, IMPACT@UNKNOWN, ALARM@CENTRE, ALARM@CENTRE, IMPACT@UNKNOWN, GLASS@LEFT | 2 | 7 | yes |
| breakin_04 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, IMPACT@UNKNOWN, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE | 2 | 6 | yes |
| chatter_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| glass_impact_01 | GLASS_IMPACT/AMBER | GLASS_IMPACT/AMBER | GLASS@LEFT, IMPACT@UNKNOWN, GLASS@UNKNOWN, GLASS@UNKNOWN, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, IMPACT@RIGHT | 1 | 8 | yes |
| lone_alarm_01 | NONE/GREEN | NONE/GREEN | ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE | 0 | 11 | yes |
| lone_glass_01 | NONE/GREEN | NONE/GREEN | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT | 0 | 8 | yes |
| lone_thud_01 | NONE/GREEN | NONE/GREEN | IMPACT@UNKNOWN | 0 | 1 | yes |

## Failed clips (why)

- **breakin_02**: labelled GLASS, ALARM not detected (no event above threshold), so the BREAKIN_ALARM chain could not form; got NONE/GREEN

## Detection per category (labelled events with at least one detection)

| Category | Detected / labelled |
|---|---|
| GLASS | 5 / 6 |
| IMPACT | 6 / 6 |
| ALARM | 4 / 5 |

## How it is measured

- *Expected/Got*: pattern/risk. Got = the highest risk any EchoTrace alert reached in the clip; no alert = NONE/GREEN.
- *EchoTrace alerts*: risk step-ups of a sequence (GREEN->AMBER, AMBER->RED); later events do not re-alert.
- *Baseline alerts*: one alert per detected IMPACT, DISTRESS, ALARM or GLASS event (what a plain audio classifier would raise). Both see the same detected events.
- *L/C/R accuracy*: detected events of a labelled category whose zone matches the label.
- *Latency*: no live-run logs with events (recordings/run_*_events.jsonl); latency not measured.

**Limitations:** Small self-recorded dataset (10 x 25 s clips), one room, one laptop microphone array (6.5 cm spacing), clips played from a phone; LEFT/CENTRE/RIGHT zones only (no front/back); FOOTSTEPS and DISTRESS are not yet reliable and are not part of this set.
