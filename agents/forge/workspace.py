from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {
    ".git", ".venv", "venv", ".venv_uv_backup", ".forge_backups",
    "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache",
    ".idea", ".vscode", "site-packages",
}
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".md",
    ".txt", ".sql", ".sh", ".ps1", ".bat", ".env", ".xml",
}

class WorkspaceSecurityError(RuntimeError):
    pass

@dataclass
class Workspace:
    root: Path

    def __init__(self, root: str | Path, create: bool = False):
        resolved = Path(root).expanduser().resolve()
        if create:
            resolved.mkdir(parents=True, exist_ok=True)
        if not resolved.exists():
            raise FileNotFoundError(resolved)
        if not resolved.is_dir():
            raise NotADirectoryError(resolved)
        self.root = resolved

    def _safe_path(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute():
            raise WorkspaceSecurityError("Absolute paths are not allowed")
        for part in relative.parts:
            low = part.lower()
            if (
                low in {".git", ".venv", "venv", "site-packages", ".forge_backups"}
                or low.startswith(".venv")
                or low.startswith("venv")
            ):
                raise WorkspaceSecurityError(f"Protected path: {relative_path}")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceSecurityError(f"Path escapes workspace: {relative_path}") from exc
        return candidate

    def list_files(self, limit: int = 500) -> list[str]:
        results = []
        for path in self.root.rglob("*"):
            if len(results) >= limit:
                break
            if not path.is_file():
                continue
            parts = path.relative_to(self.root).parts
            if any(
                p in IGNORED_DIRS or p.startswith(".venv") or p.startswith("venv")
                for p in parts
            ):
                continue
            results.append(str(path.relative_to(self.root)))
        return sorted(results)

    def list_code_files(self, limit: int = 300) -> list[str]:
        special = {"Dockerfile", "Makefile", "requirements.txt", "pyproject.toml", "package.json"}
        results = []
        for rel in self.list_files(limit * 3):
            path = Path(rel)
            if path.suffix.lower() in TEXT_EXTENSIONS or path.name in special:
                results.append(rel)
            if len(results) >= limit:
                break
        return results

    def read_text(self, relative_path: str, max_chars: int = 100000) -> str:
        path = self._safe_path(relative_path)
        if not path.exists():
            raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    def write_text(self, relative_path: str, content: str) -> None:
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        return self._safe_path(relative_path).exists()

    def build_context(self, max_files: int = 20, max_chars_per_file: int = 12000) -> str:
        all_files = self.list_code_files(300)
        chunks = [
            f"WORKSPACE ROOT: {self.root}", "", "PROJECT FILES:",
            *[f"- {name}" for name in all_files], "", "SELECTED FILE CONTENTS:",
        ]
        for rel in all_files[:max_files]:
            chunks.append(f"\n--- FILE: {rel} ---")
            try:
                chunks.append(self.read_text(rel, max_chars_per_file))
            except Exception as exc:
                chunks.append(f"[Unable to read: {exc}]")
        return "\n".join(chunks)
