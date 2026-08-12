"""
PAT OS
ui/pat_audio_visualizer.py

Read PAT's already-managed speaker reference audio and send a smoothed
voice level to the PySide6 HUD.

This module does NOT open or own an audio stream.
AudioManager remains PAT's sole audio input/output owner.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

from audio.audio_manager import audio_manager
from ui.pat_ui_bridge import pat_ui


class PATVoiceVisualizer:
    """Drive the HUD speaking animation from PAT's real output audio."""

    def __init__(
        self,
        update_hz: float = 30.0,
        reference_seconds: float = 0.06,
    ) -> None:
        self.update_hz = max(10.0, float(update_hz))
        self.reference_seconds = max(
            0.02,
            float(reference_seconds),
        )

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        self._smoothed_level = 0.0

    @property
    def is_running(self) -> bool:
        return (
            self._thread is not None
            and self._thread.is_alive()
        )

    def start(self) -> None:
        if self.is_running:
            return

        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="PATVoiceVisualizer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
        ):
            thread.join(timeout=1.0)

        self._thread = None
        self._smoothed_level = 0.0

        pat_ui.set_voice_level(0.0)

    def _run(self) -> None:
        interval = 1.0 / self.update_hz

        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            if audio_manager.is_speaking:
                audio = audio_manager.get_output_reference(
                    seconds=self.reference_seconds,
                )

                level = self._calculate_level(audio)

                # Fast attack, slower release feels natural for speech.
                smoothing = (
                    0.58
                    if level > self._smoothed_level
                    else 0.24
                )

                self._smoothed_level += (
                    level - self._smoothed_level
                ) * smoothing

            else:
                # Smoothly fall back to zero after speech ends.
                self._smoothed_level *= 0.58

                if self._smoothed_level < 0.01:
                    self._smoothed_level = 0.0

            pat_ui.set_voice_level(
                self._smoothed_level
            )

            elapsed = (
                time.monotonic()
                - loop_start
            )

            wait_time = max(
                0.0,
                interval - elapsed,
            )

            self._stop_event.wait(
                wait_time
            )

    @staticmethod
    def _calculate_level(
        audio: np.ndarray,
    ) -> float:
        """
        Convert recent int16 speaker audio into a normalized 0..1
        visual level.

        Uses RMS plus gentle nonlinear compression so normal speech
        produces visible motion without clipping the animation.
        """

        if audio.size == 0:
            return 0.0

        samples = np.asarray(
            audio,
            dtype=np.float32,
        )

        rms = float(
            np.sqrt(
                np.mean(
                    samples * samples
                )
            )
        )

        if not math.isfinite(rms):
            return 0.0

        normalized = rms / 32768.0

        # Speech RMS is usually much lower than peak amplitude.
        # This gain + sqrt curve makes conversational speech visually useful.
        level = math.sqrt(
            max(
                0.0,
                normalized * 7.0,
            )
        )

        return max(
            0.0,
            min(
                1.0,
                level,
            ),
        )


pat_voice_visualizer = PATVoiceVisualizer()
