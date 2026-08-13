from __future__ import annotations
import ast
import copy
import hashlib
import os
import re
from pathlib import Path, PurePosixPath

from agents.approval import (
    ApprovalStore,
    PendingApproval,
)
from agents.forge.agent import (
    ForgeAgent,
    ForgeResult,
)
from agents.forge.execution import (
    CheckResult,
    SafePythonRunner,
)
from agents.forge.tools import (
    ForgeTools,
)
from agents.forge.transaction import (
    WorkspaceTransaction,
)
from agents.forge.diff_preview import (
    build_plan_diff_previews,
)
from agents.forge.history import (
    ForgeHistory,
)
from agents.forge.semantic_preflight import (
    validate_plan_semantics,
)
from agents.forge.deterministic_repair import (
    repair_return_requirement,
)
from agents.sentinel.agent import (
    SentinelAgent,
)
from agents.sentinel.review_bundle import (
    build_review_bundle,
)
from agents.sentinel.pre_review import (
    build_proposal_review_bundle,
)

from agents.sentinel.review_policy import (
    enforce_review_policy,
)


SAFE_MULTI_FILE_MAX_FILES = 5
SAFE_MULTI_FILE_EXTENSIONS = {
    ".py",
}


class AgentManager:
    """
    PAT specialist-agent coordinator.

    Generic coding workflow:
        PAT -> FORGE -> isolated workspace -> validation
            -> SENTINEL -> PAT

    Existing-project workflow:
        PAT -> FORGE proposal -> SENTINEL pre-review
            -> stop on exact user-code conflicts
            -> FORGE revision if appropriate
            -> reject identical revision cycles
            -> USER APPROVAL
            -> transaction snapshot -> controlled writes
            -> validation -> SENTINEL post-apply review
            -> commit OR rollback -> PAT
    """

    def __init__(
        self,
        
        max_review_rounds=3,
    ):
        self.forge = ForgeAgent()
        self.sentinel = SentinelAgent()
        self.max_pre_review_rounds = 3
        self.max_review_rounds = (
            max_review_rounds
        )

        self.approvals = (
            ApprovalStore()
        )

        self.pat_root = (
            Path(__file__)
            .resolve()
            .parents[1]
        )

        self.history = ForgeHistory(
            self.pat_root
        )


        self.generated_root = (
            self.pat_root
            / "forge_projects"
        )

        self.generated_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _normalize_path(self, path):
        normalized = (
            str(path)
            .replace("\\", "/")
            .strip()
        )

        while normalized.startswith("./"):
            normalized = normalized[2:]

        if normalized.lower().startswith("pat_os/"):
            normalized = normalized[7:]

        return normalized


    def _plan_fingerprint(
        self,
        plan,
    ):
        """
        Return a deterministic SHA-256 fingerprint for the
        actual proposed file changes.

        Summary text and other LLM prose are intentionally
        excluded. Only normalized file paths and exact proposed
        file contents determine whether a revision is genuinely
        different.
        """

        digest = hashlib.sha256()

        changes = sorted(
            plan.files,
            key=lambda change: (
                self._normalize_path(
                    change.path
                )
            ),
        )

        for change in changes:
            normalized_path = (
                self._normalize_path(
                    change.path
                )
            )

            digest.update(
                normalized_path.encode(
                    "utf-8"
                )
            )
            digest.update(b"\0")

            digest.update(
                change.content.encode(
                    "utf-8"
                )
            )
            digest.update(b"\0")

        return digest.hexdigest()


    def _extract_exact_requested_snippets(
        self,
        task,
    ):
        """
        Extract literal code the user explicitly asked FORGE to
        insert before/after an anchor.

        Examples:
            insert "ROUTE_COMMAND_CACHE = {}" immediately before ...
            insert 'x = 1' after ...

        The quoted token is parsed with ast.literal_eval so escaped
        quotes/backslashes are handled without executing code.
        """

        patterns = [
            (
                r'\binsert\s+'
                r'("(?:\\.|[^"\\])*")'
                r'\s+(?:immediately\s+)?'
                r'(?:before|after)\b'
            ),
            (
                r"\binsert\s+"
                r"('(?:\\.|[^'\\])*')"
                r"\s+(?:immediately\s+)?"
                r"(?:before|after)\b"
            ),
        ]

        snippets = []

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                task,
                flags=re.IGNORECASE,
            ):
                literal = match.group(1)

                try:
                    value = ast.literal_eval(
                        literal
                    )
                except Exception:
                    continue

                if (
                    isinstance(value, str)
                    and value
                    and value not in snippets
                ):
                    snippets.append(
                        value
                    )

        return snippets


    def _plan_contains_exact_snippets(
        self,
        plan,
        snippets,
    ):
        if not snippets:
            return False

        contents = [
            change.content
            for change in plan.files
        ]

        return all(
            any(
                snippet in content
                for content in contents
            )
            for snippet in snippets
        )


    def _extract_requested_paths(self, task):
        text = task.replace("\\", "/")

        matches = re.findall(
            r"((?:[A-Za-z0-9_.-]+/)+"
            r"[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)",
            text,
        )

        results = []

        for match in matches:
            normalized = self._normalize_path(
                match
            )

            if normalized not in results:
                results.append(normalized)

        return results


    def _safe_project_path_error(
        self,
        path,
    ):
        """
        Return a reason when a project-relative path is unsafe.
        """

        normalized = (
            self._normalize_path(
                path
            )
        )

        if not normalized:
            return "empty path"

        if normalized.startswith(
            "/"
        ):
            return "absolute path"

        if re.match(
            r"^[A-Za-z]:/",
            normalized,
        ):
            return "absolute drive path"

        parts = (
            PurePosixPath(
                normalized
            )
            .parts
        )

        if ".." in parts:
            return "parent traversal"

        return None


    def _validate_requested_file_scope(
        self,
        requested_paths,
    ):
        """
        Validate explicit user-named paths before FORGE plans.

        Safe Multi-File Phase 1:
        - maximum 5 files
        - Python only when more than one file is named
        - safe project-relative paths only
        """

        normalized = [
            self._normalize_path(
                path
            )
            for path in requested_paths
        ]

        unsafe = []

        for path in normalized:
            reason = (
                self._safe_project_path_error(
                    path
                )
            )

            if reason:
                unsafe.append(
                    (
                        path,
                        reason,
                    )
                )

        if unsafe:
            return (
                "Unsafe file scope:\n"
                + "\n".join(
                    f"- {path}: {reason}"
                    for path, reason
                    in unsafe
                )
            )

        if len(
            normalized
        ) != len(
            set(
                normalized
            )
        ):
            return (
                "The requested file scope contains "
                "duplicate paths."
            )

        if (
            len(
                normalized
            )
            > SAFE_MULTI_FILE_MAX_FILES
        ):
            return (
                "Safe Multi-File Phase 1 allows at most "
                f"{SAFE_MULTI_FILE_MAX_FILES} files per task."
            )

        if len(
            normalized
        ) > 1:
            unsupported = [
                path
                for path in normalized
                if (
                    PurePosixPath(
                        path
                    )
                    .suffix
                    .lower()
                    not in
                    SAFE_MULTI_FILE_EXTENSIONS
                )
            ]

            if unsupported:
                return (
                    "Safe Multi-File Phase 1 is Python-only. "
                    "Unsupported paths:\n"
                    + "\n".join(
                        f"- {path}"
                        for path
                        in unsupported
                    )
                )

        return None


    def _validate_proposed_plan_scope(
        self,
        plan,
        requested_paths,
    ):
        """
        Validate FORGE's exact proposed file set before review/approval.

        Multi-file plans require an explicit user-named scope.
        FORGE may use a subset but may not expand outside that scope.
        """

        proposed = [
            self._normalize_path(
                change.path
            )
            for change in plan.files
        ]

        if not proposed:
            return (
                "FORGE did not request any file changes."
            )

        if len(
            proposed
        ) != len(
            set(
                proposed
            )
        ):
            return (
                "FORGE proposed the same file more than once."
            )

        if (
            len(
                proposed
            )
            > SAFE_MULTI_FILE_MAX_FILES
        ):
            return (
                "FORGE proposed too many files. "
                "Safe Multi-File Phase 1 allows at most "
                f"{SAFE_MULTI_FILE_MAX_FILES}."
            )

        unsafe = []

        for path in proposed:
            reason = (
                self._safe_project_path_error(
                    path
                )
            )

            if reason:
                unsafe.append(
                    (
                        path,
                        reason,
                    )
                )

        if unsafe:
            return (
                "FORGE proposed unsafe paths:\n"
                + "\n".join(
                    f"- {path}: {reason}"
                    for path, reason
                    in unsafe
                )
            )

        if len(
            proposed
        ) > 1:
            if not requested_paths:
                return (
                    "FORGE attempted a multi-file change "
                    "without an explicit user-named file scope. "
                    "Name the exact 2-5 Python files in the request."
                )

            unsupported = [
                path
                for path in proposed
                if (
                    PurePosixPath(
                        path
                    )
                    .suffix
                    .lower()
                    not in
                    SAFE_MULTI_FILE_EXTENSIONS
                )
            ]

            if unsupported:
                return (
                    "FORGE proposed non-Python files in "
                    "Safe Multi-File Phase 1:\n"
                    + "\n".join(
                        f"- {path}"
                        for path
                        in unsupported
                    )
                )

        if requested_paths:
            allowed = {
                self._normalize_path(
                    path
                )
                for path
                in requested_paths
            }

            unauthorized = (
                set(
                    proposed
                )
                - allowed
            )

            if unauthorized:
                return (
                    "FORGE attempted to modify files outside "
                    "the explicit user-approved scope:\n"
                    + "\n".join(
                        f"- {path}"
                        for path
                        in sorted(
                            unauthorized
                        )
                    )
                )

        return None

    # ==================================================
    # PUBLIC API
    # ==================================================

    def coding_task(
        self,
        task,
        workspace=None,
        require_approval=None,
    ):
        """
        Route coding work to either the existing PAT workspace or an
        isolated generated-project workspace.

        Safe Multi-File Phase 1 dispatch rule:
        when the user explicitly names 2-5 project-relative Python files,
        the task is automatically treated as an existing-PAT-project
        change and MUST go through the proposal/approval pipeline.

        Requests without an explicit multi-file scope retain the previous
        isolated-project behavior when no workspace is supplied.
        """

        requested_paths = (
            self._extract_requested_paths(
                task
            )
        )

        explicit_safe_multifile = (
            2
            <= len(
                requested_paths
            )
            <= SAFE_MULTI_FILE_MAX_FILES
        )

        if (
            workspace is None
            and explicit_safe_multifile
        ):
            scope_error = (
                self._validate_requested_file_scope(
                    requested_paths
                )
            )

            if scope_error:
                return self._simple_result(
                    (
                        "FORGE SAFE MULTI-FILE SCOPE REJECTED\n\n"
                        f"{scope_error}\n\n"
                        "NO FILES WERE MODIFIED."
                    ),
                    success=False,
                )

            workspace = self.pat_root
            require_approval = True

            print(
                "FORGE SAFE MULTI-FILE ROUTE: "
                "EXISTING PAT WORKSPACE + APPROVAL"
            )

        elif require_approval is None:
            require_approval = (
                workspace is not None
            )

        if require_approval:
            if workspace is None:
                task_id = (
                    self.forge.new_task_id()
                )

                workspace = (
                    self.generated_root
                    / task_id
                )

                workspace.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                return (
                    self._propose_existing_project_task(
                        task=task,
                        workspace=workspace,
                        task_id=task_id,
                    )
                )

            return self._propose_existing_project_task(
                task=task,
                workspace=workspace,
            )

        return self._run_isolated_task(
            task=task,
            workspace=workspace,
        )

    def approve_pending(
        self,
        approval_id=None,
    ):
        pending = self.approvals.pop(
            approval_id
        )

        if pending is None:
            return self._simple_result(
                "There are no pending FORGE changes to approve.",
                success=False,
            )

        return self._execute_approved_task(
            pending
        )

    def deny_pending(
        self,
        approval_id=None,
    ):
        pending = self.approvals.pop(
            approval_id
        )

        if pending is None:
            return self._simple_result(
                "There are no pending FORGE changes to deny.",
                success=False,
            )

        lines = [
            "FORGE CHANGE CANCELLED",
            "",
            f"Task: {pending.task_id}",
            f"Approval: {pending.approval_id}",
            "",
            "No files were modified.",
        ]

        return self._simple_result(
            "\n".join(lines),
            success=True,
            task_id=pending.task_id,
        )

    # ==================================================
    # EXISTING-PROJECT PROPOSAL
    # ==================================================


    def _extract_acceptance_criteria(
        self,
        task,
    ):
        """
        Deterministically derive a compact requirement checklist from the
        user's task text.

        This preserves explicit clauses and does not invent requirements.
        """

        text = str(task or "")
        text = text.replace(r"\_", "_")
        text = text.replace(r"\*", "*")
        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        if not text:
            return []

        raw_parts = re.split(
            r"\s*;\s*|"
            r"(?<=[.!?])\s+|"
            r"\s*:\s+(?=[A-Za-z0-9_])",
            text,
        )

        criteria = []

        for raw in raw_parts:
            clause = raw.strip(
                " \t\r\n.;"
            )

            if not clause:
                continue

            lowered = clause.lower()

            # File scope is enforced by PAT's hard path validator. Avoid
            # duplicating a pure multi-file path authorization sentence.
            if (
                (
                    lowered.startswith(
                        "have forge create "
                    )
                    or lowered.startswith(
                        "forge create "
                    )
                )
                and len(
                    re.findall(
                        r"\b[\w./\\-]+\.py\b",
                        clause,
                        flags=re.IGNORECASE,
                    )
                ) >= 2
            ):
                continue

            clause = clause[:500]

            if clause not in criteria:
                criteria.append(
                    clause
                )

            if len(criteria) >= 12:
                break

        if not criteria:
            criteria = [
                text[:500]
            ]

        return criteria


    def _acceptance_criteria_contract(
        self,
        criteria,
    ):
        if not criteria:
            return ""

        lines = [
            "",
            "",
            "MANDATORY USER ACCEPTANCE CRITERIA:",
        ]

        for index, criterion in enumerate(
            criteria,
            start=1,
        ):
            lines.append(
                f"R{index}: {criterion}"
            )

        lines.extend([
            "",
            "REQUIREMENT-COVERAGE CONTRACT:",
            "- Evaluate EVERY criterion above against the exact proposal.",
            "- A requirement is PASS only when the proposed code directly "
            "satisfies it; do not infer missing behavior.",
            "- Distinguish similar but different behavior. Examples: "
            "print is not return; defining a value is not exposing it; "
            "creating one object is not creating two; importing a symbol "
            "is not calling it.",
            "- If a criterion is not proven by the proposal, mark FAIL.",
            "- Do not convert an explicit user requirement into an optional "
            "maintainability suggestion.",
            "- Include exactly one structured line for every criterion.",
            "",
            "Your review MUST include this exact section:",
            "## REQUIREMENT COVERAGE",
        ])

        for index in range(
            1,
            len(criteria) + 1,
        ):
            lines.append(
                f"- R{index}: PASS or FAIL - concise evidence"
            )

        return "\n".join(
            lines
        )


    def _parse_requirement_coverage(
        self,
        review_text,
        criteria,
    ):
        """
        Parse the mandatory REQUIREMENT COVERAGE section.

        Returns:
            (valid, failures, reason, coverage_lines)
        """

        if not criteria:
            return (
                True,
                [],
                "",
                [],
            )

        text = str(
            review_text
            or ""
        )

        match = re.search(
            (
                r"(?is)"
                r"(?:^|\n)"
                r"[ \t]*(?:#{1,6}[ \t]*)+"
                r"REQUIREMENT COVERAGE[ \t]*\n"
                r"(.*?)"
                r"(?=\n[ \t]*(?:#{1,6}[ \t]*)+\S|\Z)"
            ),
            text,
        )

        if not match:
            return (
                False,
                [],
                "SENTINEL omitted the mandatory REQUIREMENT COVERAGE section.",
                [],
            )

        section = match.group(1)

        pattern = re.compile(
            (
                r"(?im)^\s*-\s*R(\d+)\s*:\s*"
                r"(PASS|FAIL)\b"
                r"(?:\s*(?:-|—|\||:)\s*)?"
                r"(.*?)\s*$"
            )
        )

        parsed = {}
        duplicates = set()
        lines = []

        for item in pattern.finditer(
            section
        ):
            number = int(
                item.group(1)
            )
            status = (
                item.group(2)
                .upper()
            )
            evidence = (
                item.group(3)
                .strip()
            )

            if number in parsed:
                duplicates.add(
                    number
                )
                continue

            parsed[number] = (
                status,
                evidence,
            )

            lines.append(
                (
                    number,
                    status,
                    evidence,
                )
            )

        expected = set(
            range(
                1,
                len(criteria) + 1,
            )
        )

        received = set(
            parsed
        )

        unknown = (
            received
            - expected
        )

        missing = (
            expected
            - received
        )

        empty_evidence = sorted(
            number
            for number, (
                _status,
                evidence,
            ) in parsed.items()
            if not evidence
        )

        if duplicates:
            return (
                False,
                [],
                (
                    "SENTINEL duplicated requirement IDs: "
                    + ", ".join(
                        f"R{number}"
                        for number in sorted(
                            duplicates
                        )
                    )
                ),
                lines,
            )

        if unknown:
            return (
                False,
                [],
                (
                    "SENTINEL returned unknown requirement IDs: "
                    + ", ".join(
                        f"R{number}"
                        for number in sorted(
                            unknown
                        )
                    )
                ),
                lines,
            )

        if missing:
            return (
                False,
                [],
                (
                    "SENTINEL omitted requirement IDs: "
                    + ", ".join(
                        f"R{number}"
                        for number in sorted(
                            missing
                        )
                    )
                ),
                lines,
            )

        if empty_evidence:
            return (
                False,
                [],
                (
                    "SENTINEL omitted evidence for: "
                    + ", ".join(
                        f"R{number}"
                        for number in empty_evidence
                    )
                ),
                lines,
            )

        failures = [
            number
            for number, (
                status,
                _evidence,
            ) in parsed.items()
            if status == "FAIL"
        ]

        return (
            True,
            sorted(
                failures
            ),
            "",
            sorted(
                lines,
                key=lambda item: item[0],
            ),
        )


    def _requirement_coverage_recheck(
        self,
        *,
        sentinel_result,
        criteria,
        workspace,
        task_id,
        files,
    ):
        """
        Recheck only requirement coverage once when SENTINEL omitted or
        malformed the mandatory structured checklist.

        No FORGE revision occurs during this recheck.
        """

        (
            valid,
            failures,
            reason,
            lines,
        ) = self._parse_requirement_coverage(
            sentinel_result.content,
            criteria,
        )

        if valid:
            return (
                sentinel_result.content,
                failures,
                lines,
                None,
            )

        print(
            "SENTINEL REQUIREMENT COVERAGE RECHECK: "
            + reason
        )

        request = (
            "REQUIREMENT COVERAGE RECHECK.\n\n"
            "Review the EXACT SAME proposal bundle. "
            "Do not ask FORGE to revise code during this recheck. "
            "Your sole job is to verify every explicit user acceptance "
            "criterion against the proposed code.\n"
            + self._acceptance_criteria_contract(
                criteria
            )
            + "\n\nReturn the required structured "
            "## REQUIREMENT COVERAGE section."
        )

        rechecked = self.sentinel.review(
            request=request,
            workspace=workspace,
            task_id=task_id,
            files=files,
            focus=[
                "correctness",
                "requirements",
            ],
        )

        (
            valid,
            failures,
            reason,
            lines,
        ) = self._parse_requirement_coverage(
            rechecked.content,
            criteria,
        )

        if not valid:
            return (
                rechecked.content,
                [],
                lines,
                reason,
            )

        print(
            "SENTINEL REQUIREMENT COVERAGE RECHECK: PASS"
        )

        return (
            rechecked.content,
            failures,
            lines,
            None,
        )


    def _semantic_repair_targets(
        self,
        *,
        findings,
        requested_paths,
        rejected_plan,
    ):
        """
        Return exact proposed files implicated by deterministic semantic
        findings.

        A semantic repair target must:
        - be named by a machine finding,
        - be inside the user's authorized scope,
        - already exist in the rejected candidate plan.
        """

        allowed = {
            self._normalize_path(
                path
            )
            for path in (
                requested_paths
                or []
            )
        }

        proposed = {
            self._normalize_path(
                change.path
            )
            for change in getattr(
                rejected_plan,
                "files",
                [],
            )
        }

        targets = []

        for finding in (
            findings
            or []
        ):
            path = self._normalize_path(
                getattr(
                    finding,
                    "path",
                    "",
                )
            )

            if not path:
                continue

            if (
                allowed
                and path not in allowed
            ):
                continue

            if path not in proposed:
                continue

            if path not in targets:
                targets.append(
                    path
                )

        return targets


    def _plan_change_by_path(
        self,
        plan,
        path,
    ):
        target = self._normalize_path(
            path
        )

        for change in getattr(
            plan,
            "files",
            [],
        ):
            if (
                self._normalize_path(
                    change.path
                )
                == target
            ):
                return change

        return None


    def _merge_targeted_repair(
        self,
        *,
        rejected_plan,
        repair_plan,
        target_path,
    ):
        """
        Merge exactly one repaired file into a deep copy of the rejected
        candidate plan.

        No workspace files are written here.
        """

        target = self._normalize_path(
            target_path
        )

        repair_files = list(
            getattr(
                repair_plan,
                "files",
                [],
            )
        )

        if len(
            repair_files
        ) != 1:
            raise ValueError(
                "Targeted FORGE repair must return exactly "
                "one file."
            )

        replacement = repair_files[0]

        replacement_path = (
            self._normalize_path(
                replacement.path
            )
        )

        if replacement_path != target:
            raise ValueError(
                "Targeted FORGE repair returned the wrong path: "
                f"{replacement_path!r}; expected {target!r}."
            )

        merged = copy.deepcopy(
            rejected_plan
        )

        merged_files = list(
            getattr(
                merged,
                "files",
                [],
            )
        )

        replaced = False

        for index, change in enumerate(
            merged_files
        ):
            if (
                self._normalize_path(
                    change.path
                )
                == target
            ):
                merged_files[index] = (
                    replacement
                )
                replaced = True
                break

        if not replaced:
            raise ValueError(
                "Targeted repair path does not exist in "
                "the rejected candidate plan: "
                + target
            )

        try:
            merged.files = merged_files
        except Exception:
            try:
                merged.files[:] = (
                    merged_files
                )
            except Exception as exc:
                raise ValueError(
                    "Could not merge targeted FORGE "
                    "repair into candidate plan."
                ) from exc

        return merged


    def _replace_candidate_file_content(
        self,
        *,
        candidate,
        target_path,
        content,
    ):
        """
        Replace exactly one file's content inside an in-memory candidate.

        The original rejected plan is not mutated.
        """

        target = self._normalize_path(
            target_path
        )

        files = list(
            getattr(
                candidate,
                "files",
                [],
            )
        )

        replacement_index = None

        for index, change in enumerate(
            files
        ):
            if (
                self._normalize_path(
                    change.path
                )
                == target
            ):
                replacement_index = (
                    index
                )
                break

        if replacement_index is None:
            raise ValueError(
                "Deterministic repair target is not present "
                "in the candidate plan: "
                + target
            )

        replacement = copy.deepcopy(
            files[
                replacement_index
            ]
        )

        try:
            replacement.content = (
                content
            )
        except Exception as exc:
            raise ValueError(
                "Could not replace targeted candidate file content."
            ) from exc

        files[
            replacement_index
        ] = replacement

        try:
            candidate.files = files
        except Exception:
            try:
                candidate.files[:] = (
                    files
                )
            except Exception as exc:
                raise ValueError(
                    "Could not update candidate plan files."
                ) from exc

        return candidate


    def _targeted_semantic_repair(
        self,
        *,
        rejected_plan,
        semantic_findings,
        requested_paths,
        base_task,
        workspace,
        task_id,
        round_number,
    ):
        """
        Repair only files implicated by deterministic semantic findings.

        Each repair call is restricted to exactly one existing candidate
        file. All unrelated candidate files are preserved byte-for-byte.
        """

        targets = (
            self._semantic_repair_targets(
                findings=semantic_findings,
                requested_paths=requested_paths,
                rejected_plan=rejected_plan,
            )
        )

        if not targets:
            raise ValueError(
                "PAT could not map deterministic semantic "
                "findings to an authorized rejected-plan file."
            )

        candidate = copy.deepcopy(
            rejected_plan
        )

        print(
            "FORGE TARGETED SEMANTIC REPAIR: "
            + ", ".join(
                targets
            )
        )

        for target_path in targets:
            current_change = (
                self._plan_change_by_path(
                    candidate,
                    target_path,
                )
            )

            if current_change is None:
                raise ValueError(
                    "Targeted repair candidate disappeared: "
                    + target_path
                )

            relevant = [
                finding
                for finding in semantic_findings
                if (
                    self._normalize_path(
                        getattr(
                            finding,
                            "path",
                            "",
                        )
                    )
                    == target_path
                )
            ]

            finding_text = (
                "\n".join(
                    "- "
                    + finding.format()
                    for finding in relevant
                )
                or "- Deterministic semantic repair required."
            )

            current_content = str(
                getattr(
                    current_change,
                    "content",
                    "",
                )
            )

            deterministic_content = (
                repair_return_requirement(
                    path=target_path,
                    source=current_content,
                    findings=relevant,
                )
            )

            if deterministic_content is not None:
                print(
                    "PAT DETERMINISTIC STRUCTURAL REPAIR: "
                    + target_path
                )

                candidate = (
                    self._replace_candidate_file_content(
                        candidate=candidate,
                        target_path=target_path,
                        content=deterministic_content,
                    )
                )

                # No LLM call is needed for this target. The outer proposal
                # loop will rerun the complete deterministic semantic
                # preflight across all candidate files.
                continue

            repair_task = (
                str(base_task)
                + "\n\n"
                "============================================================\n"
                "TARGETED SEMANTIC REPAIR MODE\n"
                "============================================================\n"
                f"Revision round: {round_number}\n"
                f"ONLY AUTHORIZED REPAIR FILE: {target_path}\n\n"
                "The file below is part of an unapproved candidate plan. "
                "Do not read the live workspace as the source of truth for "
                "this file; the CURRENT REJECTED CONTENT below is the exact "
                "version you must repair.\n\n"
                "MANDATORY RULES:\n"
                "1. Return a plan containing EXACTLY ONE file.\n"
                f"2. That file MUST be {target_path}.\n"
                "3. Return the complete corrected contents for that file.\n"
                "4. Resolve every machine finding below with executable code.\n"
                "5. Preserve unrelated behavior in this file.\n"
                "6. Do not create, rename, or modify any other file.\n"
                "7. A print statement does not satisfy a return requirement.\n"
                "8. If return behavior is required, place a real non-empty "
                "return statement inside callable behavior.\n"
                "9. Do not answer with commentary instead of corrected code.\n\n"
                "MACHINE FINDINGS:\n"
                + finding_text
                + "\n\n"
                "CURRENT REJECTED CONTENT:\n"
                "--- BEGIN FILE ---\n"
                + current_content
                + "\n--- END FILE ---\n"
                "============================================================\n"
                "Return the corrected one-file implementation plan."
            )

            repair_source = current_content
            repair_findings = relevant

            for repair_attempt in range(
                1,
                3,
            ):
                repair_finding_text = (
                    "\n".join(
                        "- " + finding.format()
                        for finding in repair_findings
                    )
                    or (
                        "- Deterministic semantic "
                        "repair required."
                    )
                )

                print(
                    "FORGE TARGETED REPAIR ATTEMPT: "
                    f"{repair_attempt}/2 | "
                    + target_path
                )

                repair_plan = (
                    self.forge
                    .create_targeted_repair_plan(
                        task=str(base_task),
                        target_path=target_path,
                        current_content=repair_source,
                        finding_text=repair_finding_text,
                        task_id=task_id,
                    )
                )

                if repair_plan is None:
                    print(
                        "PAT TARGETED REPAIR EXHAUSTED: "
                        + target_path
                    )

                    # All bounded repair attempts failed the
                    # deterministic self-check. Preserve the
                    # original rejected candidate unchanged so
                    # the existing fingerprint/stall guard can
                    # reject it cleanly. Never dereference None
                    # and never write an unvalidated repair.
                    return candidate

                repaired_change = (
                    self._plan_change_by_path(
                        repair_plan,
                        target_path,
                    )
                )

                if repaired_change is None:
                    raise ValueError(
                        "FORGE targeted repair did not "
                        "return the authorized file."
                    )

                repaired_content = str(
                    getattr(
                        repaired_change,
                        "content",
                        "",
                    )
                )

                if repaired_content == repair_source:
                    raise ValueError(
                        "FORGE targeted repair returned "
                        "unchanged source while findings "
                        "remain unresolved."
                    )

                trial_candidate = (
                    self._merge_targeted_repair(
                        rejected_plan=candidate,
                        repair_plan=repair_plan,
                        target_path=target_path,
                    )
                )

                trial_findings = (
                    validate_plan_semantics(
                        trial_candidate,
                        workspace,
                    )
                )

                residual_findings = [
                    finding
                    for finding in trial_findings
                    if (
                        self._normalize_path(
                            getattr(
                                finding,
                                "path",
                                "",
                            )
                        )
                        == target_path
                    )
                ]

                if not residual_findings:
                    candidate = trial_candidate

                    print(
                        "PAT TARGETED REPAIR SELF-CHECK: "
                        "PASS | "
                        + target_path
                    )
                    print(
                        "PAT TARGETED REPAIR ACCEPTED"
                    )
                    return repair_plan

                    break

                print(
                    "PAT TARGETED REPAIR SELF-CHECK: "
                    f"FAIL | {len(residual_findings)}"
                )

                for finding in residual_findings:
                    print(
                        "PAT TARGETED REPAIR FINDING: "
                        + finding.format()
                    )

                candidate = trial_candidate

                if repair_attempt >= 2:
                    break

                repair_source = repaired_content
                repair_findings = residual_findings

            if repair_plan is None:
                print(
                    "PAT TARGETED REPAIR LOOP EXHAUSTED: "
                    + target_path
                )

                # Every bounded repair attempt failed deterministic
                # self-check. Do not dereference, merge, fingerprint,
                # or otherwise treat None as a plan. Preserve the
                # rejected in-memory candidate so the caller's normal
                # unchanged-plan / fail-closed handling can reject it.
                return candidate


    def _forge_revision_snapshot(
        self,
        plan,
    ):
        """
        Return a bounded snapshot of the rejected proposal.

        This is prompt context only. It never writes the proposal to the
        workspace.
        """

        lines = []
        budget = 12000

        for change in getattr(
            plan,
            "files",
            [],
        ):
            path = str(
                getattr(
                    change,
                    "path",
                    "",
                )
            )

            content = str(
                getattr(
                    change,
                    "content",
                    "",
                )
            )

            block = (
                "\nFILE: "
                + path
                + "\n--- BEGIN REJECTED CONTENT ---\n"
                + content
                + "\n--- END REJECTED CONTENT ---\n"
            )

            if len(
                "\n".join(
                    lines
                )
            ) + len(block) > budget:
                remaining = max(
                    0,
                    budget
                    - len(
                        "\n".join(
                            lines
                        )
                    ),
                )

                if remaining > 200:
                    lines.append(
                        block[:remaining]
                        + "\n[REJECTED SNAPSHOT TRUNCATED]\n"
                    )

                break

            lines.append(
                block
            )

        return "".join(
            lines
        )


    def _forge_revision_task(
        self,
        *,
        base_task,
        feedback,
        rejected_plan,
        round_number,
    ):
        """
        Promote rejection feedback into FORGE's primary task instruction.

        The rejected proposal is included so FORGE can patch the failing
        version instead of regenerating from an unchanged workspace.
        """

        if not feedback:
            return base_task

        snapshot = (
            self._forge_revision_snapshot(
                rejected_plan
            )
            if rejected_plan is not None
            else ""
        )

        return (
            str(base_task)
            + "\n\n"
            "============================================================\n"
            "MANDATORY FORGE REVISION CONTRACT\n"
            "============================================================\n"
            f"Revision round: {round_number}\n\n"
            "The previous proposal was REJECTED. "
            "The feedback below is a required implementation constraint, "
            "not optional review advice.\n\n"
            "REVISION RULES:\n"
            "1. You MUST change the proposed file contents so every listed "
            "blocking finding is actually resolved.\n"
            "2. Do NOT return the same implementation again.\n"
            "3. Start from the rejected contents below and preserve behavior "
            "that was not identified as failing.\n"
            "4. Change only the user-authorized file paths.\n"
            "5. Do not merely add comments, notes, print statements, or "
            "explanations when the finding requires executable behavior.\n"
            "6. If a requirement says a file RETURNS a value, implement "
            "callable behavior with a real non-empty `return` statement. "
            "Printing the value is not equivalent to returning it.\n"
            "7. If a semantic finding says a symbol is unresolved, import or "
            "define that symbol in the module that uses it.\n"
            "8. If a class is called with constructor arguments, ensure that "
            "the class actually supports those arguments, for example through "
            "a valid __init__ or an active dataclass-style decorator.\n"
            "9. Before responding, compare your new file contents against the "
            "rejected snapshot and verify the blocking finding is no longer "
            "true.\n\n"
            "MANDATORY BLOCKING FEEDBACK:\n"
            + str(feedback)
            + "\n\n"
            "REJECTED PROPOSAL SNAPSHOT:\n"
            + (
                snapshot
                or "[snapshot unavailable]"
            )
            + "\n============================================================\n"
            "Return the corrected implementation plan now."
        )


    def _maybe_force_atomic_rollback_test(
        self,
        changed_files,
    ):
        """
        Test-only failure injection used to prove WorkspaceTransaction
        rollback after files have already been written.

        Safety rules:
        - disabled unless PAT_TEST_FORCE_ROLLBACK_AFTER_APPLY == "1"
        - every changed file must be under forge_lab/rollback_test/
        - otherwise the armed hook refuses to fire
        """

        enabled = (
            os.environ.get(
                "PAT_TEST_FORCE_ROLLBACK_AFTER_APPLY",
                "",
            ).strip()
            == "1"
        )

        if not enabled:
            return

        normalized = [
            self._normalize_path(
                str(path)
            )
            for path in (
                changed_files
                or []
            )
        ]

        safe_prefix = (
            "forge_lab/rollback_test/"
        )

        safe_scope = (
            bool(normalized)
            and all(
                path.startswith(
                    safe_prefix
                )
                for path in normalized
            )
        )

        if not safe_scope:
            print(
                "PAT ROLLBACK TEST HOOK: "
                "ARMED BUT SCOPE REFUSED"
            )
            return

        print(
            "PAT ROLLBACK TEST HOOK: "
            "FORCING FAILURE AFTER APPLY"
        )

        raise RuntimeError(
            "PAT TEST FAULT: forced rollback "
            "after all approved files were applied"
        )


    def _sentinel_severity_calibration(
        self,
    ):
        """
        Return PAT's reviewer severity rubric.

        This changes review calibration only. It does not change the
        deterministic severity -> status enforcement policy.
        """

        return (
            "\n\nPAT REVIEW SEVERITY CALIBRATION:\n"
            "- MEDIUM means a concrete, nontrivial correctness, security, "
            "or reliability defect that must be fixed before approval.\n"
            "- A maintainability concern by itself is normally LOW or INFO "
            "unless it causes a concrete present failure, a material "
            "reliability problem, or violates an explicit user requirement.\n"
            "- Reduced future reusability, mockability, extensibility, or "
            "test convenience is not MEDIUM by itself.\n"
            "- Direct orchestration in a demo/example function is expected. "
            "A demo may instantiate services, create sample objects, call "
            "the reporting function, and return the result. Dependency "
            "injection is optional unless the task explicitly requires "
            "reuse, substitution, mocking, or test isolation.\n"
            "- A small service directly constructing a simple in-memory "
            "storage dependency is LOW/INFO unless the task requires "
            "pluggable storage or the coupling causes a concrete defect.\n"
            "- Missing extra unit tests is INFO unless tests were explicitly "
            "required or the proposal cannot otherwise be meaningfully "
            "validated.\n"
            "- A recommendation phrased as 'consider', 'could', 'would "
            "improve', 'future', 'more reusable', or 'easier to test' is "
            "normally LOW/INFO unless a concrete current failure is shown.\n"
            "- Do not assign MEDIUM solely because another abstraction, "
            "module, interface, dependency injection layer, entry point, "
            "or test file could be added.\n"
            "- If you state that the code is correct, secure, reliable, "
            "fulfills the task, and is ready for approval, do not also "
            "assign MEDIUM unless you clearly identify the concrete defect "
            "that makes approval unsafe or incorrect.\n"
            "- Do not downgrade a genuine defect merely to make the review "
            "self-consistent. Keep MEDIUM/HIGH when the concrete defect "
            "really must be corrected before approval.\n"
        )


    def _reconcile_sentinel_review(
        self,
        sentinel_result,
        policy,
        workspace,
        task_id,
        files,
        stage,
    ):
        """
        Re-review the exact same proposal once when
        SENTINEL's final approval contradicts its own
        MEDIUM/HIGH finding.

        CRITICAL findings never enter this path.
        """

        if not getattr(
            policy,
            "needs_reconciliation",
            False,
        ):
            return (
                sentinel_result,
                policy,
            )

        print(
            "SENTINEL REVIEW CONSISTENCY CHECK: "
            f"{policy.model_status} + "
            f"{policy.highest_severity}"
        )

        previous_review = (
            sentinel_result.content
            or ""
        )

        request = (
            "REVIEW CONSISTENCY RECHECK.\n\n"
            "Re-review the EXACT SAME proposal bundle. "
            "Do not ask FORGE to change code yet.\n\n"
            f"STAGE: {stage}\n"
            f"PREVIOUS FINAL STATUS: "
            f"{policy.model_status}\n"
            f"PREVIOUS HIGHEST SEVERITY: "
            f"{policy.highest_severity}\n\n"
            "PAT SEVERITY CONTRACT:\n"
            "- CRITICAL: catastrophic or unsafe defect; BLOCKED.\n"
            "- HIGH: concrete serious defect that must be fixed "
            "before approval.\n"
            "- MEDIUM: concrete nontrivial correctness, security, "
            "or reliability defect that must be fixed before approval.\n"
            "- LOW: real but non-blocking weakness.\n"
            "- INFO: optional hardening, future improvement, style, "
            "extra coverage, or advisory recommendation.\n\n"
            "CALIBRATION RULES:\n"
            "- Do not label optional hardening MEDIUM merely because "
            "the code could be more granular or defensive.\n"
            "- 'Consider', 'could', 'future', or 'would improve' "
            "language is normally LOW/INFO unless you identify a "
            "specific failure introduced by this proposal.\n"
            "- Missing extra unit tests is INFO unless tests were "
            "explicitly required or the change cannot otherwise be "
            "meaningfully validated.\n"
            "- Do not downgrade a real defect merely to match the "
            "previous final decision.\n"
            "- Keep HIGH/MEDIUM only when a concrete defect must be "
            "corrected before approval.\n"
            "- Return a self-consistent FINAL DECISION.\n\n"
            "STRUCTURAL ERROR-BOUNDARY CALIBRATION:\n"
            "- The public function MUST keep its original public name "
            "(for example route_command). Renaming that wrapper to "
            "route_command_wrapper would be a compatibility regression, "
            "not a maintainability improvement.\n"
            "- A private implementation name such as "
            "_forge_impl_route_command is intentional separation of "
            "implementation from the stable public API. Treat that "
            "architecture as valid unless it causes a concrete defect.\n"
            "- Generic user-facing failure text is acceptable and often "
            "preferred when logger.exception() already records the active "
            "exception type, message, and traceback for developers. "
            "Do not require str(error), traceback text, command contents, "
            "or other internals in the user-facing response merely for "
            "debugging convenience.\n"
            "- If logger.exception() exists inside the active exception "
            "handler, do not call the user-facing message a MEDIUM defect "
            "solely because it is generic. Identify a concrete debugging "
            "failure first.\n"
            "- Additional exception granularity is INFO/LOW when the "
            "proposal already has specific handlers plus a final "
            "Exception application boundary, unless a concrete exception "
            "needs materially different recovery behavior.\n"
            "- Module-level logging configuration may be provided by the "
            "application entry point. Lack of local basicConfig() is INFO "
            "unless this diff demonstrably prevents required logging.\n"
            + self._sentinel_severity_calibration()
            + "\nPREVIOUS REVIEW:\n"
            + previous_review[:8000]
        )

        reconciled_result = (
            self.sentinel.review(
                request=request,
                workspace=workspace,
                task_id=task_id,
                files=files,
                focus=[
                    "correctness",
                    "security",
                    "reliability",
                    "architecture",
                    "maintainability",
                ],
            )
        )

        reconciled_policy = (
            enforce_review_policy(
                model_status=(
                    reconciled_result
                    .status_hint
                ),
                review_text=(
                    reconciled_result
                    .content
                ),
            )
        )

        print(
            "SENTINEL REVIEW CONSISTENCY RESULT: "
            f"{reconciled_policy.effective_status}"
        )

        if (
            reconciled_policy
            .needs_reconciliation
        ):
            print(
                "SENTINEL REVIEW STILL INCONSISTENT; "
                "PAT WILL FAIL CLOSED USING THE "
                "STRICTER POLICY RESULT."
            )

        return (
            reconciled_result,
            reconciled_policy,
        )

    def _propose_existing_project_task(
        self,
        task,
        workspace,
        task_id=None,
    ):
        workspace_path = (
            Path(workspace)
            .expanduser()
            .resolve()
        )

        if task_id is None:
            task_id = (
                self.forge.new_task_id()
            )

        requested_paths = (
            self._extract_requested_paths(
                task
            )
        )

        scope_error = (
            self._validate_requested_file_scope(
                requested_paths
            )
        )

        if scope_error:
            return self._simple_result(
                (
                    "FORGE SAFE MULTI-FILE SCOPE REJECTED\n\n"
                    f"Task: {task_id}\n\n"
                    f"{scope_error}\n\n"
                    "NO FILES WERE MODIFIED."
                ),
                success=False,
                task_id=task_id,
            )

        exact_requested_snippets = (
            self._extract_exact_requested_snippets(
                task
            )
        )

        scoped_task = task

        if requested_paths:
            scoped_task += (
                "\n\nSTRICT FILE SCOPE:\n"
                "The user explicitly named these files:\n"
                + "\n".join(
                    f"- {path}"
                    for path in requested_paths
                )
                + "\n\n"
                "You may ONLY modify those exact files. "
                "Do not create or modify any other files. "
                "This file scope is a USER AUTHORIZATION BOUNDARY. "
                "It outranks architecture suggestions, reviewer feedback, "
                "or implementation convenience."
            )

        if len(requested_paths) > 1:
            scoped_task += (
                "\n\nSAFE MULTI-FILE PHASE 1 CONTRACT:\n"
                f"- Maximum files: {SAFE_MULTI_FILE_MAX_FILES}\n"
                "- Python files only.\n"
                "- Return complete final contents for each file "
                "you actually need to create or update.\n"
                "- Keep imports, function names, classes, and interfaces "
                "consistent across all proposed files.\n"
                "- Do not add package-install commands, dependency changes, "
                "generated binaries, or unrelated files.\n"
                "- You may use a subset of the explicit file scope, "
                "but you may never add another path.\n"
                "- SENTINEL feedback does NOT grant permission to add files.\n"
                "- If reviewer feedback recommends a new file, entry point, "
                "test file, helper module, config file, or package file, "
                "address the underlying concern only inside the explicit "
                "user-named paths.\n"
                "- If a reviewer request cannot be satisfied without "
                "expanding scope, preserve the scope and explain that "
                "constraint in plan notes instead of inventing another path."
            )

        acceptance_criteria = (
            self._extract_acceptance_criteria(
                task
            )
        )

        print(
            "PAT ACCEPTANCE CRITERIA: "
            f"{len(acceptance_criteria)}"
        )

        sentinel_feedback = None
        rejected_fingerprint = None
        rejected_plan = None
        semantic_repair_findings = None
        final_plan = None
        final_policy = None
        final_review = None
        final_requirement_coverage = None
        final_semantic_preflight = None
        final_diff_previews = None

        # ==================================================
        # FORGE <-> SENTINEL PRE-APPROVAL LOOP
        # ==================================================

        for pre_round in range(
            1,
            self.max_pre_review_rounds + 1,
        ):
            base_generation_task = (
                task
                if len(requested_paths) == 1
                else scoped_task
            )

            generation_task = (
                self._forge_revision_task(
                    base_task=base_generation_task,
                    feedback=sentinel_feedback,
                    rejected_plan=rejected_plan,
                    round_number=pre_round,
                )
            )

            try:
                if (
                    semantic_repair_findings
                    and rejected_plan is not None
                ):
                    print(
                        "FORGE TARGETED REPAIR MODE: "
                        f"ROUND {pre_round}"
                    )

                    plan = (
                        self._targeted_semantic_repair(
                            rejected_plan=rejected_plan,
                            semantic_findings=(
                                semantic_repair_findings
                            ),
                            requested_paths=requested_paths,
                            base_task=base_generation_task,
                            workspace=workspace_path,
                            task_id=task_id,
                            round_number=pre_round,
                        )
                    )

                    if plan is None:
                        print(
                            "PAT TARGETED REPAIR FAILED CLOSED: "
                            "no validated repair plan was produced"
                        )

                        return self._simple_result(
                            (
                                "FORGE TARGETED REPAIR EXHAUSTED\n\n"
                                f"Task: {task_id}\n\n"
                                "All bounded targeted repair attempts failed "
                                "deterministic validation. PAT refused to "
                                "treat a missing repair as an implementation "
                                "plan.\n\n"
                                "NO FILES WERE MODIFIED.\n"
                                "NO APPROVAL WAS CREATED."
                            ),
                            success=False,
                            task_id=task_id,
                        )

                    # Consume the repair request. If semantic validation
                    # still fails below, fresh findings will replace it.
                    semantic_repair_findings = None

                else:
                    if sentinel_feedback:
                        print(
                            "FORGE MANDATORY REVISION CONTRACT: "
                            f"ROUND {pre_round}"
                        )

                    if len(requested_paths) == 1:
                        plan = (
                            self.forge
                            .create_single_file_plan(
                                task=generation_task,
                                workspace=workspace_path,
                                task_id=task_id,
                                target_path=requested_paths[0],
                                sentinel_feedback=sentinel_feedback,
                            )
                        )
                    else:
                        plan = (
                            self.forge
                            .create_implementation_plan(
                                task=generation_task,
                                workspace=workspace_path,
                                task_id=task_id,
                                sentinel_feedback=sentinel_feedback,
                                allowed_paths=(
                                    requested_paths
                                    or None
                                ),
                            )
                        )

            except Exception as exc:
                try:
                    self.forge.logger.exception(
                        "FORGE pre-approval plan generation failed "
                        "for %s on round %s",
                        task_id,
                        pre_round,
                    )
                except Exception:
                    pass

                return self._simple_result(
                    (
                        "FORGE PRE-APPROVAL GENERATION FAILED\n\n"
                        f"Task: {task_id}\n"
                        f"Round: {pre_round}\n\n"
                        f"{type(exc).__name__}: {exc}\n\n"
                        "NO FILES WERE MODIFIED.\n"
                        "NO APPROVAL WAS CREATED.\n\n"
                        "The FORGE/SENTINEL console remains usable; "
                        "retry the task after resolving the generation "
                        "failure."
                    ),
                    success=False,
                    task_id=task_id,
                )

            plan_scope_error = (
                self._validate_proposed_plan_scope(
                    plan=plan,
                    requested_paths=requested_paths,
                )
            )

            if plan_scope_error:
                return self._simple_result(
                    (
                        "FORGE PROPOSAL REJECTED\n\n"
                        f"Task: {task_id}\n\n"
                        f"{plan_scope_error}\n\n"
                        "NO FILES WERE MODIFIED.\n"
                        "NO APPROVAL WAS CREATED."
                    ),
                    success=False,
                    task_id=task_id,
                )

            current_fingerprint = (
                self._plan_fingerprint(
                    plan
                )
            )

            if (
                rejected_fingerprint is not None
                and current_fingerprint
                == rejected_fingerprint
            ):
                return self._simple_result(
                    (
                        "FORGE REVISION STALLED\n\n"
                        f"Task: {task_id}\n\n"
                        "PAT/SENTINEL previously required changes, "
                        "but FORGE returned the exact same file "
                        "contents again.\n\n"
                        "PAT refused to send an unchanged proposal "
                        "forward because the mandatory revision "
                        "contract was not implemented.\n\n"
                        "NO FILES WERE MODIFIED.\n"
                        "NO APPROVAL WAS CREATED.\n\n"
                        "LATEST SENTINEL FEEDBACK:\n"
                        + (
                            sentinel_feedback
                            or "No feedback available."
                        )
                    ),
                    success=False,
                    task_id=task_id,
                )

            if requested_paths:
                allowed_paths = {
                    self._normalize_path(path)
                    for path in requested_paths
                }

                proposed_paths = {
                    self._normalize_path(
                        change.path
                    )
                    for change in plan.files
                }

                unauthorized_paths = (
                    proposed_paths
                    - allowed_paths
                )

                if unauthorized_paths:
                    return self._simple_result(
                        (
                            "FORGE PROPOSAL REJECTED\n\n"
                            "FORGE attempted to modify files "
                            "outside the user's requested scope.\n\n"
                            "Allowed files:\n"
                            + "\n".join(
                                f"- {path}"
                                for path in sorted(
                                    allowed_paths
                                )
                            )
                            + "\n\nRejected files:\n"
                            + "\n".join(
                                f"- {path}"
                                for path in sorted(
                                    unauthorized_paths
                                )
                            )
                            + "\n\n"
                            "No files were modified."
                        ),
                        success=False,
                        task_id=task_id,
                    )

            diff_previews = (
                build_plan_diff_previews(
                    workspace=workspace_path,
                    changes=plan.files,
                )
            )

            if any(
                preview.truncated
                for preview in diff_previews
            ):
                return self._simple_result(
                    (
                        "FORGE PROPOSAL REJECTED\n\n"
                        "The proposed diff is too large "
                        "to preview safely.\n\n"
                        "No files were modified.\n\n"
                        "Ask FORGE for a smaller change."
                    ),
                    success=False,
                    task_id=task_id,
                )

            bundle = (
                build_proposal_review_bundle(
                    pat_root=self.pat_root,
                    workspace=workspace_path,
                    task_id=task_id,
                    task=task,
                    plan=plan,
                    context_lines=30,
                )
            )

            preflight_failed = any(
                not check.success
                for check in bundle.checks
            )

            semantic_findings = (
                validate_plan_semantics(
                    plan=plan,
                    workspace=workspace_path,
                    acceptance_criteria=(
                        acceptance_criteria
                    ),
                )
            )

            if semantic_findings:
                print(
                    "PAT SEMANTIC PREFLIGHT: FAIL | "
                    f"{len(semantic_findings)}"
                )

                for finding in semantic_findings:
                    print(
                        "PAT SEMANTIC FINDING: "
                        + finding.format()
                    )

                if (
                    exact_requested_snippets
                    and self._plan_contains_exact_snippets(
                        plan,
                        exact_requested_snippets,
                    )
                ):
                    return self._simple_result(
                        (
                            "FORGE EXACT-REQUEST CONFLICT\n\n"
                            f"Task: {task_id}\n\n"
                            "PAT's deterministic semantic preflight "
                            "found a concrete problem in a proposal "
                            "containing literal code you explicitly "
                            "requested. PAT will not silently rewrite "
                            "that literal code.\n\n"
                            "SEMANTIC FINDINGS:\n"
                            + "\n".join(
                                "- " + finding.format()
                                for finding in semantic_findings
                            )
                            + "\n\nNO FILES WERE MODIFIED.\n"
                            "NO APPROVAL WAS CREATED."
                        ),
                        success=False,
                        task_id=task_id,
                    )

                if pre_round >= self.max_pre_review_rounds:
                    return self._simple_result(
                        (
                            "FORGE PROPOSAL REJECTED\n\n"
                            f"Task: {task_id}\n\n"
                            "PAT deterministic semantic preflight "
                            "still fails after "
                            f"{self.max_pre_review_rounds} proposal rounds.\n\n"
                            "SEMANTIC FINDINGS:\n"
                            + "\n".join(
                                "- " + finding.format()
                                for finding in semantic_findings
                            )
                            + "\n\nNO FILES WERE MODIFIED.\n"
                            "NO APPROVAL WAS CREATED."
                        ),
                        success=False,
                        task_id=task_id,
                    )

                rejected_fingerprint = current_fingerprint
                rejected_plan = plan
                semantic_repair_findings = (
                    semantic_findings
                )
                sentinel_feedback = (
                    "PAT DETERMINISTIC SEMANTIC PREFLIGHT FAILED.\n"
                    "These are machine-derived Python semantic findings, "
                    "not optional reviewer suggestions. Correct them "
                    "before SENTINEL review:\n"
                    + "\n".join(
                        "- " + finding.format()
                        for finding in semantic_findings
                    )
                )

                if requested_paths:
                    sentinel_feedback += (
                        "\n\nNON-NEGOTIABLE REVISION SCOPE LOCK:\n"
                        "The user's explicitly authorized file paths are:\n"
                        + "\n".join(
                            f"- {path}"
                            for path in requested_paths
                        )
                        + "\n\nDo not add any other path while "
                        "correcting the semantic findings."
                    )

                continue

            print("PAT SEMANTIC PREFLIGHT: PASS")
            semantic_preflight_summary = (
                "PASS: deterministic non-executing Python semantic checks"
            )

            review_request = (
                "Perform a PRE-APPROVAL review of the attached "
                "FORGE proposal bundle. No target project files "
                "have been modified yet. Review the exact proposed "
                "diff and preflight validation results. Determine "
                "whether this proposal should be allowed to reach "
                "the user's approve/deny gate."
                + self._sentinel_severity_calibration()
                + self._acceptance_criteria_contract(
                    acceptance_criteria
                )
            )

            sentinel_result = (
                self.sentinel.review(
                    request=review_request,
                    workspace=bundle.bundle_path.parent,
                    task_id=task_id,
                    files=[
                        bundle.bundle_path.name
                    ],
                    focus=[
                        "correctness",
                        "security",
                        "reliability",
                        "architecture",
                        "maintainability",
                    ],
                )
            )

            policy = enforce_review_policy(
                model_status=(
                    sentinel_result.status_hint
                ),
                review_text=(
                    sentinel_result.content
                ),
            )
            sentinel_result, policy = (
                self._reconcile_sentinel_review(
                    sentinel_result=sentinel_result,
                    policy=policy,
                    workspace=(
                        bundle.bundle_path.parent
                    ),
                    task_id=task_id,
                    files=[
                        bundle.bundle_path.name
                    ],
                    stage="PRE-APPROVAL",
                )
            )


            (
                requirement_review_text,
                requirement_failures,
                requirement_lines,
                requirement_error,
            ) = self._requirement_coverage_recheck(
                sentinel_result=sentinel_result,
                criteria=acceptance_criteria,
                workspace=bundle.bundle_path.parent,
                task_id=task_id,
                files=[
                    bundle.bundle_path.name
                ],
            )

            if requirement_error:
                return self._simple_result(
                    (
                        "FORGE PROPOSAL REJECTED\n\n"
                        f"Task: {task_id}\n\n"
                        "SENTINEL REQUIREMENT COVERAGE INVALID\n\n"
                        f"{requirement_error}\n\n"
                        "PAT could not verify that every explicit user "
                        "requirement was checked.\n\n"
                        "NO FILES WERE MODIFIED.\n"
                        "NO APPROVAL WAS CREATED.\n\n"
                        "LATEST REQUIREMENT REVIEW:\n"
                        + requirement_review_text
                    ),
                    success=False,
                    task_id=task_id,
                )

            status = (
                policy.effective_status
            )

            if requirement_failures:
                status = "CHANGES_REQUIRED"

                print(
                    "PAT REQUIREMENT GATE: FAIL | "
                    + ", ".join(
                        f"R{number}"
                        for number in requirement_failures
                    )
                )
            else:
                print(
                    "PAT REQUIREMENT GATE: PASS"
                )

            if (
                preflight_failed
                and status != "BLOCKED"
            ):
                status = "CHANGES_REQUIRED"

            print(
                f"SENTINEL PRE-REVIEW: {status} | "
                f"ROUND: {pre_round}"
            )

            if policy.policy_overrode_model:
                print(
                    "SENTINEL POLICY OVERRIDE: "
                    f"{policy.model_status} -> "
                    f"{policy.effective_status}"
                )

            final_plan = plan
            final_policy = policy
            final_review = sentinel_result
            final_requirement_coverage = (
                requirement_review_text
            )
            final_semantic_preflight = (
                semantic_preflight_summary
            )
            final_diff_previews = diff_previews

            if status in {
                "APPROVED",
                "APPROVED_WITH_NOTES",
            }:
                break

            if status == "BLOCKED":
                return self._simple_result(
                    (
                        "FORGE PROPOSAL BLOCKED BY SENTINEL\n\n"
                        f"Task: {task_id}\n\n"
                        "NO FILES WERE MODIFIED.\n\n"
                        "SENTINEL REVIEW:\n"
                        + sentinel_result.content
                    ),
                    success=False,
                    task_id=task_id,
                )

            # If the user explicitly supplied literal code to insert,
            # and the rejected proposal contains that exact code, FORGE
            # must not silently mutate the user's literal instruction just
            # to satisfy SENTINEL. Stop before another LLM revision round.
            if (
                status == "CHANGES_REQUIRED"
                and exact_requested_snippets
                and self._plan_contains_exact_snippets(
                    plan,
                    exact_requested_snippets,
                )
            ):
                requested_block = "\n".join(
                    f"- {snippet}"
                    for snippet
                    in exact_requested_snippets
                )

                return self._simple_result(
                    (
                        "FORGE EXACT-REQUEST CONFLICT\n\n"
                        f"Task: {task_id}\n\n"
                        "SENTINEL requires changes to a proposal "
                        "that contains literal code you explicitly "
                        "requested.\n\n"
                        "EXACT USER-SPECIFIED CODE:\n"
                        f"{requested_block}\n\n"
                        "PAT will not let FORGE silently rewrite "
                        "that literal instruction or repeatedly "
                        "resubmit the same code seeking a different "
                        "review outcome.\n\n"
                        "NO FILES WERE MODIFIED.\n"
                        "NO APPROVAL WAS CREATED.\n\n"
                        "SENTINEL REVIEW:\n"
                        + sentinel_result.content
                    ),
                    success=False,
                    task_id=task_id,
                )

            if (
                pre_round
                >= self.max_pre_review_rounds
            ):
                return self._simple_result(
                    (
                        "FORGE PROPOSAL REJECTED\n\n"
                        "SENTINEL still requires changes after "
                        f"{self.max_pre_review_rounds} pre-review rounds.\n\n"
                        "NO FILES WERE MODIFIED.\n\n"
                        "LATEST SENTINEL REVIEW:\n"
                        + sentinel_result.content
                    ),
                    success=False,
                    task_id=task_id,
                )

            rejected_fingerprint = (
                current_fingerprint
            )
            rejected_plan = plan
            semantic_repair_findings = None

            sentinel_feedback = (
                sentinel_result.content
            )

            if requirement_review_text:
                sentinel_feedback += (
                    "\n\nMANDATORY USER REQUIREMENT COVERAGE:\n"
                    + requirement_review_text
                )

            if requirement_failures:
                sentinel_feedback += (
                    "\n\nPAT REQUIREMENT GATE FAILURE:\n"
                    "The following explicit user requirements are not "
                    "satisfied and MUST be corrected inside the existing "
                    "authorized file scope:\n"
                    + "\n".join(
                        f"- R{number}: "
                        f"{acceptance_criteria[number - 1]}"
                        for number in requirement_failures
                    )
                )

            if requested_paths:
                sentinel_feedback += (
                    "\n\n"
                    "NON-NEGOTIABLE REVISION SCOPE LOCK:\n"
                    "The user's explicitly authorized file paths are:\n"
                    + "\n".join(
                        f"- {path}"
                        for path in requested_paths
                    )
                    + "\n\n"
                    "AUTHORITY RULES:\n"
                    "1. The user file scope outranks SENTINEL feedback.\n"
                    "2. SENTINEL feedback is advisory about code quality; "
                    "it does not authorize a new file path.\n"
                    "3. Do not add main.py, __init__.py, tests, helpers, "
                    "configs, entry points, or any other path unless it is "
                    "already in the authorized list above.\n"
                    "4. Resolve valid findings only by revising the "
                    "authorized files.\n"
                    "5. If a finding cannot be resolved inside that scope, "
                    "keep the scope unchanged and state the limitation in "
                    "the plan notes.\n"
                    "6. Returning any unauthorized path is a failed plan."
                )

        if (
            final_plan is None
            or final_review is None
            or final_policy is None
            or final_requirement_coverage is None
            or final_semantic_preflight is None
            or final_diff_previews is None
        ):
            return self._simple_result(
                "FORGE pre-approval review did not produce a usable proposal.",
                success=False,
                task_id=task_id,
            )

        effective_status = (
            final_policy.effective_status
        )

        pending = (
            self.approvals.create(
                task_id=task_id,
                task=task,
                workspace=workspace_path,
                plan=final_plan,
                metadata={
                    "existing_project": True,
                    "sentinel_pre_review_status": (
                        effective_status
                    ),
                    "sentinel_pre_review": (
                        final_review.content
                    ),
                    "acceptance_criteria": (
                        acceptance_criteria
                    ),
                    "requirement_coverage": (
                        final_requirement_coverage
                    ),
                    "semantic_preflight": (
                        final_semantic_preflight
                    ),
                    "safe_multi_file_phase": (
                        1
                        if len(final_plan.files) > 1
                        else 0
                    ),
                    "approved_file_count": len(
                        final_plan.files
                    ),
                },
            )
        )

        lines = [
            "FORGE CHANGE PROPOSAL",
            "",
            f"Task: {task_id}",
            f"Approval: {pending.approval_id}",
            f"Workspace: {workspace_path}",
            "",
            (
                "SENTINEL PRE-REVIEW: "
                f"{effective_status}"
            ),
            "",
            (
                f"Summary: "
                f"{final_plan.summary or 'No summary provided.'}"
            ),
            "",
        ]

        if acceptance_criteria:
            lines.extend([
                "MANDATORY ACCEPTANCE CRITERIA:",
            ])

            for index, criterion in enumerate(
                acceptance_criteria,
                start=1,
            ):
                lines.append(
                    f"- R{index}: {criterion}"
                )

            lines.extend([
                "",
                "PAT REQUIREMENT GATE: PASS",
                "PAT SEMANTIC PREFLIGHT: PASS",
                "",
            ])

        if len(final_plan.files) > 1:
            lines.extend([
                "SAFE MULTI-FILE MODE: PHASE 1",
                (
                    "File count: "
                    f"{len(final_plan.files)}/"
                    f"{SAFE_MULTI_FILE_MAX_FILES}"
                ),
                "Scope: EXPLICIT USER-NAMED PYTHON FILES",
                "Approval lock: ENTIRE MULTI-FILE PLAN",
                "",
            ])

        lines.append(
            "FILES FORGE WANTS TO MODIFY:"
        )

        for change in final_plan.files:
            target = (
                workspace_path
                / change.path
            )

            operation = (
                "update"
                if target.exists()
                else "create"
            )

            lines.append(
                f"- {change.path} ({operation})"
            )

        lines.extend([
            "",
            "PROPOSED DIFF:",
        ])

        for preview in final_diff_previews:
            lines.extend([
                "",
                f"FILE: {preview.path}",
                (
                    f"Changes: "
                    f"+{preview.added_lines} "
                    f"-{preview.removed_lines}"
                ),
                "",
                preview.diff,
            ])

        if effective_status == "APPROVED_WITH_NOTES":
            lines.extend([
                "",
                "SENTINEL PRE-REVIEW NOTES:",
                final_review.content,
            ])

        lines.extend([
            "",
            "NO FILES HAVE BEEN MODIFIED.",
            "",
            "This exact SENTINEL-reviewed plan is now locked.",
            "",
            "Type:",
            "approve forge changes",
            "",
            "or:",
            "deny forge changes",
        ])

        forge_result = ForgeResult(
            task_id=task_id,
            content="\n".join(lines),
        )

        return {
            "forge": forge_result,
            "sentinel": final_review,
            "reviews": [
                final_review
            ],
            "review_rounds": 0,
            "approved": False,
            "status": "AWAITING_APPROVAL",
            "approval_required": True,
            "approval_id": pending.approval_id,
            "workspace": str(
                workspace_path
            ),
            "files": list(
                pending.approved_paths
            ),
            "pre_review_status": (
                effective_status
            ),
            "success": True,
        }

    # ==================================================
    # APPROVED EXISTING-PROJECT EXECUTION
    # ==================================================

    def _execute_approved_task(
        self,
        pending: PendingApproval,
    ):
        """
        Apply the exact user-approved plan once.

        Post-approval review is immutable:
        SENTINEL may approve the exact applied bytes or cause a rollback,
        but FORGE is never allowed to revise the live transaction after
        the human approval gate.
        """

        pre_status = (
            pending.metadata.get(
                "sentinel_pre_review_status"
            )
        )

        if pre_status not in {
            "APPROVED",
            "APPROVED_WITH_NOTES",
        }:
            return self._simple_result(
                (
                    "FORGE APPROVAL REFUSED\n\n"
                    "This pending plan does not have a valid "
                    "SENTINEL pre-approval review."
                ),
                success=False,
                task_id=pending.task_id,
            )

        workspace_path = Path(
            pending.workspace
        )

        approved_paths = tuple(
            pending.approved_paths
        )

        locked_semantic_findings = (
            validate_plan_semantics(
                plan=pending.plan,
                workspace=workspace_path,
                acceptance_criteria=(
                    pending.metadata.get(
                        "acceptance_criteria",
                        [],
                    )
                ),
            )
        )

        if locked_semantic_findings:
            return self._simple_result(
                (
                    "FORGE APPROVAL REFUSED\n\n"
                    f"Task: {pending.task_id}\n\n"
                    "The exact locked plan failed deterministic "
                    "semantic validation before any transaction write.\n\n"
                    "SEMANTIC FINDINGS:\n"
                    + "\n".join(
                        "- " + finding.format()
                        for finding in locked_semantic_findings
                    )
                    + "\n\nNO FILES WERE MODIFIED."
                ),
                success=False,
                task_id=pending.task_id,
            )

        transaction = (
            WorkspaceTransaction(
                workspace=workspace_path,
                task_id=pending.task_id,
                approved_paths=approved_paths,
                metadata={
                    "summary": pending.plan.summary,
                    "approval_id": pending.approval_id,
                    "task": pending.task,
                    "post_approval_mode": (
                        "IMMUTABLE_EXACT_PLAN"
                    ),
                },
            )
        )

        transaction.begin()

        reviews = []
        checks: list[CheckResult] = []
        plan = pending.plan
        applied = []

        approved_plan_scope_error = (
            self._validate_proposed_plan_scope(
                plan=plan,
                requested_paths=list(
                    pending.approved_paths
                ),
            )
        )

        if approved_plan_scope_error:
            return self._simple_result(
                (
                    "FORGE APPROVAL REFUSED\n\n"
                    "The locked plan failed the Safe Multi-File "
                    "scope invariant before any transaction write.\n\n"
                    f"{approved_plan_scope_error}"
                ),
                success=False,
                task_id=pending.task_id,
            )

        try:
            requested_paths = [
                change.path
                for change in plan.files
            ]

            # Human approval locks scope and exact plan.
            transaction.assert_scope(
                requested_paths
            )

            tools = ForgeTools(
                workspace_path,
                create=False,
            )

            # CRITICAL INVARIANT:
            # Apply the exact pending.plan once.
            # There is deliberately no FORGE generation/revision path
            # anywhere after this point.
            applied = (
                tools.apply_changes(
                    changes=plan.files,
                    task_id=pending.task_id,
                )
            )

            changed_files = [
                item["path"]
                for item in applied
            ]

            # TEST-ONLY ATOMIC ROLLBACK FAULT INJECTION.
            #
            # This runs only when explicitly armed by an environment
            # variable and only for forge_lab/rollback_test/* paths.
            # The exception is intentionally raised AFTER all approved
            # files were written so the surrounding exception handler
            # must restore the complete transaction.
            self._maybe_force_atomic_rollback_test(
                changed_files
            )

            runner = (
                SafePythonRunner(
                    workspace_path
                )
            )

            checks = runner.compile_files(
                changed_files
            )

            # Existing-project unit tests are NOT run automatically.
            # Test code can execute arbitrary project behavior and needs
            # a separate explicit execution gate.
            compile_failed = any(
                not check.success
                for check in checks
            )

            review_bundle = build_review_bundle(
                transaction=transaction,
                task=pending.task,
                summary=plan.summary,
                checks=checks,
                context_lines=30,
            )

            review_request = (
                "POST-APPLY IMMUTABLE REVIEW.\n\n"
                "Review the attached transaction review bundle. "
                "The user already approved this exact plan. "
                "PAT applied it exactly once. "
                "No revision is permitted in this transaction. "
                "Use the included diff, surrounding source context, "
                "hashes, and validation results as the source of truth. "
                "Your decision must be one of: keep the exact applied "
                "state, or require rollback. "
                "Do not request FORGE to revise the live workspace."
                + self._sentinel_severity_calibration()
            )

            sentinel_result = (
                self.sentinel.review(
                    request=review_request,
                    workspace=(
                        transaction.transaction_root
                    ),
                    task_id=pending.task_id,
                    files=[
                        "review_bundle.txt"
                    ],
                    focus=[
                        "correctness",
                        "security",
                        "reliability",
                        "architecture",
                        "maintainability",
                    ],
                )
            )

            reviews.append(
                sentinel_result
            )

            policy = enforce_review_policy(
                model_status=(
                    sentinel_result.status_hint
                ),
                review_text=(
                    sentinel_result.content
                ),
            )

            sentinel_result, policy = (
                self._reconcile_sentinel_review(
                    sentinel_result=sentinel_result,
                    policy=policy,
                    workspace=(
                        transaction.transaction_root
                    ),
                    task_id=pending.task_id,
                    files=[
                        "review_bundle.txt"
                    ],
                    stage="POST-APPLY",
                )
            )

            reviews[-1] = sentinel_result

            status = (
                policy.effective_status
            )

            if (
                policy.policy_overrode_model
            ):
                print(
                    "SENTINEL POLICY OVERRIDE: "
                    f"{policy.model_status} -> "
                    f"{policy.effective_status}"
                )

            # Compile failure can never be committed, regardless of
            # model wording.
            if (
                compile_failed
                and status != "BLOCKED"
            ):
                status = "CHANGES_REQUIRED"

            print(
                "SENTINEL POST-APPLY STATUS: "
                f"{status} | IMMUTABLE EXACT PLAN"
            )

            if status in {
                "APPROVED",
                "APPROVED_WITH_NOTES",
            }:
                transaction.commit()

                return (
                    self._build_execution_result(
                        pending=pending,
                        plan=plan,
                        applied=applied,
                        checks=checks,
                        reviews=reviews,
                        status=status,
                        kept=True,
                        transaction=transaction,
                    )
                )

            # Any non-approval after application means the exact
            # approved transaction is rolled back. No in-place repair.
            transaction.rollback()

            return (
                self._build_execution_result(
                    pending=pending,
                    plan=plan,
                    applied=applied,
                    checks=checks,
                    reviews=reviews,
                    status=status,
                    kept=False,
                    transaction=transaction,
                )
            )

        except Exception as exc:
            transaction.rollback()

            return self._simple_result(
                (
                    "FORGE EXISTING-PROJECT CHANGE FAILED\n\n"
                    f"Task: {pending.task_id}\n"
                    f"Error: {exc}\n\n"
                    "Original files were restored.\n"
                    f"Recovery snapshot: "
                    f"{transaction.recovery_location()}"
                ),
                success=False,
                task_id=pending.task_id,
            )

    # ==================================================
    # ISOLATED GENERIC PROJECTS - v1.5 BEHAVIOR
    # ==================================================

    def _run_isolated_task(
        self,
        task,
        workspace=None,
    ):
        task_id = (
            self.forge.new_task_id()
        )

        if workspace is None:
            workspace_path = (
                self.generated_root
                / task_id
            )

            workspace_path.mkdir(
                parents=True,
                exist_ok=True,
            )
        else:
            workspace_path = (
                Path(workspace)
                .expanduser()
                .resolve()
            )

        reviews = []
        checks: list[CheckResult] = []
        sentinel_feedback = None
        final_plan = None
        final_applied = []

        for review_round in range(
            1,
            self.max_review_rounds + 1,
        ):
            plan = (
                self.forge
                .create_implementation_plan(
                    task=task,
                    workspace=workspace_path,
                    task_id=task_id,
                    sentinel_feedback=sentinel_feedback,
                )
            )

            final_plan = plan

            tools = ForgeTools(
                workspace_path,
                create=True,
            )

            applied = tools.apply_changes(
                changes=plan.files,
                task_id=task_id,
            )

            final_applied = applied

            changed_files = [
                item["path"]
                for item in applied
            ]

            runner = SafePythonRunner(
                workspace_path
            )

            checks = runner.compile_files(
                changed_files
            )

            validation_failed = any(
                not check.success
                for check in checks
            )

            if plan.run_tests:
                checks.append(
                    runner.run_unittests()
                )

            review_request = (
                "Review FORGE's REAL implementation "
                "in the supplied isolated workspace.\n\n"
                f"ORIGINAL TASK:\n{task}\n\n"
                f"FORGE SUMMARY:\n{plan.summary}\n\n"
                "FILES CHANGED:\n"
                + (
                    "\n".join(
                        f"- {path}"
                        for path in changed_files
                    )
                    or "- None"
                )
                + self._sentinel_severity_calibration()
            )

            sentinel_result = (
                self.sentinel.review(
                    request=review_request,
                    workspace=workspace_path,
                    task_id=task_id,
                    files=changed_files or None,
                    focus=[
                        "correctness",
                        "security",
                        "reliability",
                        "architecture",
                        "maintainability",
                    ],
                )
            )

            reviews.append(
                sentinel_result
            )

            status = (
                sentinel_result.status_hint
            )
            if validation_failed:
                status = "CHANGES_REQUIRED"

            print(
                f"SENTINEL STATUS: {status} | "
                f"REVIEW: {review_round}"
            )

            if status in {
                "APPROVED",
                "APPROVED_WITH_NOTES",
            }:
                break

            if status not in {
                "CHANGES_REQUIRED",
                "BLOCKED",
            }:
                break

            if status == "BLOCKED":
                break

            if (
                review_round
                >= self.max_review_rounds
            ):
                break

            sentinel_feedback = (
                sentinel_result.content
            )

        final_review = (
            reviews[-1]
            if reviews
            else None
        )

        final_status = (
            final_review.status_hint
            if final_review
            else None
        )

        approved = (
            final_status
            in {
                "APPROVED",
                "APPROVED_WITH_NOTES",
            }
        )

        if final_plan is None:
            raise RuntimeError(
                "FORGE did not produce an implementation plan."
            )

        forge_result = (
            self.forge
            .build_completion_result(
                task_id=task_id,
                workspace=workspace_path,
                plan=final_plan,
                applied=final_applied,
                checks=checks,
                sentinel_status=final_status,
                review_rounds=len(reviews),
            )
        )

        return {
            "forge": forge_result,
            "sentinel": final_review,
            "reviews": reviews,
            "review_rounds": len(reviews),
            "approved": approved,
            "status": final_status,
            "workspace": str(
                workspace_path
            ),
            "files": [
                item["path"]
                for item in final_applied
            ],
            "checks": checks,
            "success": approved,
        }

    # ==================================================
    # RESULT BUILDERS
    # ==================================================

    def _build_execution_result(
        self,
        pending,
        plan,
        applied,
        checks,
        reviews,
        status,
        kept,
        transaction,
    ):
        lines = [
            (
                "FORGE EXISTING-PROJECT CHANGE COMPLETE"
                if kept
                else "FORGE EXISTING-PROJECT CHANGE ROLLED BACK"
            ),
            "",
            f"Task: {pending.task_id}",
            f"Workspace: {pending.workspace}",
            "",
            f"Summary: {plan.summary or 'Implementation processed.'}",
            "",
            "FILES:",
        ]

        for item in applied:
            lines.append(
                f"- {item['path']} ({item['operation']})"
            )

        if not applied:
            lines.append(
                "- No files changed."
            )

        lines.extend([
            "",
            "VALIDATION:",
        ])

        if checks:
            for check in checks:
                state = (
                    "PASS"
                    if check.success
                    else "FAIL"
                )

                lines.append(
                    f"- {state}: {check.name}"
                )

                if not check.success:
                    lines.append(
                        f"  {check.output}"
                    )
        else:
            lines.append(
                "- No validation checks were run."
            )

        lines.extend([
            "",
            "SENTINEL:",
            f"- Status: {status}",
            f"- Review rounds: {len(reviews)}",
            "",
            (
                "RESULT: CHANGES KEPT"
                if kept
                else "RESULT: ORIGINAL FILES RESTORED"
            ),
            (
                "Recovery snapshot: "
                f"{transaction.recovery_location()}"
            ),
        ])

        if reviews:
            lines.extend([
                "",
                "SENTINEL REVIEW:",
                reviews[-1].content,
            ])

        forge_result = ForgeResult(
            task_id=pending.task_id,
            content="\n".join(lines),
        )

        return {
            "forge": forge_result,
            "sentinel": (
                reviews[-1]
                if reviews
                else None
            ),
            "reviews": reviews,
            "review_rounds": len(reviews),
            "approved": kept,
            "status": status,
            "workspace": pending.workspace,
            "files": [
                item["path"]
                for item in applied
            ],
            "checks": checks,
            "rolled_back": not kept,
            "success": kept,
        }

    def _simple_result(
        self,
        content,
        success,
        task_id=None,
    ):
        selected_task_id = (
            task_id
            or "TASK-NONE"
        )

        return {
            "forge": ForgeResult(
                task_id=selected_task_id,
                content=content,
            ),
            "sentinel": None,
            "reviews": [],
            "review_rounds": 0,
            "approved": False,
            "status": None,
            "success": success,
        }

    # ==================================================
    # MANUAL REVIEW - KEEP EXISTING CAPABILITY
    # ==================================================

    def review_task(
        self,
        task_id,
        workspace,
        files,
        summary,
    ):
        review_request = (
            self.forge
            .request_sentinel_review(
                task_id=task_id,
                files_changed=files,
                summary=summary,
            )
        )

        return self.sentinel.review(
            request=review_request.content,
            workspace=workspace,
            task_id=task_id,
            files=files,
            focus=(
                review_request
                .metadata
                .get("focus")
            ),
        )

    def show_forge_history(
        self,
        limit=10,
    ):
        items = self.history.list(
            limit=limit,
        )

        if not items:
            return self._simple_result(
                "FORGE HISTORY\n\nNo transactions found.",
                success=True,
            )

        lines = [
            "FORGE HISTORY",
            "",
        ]

        for item in items:
            lines.append(
                f"{item.task_id} | {item.status} | v{item.manifest_version}"
            )

            if item.summary:
                lines.append(
                    f"  {item.summary}"
                )

            if item.paths:
                lines.append(
                    "  Files: "
                    + ", ".join(item.paths)
                )

            if item.committed_at:
                lines.append(
                    f"  Committed: {item.committed_at}"
                )
            elif item.created_at:
                lines.append(
                    f"  Created: {item.created_at}"
                )

            if item.undone_at:
                lines.append(
                    f"  Undone: {item.undone_at}"
                )

            lines.append("")

        lines.extend([
            "Undo a v1.8 committed transaction with:",
            "undo forge TASK-XXXXXXXX",
        ])

        return self._simple_result(
            "\n".join(lines),
            success=True,
        )


    def undo_forge_change(
        self,
        task_id,
    ):
        undo_result = self.history.undo(
            task_id
        )

        if not undo_result.success:
            return self._simple_result(
                (
                    "FORGE UNDO REFUSED\n\n"
                    f"Task: {undo_result.task_id}\n\n"
                    f"{undo_result.message}"
                ),
                success=False,
                task_id=undo_result.task_id,
            )

        restored_python = [
            path
            for path in undo_result.restored_paths
            if path.lower().endswith(".py")
        ]

        checks = []

        if restored_python and undo_result.workspace:
            runner = SafePythonRunner(
                undo_result.workspace
            )
            checks = runner.compile_files(
                restored_python
            )

        lines = [
            "FORGE UNDO COMPLETE",
            "",
            f"Task: {undo_result.task_id}",
            "",
            "RESTORED:",
        ]

        for path in undo_result.restored_paths:
            lines.append(
                f"- {path}"
            )

        lines.extend([
            "",
            "VALIDATION:",
        ])

        if checks:
            for check in checks:
                state = (
                    "PASS"
                    if check.success
                    else "FAIL"
                )
                lines.append(
                    f"- {state}: {check.name}"
                )
                if not check.success:
                    lines.append(
                        f"  {check.output}"
                    )
        else:
            lines.append(
                "- No Python files required compilation."
            )

        lines.extend([
            "",
            "RESULT: TRANSACTION UNDONE",
        ])

        success = (
            all(check.success for check in checks)
            if checks
            else True
        )

        return self._simple_result(
            "\n".join(lines),
            success=success,
            task_id=undo_result.task_id,
        )