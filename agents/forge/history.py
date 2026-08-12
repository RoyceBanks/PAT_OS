from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import shutil
from typing import Any

from .workspace import Workspace


TASK_ID_PATTERN = re.compile(r"^TASK-[A-Z0-9]+$", re.IGNORECASE)


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
class HistoryItem:
    task_id: str
    status: str
    workspace: str
    created_at: str | None
    committed_at: str | None
    undone_at: str | None
    paths: list[str]
    summary: str | None
    manifest_version: int


@dataclass
class UndoResult:
    success: bool
    task_id: str
    message: str
    restored_paths: list[str]
    workspace: str | None = None


class ForgeHistory:
    """Persistent FORGE history with conservative hash-verified undo."""

    def __init__(self, pat_root: str | Path):
        self.pat_root = Path(pat_root).expanduser().resolve()

    def _validate_task_id(self, task_id: str) -> str:
        normalized = task_id.strip().upper()
        if not TASK_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid FORGE task ID.")
        return normalized

    def _find_manifest(self, task_id: str) -> Path | None:
        task_id = self._validate_task_id(task_id)

        direct = self.pat_root / ".forge_transactions" / task_id / "manifest.json"
        if direct.exists():
            return direct

        generated = self.pat_root / "forge_projects"
        if generated.exists():
            for candidate in generated.glob(
                f"*/.forge_transactions/{task_id}/manifest.json"
            ):
                if candidate.is_file():
                    return candidate
        return None

    def _load_manifest_path(self, manifest_path: Path) -> dict[str, Any]:
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def load(self, task_id: str) -> dict[str, Any] | None:
        manifest_path = self._find_manifest(task_id)
        if manifest_path is None:
            return None
        data = self._load_manifest_path(manifest_path)
        data["_manifest_path"] = str(manifest_path)
        return data

    def list(self, limit: int = 10) -> list[HistoryItem]:
        manifests: list[Path] = []

        main_root = self.pat_root / ".forge_transactions"
        if main_root.exists():
            manifests.extend(main_root.glob("TASK-*/manifest.json"))

        generated = self.pat_root / "forge_projects"
        if generated.exists():
            manifests.extend(
                generated.glob("*/.forge_transactions/TASK-*/manifest.json")
            )

        records: list[HistoryItem] = []
        for path in manifests:
            try:
                data = self._load_manifest_path(path)
            except Exception:
                continue

            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            records.append(
                HistoryItem(
                    task_id=str(data.get("task_id", path.parent.name)),
                    status=str(data.get("status", "LEGACY")),
                    workspace=str(data.get("workspace", "")),
                    created_at=data.get("created_at"),
                    committed_at=data.get("committed_at"),
                    undone_at=data.get("undone_at"),
                    paths=[str(x) for x in data.get("approved_paths", [])],
                    summary=metadata.get("summary"),
                    manifest_version=int(data.get("manifest_version", 1)),
                )
            )

        records.sort(
            key=lambda item: item.committed_at or item.created_at or "",
            reverse=True,
        )
        return records[:limit]

    def undo(self, task_id: str) -> UndoResult:
        task_id = self._validate_task_id(task_id)
        data = self.load(task_id)

        if data is None:
            return UndoResult(False, task_id, "FORGE transaction was not found.", [])

        manifest_path = Path(data["_manifest_path"])
        version = int(data.get("manifest_version", 1))
        if version < 2:
            return UndoResult(
                False,
                task_id,
                "This is a legacy pre-v1.8 transaction. Automatic undo is disabled because it does not contain reliable post-change hashes.",
                [],
            )

        status = str(data.get("status", "")).upper()
        if status != "COMMITTED":
            return UndoResult(
                False,
                task_id,
                f"Only a COMMITTED transaction can be undone. Current status: {status or 'UNKNOWN'}.",
                [],
            )

        workspace_path = Path(data.get("workspace", "")).expanduser().resolve()
        if not workspace_path.exists():
            return UndoResult(False, task_id, "The transaction workspace no longer exists.", [])

        workspace = Workspace(workspace_path, create=False)
        entries = data.get("entries", [])
        if not isinstance(entries, list) or not entries:
            return UndoResult(False, task_id, "The transaction has no recoverable file entries.", [])

        # Preflight EVERYTHING before changing the first file.
        conflicts: list[str] = []
        missing_backups: list[str] = []

        for entry in entries:
            relative = str(entry.get("path", ""))
            expected_after = entry.get("after_sha256")
            target = workspace._safe_path(relative)

            if expected_after is None:
                conflicts.append(f"{relative}: missing committed hash")
            elif _sha256_file(target) != expected_after:
                conflicts.append(
                    f"{relative}: current file has changed since this transaction"
                )

            if bool(entry.get("existed", False)):
                backup_value = entry.get("backup_path")
                if not backup_value or not Path(backup_value).exists():
                    missing_backups.append(relative)

        if conflicts or missing_backups:
            details: list[str] = []
            if conflicts:
                details.append("Newer or unverified file state:")
                details.extend(f"- {item}" for item in conflicts)
            if missing_backups:
                details.append("Missing required backups:")
                details.extend(f"- {item}" for item in missing_backups)

            return UndoResult(
                False,
                task_id,
                "UNDO REFUSED.\n\n" + "\n".join(details) + "\n\nNo files were modified.",
                [],
                str(workspace_path),
            )

        restored: list[str] = []
        for entry in reversed(entries):
            relative = str(entry["path"])
            target = workspace._safe_path(relative)

            if bool(entry.get("existed", False)):
                backup = Path(entry["backup_path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            elif target.exists():
                if target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)

            restored.append(relative)

        data.pop("_manifest_path", None)
        data["status"] = "UNDONE"
        data["undone_at"] = _utc_now()
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return UndoResult(
            True,
            task_id,
            "Transaction restored successfully.",
            list(reversed(restored)),
            str(workspace_path),
        )
