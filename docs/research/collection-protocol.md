# Independent acoustic collection protocol — finalized rubric v1

Status: preparation only; no independent recordings collected or evaluated. Rubric ID: **echotrace-contextual-proxy-v1**. The fixed collection is 36 fresh takes, each 30 seconds (acceptable 25–35 s), across three sessions. The [ordered checklist](collection-checklist.md) and its [CSV](collection-checklist.csv) prescribe IDs, sequences, proxy risks and physical source positions. The [workflow](collection-workflow.md) provides hardware checks, capture, transfer and read-only admission commands.

## Task and ground-truth decision

The primary task for this collection is **staged contextual-proxy incident alarm detection**. AMBER/RED describe a prespecified scripted scene, not evidence of a real emergency. Ground truth comes from the scenario sheet and the human capture/context log before model output is observed. It never comes from whether EchoTrace matched a pattern. We are not collecting real break-ins or verifying real hazard severity.

| Scene family | Takes | Required scenario label | Incident annotation |
|---|---:|---|---|
| Scripted break-in precursor: GLASS then IMPACT | 6 | AMBER staged proxy | Exactly one incident spanning the two causal sounds |
| Scripted break-in with subsequent alarm: GLASS then IMPACT then ALARM | 6 | RED staged proxy | Exactly one incident spanning all three causal sounds; do not create a second incident for AMBER escalation |
| Isolated glass/impact/alarm/door (two of each) | 8 | GREEN routine isolated sound | `incidents: []` |
| Routine alarm then glass | 2 | GREEN unrelated routine sounds | `incidents: []` |
| Routine impact then alarm without glass | 2 | GREEN unrelated routine sounds | `incidents: []` |
| Routine glass plus normal speech, without impact | 2 | GREEN routine activity | `incidents: []` |
| Routine kitchen clink, object placement/drop, timer | 2 | **GREEN even when GLASS→IMPACT→ALARM is audible** | `incidents: []`; annotate all three actual physical sounds |
| Quiet/background | 4 | GREEN | `incidents: []` |
| Normal speech/household activity | 4 | GREEN | `incidents: []` |

The two kitchen scenes are **deliberately confusable contextual negatives**. Their recorded purpose is ordinary meal preparation (glass handling, placing/dropping an object, timer); positive scripts explicitly act the stated staged incident proxy. Log that distinction before capture. A timer's sound alone is not an incident. Do not relabel kitchen scenes RED after a model alert, or relabel a missed positive GREEN. All four alerting systems receive identical labels. Report results by family as well as pooled; kitchen failures are false alarms under this rubric. These labels cannot establish real-world safety recognition: acoustically identical contextual scenes can be impossible for an audio-only system to distinguish. State this limitation prominently in the paper. An acoustic-chain presence analysis, if later added, must be explicitly secondary and must use its own labels/denominator; it cannot replace these incident labels silently.

A positive take that did not enact its required sounds/order is a collection deviation, not an automatic GREEN example. Human review decides admission **without predictions**, logs the deviation, and records a fresh take if necessary. Likewise, an unplanned causal sound in a negative must be documented and adjudicated before locking; never delete or relabel a take after inference. Keep every rejected take outside recordings/test with a reason, timestamp, and replacement ID. Preserve the original schedule and each revision externally. Take counts are planned quotas, not permission to fabricate missing categories.

## Capture design and genuine independence

Use 48,000 Hz, two genuine microphone channels, PCM_24 WAV, fixed gain and recorder orientation per session. No denoising, normalization, edits, channel copying or AGC changes between takes. Disable enhancement/echo cancellation if possible and document unavoidable processing. Changing microphone geometry without adjusting frozen localization parameters is a generalization condition, not a calibrated equivalent device; record actual spacing rather than assuming 6.5 cm.

Capture new physical takes; never copy/crop/resample the ten development WAVs. Prefer fresh directly produced glass handling, ordinary impacts and other safe sounds. Do not break glass, simulate injury or create an emergency. New separately sourced playback is allowed only as **staged playback**, with asset identity, origin, rights, speaker and volume documented. Never call it a naturally occurring incident. Do not reuse any development playback excerpt. Historical development source asset identities may be unavailable: if independence cannot be established, use a newly made direct source/new documented material instead and disclose remaining provenance uncertainty. FOOTSTEPS/DISTRESS are outside this fixed core plan; annotate genuine incidental target sounds but do not invent such sounds to fill categories.

Use three sessions of twelve takes: different days or documented setup changes; a second room if available. Log actual session date/time/timezone, room, noise, recorder, mic spacing/orientation, source positions/distances, gain, app/version and enhancements. Multiple clips from one session are correlated; they are not 36 independent environments.

## Directions and physical sounds

