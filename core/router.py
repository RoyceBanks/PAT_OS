"""
PAT OS
core/router.py

Routes user commands to the correct PAT module.
"""

from __future__ import annotations

from internet.research import research_web
from engines.reminder_engine import reminder_engine
from datetime import datetime, timedelta
import re
import webbrowser
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
from brain.session_context import (
    get_last_research_query,
    get_research_sources,
    remember_research,
)
from automation.system_controls import (
    adjust_volume_percent,
    get_volume_percent,
    lock_computer,
    mute_audio,
    set_volume_percent,
    take_screenshot,
    unmute_audio,
    volume_down,
    volume_up,
)
from automation.window_controls import (
    close_window,
    focus_window,
    maximize_window,
    minimize_window,
    show_desktop,
)
from automation.clipboard import (
    clear_clipboard,
    get_clipboard,
    set_clipboard,
)
from automation.file_manager import (
    create_folder,
    find_file,
    list_files,
    open_folder,
)
from automation.file_manager import (
    create_folder,
    find_file,
    list_files,
    open_folder,
    open_found_file,
    open_found_file_folder,
)



class Intent(Enum):
    """Command types currently understood by PAT."""

    APPLICATION_PLAN = auto()
    OPEN_APPLICATION = auto()
    OPEN_WEBSITE = auto()
    WEB_SEARCH = auto()
    WEB_RESEARCH = auto()
    LIST_RESEARCH_SOURCES = auto()
    OPEN_RESEARCH_SOURCE = auto()
    OPEN_FOLDER = auto()
    LIST_FILES = auto()
    CREATE_FOLDER = auto()
    FIND_FILE = auto()
    OPEN_FOUND_FILE = auto()
    OPEN_FOUND_FILE_FOLDER = auto()
    GET_CLIPBOARD = auto()
    SET_CLIPBOARD = auto()
    CLEAR_CLIPBOARD = auto()
    SWITCH_WINDOW = auto()
    MINIMIZE_WINDOW = auto()
    MAXIMIZE_WINDOW = auto()
    CLOSE_WINDOW = auto()
    SHOW_DESKTOP = auto()
    GET_VOLUME = auto()
    SET_VOLUME = auto()
    ADJUST_VOLUME = auto()
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
    MUTE_AUDIO = auto()
    UNMUTE_AUDIO = auto()
    TAKE_SCREENSHOT = auto()
    LOCK_COMPUTER = auto()
    SET_TIMER = auto()
    SET_REMINDER = auto()
    SET_SCHEDULED_REMINDER = auto()
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
    Normalize a command before routing.
    """

    if not isinstance(command, str):
        return ""

    cleaned = " ".join(
        command.strip().lower().split()
    )

    # Remove normal sentence punctuation from
    # the end of spoken commands.
    cleaned = re.sub(
        r"[?.!,;:]+$",
        "",
        cleaned,
    )

    return cleaned.strip()

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

def extract_source_number(
    command: str,
) -> int | None:
    """Extract source number from commands."""

    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }

    match = re.match(
        r"^(?:please\s+)?open\s+"
        r"(?:the\s+)?"
        r"(first|second|third|fourth|fifth|\d+)"
        r"\s+(?:source|article)$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        match = re.match(
            r"^(?:please\s+)?open\s+"
            r"(?:source|article)\s+"
            r"(first|second|third|fourth|fifth|\d+)$",
            command,
            flags=re.IGNORECASE,
        )

    if not match:
        return None

    value = match.group(1).lower()

    if value in words:
        return words[value]

    try:
        return int(value)
    except ValueError:
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

def extract_scheduled_reminder(
    command: str,
) -> tuple[datetime, str] | None:
    """
    Understand reminders such as:

    remind me at 3:30 pm to check the cooler
    remind me tomorrow at 8 am to call John
    remind me today at 6 pm to go to the gym
    """

    match = re.match(
        r"^(?:please\s+)?"
        r"remind\s+me\s+"
        r"(?:(today|tomorrow)\s+)?"
        r"at\s+"
        r"(\d{1,2})"
        r"(?::(\d{2}))?"
        r"\s*"
        r"(am|pm|a\.m\.|p\.m\.)"
        r"\s+to\s+"
        r"(.+?)"
        r"[?.!]*$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    day_word = match.group(1)

    hour = int(
        match.group(2)
    )

    minute = int(
        match.group(3) or 0
    )

    meridiem = (
        match.group(4)
        .lower()
        .replace(".", "")
    )

    message = match.group(5).strip(
        " ?.!"
    )

    if not 1 <= hour <= 12:
        return None

    if not 0 <= minute <= 59:
        return None

    if hour == 12:
        hour = 0

    if meridiem == "pm":
        hour += 12

    now = datetime.now()

    due_time = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if day_word == "tomorrow":
        due_time += timedelta(
            days=1
        )

    elif day_word == "today":
        pass

    elif due_time <= now:
        # If no day was specified and that
        # time already passed today,
        # assume tomorrow.
        due_time += timedelta(
            days=1
        )

    return (
        due_time,
        f"Reminder: {message}.",
    )

def extract_research_query(
    command: str,
) -> str | None:
    """
    Detect commands where PAT should use
    live internet research.
    """

    # Commands asking for current/latest information.
    latest_patterns = (
        r"^what(?:'s|\s+is)\s+the\s+latest\s+"
        r"(.+?)\s+news$",

        r"^what(?:'s|\s+is)\s+the\s+latest\s+news\s+"
        r"(?:on|about)\s+(.+)$",

        r"^what(?:'s|\s+is)\s+the\s+latest\s+"
        r"(?:on|about)\s+(.+)$",

        r"^latest\s+(.+?)\s+news$",

        r"^latest\s+news\s+"
        r"(?:on|about)\s+(.+)$",

        r"^what(?:'s|\s+is)\s+new\s+"
        r"with\s+(.+)$",

        r"^what(?:'s|\s+is)\s+happening\s+"
        r"with\s+(.+)$",
    )

    for pattern in latest_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            topic = match.group(1).strip(
                " ?.!"
            )

            if topic:
                return f"latest {topic} news"

    # Explicit research commands.
    research_patterns = (
        r"^(?:please\s+)?research\s+(.+)$",

        r"^(?:please\s+)?"
        r"search(?:\s+the)?\s+web\s+and\s+"
        r"tell\s+me\s+(?:about\s+)?(.+)$",

        r"^(?:please\s+)?"
        r"search(?:\s+the)?\s+internet\s+and\s+"
        r"tell\s+me\s+(?:about\s+)?(.+)$",

        r"^(?:please\s+)?"
        r"look\s+online\s+and\s+"
        r"tell\s+me\s+(?:about\s+)?(.+)$",
    )

    for pattern in research_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            query = match.group(1).strip(
                " ?.!"
            )

            if query:
                return query

    return None

def extract_research_followup(
    command: str,
) -> str | None:
    """
    Resolve natural follow-up questions against
    PAT's previous web research topic.
    """

    previous_query = get_last_research_query()

    if not previous_query:
        return None

    patterns = (
        r"^what\s+about\s+(.+)$",
        r"^how\s+about\s+(.+)$",
        r"^and\s+what\s+about\s+(.+)$",
        r"^and\s+how\s+about\s+(.+)$",
        r"^tell\s+me\s+more(?:\s+about\s+(.+))?$",
        r"^how\s+much\s+(?:is|does)\s+(.+)$",
        r"^when\s+(?:is|was|did|does)\s+(.+)$",
        r"^compare\s+(.+)$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        detail = ""

        if match.lastindex:
            detail = (
                match.group(1) or ""
            ).strip(" ?.!")

        if detail:
            return (
                f"{previous_query} "
                f"follow up {detail}"
            )

        return (
            f"{previous_query} more information"
        )

    return None

def extract_fresh_information_query(
    command: str,
) -> str | None:
    """
    Detect questions that require current internet data.

    This acts as a fallback even when speech recognition
    slightly mangles a name or topic.
    """

    cleaned = command.strip(" ?.!")

    freshness_terms = (
        "latest",
        "latest news",
        "today",
        "today's",
        "current",
        "currently",
        "recent",
        "recent news",
        "newest",
        "news about",
        "news on",
        "what's happening",
        "what is happening",
    )

    for term in freshness_terms:
        if term in cleaned.lower():
            return cleaned

    return None

def detect_system_control(
    command: str,
) -> Intent | None:
    """Detect approved Windows system controls."""

    command = command.strip().lower()

    # Volume up
    volume_up_patterns = (
        r"^volume up$",
        r"^turn (?:the )?volume up$",
        r"^turn up (?:the )?volume$",
        r"^increase (?:the )?volume$",
        r"^raise (?:the )?volume$",
        r"^make it louder$",
        r"^turn it up$",
    )

    for pattern in volume_up_patterns:
        if re.match(pattern, command):
            return Intent.VOLUME_UP

    # Volume down
    volume_down_patterns = (
        r"^volume down$",
        r"^turn (?:the )?volume down$",
        r"^turn down (?:the )?volume$",
        r"^decrease (?:the )?volume$",
        r"^lower (?:the )?volume$",
        r"^make it quieter$",
        r"^turn it down$",
    )

    for pattern in volume_down_patterns:
        if re.match(pattern, command):
            return Intent.VOLUME_DOWN

        mute_commands = {
        "mute",
        "mute computer",
        "mute the computer",
        "mute my computer",
        "mute pc",
        "mute the pc",
        "mute my pc",
        "mute volume",
        "mute the volume",
        "mute system audio",
    }

    unmute_commands = {
        "unmute",
        "unmute computer",
        "unmute the computer",
        "unmute my computer",
        "unmute pc",
        "unmute the pc",
        "unmute my pc",
        "unmute volume",
        "unmute the volume",
        "unmute system audio",
    }

    screenshot_commands = {
        "take a screenshot",
        "take screenshot",
        "capture my screen",
        "capture the screen",
        "screenshot",
        "screenshot my screen",
    }

    lock_commands = {
        "lock my computer",
        "lock the computer",
        "lock my pc",
        "lock the pc",
    }

    if command in mute_commands:
        return Intent.MUTE_AUDIO

    if command in unmute_commands:
        return Intent.UNMUTE_AUDIO

    if command in screenshot_commands:
        return Intent.TAKE_SCREENSHOT

    if command in lock_commands:
        return Intent.LOCK_COMPUTER

    return None

def extract_volume_command(
    command: str,
) -> tuple[Intent, int | None] | None:
    """
    Detect exact volume commands.

    Examples:
        set volume to 40 percent
        increase volume by 10 percent
        lower volume by 20 percent
        what's the volume at
    """

    command = command.strip().lower()

    get_commands = {
        "what is the volume",
        "what's the volume",
        "what is the volume at",
        "what's the volume at",
        "what is my volume at",
        "what's my volume at",
        "current volume",
        "check the volume",
    }

    if command in get_commands:
        return Intent.GET_VOLUME, None

    set_patterns = (
        r"^set (?:the )?volume to (\d{1,3})(?: percent|%)?$",
        r"^change (?:the )?volume to (\d{1,3})(?: percent|%)?$",
        r"^volume to (\d{1,3})(?: percent|%)?$",
        r"^volume (\d{1,3})(?: percent|%)?$",
    )

    for pattern in set_patterns:
        match = re.match(
            pattern,
            command,
        )

        if match:
            value = int(match.group(1))

            if 0 <= value <= 100:
                return (
                    Intent.SET_VOLUME,
                    value,
                )

    increase_patterns = (
        r"^increase (?:the )?volume by (\d{1,3})(?: percent|%)?$",
        r"^raise (?:the )?volume by (\d{1,3})(?: percent|%)?$",
        r"^turn (?:the )?volume up by (\d{1,3})(?: percent|%)?$",
        r"^turn up (?:the )?volume by (\d{1,3})(?: percent|%)?$",
    )

    for pattern in increase_patterns:
        match = re.match(
            pattern,
            command,
        )

        if match:
            return (
                Intent.ADJUST_VOLUME,
                int(match.group(1)),
            )

    decrease_patterns = (
        r"^decrease (?:the )?volume by (\d{1,3})(?: percent|%)?$",
        r"^lower (?:the )?volume by (\d{1,3})(?: percent|%)?$",
        r"^turn (?:the )?volume down by (\d{1,3})(?: percent|%)?$",
        r"^turn down (?:the )?volume by (\d{1,3})(?: percent|%)?$",
    )

    for pattern in decrease_patterns:
        match = re.match(
            pattern,
            command,
        )

        if match:
            return (
                Intent.ADJUST_VOLUME,
                -int(match.group(1)),
            )

    return None

def extract_window_command(
    command: str,
) -> tuple[Intent, str | None] | None:
    """
    Detect approved desktop window commands.

    Examples:
        switch to firefox
        minimize discord
        maximize steam
        close notepad
        show desktop
    """

    command = command.strip().lower()

    show_desktop_commands = {
        "show desktop",
        "show the desktop",
        "show me the desktop",
        "go to desktop",
        "go to the desktop",
    }

    if command in show_desktop_commands:
        return Intent.SHOW_DESKTOP, None

    patterns = (
        (
            Intent.SWITCH_WINDOW,
            (
                r"^switch to (.+)$",
                r"^go to (.+)$",
                r"^focus (.+)$",
                r"^bring up (.+)$",
                r"^bring (.+) to the front$",
            ),
        ),
        (
            Intent.MINIMIZE_WINDOW,
            (
                r"^minimize (.+)$",
                r"^minimise (.+)$",
            ),
        ),
        (
            Intent.MAXIMIZE_WINDOW,
            (
                r"^maximize (.+)$",
                r"^maximise (.+)$",
            ),
        ),
        (
            Intent.CLOSE_WINDOW,
            (
                r"^close (.+)$",
            ),
        ),
    )

    for intent, intent_patterns in patterns:
        for pattern in intent_patterns:
            match = re.match(
                pattern,
                command,
                flags=re.IGNORECASE,
            )

            if match:
                application = match.group(1).strip()

                if application:
                    return intent, application

    return None

def extract_clipboard_command(
    command: str,
) -> tuple[Intent, str | None] | None:
    """Detect explicit clipboard commands."""

    command = command.strip()

    lower = command.lower()

    get_commands = {
        "what is on my clipboard",
        "what's on my clipboard",
        "read my clipboard",
        "read the clipboard",
        "check my clipboard",
    }

    if lower in get_commands:
        return Intent.GET_CLIPBOARD, None

    clear_commands = {
        "clear my clipboard",
        "clear the clipboard",
        "empty my clipboard",
        "empty the clipboard",
    }

    if lower in clear_commands:
        return Intent.CLEAR_CLIPBOARD, None

    patterns = (
        r"^copy (.+?) to my clipboard$",
        r"^copy (.+?) to the clipboard$",
        r"^put (.+?) on my clipboard$",
        r"^put (.+?) in my clipboard$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            text = match.group(1).strip()

            if text:
                return (
                    Intent.SET_CLIPBOARD,
                    text,
                )

    return None

def extract_file_command(
    command: str,
) -> tuple[Intent, object] | None:
    """
    Detect approved file-management commands.

    Examples:
        open my downloads folder
        list files in downloads
        create a folder called projects in documents
        find file report.pdf
    """

    command = command.strip().lower()

    locations = (
        "desktop",
        "documents",
        "downloads",
        "pictures",
        "photos",
        "videos",
        "music",
    )

    # Open folder
    for location in locations:
        open_commands = {
            f"open {location}",
            f"open my {location}",
            f"open {location} folder",
            f"open my {location} folder",
        }

        if command in open_commands:
            return Intent.OPEN_FOLDER, location

    # List folder contents
    list_patterns = (
        r"^list files in (?:my )?(.+?)(?: folder)?$",
        r"^show files in (?:my )?(.+?)(?: folder)?$",
        r"^what files are in (?:my )?(.+?)(?: folder)?$",
        r"^what is in (?:my )?(.+?)(?: folder)?$",
        r"^what's in (?:my )?(.+?)(?: folder)?$",
    )

    for pattern in list_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            location = match.group(1).strip()

            if location in locations:
                return (
                    Intent.LIST_FILES,
                    location,
                )

    # Create folder
    create_patterns = (
        r"^create (?:a )?folder called (.+?) in (?:my )?(.+)$",
        r"^create (?:a )?folder named (.+?) in (?:my )?(.+)$",
        r"^make (?:a )?folder called (.+?) in (?:my )?(.+)$",
        r"^make (?:a )?folder named (.+?) in (?:my )?(.+)$",
    )

    for pattern in create_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            folder_name = match.group(1).strip()
            location = match.group(2).strip()

            if location in locations:
                return (
                    Intent.CREATE_FOLDER,
                    (
                        location,
                        folder_name,
                    ),
                )

    # Find file
    find_patterns = (
        r"^find (?:the )?file(?:\s*[:,]\s*|\s+)(.+)$",
        r"^find (.+?) file$",
        r"^search for (?:the )?file(?:\s*[:,]\s*|\s+)(.+)$",
        r"^look for (?:the )?file(?:\s*[:,]\s*|\s+)(.+)$",
    )

    for pattern in find_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            filename = match.group(1).strip()

            if filename:
                return (
                    Intent.FIND_FILE,
                    filename,
                )

    return None

def extract_file_result_command(
    command: str,
) -> tuple[Intent, int] | None:
    """Detect commands referring to previous file-search results."""

    command = command.strip().lower()

    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }

    folder_patterns = (
        r"^open (?:the )?folder containing (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)(?: file| result| one)?$",
        r"^open (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+) file folder$",
    )

    for pattern in folder_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            value = match.group(1).lower()

            number = (
                words[value]
                if value in words
                else int(value)
            )

            return (
                Intent.OPEN_FOUND_FILE_FOLDER,
                number,
            )

    file_patterns = (
        r"^open (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+) file$",
        r"^open file (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+)$",
        r"^open (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+) result$",
        r"^open (?:the )?(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+) one$",
    )

    for pattern in file_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if match:
            value = match.group(1).lower()

            number = (
                words[value]
                if value in words
                else int(value)
            )

            return (
                Intent.OPEN_FOUND_FILE,
                number,
            )

    return None






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

    #
    volume_command = extract_volume_command(
        cleaned_command
    )

    if volume_command is not None:
        return volume_command


    system_control = detect_system_control(
        cleaned_command
    )

    if system_control is not None:
        return system_control, None

    system_control = detect_system_control(
        cleaned_command
    )

    if system_control is not None:
        return system_control, None


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

    scheduled_reminder = (
        extract_scheduled_reminder(
            cleaned_command
        )
    )

    if scheduled_reminder is not None:
        return (
            Intent.SET_SCHEDULED_REMINDER,
            scheduled_reminder,
        )

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

    window_command = extract_window_command(
        cleaned_command
    )

    if window_command is not None:
        return window_command

    file_command = extract_file_command(
        cleaned_command
    )

    if file_command is not None:
        return file_command

    file_result_command = extract_file_result_command(
        cleaned_command
    )

    if file_result_command is not None:
        return file_result_command

    
    # Web search commands

    if cleaned_command in {
        "what sources did you use",
        "what sources did you use?",
        "list sources",
        "show sources",
        "show me the sources",
    }:
        return (
            Intent.LIST_RESEARCH_SOURCES,
            None,
        )


    source_number = extract_source_number(
        cleaned_command
    )

    if source_number is not None:
        return (
            Intent.OPEN_RESEARCH_SOURCE,
            source_number,
        )

    research_query = extract_research_query(
        cleaned_command
    )

    fresh_query = extract_fresh_information_query(
        cleaned_command
    )

    if fresh_query:
        return (
            Intent.WEB_RESEARCH,
            fresh_query,
        )


    if research_query:
        return (
            Intent.WEB_RESEARCH,
            research_query,
        )
    
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


    research_followup = extract_research_followup(
        cleaned_command
    )

    if research_followup:
        return (
            Intent.WEB_RESEARCH,
            research_followup,
        )

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


    clipboard_command = extract_clipboard_command(
        cleaned_command
    )

    if clipboard_command is not None:
        return clipboard_command


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


    # ================================
    #
    # ================================


    if intent is Intent.OPEN_FOUND_FILE:
        if not isinstance(extracted_value, int):
            return RouteResult(
                intent=intent,
                response="The file number was invalid.",
                success=False,
            )

        success, message = open_found_file(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.OPEN_FOUND_FILE_FOLDER:
        if not isinstance(extracted_value, int):
            return RouteResult(
                intent=intent,
                response="The file number was invalid.",
                success=False,
            )

        success, message = open_found_file_folder(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )




    if intent is Intent.OPEN_FOLDER:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The folder name was invalid.",
                success=False,
            )

        success, message = open_folder(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.LIST_FILES:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The folder name was invalid.",
                success=False,
            )

        success, message = list_files(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.CREATE_FOLDER:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response="The folder request was invalid.",
                success=False,
            )

        location, folder_name = extracted_value

        success, message = create_folder(
            location,
            folder_name,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.FIND_FILE:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The filename was invalid.",
                success=False,
            )

        success, message = find_file(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )
    


    if intent is Intent.GET_CLIPBOARD:
        success, message = get_clipboard()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.SET_CLIPBOARD:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="There was nothing to copy.",
                success=False,
            )

        success, message = set_clipboard(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.CLEAR_CLIPBOARD:
        success, message = clear_clipboard()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )
    


    if intent is Intent.SWITCH_WINDOW:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        success, message = focus_window(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.MINIMIZE_WINDOW:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        success, message = minimize_window(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.MAXIMIZE_WINDOW:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        success, message = maximize_window(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.CLOSE_WINDOW:
        if not isinstance(extracted_value, str):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        success, message = close_window(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.SHOW_DESKTOP:
        success, message = show_desktop()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )




    if intent is Intent.GET_VOLUME:
        success, message = get_volume_percent()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.SET_VOLUME:
        if not isinstance(
            extracted_value,
            int,
        ):
            return RouteResult(
                intent=intent,
                response="The volume level was invalid.",
                success=False,
            )

        success, message = set_volume_percent(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.ADJUST_VOLUME:
        if not isinstance(
            extracted_value,
            int,
        ):
            return RouteResult(
                intent=intent,
                response="The volume adjustment was invalid.",
                success=False,
            )

        success, message = adjust_volume_percent(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )




    if intent is Intent.VOLUME_UP:
        success, message = volume_up()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.VOLUME_DOWN:
        success, message = volume_down()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.MUTE_AUDIO:
        success, message = mute_audio()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.UNMUTE_AUDIO:
        success, message = unmute_audio()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.TAKE_SCREENSHOT:
        success, message = take_screenshot()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.LOCK_COMPUTER:
        success, message = lock_computer()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
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


    if intent is Intent.SET_SCHEDULED_REMINDER:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "that reminder time."
                ),
                success=False,
            )

        due_time, reminder_message = (
            extracted_value
        )

        if not isinstance(
            due_time,
            datetime,
        ):
            return RouteResult(
                intent=intent,
                response="The reminder time was invalid.",
                success=False,
            )

        if not isinstance(
            reminder_message,
            str,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "The reminder message was invalid."
                ),
                success=False,
            )

        success, message = (
            reminder_engine.create_reminder_at(
                due_time,
                reminder_message,
            )
        )

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
    
    if intent is Intent.LIST_RESEARCH_SOURCES:
        sources = get_research_sources()

        if not sources:
            return RouteResult(
                intent=intent,
                response=(
                    "I do not have any recent "
                    "research sources."
                ),
                success=False,
            )

        source_names = []

        for number, source in enumerate(
            sources,
            start=1,
        ):
            title, _ = source

            source_names.append(
                f"Source {number}: {title}"
            )

        return RouteResult(
            intent=intent,
            response=". ".join(source_names),
            success=True,
        )


    if intent is Intent.OPEN_RESEARCH_SOURCE:
        if not isinstance(
            extracted_value,
            int,
        ):
            return RouteResult(
                intent=intent,
                response="The source number was invalid.",
                success=False,
            )

        sources = get_research_sources()

        index = extracted_value - 1

        if (
            index < 0
            or index >= len(sources)
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I do not have that many "
                    "research sources."
                ),
                success=False,
            )

        title, url = sources[index]

        try:
            opened = webbrowser.open(
                url,
                new=2,
                autoraise=True,
            )

        except Exception as error:
            return RouteResult(
                intent=intent,
                response=(
                    f"I could not open that source: "
                    f"{error}"
                ),
                success=False,
            )

        if not opened:
            return RouteResult(
                intent=intent,
                response=(
                    "I could not open that source."
                ),
                success=False,
            )

        return RouteResult(
            intent=intent,
            response=(
                f"Opening source "
                f"{extracted_value}: {title}."
            ),
            success=True,
        )


    if intent is Intent.WEB_RESEARCH:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not understand "
                    "what you wanted me to research."
                ),
                success=False,
            )

        success, message = research_web(
            extracted_value
        )

        if success:
            remember_research(
                query=extracted_value,
                user_command=command,
                response=message,
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


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