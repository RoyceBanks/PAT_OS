"""
PAT OS
speech/listen.py

Push-to-talk microphone recording and local speech
recognition using Faster-Whisper.
"""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import (
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
    """Record microphone audio and convert it into text."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        """
        Load the Faster-Whisper model once and reuse it.
        """

        if self._model is None:
            print(f"Loading speech model: {STT_MODEL}...")

            self._model = WhisperModel(
                STT_MODEL,
                device=STT_DEVICE,
                compute_type=STT_COMPUTE_TYPE,
            )

            print("Speech model loaded.")

        return self._model

    def _record_audio(self) -> Path | None:
        """
        Record audio until the user presses Enter again.

        Returns:
            Path to a temporary WAV file, or None if
            recording failed.
        """

        audio_frames: list[np.ndarray] = []
        stream_warning: str | None = None

        def audio_callback(
            input_data: np.ndarray,
            frame_count: int,
            time_info,
            status,
        ) -> None:
            """Collect microphone frames from SoundDevice."""

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

        temporary_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )

        temporary_path = Path(temporary_file.name)
        temporary_file.close()

        try:
            with wave.open(
                str(temporary_path),
                "wb",
            ) as wav_file:
                wav_file.setnchannels(MIC_CHANNELS)
                wav_file.setsampwidth(2)
                wav_file.setframerate(MIC_SAMPLE_RATE)
                wav_file.writeframes(audio_data.tobytes())

        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        return temporary_path

    def listen(self) -> str:
        """
        Record and transcribe one spoken command.

        Returns:
            The transcribed text, or an empty string when
            no usable speech was detected.
        """

        audio_path = self._record_audio()

        if audio_path is None:
            return ""

        try:
            model = self._load_model()

            print("Transcribing...")

            segments, _ = model.transcribe(
                str(audio_path),
                language=STT_LANGUAGE,
                beam_size=STT_BEAM_SIZE,
                vad_filter=True,
            )

            # Faster-Whisper performs transcription while
            # the segment generator is being consumed.
            transcribed_parts = [
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ]

            transcription = " ".join(
                transcribed_parts
            ).strip()

            if transcription:
                print(f"Heard: {transcription}")
            else:
                print("I did not detect any clear speech.")

            return transcription

        except Exception as error:
            print(f"Speech recognition error: {error}")
            return ""

        finally:
            audio_path.unlink(missing_ok=True)


speech_recognizer = SpeechRecognizer()


def listen() -> str:
    """Record and transcribe one spoken command."""

    return speech_recognizer.listen()


if __name__ == "__main__":
    print("PAT Speech Recognition Test\n")

    command = listen()

    print(f"\nTranscription: {command!r}")