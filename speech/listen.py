"""
PAT OS
speech/listen.py

Push-to-talk and automatic voice-command recognition
using Faster-Whisper.

Automatic mode stops recording after the user finishes
speaking instead of always waiting a fixed number of seconds.
"""

from __future__ import annotations

import tempfile
import wave
from collections import deque
from pathlib import Path
from audio.audio_manager import audio_manager
import threading
import numpy as np
from faster_whisper import WhisperModel

from config import (
    COMMAND_CHUNK_SIZE,
    COMMAND_MAX_SECONDS,
    COMMAND_SILENCE_SECONDS,
    COMMAND_SILENCE_THRESHOLD,
    COMMAND_START_TIMEOUT,
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
        """
        Record until the user presses Enter again.

        Audio comes from PAT's centralized AudioManager.
        """

        audio_frames: list[np.ndarray] = []

        stop_event = threading.Event()
        input_warning_shown = False

        input(
            "Press Enter to begin speaking..."
        )

        success, message = (
            audio_manager.start_input()
        )

        if not success:
            print(
                f"Microphone error: {message}"
            )
            return None

        audio_manager.flush_input()

        def collect_audio() -> None:
            nonlocal input_warning_shown

            while not stop_event.is_set():
                audio_chunk = (
                    audio_manager.read_frames(
                        COMMAND_CHUNK_SIZE,
                        timeout=0.5,
                        cancel_event=stop_event,
                    )
                )

                if audio_chunk is None:
                    continue

                if (
                    audio_manager.last_input_status
                    and not input_warning_shown
                ):
                    print(
                        "Microphone warning: "
                        f"{audio_manager.last_input_status}"
                    )

                    input_warning_shown = True

                audio_frames.append(
                    np.asarray(
                        audio_chunk,
                        dtype=np.int16,
                    ).copy()
                )

        recorder_thread = threading.Thread(
            target=collect_audio,
            daemon=True,
        )

        recorder_thread.start()

        try:
            input(
                "Recording... Speak now, then press "
                "Enter to stop.\n"
            )

        finally:
            stop_event.set()

            recorder_thread.join(
                timeout=1.0
            )

        if not audio_frames:
            print(
                "No microphone audio was recorded."
            )
            return None

        audio_data = np.concatenate(
            audio_frames,
            axis=0,
        )

        return self._save_audio(
            audio_data
        )
    
    def _record_until_silence(
        self,
        start_timeout: float | None = None,
        quiet: bool = False,
    ) -> Path | None:
        """
        Record until the user stops speaking.

        Audio is supplied by PAT's centralized AudioManager.
        """

        recorded_frames: list[np.ndarray] = []

        # Keeps a short amount of audio from immediately before
        # speech detection so the first word is not clipped.
        pre_roll_chunks = max(
            1,
            int(
                0.35
                * MIC_SAMPLE_RATE
                / COMMAND_CHUNK_SIZE
            ),
        )

        pre_roll: deque[np.ndarray] = deque(
            maxlen=pre_roll_chunks
        )

        speech_started = False
        silent_chunks = 0
        input_warning_shown = False

        effective_start_timeout = (
            COMMAND_START_TIMEOUT
            if start_timeout is None
            else max(
                0.1,
                float(start_timeout),
            )
        )

        start_timeout_chunks = max(
            1,
            int(
                effective_start_timeout
                * MIC_SAMPLE_RATE
                / COMMAND_CHUNK_SIZE
            ),
        )

        required_silent_chunks = max(
            1,
            int(
                COMMAND_SILENCE_SECONDS
                * MIC_SAMPLE_RATE
                / COMMAND_CHUNK_SIZE
            ),
        )

        maximum_chunks = max(
            1,
            int(
                COMMAND_MAX_SECONDS
                * MIC_SAMPLE_RATE
                / COMMAND_CHUNK_SIZE
            ),
        )

        success, message = audio_manager.start_input()

        if not success:
            print(f"Microphone error: {message}")
            return None

        audio_manager.flush_input()

        if not quiet:
            print("Listening... Speak now.")

        try:
            for chunk_number in range(maximum_chunks):
                audio_chunk = audio_manager.read_frames(
                    COMMAND_CHUNK_SIZE,
                    timeout=1.0,
                )

                if audio_chunk is None:
                    print(
                        "Microphone error: "
                        "no audio was received."
                    )
                    return None

                if (
                    audio_manager.last_input_status
                    and not input_warning_shown
                ):
                    print(
                        "Microphone warning: "
                        f"{audio_manager.last_input_status}"
                    )

                    input_warning_shown = True

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
                            np.square(audio_float)
                        )
                    )
                )

                if not speech_started:
                    pre_roll.append(
                        audio_chunk.copy()
                    )

                    if (
                        rms_volume
                        >= COMMAND_SILENCE_THRESHOLD
                    ):
                        if not quiet:
                            print("Speech detected.")

                        speech_started = True

                        recorded_frames.extend(
                            pre_roll
                        )

                        pre_roll.clear()
                        silent_chunks = 0

                    elif (
                        chunk_number + 1
                        >= start_timeout_chunks
                    ):
                        if not quiet:
                            print("No speech detected.")
                        return None

                    continue

                recorded_frames.append(
                    audio_chunk.copy()
                )

                if (
                    rms_volume
                    >= COMMAND_SILENCE_THRESHOLD
                ):
                    silent_chunks = 0

                else:
                    silent_chunks += 1

                    if (
                        silent_chunks
                        >= required_silent_chunks
                    ):
                        if not quiet:
                            print(
                                "End of speech detected."
                            )
                        break

        except Exception as error:
            print(f"Microphone error: {error}")
            return None

        

        if not speech_started or not recorded_frames:
            print("No usable speech was recorded.")
            return None

        audio_data = np.concatenate(
            recorded_frames,
            axis=0,
        )

        return self._save_audio(
            audio_data
        )

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
        start_timeout: float | None = None,
        quiet: bool = False,
    ) -> str:
        """
        Record one command and stop automatically
        when the user finishes speaking.
        """

        audio_path = self._record_until_silence(
            start_timeout=start_timeout,
            quiet=quiet,
        )

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
    start_timeout: float | None = None,
    quiet: bool = False,
) -> str:
    """Record one command and stop after silence."""

    return speech_recognizer.listen_for_command(
        start_timeout=start_timeout,
        quiet=quiet,
    )

if __name__ == "__main__":
    print("PAT Automatic Speech Test\n")

    command = listen_for_command()

    print(f"\nTranscription: {command!r}")