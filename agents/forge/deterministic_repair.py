from __future__ import annotations

import ast
from pathlib import PurePosixPath
import re


def _norm(
    path: str,
) -> str:
    return (
        str(path)
        .replace("\\", "/")
        .lstrip("./")
    )


def _function_name_for_path(
    path: str,
) -> str:
    stem = PurePosixPath(
        _norm(path)
    ).stem

    stem = re.sub(
        r"\W+",
        "_",
        stem,
    )

    stem = stem.strip(
        "_"
    ) or "module"

    if stem[0].isdigit():
        stem = "_" + stem

    return (
        "run_"
        + stem
    )


def _has_nonempty_return(
    tree: ast.Module,
) -> bool:
    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        for child in ast.walk(
            node
        ):
            if (
                isinstance(
                    child,
                    ast.Return,
                )
                and child.value is not None
            ):
                return True

    return False


def _is_terminal_single_print(
    node: ast.AST,
) -> bool:
    if not isinstance(
        node,
        ast.Expr,
    ):
        return False

    call = node.value

    if not isinstance(
        call,
        ast.Call,
    ):
        return False

    if not isinstance(
        call.func,
        ast.Name,
    ):
        return False

    if call.func.id != "print":
        return False

    if len(
        call.args
    ) != 1:
        return False

    if call.keywords:
        return False

    return True


def repair_return_requirement(
    *,
    path: str,
    source: str,
    findings,
) -> str | None:
    """
    Conservatively repair a simple script-like REQ-R*-RETURN failure.

    This function never imports or executes the candidate code.

    It applies only when:
    - at least one machine finding is REQ-R*-RETURN,
    - there is no existing callable non-empty return,
    - the module is script-like: imports/docstring plus simple
      top-level assignments/expressions,
    - the final executable statement is print(<single expression>).

    Repair:
    - keep module docstring/imports at module scope,
    - wrap executable statements into run_<filename>(),
    - replace terminal print(value) with return value.

    Anything more complex returns None so PAT can fall back to the
    existing targeted FORGE repair.
    """

    return_findings = [
        finding
        for finding in (
            findings
            or []
        )
        if re.fullmatch(
            r"REQ-R\d+-RETURN",
            str(
                getattr(
                    finding,
                    "code",
                    "",
                )
            ),
        )
    ]

    if not return_findings:
        return None

    try:
        tree = ast.parse(
            source,
            filename=path,
        )
    except SyntaxError:
        return None

    if _has_nonempty_return(
        tree
    ):
        return None

    prelude = []
    executable = []

    for index, node in enumerate(
        tree.body
    ):
        if (
            index == 0
            and isinstance(
                node,
                ast.Expr,
            )
            and isinstance(
                node.value,
                ast.Constant,
            )
            and isinstance(
                node.value.value,
                str,
            )
        ):
            prelude.append(
                node
            )
            continue

        if isinstance(
            node,
            (
                ast.Import,
                ast.ImportFrom,
            ),
        ):
            if executable:
                # Keep the transform conservative: imports must precede
                # executable script statements.
                return None

            prelude.append(
                node
            )
            continue

        # Do not structurally rewrite a module that already defines
        # functions/classes or contains control-flow blocks.
        if not isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
                ast.Expr,
            ),
        ):
            return None

        executable.append(
            node
        )

    if not executable:
        return None

    terminal = executable[
        -1
    ]

    if not _is_terminal_single_print(
        terminal
    ):
        return None

    print_call = terminal.value

    repaired_body = list(
        executable[:-1]
    )

    repaired_body.append(
        ast.Return(
            value=print_call.args[
                0
            ]
        )
    )

    fn = ast.FunctionDef(
        name=_function_name_for_path(
            path
        ),
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=repaired_body,
        decorator_list=[],
        returns=None,
        type_comment=None,
    )

    repaired_tree = ast.Module(
        body=[
            *prelude,
            fn,
        ],
        type_ignores=[],
    )

    ast.fix_missing_locations(
        repaired_tree
    )

    repaired = (
        ast.unparse(
            repaired_tree
        )
        + "\n"
    )

    # Defense-in-depth: repaired source must parse and prove a non-empty
    # callable return before it is returned to the manager.
    try:
        verified = ast.parse(
            repaired,
            filename=path,
        )
    except SyntaxError:
        return None

    if not _has_nonempty_return(
        verified
    ):
        return None

    return repaired
