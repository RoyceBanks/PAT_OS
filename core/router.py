"""
PAT OS
core/router.py

Routes user commands to the correct PAT module.
"""

from __future__ import annotations

from engines.reminder_engine import reminder_engine
from datetime import datetime, timedelta
import re
import webbrowser
from pathlib import Path
from agents.manager import AgentManager
from config import WAKE_PHRASE
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

from internet.research import (
    research_web,
    summarize_research_source,
)
from brain.session_context import (
    get_process_results,
    get_process_target,
    get_window_target,
    remember_active_target,
    remember_window_target,
    get_active_website_target,
    remember_website_target,
    remember_process_results,
    get_active_process_target,
    remember_process_target,
    get_last_research_query,
    get_last_turn,
    get_research_sources,
    get_active_research_source_number,
    remember_research,
    get_file_selection,
    remember_file_selection,
    get_active_file_number,
    get_research_selection,
    get_active_target,
    get_active_application_target,
    remember_application_target,
    remember_research_selection,
    clear_pending_action,
    get_pending_action,
    remember_pending_action,
    pending_action_expired,
)
from automation.system_controls import (
    adjust_volume_percent,
    get_volume_percent,
    lock_computer,
    mute_audio,
    restart_computer,
    set_volume_percent,
    shutdown_computer,
    sign_out_computer,
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
from automation.browser import (
    close_website_tab,
    is_known_website,
    open_website,
    search_web,
    switch_to_website_tab,
)


from automation.file_manager import (
    create_folder,
    delete_file_path,
    find_file,
    list_files,
    move_found_file,
    open_folder,
    open_found_file,
    open_found_file_folder,
    prepare_found_file_delete,
    rename_found_file,
    copy_found_file,
)
from automation.process_monitor import (
    get_cpu_usage,
    get_top_memory_process_names,
    get_memory_usage,
    get_process_details,
    get_system_usage,
    get_top_cpu_processes,
    get_top_memory_processes,
    is_process_running,
)
from automation.process_controls import (
    force_close_application,
    offer_force_close_if_running,
    resolve_safe_process_application,
)

agent_manager = AgentManager()

PAT_WORKSPACE = str(    
    Path(__file__).resolve().parents[1]
)


class Intent(Enum):
    """Command types currently understood by PAT."""

    APPLICATION_PLAN = auto()
    OPEN_APPLICATION = auto()
    GET_PROCESS_DETAILS = auto()
    OPEN_WEBSITE = auto()
    CLOSE_WEBSITE_TAB = auto()
    SWITCH_WEBSITE_TAB = auto()
    WEB_SEARCH = auto()
    WEB_RESEARCH = auto()
    LIST_RESEARCH_SOURCES = auto()
    OPEN_RESEARCH_SOURCE = auto()
    SUMMARIZE_RESEARCH_SOURCE = auto()

    OPEN_FOLDER = auto()
    LIST_FILES = auto()
    CREATE_FOLDER = auto()
    FIND_FILE = auto()
    OPEN_FOUND_FILE = auto()
    OPEN_FOUND_FILE_FOLDER = auto()
    RENAME_FOUND_FILE = auto()
    MOVE_FOUND_FILE = auto()
    COPY_FOUND_FILE = auto()

    GET_CLIPBOARD = auto()
    SET_CLIPBOARD = auto()
    CLEAR_CLIPBOARD = auto()
    REQUEST_DELETE_FOUND_FILE = auto()
    CONFIRM_PENDING_ACTION = auto()
    CANCEL_PENDING_ACTION = auto()

    REQUEST_SHUTDOWN = auto()
    REQUEST_RESTART = auto()
    REQUEST_SIGN_OUT = auto()

    SWITCH_WINDOW = auto()
    MINIMIZE_WINDOW = auto()
    MAXIMIZE_WINDOW = auto()
    CLOSE_WINDOW = auto()
    SHOW_DESKTOP = auto()

    GET_CPU_USAGE = auto()
    GET_MEMORY_USAGE = auto()
    GET_SYSTEM_USAGE = auto()
    GET_TOP_CPU_PROCESSES = auto()
    GET_TOP_MEMORY_PROCESSES = auto()
    CHECK_PROCESS_RUNNING = auto()
    REQUEST_CLOSE_PROCESS = auto()

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

    LOCAL_TIME = auto()
    LOCAL_DATE = auto()
    WAKE_PHRASE_INFO = auto()
    SYSTEM_STATUS = auto()

    SAVE_MEMORY = auto()
    GET_MEMORY = auto()
    EXIT = auto()
    CODE_AGENT = auto()
    GENERAL_AI = auto()


@dataclass
# RouteResult class handles command routing outcomes
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

TIME_COMMANDS = {
    "what time is it",
    "what's the time",
    "what is the time",
    "tell me the time",
    "give me the time",
    "current time",
    "what time is it right now",
    "what's the current time",
}

DATE_COMMANDS = {
    "what day is it",
    "what day is today",
    "what is today's date",
    "what's today's date",
    "what is the date",
    "what's the date",
    "tell me the date",
    "today's date",
    "current date",
}

WAKE_PHRASE_COMMANDS = {
    "what is your wake phrase",
    "what's your wake phrase",
    "what is the wake phrase",
    "what's the wake phrase",
    "what is your wake word",
    "what's your wake word",
    "tell me your wake phrase",
    "tell me your wake word",
}

CODING_PHRASES = (
    "write code",
    "write me code",
    "create a program",    
    "build a program",    
    "build an app",    
    "make an app",    
    "debug code",    
    "debug this",    
    "fix my code",    
    "review this code",    
    "program this",    
    "code this",    
    "write a python",    
    "create a python",    
    "build a python",
)

FORGE_APPROVE_PHRASES = {
    "approve forge changes",
    "approve forge change",
    "approve changes",
    "forge approve",
}

FORGE_DENY_PHRASES = {
    "deny forge changes",
    "deny forge change",
    "cancel forge changes",
    "reject forge changes",
    "forge deny",
}

FORGE_HISTORY_PHRASES = {
    "show forge history",
    "forge history",
    "show forge changes",
    "show forge transaction history",
}

PAT_EDIT_PHRASES = (
    "fix pat",
    "edit pat",
    "modify pat",
    "update pat",
    "change pat",
    "fix pat_os",
    "edit pat_os",
    "modify pat_os",
    "update pat_os",
    "change pat_os",
    "fix core/",
    "edit core/",
    "modify core/",
    "update core/",
    "fix agents/",
    "edit agents/",
    "modify agents/",
    "update agents/",
)

OPEN_APP_PATTERNS = (
    r"^(?:please\s+)?open(?:\s+up)?\s+(.+)$",
    r"^(?:please\s+)?launch\s+(.+)$",
    r"^(?:please\s+)?start(?:\s+up)?\s+(.+)$",
    r"^(?:please\s+)?run\s+(.+)$",
)

FILE_CONTEXT_INTENTS = {
    "FIND_FILE",
    "OPEN_FOUND_FILE",
    "OPEN_FOUND_FILE_FOLDER",
    "RENAME_FOUND_FILE",
    "MOVE_FOUND_FILE",
    "COPY_FOUND_FILE",
    "REQUEST_DELETE_FOUND_FILE",
}

RESEARCH_CONTEXT_INTENTS = {
    "WEB_RESEARCH",
    "WEB_SEARCH",
    "LIST_RESEARCH_SOURCES",
    "OPEN_RESEARCH_SOURCE",
    "SUMMARIZE_RESEARCH_SOURCE",
}

PROCESS_CONTEXT_INTENTS = {
    "OPEN_APPLICATION",
    "GET_PROCESS_DETAILS",
    "CHECK_PROCESS_RUNNING",
    "GET_TOP_CPU_PROCESSES",
    "GET_TOP_MEMORY_PROCESSES",
    "REQUEST_CLOSE_PROCESS",
    "SWITCH_WINDOW",
    "MINIMIZE_WINDOW",
    "MAXIMIZE_WINDOW",
    "CLOSE_WINDOW",
}


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

def extract_website_tab_switch(
    command: str,
) -> str | None:
    """Extract a known website from a tab-switch command."""

    command = command.strip().lower()

    match = re.match(
        r"^(?:please\s+)?switch to\s+(.+)$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    website_name = (
        match.group(1)
        .strip()
    )

    website_name = re.sub(
        r"\s+(?:tab|website|site)$",
        "",
        website_name,
        flags=re.IGNORECASE,
    ).strip()

    if is_known_website(
        website_name
    ):
        return website_name

    return None

def extract_research_source_summary(
    command: str,
) -> int | None:
    """Resolve requests for details about a research result."""

    command = command.strip().lower()

    command = re.sub(
        r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
        "",
        command,
    )

    _, _, last_intent = get_last_turn()

    if last_intent not in RESEARCH_CONTEXT_INTENTS:
        return None

    sources = get_research_sources()

    if not sources:
        return None

    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }

    match = re.match(
        (
            r"^(?:tell me more about|"
            r"tell me about|"
            r"explain|"
            r"summarize) "
            r"(?:the )?"
            r"(first|second|third|fourth|fifth|\d+)"
            r"(?: one| result| source| article)?$"
        ),
        command,
        flags=re.IGNORECASE,
    )

    if match:
        value = match.group(1).lower()

        if value in words:
            return words[value]

        try:
            return int(value)
        except ValueError:
            return None

    active_number = (
        get_active_research_source_number()
    )

    if (
        active_number is not None
        and command in {
            "tell me more",
            "tell me more about it",
            "tell me about it",
            "what is it about",
            "what's it about",
            "summarize it",
            "explain it",
        }
    ):
        return active_number

    return None

