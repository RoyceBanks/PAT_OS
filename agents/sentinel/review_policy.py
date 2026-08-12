from __future__ import annotations

import re
from dataclasses import dataclass


VALID_STATUSES = {
    "APPROVED",
    "APPROVED_WITH_NOTES",
    "CHANGES_REQUIRED",
    "BLOCKED",
}

STATUS_RANK = {
    "APPROVED": 0,
    "APPROVED_WITH_NOTES": 1,
    "CHANGES_REQUIRED": 2,
    "BLOCKED": 3,
}

SEVERITY_STATUS = {
    "INFO": "APPROVED_WITH_NOTES",
    "LOW": "APPROVED_WITH_NOTES",
    "MEDIUM": "CHANGES_REQUIRED",
    "HIGH": "CHANGES_REQUIRED",
    "CRITICAL": "BLOCKED",
}

SEVERITY_RANK = {
    "INFO": 0,
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}

_SEVERITY = (
    r"(CRITICAL|HIGH|MEDIUM|LOW|INFO)"
)


@dataclass
class ReviewPolicyResult:
    model_status: str
    effective_status: str
    finding_status: str
    highest_severity: str | None
    severities: list[str]
    policy_overrode_model: bool
    needs_reconciliation: bool
    reconciliation_reason: str | None


def normalize_status(
    status: str | None,
) -> str:
    if not status:
        return "APPROVED"

    normalized = (
        str(status)
        .strip()
        .upper()
        .replace(" ", "_")
    )

    if normalized not in VALID_STATUSES:
        return "CHANGES_REQUIRED"

    return normalized


def _append(
    found: list[str],
    severity: str,
):
    severity = severity.upper()

    if severity in SEVERITY_RANK:
        found.append(
            severity
        )


def _extract_distribution_lines(
    review_text: str,
    found: list[str],
):
    """
    Parse lines such as:

        Severity Distribution: 1 INFO, 0 MEDIUM, 0 HIGH, 0 CRITICAL
        Severity Distribution: INFO=1, MEDIUM=0

    Only nonzero counts become current findings.
    """

    for line in review_text.splitlines():
        if not re.search(
            r"(?i)\bseverity\s+distribution\b",
            line,
        ):
            continue

        for match in re.finditer(
            (
                r"(?i)"
                r"(?:(\d+)\s+"
                + _SEVERITY
                + r"\b|"
                + _SEVERITY
                + r"\s*[=:]\s*(\d+))"
            ),
            line,
        ):
            if (
                match.group(1)
                is not None
            ):
                count = int(
                    match.group(1)
                )
                severity = (
                    match.group(2)
                )
            else:
                severity = (
                    match.group(3)
                )
                count = int(
                    match.group(4)
                )

            if count > 0:
                _append(
                    found,
                    severity,
                )


