"""
PAT OS
engines/reminder_engine.py

Persistent timer and reminder engine.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from config import REMINDER_DATABASE


@dataclass
class Reminder:
    reminder_id: str
    message: str
    due_time: datetime
    timer: threading.Timer | None = None


class ReminderEngine:
    """Manage PAT timers and persistent reminders."""

    def __init__(self) -> None:
        self.reminders: dict[str, Reminder] = {}

        self.on_reminder: Callable[
            [str],
            None,
        ] | None = None

        self._lock = threading.RLock()
        self._started = False

        self._initialize_database()
        self._load_saved_reminders()

    # ======================================================
    # DATABASE
    # ======================================================

    def _connect(self) -> sqlite3.Connection:
        """Connect to the reminder database."""

        REMINDER_DATABASE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return sqlite3.connect(
            REMINDER_DATABASE,
            timeout=10,
        )

    def _initialize_database(self) -> None:
        """Create the reminders database table."""

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    reminder_id TEXT PRIMARY KEY,
                    message TEXT NOT NULL,
                    due_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            connection.commit()

    def _save_reminder(
        self,
        reminder: Reminder,
    ) -> None:
        """Save a reminder to SQLite."""

        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO reminders (
                    reminder_id,
                    message,
                    due_time,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    reminder.reminder_id,
                    reminder.message,
                    reminder.due_time.isoformat(),
                    datetime.now().isoformat(),
                ),
            )

            connection.commit()

    def _delete_saved_reminder(
        self,
        reminder_id: str,
    ) -> None:
        """Remove a reminder from SQLite."""

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM reminders
                WHERE reminder_id = ?
                """,
                (reminder_id,),
            )

            connection.commit()

    def _load_saved_reminders(self) -> None:
        """Load reminders saved during a previous PAT session."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    reminder_id,
                    message,
                    due_time
                FROM reminders
                ORDER BY due_time
                """
            ).fetchall()

        for (
            reminder_id,
            message,
            due_time_text,
        ) in rows:

            try:
                due_time = datetime.fromisoformat(
                    due_time_text
                )

            except ValueError:
                self._delete_saved_reminder(
                    reminder_id
                )
                continue

            reminder = Reminder(
                reminder_id=reminder_id,
                message=message,
                due_time=due_time,
            )

            self.reminders[reminder_id] = reminder

    # ======================================================
    # STARTUP
    # ======================================================

    def set_callback(
        self,
        callback: Callable[[str], None],
    ) -> None:
        """Set the function PAT uses when a reminder fires."""

        self.on_reminder = callback

    def start(self) -> None:
        """
        Restore saved reminders after PAT starts.

        This should be called after the voice callback
        has been registered.
        """

        with self._lock:
            if self._started:
                return

            self._started = True

            reminders = list(
                self.reminders.values()
            )

        unscheduled = [
            reminder
            for reminder in reminders
            if reminder.timer is None
        ]

        if unscheduled:
            print(
                f"Restoring "
                f"{len(unscheduled)} reminder(s)..."
            )

        for reminder in unscheduled:
            self._schedule_reminder(
                reminder
            )

    # ======================================================
    # CREATE
    # ======================================================

    def create_reminder(
        self,
        seconds: float,
        message: str,
    ) -> tuple[bool, str]:
        """Create a new timer or reminder."""

        if seconds <= 0:
            return (
                False,
                "The timer duration must be "
                "greater than zero.",
            )

        message = message.strip()

        if not message:
            return (
                False,
                "The reminder message "
                "cannot be empty.",
            )

        reminder_id = uuid.uuid4().hex[:8]

        due_time = datetime.now() + timedelta(
            seconds=seconds
        )

        reminder = Reminder(
            reminder_id=reminder_id,
            message=message,
            due_time=due_time,
        )

        try:
            self._save_reminder(
                reminder
            )

        except Exception as error:
            return (
                False,
                "I could not save that reminder: "
                f"{error}",
            )

        with self._lock:
            self.reminders[
                reminder_id
            ] = reminder

        self._schedule_reminder(
            reminder
        )

        return (
            True,
            "Reminder set for "
            f"{self._format_duration(seconds)}.",
        )

    # ======================================================
    # SCHEDULING
    # ======================================================

    def _schedule_reminder(
        self,
        reminder: Reminder,
    ) -> None:
        """Schedule a reminder based on its due time."""

        remaining_seconds = (
            reminder.due_time
            - datetime.now()
        ).total_seconds()

        # An overdue reminder fires shortly
        # after PAT starts again.
        delay = max(
            0.1,
            remaining_seconds,
        )

        timer = threading.Timer(
            delay,
            self._fire_reminder,
            args=(reminder.reminder_id,),
        )

        timer.daemon = True

        with self._lock:
            reminder.timer = timer

        timer.start()

    # ======================================================
    # FIRE
    # ======================================================

    def _fire_reminder(
        self,
        reminder_id: str,
    ) -> None:
        """Fire a reminder."""

        with self._lock:
            reminder = self.reminders.pop(
                reminder_id,
                None,
            )

        if reminder is None:
            return

        try:
            self._delete_saved_reminder(
                reminder_id
            )

        except Exception as error:
            print(
                "[REMINDER ERROR] "
                "Could not remove reminder "
                f"from database: {error}"
            )

        message = reminder.message

        print()
        print("=" * 50)
        print(
            f"PAT REMINDER: {message}"
        )
        print("=" * 50)
        print()

        if self.on_reminder is None:
            print(
                "[REMINDER] "
                "No voice callback registered."
            )
            return

        try:
            self.on_reminder(
                message
            )

        except Exception as error:
            print(
                "[REMINDER ERROR] "
                "Voice callback failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    def create_reminder_at(
        self,
        due_time: datetime,
        message: str,
    ) -> tuple[bool, str]:
        """Create a reminder for a specific date and time."""

        now = datetime.now()

        if due_time <= now:
            return (
                False,
                "That reminder time has already passed.",
            )

        message = message.strip()

        if not message:
            return (
                False,
                "The reminder message cannot be empty.",
            )

        reminder_id = uuid.uuid4().hex[:8]

        reminder = Reminder(
            reminder_id=reminder_id,
            message=message,
            due_time=due_time,
        )

        try:
            self._save_reminder(reminder)

        except Exception as error:
            return (
                False,
                f"I could not save that reminder: {error}",
            )

        with self._lock:
            self.reminders[reminder_id] = reminder

        self._schedule_reminder(reminder)

        time_text = due_time.strftime(
            "%I:%M %p"
        ).lstrip("0")

        today = now.date()
        tomorrow = (
            now + timedelta(days=1)
        ).date()

        if due_time.date() == today:
            when_text = f"today at {time_text}"

        elif due_time.date() == tomorrow:
            when_text = f"tomorrow at {time_text}"

        else:
            when_text = (
                f"{due_time.strftime('%B')} "
                f"{due_time.day} at {time_text}"
            )

        return (
            True,
            f"Reminder set for {when_text}.",
        )

    # ======================================================
    # CANCEL
    # ======================================================

    def cancel_reminder(
        self,
        reminder_id: str,
    ) -> tuple[bool, str]:
        """Cancel an active reminder."""

        with self._lock:
            reminder = self.reminders.pop(
                reminder_id,
                None,
            )

        if reminder is None:
            return (
                False,
                "I could not find "
                "that reminder.",
            )

        if reminder.timer is not None:
            reminder.timer.cancel()

        try:
            self._delete_saved_reminder(
                reminder_id
            )

        except Exception as error:
            return (
                False,
                "The reminder was cancelled, "
                "but I could not remove it "
                f"from storage: {error}",
            )

        return (
            True,
            "Reminder cancelled.",
        )

    # ======================================================
    # LIST
    # ======================================================

    def list_reminders(
        self,
    ) -> list[Reminder]:
        """Return currently active reminders."""

        with self._lock:
            reminders = list(
                self.reminders.values()
            )

        return sorted(
            reminders,
            key=lambda reminder: reminder.due_time,
        )

    def cancel_next_reminder(
        self,
    ) -> tuple[bool, str]:
        """Cancel the reminder that will fire next."""

        reminders = self.list_reminders()

        if not reminders:
            return (
                False,
                "You do not have any active reminders.",
            )

        reminder = reminders[0]

        success, _ = self.cancel_reminder(
            reminder.reminder_id
        )

        if not success:
            return (
                False,
                "I could not cancel the reminder.",
            )

        return (
            True,
            f"Cancelled: {reminder.message}",
        )


    def cancel_all_reminders(
        self,
    ) -> tuple[bool, str]:
        """Cancel every active reminder."""

        reminders = self.list_reminders()

        if not reminders:
            return (
                False,
                "You do not have any active reminders.",
            )

        cancelled = 0

        for reminder in reminders:
            success, _ = self.cancel_reminder(
                reminder.reminder_id
            )

            if success:
                cancelled += 1

        return (
            True,
            f"Cancelled {cancelled} active "
            f"reminder{'s' if cancelled != 1 else ''}.",
        )


    # ======================================================
    # HELPERS
    # ======================================================

    @staticmethod
    def _format_duration(
        seconds: float,
    ) -> str:
        """Convert seconds to a spoken duration."""

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