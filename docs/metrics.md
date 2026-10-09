# EchoTrace evaluation

Generated 2026-10-09T14:40:52 by `backend/scripts/eval.py` on 10 labelled clips (`recordings/eval/`), replayed through the same pipeline as live mode.

**Across 10 clips: 70% sequence accuracy, 76% L/C/R accuracy, EchoTrace raised 0 false alerts vs 19 for the classification-only baseline (-100%), latency not measured in this run.**

| Metric | EchoTrace | Classification-only baseline |
|---|---|---|
| Sequence recognition accuracy (risk + pattern) | 70% | n/a (no sequences) |
| False alerts on 5 non-incident clips | 0 | 19 |
| False-alert reduction | 100.0% | |
| Total alerts, all clips | 3 | 49 |
| L/C/R accuracy (49 events, 10 UNKNOWN counted wrong) | 76% | n/a |
| Latency mean / p95 | not measured | |

## Per clip

| Clip | Expected | Got | Events (category@zone) | EchoTrace alerts | Baseline alerts | OK |
|---|---|---|---|---|---|---|
| background_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| breakin_01 | BREAKIN_ALARM/RED | BREAKIN_ALARM/RED | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@UNKNOWN, IMPACT@RIGHT, ALARM@CENTRE, ALARM@CENTRE | 2 | 7 | yes |
| breakin_02 | BREAKIN_ALARM/RED | NONE/GREEN | IMPACT@CENTRE, IMPACT@UNKNOWN, IMPACT@UNKNOWN, IMPACT@UNKNOWN, IMPACT@CENTRE, IMPACT@UNKNOWN | 0 | 6 | **no** |
| breakin_03 | BREAKIN_ALARM/RED | NONE/GREEN | GLASS@LEFT, GLASS@LEFT, ALARM@CENTRE, IMPACT@UNKNOWN, GLASS@LEFT | 0 | 5 | **no** |
| chatter_01 | NONE/GREEN | NONE/GREEN | - | 0 | 0 | yes |
| demo_backup | BREAKIN_ALARM/RED | NONE/GREEN | GLASS@LEFT, GLASS@LEFT, ALARM@CENTRE, ALARM@CENTRE | 0 | 4 | **no** |
| glass_impact_01 | GLASS_IMPACT/AMBER | GLASS_IMPACT/AMBER | GLASS@LEFT, IMPACT@UNKNOWN, GLASS@UNKNOWN, GLASS@UNKNOWN, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, IMPACT@RIGHT | 1 | 8 | yes |
| lone_alarm_01 | NONE/GREEN | NONE/GREEN | ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE, ALARM@CENTRE | 0 | 11 | yes |
| lone_glass_01 | NONE/GREEN | NONE/GREEN | GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT, GLASS@LEFT | 0 | 7 | yes |
| lone_thud_01 | NONE/GREEN | NONE/GREEN | IMPACT@UNKNOWN | 0 | 1 | yes |

## Failed clips (why)

- **breakin_02**: labelled GLASS, ALARM not detected (no event above threshold), so the BREAKIN_ALARM chain could not form; got NONE/GREEN
- **breakin_03**: all labelled categories detected, but not in the labelled order within the pattern's gap limit (detected order: GLASS -> GLASS -> ALARM -> IMPACT -> GLASS); got NONE/GREEN
- **demo_backup**: labelled IMPACT not detected (no event above threshold), so the BREAKIN_ALARM chain could not form; got NONE/GREEN

## Detection per category (labelled events with at least one detection)

| Category | Detected / labelled |
|---|---|
| GLASS | 5 / 6 |
| IMPACT | 5 / 6 |
| ALARM | 4 / 5 |

## How it is measured

- *Expected/Got*: pattern/risk. Got = the highest risk any EchoTrace alert reached in the clip; no alert = NONE/GREEN.
- *EchoTrace alerts*: risk step-ups of a sequence (GREEN->AMBER, AMBER->RED); later events do not re-alert.
- *Baseline alerts*: one alert per detected IMPACT, DISTRESS, ALARM or GLASS event (what a plain audio classifier would raise). Both see the same detected events.
- *L/C/R accuracy*: detected events of a labelled category whose zone matches the label.
- *Latency*: no live-run logs with events (recordings/run_*_events.jsonl); latency not measured.

**Limitations:** Small self-recorded dataset (10 x 25 s clips), one room, one laptop microphone array (6.5 cm spacing), clips played from a phone; LEFT/CENTRE/RIGHT zones only (no front/back); FOOTSTEPS and DISTRESS are not yet reliable and are not part of this set.
