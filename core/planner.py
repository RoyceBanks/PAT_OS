"""
PAT OS
core/planner.py

Converts multi-step application commands into queued tasks.
"""

from __future__ import annotations

import re

from automation.apps import open_application
from engines.task_engine import Task, TaskEngine


ACTION_PATTERN = re.compile(
    r"^(?:please\s+)?"
    r"(open|launch|start|run)\s+"
    r"(.+?)"
    r"(?:\s+for\s+me|\s+please)?$",
    flags=re.IGNORECASE,
)

COMMAND_SEPARATOR = re.compile(
    r"\s*(?:"
    r",\s*(?:and|then)\s+"
    r"|,\s*"
    r"|\s+(?:and|then)\s+"
    r")\s*",
    flags=re.IGNORECASE,
)

def split_command(command: str) -> list[str]:
    """
    Split a multi-step command into individual instructions.
    """

    cleaned_command = " ".join(command.strip().split())

    if not cleaned_command:
        return []

    sections = COMMAND_SEPARATOR.split(cleaned_command)

    cleaned_sections: list[str] = []

    for section in sections:
        section = re.sub(
            r"^(?:and|then)\s+",
            "",
            section.strip(),
            flags=re.IGNORECASE,
        )

        if section:
            cleaned_sections.append(section)

    return cleaned_sections


def extract_application_task(
    instruction: str,
    previous_action: str | None = None,
) -> tuple[str, str] | None:
    """
    Extract an action and application name from one instruction.

    The previous action allows commands such as:

        open notepad and calculator

    to treat "calculator" as "open calculator."
    """

    match = ACTION_PATTERN.match(instruction)

    if match:
        action_word = match.group(1).lower()
        app_name = match.group(2).strip()

        return action_word, app_name

    if previous_action:
        app_name = instruction.strip()

        if app_name:
            return previous_action, app_name

    return None


def create_application_plan(
    command: str,
    engine: TaskEngine,
) -> list[Task]:
    """
    Convert a command into application-opening tasks.
    """

    instructions = split_command(command)
    created_tasks: list[Task] = []

    previous_action: str | None = None

    for instruction in instructions:
        extracted = extract_application_task(
            instruction,
            previous_action,
        )

        if extracted is None:
            continue

        action_word, app_name = extracted
        previous_action = action_word

        task = engine.create_task(
            name=f"Open {app_name}",
            action="open_application",
            app_name=app_name,
        )

        created_tasks.append(task)

    return created_tasks

def is_application_plan(command: str) -> bool:
    """
    Return True when a command contains at least two
    recognizable application-launch instructions.
    """

    instructions = split_command(command)

    if len(instructions) < 2:
        return False

    previous_action: str | None = None
    recognized_steps = 0

    for instruction in instructions:
        extracted = extract_application_task(
            instruction,
            previous_action,
        )

        if extracted is None:
            return False

        action_word, _ = extracted
        previous_action = action_word
        recognized_steps += 1

    return recognized_steps >= 2



def execute_application_plan(
    command: str,
) -> tuple[bool, str]:
    """
    Create and execute all supported tasks in a command.
    """

    engine = TaskEngine()

    engine.register_handler(
        "open_application",
        open_application,
    )

    tasks = create_application_plan(command, engine)

    if len(tasks) < 2:
        return (
            False,
            "I need at least two recognized application actions "
            "to create a multi-step plan.",
        )

    completed_tasks = engine.run_all()

    successful_results: list[str] = []
    failed_results: list[str] = []

    for task in completed_tasks:
        if task.status.name == "COMPLETED":
            successful_results.append(task.result)
        else:
            failed_results.append(task.result or task.error)

    response_parts: list[str] = []

    if successful_results:
        response_parts.append(" ".join(successful_results))

    if failed_results:
        response_parts.append(
            "Some tasks failed: " + " ".join(failed_results)
        )

    return not failed_results, " ".join(response_parts)


if __name__ == "__main__":
    print("PAT Multi-Step Planner Test")
    print("Example: open notepad and launch calculator")
    print("Type 'exit' to stop.\n")

    while True:
        user_command = input("You: ").strip()

        if user_command.lower() == "exit":
            break

        success, message = execute_application_plan(user_command)

        print(f"PAT: {message}")
        print(f"Success: {success}\n")