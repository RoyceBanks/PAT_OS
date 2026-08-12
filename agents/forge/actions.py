from __future__ import annotations
from dataclasses import dataclass, field
import json
import re

class PlanParseError(RuntimeError):
    pass

@dataclass
class FileChange:
    path: str
    content: str

@dataclass
class ImplementationPlan:
    summary: str
    files: list[FileChange] = field(default_factory=list)
    run_tests: bool = False
    notes: list[str] = field(default_factory=list)

def parse_implementation_plan(text: str) -> ImplementationPlan:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise PlanParseError("FORGE did not return a JSON implementation plan.")
    try:
        data = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"Invalid FORGE JSON: {exc}") from exc
    raw_files = data.get("files", [])
    if not isinstance(raw_files, list) or len(raw_files) > 20:
        raise PlanParseError("Invalid file list in implementation plan.")
    changes = []
    for item in raw_files:
        if not isinstance(item, dict):
            raise PlanParseError("Each file change must be an object.")
        path = str(item.get("path", "")).strip()
        content = item.get("content")
        if not path or not isinstance(content, str):
            raise PlanParseError("Every file change needs path and content.")
        changes.append(FileChange(path=path, content=content))
    notes = data.get("notes", [])
    return ImplementationPlan(
        summary=str(data.get("summary", "")).strip(),
        files=changes,
        run_tests=bool(data.get("run_tests", False)),
        notes=[str(x) for x in notes] if isinstance(notes, list) else [],
    )
