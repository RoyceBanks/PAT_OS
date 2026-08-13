from __future__ import annotations

from dataclasses import dataclass
import ast
import builtins
from pathlib import Path, PurePosixPath
import re
import symtable


@dataclass(frozen=True)
class SemanticFinding:
    code: str
    path: str
    message: str
    evidence: str = ""

    def format(self) -> str:
        text = f"[{self.code}] {self.path}: {self.message}"
        if self.evidence:
            text += f" Evidence: {self.evidence}"
        return text


_MAGIC_GLOBALS = {
    "__name__",
    "__file__",
    "__package__",
    "__spec__",
    "__loader__",
    "__builtins__",
    "__doc__",
    "__annotations__",
}


def _norm(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _module_name(path: str) -> str:
    p = PurePosixPath(_norm(path))
    parts = list(p.parts)
    if not parts:
        return ""
    parts[-1] = PurePosixPath(parts[-1]).stem
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _module_defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()

    def bind_target(node):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                bind_target(item)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                bind_target(target)
        elif isinstance(node, ast.AnnAssign):
            bind_target(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind_target(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars:
                    bind_target(item.optional_vars)
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.name:
                    names.add(handler.name)

    return names


def _unresolved_globals(source: str, filename: str) -> set[str]:
    table = symtable.symtable(source, filename, "exec")
    module_bound = set()

    for ident in table.get_identifiers():
        symbol = table.lookup(ident)
        if (
            symbol.is_assigned()
            or symbol.is_imported()
            or symbol.is_namespace()
            or symbol.is_parameter()
        ):
            module_bound.add(ident)

    allowed = set(dir(builtins)) | _MAGIC_GLOBALS | module_bound
    unresolved: set[str] = set()

    def walk(scope):
        for ident in scope.get_identifiers():
            symbol = scope.lookup(ident)
            if (
                symbol.is_referenced()
                and symbol.is_global()
                and ident not in allowed
            ):
                unresolved.add(ident)

        for child in scope.get_children():
            walk(child)

    walk(table)
    return unresolved


def _class_info(tree: ast.Module) -> dict[str, dict]:
    result = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        fields = set()
        explicit_init = False
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.add(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        fields.add(target.id)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                explicit_init = True

        decorators = set()
        for deco in node.decorator_list:
            if isinstance(deco, ast.Name):
                decorators.add(deco.id)
            elif isinstance(deco, ast.Attribute):
                decorators.add(deco.attr)

        result[node.name] = {
            "node": node,
            "fields": fields,
            "explicit_init": explicit_init,
            "decorators": decorators,
            "has_bases": bool(node.bases),
        }
    return result


def _from_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    mapping = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            mapping[alias.asname or alias.name] = (node.module, alias.name)
    return mapping


def _callable_nodes(tree: ast.Module):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _nonempty_returns(fn) -> list[ast.Return]:
    returns = []
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not fn:
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            returns.append(node)
    return returns


def _call_name(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return ""

def _unsafe_eval_calls(
    tree: ast.Module,
) -> list[ast.Call]:
    """
    Return direct uses of Python eval() that PAT does not allow
    in generated proposals.

    This is a deterministic, non-executing security check.
    """

    calls = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        # Direct builtin-style call:
        # eval(...)
        if (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id == "eval"
        ):
            calls.append(
                node
            )
            continue

        # Explicit builtins.eval(...)
        if (
            isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr == "eval"
            and isinstance(
                node.func.value,
                ast.Name,
            )
            and node.func.value.id == "builtins"
        ):
            calls.append(
                node
            )

    return calls


def _dict_string_keys(node: ast.AST) -> set[str]:
    keys = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Dict):
            for key in child.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value.lower())
    return keys


def _resolve_criterion_path(criterion: str, paths: list[str]) -> str | None:
    names = re.findall(r"([A-Za-z0-9_./\\-]+\.py)\b", criterion)
    if not names:
        return None

    candidate = _norm(names[0])
    exact = [path for path in paths if path == candidate]
    if len(exact) == 1:
        return exact[0]

    base = PurePosixPath(candidate).name
    by_base = [path for path in paths if PurePosixPath(path).name == base]
    if len(by_base) == 1:
        return by_base[0]

    return None


def _criterion_findings(criteria, modules):
    findings = []
    paths = list(modules)

    for index, criterion in enumerate(criteria, start=1):
        low = criterion.lower()
        path = _resolve_criterion_path(criterion, paths)
        if path is None:
            continue

        tree = modules[path]["tree"]
        functions = _callable_nodes(tree)

        # Explicit "returns" requirement: require callable behavior with a
        # non-empty Return. Module-level print/assignment does not count.
        if re.search(r"\breturns?\b", low):
            returning = [fn for fn in functions if _nonempty_returns(fn)]
            if not returning:
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-RETURN",
                        path=path,
                        message=(
                            "Explicit requirement says this file returns a value, "
                            "but no function/method has a non-empty return statement."
                        ),
                        evidence=criterion,
                    )
                )
                continue

        # Common demo behavior: two task creations, one completion, return.
        if (
            "two task" in low
            and "complete" in low
            and "return" in low
        ):
            satisfied = False
            for fn in functions:
                calls = [node for node in ast.walk(fn) if isinstance(node, ast.Call)]
                names = [_call_name(call).lower() for call in calls]
                creates = sum(
                    1
                    for name in names
                    if name in {"create_task", "add_task"}
                    or ("create" in name and "task" in name)
                )
                completes = sum(
                    1
                    for name in names
                    if name in {"mark_complete", "complete_task"}
                    or "complete" in name
                )
                if creates >= 2 and completes >= 1 and _nonempty_returns(fn):
                    satisfied = True
                    break

            if not satisfied:
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-DEMO",
                        path=path,
                        message=(
                            "No single callable proves the requested demo flow: "
                            "create/build two tasks, complete one, and return a result."
                        ),
                        evidence=criterion,
                    )
                )

        # Explicit class declaration with named fields.
        match = re.search(
            r"defines\s+([A-Za-z_]\w*)\s+with\s+(.+)",
            criterion,
            flags=re.IGNORECASE,
        )
        if match:
            class_name = match.group(1)
            tail = match.group(2)
            requested_fields = [
                token
                for token in re.findall(r"\b[A-Za-z_]\w*\b", tail)
                if token.lower() not in {"and", "or", "the", "a", "an"}
            ]
            info = modules[path]["classes"].get(class_name)
            if info is None:
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-CLASS",
                        path=path,
                        message=f"Required class {class_name!r} is not defined.",
                        evidence=criterion,
                    )
                )
            else:
                missing = [name for name in requested_fields if name not in info["fields"]]
                if missing:
                    findings.append(
                        SemanticFinding(
                            code=f"REQ-R{index}-FIELDS",
                            path=path,
                            message=(
                                f"Class {class_name!r} is missing required field(s): "
                                + ", ".join(missing)
                            ),
                            evidence=criterion,
                        )
                    )

        # Report summary with named count keys.
        if "summary" in low and "total" in low and "completed" in low and "return" in low:
            has_keys = False
            for fn in functions:
                for ret in _nonempty_returns(fn):
                    keys = _dict_string_keys(ret.value)
                    if {"total", "completed"}.issubset(keys):
                        has_keys = True
                        break
                if has_keys:
                    break
            if not has_keys:
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-SUMMARY",
                        path=path,
                        message=(
                            "No returned dictionary proves both 'total' and 'completed' summary counts."
                        ),
                        evidence=criterion,
                    )
                )

        # Common add/list requirement.
        if "add/list" in low or ("add" in low and "list" in low and "task" in low):
            method_names = {
                node.name.lower()
                for node in functions
            }
            if not any("add" in name for name in method_names) or not any("list" in name for name in method_names):
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-ADD-LIST",
                        path=path,
                        message="Required add/list task operations are not both present.",
                        evidence=criterion,
                    )
                )

        # Common create/complete service requirement.
        if "create task" in low and "complete" in low:
            method_names = {node.name.lower() for node in functions}
            if not any("create" in name and "task" in name for name in method_names) or not any("complete" in name for name in method_names):
                findings.append(
                    SemanticFinding(
                        code=f"REQ-R{index}-CREATE-COMPLETE",
                        path=path,
                        message="Required create-task and complete-task operations are not both present.",
                        evidence=criterion,
                    )
                )

    return findings


