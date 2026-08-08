"""
PAT OS
audio/audio_manager.py

Centralized audio input/output management for PAT.
"""

from __future__ import annotations

import threading
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import (
    MIC_CHANNELS,
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
)


class AudioManager:
    """
    Central controller for PAT audio.

    Responsibilities:
    - Own PAT's output stream
    - Own PAT's microphone input stream
    - Track speaking/listening state
    - Allow immediate output interruption
    - Provide microphone audio to wake/STT systems
    """

    def __init__(
        self,
        output_device: int | str | None = None,
        input_device: int | str | None = None,
        input_sample_rate: int = 16000,
        input_channels: int = 1,
        block_frames: int = 1024,
        input_buffer_blocks: int = 128,
    ) -> None:
        self.output_device = output_device

        self.input_device = input_device
        self.input_sample_rate = input_sample_rate
        self.input_channels = input_channels

        self.block_frames = block_frames
        self.input_buffer_blocks = input_buffer_blocks

        # --------------------------------------------------
        # OUTPUT
        # --------------------------------------------------

        self._output_lock = threading.RLock()

        self._output_stream: (
            sd.OutputStream | None
        ) = None

        self._stop_output = threading.Event()
        self._speaking = threading.Event()

        # --------------------------------------------------
        # INPUT
        # --------------------------------------------------

        self._input_lock = threading.RLock()

        self._input_stream: (
            sd.InputStream | None
        ) = None

        self._listening = threading.Event()

        self._input_condition = threading.Condition()

        self._input_buffer: deque[np.ndarray] = deque(
            maxlen=input_buffer_blocks
        )

        self._last_input_status: str | None = None

    # ======================================================
    # STATE
    # ======================================================

    @property
    def is_speaking(self) -> bool:
        """Return whether PAT is currently playing audio."""

        return self._speaking.is_set()

    @property
    def is_listening(self) -> bool:
        """Return whether PAT's microphone stream is active."""

        return self._listening.is_set()

    @property
    def last_input_status(self) -> str | None:
        """Return the latest PortAudio input warning."""

        return self._last_input_status

    # ======================================================
    # OUTPUT
    # ======================================================

    def stop_output(self) -> None:
        """Immediately request current playback to stop."""

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
        Play a 16-bit PCM WAV through PAT's managed
        output stream.
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

    # ======================================================
    # INPUT CALLBACK
    # ======================================================

    def _input_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status,
    ) -> None:
        """
        Receive microphone audio from PortAudio.

        The callback does minimal work and stores audio
        for other PAT systems to consume.
        """

        if status:
            self._last_input_status = str(
                status
            )

        chunk = indata.copy()

        with self._input_condition:
            self._input_buffer.append(
                chunk
            )

            self._input_condition.notify_all()

    # ======================================================
    # INPUT CONTROL
    # ======================================================

    def start_input(self) -> tuple[bool, str]:
        """
        Start PAT's persistent microphone stream.

        Calling this more than once is safe.
        """

        with self._input_lock:
            if (
                self._input_stream is not None
                and self._listening.is_set()
            ):
                return (
                    True,
                    "Microphone stream is already running.",
                )

            try:
                self.flush_input()

                self._last_input_status = None

                stream = sd.InputStream(
                    samplerate=self.input_sample_rate,
                    channels=self.input_channels,
                    dtype="int16",
                    device=self.input_device,
                    blocksize=self.block_frames,
                    callback=self._input_callback,
                )

                stream.start()

                self._input_stream = stream
                self._listening.set()

                return (
                    True,
                    "Microphone stream started.",
                )

            except Exception as error:
                self._input_stream = None
                self._listening.clear()

                return (
                    False,
                    f"Could not start microphone: {error}",
                )

    def stop_input(self) -> tuple[bool, str]:
        """Stop PAT's microphone stream."""

        with self._input_lock:
            stream = self._input_stream

            if stream is None:
                self._listening.clear()

                return (
                    True,
                    "Microphone stream is already stopped.",
                )

            try:
                try:
                    if stream.active:
                        stream.stop()
                except Exception:
                    pass

                try:
                    stream.close()
                except Exception:
                    pass

                self._input_stream = None
                self._listening.clear()

                return (
                    True,
                    "Microphone stream stopped.",
                )

            except Exception as error:
                self._input_stream = None
                self._listening.clear()

                return (
                    False,
                    f"Could not stop microphone: {error}",
                )

    # ======================================================
    # INPUT BUFFER
    # ======================================================

    def flush_input(self) -> None:
        """Discard microphone audio currently buffered."""

        with self._input_condition:
            self._input_buffer.clear()

    def read_frames(
        self,
        frame_count: int,
        timeout: float = 5.0,
    ) -> np.ndarray | None:
        """
        Read a requested number of microphone frames.

        Audio comes from the persistent InputStream rather
        than opening another sounddevice stream.
        """

        if frame_count <= 0:
            return None

        deadline = (
            time.monotonic()
            + timeout
        )

        pieces: list[np.ndarray] = []

        frames_remaining = frame_count

        while frames_remaining > 0:
            with self._input_condition:
                while not self._input_buffer:
                    remaining_time = (
                        deadline
                        - time.monotonic()
                    )

                    if remaining_time <= 0:
                        break

                    self._input_condition.wait(
                        timeout=remaining_time
                    )

                if not self._input_buffer:
                    break

                chunk = self._input_buffer.popleft()

                chunk_frames = len(
                    chunk
                )

                if chunk_frames <= frames_remaining:
                    pieces.append(
                        chunk
                    )

                    frames_remaining -= (
                        chunk_frames
                    )

                else:
                    pieces.append(
                        chunk[
                            :frames_remaining
                        ]
                    )

                    leftover = chunk[
                        frames_remaining:
                    ]

                    self._input_buffer.appendleft(
                        leftover
                    )

                    frames_remaining = 0

        if not pieces:
            return None

        return np.concatenate(
            pieces,
            axis=0,
        )

    def read_seconds(
        self,
        seconds: float,
        timeout: float | None = None,
    ) -> np.ndarray | None:
        """Read a specific duration from PAT's microphone."""

        if seconds <= 0:
            return None

        frame_count = int(
            self.input_sample_rate
            * seconds
        )

        if timeout is None:
            timeout = seconds + 2.0

        return self.read_frames(
            frame_count=frame_count,
            timeout=timeout,
        )


audio_manager = AudioManager(
    input_device=MIC_DEVICE,
    input_sample_rate=MIC_SAMPLE_RATE,
    input_channels=MIC_CHANNELS,
)