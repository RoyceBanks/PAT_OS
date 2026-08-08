"""
PAT OS
automation/clipboard.py

Safe clipboard controls for PAT.
"""

from __future__ import annotations

import pyperclip


MAX_CLIPBOARD_RESPONSE = 500


def set_clipboard(
    text: str,
) -> tuple[bool, str]:
    """Copy text to the Windows clipboard."""

    try:
        text = text.strip()

        if not text:
            return (
                False,
                "There was nothing to copy.",
            )

        pyperclip.copy(text)

        return (
            True,
            "Copied to your clipboard.",
        )

    except Exception as error:
        return (
            False,
            f"I could not copy that: {error}",
        )


def get_clipboard() -> tuple[bool, str]:
    """Read text currently stored on the clipboard."""

    try:
        text = pyperclip.paste()

        if not text:
            return (
                True,
                "Your clipboard is empty.",
            )

        text = str(text)

        if len(text) > MAX_CLIPBOARD_RESPONSE:
            preview = (
                text[:MAX_CLIPBOARD_RESPONSE]
                + "..."
            )

            return (
                True,
                "Your clipboard contains: "
                f"{preview}",
            )

        return (
            True,
            f"Your clipboard contains: {text}",
        )

    except Exception as error:
        return (
            False,
            f"I could not read the clipboard: {error}",
        )


def clear_clipboard() -> tuple[bool, str]:
    """Clear the Windows clipboard."""

    try:
        pyperclip.copy("")

        return (
            True,
            "Clipboard cleared.",
        )

    except Exception as error:
        return (
            False,
            f"I could not clear the clipboard: {error}",
        )


if __name__ == "__main__":
    print("PAT Clipboard Test")
    print()
    print("1. Copy test text")
    print("2. Read clipboard")
    print("3. Clear clipboard")

    choice = input(
        "Select test: "
    ).strip()

    if choice == "1":
        print(
            set_clipboard(
                "PAT clipboard test"
            )
        )

    elif choice == "2":
        print(
            get_clipboard()
        )

    elif choice == "3":
        print(
            clear_clipboard()
        )

    else:
        print("Unknown test.")