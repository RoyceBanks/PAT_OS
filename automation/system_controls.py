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

import pyautogui

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


def toggle_mute() -> tuple[bool, str]:
    """Toggle Windows audio mute."""

    try:
        pyautogui.press(
            "volumemute"
        )

        return (
            True,
            "Toggled mute.",
        )

    except Exception as error:
        return (
            False,
            f"I could not change mute: {error}",
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
    print("3. Toggle mute")
    print("4. Screenshot")
    print()

    choice = input(
        "Select test: "
    ).strip()

    if choice == "1":
        print(volume_up())

    elif choice == "2":
        print(volume_down())

    elif choice == "3":
        print(toggle_mute())

    elif choice == "4":
        print(take_screenshot())

    else:
        print("Unknown test.")