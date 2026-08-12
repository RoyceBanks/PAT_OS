"""
PAT OS
brain/session_context.py

Temporary conversation context for the current PAT session.
"""

from __future__ import annotations
import time
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ActiveTarget:
    """The object PAT is currently discussing."""

    kind: str
    value: object
    label: str | None = None

@dataclass
class SessionContext:
    pending_action: PendingAction | None = None
    active_target: ActiveTarget | None = None
    
    last_process_results: list[str] | None = None
    last_file_results: list[str] | None = None
    last_file_selection: int | None = None
    last_research_query: str | None = None
    last_research_selection: int | None = None
    last_user_command: str | None = None
    last_response: str | None = None
    last_intent: str | None = None

    last_research_sources: list[
        tuple[str, str]
    ] | None = None

@dataclass
class PendingAction:
    """An action waiting for user confirmation."""

    action_type: str
    payload: object
    description: str
    expires_at: float


session_context = SessionContext()

def remember_active_target(
    kind: str,
    value: object,
    label: str | None = None,
) -> None:
    """Remember the object PAT is currently discussing."""

    cleaned_kind = kind.strip().lower()

    if not cleaned_kind:
        return

    cleaned_label = None

    if label is not None:
        cleaned = label.strip()

        if cleaned:
            cleaned_label = cleaned

    session_context.active_target = ActiveTarget(
        kind=cleaned_kind,
        value=value,
        label=cleaned_label,
    )

def get_active_target() -> ActiveTarget | None:
    """Return PAT's current conversational target."""

    return session_context.active_target

def get_active_research_source_number() -> int | None:
    """Return the numbered source matching the active research target."""

    target = get_active_target()

    if (
        target is None
        or target.kind != "research_source"
    ):
        return None

    sources = (
        session_context.last_research_sources
        or []
    )

    for number, (
        _title,
        url,
    ) in enumerate(
        sources,
        start=1,
    ):
        if url == target.value:
            return number

    return None

def clear_active_target() -> None:
    """Forget PAT's current conversational target."""

    session_context.active_target = None

def remember_turn(
    user_command: str,
    response: str,
    intent: str,
) -> None:
    """Remember the latest PAT conversation turn."""

    session_context.last_user_command = (
        user_command.strip()
    )

    session_context.last_response = (
        response.strip()
    )

    session_context.last_intent = (
        intent.strip()
    )

def get_last_turn(
) -> tuple[str | None, str | None, str | None]:
    """Return PAT's latest conversation turn."""

    return (
        session_context.last_user_command,
        session_context.last_response,
        session_context.last_intent,
    )

def remember_process_target(
    application: str,
) -> None:
    """Remember the process PAT is currently discussing."""

    cleaned = application.strip().lower()

    if not cleaned:
        return

    remember_active_target(
        kind="process",
        value=cleaned,
        label=cleaned,
    )


def get_active_process_target() -> str | None:
    """Return PAT's active process target."""

    target = get_active_target()

    if (
        target is None
        or target.kind != "process"
        or not isinstance(target.value, str)
    ):
        return None

    return target.value

def remember_process_results(
    applications: list[str],
) -> None:
    """Remember ordered results from a process query."""

    cleaned = []

    for application in applications:
        name = application.strip().lower()

        if name.endswith(".exe"):
            name = name[:-4]

        if name:
            cleaned.append(
                name
            )

    session_context.last_process_results = (
        cleaned
    )
    target = get_active_target()

    if (
        target is not None
        and target.kind == "process"
    ):
        clear_active_target()

    

def remember_website_target(
    website: str,
) -> None:
    """Remember the website PAT is currently discussing."""

    cleaned = website.strip().lower()

    if not cleaned:
        return


    remember_active_target(
        kind="website",
        value=cleaned,
        label=cleaned,
    )

def get_active_website_target() -> str | None:
    """Return PAT's active website."""

    target = get_active_target()

    if (
        target is None
        or target.kind != "website"
        or not isinstance(target.value, str)
    ):
        return None

    return target.value
    
def remember_application_target(
    application: str,
) -> None:
    """Remember the desktop application PAT is discussing."""

    cleaned = application.strip().lower()

    if not cleaned:
        return


    remember_active_target(
        kind="application",
        value=cleaned,
        label=cleaned,
    )

def get_active_application_target() -> str | None:
    """Return PAT's active desktop application."""

    target = get_active_target()

    if (
        target is None
        or target.kind != "application"
        or not isinstance(target.value, str)
    ):
        return None

    return target.value

