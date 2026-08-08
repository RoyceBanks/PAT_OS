"""
PAT OS Health_check.py

Tests PAT's major systems after installation.
"""

from __future__ import annotations

import sys
import uuid

import numpy as np
import sounddevice as sd

from brain.ai import ask_ai
from brain.memory import (
    delete_memory,
    get_memory,
    save_memory,
)
from config import (
    MIC_CHANNELS,
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
)
from voice.speak import speak


# ==========================================================
# DISPLAY
# ==========================================================

def print_header(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def passed(message: str) -> None:
    print(f"[PASS] {message}")


def failed(message: str) -> None:
    print(f"[FAIL] {message}")


# ==========================================================
# PYTHON
# ==========================================================

def test_python() -> bool:
    """Verify the Python runtime."""

    print_header("Python")

    version = sys.version_info

    version_text = (
        f"{version.major}."
        f"{version.minor}."
        f"{version.micro}"
    )

    print(f"Python: {version_text}")

    if version >= (3, 11):
        passed("Python runtime")
        return True

    failed("Python 3.11 or newer is required.")
    return False


# ==========================================================
# AI
# ==========================================================

def test_ai() -> bool:
    """Send a small request through PAT's AI brain."""

    print_header("PAT AI")

    print("Sending test request to PAT...")

    try:
        response = ask_ai(
            "Reply with only these words: PAT AI OK"
        )

        print(f"Response: {response}")

        if not response:
            failed("AI returned an empty response.")
            return False

        lowered = response.lower()

        error_phrases = (
            "encountered an error",
            "could not contact",
            "connection refused",
        )

        if any(
            phrase in lowered
            for phrase in error_phrases
        ):
            failed("PAT AI connection")
            return False

        passed("PAT AI responded.")
        return True

    except Exception as error:
        failed(f"PAT AI error: {error}")
        return False


# ==========================================================
# MEMORY
# ==========================================================

def test_memory() -> bool:
    """Perform a temporary memory write/read/delete test."""

    print_header("PAT Memory")

    test_key = (
        "_pat_health_check_"
        + uuid.uuid4().hex
    )

    test_value = "memory system operational"

    try:
        save_success, save_message = save_memory(
            test_key,
            test_value,
        )

        if not save_success:
            failed(
                f"Memory write failed: {save_message}"
            )
            return False

        recalled_value = get_memory(test_key)

        if recalled_value != test_value:
            failed(
                "Memory read did not match "
                "the value that was written."
            )

            delete_memory(test_key)
            return False

        delete_success, delete_message = delete_memory(
            test_key
        )

        if not delete_success:
            failed(
                f"Memory cleanup failed: "
                f"{delete_message}"
            )
            return False

        passed("Memory write/read/delete")
        return True

    except Exception as error:
        failed(f"Memory test error: {error}")
        return False


# ==========================================================
# MICROPHONE
# ==========================================================

def test_microphone() -> bool:
    """Verify PAT can access the microphone."""

    print_header("Microphone")

    try:
        device = sd.query_devices(
            MIC_DEVICE,
            "input",
        )

        device_name = device.get(
            "name",
            "Unknown microphone",
        )

        print(f"Input device: {device_name}")
        print("Recording a short microphone test...")

        frame_count = int(
            MIC_SAMPLE_RATE * 0.5
        )

        recording = sd.rec(
            frame_count,
            samplerate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
            dtype="int16",
            device=MIC_DEVICE,
        )

        sd.wait()

        if recording.size == 0:
            failed("Microphone returned no audio data.")
            return False

        audio = recording.astype(np.float32)

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(audio)
                )
            )
        )

        print(f"Microphone level: {rms:.1f}")

        passed("Microphone access")
        return True

    except Exception as error:
        failed(f"Microphone error: {error}")
        return False


# ==========================================================
# VOICE
# ==========================================================

def test_voice() -> bool:
    """Verify PAT can generate and play speech."""

    print_header("PAT Voice")

    print("PAT should speak now.")

    try:
        success, message = speak(
            "PAT voice system operational."
        )

        if not success:
            failed(message)
            return False

        passed("Text to speech")
        return True

    except Exception as error:
        failed(f"Voice error: {error}")
        return False


# ==========================================================
# HEALTH TEST
# ==========================================================

def run_health_check() -> bool:
    """Run PAT's complete basic health check."""

    print()
    print("=" * 60)
    print(f"PAT OS v{VERSION}")
    print("System Health Check")
    print("=" * 60)

    results = {
        "Python": test_python(),
        "AI": test_ai(),
        "Memory": test_memory(),
        "Microphone": test_microphone(),
        "Voice": test_voice(),
    }

    print_header("Health Summary")

    passed_count = 0

    for name, result in results.items():

        if result:
            passed(name)
            passed_count += 1
        else:
            failed(name)

    total = len(results)

    print()
    print(
        f"Systems passed: "
        f"{passed_count}/{total}"
    )

    if passed_count == total:
        print()
        print("All tested PAT systems are operational.")

    else:
        print()
        print(
            "One or more PAT systems "
            "need attention."
        )

    print()
    
    return passed_count == total

if __name__ == "__main__":
    run_health_check()