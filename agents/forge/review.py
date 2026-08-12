from __future__ import annotations

from dataclasses import dataclass, field
from .messages import AgentMessage


@dataclass
class ChangeSet:
    task_id: str
    files_changed: list[str] = field(default_factory=list)
    summary: str = ""
    tests_run: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


def build_sentinel_review_request(change_set: ChangeSet) -> AgentMessage:
    content = (
        "Review FORGE's implementation.\n\n"
        f"Summary:\n{change_set.summary}\n\n"
        "Files changed:\n"
        + "\n".join(f"- {p}" for p in change_set.files_changed)
        + "\n\nTests/validation:\n"
        + ("\n".join(f"- {t}" for t in change_set.tests_run) if change_set.tests_run else "- None reported")
        + "\n\nKnown risks:\n"
        + ("\n".join(f"- {r}" for r in change_set.risks) if change_set.risks else "- None reported")
    )

    return AgentMessage(
        type="REVIEW_REQUEST",
        sender="FORGE",
        recipient="SENTINEL",
        task_id=change_set.task_id,
        content=content,
        metadata={
            "files": change_set.files_changed,
            "focus": [
                "correctness", "security", "reliability",
                "architecture", "performance", "maintainability",
            ],
        },
    )
