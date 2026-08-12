from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import re
import textwrap


STRUCTURAL_EDIT_SYSTEM_PROMPT = """You are FORGE in restricted structural-edit mode.
PAT already selected and locked the real Python function using AST.
Your only job is to return concise exception handler clauses.
Return only SUMMARY and HANDLERS tags. Do not rewrite functions, emit patches, explain reasoning, or claim tests ran.
Never use bare except. Preserve the stated return contract.
PAT mechanically adds logging.exception(...) to every handler, so do not add traceback/logging code yourself.
PAT also guarantees a final Exception fallback for the verified RouteResult boundary if you omit one.
Specific handlers should only be used when they provide genuinely different recovery behavior.
Keep the response under 30 lines."""


class StructuralEditError(RuntimeError):
    """Raised when a structural edit cannot be proven safe."""


@dataclass(frozen=True)
class FunctionTarget:
    target_id: str
    name: str
    implementation_name: str
    lineno: int
    end_lineno: int
    is_async: bool
    call_expression: str
    docstring: str | None
    source_excerpt: str


@dataclass(frozen=True)
class StructuralProposal:
    summary: str
    content: str
    target_id: str
    operation: str = "wrap_function_error_handling"


class PythonStructuralEditor:
    """
    Trusted AST-based Python structural editor.

    FORGE v2.0 phase 1 supports one narrow structural operation:
    add error handling around a module-level function without
    rewriting/reindenting the original function body.
    """

    ERROR_CUES = (
        "error handling",
        "exception handling",
        "handle errors",
        "handle error",
        "handle exceptions",
        "handle exception",
        "try/except",
        "try except",
        "catch errors",
        "catch exceptions",
    )

    def __init__(
        self,
        source: str,
        path: str = "<memory>",
    ):
        self.source = source
        self.path = path

        try:
            self.tree = ast.parse(
                source,
                filename=path,
            )
        except SyntaxError as exc:
            raise StructuralEditError(
                f"Cannot structurally edit invalid Python: {exc}"
            ) from exc

        self.lines = source.splitlines(keepends=True)

        self._module_functions = [
            node
            for node in self.tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
        ]

        self._top_level_names = {
            node.name
            for node in self.tree.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            )
        }

    def supports_task(
        self,
        task: str,
    ) -> bool:
        lowered = task.lower()

        return any(
            cue in lowered
            for cue in self.ERROR_CUES
        )

    def resolve_target(
        self,
        task: str,
    ) -> FunctionTarget | None:
        if not self.supports_task(task):
            return None

        matches = []

        for node in self._module_functions:
            if re.search(
                (
                    rf"(?<![A-Za-z0-9_])"
                    rf"{re.escape(node.name)}"
                    rf"(?![A-Za-z0-9_])"
                ),
                task,
                flags=re.IGNORECASE,
            ):
                matches.append(node)

        if not matches:
            return None

        names = {
            node.name
            for node in matches
        }

        if len(names) != 1:
            raise StructuralEditError(
                "Structural edit request names more than one function: "
                + ", ".join(sorted(names))
            )

        return self._build_target(matches[0])

    def _build_target(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> FunctionTarget:
        if node.decorator_list:
            raise StructuralEditError(
                "FORGE v2.0 phase 1 refuses decorated "
                f"function {node.name!r}."
            )

        for child in ast.walk(node):
            if (
                isinstance(child, ast.Name)
                and isinstance(child.ctx, ast.Load)
                and child.id == node.name
            ):
                raise StructuralEditError(
                    "FORGE v2.0 phase 1 refuses "
                    f"self-referential function {node.name!r}."
                )

        if not node.body:
            raise StructuralEditError(
                f"Function {node.name!r} has no body."
            )

        implementation_name = (
            f"_forge_impl_{node.name}"
        )

        if implementation_name in self._top_level_names:
            digest = sha256(
                self._function_source(node).encode("utf-8")
            ).hexdigest()[:8]

            implementation_name = (
                f"_forge_impl_{node.name}_{digest}"
            )

        call_expression = self._build_call_expression(
            node,
            implementation_name,
        )

        function_lines = (
            self._function_source(node).splitlines()
        )

        # Compact structural context. The LLM only chooses handlers.
        excerpt_lines = function_lines[:12]

        return_examples = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Return):
                continue

            if child.value is None:
                item = "return"
            else:
                value = (
                    ast.get_source_segment(self.source, child.value)
                    or ast.unparse(child.value)
                )
                item = "return " + " ".join(value.split())

            if item not in return_examples:
                return_examples.append(item[:400])

            if len(return_examples) >= 6:
                break

        if return_examples:
            excerpt_lines.extend([
                "",
                "REPRESENTATIVE RETURNS:",
                *[f"- {item}" for item in return_examples],
            ])

        handled = []
        for child in ast.walk(node):
            if not isinstance(child, ast.ExceptHandler):
                continue

            if child.type is None:
                item = "<bare except>"
            else:
                item = (
                    ast.get_source_segment(self.source, child.type)
                    or ast.unparse(child.type)
                )

            if item not in handled:
                handled.append(item)

            if len(handled) >= 6:
                break

        if handled:
            excerpt_lines.extend([
                "",
                "EXCEPTION TYPES ALREADY HANDLED:",
                *[f"- {item}" for item in handled],
            ])

        return FunctionTarget(
            target_id=(
                f"FUNCTION:{node.name}:"
                f"{node.lineno}-{node.end_lineno}"
            ),
            name=node.name,
            implementation_name=implementation_name,
            lineno=node.lineno,
            end_lineno=node.end_lineno or node.lineno,
            is_async=isinstance(
                node,
                ast.AsyncFunctionDef,
            ),
            call_expression=call_expression,
            docstring=ast.get_docstring(
                node,
                clean=True,
            ),
            source_excerpt="\n".join(excerpt_lines),
        )

    def _function_source(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str:
        return "".join(
            self.lines[
                node.lineno - 1:
                (
                    node.end_lineno
                    or node.lineno
                )
            ]
        )

    @staticmethod
    def _build_call_expression(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        implementation_name: str,
    ) -> str:
        args = []

        for arg in [
            *node.args.posonlyargs,
            *node.args.args,
        ]:
            args.append(arg.arg)

        if node.args.vararg is not None:
            args.append(
                f"*{node.args.vararg.arg}"
            )

        for arg in node.args.kwonlyargs:
            args.append(
                f"{arg.arg}={arg.arg}"
            )

        if node.args.kwarg is not None:
            args.append(
                f"**{node.args.kwarg.arg}"
            )

        call = (
            f"{implementation_name}"
            f"({', '.join(args)})"
        )

        if isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            call = f"await {call}"

        return call

    @staticmethod
    def _compact_sentinel_feedback(
        feedback: str,
        max_chars: int = 1400,
    ) -> str:
        """
        Keep only actionable review material for structural revisions.

        The full SENTINEL report is useful for audit/history, but FORGE
        only needs the specific severity/problem/recommendation lines
        required to repair the handler.
        """

        if not feedback:
            return ""

        selected = []

        patterns = (
            "status:",
            "severity:",
            "problem:",
            "recommendation:",
            "final decision",
        )

        for raw_line in feedback.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            normalized = (
                line
                .replace("**", "")
                .strip()
                .lower()
            )

            if (
                any(
                    normalized.startswith(prefix)
                    for prefix in patterns
                )
                or normalized.startswith("- status:")
                or normalized.startswith("- severity:")
                or normalized.startswith("- problem:")
                or normalized.startswith("- recommendation:")
            ):
                cleaned = (
                    line
                    .replace("**", "")
                    .strip()
                )

                if cleaned not in selected:
                    selected.append(cleaned)

        if not selected:
            compact = feedback[:max_chars]
        else:
            compact = "\n".join(selected)

        return compact[:max_chars]


    def build_handler_prompt(
        self,
        task: str,
        target: FunctionTarget,
        sentinel_feedback: str | None = None,
    ) -> str:
        feedback = ""

        if sentinel_feedback:
            compact_feedback = (
                self._compact_sentinel_feedback(
                    sentinel_feedback
                )
            )

            feedback = (
                "\nSENTINEL ACTIONABLE FEEDBACK:\n"
                f"{compact_feedback}\n"
            )

        prompt = f"""TASK:
{task}

LOCKED TARGET: {target.target_id}
PUBLIC FUNCTION: {target.name}
PAT WRAPPER CALL: {target.call_expression}

PAT keeps the original implementation body unchanged and only places your HANDLERS after its try block.

VERIFIED COMPACT CONTEXT:
{target.source_excerpt[:6000]}
{feedback}
RETURN EXACTLY:
<SUMMARY>one short sentence</SUMMARY>
<HANDLERS>
except SpecificException as error:
    ...concise handler preserving the return contract...
</HANDLERS>

Rules: except clauses only; no try/def/class/else/finally; no bare except; no markdown; under 30 lines.
PAT adds logging.exception with traceback automatically. Do not add logging code.
PAT guarantees a final generic Exception fallback for verified RouteResult routing boundaries.
Use specific exception handlers only when they need a distinct recovery response.
Do not expose a traceback or private command contents in the user-facing response.
"""

        if len(prompt) > 7000:
            raise StructuralEditError(
                "Structural prompt exceeded the v2.0.2 safe limit."
            )

        return prompt

    def apply_handler_response(
        self,
        target: FunctionTarget,
        response: str,
    ) -> StructuralProposal:
        summary = (
            self._extract_tag(
                response,
                "SUMMARY",
            )
            or (
                "Add error handling "
                f"wrapper for {target.name}"
            )
        )

        handlers = self._extract_tag(
            response,
            "HANDLERS",
        )

        if not handlers:
            raise StructuralEditError(
                "FORGE did not return <HANDLERS> "
                "for structural edit."
            )

        handlers = self._strip_code_fence(
            textwrap.dedent(
                handlers
            ).strip("\n")
        )

        self._validate_handlers(
            handlers
        )

        handlers = (
            self._ensure_terminal_exception_handler(
                handlers=handlers,
                target=target,
            )
        )

        handlers = (
            self._instrument_handlers(
                handlers=handlers,
                target=target,
            )
        )

        node = self._node_for_target(
            target
        )

        renamed_source = (
            self._rename_function_header(
                node,
                target.implementation_name,
            )
        )

        wrapper_source = (
            self._build_wrapper_source(
                node,
                target,
                handlers,
            )
        )

        before = "".join(
            self.lines[
                :node.lineno - 1
            ]
        )

        after = "".join(
            self.lines[
                (
                    node.end_lineno
                    or node.lineno
                ):
            ]
        )

        candidate = (
            before
            + renamed_source
        )

        if not candidate.endswith("\n"):
            candidate += "\n"

        candidate += (
            "\n\n"
            + wrapper_source.rstrip()
            + "\n"
        )

        if after:
            candidate += (
                "\n"
                + after.lstrip("\n")
            )

        candidate = (
            self._ensure_logging_support(
                candidate
            )
        )

        try:
            compile(
                candidate,
                self.path,
                "exec",
            )
        except SyntaxError as exc:
            raise StructuralEditError(
                "Structural proposal failed "
                f"in-memory compilation: {exc}"
            ) from exc

        return StructuralProposal(
            summary=summary.strip(),
            content=candidate,
            target_id=target.target_id,
        )

    @staticmethod
    def _handler_catches_exception(
        handler: ast.ExceptHandler,
    ) -> bool:
        """
        Return True only when this handler catches Exception
        (directly or inside a tuple). BaseException is not
        treated as an acceptable application boundary.
        """

        if handler.type is None:
            return False

        if (
            isinstance(
                handler.type,
                ast.Name,
            )
            and handler.type.id
            == "Exception"
        ):
            return True

        if isinstance(
            handler.type,
            ast.Tuple,
        ):
            for item in handler.type.elts:
                if (
                    isinstance(
                        item,
                        ast.Name,
                    )
                    and item.id
                    == "Exception"
                ):
                    return True

        return False


    def _ensure_terminal_exception_handler(
        self,
        handlers: str,
        target: FunctionTarget,
    ) -> str:
        """
        Guarantee a final last-resort Exception boundary.

        Specific FORGE handlers remain first. PAT adds the final
        fallback only when FORGE omitted it.

        Phase 1 currently knows how to construct a safe fallback
        for RouteResult-returning routing functions. Unknown return
        contracts are refused rather than guessed.
        """

        probe = (
            "def __forge_probe__():\n"
            "    try:\n"
            "        pass\n"
            + textwrap.indent(
                handlers,
                "    ",
            )
            + "\n"
        )

        tree = ast.parse(
            probe
        )

        function = tree.body[0]
        try_node = function.body[0]

        if any(
            self._handler_catches_exception(
                handler
            )
            for handler in try_node.handlers
        ):
            return handlers

        # route_command's trusted AST signature has a
        # RouteResult return annotation. Do not generalize this
        # fallback to unknown return contracts.
        target_node = (
            self._node_for_target(
                target
            )
        )

        return_annotation = (
            ast.unparse(
                target_node.returns
            )
            if target_node.returns
            is not None
            else None
        )

        if return_annotation != "RouteResult":
            raise StructuralEditError(
                "FORGE structural handler omitted a final "
                "Exception boundary, and PAT cannot safely "
                "construct a fallback for return type "
                f"{return_annotation!r}."
            )

        fallback = ast.ExceptHandler(
            type=ast.Name(
                id="Exception",
                ctx=ast.Load(),
            ),
            name="error",
            body=[
                ast.Return(
                    value=ast.Call(
                        func=ast.Name(
                            id="RouteResult",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[
                            ast.keyword(
                                arg="intent",
                                value=ast.Attribute(
                                    value=ast.Name(
                                        id="Intent",
                                        ctx=ast.Load(),
                                    ),
                                    attr="GENERAL_AI",
                                    ctx=ast.Load(),
                                ),
                            ),
                            ast.keyword(
                                arg="response",
                                value=ast.Constant(
                                    value=(
                                        "PAT encountered an "
                                        "unexpected routing error."
                                    )
                                ),
                            ),
                            ast.keyword(
                                arg="success",
                                value=ast.Constant(
                                    value=False
                                ),
                            ),
                        ],
                    )
                )
            ],
        )

        try_node.handlers.append(
            fallback
        )

        ast.fix_missing_locations(
            tree
        )

        rendered = ast.unparse(
            try_node
        ).splitlines()

        except_index = None

        for index, line in enumerate(
            rendered
        ):
            if line.startswith(
                "except "
            ):
                except_index = index
                break

        if except_index is None:
            raise StructuralEditError(
                "PAT could not reconstruct "
                "terminal exception handlers."
            )

        return "\n".join(
            rendered[
                except_index:
            ]
        )


    @staticmethod
    def _handler_has_exception_logging(
        handler: ast.ExceptHandler,
    ) -> bool:
        for node in ast.walk(handler):
            if not isinstance(
                node,
                ast.Call,
            ):
                continue

            func = node.func

            if not (
                isinstance(
                    func,
                    ast.Attribute,
                )
                and func.attr == "exception"
                and isinstance(
                    func.value,
                    ast.Name,
                )
            ):
                continue

            if func.value.id in {
                "logger",
                "logging",
            }:
                return True

        return False


    def _instrument_handlers(
        self,
        handlers: str,
        target: FunctionTarget,
    ) -> str:
        """
        Mechanically add traceback-preserving diagnostics.

        logging.exception() records the active exception type,
        message, and traceback without exposing the traceback
        in PAT's user-facing response.

        The module-level logging convenience function delegates to
        the root logger and ensures a basic handler exists when the
        application has not configured logging yet.
        """

        probe = (
            "def __forge_probe__():\n"
            "    try:\n"
            "        pass\n"
            + textwrap.indent(
                handlers,
                "    ",
            )
            + "\n"
        )

        tree = ast.parse(
            probe
        )

        function = tree.body[0]
        try_node = function.body[0]

        for handler in try_node.handlers:
            if self._handler_has_exception_logging(
                handler
            ):
                continue

            log_call = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(
                            id="logging",
                            ctx=ast.Load(),
                        ),
                        attr="exception",
                        ctx=ast.Load(),
                    ),
                    args=[
                        ast.Constant(
                            value=(
                                "Unhandled exception at "
                                f"{target.name} boundary"
                            )
                        )
                    ],
                    keywords=[],
                )
            )

            handler.body.insert(
                0,
                log_call,
            )

        ast.fix_missing_locations(
            tree
        )

        rendered = ast.unparse(
            try_node
        ).splitlines()

        except_index = None

        for index, line in enumerate(
            rendered
        ):
            if line.startswith(
                "except "
            ):
                except_index = index
                break

        if except_index is None:
            raise StructuralEditError(
                "PAT could not reconstruct "
                "instrumented exception handlers."
            )

        return "\n".join(
            rendered[
                except_index:
            ]
        )


    @staticmethod
    def _ensure_logging_support(
        source: str,
    ) -> str:
        """
        Ensure:
            import logging

        Structural handlers use logging.exception(), which logs
        through the root logger. No module-local logger or local
        basicConfig() call is required in the target module.
        """

        tree = ast.parse(
            source
        )

        has_logging_import = False

        for node in tree.body:
            if not isinstance(
                node,
                ast.Import,
            ):
                continue

            if any(
                alias.name == "logging"
                for alias in node.names
            ):
                has_logging_import = True
                break

        if has_logging_import:
            return source

        lines = source.splitlines(
            keepends=True
        )

        future_end = 0

        for node in tree.body:
            if (
                isinstance(
                    node,
                    ast.ImportFrom,
                )
                and node.module
                == "__future__"
            ):
                future_end = max(
                    future_end,
                    node.end_lineno
                    or node.lineno,
                )

        lines.insert(
            future_end,
            "import logging\n",
        )

        return "".join(
            lines
        )


    def _node_for_target(
        self,
        target: FunctionTarget,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        for node in self._module_functions:
            if (
                node.name == target.name
                and node.lineno == target.lineno
                and (
                    node.end_lineno
                    or node.lineno
                )
                == target.end_lineno
            ):
                return node

        raise StructuralEditError(
            "Trusted structural target no "
            "longer matches parsed source."
        )

    def _rename_function_header(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        implementation_name: str,
    ) -> str:
        function_source = self._function_source(
            node
        )

        header_line_count = (
            node.body[0].lineno
            - node.lineno
        )

        if header_line_count <= 0:
            raise StructuralEditError(
                "Unable to identify function header."
            )

        parts = function_source.splitlines(
            keepends=True
        )

        header = "".join(
            parts[:header_line_count]
        )

        body = "".join(
            parts[header_line_count:]
        )

        if isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            pattern = (
                rf"\basync\s+def\s+"
                rf"{re.escape(node.name)}\b"
            )
            replacement = (
                "async def "
                f"{implementation_name}"
            )
        else:
            pattern = (
                rf"\bdef\s+"
                rf"{re.escape(node.name)}\b"
            )
            replacement = (
                f"def {implementation_name}"
            )

        renamed_header, count = re.subn(
            pattern,
            replacement,
            header,
            count=1,
        )

        if count != 1:
            raise StructuralEditError(
                "Could not safely rename "
                "trusted function header."
            )

        return (
            renamed_header
            + body
        )

    def _build_wrapper_source(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        target: FunctionTarget,
        handlers: str,
    ) -> str:
        header_line_count = (
            node.body[0].lineno
            - node.lineno
        )

        function_source = self._function_source(
            node
        )

        parts = function_source.splitlines(
            keepends=True
        )

        header = "".join(
            parts[:header_line_count]
        ).rstrip("\n")

        body_lines = []

        # The renamed implementation keeps the original function body
        # and therefore keeps the original docstring. The public wrapper
        # gets an explicit architectural docstring so reviewers and
        # maintainers can immediately see why both functions exist.
        wrapper_docstring = [
            (
                "Public error-handling boundary for "
                f"`{target.name}`."
            ),
            "",
            (
                "Delegates normal routing behavior to "
                f"`{target.implementation_name}`, which contains "
                "the original implementation, while preserving "
                f"`{target.name}` as the stable public API."
            ),
            (
                "Boundary handlers log exception diagnostics and "
                "return safe failure results without exposing "
                "internal traceback details to callers."
            ),
        ]

        body_lines.append(
            '    """'
        )

        for doc_line in (
            wrapper_docstring
        ):
            body_lines.append(
                (
                    "    " + doc_line
                    if doc_line
                    else "    "
                )
            )

        body_lines.append(
            '    """'
        )

        body_lines.extend([
            "    try:",
            (
                "        return "
                + target.call_expression
            ),
        ])

        for line in handlers.splitlines():
            body_lines.append(
                (
                    "    " + line
                    if line
                    else ""
                )
            )

        return (
            header
            + "\n"
            + "\n".join(body_lines)
        )

    @staticmethod
    def _extract_tag(
        text: str,
        tag: str,
    ) -> str | None:
        match = re.search(
            (
                rf"<{tag}>"
                rf"(.*?)"
                rf"</{tag}>"
            ),
            text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if not match:
            return None

        return (
            match.group(1)
            .strip()
        )

    @staticmethod
    def _strip_code_fence(
        text: str,
    ) -> str:
        text = re.sub(
            r"^```(?:python)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        return text.strip("\n")

    @staticmethod
    def _validate_handlers(
        handlers: str,
    ) -> None:
        if not re.match(
            r"^except\b",
            handlers.lstrip(),
        ):
            raise StructuralEditError(
                "Structural handler block must "
                "begin with an except clause."
            )

        probe = (
            "def __forge_probe__():\n"
            "    try:\n"
            "        pass\n"
            + textwrap.indent(
                handlers,
                "    ",
            )
            + "\n"
        )

        try:
            tree = ast.parse(
                probe
            )
        except SyntaxError as exc:
            raise StructuralEditError(
                "Invalid exception handler "
                f"syntax: {exc}"
            ) from exc

        function = tree.body[0]

        if not isinstance(
            function,
            ast.FunctionDef,
        ):
            raise StructuralEditError(
                "Handler validation failed."
            )

        if (
            len(function.body) != 1
            or not isinstance(
                function.body[0],
                ast.Try,
            )
        ):
            raise StructuralEditError(
                "Handler response contains "
                "statements outside the "
                "except clauses."
            )

        try_node = function.body[0]

        if not try_node.handlers:
            raise StructuralEditError(
                "At least one exception "
                "handler is required."
            )

        if (
            try_node.orelse
            or try_node.finalbody
        ):
            raise StructuralEditError(
                "FORGE v2.0 phase 1 accepts "
                "except clauses only; no else/finally."
            )

        for handler in try_node.handlers:
            if handler.type is None:
                raise StructuralEditError(
                    "Bare except clauses are not allowed."
                )
