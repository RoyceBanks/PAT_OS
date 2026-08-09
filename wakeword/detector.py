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
import threading

from faster_whisper import WhisperModel

from config import (
    WAKE_CHANNELS,
    COMMAND_CHUNK_SIZE,
    COMMAND_MAX_SECONDS,
    COMMAND_SILENCE_SECONDS,
    COMMAND_SILENCE_THRESHOLD,
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

    def _record_chunk(
        self,
        listen_seconds: float = WAKE_LISTEN_SECONDS,
        cancel_event: threading.Event | None = None,
    ) -> Path | None:
        """Capture one short window from PAT's AudioManager."""

        # Discard audio collected while the previous
        # chunk was being transcribed.
        audio_manager.flush_input()

        audio_data = audio_manager.read_seconds(
            listen_seconds,
            timeout=listen_seconds + 2.0,
            cancel_event=cancel_event,
        )

        if audio_data is None:
            if (
                cancel_event is not None
                and cancel_event.is_set()
            ):
                return None

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

    def capture_continuation(
        self,
        max_seconds: float = 6.0,
    ) -> str:
        """
        Capture speech that continues after a detected
        'Hey Pat' barge-in.

        The AudioManager buffer is intentionally NOT flushed.
        This preserves words spoken while the initial wake
        window was being transcribed.
        """

        recorded_frames: list[np.ndarray] = []

        sample_rate = (
            audio_manager.input_sample_rate
        )

        required_silent_chunks = max(
            1,
            int(
                COMMAND_SILENCE_SECONDS
                * sample_rate
                / COMMAND_CHUNK_SIZE
            ),
        )

        maximum_seconds = min(
            max_seconds,
            COMMAND_MAX_SECONDS,
        )

        maximum_chunks = max(
            1,
            int(
                maximum_seconds
                * sample_rate
                / COMMAND_CHUNK_SIZE
            ),
        )

        speech_seen = False
        silent_chunks = 0

        for _ in range(maximum_chunks):
            audio_chunk = audio_manager.read_frames(
                COMMAND_CHUNK_SIZE,
                timeout=1.0,
            )

            if audio_chunk is None:
                break

            audio_chunk = np.asarray(
                audio_chunk,
                dtype=np.int16,
            )

            audio_float = audio_chunk.astype(
                np.float32
            )

            rms_volume = float(
                np.sqrt(
                    np.mean(
                        np.square(
                            audio_float
                        )
                    )
                )
            )

            recorded_frames.append(
                audio_chunk.copy()
            )

            if (
                rms_volume
                >= COMMAND_SILENCE_THRESHOLD
            ):
                speech_seen = True
                silent_chunks = 0

            else:
                silent_chunks += 1

                if (
                    silent_chunks
                    >= required_silent_chunks
                ):
                    break

        if (
            not speech_seen
            or not recorded_frames
        ):
            return ""

        audio_data = np.concatenate(
            recorded_frames,
            axis=0,
        )

        temporary_file = (
            tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            )
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
                    audio_data.tobytes()
                )

            transcription = (
                self._transcribe_chunk(
                    temporary_path
                )
            )

        except Exception as error:
            print(
                "Barge-in continuation "
                f"error: {error}"
            )

            return ""

        finally:
            temporary_path.unlink(
                missing_ok=True
            )

        return self._normalize_text(
            transcription
        )


    def check_once(
        self,
        cancel_event: threading.Event | None = None,
        listen_seconds: float = WAKE_LISTEN_SECONDS,
    ) -> tuple[bool, str]:
        """
        Check one microphone window for PAT's wake phrase.

        Returns:
            A tuple containing:
            - Whether the wake phrase was detected
            - Any command spoken after the wake phrase
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

            return False, ""

        audio_path = self._record_chunk(
            listen_seconds=listen_seconds,
            cancel_event=cancel_event,
        )

        if audio_path is None:
            return False, ""

        try:
            transcription = (
                self._transcribe_chunk(
                    audio_path
                )
            )

        except Exception as error:
            if not (
                cancel_event is not None
                and cancel_event.is_set()
            ):
                print(
                    "Barge-in transcription "
                    f"error: {error}"
                )

            return False, ""

        finally:
            audio_path.unlink(
                missing_ok=True
            )

        if not transcription:
            return False, ""

        normalized_text = (
            self._normalize_text(
                transcription
            )
        )

        if target_phrase not in normalized_text:
            return False, ""

        command_after_wake = (
            normalized_text.split(
                target_phrase,
                1,
            )[1]
            .strip()
        )

        return (
            True,
            command_after_wake,
        )

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

def check_for_wake_word(
    cancel_event: threading.Event | None = None,
    listen_seconds: float = WAKE_LISTEN_SECONDS,
) -> tuple[bool, str]:
    """
    Check one audio window for PAT's wake phrase
    and any command spoken after it.
    """

    return wake_phrase_detector.check_once(
        cancel_event=cancel_event,
        listen_seconds=listen_seconds,
    )

def capture_barge_in_continuation(
    max_seconds: float = 6.0,
) -> str:
    """
    Capture command speech continuing after
    a barge-in wake phrase.
    """

    return (
        wake_phrase_detector.capture_continuation(
            max_seconds=max_seconds
        )
    )



if __name__ == "__main__":
    print("PAT Wake Phrase Test")

    detected = listen_for_wake_word()

    print(f"Detected: {detected}")