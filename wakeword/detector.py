"""
PAT OS
wakeword/detector.py

Temporary open-source "Hey Pat" wake phrase detector.

This prototype uses Faster-Whisper. It can later be replaced
with a custom OpenWakeWord ONNX model without changing the
rest of PAT OS.
"""

from __future__ import annotations

import re
import tempfile
import wave
from pathlib import Path
from audio.audio_manager import audio_manager
import numpy as np

from faster_whisper import WhisperModel

from config import (
    WAKE_CHANNELS,
    WAKE_COMPUTE_TYPE,
    WAKE_DEVICE,
    WAKE_LISTEN_SECONDS,
    WAKE_MODEL,
    WAKE_PHRASE,
    WAKE_SAMPLE_RATE,
)


class WakePhraseDetector:
    """Continuously listen for PAT's wake phrase."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        """Load the lightweight wake-phrase model once."""

        if self._model is None:
            print(
                f"Loading wake phrase model: {WAKE_MODEL}..."
            )

            self._model = WhisperModel(
                WAKE_MODEL,
                device=WAKE_DEVICE,
                compute_type=WAKE_COMPUTE_TYPE,
            )

            print("Wake phrase model loaded.")

        return self._model

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize recognized speech for phrase matching.

        Example:
            "Hey, Pat!" becomes "hey pat"
        """

        cleaned_text = text.lower()

        cleaned_text = re.sub(
            r"[^a-z0-9\s]",
            " ",
            cleaned_text,
        )

        return " ".join(cleaned_text.split())

    def _record_chunk(self) -> Path | None:
        """Capture one short window from PAT's AudioManager."""

        # Discard audio collected while the previous
        # chunk was being transcribed.
        audio_manager.flush_input()

        audio_data = audio_manager.read_seconds(
            WAKE_LISTEN_SECONDS,
            timeout=WAKE_LISTEN_SECONDS + 2.0,
        )

        if audio_data is None:
            print(
                "Wake microphone error: "
                "no audio was received."
            )
            return None

        temporary_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )

        temporary_path = Path(
            temporary_file.name
        )

        temporary_file.close()

        try:
            with wave.open(
                str(temporary_path),
                "wb",
            ) as wav_file:
                wav_file.setnchannels(
                    audio_manager.input_channels
                )

                wav_file.setsampwidth(2)

                wav_file.setframerate(
                    audio_manager.input_sample_rate
                )

                wav_file.writeframes(
                    np.asarray(
                        audio_data,
                        dtype=np.int16,
                    ).tobytes()
                )

        except Exception as error:
            temporary_path.unlink(
                missing_ok=True
            )

            print(
                f"Wake audio error: {error}"
            )

            return None

        return temporary_path
 
    def _transcribe_chunk(
        self,
        audio_path: Path,
    ) -> str:
        """Transcribe one short microphone recording."""

        model = self._load_model()

        segments, _ = model.transcribe(
            str(audio_path),
            language="en",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        spoken_parts = [
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ]

        return " ".join(spoken_parts).strip()

    def listen(self) -> bool:
        """
        Listen continuously until the wake phrase is heard.

        Returns:
            True when the phrase is detected.
            False if listening is cancelled.
        """

        target_phrase = self._normalize_text(
            WAKE_PHRASE
        )

        self._load_model()

        success, message = (
            audio_manager.start_input()
        )

        if not success:
            print(
                f"Wake microphone error: {message}"
            )
            return False

        print(
            f'\nWaiting for "{WAKE_PHRASE.title()}"...'
        )

        print(
            "Press Ctrl+C to stop.\n"
        )

        try:
            while True:
                audio_path = self._record_chunk()

                if audio_path is None:
                    continue

                try:
                    transcription = (
                        self._transcribe_chunk(
                            audio_path
                        )
                    )

                except Exception as error:
                    print(
                        "Wake phrase transcription "
                        f"error: {error}"
                    )

                    continue

                finally:
                    audio_path.unlink(
                        missing_ok=True
                    )

                if not transcription:
                    continue

                normalized_text = (
                    self._normalize_text(
                        transcription
                    )
                )

                print(
                    "Wake listener heard: "
                    f"{transcription}"
                )

                if (
                    target_phrase
                    in normalized_text
                ):
                    print(
                        "\nWake phrase detected!"
                    )

                    return True

        except KeyboardInterrupt:
            print(
                "\nWake phrase listener stopped."
            )

            return False

        

wake_phrase_detector = WakePhraseDetector()


def listen_for_wake_word() -> bool:
    """Wait until the user says the configured phrase."""

    return wake_phrase_detector.listen()


if __name__ == "__main__":
    print("PAT Wake Phrase Test")

    detected = listen_for_wake_word()

    print(f"Detected: {detected}")