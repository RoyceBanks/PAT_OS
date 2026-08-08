"""
PAT OS
audio/audio_manager.py

Centralized audio input/output management for PAT.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


class AudioManager:
    """
    Central controller for PAT audio.

    v0.7 goals:
    - Replace global sd.play / sd.rec helpers
    - Track speech state
    - Allow immediate playback interruption
    - Prepare for simultaneous microphone monitoring
    """

    def __init__(
        self,
        output_device: int | str | None = None,
        block_frames: int = 1024,
    ) -> None:
        self.output_device = output_device
        self.block_frames = block_frames

        self._output_lock = threading.RLock()

        self._output_stream: (
            sd.OutputStream | None
        ) = None

        self._stop_output = threading.Event()
        self._speaking = threading.Event()

    @property
    def is_speaking(self) -> bool:
        """Return whether PAT is currently playing speech."""

        return self._speaking.is_set()

    def stop_output(self) -> None:
        """Immediately request that current playback stop."""

        self._stop_output.set()

        with self._output_lock:
            stream = self._output_stream

        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass

    def play_wav(
        self,
        file_path: str | Path,
    ) -> tuple[bool, str]:
        """
        Play a 16-bit PCM WAV through an explicit OutputStream.

        This intentionally avoids sounddevice's global sd.play()
        helper so PAT can centrally control its output stream.
        """

        path = Path(file_path)

        if not path.exists():
            return (
                False,
                f"Audio file does not exist: {path}",
            )

        try:
            with wave.open(
                str(path),
                "rb",
            ) as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()

                if sample_width != 2:
                    return (
                        False,
                        (
                            "PAT AudioManager currently supports "
                            "16-bit PCM WAV files only."
                        ),
                    )

                raw_audio = wav_file.readframes(
                    frame_count
                )

            audio = np.frombuffer(
                raw_audio,
                dtype=np.int16,
            )

            if channels <= 0:
                return (
                    False,
                    "The WAV file has no audio channels.",
                )

            audio = audio.reshape(
                -1,
                channels,
            )

            self._stop_output.clear()
            self._speaking.set()

            stream = sd.OutputStream(
                samplerate=sample_rate,
                channels=channels,
                dtype="int16",
                device=self.output_device,
            )

            with self._output_lock:
                self._output_stream = stream

            try:
                stream.start()

                total_frames = len(
                    audio
                )

                start = 0

                while start < total_frames:
                    if self._stop_output.is_set():
                        return (
                            True,
                            "Playback interrupted.",
                        )

                    end = min(
                        start + self.block_frames,
                        total_frames,
                    )

                    chunk = audio[
                        start:end
                    ]

                    stream.write(
                        chunk
                    )

                    start = end

                return (
                    True,
                    "Playback completed.",
                )

            except sd.PortAudioError as error:
                if self._stop_output.is_set():
                    return (
                        True,
                        "Playback interrupted.",
                    )

                return (
                    False,
                    f"Audio playback error: {error}",
                )

            finally:
                try:
                    if stream.active:
                        stream.stop()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

                with self._output_lock:
                    if self._output_stream is stream:
                        self._output_stream = None

        except Exception as error:
            return (
                False,
                f"Audio manager error: {error}",
            )

        finally:
            self._speaking.clear()
            self._stop_output.clear()


audio_manager = AudioManager()
