from __future__ import annotations

import ast
from collections import Counter


_FORGE_IMPL_PREFIX = "_forge_impl_"


def _top_level_function_counts(
    source: str,
) -> Counter[str]:
    tree = ast.parse(source)

    return Counter(
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    )


def build_python_structure_facts(
    before_source: str,
    after_source: str,
    relative_path: str,
) -> list[str]:
    if not relative_path.lower().endswith(".py"):
        return []

    facts: list[str] = []

    try:
        before_counts = _top_level_function_counts(
            before_source
        )
    except SyntaxError as exc:
        before_counts = Counter()
        facts.append(
            "- BEFORE AST parse unavailable: "
            f"{exc.msg}"
        )

    try:
        after_counts = _top_level_function_counts(
            after_source
        )
    except SyntaxError as exc:
        return facts + [
            "- AFTER AST parse FAILED: "
            f"{exc.msg}"
        ]

    wrapper_pairs: list[tuple[str, str]] = []

    for implementation_name in sorted(after_counts):
        if not implementation_name.startswith(
            _FORGE_IMPL_PREFIX
        ):
            continue

        public_name = implementation_name[
            len(_FORGE_IMPL_PREFIX):
        ]

        if public_name:
            wrapper_pairs.append(
                (
                    public_name,
                    implementation_name,
                )
            )

    for public_name, implementation_name in wrapper_pairs:
        before_public = before_counts[public_name]
        after_public = after_counts[public_name]
        before_impl = before_counts[implementation_name]
        after_impl = after_counts[implementation_name]

        public_duplicate = after_public > 1
        implementation_duplicate = after_impl > 1

        facts.extend(
            [
                (
                    "- WRAPPER PAIR: "
                    f"public={public_name}; "
                    f"implementation={implementation_name}"
                ),
                (
                    "- DEFINITION COUNTS: "
                    f"before {public_name}={before_public}; "
                    f"after {public_name}={after_public}; "
                    f"before {implementation_name}={before_impl}; "
                    f"after {implementation_name}={after_impl}"
                ),
                (
                    "- DUPLICATION CHECK: "
                    f"public_duplicate={public_duplicate}; "
                    f"implementation_duplicate="
                    f"{implementation_duplicate}"
                ),
            ]
        )

        if (
            before_public == 1
            and after_public == 1
            and before_impl == 0
            and after_impl == 1
            and not public_duplicate
            and not implementation_duplicate
        ):
            facts.append(
                (
                    "- RENAME/WRAPPER FACT: "
                    f"the original top-level {public_name} "
                    f"definition was renamed to "
                    f"{implementation_name}, and the AFTER "
                    f"source contains exactly one public "
                    f"{public_name} wrapper. The removed '-' "
                    "definition in the unified diff does NOT "
                    "coexist with the AFTER source."
                )
            )

    duplicate_names = sorted(
        name
        for name, count in after_counts.items()
        if count > 1
    )

    if wrapper_pairs:
        if duplicate_names:
            facts.append(
                "- DUPLICATE TOP-LEVEL FUNCTION NAMES "
                "IN AFTER SOURCE: "
                + ", ".join(duplicate_names)
            )
        else:
            facts.append(
                "- DUPLICATE TOP-LEVEL FUNCTION NAMES "
                "IN AFTER SOURCE: NONE"
            )

    return facts
