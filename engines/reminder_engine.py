"""
PAT OS
engines/reminder_engine.py

Timer and reminder engine.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable


@dataclass
class Reminder:
    reminder_id: str
    message: str
    due_time: datetime
    timer: threading.Timer | None = None


class ReminderEngine:
    """Manage PAT timers and reminders."""

    def __init__(self) -> None:
        self.reminders: dict[str, Reminder] = {}
        self.on_reminder: Callable[[str], None] | None = None

    def set_callback(
        self,
        callback: Callable[[str], None],
    ) -> None:
        """Set the function called when a reminder fires."""

        self.on_reminder = callback

    def create_reminder(
        self,
        seconds: float,
        message: str,
    ) -> tuple[bool, str]:
        """Create a reminder that fires after a delay."""

        if seconds <= 0:
            return False, "The timer duration must be greater than zero."

        reminder_id = uuid.uuid4().hex[:8]

        due_time = datetime.now() + timedelta(
            seconds=seconds
        )

        reminder = Reminder(
            reminder_id=reminder_id,
            message=message,
            due_time=due_time,
        )

        timer = threading.Timer(
            seconds,
            self._fire_reminder,
            args=(reminder_id,),
        )

        timer.daemon = True

        reminder.timer = timer
        self.reminders[reminder_id] = reminder

        timer.start()

        return (
            True,
            f"Reminder set for {self._format_duration(seconds)}.",
        )

    def _fire_reminder(
        self,
        reminder_id: str,
    ) -> None:
        """Run when a reminder becomes due."""

        reminder = self.reminders.pop(
            reminder_id,
            None,
        )

        if reminder is None:
            print(
                f"Reminder {reminder_id} "
                "could not be found."
            )
            return

        message = reminder.message

        print()
        print("=" * 50)
        print(f"PAT REMINDER: {message}")
        print("=" * 50)
        print()

        if self.on_reminder is None:
            print(
                "[REMINDER] No voice callback "
                "is currently registered."
            )
            return

        print(
            "[REMINDER] Sending reminder "
            "to PAT voice..."
        )

        try:
            self.on_reminder(message)

            print(
                "[REMINDER] Voice callback completed."
            )

        except Exception as error:
            print(
                "[REMINDER ERROR] Voice callback failed:"
            )
            print(
                f"{type(error).__name__}: {error}"
            )

    def cancel_reminder(
        self,
        reminder_id: str,
    ) -> tuple[bool, str]:
        """Cancel an active reminder."""

        reminder = self.reminders.pop(
            reminder_id,
            None,
        )

        if reminder is None:
            return False, "I could not find that reminder."

        if reminder.timer is not None:
            reminder.timer.cancel()

        return True, "Reminder cancelled."

    def list_reminders(self) -> list[Reminder]:
        """Return active reminders."""

        return sorted(
            self.reminders.values(),
            key=lambda item: item.due_time,
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Turn seconds into spoken time."""

        seconds = int(seconds)

        if seconds < 60:
            return (
                f"{seconds} second"
                f"{'s' if seconds != 1 else ''}"
            )

        minutes = seconds // 60

        if minutes < 60:
            return (
                f"{minutes} minute"
                f"{'s' if minutes != 1 else ''}"
            )

        hours = minutes // 60

        return (
            f"{hours} hour"
            f"{'s' if hours != 1 else ''}"
        )


reminder_engine = ReminderEngine()


if __name__ == "__main__":
    print("PAT Reminder Engine Test")
    print("Setting a 5 second reminder...")

    reminder_engine.set_callback(
        lambda message: print(
            f"CALLBACK: {message}"
        )
    )

    success, response = reminder_engine.create_reminder(
        5,
        "This is a PAT timer test.",
    )

    print(response)

    time.sleep(7)
