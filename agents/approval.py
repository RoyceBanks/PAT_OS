from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import uuid

from agents.forge.actions import ImplementationPlan


@dataclass
class PendingApproval:
    approval_id: str
    task_id: str
    task: str
    workspace: str
    plan: ImplementationPlan
    approved_paths: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalStore:
    """
    Ephemeral approval store.

    Pending approvals intentionally do not survive a PAT restart.
    This prevents stale approvals from being executed later.
    """

    def __init__(self):
        self._pending: dict[str, PendingApproval] = {}
        self._latest_id: str | None = None

    def create(
        self,
        task_id: str,
        task: str,
        workspace: str | Path,
        plan: ImplementationPlan,
        metadata: dict[str, Any] | None = None,
    ) -> PendingApproval:
        approval_id = (
            "APPROVAL-"
            + uuid.uuid4().hex[:8].upper()
        )

        approved_paths = tuple(
            change.path
            for change in plan.files
        )

        pending = PendingApproval(
            approval_id=approval_id,
            task_id=task_id,
            task=task,
            workspace=str(
                Path(workspace)
                .expanduser()
                .resolve()
            ),
            plan=plan,
            approved_paths=approved_paths,
            metadata=metadata or {},
        )

        self._pending[approval_id] = pending
        self._latest_id = approval_id

        return pending

    def get(
        self,
        approval_id: str | None = None,
    ) -> PendingApproval | None:
        selected = (
            approval_id
            or self._latest_id
        )

        if selected is None:
            return None

        return self._pending.get(
            selected
        )

    def pop(
        self,
        approval_id: str | None = None,
    ) -> PendingApproval | None:
        selected = (
            approval_id
            or self._latest_id
        )

        if selected is None:
            return None

        pending = self._pending.pop(
            selected,
            None,
        )

        if selected == self._latest_id:
            self._latest_id = (
                next(
                    reversed(self._pending),
                    None,
                )
                if self._pending
                else None
            )

        return pending

    def clear(self) -> None:
        self._pending.clear()
        self._latest_id = None

    def count(self) -> int:
        return len(
            self._pending
        )