def get_process_results() -> list[str]:
    """Return the most recent ordered process results."""

    return (
        session_context.last_process_results
        or []
    )

def remember_pending_action(
    action_type: str,
    payload: object,
    description: str,
    timeout_seconds: float = 30.0,
) -> None:
    """Store an action temporarily while waiting for confirmation."""

    session_context.pending_action = PendingAction(
        action_type=action_type,
        payload=payload,
        description=description,
        expires_at=time.monotonic() + timeout_seconds,
    )

def pending_action_expired() -> bool:
    """Return True if the current confirmation request expired."""

    pending = session_context.pending_action

    if pending is None:
        return False

    return time.monotonic() >= pending.expires_at

def get_pending_action() -> PendingAction | None:
    """Return the action currently waiting for confirmation."""

    return session_context.pending_action

def clear_pending_action() -> None:
    """Forget the current pending action."""

    session_context.pending_action = None

def remember_research_sources(
    sources: list[tuple[str, str]],
) -> None:
    """Remember titles and URLs from the latest research."""

    session_context.last_research_sources = sources
    session_context.last_research_selection = None

    target = session_context.active_target

    if (
        target is not None
        and target.kind == "research_source"
    ):
        session_context.active_target = None

def get_research_sources() -> list[tuple[str, str]]:
    """Return sources from the latest research."""

    return (
        session_context.last_research_sources
        or []
    )

def remember_research_selection(
    number: int,
) -> None:
    """Remember the research result PAT is discussing."""

    if number > 0:
        session_context.last_research_selection = number

def get_research_selection() -> int | None:
    """Return the currently selected research result."""

    if session_context.last_research_selection is not None:
        return session_context.last_research_selection

    sources = (
        session_context.last_research_sources
        or []
    )

    if len(sources) == 1:
        return 1

    return None

def clear_research_selection() -> None:
    """Forget the selected research result."""

    session_context.last_research_selection = None

def remember_research(
    query: str,
    user_command: str,
    response: str,
) -> None:
    """Remember the latest web research conversation."""

    session_context.last_research_query = query
    session_context.last_user_command = user_command
    session_context.last_response = response

def get_last_research_query() -> str | None:
    """Return the previous research topic."""

    return session_context.last_research_query

def remember_file_results(
    paths: list[str],
) -> None:
    """Remember files returned by the latest file search."""

    session_context.last_file_results = paths
    session_context.last_file_selection = None

    target = get_active_target()

    if (
        target is not None
        and target.kind == "file"
    ):
        clear_active_target()

    # Preserve PAT's existing behavior:
    # one result is automatically the active file.
    if len(paths) == 1:
        path = paths[0]

        session_context.last_file_selection = 1

        remember_active_target(
            kind="file",
            value=path,
            label=Path(path).name,
        )

def remember_file_selection(
    number: int,
) -> None:
    """Remember the file result PAT is currently discussing."""

    results = (
        session_context.last_file_results
        or []
    )

    index = number - 1

    if (
        index < 0
        or index >= len(results)
    ):
        return

    path = results[index]

    session_context.last_file_selection = number

    remember_active_target(
        kind="file",
        value=path,
        label=Path(path).name,
    )

def get_file_selection() -> int | None:
    """Return the currently selected file-result number."""

    if session_context.last_file_selection is not None:
        return session_context.last_file_selection

    results = (
        session_context.last_file_results
        or []
    )

    if len(results) == 1:
        return 1

    return None

def get_active_file_number() -> int | None:
    """Return the result number matching PAT's active file."""

    target = get_active_target()

    if (
        target is None
        or target.kind != "file"
        or not isinstance(target.value, str)
    ):
        return None

    results = (
        session_context.last_file_results
        or []
    )

    for number, path in enumerate(
        results,
        start=1,
    ):
        if Path(path) == Path(target.value):
            return number

    return None

def clear_file_selection() -> None:
    """Forget the selected file result."""

    session_context.last_file_selection = None

def get_file_results() -> list[str]:
    """Return files from the latest file search."""

    return (
        session_context.last_file_results
        or []
    )

def clear_file_results() -> None:
    """Forget previous file-search results."""

    session_context.last_file_results = None

def clear_session_context() -> None:
    """Forget temporary conversation context."""

    session_context.last_file_results = None
    
    session_context.last_process_results = None
    session_context.pending_action = None
    session_context.last_research_query = None
    session_context.last_user_command = None
    session_context.last_research_selection = None
    session_context.last_response = None
    session_context.last_research_sources = None
    session_context.last_intent = None
    session_context.active_target = None
    session_context.last_file_selection = None