"""
PAT OS
core/router.py

Routes user commands to the correct PAT module.
"""

from __future__ import annotations

from engines.reminder_engine import reminder_engine
from datetime import datetime
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any
from automation.system import get_system_status
from automation.apps import open_application
from brain.ai import ask_ai
from brain.memory import get_memory, save_memory
from core.planner import (
    execute_application_plan,
    is_application_plan,
)
from automation.browser import (
    is_known_website,
    open_website,
    search_web,
)


class Intent(Enum):
    """Command types currently understood by PAT."""

    APPLICATION_PLAN = auto()
    OPEN_APPLICATION = auto()
    OPEN_WEBSITE = auto()
    WEB_SEARCH = auto()
    SET_TIMER = auto()
    SET_REMINDER = auto()
    LIST_REMINDERS = auto()
    CANCEL_REMINDER = auto()
    CANCEL_ALL_REMINDERS = auto()
    SYSTEM_STATUS = auto()
    SAVE_MEMORY = auto()
    GET_MEMORY = auto()
    EXIT = auto()
    GENERAL_AI = auto()


@dataclass
class RouteResult:
    """Standard result returned after routing a command."""

    intent: Intent
    response: str
    success: bool = True
    should_exit: bool = False


EXIT_COMMANDS = {
    "exit",
    "quit",
    "goodbye",
    "shut down pat",
    "shutdown pat",
    "close pat",
}

SYSTEM_STATUS_COMMANDS = {
    "system status",
    "computer status",
    "check system status",
    "check my computer",
    "how is my computer",
    "how is my computer doing",
    "check cpu and memory",
    "cpu and memory status",
}


OPEN_APP_PATTERNS = (
    r"^(?:please\s+)?open(?:\s+up)?\s+(.+)$",
    r"^(?:please\s+)?launch\s+(.+)$",
    r"^(?:please\s+)?start(?:\s+up)?\s+(.+)$",
    r"^(?:please\s+)?run\s+(.+)$",
)


def clean_command(command: str) -> str:
    """
    Normalize a command before routing it.

    Example:
        "  Open   Notepad  " becomes "open notepad"
    """

    if not isinstance(command, str):
        return ""

    return " ".join(command.strip().lower().split())


def extract_application_name(command: str) -> str | None:
    """
    Extract an application name from a single-app command.

    Examples:
        open Firefox
        launch calculator
        start Discord
        run VS Code
    """

    for pattern in OPEN_APP_PATTERNS:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        app_name = match.group(1).strip()

        app_name = re.sub(
            r"\s+(?:please|for me)$",
            "",
            app_name,
            flags=re.IGNORECASE,
        ).strip()

        if app_name:
            return app_name

    return None


def extract_memory(
    command: str,
) -> tuple[str, str | None] | None:
    """
    Extract a memory command.

    Save example:
        remember my favorite browser is Firefox

    Recall examples:
        what is my favorite browser
        what's my favorite browser
    """

    save_match = re.match(
        r"^(?:please\s+)?remember\s+"
        r"(?:that\s+)?my\s+(.+?)\s+is\s+(.+?)"
        r"(?:\s+please)?[?.!]*$",
        command,
        flags=re.IGNORECASE,
    )

    if save_match:
        memory_key = save_match.group(1).strip(" ?.!")
        memory_value = save_match.group(2).strip(" ?.!")

        if memory_key and memory_value:
            return memory_key, memory_value

    recall_match = re.match(
        r"^(?:what\s+is|what's)\s+my\s+(.+?)[?.!]*$",
        command,
        flags=re.IGNORECASE,
    )

    if recall_match:
        memory_key = recall_match.group(1).strip(" ?.!")

        if memory_key:
            return memory_key, None

    return None

