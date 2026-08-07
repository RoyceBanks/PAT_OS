"""
PAT OS
speech/interrupt.py

Lightweight voice interruption while PAT is speaking.
"""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from config import (
    MIC_DEVICE,
    MIC_SAMPLE_RATE,
)


INTERRUPT_MODEL = "tiny.en"
INTERRUPT_SECONDS = 1.5

STOP_PHRASES = {
    "stop",
    "pat stop",
    "stop pat",
    "quiet",
    "be quiet",
    "pat quiet",
    "shut up",
    "pat shut up",
}


class SpeechInterruptListener:
    """Listen for stop commands while PAT is speaking."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._stop_event = threading.Event()

    def _load_model(self) -> WhisperModel:
        if self._model is None:
            print("Loading speech interrupt model...")

            self._model = WhisperModel(
                INTERRUPT_MODEL,
                device="cpu",
                compute_type="int8",
            )

            print("Speech interrupt model loaded.")

        return self._model

    def stop(self) -> None:
        """Stop the interrupt listener."""

        self._stop_event.set()

    def _normalize(self, text: str) -> str:
        """Normalize transcribed speech."""

        cleaned = text.lower().strip()

        for character in ".,!?;:":
            cleaned = cleaned.replace(
                character,
                "",
            )

        return " ".join(
            cleaned.split()
        )

    def listen(
        self,
        on_interrupt,
    ) -> None:
        """
        Listen until PAT finishes speaking
        or the user asks PAT to stop.
        """

        self._stop_event.clear()

        model = self._load_model()

        while not self._stop_event.is_set():
            try:
                frames = int(
                    MIC_SAMPLE_RATE
                    * INTERRUPT_SECONDS
                )

                audio = sd.rec(
                    frames,
                    samplerate=MIC_SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    device=MIC_DEVICE,
                )

                sd.wait()

                if self._stop_event.is_set():
                    return

                audio = np.squeeze(audio)

                segments, _ = model.transcribe(
                    audio,
                    language="en",
                    beam_size=1,
                    vad_filter=True,
                )

                text = " ".join(
                    segment.text
                    for segment in segments
                ).strip()

                if not text:
                    continue

                heard = self._normalize(
                    text
                )

                print(
                    f"[Speech interrupt heard: {heard}]"
                )

                if heard in STOP_PHRASES:
                    print(
                        "[Voice interruption detected]"
                    )

                    on_interrupt()
                    return

            except Exception as error:
                if not self._stop_event.is_set():
                    print(
                        "[INTERRUPT LISTENER ERROR] "
                        f"{error}"
                    )

                return


speech_interrupt_listener = (
    SpeechInterruptListener()
)