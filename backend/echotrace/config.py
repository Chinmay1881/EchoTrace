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
TOP_K = 5

# ---------------------------------------------------------------- detection (hysteresis)
ON_THRESHOLD = 0.30
OFF_THRESHOLD = 0.15
ON_N, ON_M = 1, 2              # N of the last M windows >= ON to open an event
OFF_HOPS = 2                   # consecutive windows < OFF to close it

# ---------------------------------------------------------------- localization
MIC_SPACING_M = 0.065
SPEED_OF_SOUND = 343.0
CENTRE_HALF_ANGLE_DEG = 20.0
GCC_UPSAMPLE = 8
GCC_BAND_HZ = (300.0, 8_000.0)

# ---------------------------------------------------------------- correlation
LINK_WINDOW_S = 8.0

# ---------------------------------------------------------------- categories (AudioSet display names)
CATEGORIES: dict[str, list[str]] = {
    "FOOTSTEPS": ["Walk, footsteps", "Run"],
    "IMPACT": ["Thump, thud", "Slam", "Bang", "Smash, crash", "Knock"],
    "DISTRESS": ["Screaming", "Yell", "Crying, sobbing", "Shout", "Groan", "Whimper"],
    "ALARM": ["Smoke detector, smoke alarm", "Fire alarm", "Alarm", "Siren", "Buzzer"],
    "GLASS": ["Glass", "Shatter", "Breaking"],
    "DOOR": ["Door", "Sliding door", "Cupboard open or close"],
}
