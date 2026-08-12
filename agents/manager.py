from __future__ import annotations
import ast
import hashlib
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

        elif workspace is None:
            require_approval = False

        elif require_approval is None:
            require_approval = True

        if require_approval:
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
            "unless this diff demonstrably prevents required logging.\n\n"
            "PREVIOUS REVIEW:\n"
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
    ):
        workspace_path = (
            Path(workspace)
            .expanduser()
            .resolve()
        )

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

        sentinel_feedback = None
        rejected_fingerprint = None
        final_plan = None
        final_policy = None
        final_review = None
        final_diff_previews = None

        # ==================================================
        # FORGE <-> SENTINEL PRE-APPROVAL LOOP
        # ==================================================

        for pre_round in range(
            1,
            self.max_pre_review_rounds + 1,
        ):
            try:
                if len(requested_paths) == 1:
                    plan = (
                        self.forge
                        .create_single_file_plan(
                            task=task,
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
                            task=scoped_task,
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
                        "SENTINEL previously required changes, "
                        "but FORGE returned the exact same file "
                        "contents again.\n\n"
                        "PAT refused to send an unchanged proposal "
                        "back through SENTINEL merely to seek a "
                        "different review outcome.\n\n"
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

            review_request = (
                "Perform a PRE-APPROVAL review of the attached "
                "FORGE proposal bundle. No target project files "
                "have been modified yet. Review the exact proposed "
                "diff and preflight validation results. Determine "
                "whether this proposal should be allowed to reach "
                "the user's approve/deny gate."
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


            status = (
                policy.effective_status
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

            sentinel_feedback = (
                sentinel_result.content
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