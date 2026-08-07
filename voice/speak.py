"""
PAT OS
voice/speak.py

Local text-to-speech using Piper.
"""

from __future__ import annotations
import html
import re
import tempfile
import wave
import winsound
from pathlib import Path

from piper import PiperVoice

from config import (
    VOICE_CONFIG,
    VOICE_ENABLED,
    VOICE_MODEL,
)


def clean_text_for_speech(text: str) -> str:
    """
    Remove Markdown and other formatting that should not
    be spoken aloud.

    Example:
        "**CPU:** 20%" becomes "CPU: 20%"
    """

    cleaned_text = html.unescape(text)

    # Convert Markdown images and links to their visible labels.
    cleaned_text = re.sub(
        r"!\[([^\]]*)\]\([^)]+\)",
        r"\1",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        cleaned_text,
    )

    # Remove web addresses.
    cleaned_text = re.sub(
        r"https?://\S+|www\.\S+",
        "",
        cleaned_text,
    )

    # Remove fenced-code markers while retaining their text.
    cleaned_text = re.sub(
        r"```(?:[a-zA-Z0-9_+-]+)?",
        "",
        cleaned_text,
    )

    cleaned_text = cleaned_text.replace("```", "")
    cleaned_text = cleaned_text.replace("`", "")

    # Remove Markdown headings, quotes, and list markers.
    cleaned_text = re.sub(
        r"^\s{0,3}#{1,6}\s*",
        "",
        cleaned_text,
        flags=re.MULTILINE,
    )

    cleaned_text = re.sub(
        r"^\s*>\s?",
        "",
        cleaned_text,
        flags=re.MULTILINE,
    )

    cleaned_text = re.sub(
        r"^\s*[-*+]\s+",
        "",
        cleaned_text,
        flags=re.MULTILINE,
    )

    # Remove bold, italic, underline, and strike markers.
    cleaned_text = cleaned_text.replace("**", "")
    cleaned_text = cleaned_text.replace("__", "")
    cleaned_text = cleaned_text.replace("*", "")
    cleaned_text = cleaned_text.replace("~", "")
    cleaned_text = cleaned_text.replace("_", " ")

    # Turn line breaks into natural pauses.
    cleaned_text = re.sub(
        r"\s*\n+\s*",
        ". ",
        cleaned_text,
    )

    # Clean duplicate punctuation and spaces.
    cleaned_text = re.sub(
        r"\.{2,}",
        ".",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"[ \t]+",
        " ",
        cleaned_text,
    )

    cleaned_text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        cleaned_text,
    )

    return cleaned_text.strip()


class VoiceEngine:
    """Generate and play PAT's speech locally."""

    def __init__(
        self,
        model_path: str | Path = VOICE_MODEL,
        config_path: str | Path = VOICE_CONFIG,
    ) -> None:
        self.model_path = Path(model_path)
        self.config_path = Path(config_path)
        self._voice: PiperVoice | None = None

    def _validate_files(self) -> None:
        """Confirm that the Piper voice files exist."""

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Voice model not found: {self.model_path}"
            )

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Voice configuration not found: "
                f"{self.config_path}"
            )

    def _load_voice(self) -> PiperVoice:
        """Load the voice once and reuse it."""

        if self._voice is None:
            self._validate_files()

            print("Loading PAT voice...")

            self._voice = PiperVoice.load(
                str(self.model_path),
                config_path=str(self.config_path),
            )

            print("PAT voice loaded.")

        return self._voice

    def speak(self, text: str) -> tuple[bool, str]:
        """
        Generate speech and play it through Windows.

        Returns:
            Success status and a diagnostic message.
        """

        cleaned_text = clean_text_for_speech(text)

        if not VOICE_ENABLED:
            return True, "Voice output is disabled."

        if not cleaned_text:
            return False, "No text was provided for speech."

        temporary_path: Path | None = None

        try:
            voice = self._load_voice()

            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

            with wave.open(str(temporary_path), "wb") as wav_file:
                voice.synthesize_wav(
                    cleaned_text,
                    wav_file,
                )

            # PlaySound blocks until PAT finishes speaking.
            winsound.PlaySound(
                str(temporary_path),
                winsound.SND_FILENAME,
            )

            return True, "Speech completed."

        except Exception as error:
            return False, f"Voice output failed: {error}"

        finally:
            if temporary_path and temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass


voice_engine = VoiceEngine()


def speak(text: str) -> tuple[bool, str]:
    """Speak text through the shared PAT voice engine."""

    return voice_engine.speak(text)


if __name__ == "__main__":
    success, message = speak(
        "Systems online. PAT voice is ready."
    )

    print(message)
    print(f"Success: {success}")