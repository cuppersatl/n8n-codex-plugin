import json
import unittest

from scripts.n8n_mcp_server import N8nMcpServer


class StubClient:
    def __init__(self):
        self.updated = []

    def list_workflows(self, **kwargs):
        return {
            "data": [
                {
                    "id": "wf-1",
                    "name": "Deploy site",
                    "active": True,
                    "isArchived": False,
                    "updatedAt": "2026-04-02T16:28:56.000Z",
                    "tags": [{"name": "ops"}],
                    "nodes": [{}, {}, {}],
                }
            ],
            "nextCursor": None,
        }

    def get_workflow(self, workflow_id):
        return {
            "id": workflow_id,
            "name": "Deploy site",
            "nodes": [{"id": "1", "name": "Start"}],
            "connections": {},
            "settings": {"executionOrder": "v1"},
        }

    def list_executions(self, **kwargs):
        data = [
            {
                "id": "ex-1",
                "status": "success",
                "finished": True,
                "mode": "manual",
                "startedAt": "2026-04-02T16:00:00.000Z",
                "stoppedAt": "2026-04-02T16:00:05.000Z",
                "workflowId": "wf-1",
            },
            {
                "id": "ex-2",
                "status": "error",
                "finished": True,
                "mode": "trigger",
                "startedAt": "2026-04-02T17:00:00.000Z",
                "stoppedAt": "2026-04-02T17:00:07.000Z",
                "workflowId": "wf-1",
            },
        ]
        if kwargs.get("status"):
            data = [item for item in data if item["status"] == kwargs["status"]]
        if kwargs.get("workflow_id"):
            data = [item for item in data if item["workflowId"] == kwargs["workflow_id"]]
        return {
            "data": data,
            "nextCursor": None,
        }

    def get_execution(self, execution_id, include_data=True):
        return {"id": execution_id, "status": "success", "includeData": include_data}

    def health_check(self):
        return {"ok": True, "baseUrl": "https://example.n8n.cloud", "apiVersion": "v1"}

    def update_workflow(self, workflow_id, workflow):
        self.updated.append((workflow_id, workflow))
        return {"id": workflow_id, **workflow}

    def rename_workflow(self, workflow_id, new_name):
        self.updated.append((workflow_id, {"name": new_name}))
        return {"id": workflow_id, "name": new_name}


class StubBackupStore:
    def __init__(self):
        self.saved = []
        self.backups = {
            "backup-1": {
                "metadata": {
                    "backup_id": "backup-1",
                    "workflow_id": "wf-1",
                    "workflow_name": "Deploy site",
                    "path": "/tmp/backup-1.json",
                },
                "workflow": {"name": "Deploy site", "nodes": [], "connections": {}, "settings": {}},
            }
        }

    def save_backup(self, workflow_id, workflow):
        record = {
            "backup_id": "backup-1",
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name", ""),
            "path": "/tmp/backup-1.json",
        }
        self.saved.append((workflow_id, workflow))
        return record

    def list_backups(self, workflow_id=None):
        backups = [item["metadata"] for item in self.backups.values()]
        if workflow_id:
            backups = [item for item in backups if item["workflow_id"] == workflow_id]
        return backups

    def load_backup(self, backup_id):
        return self.backups[backup_id]


