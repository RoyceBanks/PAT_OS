from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from .config import CONFIG
from .llm import OllamaBackend
from .logging_setup import get_logger
from .messages import AgentMessage
from .prompts import SENTINEL_SYSTEM_PROMPT
from .workspace import Workspace
from .review_llm import sentinel_review_chat


@dataclass
class SentinelResult:
    task_id: str
    content: str
    status_hint: str | None = None


class SentinelAgent:
    name = "SENTINEL"

    def __init__(self, llm: OllamaBackend | None = None):
        self.llm = llm or OllamaBackend()
        self.logger = get_logger()

    def _task_id(self) -> str:
        return f"REVIEW-{uuid.uuid4().hex[:8].upper()}"

    def review(
        self,
        request: str,
        workspace: str | Path,
        task_id: str | None = None,
        files: list[str] | None = None,
        focus: list[str] | None = None,
    ) -> SentinelResult:
        task_id = task_id or self._task_id()
        focus = focus or [
            "security",
            "correctness",
            "reliability",
            "architecture",
            "performance",
            "maintainability",
        ]

        self.logger.info("Review started for %s", task_id)

        project = Workspace(workspace)
        context = project.build_review_context(
            files=files,
            max_files=CONFIG.max_context_files,
        )

        prompt = f"""
TASK ID: {task_id}

REVIEW REQUEST:
{request}

REVIEW FOCUS:
{", ".join(focus)}

PROJECT CONTEXT:
{context}

INSTRUCTIONS:
Perform an independent SENTINEL review.

Do not assume FORGE is correct.
Do not fabricate findings.
Only report issues supported by the supplied code/context.

Use the required SENTINEL review format:
REVIEW SUMMARY
FINDINGS
POSITIVE NOTES
FINAL DECISION

For every finding include:
ID
Severity
Category
Location
Problem
Evidence
Risk
Recommendation
Verification

Choose one final status:
APPROVED
APPROVED_WITH_NOTES
CHANGES_REQUIRED
BLOCKED
"""

        content = sentinel_review_chat(self.llm, SENTINEL_SYSTEM_PROMPT, prompt)

        self.logger.info("Review completed for %s", task_id)

        return SentinelResult(
            task_id=task_id,
            content=content,
            status_hint=self._extract_status(content),
        )

    def handle_message(
        self,
        message: AgentMessage,
        workspace: str | Path,
    ) -> AgentMessage:
        if message.recipient != self.name:
            raise ValueError(
                f"Message recipient is {message.recipient}, not SENTINEL."
            )

        if message.type not in {
            "REVIEW_REQUEST",
            "TASK",
            "QUESTION",
            "HANDOFF",
        }:
            raise ValueError(
                f"SENTINEL cannot currently handle message type {message.type}."
            )

        files = message.metadata.get("files")
        focus = message.metadata.get("focus")

        result = self.review(
            request=message.content,
            workspace=workspace,
            task_id=message.task_id,
            files=files,
            focus=focus,
        )

        return AgentMessage(
            type="CODE_REVIEW",
            sender="SENTINEL",
            recipient=message.sender,
            task_id=result.task_id,
            content=result.content,
            metadata={
                "in_reply_to": message.message_id,
                "status": result.status_hint,
                "reviewed_files": files or [],
            },
        )

    def inspect_project(
        self,
        workspace: str | Path,
    ) -> SentinelResult:
        return self.review(
            request=(
                "Perform a read-only audit of this project. Identify the most "
                "important security, correctness, reliability, architecture, "
                "performance, and maintainability risks. Do not modify files."
            ),
            workspace=workspace,
        )

    @staticmethod
    def _extract_status(content: str) -> str | None:
        statuses = [
            "BLOCKED",
            "CHANGES_REQUIRED",
            "APPROVED_WITH_NOTES",
            "APPROVED",
        ]

        upper = content.upper()

        for status in statuses:
            if status in upper:
                return status

        return None
