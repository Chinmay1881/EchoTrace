"""All EchoTrace tunables live here. Change values here, not in the modules."""

from pathlib import Path

# ---------------------------------------------------------------- paths
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
RECORDINGS_DIR = REPO_DIR / "recordings"
DOCS_DIR = REPO_DIR / "docs"
CALIBRATION_FILE = BACKEND_DIR / "calibration.json"

# ---------------------------------------------------------------- model weights
PANNS_DATA_DIR = Path.home() / "panns_data"
WEIGHTS_FILE = PANNS_DATA_DIR / "Cnn14_mAP=0.431.pth"
WEIGHTS_URL = "https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
WEIGHTS_SIZE = 327_428_481
LABELS_FILE = PANNS_DATA_DIR / "class_labels_indices.csv"
LABELS_URL = "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
LABELS_COUNT = 527

# ---------------------------------------------------------------- audio capture
CAPTURE_RATE = 48_000          # WDM-KS on the Intel array accepts 48 kHz only
CAPTURE_CHANNELS = 2
BLOCK_SIZE = 2_400             # 50 ms blocks
# Preferred input devices, matched by case-insensitive name substring, in order.
DEVICE_NAME_PREFS = ["Microphone Array 2", "Microphone Array 1"]
# Host APIs in order of preference. WASAPI/MME apply voice processing and merge channels.
HOST_API_PREFS = ["Windows WDM-KS", "Windows WASAPI", "Windows DirectSound", "MME"]
REQUIRED_HOST_API = "Windows WDM-KS"
# Endpoints that are speaker loopbacks, never real microphones.
LOOPBACK_NAME_HINTS = ["stereo mix", "pc speaker", "loopback", "what u hear", "wave out"]
# Channels with correlation above this (and ~zero lag) are treated as identical (no localization).
IDENTICAL_CHANNEL_CORR = 0.995

# ---------------------------------------------------------------- tagging
MODEL_RATE = 32_000
WINDOW_S = 1.0                 # configurable to 2.0
HOP_S = 0.5
TAGGER_GAIN_DB = 20.0          # applied before tagging only (quiet room ~ -56 dBFS); tuned in Phase 1
TAGGER_DITHER_DBFS = -100.0    # fixed tiny noise floor so digital silence/pure tones stay in-distribution
TOP_K = 5

# ---------------------------------------------------------------- detection (hysteresis)
ON_THRESHOLD = 0.30
OFF_THRESHOLD = 0.15
# Per-category (on, off) overrides. Short transients (a thud) fill only a small part of a 1 s window, so
# CNN14's clip-wise score is diluted: guided run 113628 had IMPACT hits 2 -> 5 going 0.30 -> 0.20 with no
# new triggers in non-impact steps.
CATEGORY_THRESHOLDS: dict[str, tuple[float, float]] = {
    "IMPACT": (0.20, 0.10),
}


def thresholds(category: str) -> tuple[float, float]:
    """(on, off) hysteresis thresholds for a category."""
    return CATEGORY_THRESHOLDS.get(category, (ON_THRESHOLD, OFF_THRESHOLD))


ON_N, ON_M = 1, 2              # N of the last M windows >= ON to open an event
OFF_HOPS = 1                   # consecutive windows < OFF to close it (events are emitted on close)
MAX_EVENT_S = 2.0              # a longer sound is emitted in 2 s pieces (keeps latency bounded; walking
                               # becomes several FOOTSTEPS events, so its trajectory can move)

# ---------------------------------------------------------------- localization
MIC_SPACING_M = 0.065
SPEED_OF_SOUND = 343.0
CENTRE_HALF_ANGLE_DEG = 20.0
GCC_UPSAMPLE = 8
# Guided run #3 localized cleanly with this band (LEFT +7, RIGHT -7..-8, sd ~0.5). Above c/2d ~ 2.6 kHz a
# narrowband source can alias inside +/-9 samples; lower the top edge if calibration shows flipped glass/alarms.
GCC_BAND_HZ = (300.0, 8_000.0)
LOC_FRAME = 1024               # ~21 ms GCC-PHAT frames
LOC_FRAME_HOP = 512
LOC_MAX_FRAMES = 12            # highest-energy frames near the onset that get a vote
LOC_PRE_S = 0.5                # audio before t_start included in the search
LOC_MAX_SPAN_S = 2.5
LOC_MIN_VOTE = 0.6             # winning zone needs at least this share of the (peak-weighted) votes, else UNKNOWN
                               # (live run 12:33: an IMPACT read LEFT and 2 ALARMs read RIGHT among correct ones)