def validate_plan_semantics(
    plan,
    workspace,
    acceptance_criteria=None,
) -> list[SemanticFinding]:
    """
    Deterministic, non-executing semantic preflight for proposed Python.

    It intentionally does NOT import or run generated code.
    """

    workspace = Path(workspace)
    criteria = list(acceptance_criteria or [])
    modules = {}
    findings: list[SemanticFinding] = []

    for change in plan.files:
        path = _norm(change.path)
        if not path.lower().endswith(".py"):
            continue

        source = change.content
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            findings.append(
                SemanticFinding(
                    code="AST-SYNTAX",
                    path=path,
                    message="Proposed Python cannot be parsed.",
                    evidence=f"line {exc.lineno}: {exc.msg}",
                )
            )
            continue

        modules[path] = {
            "source": source,
            "tree": tree,
            "module": _module_name(path),
            "defined": _module_defined_names(tree),
            "classes": _class_info(tree),
            "imports": _from_imports(tree),
        }

    # Security: generated Python must not use eval().
    for path, info in modules.items():
        for call in _unsafe_eval_calls(
            info["tree"]
        ):
            findings.append(
                SemanticFinding(
                    code="AST-UNSAFE-EVAL",
                    path=path,
                    message=(
                        "Proposed Python uses eval(), "
                        "which PAT does not allow in "
                        "generated code."
                    ),
                    evidence=(
                        "direct eval call at line "
                        + str(
                            getattr(
                                call,
                                "lineno",
                                "?",
                            )
                        )
                    ),
                )
            )

    module_by_name = {
        info["module"]: path
        for path, info in modules.items()
        if info["module"]
    }

    # 1) Obvious unresolved global names using Python's symbol table.
    for path, info in modules.items():
        try:
            unresolved = _unresolved_globals(
                info["source"],
                path,
            )
        except SyntaxError:
            continue

        for name in sorted(unresolved):
            findings.append(
                SemanticFinding(
                    code="UNRESOLVED-GLOBAL",
                    path=path,
                    message=f"Name {name!r} is referenced as a global but is not defined/imported in this module.",
                )
            )

    # 2) Cross-file from-import symbols must exist in proposed local module.
    for path, info in modules.items():
        for local_name, (module_name, symbol_name) in info["imports"].items():
            target_path = module_by_name.get(module_name)
            if not target_path:
                # If this looks like a project-local import, check an existing
                # source file without importing it.
                candidate = workspace / Path(*module_name.split("."))
                candidate_py = candidate.with_suffix(".py")
                candidate_init = candidate / "__init__.py"
                target_source = None
                if candidate_py.exists():
                    target_source = candidate_py.read_text(encoding="utf-8")
                elif candidate_init.exists():
                    target_source = candidate_init.read_text(encoding="utf-8")

                if target_source is None:
                    continue

                try:
                    target_tree = ast.parse(target_source)
                except SyntaxError:
                    continue
                target_defined = _module_defined_names(target_tree)
            else:
                target_defined = modules[target_path]["defined"]

            if symbol_name not in target_defined:
                findings.append(
                    SemanticFinding(
                        code="LOCAL-IMPORT-SYMBOL",
                        path=path,
                        message=(
                            f"Import requests {symbol_name!r} from {module_name!r}, "
                            "but that symbol is not defined there."
                        ),
                        evidence=f"local binding: {local_name}",
                    )
                )

    # 3) Detect calls to simple local classes that cannot accept arguments.
    class_registry = {}
    for path, info in modules.items():
        for class_name, class_info in info["classes"].items():
            class_registry[(info["module"], class_name)] = (path, class_info)

    for path, info in modules.items():
        import_map = info["imports"]
        local_classes = info["classes"]

        for call in [node for node in ast.walk(info["tree"]) if isinstance(node, ast.Call)]:
            if not (call.args or call.keywords):
                continue

            target = None
            called_name = None
            if isinstance(call.func, ast.Name):
                called_name = call.func.id
                if called_name in local_classes:
                    target = (path, local_classes[called_name])
                elif called_name in import_map:
                    mod, symbol = import_map[called_name]
                    target = class_registry.get((mod, symbol))

            if not target:
                continue

            target_path, class_info = target
            if (
                not class_info["explicit_init"]
                and not class_info["has_bases"]
                and not ({"dataclass", "define", "attrs"} & class_info["decorators"])
            ):
                findings.append(
                    SemanticFinding(
                        code="CLASS-CONSTRUCTOR",
                        path=path,
                        message=(
                            f"Class {called_name!r} is called with arguments, but its definition in "
                            f"{target_path} has no explicit __init__, base class, or recognized dataclass decorator."
                        ),
                        evidence=(
                            f"line {getattr(call, 'lineno', '?')}"
                        ),
                    )
                )

    # 4) Deterministic acceptance-criteria patterns.
    findings.extend(
        _criterion_findings(
            criteria,
            modules,
        )
    )

    # De-duplicate identical findings while preserving order.
    unique = []
    seen = set()
    for finding in findings:
        key = (
            finding.code,
            finding.path,
            finding.message,
            finding.evidence,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)

    return unique
