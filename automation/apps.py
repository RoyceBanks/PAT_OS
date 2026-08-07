"""
PAT OS
automation/apps.py

Safely launches approved Windows applications.
"""

from __future__ import annotations

import re
import os
import shutil
import subprocess
from pathlib import Path


# Add or change applications here.
# PAT will only open programs listed in this dictionary.
APP_PATHS: dict[str, list[str]] = {
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "discord": [
        os.path.expandvars(
            r"%LOCALAPPDATA%\Discord\Update.exe"
        ),
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ],
    "vscode": [
        os.path.expandvars(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
        ),
    ],
    "notepad": [
        "notepad.exe",
    ],
    "calculator": [
        "calc.exe",
    ],
    "file explorer": [
        "explorer.exe",
    ],
    "task manager": [
        "taskmgr.exe",
    ],
}


ALIASES: dict[str, str] = {
    "google": "firefox",
    "browser": "firefox",
    "web browser": "firefox",
    "look up": "firefox",
    "mozilla firefox": "firefox",

    "visual studio code": "vscode",
    "vs code": "vscode",
    "code": "vscode",

    "files": "file explorer",
    "explorer": "file explorer",

    "calc": "calculator",
}

def normalize_app_name(app_name: str) -> str:
    """
    Normalize an application name before looking it up.

    Removes punctuation added by speech recognition.
    """

    cleaned_name = app_name.strip().lower()

    # Remove punctuation from the beginning and end.
    cleaned_name = re.sub(
        r"^[\s.,!?;:'\"]+|[\s.,!?;:'\"]+$",
        "",
        cleaned_name,
    )

    # Replace repeated spaces with one space.
    cleaned_name = " ".join(cleaned_name.split())

    return ALIASES.get(cleaned_name, cleaned_name)


def _launch_discord(executable: str) -> None:
    """Launch Discord through its updater executable."""

    subprocess.Popen(
        [executable, "--processStart", "Discord.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _find_executable(candidates: list[str]) -> str | None:
    """Find the first valid executable from configured candidates."""

    for candidate in candidates:
        expanded = os.path.expandvars(os.path.expanduser(candidate))

        if Path(expanded).exists():
            return expanded

        command_path = shutil.which(expanded)

        if command_path:
            return command_path

    return None


def open_application(app_name: str) -> tuple[bool, str]:
    """
    Open an approved application.

    Returns:
        A tuple containing:
        - True or False for success
        - A message PAT can display or speak
    """

    normalized_name = normalize_app_name(app_name)

    if normalized_name not in APP_PATHS:
        available = ", ".join(sorted(APP_PATHS))

        return (
            False,
            f"I do not have {app_name} configured yet. "
            f"Configured applications are: {available}.",
        )

    executable = _find_executable(APP_PATHS[normalized_name])

    if executable is None:
        return (
            False,
            f"I found {normalized_name} in my configuration, "
            "but I could not locate it on this computer.",
        )

    try:
        if normalized_name == "discord":
            _launch_discord(executable)
        else:
            subprocess.Popen(
                [executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        return True, f"Opening {normalized_name}."

    except OSError as error:
        return False, f"I could not open {normalized_name}: {error}"


if __name__ == "__main__":
    requested_app = input("Application to open: ")
    success, message = open_application(requested_app)

    print(message)
    print(f"Success: {success}")