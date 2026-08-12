from __future__ import annotations
from pathlib import Path
import shutil
from .actions import FileChange
from .workspace import Workspace

class ForgeTools:
    def __init__(self, workspace: str | Path, create: bool = False):
        self.workspace = Workspace(workspace, create=create)

    def apply_changes(self, changes: list[FileChange], task_id: str) -> list[dict]:
        results = []
        for change in changes:
            target = self.workspace._safe_path(change.path)
            existed = target.exists()
            backup = None
            if existed and target.is_file():
                backup = self.workspace.root / ".forge_backups" / task_id / Path(change.path)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            self.workspace.write_text(change.path, change.content)
            results.append({
                "path": change.path,
                "operation": "updated" if existed else "created",
                "backup": str(backup) if backup else None,
            })
        return results
