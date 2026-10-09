# EchoTrace — project brief (source of truth across sessions)

Solo build at Hacktoberfest Hack Day Bengaluru (IEEE RIT), track: Healthcare, well-being & public services.
Hard deadline: working live demo by 18:00 on 2026-10-09. Fresh build: all code written in this repo; never read/copy from other folders.
Work phase by phase. At the end of each phase: commit + push to origin/main, give exact PowerShell verify commands and expected output, then STOP until the user says "next". Claude cannot hear the mic: anything involving live audio must come with a script the user runs and reports back on.

## Collaboration rules (from the user, 2026-10-09 ~12:00; binding)
- A teammate builds frontend/, README.md and pitch/ in parallel against a mock server on :8000 that follows the
  WS contract below. NEVER create or edit files in frontend/, README.md or pitch/.
- Keep the WS contract below EXACTLY as written. If it must change: stop and ask the user first.
- FastAPI server runs on port 8000 with exactly the listed endpoints and serves frontend/dist as static files.
- Always `git pull --rebase` before `git push`.

## Progress
- [x] Phase 0 — Setup
- [~] Phase 1 — Hearing (PANNs live): code + tests done and pushed. Guided run #1 (topk_20261009_111505) was
      UNUSABLE for tuning: test sounds never rose above the room (max level -34.8 dBFS was in BACKGROUND; IMPACT
      loudest -39 dBFS; no alarm-like label at all; Speech ~0.9 every step; 86 ms/hop suggests CPU). Tunables left
      unchanged on purpose. Added per-step verdicts + r = redo, --save-wav, attempt/model_device CSV columns.
      Guided run #2 (topk_20261009_113628, cuda, gain +20, window 1.0; NO wav was saved despite the plan):
      background music + talking (Music ~0.92, Speech ~0.9). Results: GLASS HEARD (Glass 0.71, Breaking 0.51,
      Shatter 0.43). IMPACT/KNOCK loud (+16/+17 dB) but heard as Hammer 0.35 / Chop 0.51 / Basketball bounce 0.56.
      DISTRESS clip heard as Neigh/Horse 0.74 (bad clip). ALARM clip heard as Wind chime/Chime (not a beeping
      detector). FOOTSTEPS too quiet (+2.4 dB). Tuned: IMPACT += Hammer, Chop; IMPACT on/off 0.20/0.10
      (config.CATEGORY_THRESHOLDS). Window/gain unchanged: no WAV, so no offline sweep possible.
      NEXT: short rerun `--guided --steps FOOTSTEPS,IMPACT,DISTRESS,ALARM --save-wav`, then sweep window 1.0/2.0 x
      gain 0/6/12/20 offline on that WAV and retune.

      Guided run #3 (topk_20261009_115300, full 8 steps, again NO wav): IMPACT HEARD 0.37 (new config), ALARM HEARD
      0.45 (Beep, bleep 0.71 is the top alarm-ish label but is NOT in ALARM yet - candidate), GLASS HEARD 0.78.
      FOOTSTEPS loud (+19.8 dB) but heard as Fireworks 0.86 / Chop 0.78 (clip). DISTRESS still Neigh/Horse (clip).
      KNOCK +11 dB not recognised. CHATTER clean.

## Localization findings (for calibrate_direction.py / Phase 2)
- Run #3: LEFT steps FOOTSTEPS +7.1 (sd 0.5), GLASS +7.7 (sd 0.35); RIGHT steps IMPACT -8.0 (sd 0.5), KNOCK -7.0.
  Strongly confirms raw positive lag = LEFT on this laptop -> default calibration sign maps positive raw lag to LEFT.
- Run #2 GCC-PHAT loud-hop medians: RIGHT = IMPACT -5.6 (sd 0.4), DISTRESS -6.8, KNOCK -6.2; CENTRE = ALARM -0.7;
  LEFT = FOOTSTEPS +6.0 (but only +2.4 dB over room, may be a background source). So with the current channel order,
  NEGATIVE lag = RIGHT on this laptop (to be confirmed by calibration).
- GLASS on the LEFT gave -5.5 (sd 0.4) with channel corr collapsing to 0.15: most likely SPATIAL ALIASING. With
  d = 6.5 cm, frequencies above c/2d ~ 2.6 kHz give a second peak inside +/-9.1 samples; glass energy ~4 kHz has a
  ~11.4-sample period and +6 - 11.4 = -5.4. Phase 2: cap/weight the GCC band below ~2.6-3 kHz (config.GCC_BAND_HZ)
  and verify on a recorded glass clip.