class N8nMcpServerTests(unittest.TestCase):
    def setUp(self):
        self.client = StubClient()
        self.backups = StubBackupStore()
        self.server = N8nMcpServer(client=self.client, backup_store=self.backups)

    def test_tools_list_includes_read_only_n8n_tools(self):
        response = self.server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )

        tool_names = [tool["name"] for tool in response["result"]["tools"]]
        self.assertEqual(
            tool_names,
            [
                "n8n_health_check",
                "n8n_list_workflows",
                "n8n_get_workflow",
                "n8n_list_executions",
                "n8n_get_execution",
                "n8n_diff_workflow_update",
                "n8n_latest_failed_executions",
                "n8n_rename_workflow",
                "n8n_update_workflow_full_json",
                "n8n_list_workflow_backups",
                "n8n_restore_workflow_backup",
            ],
        )

    def test_call_tool_returns_structured_content(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "n8n_get_workflow",
                    "arguments": {"workflow_id": "wf-1"},
                },
            }
        )

        self.assertEqual(response["result"]["isError"], False)
        self.assertEqual(response["result"]["structuredContent"]["id"], "wf-1")
        self.assertIn("Deploy site", response["result"]["content"][0]["text"])

    def test_list_workflows_returns_compact_summary_by_default(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "n8n_list_workflows",
                    "arguments": {"limit": 10},
                },
            }
        )

        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["data"][0]["id"], "wf-1")
        self.assertEqual(payload["data"][0]["nodeCount"], 3)
        self.assertEqual(payload["data"][0]["tags"], ["ops"])
        self.assertNotIn("nodes", payload["data"][0])
        self.assertIn("Deploy site", response["result"]["content"][0]["text"])
        self.assertIn("1 workflow", response["result"]["content"][0]["text"])

    def test_list_executions_returns_compact_summary_by_default(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {
                    "name": "n8n_list_executions",
                    "arguments": {"limit": 10},
                },
            }
        )

        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["data"][0]["id"], "ex-1")
        self.assertEqual(payload["data"][0]["status"], "success")
        self.assertNotIn("finished", payload["data"][0])
        self.assertIn("success", response["result"]["content"][0]["text"])

    def test_latest_failed_executions_filters_to_errors(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 23,
                "method": "tools/call",
                "params": {
                    "name": "n8n_latest_failed_executions",
                    "arguments": {"workflow_id": "wf-1", "limit": 5},
                },
            }
        )

        payload = response["result"]["structuredContent"]
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["status"], "error")
        self.assertIn("error", response["result"]["content"][0]["text"])

    def test_rename_workflow_tool_updates_name(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 24,
                "method": "tools/call",
                "params": {
                    "name": "n8n_rename_workflow",
                    "arguments": {"workflow_id": "wf-1", "new_name": "Deploy site TEST"},
                },
            }
        )

        payload = response["result"]["structuredContent"]
        self.assertEqual(payload["workflow_id"], "wf-1")
        self.assertEqual(payload["updated_workflow"]["name"], "Deploy site TEST")

    def test_unknown_tool_returns_error_result(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "missing_tool", "arguments": {}},
            }
        )

        self.assertEqual(response["result"]["isError"], True)
        self.assertIn("Unknown tool", response["result"]["content"][0]["text"])

    def test_update_tool_saves_backup_before_replacing_workflow(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "n8n_update_workflow_full_json",
                    "arguments": {
                        "workflow_id": "wf-1",
                        "workflow": {
                            "name": "Deploy site v2",
                            "nodes": [],
                            "connections": {},
                            "settings": {},
                        },
                    },
                },
            }
        )

        self.assertEqual(response["result"]["isError"], False)
        self.assertEqual(self.backups.saved[0][0], "wf-1")
        self.assertEqual(self.client.updated[0][0], "wf-1")
        self.assertEqual(
            response["result"]["structuredContent"]["backup"]["backup_id"],
            "backup-1",
        )

    def test_diff_tool_summarizes_top_level_changes(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "n8n_diff_workflow_update",
                    "arguments": {
                        "workflow_id": "wf-1",
                        "workflow": {
                            "name": "Deploy site TEST",
                            "nodes": [{"id": "1", "name": "Start"}, {"id": "2", "name": "Code"}],
                            "connections": {},
                            "settings": {"executionOrder": "v1"},
                        },
                    },
                },
            }
        )

        diff = response["result"]["structuredContent"]["diff"]
        self.assertEqual(diff["workflow_id"], "wf-1")
        self.assertEqual(diff["summary"]["nameChanged"], True)
        self.assertEqual(diff["summary"]["nodeCountBefore"], 1)
        self.assertEqual(diff["summary"]["nodeCountAfter"], 2)

    def test_restore_tool_reapplies_saved_backup(self):
        response = self.server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "n8n_restore_workflow_backup",
                    "arguments": {"backup_id": "backup-1"},
                },
            }
        )

        self.assertEqual(response["result"]["isError"], False)
        self.assertEqual(self.client.updated[0][0], "wf-1")
        self.assertEqual(response["result"]["structuredContent"]["restored_from"], "backup-1")

    def test_json_rpc_batch_is_supported(self):
        responses = self.server.handle_message_batch(
            [
                {"jsonrpc": "2.0", "id": 10, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "n8n_health_check", "arguments": {}},
                },
            ]
        )

        encoded = json.dumps(responses)
        self.assertIn('"id": 10', encoded)
        self.assertIn('"id": 11', encoded)


if __name__ == "__main__":
    unittest.main()
