import json
import tempfile
import unittest
from pathlib import Path

from scripts.backup_store import WorkflowBackupStore


class WorkflowBackupStoreTests(unittest.TestCase):
    def test_save_and_reload_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowBackupStore(Path(tmpdir))
            workflow = {"id": "wf-1", "name": "Deploy site", "nodes": [], "connections": {}, "settings": {}}

            metadata = store.save_backup("wf-1", workflow)
            loaded = store.load_backup(metadata["backup_id"])

            self.assertEqual(loaded["workflow"]["name"], "Deploy site")
            self.assertEqual(loaded["metadata"]["workflow_id"], "wf-1")
            self.assertTrue(Path(metadata["path"]).exists())

    def test_list_backups_filters_by_workflow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = WorkflowBackupStore(Path(tmpdir))
            store.save_backup("wf-1", {"id": "wf-1", "name": "One"})
            store.save_backup("wf-2", {"id": "wf-2", "name": "Two"})

            backups = store.list_backups("wf-1")

            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0]["workflow_id"], "wf-1")


if __name__ == "__main__":
    unittest.main()