- CNN14 timing in the user's runs: 60-85 ms/hop even on cuda (10 ms in Claude's test). Fine for 0.5 s hops; maybe GPU
  power state. Latency metric (Phase 5) must be measured on the demo setup.

## Findings so far
- WDM-KS "Microphone Array 2" index moves (17 -> 11 within an hour): always resolve by name.
- Quiet-ish room channel corr ~0.92 (not 0.73); a steady talker gave a stable GCC-PHAT lag (~-6 samples, sd 0.1-0.3),
  so real sources do separate the channels.
- CPU CNN14 returns garbage for digitally perfect input (pure tones / exact silence): log-mel hits its -100 dB amin
  floor. GPU hides it (TF32 noise). Fixed with a fixed -100 dBFS dither in tagging.prepare (config.TAGGER_DITHER_DBFS).
- GPU CNN14 ~10 ms per 1 s window in the live loop.
- PowerShell 5.1 mangles quotes in `python -c "..."`: use script files. Git Bash here has no coreutils.
- [x] Phase 2 — Connecting (core logic): Analyzer/Pipeline, all three sources, calibrate_direction.py, run_pipeline.py.
      Message semantics within the unchanged contract (tell the frontend teammate):
      * a `sequence` message is RE-SENT with the same id every time its cluster gains an event (upsert by id);
        pattern is a template name, "ISOLATED_EVENT" (single event) or "NONE" (unmatched cluster)
      * events are emitted when they END (or every MAX_EVENT_S = 2 s for long sounds, e.g. walking)
      * status every 1 s of stream time + after every event; latency_ms = 0.0 until the first event is sent
      * SIMULATED: no model runs; status.model_device reports "cpu", device "simulated scenario", host_api "none"
      * angle_deg: + = RIGHT, - = LEFT (after calibration); null when the zone is UNKNOWN for lack of audio
      Post-live-run update (12:33 run, now tests/fixtures/live_run_20261009_1233.json + test_regression_live_run.py):
      * patterns live in config.PATTERNS (editable); added BREAKIN_ALARM (GLASS->IMPACT->ALARM, 15 s, RED) and
        GLASS_IMPACT (15 s, AMBER); matcher = state machine finding the ordered subsequence in a growing sequence
      * a sequence alerts ONCE per escalation (GREEN->AMBER->RED); later events update the same id, never
        downgrade, and the why-list says "N later event(s) added ... without a new alert"; Analyzer.alerts = the
        alert log (use it for metrics, not sequence updates)
      * why-lines / summaries / trajectory group consecutive same-category events (majority zone per group;
        footsteps keep per-event movement)
      * ALARM += "Beep, bleep"; LOC_MIN_VOTE 0.6; calibrate_direction.py refuses sd > 2.5, non-opposite sides,
        |offset| > 2, CENTRE mismatch. Current backend/calibration.json (12:30) kept: offset -0.23 OK, but its
        sd 7.7/6.6 would fail the new checks -> recalibrate.
      * SimSource scenarios: demo | breakin | all (default all = 120 s loop); run_pipeline.py writes
        recordings/run_*_events.jsonl (metadata only) for future fixtures
- [x] Phase 3 — Serving: api/server.py (Engine + create_app), scripts/serve.py (one command), scripts/ws_print.py.
      REST shapes match the teammate's frontend/mock/mock-server.mjs: /api/status = status data (+ extras mode,
      error, tagger, running, clients, calibration); /api/mode GET/POST -> {source,t,wall,device,file,scenario};
      POST body {source, device?, file?, scenario?}; /api/events = plain array; /api/reset -> {..meta, ok:true};
      /api/metrics = docs/metrics.json or {}; errors {"error": ...} (400 bad input, 409 device failure -> stays on
      previous mode, 503 CNN14 unavailable); CORS *. WS sends a snapshot on connect (status, last 50 events,
      current sequences). Ids are prefixed per mode session ("m2-e1", "m2-s1"). / serves frontend/dist (SPA
      fallback, picked up without restart) or a placeholder. Startup: LIVE by default, falls back to SIMULATED
      (labelled, error shown in /api/status) if the mic can't open.
      OPEN QUESTION for the user/teammate: the mock uses angle_deg + = LEFT; the backend uses + = RIGHT.
