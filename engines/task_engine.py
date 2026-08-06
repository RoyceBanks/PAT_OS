"""
PAT OS
engines/task_engine.py

Creates, queues, executes, and tracks PAT tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable
from uuid import uuid4


class TaskStatus(Enum):
    """Possible states for a PAT task."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class Task:
    """One action that PAT needs to perform."""

    name: str
    action: str
    arguments: dict[str, Any] = field(default_factory=dict)

    task_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: str = ""

    created_at: datetime = field(
        default_factory=datetime.now
    )

    started_at: datetime | None = None
    completed_at: datetime | None = None


TaskHandler = Callable[..., tuple[bool, str]]


class TaskEngine:
    """
    PAT's central task manager.

    Handlers are registered using an action name.

    Example:
        engine.register_handler(
            "open_application",
            open_application,
        )
    """

    def __init__(self) -> None:
        self.handlers: dict[str, TaskHandler] = {}
        self.queue: list[Task] = []
        self.history: list[Task] = []

    def register_handler(
        self,
        action: str,
        handler: TaskHandler,
    ) -> None:
        """Connect an action name to a Python function."""

        cleaned_action = action.strip().lower()

        if not cleaned_action:
            raise ValueError("Action name cannot be empty.")

        if not callable(handler):
            raise TypeError("Task handler must be callable.")

        self.handlers[cleaned_action] = handler

    def create_task(
        self,
        name: str,
        action: str,
        **arguments: Any,
    ) -> Task:
        """Create a task and add it to the queue."""

        task = Task(
            name=name.strip(),
            action=action.strip().lower(),
            arguments=arguments,
        )

        self.queue.append(task)

        return task

    def cancel_task(self, task_id: str) -> tuple[bool, str]:
        """Cancel a pending task."""

        for task in self.queue:
            if task.task_id == task_id:
                if task.status is not TaskStatus.PENDING:
                    return False, "That task is no longer pending."

                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.result = "Task cancelled."

                self.queue.remove(task)
                self.history.append(task)

                return True, f"Cancelled task: {task.name}."

        return False, "I could not find that task."

    def execute_task(self, task: Task) -> Task:
        """Execute one task using its registered handler."""

        if task.status is TaskStatus.CANCELLED:
            return task

        handler = self.handlers.get(task.action)

        if handler is None:
            task.status = TaskStatus.FAILED
            task.error = (
                f"No handler is registered for "
                f"'{task.action}'."
            )
            task.completed_at = datetime.now()

            return task

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        try:
            success, message = handler(**task.arguments)

            task.result = message

            if success:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.FAILED
                task.error = message

        except Exception as error:
            task.status = TaskStatus.FAILED
            task.error = str(error)
            task.result = (
                f"Task '{task.name}' failed: {error}"
            )

        finally:
            task.completed_at = datetime.now()

        return task

    def run_next(self) -> Task | None:
        """Run the next pending task in the queue."""

        if not self.queue:
            return None

        task = self.queue.pop(0)
        completed_task = self.execute_task(task)

        self.history.append(completed_task)

        return completed_task

    def run_all(self) -> list[Task]:
        """Run every task currently waiting in the queue."""

        completed_tasks: list[Task] = []

        while self.queue:
            task = self.run_next()

            if task is not None:
                completed_tasks.append(task)

        return completed_tasks

    def get_pending_tasks(self) -> list[Task]:
        """Return all tasks still waiting to run."""

        return [
            task
            for task in self.queue
            if task.status is TaskStatus.PENDING
        ]

    def get_history(self) -> list[Task]:
        """Return tasks completed during this session."""

        return self.history.copy()


task_engine = TaskEngine()


if __name__ == "__main__":
    from automation.apps import open_application

    task_engine.register_handler(
        "open_application",
        open_application,
    )

    task_engine.create_task(
        name="Open Notepad",
        action="open_application",
        app_name="notepad",
    )

    task_engine.create_task(
        name="Open Calculator",
        action="open_application",
        app_name="calculator",
    )

    print("Running PAT task queue...\n")

    results = task_engine.run_all()

    for task in results:
        print(f"Task: {task.name}")
        print(f"Status: {task.status.name}")
        print(f"Result: {task.result}")
        print("-" * 40)