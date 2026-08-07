"""
PAT OS
speech/listen.py

Push-to-talk and automatic voice-command recognition
using Faster-Whisper.
"""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import (
    COMMAND_LISTEN_SECONDS,
    MIC_CHANNELS,
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
    STT_BEAM_SIZE,
    STT_COMPUTE_TYPE,
    STT_DEVICE,
    STT_LANGUAGE,
    STT_MODEL,
)


class SpeechRecognizer:
    """Record microphone audio and convert it to text."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        """Load Faster-Whisper once and reuse it."""

        if self._model is None:
            print(f"Loading speech model: {STT_MODEL}...")

            self._model = WhisperModel(
                STT_MODEL,
                device=STT_DEVICE,
                compute_type=STT_COMPUTE_TYPE,
            )

            print("Speech model loaded.")

        return self._model

    def _save_audio(
        self,
        audio_data: np.ndarray,
    ) -> Path:
        """Save microphone data to a temporary WAV file."""

        temporary_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )

        audio_path = Path(temporary_file.name)
        temporary_file.close()

        try:
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(MIC_CHANNELS)
                wav_file.setsampwidth(2)
                wav_file.setframerate(MIC_SAMPLE_RATE)
                wav_file.writeframes(
                    np.asarray(
                        audio_data,
                        dtype=np.int16,
                    ).tobytes()
                )

        except Exception:
            audio_path.unlink(missing_ok=True)
            raise

        return audio_path

    def _record_push_to_talk(self) -> Path | None:
        """Record until the user presses Enter again."""

        audio_frames: list[np.ndarray] = []
        stream_warning: str | None = None

        def audio_callback(
            input_data: np.ndarray,
            frame_count: int,
            time_info,
            status,
        ) -> None:
            del frame_count
            del time_info

            nonlocal stream_warning

            if status:
                stream_warning = str(status)

            audio_frames.append(input_data.copy())

        input("Press Enter to begin speaking...")

        try:
            with sd.InputStream(
                samplerate=MIC_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=MIC_DEVICE,
                callback=audio_callback,
            ):
                input(
                    "Recording... Speak now, then press "
                    "Enter to stop.\n"
                )

        except Exception as error:
            print(f"Microphone error: {error}")
            return None

        if stream_warning:
            print(f"Microphone warning: {stream_warning}")

        if not audio_frames:
            print("No microphone audio was recorded.")
            return None

        audio_data = np.concatenate(
            audio_frames,
            axis=0,
        )

        return self._save_audio(audio_data)

    def _record_fixed_duration(
        self,
        seconds: float,
    ) -> Path | None:
        """Record automatically for a fixed number of seconds."""

        frame_count = int(
            MIC_SAMPLE_RATE * seconds
        )

        print(
            f"Listening for your command "
            f"({seconds:.0f} seconds)..."
        )

        try:
            audio_data = sd.rec(
                frame_count,
                samplerate=MIC_SAMPLE_RATE,
                channels=MIC_CHANNELS,
                dtype="int16",
                device=MIC_DEVICE,
            )

            sd.wait()

        except Exception as error:
            print(f"Microphone error: {error}")
            return None

        return self._save_audio(audio_data)

    def _transcribe_audio(
        self,
        audio_path: Path,
    ) -> str:
        """Transcribe a WAV file into text."""

        model = self._load_model()

        print("Transcribing...")

        segments, _ = model.transcribe(
            str(audio_path),
            language=STT_LANGUAGE,
            beam_size=STT_BEAM_SIZE,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        parts = [
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ]

        transcription = " ".join(parts).strip()

        if transcription:
            print(f"Heard: {transcription}")
        else:
            print("I did not detect clear speech.")

        return transcription

    def listen(self) -> str:
        """Record one push-to-talk command."""

        audio_path = self._record_push_to_talk()

        if audio_path is None:
            return ""

        try:
            return self._transcribe_audio(audio_path)

        except Exception as error:
            print(f"Speech recognition error: {error}")
            return ""

        finally:
            audio_path.unlink(missing_ok=True)

    def listen_for_command(
        self,
        seconds: float = COMMAND_LISTEN_SECONDS,
    ) -> str:
        """Automatically record and transcribe one command."""

        audio_path = self._record_fixed_duration(seconds)

        if audio_path is None:
            return ""

        try:
            return self._transcribe_audio(audio_path)

        except Exception as error:
            print(f"Speech recognition error: {error}")
            return ""

        finally:
            audio_path.unlink(missing_ok=True)


speech_recognizer = SpeechRecognizer()


def listen() -> str:
    """Record one push-to-talk command."""

    return speech_recognizer.listen()


def listen_for_command(
    seconds: float = COMMAND_LISTEN_SECONDS,
) -> str:
    """Automatically record one spoken command."""

    return speech_recognizer.listen_for_command(seconds)


if __name__ == "__main__":
    print("PAT Automatic Speech Test\n")

    command = listen_for_command()

    print(f"\nTranscription: {command!r}")