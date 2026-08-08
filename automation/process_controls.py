"""
PAT OS
automation/process_controls.py

Controlled process-management functions for PAT.
"""

from __future__ import annotations

import time

import psutil

from automation.process_monitor import PROCESS_ALIASES


FORCE_CLOSE_ALLOWED = {
    "discord",
    "firefox",
    "steam",
    "visual studio code",
    "notepad",
    "calculator",
}


APPLICATION_ALIASES = {
    "vs code": "visual studio code",
    "vscode": "visual studio code",
}


DISPLAY_NAMES = {
    "discord": "Discord",
    "firefox": "Firefox",
    "steam": "Steam",
    "visual studio code": "Visual Studio Code",
    "notepad": "Notepad",
    "calculator": "Calculator",
}


def _canonical_application(
    application: str,
) -> str | None:
    """Resolve an application to an approved process target."""

    application = " ".join(
        application.strip().lower().split()
    )

    application = APPLICATION_ALIASES.get(
        application,
        application,
    )

    if application not in FORCE_CLOSE_ALLOWED:
        return None

    return application


def _get_matching_processes(
    application: str,
) -> list[psutil.Process]:
    """Return processes belonging to an approved application."""

    canonical = _canonical_application(
        application
    )

    if canonical is None:
        return []

    process_names = PROCESS_ALIASES.get(
        canonical,
        (),
    )

    process_names = {
        name.casefold()
        for name in process_names
    }

    matches = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
        ]
    ):
        try:
            name = process.info["name"]

            if (
                name
                and name.casefold()
                in process_names
            ):
                matches.append(
                    process
                )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):
            continue

    return matches


def offer_force_close_if_running(
    application: str,
    wait_seconds: float = 1.5,
) -> tuple[bool, str]:
    """
    Check whether an approved application remains running
    after PAT attempted a normal window close.
    """

    canonical = _canonical_application(
        application
    )

    if canonical is None:
        return False, ""

    if wait_seconds > 0:
        time.sleep(
            wait_seconds
        )

    processes = _get_matching_processes(
        canonical
    )

    if not processes:
        return False, ""

    display_name = DISPLAY_NAMES.get(
        canonical,
        canonical.title(),
    )

    return (
        True,
        (
            f"{display_name} is still running. "
            f"Do you want me to force close it?"
        ),
    )

def force_close_application(
    application: str,
) -> tuple[bool, str]:
    """
    Force-close every process belonging to an approved app.

    This must only be called after explicit user confirmation.
    """

    canonical = _canonical_application(
        application
    )

    if canonical is None:
        return (
            False,
            "That application is not approved for force closing.",
        )

    display_name = DISPLAY_NAMES.get(
        canonical,
        canonical.title(),
    )

    initial_processes = _get_matching_processes(
        canonical
    )

    if not initial_processes:
        return (
            True,
            f"{display_name} is already closed.",
        )

    # Some applications use multiple processes and may
    # briefly respawn a child process while shutting down.
    # Make several controlled passes.
    for _ in range(3):
        processes = _get_matching_processes(
            canonical
        )

        if not processes:
            return (
                True,
                f"Force closed {display_name}.",
            )

        for process in processes:
            try:
                process.kill()

            except psutil.NoSuchProcess:
                continue

            except psutil.AccessDenied:
                continue

            except psutil.ZombieProcess:
                continue

        try:
            psutil.wait_procs(
                processes,
                timeout=1.5,
            )

        except Exception:
            pass

        time.sleep(
            0.3
        )

    # The final result determines success.
    remaining = _get_matching_processes(
        canonical
    )

    if remaining:
        return (
            False,
            (
                f"I tried to force close {display_name}, "
                f"but {len(remaining)} of its processes "
                f"are still running."
            ),
        )

    return (
        True,
        f"Force closed {display_name}.",
    )