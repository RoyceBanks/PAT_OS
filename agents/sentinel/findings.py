from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
ReviewStatus = Literal[
    "APPROVED",
    "APPROVED_WITH_NOTES",
    "CHANGES_REQUIRED",
    "BLOCKED",
]


@dataclass
class ReviewFinding:
    id: str
    severity: Severity
    category: str
    location: str
    problem: str
    evidence: str
    risk: str
    recommendation: str
    verification: str = ""


@dataclass
class ReviewReport:
    task_id: str
    status: ReviewStatus
    findings: list[ReviewFinding] = field(default_factory=list)
    positive_notes: list[str] = field(default_factory=list)
    summary: str = ""

    def counts(self) -> dict[str, int]:
        counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0,
        }

        for finding in self.findings:
            counts[finding.severity] += 1

        return counts

    @staticmethod
    def recommended_status(findings: list[ReviewFinding]) -> ReviewStatus:
        severities = {finding.severity for finding in findings}

        if "CRITICAL" in severities:
            return "BLOCKED"

        if "HIGH" in severities or "MEDIUM" in severities:
            return "CHANGES_REQUIRED"

        if "LOW" in severities or "INFO" in severities:
            return "APPROVED_WITH_NOTES"

        return "APPROVED"
