"""
==========================================================
PAT OS v0.1
config.py

Global configuration file for PAT OS.
Edit settings here instead of changing them throughout
the codebase.
==========================================================
"""

from pathlib import Path

# ==========================================================
# PROJECT PATHS
# ==========================================================

ROOT_DIR = Path(__file__).parent

DATA_DIR = ROOT_DIR / "data"
MODEL_DIR = ROOT_DIR / "models"
SOUND_DIR = ROOT_DIR / "sounds"
LOG_DIR = ROOT_DIR / "logs"

# Create folders if they don't exist
for folder in [DATA_DIR, MODEL_DIR, SOUND_DIR, LOG_DIR]:
    folder.mkdir(exist_ok=True)

# ==========================================================
# ASSISTANT
# ==========================================================

ASSISTANT_NAME = "PAT"

WAKE_WORD = "hey pat"

VERSION = "0.1.0"

DEBUG = True

# ==========================================================
# AI SETTINGS
# ==========================================================

USE_LOCAL_AI = True

OLLAMA_MODEL = "pat"

SYSTEM_PROMPT = """
You are PAT.

PAT stands for Personal AI Technician.

You are intelligent, calm, friendly, concise,
and helpful.

You assist with computer tasks,
answer questions,
control the operating system,
and remember information.
"""

# ==========================================================
# VOICE
# ==========================================================

VOICE_ENABLED = True

VOICE_NAME = "en_US-lessac-medium"

VOICE_RATE = 1.0

VOICE_VOLUME = 1.0

# ==========================================================
# SPEECH RECOGNITION
# ==========================================================

MIC_SAMPLE_RATE = 16000

MIC_CHANNELS = 1

MIC_DEVICE = None

# ==========================================================
# WAKE WORD
# ==========================================================

WAKEWORD_MODEL = MODEL_DIR / "hey_pat.onnx"

WAKE_THRESHOLD = 0.50

# ==========================================================
# MEMORY
# ==========================================================

MEMORY_DATABASE = DATA_DIR / "memory.db"

MAX_MEMORY_RESULTS = 10

# ==========================================================
# AUTOMATION
# ==========================================================

ALLOW_MOUSE_CONTROL = True

ALLOW_KEYBOARD_CONTROL = True

ALLOW_SYSTEM_COMMANDS = True

# ==========================================================
# CAMERA
# ==========================================================

DEFAULT_CAMERA = 0

CAMERA_WIDTH = 1280

CAMERA_HEIGHT = 720

# ==========================================================
# LOGGING
# ==========================================================

LOG_FILE = LOG_DIR / "pat.log"

LOG_LEVEL = "INFO"

# ==========================================================
# STARTUP
# ==========================================================

STARTUP_SOUND = SOUND_DIR / "startup.wav"

WAKE_SOUND = SOUND_DIR / "wake.wav"

SHUTDOWN_SOUND = SOUND_DIR / "shutdown.wav"

# ==========================================================
# INTERNET
# ==========================================================

CHECK_FOR_UPDATES = False

ENABLE_WEB_SEARCH = True

# ==========================================================
# SECURITY
# ==========================================================

OWNER_NAME = "Technician"

VOICE_LOCK = False

FACE_RECOGNITION = False