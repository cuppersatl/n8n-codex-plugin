from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WorkflowBackupStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.json"

    def save_backup(self, workflow_id: str, workflow: dict[str, Any]) -> dict[str, Any]:
        workflow_name = workflow.get("name", "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_id = f"{workflow_id}-{timestamp}-{uuid.uuid4().hex[:8]}"
        workflow_dir = self.root / workflow_id
        workflow_dir.mkdir(parents=True, exist_ok=True)
        backup_path = workflow_dir / f"{backup_id}.json"

        with backup_path.open("w") as handle:
            json.dump(workflow, handle, indent=2)
            handle.write("\n")

        metadata = {
            "backup_id": backup_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "path": str(backup_path),
            "created_at": timestamp,
        }
        index = self._load_index()
        index.insert(0, metadata)
        self._write_index(index)
        return metadata

    def list_backups(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        backups = self._load_index()
        if workflow_id is None:
            return backups
        return [item for item in backups if item["workflow_id"] == workflow_id]

    def load_backup(self, backup_id: str) -> dict[str, Any]:
        for metadata in self._load_index():
            if metadata["backup_id"] == backup_id:
                with Path(metadata["path"]).open() as handle:
                    workflow = json.load(handle)
                return {"metadata": metadata, "workflow": workflow}
        raise KeyError(f"Backup not found: {backup_id}")

    def _load_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        with self.index_path.open() as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise ValueError(f"Backup index must be a list: {self.index_path}")
        return payload

    def _write_index(self, backups: list[dict[str, Any]]) -> None:
        with self.index_path.open("w") as handle:
            json.dump(backups, handle, indent=2)
            handle.write("\n")
