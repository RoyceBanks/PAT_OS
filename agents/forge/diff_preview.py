from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from .actions import FileChange
from .workspace import Workspace


@dataclass
class DiffPreview:
    path: str
    diff: str
    added_lines: int
    removed_lines: int
    truncated: bool = False


def _count_changed_lines(diff_lines: list[str]) -> tuple[int, int]:
    added = 0
    removed = 0

    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---"):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return added, removed


def build_diff_preview(
    workspace: str | Path,
    change: FileChange,
    max_chars: int = 20_000,
    context_lines: int = 3,
) -> DiffPreview:
    project = Workspace(
        workspace,
        create=False,
    )

    path = change.path

    try:
        old_text = project.read_text(
            path,
            max_chars=500_000,
        )
    except FileNotFoundError:
        old_text = ""

    old_lines = old_text.splitlines(
        keepends=True
    )
    new_lines = change.content.splitlines(
        keepends=True
    )

    raw_lines = list(
        unified_diff(
            old_lines,
            new_lines,
            fromfile=path,
            tofile=path,
            n=context_lines,
            lineterm="",
        )
    )

    normalized_lines = [
        line[:-1] if line.endswith("\n") else line
        for line in raw_lines
    ]

    added, removed = _count_changed_lines(
        normalized_lines
    )

    text = "\n".join(
        normalized_lines
    )

    truncated = False

    if len(text) > max_chars:
        truncated = True
        text = (
            text[:max_chars]
            + "\n\n[DIFF PREVIEW TRUNCATED]"
        )

    if not text:
        text = "[NO TEXTUAL CHANGES]"

    return DiffPreview(
        path=path,
        diff=text,
        added_lines=added,
        removed_lines=removed,
        truncated=truncated,
    )


def build_plan_diff_previews(
    workspace: str | Path,
    changes: list[FileChange],
    max_chars_per_file: int = 20_000,
) -> list[DiffPreview]:
    return [
        build_diff_preview(
            workspace=workspace,
            change=change,
            max_chars=max_chars_per_file,
        )
        for change in changes
    ]
