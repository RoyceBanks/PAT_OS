"""
PAT OS
automation/system_controls.py

Approved Windows system controls.

Only explicitly defined actions are available.
"""

from __future__ import annotations

import ctypes
from datetime import datetime
from pathlib import Path
import subprocess
import pyautogui
from pycaw.pycaw import AudioUtilities
from config import DATA_DIR




SCREENSHOT_DIR = DATA_DIR / "screenshots"


def volume_up() -> tuple[bool, str]:
    """Increase Windows volume."""

    try:
        pyautogui.press(
            "volumeup",
            presses=2,
            interval=0.05,
        )

        return (
            True,
            "Volume increased.",
        )

    except Exception as error:
        return (
            False,
            f"I could not increase the volume: {error}",
        )


def volume_down() -> tuple[bool, str]:
    """Decrease Windows volume."""

    try:
        pyautogui.press(
            "volumedown",
            presses=2,
            interval=0.05,
        )

        return (
            True,
            "Volume decreased.",
        )

    except Exception as error:
        return (
            False,
            f"I could not decrease the volume: {error}",
        )

def mute_audio() -> tuple[bool, str]:
    """Mute Windows system audio."""

    try:
        volume = _get_endpoint_volume()

        if volume.GetMute():
            return True, "The computer is already muted."

        volume.SetMute(1, None)

        return True, "Computer muted."

    except Exception as error:
        return (
            False,
            f"I could not mute the computer: {error}",
        )


def unmute_audio() -> tuple[bool, str]:
    """Unmute Windows system audio."""

    try:
        volume = _get_endpoint_volume()

        if not volume.GetMute():
            return True, "The computer is already unmuted."

        volume.SetMute(0, None)

        return True, "Computer unmuted."

    except Exception as error:
        return (
            False,
            f"I could not unmute the computer: {error}",
        )

def _get_endpoint_volume():
    """Return the default Windows audio endpoint volume."""

    device = AudioUtilities.GetSpeakers()

    return device.EndpointVolume

def get_volume_percent() -> tuple[bool, str]:
    """Return the current Windows master volume."""

    try:
        volume = _get_endpoint_volume()

        current = round(
            volume.GetMasterVolumeLevelScalar()
            * 100
        )

        return (
            True,
            f"Volume is at {current} percent.",
        )

    except Exception as error:
        return (
            False,
            f"I could not read the volume: {error}",
        )


def set_volume_percent(
    percent: int,
) -> tuple[bool, str]:
    """Set Windows master volume to a percentage."""

    try:
        percent = max(
            0,
            min(100, int(percent)),
        )

        volume = _get_endpoint_volume()

        volume.SetMasterVolumeLevelScalar(
            percent / 100.0,
            None,
        )

        return (
            True,
            f"Volume set to {percent} percent.",
        )

    except Exception as error:
        return (
            False,
            f"I could not set the volume: {error}",
        )

def shutdown_computer() -> tuple[bool, str]:
    """Shut down Windows immediately after PAT confirmation."""

    try:
        subprocess.run(
            [
                "shutdown.exe",
                "/s",
                "/t",
                "0",
            ],
            check=True,
        )

        return (
            True,
            "Shutting down the computer.",
        )

    except Exception as error:
        return (
            False,
            f"I could not shut down the computer: {error}",
        )

def restart_computer() -> tuple[bool, str]:
    """Restart Windows immediately after PAT confirmation."""

    try:
        subprocess.run(
            [
                "shutdown.exe",
                "/r",
                "/t",
                "0",
            ],
            check=True,
        )

        return (
            True,
            "Restarting the computer.",
        )

    except Exception as error:
        return (
            False,
            f"I could not restart the computer: {error}",
        )

def sign_out_computer() -> tuple[bool, str]:
    """Sign the current Windows user out after confirmation."""

    try:
        subprocess.run(
            [
                "shutdown.exe",
                "/l",
            ],
            check=True,
        )

        return (
            True,
            "Signing you out.",
        )

    except Exception as error:
        return (
            False,
            f"I could not sign you out: {error}",
        )

def adjust_volume_percent(
    amount: int,
) -> tuple[bool, str]:
    """Raise or lower Windows volume by a percentage."""

    try:
        volume = _get_endpoint_volume()

        current = round(
            volume.GetMasterVolumeLevelScalar()
            * 100
        )

        target = max(
            0,
            min(100, current + int(amount)),
        )

        volume.SetMasterVolumeLevelScalar(
            target / 100.0,
            None,
        )

        return (
            True,
            f"Volume set to {target} percent.",
        )

    except Exception as error:
        return (
            False,
            f"I could not adjust the volume: {error}",
        )

def lock_computer() -> tuple[bool, str]:
    """Lock the current Windows session."""

    try:
        result = ctypes.windll.user32.LockWorkStation()

        if result == 0:
            return (
                False,
                "Windows did not confirm the lock request.",
            )

        return (
            True,
            "Locking your computer.",
        )

    except Exception as error:
        return (
            False,
            f"I could not lock the computer: {error}",
        )

def take_screenshot() -> tuple[bool, str]:
    """Capture the desktop and save it locally."""

    try:
        SCREENSHOT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        screenshot_path = (
            SCREENSHOT_DIR
            / f"screenshot_{timestamp}.png"
        )

        screenshot = pyautogui.screenshot()

        screenshot.save(
            screenshot_path
        )

        return (
            True,
            f"Screenshot saved as {screenshot_path.name}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not take a screenshot: {error}",
        )


if __name__ == "__main__":
    print("PAT Windows Controls Test")
    print()
    print("1. Volume up")
    print("2. Volume down")
    print("3. Mute")
    print("4. Unmute")
    print("5. Screenshot")
    print()

    choice = input(
        "Select test: "
    ).strip()

    if choice == "1":
        print(volume_up())

    elif choice == "2":
        print(volume_down())

    elif choice == "3":
        print(mute_audio())

    elif choice == "4":
        print(unmute_audio())

    elif choice == "5":
        print(take_screenshot())

    else:
        print("Unknown test.")