def extract_severities(
    review_text: str,
) -> list[str]:
    """
    Extract CURRENT finding severities without being fooled
    by historical prose.

    Strong current-review forms:
        Severity: MEDIUM
        **Severity**: MEDIUM
        ID: MEDIUM-001
        **ID**: MEDIUM-001
        Medium count: 1
        Findings: 1 MEDIUM severity issue
        Severity Distribution: 1 INFO, 0 MEDIUM
        1. Generic Error Messages (MEDIUM)
        - Function Naming Ambiguity [MEDIUM]

    Deliberately NOT treated as a current finding:
        "the previous MEDIUM severity issue was resolved"

    A bare phrase like "MEDIUM severity" is too ambiguous
    outside a structured field/count, so v1.3.4 does not
    parse it globally.
    """

    if not review_text:
        return []

    found: list[str] = []

    # 1. Explicit finding field:
    #    Severity: MEDIUM
    for match in re.finditer(
        (
            r"(?im)"
            r"(?:\*\*)?"
            r"severity"
            r"(?:\*\*)?"
            r"\s*[:\-]\s*"
            + _SEVERITY
            + r"\b"
        ),
        review_text,
    ):
        _append(
            found,
            match.group(1),
        )

    # 2. Finding ID encodes severity:
    #    ID: MEDIUM-001
    for match in re.finditer(
        (
            r"(?im)"
            r"(?:\*\*)?"
            r"id"
            r"(?:\*\*)?"
            r"\s*[:\-]\s*"
            + _SEVERITY
            + r"[-_]\d+\b"
        ),
        review_text,
    ):
        _append(
            found,
            match.group(1),
        )

    # 3. Named severity count:
    #    Medium count: 1
    for match in re.finditer(
        (
            r"(?im)\b"
            + _SEVERITY
            + r"\s+count"
            r"\s*[:\-]\s*"
            r"(\d+)\b"
        ),
        review_text,
    ):
        severity = (
            match.group(1)
        )
        count = int(
            match.group(2)
        )

        if count > 0:
            _append(
                found,
                severity,
            )

    # 4. Numbered finding summary:
    #    1 MEDIUM severity issue
    #    2 HIGH severity findings
    #
    # A numeric count is required. This is what prevents
    # "previous MEDIUM severity issue" from being parsed.
    for match in re.finditer(
        (
            r"(?i)\b"
            r"(\d+)\s+"
            + _SEVERITY
            + r"\s+severity"
            r"(?:\s+(?:issue|issues|finding|findings))?"
            r"\b"
        ),
        review_text,
    ):
        count = int(
            match.group(1)
        )
        severity = (
            match.group(2)
        )

        if count > 0:
            _append(
                found,
                severity,
            )

    # 5. Finding-title severity:
    #    1. **Generic Error Messages (MEDIUM)**
    #    - Function Naming Ambiguity [MEDIUM]
    #
    # Restrict this to heading/list-like lines so historical prose
    # such as "resolved the previous MEDIUM severity issue" remains
    # ignored.
    for line in review_text.splitlines():
        stripped = (
            line
            .strip()
            .replace("**", "")
        )

        if not re.match(
            r"^(?:\d+[.)]\s+|[-*]\s+)",
            stripped,
        ):
            continue

        match = re.search(
            (
                r"(?:\(|\[)"
                + _SEVERITY
                + r"(?:\)|\])"
                r"\s*$"
            ),
            stripped,
            flags=re.IGNORECASE,
        )

        if match:
            _append(
                found,
                match.group(1),
            )

    # 6. Structured severity distribution.
    _extract_distribution_lines(
        review_text,
        found,
    )

    return found


def highest_severity(
    severities: list[str],
) -> str | None:
    if not severities:
        return None

    return max(
        severities,
        key=lambda item: (
            SEVERITY_RANK[item]
        ),
    )


def _needs_reconciliation(
    model_status: str,
    finding_status: str,
    highest: str | None,
) -> tuple[bool, str | None]:
    # CRITICAL remains immediate BLOCKED.
    if highest == "CRITICAL":
        return (
            False,
            None,
        )

    if (
        model_status
        in {
            "APPROVED",
            "APPROVED_WITH_NOTES",
        }
        and finding_status
        == "CHANGES_REQUIRED"
    ):
        return (
            True,
            (
                "SENTINEL approved the proposal while "
                "assigning a current severity that PAT "
                "policy treats as requiring code changes."
            ),
        )

    return (
        False,
        None,
    )


def enforce_review_policy(
    model_status: str | None,
    review_text: str,
) -> ReviewPolicyResult:
    normalized_model = (
        normalize_status(
            model_status
        )
    )

    severities = (
        extract_severities(
            review_text
        )
    )

    highest = (
        highest_severity(
            severities
        )
    )

    finding_status = (
        SEVERITY_STATUS[highest]
        if highest is not None
        else "APPROVED"
    )

    effective = max(
        (
            normalized_model,
            finding_status,
        ),
        key=lambda item: (
            STATUS_RANK[item]
        ),
    )

    (
        needs_reconciliation,
        reconciliation_reason,
    ) = _needs_reconciliation(
        model_status=normalized_model,
        finding_status=finding_status,
        highest=highest,
    )

    return ReviewPolicyResult(
        model_status=normalized_model,
        effective_status=effective,
        finding_status=finding_status,
        highest_severity=highest,
        severities=severities,
        policy_overrode_model=(
            effective
            != normalized_model
        ),
        needs_reconciliation=(
            needs_reconciliation
        ),
        reconciliation_reason=(
            reconciliation_reason
        ),
    )