def extract_source_number(
    command: str,
) -> int | None:
    """Resolve an explicit or contextual research-result reference."""

    command = command.strip().lower()

    command = re.sub(
        r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
        "",
        command,
    )

    words = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }

    number_pattern = (
        r"(first|second|third|fourth|fifth|\d+)"
    )

    # Explicit research-result commands.
    explicit_patterns = (
        (
            rf"^(?:please\s+)?open\s+"
            rf"(?:the\s+)?{number_pattern}\s+"
            rf"(?:source|article|result)$"
        ),
        (
            rf"^(?:please\s+)?open\s+"
            rf"(?:source|article|result)\s+"
            rf"{number_pattern}$"
        ),
    )

    for pattern in explicit_patterns:
        match = re.match(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        value = match.group(1).lower()

        if value in words:
            return words[value]

        try:
            return int(value)
        except ValueError:
            return None

    # Generic references such as "the second one" are
    # only research references when research is the
    # most recent conversational context.
    _, _, last_intent = get_last_turn()

    if last_intent not in RESEARCH_CONTEXT_INTENTS:
        return None

    if not get_research_sources():
        return None

    active_number = (
        get_active_research_source_number()
    )

    if (
        active_number is not None
        and command in {
            "open it again",
            "open that again",
            "open this again",
            "reopen it",
            "reopen that",
            "reopen this",
        }
    ):
        return active_number

    contextual_match = re.match(
        (
            rf"^(?:please\s+)?open\s+"
            rf"(?:the\s+)?{number_pattern}"
            rf"(?:\s+(?:one|result|source|article))?$"
        ),
        command,
        flags=re.IGNORECASE,
    )

    if not contextual_match:
        return None

    value = contextual_match.group(1).lower()

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

    _, _, last_intent = get_last_turn()

    if last_intent not in RESEARCH_CONTEXT_INTENTS:
        return None

    previous_query = get_last_research_query()

    if not previous_query:
        return None
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

def resolve_window_reference(
    target: str,
) -> str | None:
    """
    Resolve conversational window references and
    normalize natural window names.
    """

    cleaned = target.strip().lower()

    contextual_references = {
        "it",
        "that",
        "this",
        "screen",
        "the screen",
        "window",
        "the window",
        "this window",
        "that window",
        "current window",
        "the current window",
    }

    if cleaned in contextual_references:
        active_target = get_active_target()

        if active_target is not None:
            return (
                get_active_application_target()
                or get_active_website_target()
            )

        # Compatibility fallback for window/website
        # behavior not migrated yet.
        return get_window_target()

    # Remove conversational articles from real names.
    for prefix in (
        "the ",
        "my ",
    ):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    if not cleaned:
        return None

    return cleaned

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
                application = resolve_window_reference(
                    match.group(1)
                )

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

        # Natural local file-search phrases.
    natural_find_patterns = (
        r"^find (?:a )?file named (.+)$",
        r"^find my (.+)$",
        r"^find (.+)$",
        r"^look for my (.+)$",
        r"^look for (.+)$",
        r"^search my files for (.+)$",
        r"^search the computer for (.+)$",
        r"^search my computer for (.+)$",
    )

    for pattern in natural_find_patterns:
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

    # Explicit file references are always file commands.
    explicit_file_patterns = (
        (
            r"^open (?:the )?"
            r"(first|second|third|fourth|fifth|sixth|"
            r"seventh|eighth|ninth|tenth|\d+) file$"
        ),
        (
            r"^open file "
            r"(first|second|third|fourth|fifth|sixth|"
            r"seventh|eighth|ninth|tenth|\d+)$"
        ),
    )

    for pattern in explicit_file_patterns:
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


    # Ambiguous phrases like "second result" or
    # "second one" only belong to files when file
    # context is currently active.
    _, _, last_intent = get_last_turn()

    if last_intent in FILE_CONTEXT_INTENTS:
        contextual_file_patterns = (
            (
                r"^open (?:the )?"
                r"(first|second|third|fourth|fifth|sixth|"
                r"seventh|eighth|ninth|tenth|\d+) result$"
            ),
            (
                r"^open (?:the )?"
                r"(first|second|third|fourth|fifth|sixth|"
                r"seventh|eighth|ninth|tenth|\d+) one$"
            ),
        )

        for pattern in contextual_file_patterns:
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

def extract_file_modify_command(
    command: str,
) -> tuple[Intent, object] | None:
    """Detect safe rename and move commands."""

    command = command.strip().lower()

    command = re.sub(
        r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
        "",
        command,
    )

    _, _, last_intent = get_last_turn()

    selected_number = get_active_file_number()

    if (
        selected_number is not None
        and last_intent in FILE_CONTEXT_INTENTS
    ):
        copy_context = re.match(
            (
                r"^(?:copy|duplicate) "
                r"(?:it|that|this|the file) "
                r"to (?:my )?"
                r"(.+?)(?: folder)?$"
            ),
            command,
            flags=re.IGNORECASE,
        )

        if copy_context:
            destination = (
                copy_context.group(1).strip()
            )

            if destination:
                return (
                    Intent.COPY_FOUND_FILE,
                    (
                        selected_number,
                        destination,
                    ),
                )
        
        rename_context = re.match(
            (
                r"^rename "
                r"(?:it|that|this|the file) "
                r"to (.+)$"
            ),
            command,
            flags=re.IGNORECASE,
        )

        if rename_context:
            new_name = (
                rename_context.group(1).strip()
            )

            if new_name:
                return (
                    Intent.RENAME_FOUND_FILE,
                    (
                        selected_number,
                        new_name,
                    ),
                )

        move_context = re.match(
            (
                r"^move "
                r"(?:it|that|this|the file) "
                r"to (?:my )?"
                r"(.+?)(?: folder)?$"
            ),
            command,
            flags=re.IGNORECASE,
        )

        if move_context:
            destination = (
                move_context.group(1).strip()
            )

            if destination:
                return (
                    Intent.MOVE_FOUND_FILE,
                    (
                        selected_number,
                        destination,
                    ),
                )

 

    number_words = {
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

    number_pattern = (
        r"(first|second|third|fourth|fifth|sixth|"
        r"seventh|eighth|ninth|tenth|\d+)"
    )

    copy_match = re.match(
        (
            rf"^(?:copy|duplicate) "
            rf"(?:the )?{number_pattern} "
            rf"(?:file|result|one) "
            rf"to (?:my )?"
            rf"(.+?)(?: folder)?$"
        ),
        command,
        flags=re.IGNORECASE,
    )

    if copy_match:
        value = copy_match.group(1).lower()
        destination = copy_match.group(2).strip()

        number = (
            number_words[value]
            if value in number_words
            else int(value)
        )

        return (
            Intent.COPY_FOUND_FILE,
            (
                number,
                destination,
            ),
        )

    rename_match = re.match(
        rf"^rename (?:the )?{number_pattern} "
        rf"(?:file|result) to (.+)$",
        command,
        flags=re.IGNORECASE,
    )

    if rename_match:
        value = rename_match.group(1).lower()
        new_name = rename_match.group(2).strip()

        number = (
            number_words[value]
            if value in number_words
            else int(value)
        )

        return (
            Intent.RENAME_FOUND_FILE,
            (number, new_name),
        )

    move_match = re.match(
        rf"^move (?:the )?{number_pattern} "
        rf"(?:file|result) to (?:my )?(.+?)(?: folder)?$",
        command,
        flags=re.IGNORECASE,
    )

    if move_match:
        value = move_match.group(1).lower()
        destination = move_match.group(2).strip()

        number = (
            number_words[value]
            if value in number_words
            else int(value)
        )

        return (
            Intent.MOVE_FOUND_FILE,
            (number, destination),
        )

    return None

def extract_delete_file_command(
    command: str,
) -> tuple[Intent, int] | None:
    """Detect deletion of a previous file-search result."""

    command = command.strip().lower()
    command = re.sub(
        r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
        "",
        command,
    )

    _, _, last_intent = get_last_turn()

    selected_number = get_active_file_number()

    context_delete_commands = {
        "delete it",
        "delete that",
        "delete this",
        "get rid of it",
        "get rid of that",
        "delete the file",
        "remove it",
        "remove that",
        "remove this",
        "remove the file",
        "trash it",
        "trash that",
        "send it to the recycle bin",
        "send that to the recycle bin",
        "move it to the recycle bin",
        "move that to the recycle bin",
    }

    if (
        command in context_delete_commands
        and selected_number is not None
        and last_intent in FILE_CONTEXT_INTENTS
    ):
        return (
            Intent.REQUEST_DELETE_FOUND_FILE,
            selected_number,
        )

    number_words = {
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

    number_pattern = (
        r"(first|second|third|fourth|fifth|sixth|"
        r"seventh|eighth|ninth|tenth|\d+)"
    )

    match = re.match(
        rf"^(?:delete|remove) (?:the )?"
        rf"{number_pattern} "
        rf"(?:file|result)$",
        command,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    value = match.group(1).lower()

    number = (
        number_words[value]
        if value in number_words
        else int(value)
    )

    return (
        Intent.REQUEST_DELETE_FOUND_FILE,
        number,
    )

def extract_power_command(
    command: str,
) -> tuple[Intent, None] | None:
    """Detect Windows power commands that require confirmation."""

    command = command.strip().lower()

    shutdown_commands = {
        "shutdown",
        "shut down",
        "shutdown computer",
        "shutdown the computer",
        "shut down computer",
        "shut down the computer",
        "turn off computer",
        "turn off the computer",
        "turn the computer off",
    }

    restart_commands = {
        "restart",
        "restart computer",
        "restart the computer",
        "reboot",
        "reboot computer",
        "reboot the computer",
    }

    sign_out_commands = {
        "sign out",
        "sign me out",
        "sign out of windows",
        "log out",
        "log me out",
        "logout",
    }

    if command in shutdown_commands:
        return (
            Intent.REQUEST_SHUTDOWN,
            None,
        )

    if command in restart_commands:
        return (
            Intent.REQUEST_RESTART,
            None,
        )

    if command in sign_out_commands:
        return (
            Intent.REQUEST_SIGN_OUT,
            None,
        )

    return None

def extract_process_monitor_command(
    command: str,
) -> tuple[Intent, object] | None:
    """Detect read-only system and process monitoring commands."""

    command = command.strip().lower()

    system_commands = {
        "system usage",
        "system status",
        "how is the computer doing",
        "how is my computer doing",
        "check system usage",
        "check system status",
    }

    cpu_commands = {
        "cpu usage",
        "what is my cpu usage",
        "what's my cpu usage",
        "how much cpu am i using",
        "how much cpu is being used",
        "check cpu usage",
    }

    memory_commands = {
        "memory usage",
        "ram usage",
        "what is my memory usage",
        "what's my memory usage",
        "what is my ram usage",
        "what's my ram usage",
        "how much memory is free",
        "how much ram is free",
        "how much memory is available",
        "how much ram is available",
        "check memory usage",
        "check ram usage",
    }

    top_memory_commands = {
        "what is using the most ram",
        "what's using the most ram",
        "what is using the most memory",
        "what's using the most memory",
        "top memory processes",
        "show me the top memory processes",
        "show the top memory processes",
    }

    top_cpu_commands = {
        "what is using the most cpu",
        "what's using the most cpu",
        "top cpu processes",
        "show me the top cpu processes",
        "show the top cpu processes",
    }

    if command in system_commands:
        return (
            Intent.GET_SYSTEM_USAGE,
            None,
        )

    if command in cpu_commands:
        return (
            Intent.GET_CPU_USAGE,
            None,
        )

    if command in memory_commands:
        return (
            Intent.GET_MEMORY_USAGE,
            None,
        )

    if command in top_memory_commands:
        return (
            Intent.GET_TOP_MEMORY_PROCESSES,
            None,
        )

    if command in top_cpu_commands:
        return (
            Intent.GET_TOP_CPU_PROCESSES,
            None,
        )

    process_match = re.match(
        r"^(?:is|check if|check whether) "
        r"(.+?) "
        r"(?:running|open)$",
        command,
        flags=re.IGNORECASE,
    )

    if process_match:
        application = (
            process_match
            .group(1)
            .strip()
        )

        if application:
            return (
                Intent.CHECK_PROCESS_RUNNING,
                application,
            )

    return None

def extract_process_followup_command(
    command: str,
) -> tuple[Intent, object] | None:
    """Resolve conversational follow-ups about processes."""

    command = command.strip().lower()

    command = re.sub(
            r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
            "",
            command,
        )

    _, _, last_intent = get_last_turn()

    if last_intent not in PROCESS_CONTEXT_INTENTS:
        return None

    process_target = (
        get_active_process_target()
    )

    application_target = (
        get_active_application_target()
    )

    detail_target = (
        process_target
        or application_target
    )

    if detail_target is not None:
        detail_commands = {
            "tell me more about it",
            "tell me more",
            "how much ram is it using",
            "how much memory is it using",
            "what is its pid",
            "what's its pid",
            "give me its details",
            "show me its details",
        }

        if command in detail_commands:
            return (
                Intent.GET_PROCESS_DETAILS,
                detail_target,
            )


    if process_target is not None:
        if command in {
            "close it",
            "close that",
            "close the app",
            "close the application",
        }:
            return (
                Intent.REQUEST_CLOSE_PROCESS,
                process_target,
            )

        if command in {
            "open it again",
            "open that again",
            "reopen it",
            "reopen that",
            "start it again",
        }:
            return (
                Intent.OPEN_APPLICATION,
                process_target,
            )


    if application_target is not None:
        if command in {
            "close it",
            "close that",
            "close the app",
            "close the application",
        }:
            return (
                Intent.CLOSE_WINDOW,
                application_target,
            )

        if command in {
            "open it again",
            "open that again",
            "reopen it",
            "reopen that",
            "start it again",
        }:
            return (
                Intent.OPEN_APPLICATION,
                application_target,
            )

    result_match = re.match(
        (
            r"^(?:"
            r"tell me more about|"
            r"tell me about|"
            r"show me details for|"
            r"what about"
            r") "
            r"(?:the )?"
            r"(first|second|third|fourth|fifth|\d+)"
            r"(?: one| process| result)?$"
        ),
        command,
        flags=re.IGNORECASE,
    )

    if result_match:
        number_words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
        }

        value = result_match.group(1)

        number = (
            number_words[value]
            if value in number_words
            else int(value)
        )

        results = get_process_results()

        index = number - 1

        if (
            index >= 0
            and index < len(results)
        ):
            application = results[index]

            remember_process_target(
                application
            )

            return (
                Intent.GET_PROCESS_DETAILS,
                application,
            )
    close_result_match = re.match(
        (
            r"^close (?:the )?"
            r"(first|second|third|fourth|fifth|\d+)"
            r"(?: one| process| result)?$"
        ),
        command,
        flags=re.IGNORECASE,
    )

    if close_result_match:
        number_words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
        }

        value = (
            close_result_match
            .group(1)
            .lower()
        )

        number = (
            number_words[value]
            if value in number_words
            else int(value)
        )

        results = get_process_results()

        index = number - 1

        if (
            index >= 0
            and index < len(results)
        ):
            application = (
                resolve_safe_process_application(
                    results[index]
                )
            )

            if application is not None:
                remember_process_target(
                    application
                )

                return (
                    Intent.CLOSE_WINDOW,
                    application,
                )


    return None

def extract_website_followup_command(
    command: str,
) -> tuple[Intent, object] | None:
    """Resolve conversational follow-ups about websites."""

    command = command.strip().lower()

    command = re.sub(
        r"^(?:okay|ok|alright|all right|sure)\s*[,.-]?\s+",
        "",
        command,
    )

    website_target = (
        get_active_website_target()
    )

    if website_target is None:
        return None

    _, _, last_intent = get_last_turn()

    website_context_intents = {
        "OPEN_WEBSITE",
        "CLOSE_WEBSITE_TAB",
        "SWITCH_WEBSITE_TAB",
        "CLOSE_WINDOW",
        "SWITCH_WINDOW",
        "MINIMIZE_WINDOW",
        "MAXIMIZE_WINDOW",
    }

    if last_intent not in website_context_intents:
        return None

    if command in {
        "close it",
        "close that",
        "close the site",
        "close the website",
        "close the tab",
    }:
        return (
            Intent.CLOSE_WEBSITE_TAB,
            website_target,
        )

    if command in {
        "open it again",
        "open that again",
        "reopen it",
        "reopen that",
    }:
        return (
            Intent.OPEN_WEBSITE,
            website_target,
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
    pending_action = get_pending_action()
    raw_command = command.strip().lower()

    # ======================================================
    # FORGE COMMANDS - CHECK BEFORE OTHER INTENTS
    # ======================================================

    if raw_command in FORGE_HISTORY_PHRASES:
        return Intent.CODE_AGENT, command

    if re.fullmatch(
        r"undo\s+forge\s+TASK-[A-Za-z0-9]+",
        raw_command,
        flags=re.IGNORECASE,
    ):
        return Intent.CODE_AGENT, command


    if raw_command in FORGE_APPROVE_PHRASES:
        return Intent.CODE_AGENT, command

    if raw_command in FORGE_DENY_PHRASES:
        return Intent.CODE_AGENT, command

    forge_prefixes = (
        "forge ",
        "have forge ",
        "ask forge ",
        "tell forge ",
        "get forge ",
    )

    if raw_command.startswith(forge_prefixes):
        return Intent.CODE_AGENT, command


    if (
        pending_action is not None
        and pending_action_expired()
    ):
        clear_pending_action()
        pending_action = None

    if pending_action is not None:
        confirmation_commands = {
            "yes",
            "yes please",
            "confirm",
            "confirm it",
            "do it",
            "go ahead",
            "proceed",
        }

        cancellation_commands = {
            "no",
            "no thanks",
            "cancel",
            "cancel it",
            "never mind",
            "nevermind",
            "stop",
        }

        if cleaned_command in confirmation_commands:
            return (
                Intent.CONFIRM_PENDING_ACTION,
                None,
            )

        if cleaned_command in cancellation_commands:
            return (
                Intent.CANCEL_PENDING_ACTION,
                None,
            )

        # Any unrelated command cancels the old request so a
        # future accidental "yes" cannot trigger it.
        clear_pending_action()


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

    power_command = extract_power_command(
        cleaned_command
    )

    if power_command is not None:
        return power_command



    # Local time and date
    if cleaned_command in TIME_COMMANDS:
        return Intent.LOCAL_TIME, None

    if cleaned_command in DATE_COMMANDS:
        return Intent.LOCAL_DATE, None

    # PAT wake phrase
    if cleaned_command in WAKE_PHRASE_COMMANDS:
        return Intent.WAKE_PHRASE_INFO, None

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

    # Conversational website follow-up
    website_followup = extract_website_followup_command(
        cleaned_command
    )
        
    if website_followup is not None:
        return website_followup

    # Explicit website-tab switch
    website_tab = extract_website_tab_switch(
        cleaned_command
    )

    if website_tab is not None:
        return (
            Intent.SWITCH_WEBSITE_TAB,
            website_tab,
        )

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

    file_modify_command = extract_file_modify_command(
        cleaned_command
    )

    if file_modify_command is not None:
        return file_modify_command

    delete_file_command = extract_delete_file_command(
        cleaned_command
    )

    if delete_file_command is not None:
        return delete_file_command





    
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


    source_summary_number = (
        extract_research_source_summary(
            cleaned_command
        )
    )

    if source_summary_number is not None:
        return (
            Intent.SUMMARIZE_RESEARCH_SOURCE,
            source_summary_number,
        )

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


    # Conversational process/application follow-up
    process_followup = extract_process_followup_command(
        cleaned_command
    )

    if process_followup is not None:
        return process_followup

    
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


    process_monitor_command = (    
        extract_process_monitor_command(        
            cleaned_command    
        )
    )

    if process_monitor_command is not None:    
        return process_monitor_command
    # ======================================================# 
    # FORGE CODING AGENT
    # ======================================================
    if cleaned_command in FORGE_APPROVE_PHRASES:
        return Intent.CODE_AGENT, command

    if cleaned_command in FORGE_DENY_PHRASES:
        return Intent.CODE_AGENT, command




    if any(    
        phrase in cleaned_command    
        for phrase in CODING_PHRASES
    ):    
        return (        
            Intent.CODE_AGENT,        
            command,    
        )


    # Anything else goes to PAT's AI.
    return Intent.GENERAL_AI, None


# Handle main command routing logic
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

    if intent is Intent.WAKE_PHRASE_INFO:
        return RouteResult(
            intent=intent,
            response=(
                f'My wake phrase is "{WAKE_PHRASE.title()}".'
            ),
            success=True,
        )

    if intent is Intent.GET_SYSTEM_USAGE:
        success, message = get_system_usage()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.GET_CPU_USAGE:
        success, message = get_cpu_usage()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.GET_MEMORY_USAGE:
        success, message = get_memory_usage()

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.GET_TOP_MEMORY_PROCESSES:
        success, message = (
            get_top_memory_processes()
        )

        if success:
            process_names = (
                get_top_memory_process_names()
            )

            remember_process_results(
                process_names
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.GET_TOP_CPU_PROCESSES:
        success, message, process_names = (
            get_top_cpu_processes()
        )

        if success:
            remember_process_results(
                process_names
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.CHECK_PROCESS_RUNNING:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        remember_process_target(
            extracted_value
        )

        success, message = is_process_running(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    if intent is Intent.GET_PROCESS_DETAILS:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response="The process name was invalid.",
                success=False,
            )

        remember_process_target(
            extracted_value
        )

        success, message = get_process_details(
            extracted_value
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.REQUEST_SHUTDOWN:
        message = (
            "Are you sure you want me to shut down "
            "the computer?"
        )

        remember_pending_action(
            action_type="shutdown_computer",
            payload=None,
            description=message,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=True,
        )


    if intent is Intent.REQUEST_RESTART:
        message = (
            "Are you sure you want me to restart "
            "the computer?"
        )

        remember_pending_action(
            action_type="restart_computer",
            payload=None,
            description=message,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=True,
        )


    if intent is Intent.REQUEST_SIGN_OUT:
        message = (
            "Are you sure you want me to sign you "
            "out of Windows?"
        )

        remember_pending_action(
            action_type="sign_out_computer",
            payload=None,
            description=message,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=True,
        )



    if intent is Intent.REQUEST_DELETE_FOUND_FILE:
        if not isinstance(extracted_value, int):
            return RouteResult(
                intent=intent,
                response="The file number was invalid.",
                success=False,
            )

        success, message, path = prepare_found_file_delete(
            extracted_value
        )

        if not success or path is None:
            return RouteResult(
                intent=intent,
                response=message,
                success=False,
            )

        remember_pending_action(
            action_type="delete_file",
            payload=path,
            description=message,
        )

        return RouteResult(
            intent=intent,
            response=message,
            success=True,
        )


    if intent is Intent.CANCEL_PENDING_ACTION:
        clear_pending_action()

        return RouteResult(
            intent=intent,
            response="Canceled.",
            success=True,
        )


    if intent is Intent.CONFIRM_PENDING_ACTION:
        pending = get_pending_action()

        if pending is None:
            return RouteResult(
                intent=intent,
                response="There is nothing waiting for confirmation.",
                success=False,
            )

        # Clear before execution so "yes" cannot accidentally
        # run the same destructive action twice.
        clear_pending_action()


        if pending.action_type == "force_close_application":
            success, message = force_close_application(
                str(pending.payload)
            )

            return RouteResult(
                intent=intent,
                response=message,
                success=success,
            )

        if pending.action_type == "delete_file":
            success, message = delete_file_path(
                str(pending.payload)
            )

            return RouteResult(
                intent=intent,
                response=message,
                success=success,
            )

            

        return RouteResult(
            intent=intent,
            response="I do not recognize that pending action.",
            success=False,
        )


        if pending.action_type == "shutdown_computer":
            success, message = shutdown_computer()

            return RouteResult(
                intent=intent,
                response=message,
                success=success,
            )


        if pending.action_type == "restart_computer":
            success, message = restart_computer()

            return RouteResult(
                intent=intent,
                response=message,
                success=success,
            )


        if pending.action_type == "sign_out_computer":
            success, message = sign_out_computer()

            return RouteResult(
                intent=intent,
                response=message,
                success=success,
            )


    if intent is Intent.COPY_FOUND_FILE:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response="The copy request was invalid.",
                success=False,
            )

        number, destination = extracted_value

        success, message = copy_found_file(
            number,
            destination,
        )

        if success:
            remember_file_selection(
                number
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.RENAME_FOUND_FILE:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response="The rename request was invalid.",
                success=False,
            )

        number, new_name = extracted_value

        success, message = rename_found_file(
            number,
            new_name,
        )
        if success:
            remember_file_selection(
                number
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


    if intent is Intent.MOVE_FOUND_FILE:
        if (
            not isinstance(extracted_value, tuple)
            or len(extracted_value) != 2
        ):
            return RouteResult(
                intent=intent,
                response="The move request was invalid.",
                success=False,
            )

        number, destination = extracted_value

        success, message = move_found_file(
            number,
            destination,
        )
        if success:
            remember_file_selection(
                number
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )


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

        if success:
            remember_file_selection(
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

        if success:
            remember_file_selection(
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
        if success:
            remember_application_target(
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
        if success:
            remember_application_target(
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

    close_requested_from_process = False

    if intent is Intent.REQUEST_CLOSE_PROCESS:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "The process name was invalid."
                ),
                success=False,
            )

        process_target = extracted_value

        application = (
            resolve_safe_process_application(
                process_target
            )
        )

        if application is None:
            return RouteResult(
                intent=intent,
                response=(
                    f"I can inspect {process_target}, "
                    "but I won't terminate it because "
                    "it is not on my approved "
                    "application close list."
                ),
                success=False,
            )

        remember_process_target(
            application
        )

        close_requested_from_process = True

        extracted_value = application
        intent = Intent.CLOSE_WINDOW



    if intent is Intent.CLOSE_WINDOW:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response="The application name was invalid.",
                success=False,
            )

        application = extracted_value

        success, message = close_window(
            application
        )

        should_offer, force_message = (
            offer_force_close_if_running(
                application,
                wait_seconds=(
                    1.5
                    if success
                    else 0.0
                ),
            )
        )

        if (
            should_offer
            and not close_requested_from_process
        ):
            remember_application_target(
                application
            )

        if should_offer:
            remember_pending_action(
                action_type="force_close_application",
                payload=application,
                description=force_message,
            )

            if (
                success
                and not close_requested_from_process
            ):
                remember_application_target(
                    application
                )

            return RouteResult(
                intent=intent,
                response=force_message,
                success=True,
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
    # LOCAL TIME
    # ======================================================

    if intent is Intent.LOCAL_TIME:
        now = datetime.now()

        time_text = now.strftime(
            "%I:%M %p"
        ).lstrip("0")

        return RouteResult(
            intent=intent,
            response=f"It is {time_text}.",
            success=True,
        )


    # ======================================================
    # LOCAL DATE
    # ======================================================

    if intent is Intent.LOCAL_DATE:
        now = datetime.now()

        date_text = (
            f"{now.strftime('%A, %B')} "
            f"{now.day}, "
            f"{now.year}"
        )

        return RouteResult(
            intent=intent,
            response=f"Today is {date_text}.",
            success=True,
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

        remember_research_selection(
            extracted_value
        )

        remember_active_target(
            kind="research_source",
            value=url,
            label=title,
        )

        return RouteResult(
            intent=intent,
            response=(
                f"Opening source "
                f"{extracted_value}: {title}."
            ),
            success=True,
        )
    if intent is Intent.SUMMARIZE_RESEARCH_SOURCE:
        if not isinstance(
            extracted_value,
            int,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "The research source number was invalid."
                ),
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

        success, message = (
            summarize_research_source(
                title,
                url,
            )
        )

        if success:
            remember_research_selection(
                extracted_value
            )

            remember_active_target(
                kind="research_source",
                value=url,
                label=title,
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
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

        if success:
            remember_website_target(
                extracted_value
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )

    # ======================================================
    # SWITCH WEBSITE TAB
    # ======================================================

    if intent is Intent.SWITCH_WEBSITE_TAB:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not determine "
                    "which website tab to switch to."
                ),
                success=False,
            )

        success, message = switch_to_website_tab(
            extracted_value
        )

        if success:
            remember_website_target(
                extracted_value
            )

        return RouteResult(
            intent=intent,
            response=message,
            success=success,
        )



    # ======================================================
    # CLOSE WEBSITE TAB
    # ======================================================

    if intent is Intent.CLOSE_WEBSITE_TAB:
        if not isinstance(
            extracted_value,
            str,
        ):
            return RouteResult(
                intent=intent,
                response=(
                    "I could not determine "
                    "which website tab to close."
                ),
                success=False,
            )

        success, message = close_website_tab(
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

        if success:
            remember_application_target(
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
    # FORGE CODING AGENT
    # ======================================================

    if intent is Intent.CODE_AGENT:
        try:
            cleaned = command.strip().lower()

            # ==========================================
            # FORGE HISTORY
            # ==========================================

            if cleaned in FORGE_HISTORY_PHRASES:
                result = (
                    agent_manager
                    .show_forge_history()
                )

            # ==========================================
            # FORGE UNDO
            # ==========================================

            elif re.fullmatch(
                r"undo\s+forge\s+TASK-[A-Za-z0-9]+",
                command.strip(),
                flags=re.IGNORECASE,
            ):
                task_id = (
                    command
                    .strip()
                    .split()[-1]
                    .upper()
                )

                result = (
                    agent_manager
                    .undo_forge_change(
                        task_id
                    )
                )

            # ==========================================
            # APPROVE
            # ==========================================

            elif cleaned in FORGE_APPROVE_PHRASES:
                result = (
                    agent_manager
                    .approve_pending()
                )

            # ==========================================
            # DENY
            # ==========================================

            elif cleaned in FORGE_DENY_PHRASES:
                result = (
                    agent_manager
                    .deny_pending()
                )

            # ==========================================
            # PAT SELF-EDIT
            # ==========================================

            elif (
                any(
                    phrase in cleaned
                    for phrase in PAT_EDIT_PHRASES
                )
                or (
                    "forge" in cleaned
                    and (
                        " pat " in f" {cleaned} "
                        or "pat_os" in cleaned
                        or "core/" in cleaned
                        or "core\\" in cleaned
                        or "agents/" in cleaned
                        or "agents\\" in cleaned
                    )
                )
            ):
                result = agent_manager.coding_task(
                    task=command,
                    workspace=PAT_WORKSPACE,
                    require_approval=True,
                )

            # ==========================================
            # NORMAL ISOLATED FORGE TASK
            # ==========================================

            else:
                result = agent_manager.coding_task(
                    task=command,
                )

            forge_result = result["forge"]

            return RouteResult(
                intent=Intent.CODE_AGENT,
                response=forge_result.content,
                success=result.get(
                    "success",
                    True,
                ),
            )

        except Exception as error:
            return RouteResult(
                intent=Intent.CODE_AGENT,
                response=(
                    "FORGE encountered an error: "
                    f"{error}"
                ),
                success=False,
            )
            # ------------------------------------------
            # EXPLICIT FORGE COMMAND
            # ------------------------------------------
            FORGE_COMMAND_PREFIXES = (
                "forge ",
                "have forge ",
                "ask forge ",
                "tell forge ",
                "get forge ",
            )

            if cleaned_command.startswith(
                FORGE_COMMAND_PREFIXES
            ):
                return (
                    Intent.CODE_AGENT,
                    command,
                )

            # ------------------------------------------
            # NORMAL ISOLATED FORGE PROJECT
            # ------------------------------------------
            else:
                result = agent_manager.coding_task(
                    task=command,
                )

            forge_result = result["forge"]

            return RouteResult(
                intent=Intent.CODE_AGENT,
                response=forge_result.content,
                success=result.get("success", True),
            )

        except Exception as error:
            return RouteResult(
                intent=Intent.CODE_AGENT,
                response=(
                    "FORGE encountered an error: "
                    f"{error}"
                ),
                success=False,
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