def extract_search_query(command: str) -> str | None:
    """Extract a web search query from a command."""

    patterns = (
        r"^(?:please\s+)?search(?:\s+the)?\s+web\s+for\s+(.+)$",
        r"^(?:please\s+)?search\s+for\s+(.+)$",
        r"^(?:please\s+)?look\s+up\s+(.+)$",
        r"^(?:please\s+)?google\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            query = match.group(1).strip(" ?.!")

            if query:
                return query

    return None


def extract_website_name(command: str) -> str | None:
    """Extract a known website from a command."""

    patterns = (
        r"^(?:please\s+)?open(?:\s+up)?\s+(.+)$",
        r"^(?:please\s+)?visit\s+(.+)$",
        r"^(?:please\s+)?go\s+to\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        website_name = match.group(1).strip(" ?.!")

        website_name = re.sub(
            r"\s+(?:website|site)$",
            "",
            website_name,
            flags=re.IGNORECASE,
        ).strip()

        if is_known_website(website_name):
            return website_name

    return None

def parse_duration(
    amount: str,
    unit: str,
) -> float | None:
    """Convert a spoken duration into seconds."""

    try:
        value = float(amount)
    except ValueError:
        return None

    if value <= 0:
        return None

    normalized_unit = unit.lower().rstrip("s")

    multipliers = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
    }

    multiplier = multipliers.get(normalized_unit)

    if multiplier is None:
        return None

    return value * multiplier


def extract_timer(
    command: str,
) -> tuple[float, str] | None:
    """
    Extract commands such as:
    set a timer for 30 seconds
    timer for 5 minutes
    """

    match = re.match(
        r"^(?:please\s+)?"
        r"(?:set\s+)?(?:a\s+)?timer\s+for\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(seconds?|minutes?|hours?)"
        r"[?.!]*$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    amount = match.group(1)
    unit = match.group(2)

    seconds = parse_duration(
        amount,
        unit,
    )

    if seconds is None:
        return None

    return (
        seconds,
        "Your timer is finished.",
    )


def extract_reminder(
    command: str,
) -> tuple[float, str] | None:
    """
    Extract commands such as:
    remind me in 10 minutes to check the cooler
    """

    match = re.match(
        r"^(?:please\s+)?"
        r"remind\s+me\s+in\s+"
        r"(\d+(?:\.\d+)?)\s+"
        r"(seconds?|minutes?|hours?)\s+"
        r"to\s+(.+?)"
        r"[?.!]*$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    amount = match.group(1)
    unit = match.group(2)
    message = match.group(3).strip(" ?.!")

    seconds = parse_duration(
        amount,
        unit,
    )

    if seconds is None or not message:
        return None

    return (
        seconds,
        f"Reminder: {message}.",
    )

def detect_intent(
    command: str,
) -> tuple[Intent, Any | None]:
    """
    Determine what the user wants PAT to do.

    Returns:
        A tuple containing:
        - The detected intent
        - Any extracted data required by that intent
    """

    cleaned_command = clean_command(command)

    # Empty command
    if not cleaned_command:
        return Intent.GENERAL_AI, None

    # Exit PAT
    if cleaned_command in EXIT_COMMANDS:
        return Intent.EXIT, None

    # System information
    if cleaned_command in SYSTEM_STATUS_COMMANDS:
        return Intent.SYSTEM_STATUS, None

    # Memory commands
    memory = extract_memory(cleaned_command)

    if memory is not None:
        memory_key, memory_value = memory

        if memory_value is None:
            return Intent.GET_MEMORY, memory_key

        return Intent.SAVE_MEMORY, (
            memory_key,
            memory_value,
        )

    if cleaned_command in {
        "what reminders do i have",
        "what timers do i have",
        "list reminders",
        "list my reminders",
        "show reminders",
    }:
        return Intent.LIST_REMINDERS, None

    if cleaned_command in {
        "cancel all reminders",
        "cancel all timers",
        "cancel all timers and reminders",
        "clear all reminders",
        "clear all timers",
    }:
        return Intent.CANCEL_ALL_REMINDERS, None


    if cleaned_command in {
        "cancel my reminder",
        "cancel my timer",
        "cancel reminder",
        "cancel timer",
        "cancel my next reminder",
        "cancel my next timer",
        "cancel the reminder",
        "cancel the timer",
    }:
        return Intent.CANCEL_REMINDER, None

    reminder = extract_reminder(
        cleaned_command
    )

    if reminder is not None:
        return Intent.SET_REMINDER, reminder


    timer = extract_timer(
        cleaned_command
    )

    if timer is not None:
        return Intent.SET_TIMER, timer

    
    # Web search commands
    search_query = extract_search_query(
        cleaned_command
    )

    if search_query:
        return Intent.WEB_SEARCH, search_query

    # Known website commands
    website_name = extract_website_name(
        cleaned_command
    )

    if website_name:
        return Intent.OPEN_WEBSITE, website_name

    # Multi-application commands
    if is_application_plan(cleaned_command):
        return (
            Intent.APPLICATION_PLAN,
            cleaned_command,
        )

    # Single application command
    application_name = extract_application_name(
        cleaned_command
    )

    if application_name:
        return (
            Intent.OPEN_APPLICATION,
            application_name,
        )

    # Anything else goes to PAT's AI.
    return Intent.GENERAL_AI, None


def route_command(command: str) -> RouteResult:
    """
    Route a user command to the correct PAT module.
    """

    if not isinstance(command, str) or not command.strip():
        return RouteResult(
            intent=Intent.GENERAL_AI,
            response="I did not receive a command.",
            success=False,
        )

    intent, extracted_value = detect_intent(command)

    # ======================================================
    # EXIT
    # ======================================================

    if intent is Intent.EXIT:
        return RouteResult(
            intent=intent,
            response="Shutting down PAT. Goodbye.",
            success=True,
            should_exit=True,
        )

    # ======================================================
    # SYSTEM STATUS
    # ======================================================

    if intent is Intent.SYSTEM_STATUS:
        success, message = get_system_status()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent in {
        Intent.SET_TIMER,
        Intent.SET_REMINDER,
    }:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "that timer or reminder."
                ),
                success=False,
            )

        seconds, reminder_message = extracted_value

        if not isinstance(seconds, (int, float)):
            return RouteResult(
                intent=intent,
                response="The duration was invalid.",
                success=False,
            )

        if not isinstance(reminder_message, str):
            return RouteResult(
                intent=intent,
                response="The reminder message was invalid.",
                success=False,
            )

        success, message = reminder_engine.create_reminder(
            seconds,
            reminder_message,
        )

        if success and intent is Intent.SET_TIMER:
            message = message.replace(
                "Reminder set",
                "Timer set",
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


        if intent is Intent.LIST_REMINDERS:
            reminders = reminder_engine.list_reminders()

            if not reminders:
                return RouteResult(
                    intent=intent,
                    response=(
                        "You do not have any active "
                        "timers or reminders."
                    ),
                    success=True,
                )

            reminder_text = []

            for reminder in reminders:
                remaining_seconds = max(
                    0,
                    (
                        reminder.due_time
                        - datetime.now()
                    ).total_seconds(),
                )

                remaining_minutes = int(
                    remaining_seconds // 60
                )

                if remaining_minutes >= 1:
                    remaining = (
                        f"about {remaining_minutes} minutes"
                    )
                else:
                    remaining = (
                        f"about {int(remaining_seconds)} seconds"
                    )

                reminder_text.append(
                    f"{reminder.message} in {remaining}"
                )

            return RouteResult(
                intent=intent,
                response=(
                    "You have "
                    f"{len(reminders)} active. "
                    + ". ".join(reminder_text)
                ),
                success=True,
            )
    if intent is Intent.CANCEL_REMINDER:
        success, message = (
            reminder_engine.cancel_next_reminder()
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.CANCEL_ALL_REMINDERS:
        success, message = (
            reminder_engine.cancel_all_reminders()
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # WEB SEARCH
    # ======================================================

    if intent is Intent.WEB_SEARCH:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "the search request."
                ),
                success=False,
            )

        success, message = search_web(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # WEBSITE
    # ======================================================

    if intent is Intent.OPEN_WEBSITE:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not determine "
                    "which website to open."
                ),
                success=False,
            )

        success, message = open_website(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # APPLICATION PLAN
    # ======================================================

    if intent is Intent.APPLICATION_PLAN:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "that application plan."
                ),
                success=False,
            )

        success, message = execute_application_plan(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # OPEN APPLICATION
    # ======================================================

    if intent is Intent.OPEN_APPLICATION:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not determine "
                    "which application to open."
                ),
                success=False,
            )

        success, message = open_application(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # SAVE MEMORY
    # ======================================================

    if intent is Intent.SAVE_MEMORY:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "that memory."
                ),
                success=False,
            )

        memory_key, memory_value = extracted_value

        if not isinstance(memory_key, str):
            return RouteResult(
                intent=intent,
                response="The memory name was invalid.",
                success=False,
            )

        if not isinstance(memory_value, str):
            return RouteResult(
                intent=intent,
                response="The memory value was invalid.",
                success=False,
            )

        success, message = save_memory(
            memory_key,
            memory_value,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # GET MEMORY
    # ======================================================

    if intent is Intent.GET_MEMORY:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not determine "
                    "which memory to retrieve."
                ),
                success=False,
            )

        memory_value = get_memory(
            extracted_value
        )

        if memory_value is None:
            return RouteResult(
                intent=intent,
                response=(
                    f"I don't know your "
                    f"{extracted_value} yet."
                ),
                success=False,
            )

        return RouteResult(
            intent=intent,
            response=(
                f"Your {extracted_value} is "
                f"{memory_value}."
            ),
            success=True,
        )

    # ======================================================
    # GENERAL AI
    # ======================================================

    try:
        ai_response = ask_ai(command)

        return RouteResult(
            intent=Intent.GENERAL_AI,
            response=ai_response,
            success=True,
        )

    except Exception as error:
        return RouteResult(
            intent=Intent.GENERAL_AI,
            response=(
                "I could not contact my AI engine: "
                f"{error}"
            ),
            success=False,
        )

if __name__ == "__main__":
    print("PAT Router Test")
    print("Type 'exit' to stop.\n")

    while True:
        user_command = input("You: ").strip()

        result = route_command(user_command)

        print(f"Intent: {result.intent.name}")
        print(f"PAT: {result.response}")
        print(f"Success: {result.success}\n")

        if result.should_exit:
            break