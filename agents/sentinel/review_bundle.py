from __future__ import annotations

from difflib import unified_diff
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Any
from agents.sentinel.structure_facts import build_python_structure_facts


def _hash_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    digest = sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _unified_diff(
    old_text: str,
    new_text: str,
    relative_path: str,
    context_lines: int,
) -> str:
    old_lines = old_text.splitlines(
        keepends=True
    )
    new_lines = new_text.splitlines(
        keepends=True
    )

    lines = list(
        unified_diff(
            old_lines,
            new_lines,
            fromfile=f"before/{relative_path}",
            tofile=f"after/{relative_path}",
            n=context_lines,
            lineterm="",
        )
    )

    normalized = [
        line[:-1]
        if line.endswith("\n")
        else line
        for line in lines
    ]

    return "\n".join(
        normalized
    ) or "[NO TEXTUAL CHANGES]"


def build_review_bundle(
    transaction: Any,
    task: str,
    summary: str,
    checks: Iterable[Any],
    context_lines: int = 30,
    max_chars: int = 100_000,
) -> Path:
    """
    Build a compact, deterministic review artifact from:
    - transaction backups (before)
    - actual current workspace files (after)
    - real validation check results

    The bundle is stored inside the transaction directory so it
    remains available for audit/history.
    """

    workspace_root = transaction.workspace.root

    sections = [
        "SENTINEL TRANSACTION REVIEW BUNDLE",
        "",
        f"TASK ID: {transaction.task_id}",
        f"WORKSPACE: {workspace_root}",
        "",
        "ORIGINAL TASK:",
        task,
        "",
        "FORGE SUMMARY:",
        summary,
        "",
        "VALIDATION RESULTS:",
    ]

    check_list = list(checks)

    if check_list:
        for check in check_list:
            status = (
                "PASS"
                if check.success
                else "FAIL"
            )

            sections.append(
                f"- {status}: {check.name}"
            )

            if check.output:
                sections.append(
                    f"  {check.output}"
                )
    else:
        sections.append(
            "- No validation checks were run."
        )

    sections.extend([
        "",
        "ACTUAL FILE CHANGES:",
    ])

    for entry in transaction.entries:
        relative = entry.path

        current_path = (
            workspace_root / relative
        ).resolve()

        if entry.existed:
            if not entry.backup_path:
                old_text = ""
                before_hash = None
            else:
                backup = Path(
                    entry.backup_path
                )
                old_text = _read_text(
                    backup
                )
                before_hash = _hash_file(
                    backup
                )
        else:
            old_text = ""
            before_hash = None

        new_text = _read_text(
            current_path
        )

        after_hash = _hash_file(
            current_path
        )

        diff = _unified_diff(
            old_text=old_text,
            new_text=new_text,
            relative_path=relative,
            context_lines=context_lines,
        )

        sections.extend([
            "",
            "=" * 72,
            f"FILE: {relative}",
            f"BEFORE SHA256: {before_hash or '[FILE DID NOT EXIST]'}",
            f"AFTER SHA256: {after_hash or '[FILE MISSING]'}",
            "",
            "DIFF:",
            diff,
        ])

        structure_facts = (
            build_python_structure_facts(
                before_source=old_text,
                after_source=new_text,
                relative_path=relative,
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
                        "computed from the complete parsed BEFORE/AFTER "
                        "Python source. Definition counts and duplication "
                        "facts are authoritative. Removed '-' unified-diff "
                        "definitions do not coexist with the AFTER source."
                    ),
                ]
            )


    sections.extend([
        "",
        "=" * 72,
        "",
        "REVIEW INSTRUCTIONS:",
        (
            "Review the actual transaction diff above. "
            "The BEFORE side comes from PAT's transaction backup. "
            "The AFTER side comes from the current real workspace after "
            "FORGE applied the approved plan. Validation results above "
            "come from PAT's local validation tools."
        ),
        (
            "Do not block merely because the full project is not included. "
            "If the shown surrounding context is genuinely insufficient "
            "to assess a material issue, state exactly what additional "
            "context is needed."
        ),
        (
            "Distinguish ordinary input validation from real security "
            "vulnerabilities. Severity must match demonstrated impact."
        ),
    ])

    content = "\n".join(
        sections
    )

    if len(content) > max_chars:
        raise RuntimeError(
            "SENTINEL review bundle exceeded the safe size limit. "
            "The change is too large for compact automatic review."
        )

    transaction.transaction_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = (
        transaction.transaction_root
        / "review_bundle.txt"
    )

    output.write_text(
        content,
        encoding="utf-8",
    )

    return output
