"""
PAT OS
ui/pat_ui_bridge.py

Process-safe bridge between PAT's existing assistant loop and the
PySide6 visual HUD.

Design:
- PAT's existing main loop stays in its current process/thread.
- The Qt HUD runs in a separate process, where Qt owns the GUI thread.
- PAT sends small UI events through a multiprocessing Queue.

This keeps the visual layer isolated from the router, audio manager,
wake-word loop, and FORGE work.
"""

from __future__ import annotations

import multiprocessing as mp
from queue import Empty
from typing import Any


def _ui_process_main(
    event_queue: Any,
) -> None:
    """Run the PySide6 HUD in its own process."""

    import sys

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ui.pat_window_qt import PATWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PAT Visual Core")

    window = PATWindow()
    window.show()

    def process_events() -> None:
        while True:
            try:
                event = event_queue.get_nowait()
            except Empty:
                break

            if not isinstance(event, dict):
                continue

            event_type = event.get("type")

            if event_type == "state":
                state = event.get("value")

                if isinstance(state, str):
                    window.set_state(state)

            elif event_type == "user_text":
                text = event.get("value")

                if isinstance(text, str):
                    window.set_user_text(text)

            elif event_type == "pat_text":
                text = event.get("value")

                if isinstance(text, str):
                    window.set_pat_text(text)

            elif event_type == "target":
                kind = event.get("kind")
                value = event.get("value")

                if kind is not None:
                    kind = str(kind)

                if value is not None:
                    value = str(value)

                window.set_active_target(
                    kind,
                    value,
                )

            elif event_type == "clear_target":
                window.set_active_target(
                    None,
                    None,
                )

            elif event_type == "shutdown":
                app.quit()
                return

    timer = QTimer()
    timer.timeout.connect(process_events)
    timer.start(25)

    app.exec()


class PATUIBridge:
    """Send UI updates to PAT's PySide6 HUD."""

    def __init__(self) -> None:
        self._context = mp.get_context("spawn")
        self._queue: Any | None = None
        self._process: mp.Process | None = None

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.is_alive()
        )

    def start(self) -> None:
        """Start the HUD if it is not already running."""

        if self.is_running:
            return

        self._queue = self._context.Queue()

        self._process = self._context.Process(
            target=_ui_process_main,
            args=(self._queue,),
            name="PATVisualUI",
            daemon=True,
        )

        self._process.start()

    def stop(self) -> None:
        """Ask the HUD to close and clean up its process."""

        process = self._process

        if process is None:
            return

        if process.is_alive():
            self._send(
                {
                    "type": "shutdown",
                }
            )

            process.join(
                timeout=1.5
            )

        if process.is_alive():
            process.terminate()
            process.join(
                timeout=1.0
            )

        self._process = None

        if self._queue is not None:
            try:
                self._queue.close()
            except Exception:
                pass

        self._queue = None

    def set_state(
        self,
        state: str,
    ) -> None:
        self._send(
            {
                "type": "state",
                "value": state.upper(),
            }
        )

    def set_idle(self) -> None:
        self.set_state("IDLE")

    def set_listening(self) -> None:
        self.set_state("LISTENING")

    def set_thinking(self) -> None:
        self.set_state("THINKING")

    def set_speaking(self) -> None:
        self.set_state("SPEAKING")

    def set_waiting(self) -> None:
        self.set_state("WAITING")

    def set_user_text(
        self,
        text: str,
    ) -> None:
        self._send(
            {
                "type": "user_text",
                "value": text,
            }
        )

    def set_pat_text(
        self,
        text: str,
    ) -> None:
        self._send(
            {
                "type": "pat_text",
                "value": text,
            }
        )

    def set_active_target(
        self,
        kind: str | None,
        value: object | None,
    ) -> None:
        if not kind or value is None:
            self.clear_active_target()
            return

        self._send(
            {
                "type": "target",
                "kind": kind,
                "value": value,
            }
        )

    def clear_active_target(self) -> None:
        self._send(
            {
                "type": "clear_target",
            }
        )

    def sync_active_target(
        self,
        target: object | None,
    ) -> None:
        """
        Sync a brain.session_context.ActiveTarget without importing
        session_context into the GUI process.
        """

        if target is None:
            self.clear_active_target()
            return

        kind = getattr(
            target,
            "kind",
            None,
        )

        value = getattr(
            target,
            "label",
            None,
        )

        if not value:
            value = getattr(
                target,
                "value",
                None,
            )

        self.set_active_target(
            kind,
            value,
        )

    def _send(
        self,
        event: dict[str, object],
    ) -> None:
        if not self.is_running:
            return

        queue = self._queue

        if queue is None:
            return

        try:
            queue.put_nowait(event)
        except Exception:
            # The visual layer must never bring down PAT's core.
            pass


pat_ui = PATUIBridge()
