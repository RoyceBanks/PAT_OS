"""
PAT OS v0.6.0
config.py

Central configuration for PAT OS.

This file contains shared settings for PAT's AI, voice,
speech recognition, wake phrase, memory, reminders,
automation, internet access, and future subsystems.
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

# Create required runtime folders automatically.
for folder in (
    DATA_DIR,
    MODEL_DIR,
    SOUND_DIR,
    LOG_DIR,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )


# ==========================================================
# ASSISTANT
# ==========================================================

ASSISTANT_NAME = "PAT"
VERSION = "0.6.0"

# Keep enabled during active development.
DEBUG = True


# ==========================================================
# LOCAL AI
# ==========================================================

USE_LOCAL_AI = True
OLLAMA_MODEL = "pat"

SYSTEM_PROMPT = """
You are PAT.

PAT stands for Personal AI Technician.

You are the user's personal AI computer assistant.

You are calm, capable, friendly, concise, and helpful.

You assist with computer tasks, answer questions, remember
information, perform research through PAT's approved tools,
and control approved operating-system functions.

Never claim that you completed a computer action unless
PAT's software confirmed that the action succeeded.

Never claim that you searched the internet or retrieved
current information unless PAT's web research tools actually
performed the search.

Computer actions must only be performed through PAT's
approved automation tools.

Respond in plain spoken English.

Avoid Markdown, headings, tables, code fences, and bullet
symbols unless the user specifically requests formatted text.
""".strip()


# ==========================================================
# VOICE OUTPUT
# ==========================================================

VOICE_ENABLED = True
VOICE_NAME = "en_US-lessac-medium"

VOICE_DIR = MODEL_DIR / "voices"

VOICE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

VOICE_MODEL = (
    VOICE_DIR
    / f"{VOICE_NAME}.onnx"
)

VOICE_CONFIG = (
    VOICE_DIR
    / f"{VOICE_NAME}.onnx.json"
)

# Reserved for future direct voice-volume control.
VOICE_VOLUME = 1.0


# ==========================================================
# SPOKEN RESPONSE LIMITS
# ==========================================================

# PAT prints the complete answer to the console but limits
# long spoken responses for more natural conversations.

SPEECH_MAX_CHARS = 600
SPEECH_MAX_SENTENCES = 6


# ==========================================================
# SPEECH RECOGNITION
# ==========================================================

MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1

# None tells SoundDevice to use the Windows default device.
MIC_DEVICE = None

STT_MODEL = "base.en"
STT_DEVICE = "cpu"
STT_COMPUTE_TYPE = "int8"
STT_LANGUAGE = "en"
STT_BEAM_SIZE = 5

# Maximum duration of one spoken command.
COMMAND_MAX_SECONDS = 12.0

# Maximum time PAT waits for speech to begin.
COMMAND_START_TIMEOUT = 5.0

# Recording ends after this amount of silence.
COMMAND_SILENCE_SECONDS = 1.2

# Microphone level considered silence.
# Lower values increase sensitivity.
COMMAND_SILENCE_THRESHOLD = 300.0

COMMAND_CHUNK_SIZE = 1024


# ==========================================================
# WAKE PHRASE
# ==========================================================

WAKE_PHRASE = "hey pat"

# PAT currently uses Faster-Whisper for wake phrase
# recognition instead of OpenWakeWord.
WAKE_MODEL = "tiny.en"
WAKE_DEVICE = "cpu"
WAKE_COMPUTE_TYPE = "int8"

WAKE_SAMPLE_RATE = 16000
WAKE_CHANNELS = 1

# None uses the default microphone.
WAKE_MIC_DEVICE = None

# Duration of each wake phrase listening window.
WAKE_LISTEN_SECONDS = 2.0

# Conversation
CONVERSATION_FOLLOW_UP_SECONDS = 4.0
AI_CONVERSATION_TURNS = 10

# ==========================================================
# MEMORY
# ==========================================================

MEMORY_DATABASE = (
    DATA_DIR
    / "memory.db"
)

MAX_MEMORY_RESULTS = 10


# ==========================================================
# REMINDERS
# ==========================================================

REMINDER_DATABASE = (
    DATA_DIR
    / "reminders.db"
)


# ==========================================================
# AUTOMATION
# ==========================================================

# These settings describe which categories of automation
# PAT is allowed to use.

ALLOW_MOUSE_CONTROL = True
ALLOW_KEYBOARD_CONTROL = True
ALLOW_SYSTEM_COMMANDS = True


# ==========================================================
# INTERNET / WEB RESEARCH
# ==========================================================

ENABLE_WEB_SEARCH = True

SEARCH_ENGINE_URL = (
    "https://duckduckgo.com/"
)

# Automatic PAT software update checks are not yet enabled.
CHECK_FOR_UPDATES = False


# ==========================================================
# LOGGING
# ==========================================================

LOG_FILE = (
    LOG_DIR
    / "pat.log"
)

LOG_LEVEL = "INFO"


# ==========================================================
# SOUNDS
# ==========================================================

STARTUP_SOUND = (
    SOUND_DIR
    / "startup.wav"
)

WAKE_SOUND = (
    SOUND_DIR
    / "wake.wav"
)

SHUTDOWN_SOUND = (
    SOUND_DIR
    / "shutdown.wav"
)


# ==========================================================
# FUTURE VISION SETTINGS
# ==========================================================

# Reserved for PAT's future vision subsystem.

DEFAULT_CAMERA = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720


# ==========================================================
# SECURITY
# ==========================================================

OWNER_NAME = "Technician"

# Reserved for future authentication systems.
VOICE_LOCK = False
FACE_RECOGNITION = False