# EchoTrace evaluation

Generated 2026-10-09T15:34:08 by `backend/scripts/eval.py` on 10 labelled clips (`recordings/eval/`), replayed through the same pipeline as live mode.

**Sensitivity profile: `high`** (detection thresholds; see the disclosure section below). Tagger gain +20 dB.

**Across 10 self-recorded clips, EchoTrace raised 7 alerts vs 56 for a classification-only baseline; on the 5 no-incident clips, 0 vs 20. Every miss was a detection miss; the correlation logic was correct on everything detected.**

Sequence recognition accuracy 90% (9/10 clips); L/C/R accuracy 82%; latency not measured yet (no live-run log).

| Metric | EchoTrace | Classification-only baseline |
|---|---|---|
| Sequence recognition accuracy (risk + pattern) | 90% | n/a (no sequences) |
| False alerts on 5 non-incident clips | 0 | 20 |
| False-alert reduction | 100.0% | |
| Total alerts, all clips | 7 | 56 |
| L/C/R accuracy (56 events, 1 UNKNOWN counted wrong) | 82% | n/a |
| ...of which low-confidence zones right / wrong (shown with "?") | 6 / 7 | |
| Latency mean / p95 | not measured | |

## Changes after the first evaluation (disclosure)

Two changes were made **after** seeing earlier results on these same 10 clips, so they are no longer a fully independent test. Every version is re-run from code below.

1. **Sensitivity** (`normal` -> `high`): detection thresholds were lowered because real sounds were often recognised below threshold in live use. Checked first on speech and silence only: 0 events on the background and chatter clips and in the BACKGROUND/CHATTER steps of three logged guided runs (highest speech/silence category score 0.03).
2. **Direction logic** (v1 -> v2): a best-guess zone with 40-60% frame agreement is now reported as *low confidence* instead of UNKNOWN (shown faded with a "?" on the dashboard). Low-confidence zones count as normal predictions in L/C/R accuracy and are also reported separately. An inter-channel level difference (ILD) cue, a 300-3000 Hz GCC band and SNR-weighted voting over more frames were also measured on these clips and **rejected** (no gain, or more confident wrong zones on table impacts).

| | high, direction v2 **(demo)** | normal, direction v1 (first eval) | high, direction v1 |
|---|---|---|---|
| on/off thresholds | IMPACT 0.12/0.06, others 0.20/0.10 | IMPACT 0.20/0.10, others 0.30/0.15 | IMPACT 0.12/0.06, others 0.20/0.10 |
| direction logic | v2: 40-60% vote -> low-confidence zone | v1: UNKNOWN below 60% vote | v1: UNKNOWN below 60% vote |
| Sequence accuracy | 90% (9/10) | 70% (7/10) | 90% (9/10) |
| L/C/R accuracy | 82% (46/56) | 76% (37/49) | 71% (40/56) |
| UNKNOWN zones | 1 | 10 | 14 |
| high-confidence zones right / wrong | 40 / 2 | 37 / 2 | 40 / 2 |
| low-confidence zones right / wrong | 6 / 7 | 0 / 0 | 0 / 0 |
| Detection GLASS | 5/6 | 5/6 | 5/6 |
| Detection IMPACT | 6/6 | 5/6 | 6/6 |
| Detection ALARM | 4/5 | 4/5 | 4/5 |
| Alerts on no-incident clips (EchoTrace vs baseline) | 0 vs 20 | 0 vs 19 | 0 vs 20 |
| Alerts on all clips (EchoTrace vs baseline) | 7 vs 56 | 3 vs 49 | 7 vs 56 |
| Clips that fail | breakin_02 | breakin_02, breakin_03, breakin_04 | breakin_02 |

## Per clip

| Clip | Expected | Got | Events (category@zone) | EchoTrace alerts | Baseline alerts | OK |
|---|---|---|---|---|---|---|
| background_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| breakin_01 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, IMPACT@LEFT, GLASS@LEFT, IMPACT@RIGHT, ALARM@CENTRE, ALARM@CENTRE | 2 | 8 | yes |
| breakin_02 | BREAKIN_ALARM/RED | NONE/GREEN | IMPACT@RIGHT, IMPACT@CENTRE, IMPACT@LEFT, IMPACT@CENTRE, IMPACT@CENTRE, IMPACT@CENTRE, IMPACT@RIGHT | 0 | 7 | **no** |
| breakin_03 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, IMPACT@RIGHT, ALARM@CENTRE, ALARM@CENTRE, IMPACT@CENTRE, GLASS@LEFT | 2 | 7 | yes |
| breakin_04 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, IMPACT@RIGHT, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE | 2 | 6 | yes |
| chatter_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| glass_impact_01 | GLASS_IMPACT/AMBER | GLASS_IMPACT/AMBER | GLASS@LEFT, IMPACT@UNKNOWN, GLASS@LEFT, GLASS@RIGHT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, IMPACT@RIGHT | 1 | 8 | yes |
| lone_alarm_01 | NONE/GREEN | NONE/GREEN | ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE | 0 | 11 | yes |
| lone_glass_01 | NONE/GREEN | NONE/GREEN | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT | 0 | 8 | yes |
| lone_thud_01 | NONE/GREEN | NONE/GREEN | IMPACT@CENTRE | 0 | 1 | yes |

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
