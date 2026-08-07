"""
PAT OS
brain/session_context.py

Temporary conversation context for the current PAT session.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionContext:
    last_research_query: str | None = None
    last_user_command: str | None = None
    last_response: str | None = None


session_context = SessionContext()


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


def clear_session_context() -> None:
    """Forget temporary conversation context."""

    session_context.last_research_query = None
    session_context.last_user_command = None
    session_context.last_response = None