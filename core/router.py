"""
PAT OS
core/router.py

Routes user commands to the correct PAT module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from automation.apps import open_application
from brain.ai import ask_ai

from brain.memory import (
    save_memory,
    get_memory,
    list_memories,
)


class Intent(Enum):
    """Commands currently understood by PAT."""

    OPEN_APPLICATION = auto()
    SAVE_MEMORY = auto()
    GET_MEMORY = auto()
    EXIT = auto()
    GENERAL_AI = auto()


@dataclass
class RouteResult:
    """Result returned after processing a user command."""

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


OPEN_APP_PATTERNS = (
    r"^(?:please\s+)?open\s+(.+)$",
    r"^(?:please\s+)?launch\s+(.+)$",
    r"^(?:please\s+)?start\s+(.+)$",
    r"^(?:please\s+)?run\s+(.+)$",
)


def clean_command(command: str) -> str:
    """Normalize a command before routing it."""

    return " ".join(command.strip().lower().split())


def extract_application_name(command: str) -> str | None:
    """
    Extract an application name from commands such as:

    open Chrome
    launch Discord
    start calculator
    """

    for pattern in OPEN_APP_PATTERNS:
        match = re.match(pattern, command, flags=re.IGNORECASE)

        if match:
            app_name = match.group(1).strip()

            # Remove optional words from the end.
            app_name = re.sub(
                r"\s+(?:please|for me)$",
                "",
                app_name,
                flags=re.IGNORECASE,
            )

            return app_name

    return None

def extract_memory(command):

    remember = re.match(
        r"remember\s+my\s+(.+?)\s+is\s+(.+)",
        command,
        re.IGNORECASE,
    )

    if remember:
        return (
            remember.group(1).strip(),
            remember.group(2).strip(),
        )

    recall = re.match(
        r"(?:what is|what's)\s+my\s+(.+)",
        command,
        re.IGNORECASE,
    )

    if recall:
        return (
            recall.group(1).strip(),
            None,
        )

    return None

def detect_intent(command: str) -> tuple[Intent, str | None]:
    """
    Determine what the user wants PAT to do.

    Returns:
        A tuple containing:
        - detected Intent
        - optional extracted value, such as an application name
    """
    
    cleaned_command = clean_command(command)

    if cleaned_command in EXIT_COMMANDS:
        return Intent.EXIT, None

    application_name = extract_application_name(cleaned_command)

    if application_name:
        return Intent.OPEN_APPLICATION, application_name

    return Intent.GENERAL_AI, None

    memory = extract_memory(command)

    if memory:

        key, value = memory

    if value is None:
        return Intent.GET_MEMORY, key

    return Intent.SAVE_MEMORY, memory


def route_command(command: str) -> RouteResult:
    """
    Route a command to the appropriate PAT module.
    """

    if not command or not command.strip():
        return RouteResult(
            intent=Intent.GENERAL_AI,
            response="I did not receive a command.",
            success=False,
        )

    intent, extracted_value = detect_intent(command)

    if intent is Intent.EXIT:
        return RouteResult(
            intent=intent,
            response="Shutting down PAT. Goodbye.",
            should_exit=True,
        )

    if intent is Intent.OPEN_APPLICATION:
        if extracted_value is None:
            return RouteResult(
                intent=intent,
                response="I could not determine which application to open.",
                success=False,
            )

        success, message = open_application(extracted_value)

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    try:
        response = ask_ai(command)

        return RouteResult(
            intent=Intent.GENERAL_AI,
            response=response,
        )

    except Exception as error:
        return RouteResult(
            intent=Intent.GENERAL_AI,
            response=f"I could not contact my AI engine: {error}",
            success=False,
        )
    if intent is Intent.SAVE_MEMORY:

        key, value = extracted_value

        success, message = save_memory(key, value)

        return RouteResult(
            intent=intent,
            esponse=message,
            success=success,
        )


    if intent is Intent.GET_MEMORY:

        value = get_memory(extracted_value)

        if value:

            return RouteResult(
                intent=intent,
                response=f"Your {extracted_value} is {value}.",
            )

        return RouteResult(
            intent=intent,
            response=f"I don't know your {extracted_value} yet.",
            success=False,
        )

if __name__ == "__main__":
    print("PAT Router Test")
    print("Type 'exit' to stop.\n")

    while True:
        user_command = input("You: ")

        result = route_command(user_command)

        print(f"Intent: {result.intent.name}")
        print(f"PAT: {result.response}\n")

        if result.should_exit:
            break