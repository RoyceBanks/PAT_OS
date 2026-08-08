"""
PAT OS
brain/session_context.py

Temporary conversation context for the current PAT session.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionContext:
    last_file_results: list[str] | None = None
    last_research_query: str | None = None
    last_user_command: str | None = None
    last_response: str | None = None
    last_research_sources: list[
        tuple[str, str]
    ] | None = None


session_context = SessionContext()

def remember_research_sources(
    sources: list[tuple[str, str]],
) -> None:
    """Remember titles and URLs from the latest research."""

    session_context.last_research_sources = sources


def get_research_sources() -> list[tuple[str, str]]:
    """Return sources from the latest research."""

    return (
        session_context.last_research_sources
        or []
    )


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
    session_context.last_research_query = None
    session_context.last_user_command = None
    session_context.last_response = None
    session_context.last_research_sources = None