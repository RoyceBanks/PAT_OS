from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    ".venv_uv_backup",
    ".forge_backups",
    ".forge_transactions",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "site-packages",
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

    def __init__(
        self,
        root: str | Path,
    ):
        resolved = (
            Path(root)
            .expanduser()
            .resolve()
        )

        if not resolved.exists():
            raise FileNotFoundError(
                f"Workspace does not exist: {resolved}"
            )

        if not resolved.is_dir():
            raise NotADirectoryError(
                f"Workspace is not a directory: {resolved}"
            )

        self.root = resolved

    @staticmethod
    def _normalize_relative(
        relative_path: str | Path,
    ) -> str:
        """
        Normalize Windows/POSIX separators to a stable
        workspace-relative POSIX-style path.
        """

        text = str(
            relative_path
        ).replace("\\", "/")

        while text.startswith("./"):
            text = text[2:]

        return text

    def _safe_path(
        self,
        relative_path: str | Path,
    ) -> Path:
        normalized = self._normalize_relative(
            relative_path
        )

        relative = Path(normalized)

        if relative.is_absolute():
            raise WorkspaceSecurityError(
                f"Absolute path is not allowed: {relative_path}"
            )

        candidate = (
            self.root / relative
        ).resolve()

        try:
            candidate.relative_to(
                self.root
            )
        except ValueError as exc:
            raise WorkspaceSecurityError(
                f"Path escapes workspace: {relative_path}"
            ) from exc

        return candidate

    def list_files(
        self,
        limit: int = 600,
    ) -> list[str]:
        results: list[str] = []

        for path in self.root.rglob("*"):
            if len(results) >= limit:
                break

            if not path.is_file():
                continue

            relative = path.relative_to(
                self.root
            )

            if any(
                part in IGNORED_DIRS
                or part.startswith(".venv")
                or part.startswith("venv")
                for part in relative.parts
            ):
                continue

            # Stable separators on Windows and Linux.
            results.append(
                relative.as_posix()
            )

        return sorted(
            results
        )

    def list_code_files(
        self,
        limit: int = 400,
    ) -> list[str]:
        results: list[str] = []

        special = {
            "Dockerfile",
            "Makefile",
            "requirements.txt",
            "pyproject.toml",
            "package.json",
        }

        for relative in self.list_files(
            limit=limit * 3
        ):
            path = Path(relative)

            if (
                path.suffix.lower()
                in TEXT_EXTENSIONS
                or path.name in special
            ):
                results.append(
                    relative
                )

            if len(results) >= limit:
                break

        return results

    def read_text(
        self,
        relative_path: str,
        max_chars: int = 120_000,
    ) -> str:
        path = self._safe_path(
            relative_path
        )

        if not path.exists():
            raise FileNotFoundError(
                relative_path
            )

        if not path.is_file():
            raise IsADirectoryError(
                relative_path
            )

        return path.read_text(
            encoding="utf-8",
            errors="replace",
        )[:max_chars]

    def build_review_context(
        self,
        files: list[str] | None = None,
        max_files: int = 30,
        max_chars_per_file: int = 120_000,
    ) -> str:
        """
        Build SENTINEL review context.

        Critical rule:
        If the caller explicitly supplies files, review those
        files directly. Do NOT require them to appear in a
        discovery list first.
        """

        all_files = self.list_code_files(
            limit=400
        )

        missing: list[str] = []

        if files:
            selected: list[str] = []

            for requested in files:
                normalized = (
                    self._normalize_relative(
                        requested
                    )
                )

                if normalized in selected:
                    continue

                try:
                    path = self._safe_path(
                        normalized
                    )

                    if (
                        path.exists()
                        and path.is_file()
                    ):
                        selected.append(
                            normalized
                        )
                    else:
                        missing.append(
                            normalized
                        )

                except Exception:
                    missing.append(
                        normalized
                    )

                if len(selected) >= max_files:
                    break

        else:
            selected = all_files[
                :max_files
            ]

        chunks = [
            f"WORKSPACE ROOT: {self.root}",
            "",
            "PROJECT FILES:",
            *[
                f"- {name}"
                for name in all_files
            ],
            "",
            "FILES SELECTED FOR REVIEW:",
        ]

        if selected:
            chunks.extend(
                f"- {name}"
                for name in selected
            )
        else:
            chunks.append(
                "- [NONE]"
            )

        if missing:
            chunks.extend([
                "",
                "REQUESTED FILES NOT FOUND:",
                *[
                    f"- {name}"
                    for name in missing
                ],
            ])

        chunks.extend([
            "",
            "FILE CONTENTS:",
        ])

        for relative in selected:
            chunks.append(
                f"\n--- FILE: {relative} ---"
            )

            try:
                chunks.append(
                    self.read_text(
                        relative,
                        max_chars=max_chars_per_file,
                    )
                )
            except Exception as exc:
                chunks.append(
                    f"[Unable to read file: {exc}]"
                )

        return "\n".join(
            chunks
        )
