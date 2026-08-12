from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid

VALID_MESSAGE_TYPES = {
    "TASK", "QUESTION", "RESULT", "ERROR", "STATUS",
    "HANDOFF", "REVIEW_REQUEST", "CODE_REVIEW",
}


@dataclass
class AgentMessage:
    type: str
    sender: str
    recipient: str
    content: str
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        self.type = self.type.upper()
        self.sender = self.sender.upper()
        self.recipient = self.recipient.upper()

        if self.type not in VALID_MESSAGE_TYPES:
            raise ValueError(
                f"Unsupported message type: {self.type}. "
                f"Allowed: {sorted(VALID_MESSAGE_TYPES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
