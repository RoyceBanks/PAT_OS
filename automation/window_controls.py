"""
PAT OS
automation/window_controls.py

Safe Windows desktop window controls.
"""

from __future__ import annotations

import pyautogui
import pygetwindow as gw


WINDOW_ALIASES = {
    "firefox": (
        "firefox",
        "mozilla firefox",
    ),
    "discord": (
        "discord",
    ),
    "steam": (
        "steam",
    ),
    "notepad": (
        "notepad",
    ),
    "visual studio code": (
        "visual studio code",
        "vs code",
    ),
    "vscode": (
        "visual studio code",
        "vs code",
    ),
    "calculator": (
        "calculator",
    ),
    "task manager": (
        "task manager",
    ),
}


def _get_search_names(
    application: str,
) -> tuple[str, ...]:
    """
    Return possible window-title names for an application.
    """

    cleaned = application.strip().lower()

    return WINDOW_ALIASES.get(
        cleaned,
        (cleaned,),
    )


def _find_window(
    application: str,
):
    """
    Find the best matching visible application window.
    """

    search_names = _get_search_names(
        application
    )

    windows = gw.getAllWindows()

    matches = []

    for window in windows:
        title = (
            window.title
            or ""
        ).strip()

        if not title:
            continue

        title_lower = title.lower()

        for name in search_names:
            if name in title_lower:
                matches.append(window)
                break

    if not matches:
        return None

    # Prefer an already active window.
    for window in matches:
        try:
            if window.isActive:
                return window

        except Exception:
            pass

    # Otherwise use the first matching window.
    return matches[0]


def focus_window(
    application: str,
) -> tuple[bool, str]:
    """
    Bring an application window to the front.
    """

    try:
        window = _find_window(
            application
        )

        if window is None:
            return (
                False,
                f"I could not find an open {application} window.",
            )

        if window.isMinimized:
            window.restore()

        window.activate()

        return (
            True,
            f"Switched to {application}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not switch to {application}: {error}",
        )


def minimize_window(
    application: str,
) -> tuple[bool, str]:
    """
    Minimize an application window.
    """

    try:
        window = _find_window(
            application
        )

        if window is None:
            return (
                False,
                f"I could not find an open {application} window.",
            )

        if window.isMinimized:
            return (
                True,
                f"{application} is already minimized.",
            )

        window.minimize()

        return (
            True,
            f"Minimized {application}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not minimize {application}: {error}",
        )


def maximize_window(
    application: str,
) -> tuple[bool, str]:
    """
    Maximize an application window.
    """

    try:
        window = _find_window(
            application
        )

        if window is None:
            return (
                False,
                f"I could not find an open {application} window.",
            )

        if window.isMinimized:
            window.restore()

        if window.isMaximized:
            return (
                True,
                f"{application} is already maximized.",
            )

        window.maximize()

        return (
            True,
            f"Maximized {application}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not maximize {application}: {error}",
        )


def close_window(
    application: str,
) -> tuple[bool, str]:
    """
    Ask an application window to close.

    Applications with unsaved work may display their
    normal save confirmation dialog.
    """

    try:
        window = _find_window(
            application
        )

        if window is None:
            return (
                False,
                f"I could not find an open {application} window.",
            )

        window.close()

        return (
            True,
            f"Closing {application}.",
        )

    except Exception as error:
        return (
            False,
            f"I could not close {application}: {error}",
        )


def show_desktop() -> tuple[bool, str]:
    """
    Show the Windows desktop.
    """

    try:
        pyautogui.hotkey(
            "win",
            "d",
        )

        return (
            True,
            "Showing the desktop.",
        )

    except Exception as error:
        return (
            False,
            f"I could not show the desktop: {error}",
        )


if __name__ == "__main__":
    print("PAT Window Controls Test")
    print()
    print("1. Switch to window")
    print("2. Minimize window")
    print("3. Maximize window")
    print("4. Show desktop")
    print()
    print(
        "Close-window testing is intentionally "
        "not included in this menu."
    )
    print()

    choice = input(
        "Select test: "
    ).strip()

    if choice == "4":
        print(
            show_desktop()
        )

    elif choice in {
        "1",
        "2",
        "3",
    }:
        application = input(
            "Application name: "
        ).strip()

        if choice == "1":
            print(
                focus_window(
                    application
                )
            )

        elif choice == "2":
            print(
                minimize_window(
                    application
                )
            )

        elif choice == "3":
            print(
                maximize_window(
                    application
                )
            )

    else:
        print("Unknown test.")