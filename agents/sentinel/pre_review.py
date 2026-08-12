from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path

from agents.forge.actions import ImplementationPlan
from agents.forge.workspace import Workspace
from agents.sentinel.structure_facts import build_python_structure_facts


@dataclass
class ProposalCheck:
    name: str
    success: bool
    output: str


@dataclass
class ProposalReviewBundle:
    bundle_path: Path
    checks: list[ProposalCheck]
    diff_text: str


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _compile_proposed_python(plan: ImplementationPlan) -> list[ProposalCheck]:
    """Compile proposed Python source in memory without executing it."""

    checks: list[ProposalCheck] = []

    for change in plan.files:
        if not change.path.lower().endswith(".py"):
            continue

        try:
            compile(change.content, change.path, "exec")
            checks.append(
                ProposalCheck(
                    name=f"preflight-compile:{change.path}",
                    success=True,
                    output="Proposed Python syntax compiled successfully in memory.",
                )
            )
        except Exception as exc:
            checks.append(
                ProposalCheck(
                    name=f"preflight-compile:{change.path}",
                    success=False,
                    output=str(exc),
                )
            )

    return checks


def _diff_text(old_text: str, new_text: str, path: str, context_lines: int) -> str:
    raw = list(
        unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"current/{path}",
            tofile=f"proposed/{path}",
            n=context_lines,
            lineterm="",
        )
    )

    normalized = [line[:-1] if line.endswith("\n") else line for line in raw]
    return "\n".join(normalized) or "[NO TEXTUAL CHANGES]"


def build_proposal_review_bundle(
    pat_root: str | Path,
    workspace: str | Path,
    task_id: str,
    task: str,
    plan: ImplementationPlan,
    context_lines: int = 30,
    max_chars: int = 100_000,
) -> ProposalReviewBundle:
    """Build SENTINEL's pre-approval review artifact without editing targets."""

    project = Workspace(workspace, create=False)
    proposal_root = Path(pat_root).expanduser().resolve() / ".forge_proposals" / task_id
    proposal_root.mkdir(parents=True, exist_ok=True)

    checks = _compile_proposed_python(plan)

    sections = [
        "SENTINEL PRE-APPROVAL PROPOSAL REVIEW BUNDLE",
        "",
        f"TASK ID: {task_id}",
        f"WORKSPACE: {project.root}",
        "",
        "ORIGINAL USER TASK:",
        task,
        "",
        "FORGE PROPOSAL SUMMARY:",
        plan.summary,
        "",
        "PRE-APPLY VALIDATION:",
    ]

    if checks:
        for check in checks:
            state = "PASS" if check.success else "FAIL"
            sections.append(f"- {state}: {check.name}")
            if check.output:
                sections.append(f"  {check.output}")
    else:
        sections.append("- No Python files required preflight compilation.")

    sections.extend(["", "PROPOSED ACTUAL FILE CHANGES:"])
    combined_diffs: list[str] = []

    for change in plan.files:
        try:
            old_text = project.read_text(change.path, max_chars=500_000)
            existed = True
        except FileNotFoundError:
            old_text = ""
            existed = False

        diff = _diff_text(old_text, change.content, change.path, context_lines)
        combined_diffs.append(diff)

        sections.extend(
            [
                "",
                "=" * 72,
                f"FILE: {change.path}",
                "CURRENT SHA256: "
                + (_sha256_text(old_text) if existed else "[FILE DOES NOT EXIST]"),
                "PROPOSED SHA256: " + _sha256_text(change.content),
                "",
                "DIFF:",
                diff,
            ]
        )

        structure_facts = (
            build_python_structure_facts(
                before_source=old_text,
                after_source=change.content,
                relative_path=change.path,
            )
        )

        if structure_facts:
            sections.extend(
                [
                    "",
                    "AST STRUCTURAL FACTS:",
                    *structure_facts,
                    "",
                    (
                        "AST FACT INTERPRETATION: These facts are "
                        "computed from the complete parsed current/proposed "
                        "Python source. Definition counts and duplication "
                        "facts are authoritative. Removed '-' unified-diff "
                        "definitions do not coexist with the proposed source."
                    ),
                ]
            )


    sections.extend(
        [
            "",
            "=" * 72,
            "",
            "PRE-APPROVAL REVIEW INSTRUCTIONS:",
            "Review this exact proposed diff before target files are modified.",
            "Check whether it matches the user's request and assess correctness, security, reliability, architecture and maintainability.",
            "The current side came from the real workspace; the proposed side is the exact plan PAT will store if approved.",
            "Do not require the whole project unless the displayed context is genuinely insufficient for a material finding.",
        ]
    )

    content = "\n".join(sections)

    if len(content) > max_chars:
        raise RuntimeError(
            "SENTINEL pre-review bundle exceeded the safe size limit. Ask FORGE for a smaller proposal."
        )

    bundle_path = proposal_root / "pre_review_bundle.txt"
    bundle_path.write_text(content, encoding="utf-8")

    return ProposalReviewBundle(
        bundle_path=bundle_path,
        checks=checks,
        diff_text="\n\n".join(combined_diffs),
    )
