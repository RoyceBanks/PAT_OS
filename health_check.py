"""
PAT OS Health Check

Non-destructive system health tests for PAT OS.
"""

from __future__ import annotations

import sqlite3
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import sounddevice as sd
from audio.audio_manager import audio_manager
from automation.clipboard import (
    clear_clipboard,
    get_clipboard,
    set_clipboard,
)
from automation.file_manager import SAFE_LOCATIONS
from automation.process_controls import (
    resolve_safe_process_application,
)
from automation.process_monitor import get_system_usage
from automation.system_controls import get_volume_percent
from automation.window_controls import (
    close_window,
    focus_window,
    maximize_window,
    minimize_window,
    show_desktop,
)
from brain.ai import ask_ai
from brain.memory import (
    delete_memory,
    get_memory,
    save_memory,
)
from brain.session_context import (
    clear_pending_action,
    get_pending_action,
    pending_action_expired,
    remember_pending_action,
)
from config import (
    MIC_CHANNELS,
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
    REMINDER_DATABASE,
    VERSION,
)
from internet.search import search_internet
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

        recalled_value = get_memory(
            test_key
        )

        if recalled_value != test_value:
            failed(
                "Memory read did not match "
                "the value that was written."
            )

            delete_memory(
                test_key
            )
            return False

        delete_success, delete_message = (
            delete_memory(
                test_key
            )
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

        try:
            delete_memory(
                test_key
            )
        except Exception:
            pass

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

        print(
            f"Input device: {device_name}"
        )

        print(
            "Recording a short microphone test..."
        )

        was_listening = audio_manager.is_listening

        success, message = audio_manager.start_input()

        if not success:
            failed(
                f"Could not start microphone: {message}"
            )
            return False

        try:
            audio_manager.flush_input()

            recording = audio_manager.read_seconds(
                0.5,
                timeout=2.0,
            )

        finally:
            # Don't shut the microphone down if another
            # PAT component already had it running.
            if not was_listening:
                audio_manager.stop_input()

        if (
            recording is None
            or recording.size == 0
        ):
            failed(
                "Microphone returned no audio data."
            )
            return False

        audio = recording.astype(
            np.float32
        )

        rms = float(
            np.sqrt(
                np.mean(
                    np.square(
                        audio
                    )
                )
            )
        )

        print(
            f"Microphone level: {rms:.1f}"
        )

        passed("Microphone access")
        return True

    except Exception as error:
        failed(
            f"Microphone error: {error}"
        )
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
        failed(
            f"Voice error: {error}"
        )
        return False


# ==========================================================
# REMINDERS
# ==========================================================

def test_reminders() -> bool:
    """
    Verify PAT's reminder database exists
    and its SQLite schema is readable.
    """

    print_header("Reminder System")

    try:
        database_path = Path(
            REMINDER_DATABASE
        )

        print(
            f"Database: {database_path}"
        )

        if not database_path.exists():
            failed(
                "Reminder database does not exist."
            )
            return False

        connection = sqlite3.connect(
            str(database_path)
        )

        try:
            result = connection.execute(
                "PRAGMA quick_check"
            ).fetchone()

            if (
                not result
                or result[0].lower() != "ok"
            ):
                failed(
                    "Reminder database integrity check failed."
                )
                return False

            table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name = 'reminders'
                """
            ).fetchone()

            if table is None:
                failed(
                    "Reminder table was not found."
                )
                return False

        finally:
            connection.close()

        passed(
            "Reminder database and schema"
        )
        return True

    except Exception as error:
        failed(
            f"Reminder system error: {error}"
        )
        return False


# ==========================================================
# INTERNET / RESEARCH
# ==========================================================

def test_internet_research() -> bool:
    """
    Verify the internet/research modules are available.

    This test does not perform a live internet request so
    temporary network failures do not break the health check.
    """

    print_header("Internet / Research")

    try:
        if not callable(
            search_internet
        ):
            failed(
                "Internet search function is unavailable."
            )
            return False

        try:
            import internet.fetch
            import internet.research

        except Exception as error:
            failed(
                f"Research module import failed: {error}"
            )
            return False

        passed(
            "Search, fetch, and research modules"
        )
        return True

    except Exception as error:
        failed(
            f"Internet/research error: {error}"
        )
        return False


# ==========================================================
# WINDOWS AUDIO
# ==========================================================

def test_windows_audio() -> bool:
    """
    Verify PAT can read Windows master-volume state.

    Volume is not changed.
    """

    print_header("Windows Audio Controls")

    try:
        success, message = (
            get_volume_percent()
        )

        print(message)

        if not success:
            failed(
                "Windows audio control"
            )
            return False

        passed(
            "Windows audio access"
        )
        return True

    except Exception as error:
        failed(
            f"Windows audio error: {error}"
        )
        return False


# ==========================================================
# WINDOW MANAGEMENT
# ==========================================================

def test_window_management() -> bool:
    """
    Verify window-control functions are available.

    No windows are moved, minimized, closed,
    or otherwise changed.
    """

    print_header("Window Management")

    try:
        functions = (
            focus_window,
            minimize_window,
            maximize_window,
            close_window,
            show_desktop,
        )

        if not all(
            callable(function)
            for function in functions
        ):
            failed(
                "One or more window functions "
                "are unavailable."
            )
            return False

        passed(
            "Window management module"
        )
        return True

    except Exception as error:
        failed(
            f"Window management error: {error}"
        )
        return False


# ==========================================================
# CLIPBOARD
# ==========================================================

def test_clipboard() -> bool:
    """
    Verify clipboard functions are available.

    PAT does not read, print, clear, or replace
    the user's clipboard during this test.
    """

    print_header("Clipboard")

    try:
        functions = (
            get_clipboard,
            set_clipboard,
            clear_clipboard,
        )

        if not all(
            callable(function)
            for function in functions
        ):
            failed(
                "One or more clipboard functions "
                "are unavailable."
            )
            return False

        passed(
            "Clipboard control module"
        )
        return True

    except Exception as error:
        failed(
            f"Clipboard error: {error}"
        )
        return False


# ==========================================================
# FILE MANAGER
# ==========================================================

def test_file_manager() -> bool:
    """
    Verify PAT's approved file locations.

    No files or folders are created, modified,
    moved, renamed, or deleted.
    """

    print_header("File Manager")

    try:
        if not SAFE_LOCATIONS:
            failed(
                "No approved file locations "
                "are configured."
            )
            return False

        print(
            f"Approved locations: "
            f"{len(SAFE_LOCATIONS)}"
        )

        existing = 0

        for name, path in SAFE_LOCATIONS.items():
            status = (
                "OK"
                if Path(path).exists()
                else "Missing"
            )

            print(
                f"{name}: {path} [{status}]"
            )

            if Path(path).exists():
                existing += 1

        if existing == 0:
            failed(
                "None of PAT's approved "
                "file locations exist."
            )
            return False

        passed(
            "Safe file location mapping"
        )
        return True

    except Exception as error:
        failed(
            f"File manager error: {error}"
        )
        return False


# ==========================================================
# PROCESS MONITORING
# ==========================================================

def test_process_monitoring() -> bool:
    """
    Verify PAT can read system/process information.

    No processes are closed or changed.
    """

    print_header("Process Monitoring")

    try:
        success, message = (
            get_system_usage()
        )

        print(message)

        if not success:
            failed(
                "Process/system monitoring"
            )
            return False

        safe_test = (
            resolve_safe_process_application(
                "firefox"
            )
        )

        if safe_test != "firefox":
            failed(
                "Safe process allowlist "
                "resolution failed."
            )
            return False

        unsafe_test = (
            resolve_safe_process_application(
                "svchost"
            )
        )

        if unsafe_test is not None:
            failed(
                "Unsafe process was unexpectedly "
                "approved for closing."
            )
            return False

        passed(
            "Process monitoring and safety allowlist"
        )
        return True

    except Exception as error:
        failed(
            f"Process monitoring error: {error}"
        )
        return False


# ==========================================================
# CONFIRMATION SAFETY
# ==========================================================

def test_confirmation_safety() -> bool:
    """
    Verify pending-action storage and expiration.

    No real destructive action is executed.
    """

    print_header("Confirmation Safety")

    try:
        clear_pending_action()

        remember_pending_action(
            action_type="health_check_test",
            payload=None,
            description=(
                "Temporary health-check action"
            ),
            timeout_seconds=0.05,
        )

        pending = get_pending_action()

        if pending is None:
            failed(
                "Pending action could not be stored."
            )
            return False

        if pending_action_expired():
            failed(
                "Pending action expired too early."
            )
            clear_pending_action()
            return False

        time.sleep(
            0.08
        )

        if not pending_action_expired():
            failed(
                "Pending action did not expire."
            )
            clear_pending_action()
            return False

        clear_pending_action()

        if get_pending_action() is not None:
            failed(
                "Pending action could not be cleared."
            )
            return False

        passed(
            "Confirmation storage, timeout, and cleanup"
        )
        return True

    except Exception as error:
        clear_pending_action()

        failed(
            f"Confirmation safety error: {error}"
        )
        return False


# ==========================================================
# HEALTH CHECK
# ==========================================================

def run_health_check() -> bool:
    """Run PAT OS's complete health check."""

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
        "Reminders": test_reminders(),
        "Internet / Research": test_internet_research(),
        "Windows Audio": test_windows_audio(),
        "Window Management": test_window_management(),
        "Clipboard": test_clipboard(),
        "File Manager": test_file_manager(),
        "Process Monitoring": test_process_monitoring(),
        "Confirmation Safety": test_confirmation_safety(),
    }

    print_header(
        "Health Summary"
    )

    passed_count = 0

    for name, result in results.items():
        if result:
            passed(name)
            passed_count += 1
        else:
            failed(name)

    total = len(
        results
    )

    print()

    print(
        f"Systems passed: "
        f"{passed_count}/{total}"
    )

    if passed_count == total:
        print()
        print(
            "All tested PAT systems "
            "are operational."
        )

    else:
        print()
        print(
            "One or more PAT systems "
            "need attention."
        )

    print()

    return (
        passed_count == total
    )


if __name__ == "__main__":
    run_health_check()