- [x] Phase 4 — Dashboard (frontend/): React 18 + Vite 5 + TS, plain CSS. src/useEchoTrace.ts (WS + reconnect,
      upsert by id, clears on session-prefix/source change), components StatusBanner, Controls, AcousticMap,
      SequencePanel (+detail), Timeline, LiveMeters, MetricsPanel. `npm run build` -> frontend/dist (gitignored;
      a fresh clone must build once). Dev: `npm run dev` on :5173 proxies /api + /ws to 127.0.0.1:8000.
      Verified by screenshots via Edge DevTools protocol at 1366x768 and 1920x1080 (no page scroll).
      13:40 "no events in LIVE dashboard" report: NOT reproducible - serve.py LIVE + dashboard rendered events from
      a speaker beep (ALARM 0.41-0.56, latency ~31 ms). Added a category-score strip (score, 4 s peak, threshold) to
      LiveMeters so sub-threshold sounds are visible. frontend/src/labels.ts CATEGORY_THRESHOLD mirrors config.py -
      keep them in sync. C: drive was FULL (0 GB free; ~7 GB in pip/npm caches the user can purge).
- [x] Phase 5 — Proof + fallback (user took over eval from Person C). recordings/eval/*.wav (10 x 25 s, committed)
      + labels/*.json (ground truth as PERFORMED, never edited to match the model). backend/echotrace/eval/metrics.py
      (pure maths, tested) + scripts/eval.py -> docs/metrics.json (agreed shape + extras) and docs/metrics.md.
      Result 14:37: 7/10 clips (70%), false alerts EchoTrace 0 vs baseline 19 on 5 non-incident clips (all clips
      3 vs 49), L/C/R 76% (37/49, 10 UNKNOWN). Failures = detection misses, NOT correlation: breakin_02 (glass +
      alarm not heard), breakin_03 (book drop not detected before the alarm), demo_backup (impact max 0.12 < 0.20).
      NO thresholds were tuned on the eval set (user's honesty rule: ask first, show before/after).
      Latency null: no recordings/run_*_events.jsonl yet (run run_pipeline.py --source live, then re-run eval).
      RECORDED mode: loops in real time with RECORDED_LOOP_GAP_S silence; bare names resolve in recordings/eval/.
      demo_backup.wav does NOT go RED (impact missed); breakin_01.wav does (verified through serve.py).
      Dashboard MetricsPanel renders null latency as "0 ms" (Math.round(null)) - frontend fix pending user OK.
      docs/backend_readme_section.md for Person B's README.
- [ ] Phase 6 — Open-source polish

## What EchoTrace is
Open-weight, fully local AI that turns environmental sound into situational awareness for emergency responders, firefighters, industrial-safety teams and smart-building operators, for when cameras can't see (smoke, darkness, blind spots). Existing audio AI labels sounds one at a time. EchoTrace:
1. DETECTS acoustic events with PANNs (CNN14, pretrained on AudioSet, 527 classes)
2. LOCALIZES each event approximately to LEFT / CENTRE / RIGHT using GCC-PHAT + TDOA on a 2-channel mic (signal processing, not ML)
3. CORRELATES events across time and space into sequences (temporal event graph)
4. RAISES explainable GREEN / AMBER / RED alerts with deterministic plain-language summaries

Complements CCTV; never replaces it. Tagline: "PANNs hears. EchoTrace connects."

DEMO: repeatable 4-sound sequence into the live mic (phone speaker ~1 m left/centre/right of the laptop):
FOOTSTEPS (LEFT) -> FOOTSTEPS (CENTRE) -> IMPACT (RIGHT) -> DISTRESS (RIGHT).
Dashboard labels each sound with time + confidence, places it L/C/R, links them into ONE sequence ("Possible correlated acoustic sequence, moving towards RIGHT") and explains why.

METRICS vs a CLASSIFICATION-ONLY BASELINE (alerts whenever any single concerning label crosses threshold):
sequence-recognition accuracy, false-alert reduction, L/C/R accuracy, end-to-end latency.

## Known environment facts (verified; design for them)
- Windows 11, PowerShell. System Python is 3.14 — do NOT use. Use `py -3.12 -m venv backend\.venv`.
- torch CUDA 12.8 wheel (`--index-url https://download.pytorch.org/whl/cu128`) works on RTX 4050 Laptop GPU. CPU must still work (auto-detect, `--cpu`). CNN14 ≈ 12 ms / 1 s window on GPU, ≈ 46 ms on CPU.
- No `wget`. panns_inference shells out to wget for `Cnn14_mAP=0.431.pth` and `class_labels_indices.csv` in `~/panns_data/`. BOTH ALREADY PRESENT (weights 327,428,481 bytes; CSV 14,675 bytes, 527 classes). download_weights.py detects valid files and skips; if downloading, RESUME partial files (HTTP 206; Zenodo drops connections), retry, never delete partials. `--check` flag.
- MIC: built-in Intel array. Device name containing "Microphone Array 2" (fallback "Microphone Array 1") via **Windows WDM-KS** host API ONLY.
  - WASAPI/MME versions go through voice processing: channels merged (corr ~0.9996, lag 0), sounds suppressed → unusable.
  - WDM-KS: genuine stereo (corr ~0.73). 48 kHz only (44.1/96 rejected); 2 channels. Exclusive — close other apps.
- Select devices by NAME SUBSTRING (indices change with Bluetooth headset). Prefer host API order: WDM-KS first.
- Mic spacing d = 0.065 m. Max delay ≈ ±9.1 samples @ 48 kHz; CENTRE zone (|angle| < 20°) ≈ ±3.1 samples. GCC-PHAT needs sub-sample precision: zero-padded IFFT upsampling (~8x) + parabolic peak interpolation.
- No hardware gain: quiet room ≈ -56 dBFS. Configurable TAGGER_GAIN_DB applied before tagging (NOT before localization).
- list_devices.py hides loopback endpoints ("Stereo Mix", "PC Speaker").

## Hard constraints
- No proprietary/cloud AI API, no generative LLM. Summaries template-based, deterministic.
- Model: PANNs CNN14 via `panns_inference` (code MIT; weights CC BY 4.0 from Zenodo — attribute in README). No training/fine-tuning.
- Stack: Python 3.12, PyTorch, FastAPI, uvicorn, WebSockets, sounddevice, numpy, scipy. Frontend: React + Vite + TypeScript, plain CSS, no heavy UI lib. Optional SQLite only if time allows.
- Privacy: local inference only; store event metadata; raw audio saved only when explicitly recording a test clip.
- Ethics wording (UI + summaries): RED = "potentially significant sequence", never "confirmed emergency". No identity tracking — only "possible acoustic trajectory". Every event shows confidence; every alert shows why.
- SOURCE HONESTY: every message and UI screen carries source mode LIVE | RECORDED | SIMULATED. Never show simulated/recorded as live (always-visible badge; SIMULATED has distinct warning colour).
- Modular pipeline (tagger, localizer, correlator swappable behind small interfaces). MIT licence. All tunables in one config.py.
- Simple and robust over clever.

## Architecture
```
echotrace/ (repo root)
  backend/
    echotrace/
      config.py               # rates, window/hop, gain, thresholds, mic spacing, device names, category map, pattern settings
      schemas.py              # Pydantic WS contract
      audio/sources.py        # LiveMicSource (sounddevice, WDM-KS, 48k, 2ch; callback only enqueues + counts drops), WavReplaySource (real-time paced), SimSource (scripted synthetic events, no model)
      tagging/panns_tagger.py # rolling 48k stereo window -> downmix -> gain -> resample_poly to 32k (whole window) -> CNN14 clipwise; window 1.0 s (cfg 2.0), hop 0.5 s; warm-up
      tagging/categories.py   # AudioSet label NAMES -> categories; resolve at startup, fail loudly with "did you mean"
      detection/debounce.py   # per-category hysteresis (on ~0.30, off ~0.15, N-of-M) -> events t_start/t_end/peak conf
      localization/gcc_phat.py  # GCC-PHAT on raw 48k stereo, energy-gated frames near onset, band-limited, upsampled + parabolic, lags ±max_lag; angle = arcsin(clip(c*tau/d)); majority vote
      localization/zones.py   # angle -> LEFT/CENTRE/RIGHT, sign/offset from calibration JSON, UNKNOWN if channels identical / low confidence
      correlation/graph.py    # events = nodes; link to recent events within ~8 s; zone progression = "possible acoustic trajectory"
      correlation/patterns.py # MOVEMENT_IMPACT_DISTRESS: FOOTSTEPS+ -> IMPACT -> DISTRESS => RED
                              # IMPACT_DISTRESS: IMPACT -> DISTRESS => AMBER
                              # ALARM_EVACUATION: ALARM -> several FOOTSTEPS => AMBER
                              # GLASS_INTRUSION: GLASS -> FOOTSTEPS => AMBER
                              # isolated single event => GREEN (logged, no alert) = false-alert reduction vs baseline
      risk/engine.py          # current risk + decay to GREEN after quiet time
      risk/summary.py         # deterministic text, e.g. "14:02:11 - Footsteps heard moving LEFT -> CENTRE, followed 1.2 s later by an impact on the RIGHT (71%) and a possible distress vocalisation on the RIGHT (54%). Pattern: movement -> impact -> distress. Status RED: potentially significant sequence - verify."
      baseline.py             # classification-only baseline alerter (metrics)
      pipeline.py             # audio -> queue -> inference thread -> debounce -> localize -> correlate -> risk -> asyncio broadcast (call_soon_threadsafe); drop stale windows if behind + report
      api/server.py           # FastAPI: WS /ws; GET /api/status; GET/POST /api/mode {source, device?, file?}; GET /api/events; POST /api/reset; GET /api/metrics; serves built frontend
    scripts/  download_weights.py, list_devices.py, live_topk.py, record_clip.py, calibrate_direction.py, eval.py, ws_print.py
    tests/
  frontend/   (React + Vite + TS)
  recordings/ (demo clips + labels/*.json ground truth; topk logs)
  docs/
  README.md, LICENSE (MIT), .gitignore
```

CATEGORIES (AudioSet display names; verify in CSV; category score = max over members; tuned after Phase 1):
- FOOTSTEPS: "Walk, footsteps", "Run"
- IMPACT: "Thump, thud", "Slam", "Bang", "Smash, crash", "Knock"
- DISTRESS: "Screaming", "Yell", "Crying, sobbing", "Shout", "Groan", "Whimper"
- ALARM: "Smoke detector, smoke alarm", "Fire alarm", "Alarm", "Siren", "Buzzer"
- GLASS: "Glass", "Shatter", "Breaking"
- DOOR: "Door", "Sliding door", "Cupboard open or close"

## WebSocket contract (Pydantic in schemas.py + TS in frontend/src/types.ts)
All messages `{type, data}`. Every data has `source` ("LIVE"|"RECORDED"|"SIMULATED"), `t` (monotonic s since session start), `wall` (ISO).
- frame: `{top:[{label,p}] (5), categories:{FOOTSTEPS:p,...}, rms_db:[l,r]}`
- event: `{id, t_start, t_end, category, label, confidence, zone:"LEFT"|"CENTRE"|"RIGHT"|"UNKNOWN", angle_deg|null}`
- sequence: `{id, event_ids, pattern, risk:"GREEN"|"AMBER"|"RED", explanation:[str], summary, trajectory:[zone,...]}`
- status: `{risk, latency_ms, device, host_api, sample_rate, channels, localization:"ON"|"OFF", model_device:"cpu"|"cuda", dropped_blocks}`
latency_ms = capture of the audio block that triggered the event -> WS send time.

GET /api/metrics returns docs/metrics.json AS-IS (no rewriting; extra keys pass through), or {} if missing
(invalid JSON -> {"error": ...}). docs/metrics.json is written by Person C's eval in this shape
(Pydantic `Metrics` in schemas.py; TS type in frontend should mirror it):
```
{"generated_at": str (ISO), "clips": int (number of clips),
 "sequence_accuracy": float, "false_alerts": {"echotrace": int, "baseline": int, "reduction_pct": float},
 "lcr_accuracy": float, "latency_ms": {"mean": float, "p95": float},
 "per_clip": [{"clip": str, "expected": str, "got": str, "ok": bool}]}
```

## Ownership (from the user)
- 2026-10-09 ~13:00: Person B stopped; Claude now builds frontend/ (Phase 4). Keep frontend/mock/ + "mock" script.
- Person B: README.md. Person C: backend/echotrace/eval/, backend/scripts/eval.py, docs/.
  pitch/ is not ours either. Never create or edit files there.
- Offline entry point for eval: `echotrace.pipeline.run_wav(path, tagger=None, *, force_cpu=False,
  calibration=None, start_wall=None, keep_frames=True) -> list[dict]` (all WS messages, source RECORDED,
  faster than real time, deterministic, latency not measured) and `run_wav_detailed(...) -> (messages, analyzer)`
  (analyzer.events / .alerts = EchoTrace alerts, one per escalation / .baseline.alerts / .sequences).
  CNN14 is cached per process (`default_tagger()`).
- Eval data: recordings/eval/*.wav is committed (exception to the *.wav ignore); recordings/eval/labels/*.json too.
- All capture/latency timestamps use time.perf_counter() (time.monotonic() ticks every ~15.6 ms on Windows).

## Phases
**PHASE 0 — Setup**: scaffold, requirements.txt, .gitignore, MIT LICENSE, CLAUDE.md, venv (py -3.12). download_weights.py (detect existing; --check), list_devices.py (WDM-KS first; mark 48k x 2ch; hide loopbacks; check channels distinct). Commit + push.

**PHASE 1 — Hearing**: tagging/ + LiveMicSource + scripts/live_topk.py: `--device --window --hop --gain --cpu`; header (device, host API, rate, channels, cpu/cuda, window, hop); every hop: per-channel meter, top-5, category scores (* for >= 0.30); `--log` writes all 527 probs per hop to recordings/topk_*.csv; `--guided` test script with prompts + 5 s get-ready gaps (not counted), `n` skips a step: BACKGROUND 20 s, FOOTSTEPS, IMPACT (thud/book drop), DISTRESS (scream clip), ALARM (clip), GLASS (clip), KNOCK, CHATTER (should trigger nothing); on finish/Ctrl+C: per-category max/mean/hops>=0.30, top-10 labels overall, per-step breakdown. scripts/record_clip.py (48k stereo 24-bit WAV; warn if channels identical). Tests: category names resolve; resampling shape/frequency; windowing; device picking; CNN14 smoke test on generated WAV. After the user's guided test: read CSV logs, tune CATEGORIES, thresholds, TAGGER_GAIN_DB. Commit + push.

**PHASE 2 — Connecting** (unit-testable without mic): debounce, gcc_phat + zones, graph, patterns, risk engine, summary, baseline, pipeline wired to all three sources. SimSource emits scripted demo sequence + distractor single events, tagged SIMULATED. Tests: hysteresis merges/splits; GCC-PHAT recovers sub-sample + integer delays (noise, clicks) with correct L/C/R at d=6.5 cm; demo sequence -> one RED sequence with correct explanation; isolated events -> GREEN while baseline alerts; summaries deterministic. Localization OFF (zones UNKNOWN, status says so) if channels identical or mono; classification + correlation keep working. scripts/calibrate_direction.py (LEFT then RIGHT) -> calibration JSON sign/offset. Commit + push.

**PHASE 3 — Serving**: FastAPI + WS broadcast + REST + runtime source switching (LIVE / RECORDED wav / SIMULATED); ws_print.py; one command starts everything. Commit + push.

**PHASE 4 — Dashboard** (dark ops console, projector-readable): StatusBanner (big risk + cautious wording + always-visible SOURCE badge + latency + localization ON/OFF); AcousticMap (top-down room, mic pair at bottom, L/C/R zones, dots by category fading ~15 s, arrows for active sequence trajectory); Timeline (lane per category, last 60 s, bars w/ confidence, sequence links); DetailPanel (click sequence -> pattern, risk, summary, why list, contributing events w/ time/conf/zone); Live meters (per-channel level + top-5); Controls (source switcher Live/Replay/Sim, reset; WS auto-reconnect); MetricsPanel (/api/metrics). Vite proxy in dev; backend serves build. Commit + push.

**PHASE 5 — Proof + fallback**: recordings/labels/*.json + scripts/eval.py replays labelled WAVs through the SAME pipeline (faster than real time): sequence-recognition accuracy, false alerts EchoTrace vs baseline (+ % reduction), L/C/R accuracy, latency mean/p95 (from a real-time run). Writes docs/metrics.json + markdown table. Negative clips (lone door slam, lone footsteps, chatter). Fallback ladder, one click each: LIVE -> RECORDED demo clip -> SIMULATED (labelled). Commit + push.

**PHASE 6 — Polish**: README (problem, mermaid pipeline, Windows setup, demo, record + evaluate, metrics table, ethics & limitations — zones only, front/back ambiguity, 6.5 cm array, noisy rooms, supplements responders; troubleshooting — WDM-KS exclusivity, Windows audio enhancements, Bluetooth headset; attribution — Kong et al. 2020 PANNs, qiuqiangkong/audioset_tagging_cnn MIT, panns_inference, Zenodo weights CC BY 4.0, AudioSet). Fresh clone must run from README. Commit + push.

## Conventions
- Run backend scripts from `backend\` with the venv python: `backend\.venv\Scripts\python.exe`.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
