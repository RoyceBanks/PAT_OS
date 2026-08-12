from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil
from typing import Any

from .workspace import Workspace


MANIFEST_VERSION = 2


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class SnapshotEntry:
    path: str
    existed: bool
    was_file: bool
    backup_path: str | None
    before_sha256: str | None = None
    after_sha256: str | None = None


class WorkspaceTransaction:
    """Controlled workspace transaction with rollback + undo metadata."""

    def __init__(
        self,
        workspace: str | Path,
        task_id: str,
        approved_paths: list[str] | tuple[str, ...],
        metadata: dict[str, Any] | None = None,
    ):
        self.workspace = Workspace(workspace, create=False)
        self.task_id = task_id
        self.approved_paths = tuple(dict.fromkeys(str(p) for p in approved_paths))
        self.metadata = dict(metadata or {})
        self.transaction_root = self.workspace.root / ".forge_transactions" / task_id
        self.backup_root = self.transaction_root / "originals"
        self.manifest_path = self.transaction_root / "manifest.json"
        self.entries: list[SnapshotEntry] = []
        self.started = False
        self.finished = False
        self.created_at = _utc_now()

    def _write_manifest(self, status: str, **extra: Any) -> None:
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "task_id": self.task_id,
            "workspace": str(self.workspace.root),
            "created_at": self.created_at,
            "status": status,
            "approved_paths": list(self.approved_paths),
            "metadata": self.metadata,
            "entries": [asdict(entry) for entry in self.entries],
        }
        manifest.update(extra)
        self.transaction_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def begin(self) -> None:
        if self.started:
            return

        self.backup_root.mkdir(parents=True, exist_ok=True)
        entries: list[SnapshotEntry] = []

        for relative in self.approved_paths:
            target = self.workspace._safe_path(relative)
            existed = target.exists()
            was_file = target.is_file() if existed else False
            backup_path = None
            before_hash = None

            if existed:
                if not was_file:
                    raise RuntimeError(f"FORGE approval target is not a file: {relative}")

                before_hash = _sha256_file(target)
                backup = self.backup_root / Path(relative)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backup_path = str(backup)

            entries.append(
                SnapshotEntry(
                    path=relative,
                    existed=existed,
                    was_file=was_file,
                    backup_path=backup_path,
                    before_sha256=before_hash,
                )
            )

        self.entries = entries
        self.started = True
        self._write_manifest("STARTED")

    def assert_scope(self, paths: list[str] | tuple[str, ...]) -> None:
        extra = sorted(set(map(str, paths)) - set(self.approved_paths))
        if extra:
            raise PermissionError(
                "FORGE attempted to modify paths that were not approved: "
                + ", ".join(extra)
            )

    def rollback(self) -> None:
        if not self.started:
            return

        for entry in reversed(self.entries):
            target = self.workspace._safe_path(entry.path)

            if entry.existed:
                if not entry.backup_path:
                    raise RuntimeError(f"Transaction backup is missing for {entry.path}")

                backup = Path(entry.backup_path)
                if not backup.exists():
                    raise RuntimeError(f"Transaction backup file is missing: {backup}")

                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            elif target.exists():
                if target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)

        self.finished = True
        self._write_manifest("ROLLED_BACK", rolled_back_at=_utc_now())

    def commit(self) -> None:
        if not self.started:
            raise RuntimeError("Transaction has not started.")

        for entry in self.entries:
            target = self.workspace._safe_path(entry.path)
            entry.after_sha256 = _sha256_file(target)

        self.finished = True
        self._write_manifest("COMMITTED", committed_at=_utc_now())

    def recovery_location(self) -> str:
        return str(self.transaction_root)
