"""
PAT OS
speech/corrections.py

Correct common speech-recognition mistakes before
commands are sent to PAT's router.
"""

from __future__ import annotations

import re


CORRECTIONS = {
    r"\blatest\s+in\s+video\s+news\b":
        "latest NVIDIA news",

    r"\blatest\s+nividia\s+news\b":
        "latest NVIDIA news",

    r"\blatest\s+nivida\s+news\b":
        "latest NVIDIA news",

    r"\bin\s+video\s+gpu\b":
        "NVIDIA GPU",

    r"\bnividia\b":
        "NVIDIA",

    r"\bnivida\b":
        "NVIDIA",

    r"\bnvidia\b":
        "NVIDIA",

    r"\bopen ai\b":
        "OpenAI",

    r"\bchat g p t\b":
        "ChatGPT",

    r"\braspberry pie\b":
        "Raspberry Pi",

    r"\bvisual studio coat\b":
        "Visual Studio Code",

    r"\bvs coat\b":
        "VS Code",

    r"\bfire fox\b":
        "Firefox",

    r"\byou tube\b":
        "YouTube",

    r"\bgit hub\b":
        "GitHub",
}


def correct_transcription(text: str) -> str:
    """Correct known speech-recognition mistakes."""

    corrected = text.strip()

    for pattern, replacement in CORRECTIONS.items():
        corrected = re.sub(
            pattern,
            replacement,
            corrected,
            flags=re.IGNORECASE,
        )

    return corrected