Observer geometry, not GCC-PHAT output, supplies direction. Face the front of the fixed laptop/array. Physical LEFT is the observer's left looking forward from the recorder, CENTRE directly ahead, RIGHT to the right. Mark approximately -45°, 0°, +45° spots at measured 1–2 m distances; signs are only ground-truth coordinates and never inferred from the channel ordering or calibration sign. Do not adjust calibration using held-out predictions. Checklist L/C/R entries refer to successive **sound sources**, not a moving person. Record an actual measured position per sound. Keep sources stationary during each sound; moving-source trajectories are outside this core collection.

Before the held-out session, manually make separate practice LEFT/CENTRE/RIGHT takes outside recordings/test, without inference. Check hardware routing and independent signals, then freeze placement and gain. Settings accepting two channels do not prove two separate microphones; independent noise also does not prove useful TDOA geometry. Confirm hardware specs/routing and inspect practice channel waveforms. Digital mono duplication makes localization invalid. Do not label diffuse background as CENTRE. If an incidental target source cannot be independently located, retain the take/log outside admission while a blind reviewer resolves it or obtain a fresh take; never guess direction from the model. Current event schema requires a known LEFT/CENTRE/RIGHT zone for each labelled target sound.

Each physical sound gets one unique event ID and one independently justified primary target category. If one physical sound could belong to multiple categories, resolve and document the primary category blind to model output; do not duplicate it merely because the classifier emitted multiple categories. Repeated separate impacts are separate physical events. A sustained alarm is one physical event, regardless of emitted detector fragments. Speech is not DISTRESS unless a genuine distress vocalization occurred; this plan uses ordinary speech only. Category labels are the unique categories of all actually annotated physical target events. Quiet/background clips may have no target events.

## Timing and incident annotations

Use 3–5 seconds quiet lead-in, about 2–4 seconds between scripted sounds, and at least 5–8 seconds tail. Preserve the full 30-second take. These are instructions, **not annotation timestamps**. Annotators listen/inspect the original waveform and contemporaneous context log/reference video (with consent) without classifier scores. Timestamp actual acoustic onset and offset in seconds from the first saved sample, to 0.01 s where resolvable. Exclude planned countdown time before file capture. Continuous sounds keep their audible interval; short separate sounds remain separate. Document timing ambiguity in notes and have a second blind reviewer resolve it before freeze. Do not snap times to pipeline hops.

Required event fields: `id`, positive-duration `start_s`, `end_s`, `category`, `zone`. Add physical position/distance and evidence notes. Required incident fields: `id`, `start_s`, `end_s`, `risk`, and unique causal `event_ids`. For each positive, incident start is the earliest causal event onset and end the latest causal event offset (exactly reuse event timestamp values); unrelated background events are not causal. There is one incident per positive script and **none per negative**, even when a negative has multiple sounds. Recording risk is maximum incident risk, or GREEN when none. Preserve one incident when EchoTrace later emits both AMBER and RED; escalation is not a second ground-truth incident. Matching remains the frozen 1-second tolerance and one-to-one assignment; do not enlarge intervals to encompass alerts.

Templates below are deliberately incomplete schema aids, not scientific annotations:

```json
{"id":"<physical-sound-id>","start_s":null,"end_s":null,"category":"<human category>","zone":"<physical LEFT|CENTRE|RIGHT>"}
```

```json
{"id":"<incident-id>","start_s":null,"end_s":null,"risk":"<script AMBER|RED>","event_ids":[]}
```

## Provenance and admission

The QC scaffold supplies measured file hash/duration but leaves human labels/provenance incomplete. Complete each recording in recordings/test/manifest.json, schema_version 1, split independent-test. Required base fields: recording_id, wav, sha256, actual ISO date, source, device, environment, annotator, duration_s, used_for_tuning:false, category_labels, ground_truth_risk, events, incidents.

Collection preflight additionally requires: `rubric_id: echotrace-contextual-proxy-v1`, checklist `scenario` and `session_id`, room_id, capture_app_version, processing_settings, context_log, hardware_qualification (nonempty documented references/descriptions), source_mode (`direct`, `playback`, `mixed`), dropped_blocks and overflows. Both counters must be observed zero; do not fabricate counters for an app that cannot report them. Such a path remains unqualified for this core admission until equivalent capture-integrity diagnostics are available. Playback/mixed additionally requires source_assets objects with nonempty `id`, `origin`, `rights`, `speaker`, `volume`. Hardware qualification refers to separate precollection practice/spec evidence, never predictions. Add reviewer identity and notes, actual time/timezone, physical mic spacing and source distances. Keep context evidence privately when sensitive; a meaningful log reference suffices in the manifest.

Read-only preflight validates format/quality/provenance and manifest consistency; it cannot prove audible truth, real two-microphone geometry or honest independence. A quiet take may be silent, so channel independence must also be established from practice. Human review is mandatory. Full-study readiness requires all 36 planned IDs. Save the rubric/checklist, their hashes, source code/settings/model identities and external session log before capture. The evaluation protocol lock is created only after annotated files are admitted. **Preparation stops here: do not run inference or freeze a test dataset that does not exist.** No threshold, correlation, localization or model changes are authorized by collection results.
