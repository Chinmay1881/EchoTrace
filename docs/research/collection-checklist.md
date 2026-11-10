# Ordered 36-clip capture checklist

Planned takes only; these rows are not recordings or completed annotations. All takes target 30 s (accepted 25–35 s). L/C/R are the positions of successive physical sources, never predicted zones. See collection-protocol.md for the finalized rubric and collection-workflow.md for commands.

| # | WAV stem | Intended sounds | Proxy risk | Source positions |
|---:|---|---|---|---|
| 1 | s01_take01_gi_l | GLASS>IMPACT | AMBER | L>L |
| 2 | s01_take02_isolated_glass_l | GLASS | GREEN | L |
| 3 | s01_take03_ba_l | GLASS>IMPACT>ALARM | RED | L>L>L |
| 4 | s01_take04_alarm_glass_l | ALARM>GLASS | GREEN | L>R |
| 5 | s01_take05_quiet | background | GREEN | none |
| 6 | s01_take06_gi_c | GLASS>IMPACT | AMBER | C>C |
| 7 | s01_take07_isolated_impact_c | IMPACT | GREEN | C |
| 8 | s01_take08_ba_c | GLASS>IMPACT>ALARM | RED | C>C>C |
| 9 | s01_take09_impact_alarm_c | IMPACT>ALARM | GREEN | C>L |
| 10 | s01_take10_speech | speech | GREEN | known positions |
| 11 | s01_take11_glass_speech_l | GLASS+speech | GREEN | L |
| 12 | s01_take12_isolated_alarm_r | ALARM | GREEN | R |
| 13 | s02_take01_ba_r | GLASS>IMPACT>ALARM | RED | R>R>R |
| 14 | s02_take02_fan | fan | GREEN | none |
| 15 | s02_take03_gi_r | GLASS>IMPACT | AMBER | R>R |
| 16 | s02_take04_isolated_door_l | DOOR | GREEN | L |
| 17 | s02_take05_kitchen_l | GLASS>IMPACT>ALARM | GREEN | L>C>R |
| 18 | s02_take06_speech_fan | speech+fan | GREEN | known positions |
| 19 | s02_take07_ba_l_move | GLASS>IMPACT>ALARM | RED | L>R>L |
| 20 | s02_take08_isolated_glass_r | GLASS | GREEN | R |
| 21 | s02_take09_gi_l_move | GLASS>IMPACT | AMBER | L>R |
| 22 | s02_take10_alarm_glass_r | ALARM>GLASS | GREEN | R>L |
| 23 | s02_take11_glass_speech_r | GLASS+speech | GREEN | R |
| 24 | s02_take12_isolated_impact_l | IMPACT | GREEN | L |
| 25 | s03_take01_gi_c_move | GLASS>IMPACT | AMBER | C>L |
| 26 | s03_take02_outdoor | distant outdoor background | GREEN | none |
| 27 | s03_take03_ba_c_move | GLASS>IMPACT>ALARM | RED | C>L>R |
| 28 | s03_take04_isolated_alarm_l | ALARM | GREEN | L |
| 29 | s03_take05_impact_alarm_r | IMPACT>ALARM | GREEN | R>C |
| 30 | s03_take06_dishes | dishes | GREEN | C |
| 31 | s03_take07_gi_r_move | GLASS>IMPACT | AMBER | R>C |
| 32 | s03_take08_isolated_door_r | DOOR | GREEN | R |
| 33 | s03_take09_ba_r_move | GLASS>IMPACT>ALARM | RED | R>C>L |
| 34 | s03_take10_kitchen_r | GLASS>IMPACT>ALARM | GREEN | R>L>C |
| 35 | s03_take11_background_second | room background | GREEN | none |
| 36 | s03_take12_cupboard | DOOR+household noise | GREEN | L |

For each row: verify a fresh filename; confirm the session setup/physical side marks; log context before capture; manually capture 30 s; inspect format and listening quality without a classifier; retain any failed take with a reason and use a new replacement take ID recorded in the checklist **before inference**; annotate actual sound intervals, physical positions, provenance and incidents; obtain blind annotation review. Do not edit a planned GREEN take to AMBER/RED after model output. If a replacement ID is needed, update the external capture log and prespecified checklist before locking; preserve this original checklist version and hashes.

Session s01: first setup. Session s02: different day or documented second setup. Session s03: another day/position, second room if available. Every setup uses two separate microphone channels at 48 kHz PCM_24 and fixed gain. Use source distance 1–2 m and record the measured value. No source positions are assigned to diffuse background; any incidental target event must be localized by the collection log or independently observed geometry, otherwise resolve it before admission.

Every file requires: session, room, device/spacing/orientation, actual capture time/timezone, processing/app settings, dropped-block/overflow status, source provenance, annotator/reviewer, human timing and zone labels. Positive takes require exactly one staged proxy incident; all negative takes require incidents=[]. The entire plan has 6 AMBER, 6 RED and 24 GREEN takes.
