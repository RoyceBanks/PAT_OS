"""
PAT OS v0.2
config.py

Central configuration for PAT OS.
"""

from pathlib import Path


# ==========================================================
# PROJECT PATHS
# ==========================================================

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "data"
MODEL_DIR = ROOT_DIR / "models"
SOUND_DIR = ROOT_DIR / "sounds"
LOG_DIR = ROOT_DIR / "logs"

# Create required folders automatically.
for folder in (
    DATA_DIR,
    MODEL_DIR,
    SOUND_DIR,
    LOG_DIR,
):
    folder.mkdir(parents=True, exist_ok=True)


# ==========================================================
# ASSISTANT
# ==========================================================

ASSISTANT_NAME = "PAT"
VERSION = "0.2.0"
DEBUG = True


# ==========================================================
# AI SETTINGS
# ==========================================================

USE_LOCAL_AI = True
OLLAMA_MODEL = "pat"

SYSTEM_PROMPT = """
You are PAT.

PAT stands for Personal AI Technician.

You are intelligent, calm, friendly, concise, and helpful.

You assist with computer tasks, answer questions, control
approved operating-system functions, and remember information.

Never claim that you completed an action unless PAT's software
confirmed that the action succeeded.
""".strip()


# ==========================================================
# VOICE OUTPUT
# ==========================================================

SPEECH_MAX_CHARS = 500
SPEECH_MAX_SENTENCES = 4
VOICE_ENABLED = True
VOICE_NAME = "en_US-lessac-medium"

VOICE_DIR = MODEL_DIR / "voices"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

VOICE_MODEL = VOICE_DIR / f"{VOICE_NAME}.onnx"
VOICE_CONFIG = VOICE_DIR / f"{VOICE_NAME}.onnx.json"

# Your current speak.py does not use this setting yet.
VOICE_VOLUME = 1.0


# ==========================================================
# SPEECH RECOGNITION
# ==========================================================

MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1
MIC_DEVICE = None

STT_MODEL = "base.en"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"
STT_LANGUAGE = "en"
STT_BEAM_SIZE = 5
# Maximum time allowed for one command.
COMMAND_MAX_SECONDS = 12.0

# How long PAT waits for you to begin speaking.
COMMAND_START_TIMEOUT = 5.0

# Stop recording after this much silence.
COMMAND_SILENCE_SECONDS = 1.2

# Microphone volume considered speech.
# Lower = more sensitive; higher = less sensitive.
COMMAND_SILENCE_THRESHOLD = 300.0

COMMAND_CHUNK_SIZE = 1024

# ==========================================================
# WAKE PHRASE PROTOTYPE
# ==========================================================

WAKE_PHRASE = "hey pat"

# A smaller model keeps wake-phrase checks faster.
WAKE_MODEL = "tiny.en"
WAKE_DEVICE = "cpu"
WAKE_COMPUTE_TYPE = "int8"

WAKE_SAMPLE_RATE = 16000
WAKE_CHANNELS = 1
WAKE_MIC_DEVICE = None

# Number of seconds recorded during each listening window.
WAKE_LISTEN_SECONDS = 2.0


# ==========================================================
# MEMORY
# ==========================================================

MEMORY_DATABASE = DATA_DIR / "memory.db"
MAX_MEMORY_RESULTS = 10
REMINDER_DATABASE = DATA_DIR / "reminders.db"

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
# SOUNDS
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

# ==========================================================
# BROWSER / WEB
# ==========================================================

SEARCH_ENGINE_URL = "https://duckduckgo.com/"