LOC_MIN_PEAK = 0.10            # mean GCC-PHAT peak of the winning frames; below -> UNKNOWN
LOC_CHECK_EVERY_S = 5.0        # how often the channels are re-checked for being identical (-> localization OFF)
AUDIO_RING_S = 15.0            # raw stereo kept in memory for localization (never written to disk)
# Without a calibration file: guided runs #2/#3 showed raw positive lag (right channel later) = LEFT.
# Corrected lag = sign * (raw - offset); corrected positive = RIGHT. calibrate_direction.py overwrites this.
DEFAULT_CAL_SIGN = -1
DEFAULT_CAL_OFFSET = 0.0

# ---------------------------------------------------------------- correlation / risk
LINK_WINDOW_S = 8.0            # events closer than this (end -> start) belong to the same sequence
PATTERN_MAX_GAP_S = 8.0        # default max gap between consecutive matched events of a pattern

# Ordered pattern templates, highest priority first. steps = [(category, min events)]; repeats of a step's
# category are absorbed; unrelated events may be interleaved; consecutive matched events must be within
# max_gap_s (falls back to PATTERN_MAX_GAP_S). A sequence that matches nothing stays GREEN (logged, no alert).
PATTERNS: list[dict] = [
    {"name": "MOVEMENT_IMPACT_DISTRESS", "steps": [("FOOTSTEPS", 1), ("IMPACT", 1), ("DISTRESS", 1)],
     "risk": "RED", "description": "movement -> impact -> distress"},
    {"name": "BREAKIN_ALARM", "steps": [("GLASS", 1), ("IMPACT", 1), ("ALARM", 1)], "max_gap_s": 15.0,
     "risk": "RED", "description": "breaking glass -> impact -> alarm (possible break-in/incident with alarm)"},
    {"name": "IMPACT_DISTRESS", "steps": [("IMPACT", 1), ("DISTRESS", 1)],
     "risk": "AMBER", "description": "impact -> distress"},
    {"name": "ALARM_EVACUATION", "steps": [("ALARM", 1), ("FOOTSTEPS", 2)],
     "risk": "AMBER", "description": "alarm -> movement (possible evacuation)"},
    {"name": "GLASS_INTRUSION", "steps": [("GLASS", 1), ("FOOTSTEPS", 1)],
     "risk": "AMBER", "description": "breaking glass -> movement"},
    {"name": "GLASS_IMPACT", "steps": [("GLASS", 1), ("IMPACT", 1)], "max_gap_s": 15.0,
     "risk": "AMBER", "description": "breaking glass -> impact"},
]
RISK_DECAY_S = 20.0            # quiet time after a sequence's last event before its risk stops counting
CONCERNING = ["IMPACT", "DISTRESS", "ALARM", "GLASS"]   # the baseline alerts on any single one of these

# ---------------------------------------------------------------- RECORDED (backup demo) mode
RECORDED_DEFAULT_CLIP = "demo_backup.wav"   # looked up in recordings/eval/ first
RECORDED_LOOP = True
RECORDED_LOOP_GAP_S = 10.0     # silence between loops so the dashboard visibly resets between runs

# ---------------------------------------------------------------- pipeline
STATUS_EVERY_S = 1.0
MAX_BACKLOG_S = 1.0            # if analysis falls this far behind, skip stale windows (reported as dropped)

# ---------------------------------------------------------------- categories (AudioSet display names)
CATEGORIES: dict[str, list[str]] = {
    "FOOTSTEPS": ["Walk, footsteps", "Run"],
    # Hammer/Chop: what CNN14 actually output for table thuds and knocks in guided run 113628 (0.35 / 0.51),
    # <= 0.07 in every non-impact step. Not added: Basketball bounce (would be shown to users as the event
    # label), Tap (fires on footsteps), Wood / Wood block (no evidence).
    "IMPACT": ["Thump, thud", "Slam", "Bang", "Smash, crash", "Knock", "Hammer", "Chop"],
    "DISTRESS": ["Screaming", "Yell", "Crying, sobbing", "Shout", "Groan", "Whimper"],
    # Beep, bleep: 0.71 on the real smoke-detector clip (run 115300), 0.00 in every BACKGROUND/CHATTER and
    # non-alarm step of all three guided runs.
    "ALARM": ["Smoke detector, smoke alarm", "Fire alarm", "Alarm", "Siren", "Buzzer", "Beep, bleep"],
    "GLASS": ["Glass", "Shatter", "Breaking"],
    "DOOR": ["Door", "Sliding door", "Cupboard open or close"],
}
