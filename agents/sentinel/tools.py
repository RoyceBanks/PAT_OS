from __future__ import annotations

from pathlib import Path
from .workspace import Workspace


class SentinelTools:
    """Read-only project tools for SENTINEL."""

    def __init__(self, workspace: str | Path):
        self.workspace = Workspace(workspace)

    def list_files(self) -> list[str]:
        return self.workspace.list_files()

    def read_file(self, path: str) -> str:
        return self.workspace.read_text(path)

    def project_context(
        self,
        files: list[str] | None = None,
    ) -> str:
        return self.workspace.build_review_context(files=files)
