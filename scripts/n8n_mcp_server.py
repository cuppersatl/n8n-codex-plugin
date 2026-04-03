from __future__ import annotations

import json
import os
import pathlib
import sys
import traceback
from typing import Any, Callable

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.backup_store import WorkflowBackupStore
from scripts.n8n_client import N8nClient, N8nConfig


def _tool(name: str, description: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "description": description, "inputSchema": schema}


def _compact_workflow_summary(workflow: dict[str, Any]) -> dict[str, Any]:
    tags = workflow.get("tags") or []
    return {
        "id": workflow.get("id"),
        "name": workflow.get("name"),
        "active": workflow.get("active"),
        "isArchived": workflow.get("isArchived"),
        "updatedAt": workflow.get("updatedAt"),
        "nodeCount": len(workflow.get("nodes") or []),
        "tags": [tag["name"] if isinstance(tag, dict) else tag for tag in tags],
    }


def _compact_execution_summary(execution: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": execution.get("id"),
        "workflowId": execution.get("workflowId"),
        "status": execution.get("status"),
        "mode": execution.get("mode"),
        "startedAt": execution.get("startedAt"),
        "stoppedAt": execution.get("stoppedAt"),
    }


def _workflow_diff(before: dict[str, Any], after: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    before_nodes = before.get("nodes") or []
    after_nodes = after.get("nodes") or []
    before_names = [node.get("name") for node in before_nodes if isinstance(node, dict)]
    after_names = [node.get("name") for node in after_nodes if isinstance(node, dict)]
    return {
        "workflow_id": workflow_id,
        "summary": {
            "nameChanged": before.get("name") != after.get("name"),
            "nodeCountBefore": len(before_nodes),
            "nodeCountAfter": len(after_nodes),
            "settingsChanged": (before.get("settings") or {}) != (after.get("settings") or {}),
        },
        "before": {
            "name": before.get("name"),
            "nodeNames": before_names,
            "settings": before.get("settings") or {},
        },
        "after": {
            "name": after.get("name"),
            "nodeNames": after_names,
            "settings": after.get("settings") or {},
        },
    }


def _render_tool_text(name: str, payload: dict[str, Any]) -> str:
    if name == "n8n_list_workflows":
        items = payload.get("data") or []
        lines = [f"{len(items)} workflow(s)"]
        for item in items:
            status = "active" if item.get("active") else "inactive"
            lines.append(
                f"- {item.get('name')} [{item.get('id')}] | {status} | nodes={item.get('nodeCount')}"
            )
        return "\n".join(lines)
    if name == "n8n_list_executions":
        items = payload.get("data") or []
        lines = [f"{len(items)} execution(s)"]
        for item in items:
            lines.append(
                f"- {item.get('id')} | workflow={item.get('workflowId')} | {item.get('status')} | {item.get('mode')}"
            )
        return "\n".join(lines)
    if name == "n8n_latest_failed_executions":
        items = payload.get("data") or []
        lines = [f"{len(items)} failed execution(s)"]
        for item in items:
            lines.append(
                f"- {item.get('id')} | workflow={item.get('workflowId')} | {item.get('status')} | {item.get('startedAt')}"
            )
        return "\n".join(lines)
    if name == "n8n_list_workflow_backups":
        items = payload.get("backups") or []
        lines = [f"{len(items)} backup(s)"]
        for item in items:
            lines.append(
                f"- {item.get('backup_id')} | workflow={item.get('workflow_id')} | {item.get('created_at')}"
            )
        return "\n".join(lines)
    if name == "n8n_diff_workflow_update":
        diff = payload.get("diff") or {}
        summary = diff.get("summary") or {}
        return "\n".join(
            [
                f"Workflow diff for {diff.get('workflow_id')}",
                f"- name changed: {summary.get('nameChanged')}",
                f"- nodes: {summary.get('nodeCountBefore')} -> {summary.get('nodeCountAfter')}",
                f"- settings changed: {summary.get('settingsChanged')}",
            ]
        )
    if name == "n8n_rename_workflow":
        updated = payload.get("updated_workflow") or {}
        return f"Renamed workflow {payload.get('workflow_id')} to {updated.get('name')}"
    return json.dumps(payload, indent=2, sort_keys=True)


class N8nMcpServer:
    def __init__(self, client: N8nClient | None, backup_store: WorkflowBackupStore):
        self.client = client
        self.backup_store = backup_store
        self.tools = {
            "n8n_health_check": self._health_check,
            "n8n_list_workflows": self._list_workflows,
            "n8n_get_workflow": self._get_workflow,
            "n8n_list_executions": self._list_executions,
            "n8n_get_execution": self._get_execution,
            "n8n_diff_workflow_update": self._diff_workflow_update,
            "n8n_latest_failed_executions": self._latest_failed_executions,
            "n8n_rename_workflow": self._rename_workflow,
            "n8n_update_workflow_full_json": self._update_workflow_full_json,
            "n8n_list_workflow_backups": self._list_workflow_backups,
            "n8n_restore_workflow_backup": self._restore_workflow_backup,
        }

    def handle_message_batch(self, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.handle_request(item) for item in payload]

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        request_id = request.get("id")

        if method == "initialize":
            return self._result(
                request_id,
                {
                    "protocolVersion": "2025-03-26",
                    "serverInfo": {"name": "n8n-readonly", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            )

        if method == "notifications/initialized":
            return {}

        if method == "tools/list":
            return self._result(request_id, {"tools": self._tool_definitions()})

        if method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            return self._call_tool(request_id, name, arguments)

        return self._error(request_id, -32601, f"Method not found: {method}")

    def _call_tool(self, request_id: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self.tools.get(name)
        if handler is None:
            return self._tool_error(request_id, f"Unknown tool: {name}")

        try:
            payload = handler(arguments)
        except Exception as exc:  # pragma: no cover
            return self._tool_error(request_id, f"{exc.__class__.__name__}: {exc}")

        text = _render_tool_text(name, payload)
        return self._result(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "structuredContent": payload,
                "isError": False,
            },
        )

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            _tool("n8n_health_check", "Verify connectivity to the configured n8n instance.", {"type": "object", "properties": {}}),
            _tool(
                "n8n_list_workflows",
                "List workflows from n8n with optional active/tag filters.",
                {
                    "type": "object",
                    "properties": {
                        "active": {"type": "boolean"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 250},
                        "cursor": {"type": "string"},
                    },
                },
            ),
            _tool(
                "n8n_get_workflow",
                "Fetch a single workflow by ID.",
                {
                    "type": "object",
                    "properties": {"workflow_id": {"type": "string"}},
                    "required": ["workflow_id"],
                },
            ),
            _tool(
                "n8n_list_executions",
                "List workflow executions with optional workflow/status filters.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "status": {"type": "string"},
                        "include_data": {"type": "boolean"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 250},
                        "cursor": {"type": "string"},
                    },
                },
            ),
            _tool(
                "n8n_get_execution",
                "Fetch a single execution by ID.",
                {
                    "type": "object",
                    "properties": {
                        "execution_id": {"type": "string"},
                        "include_data": {"type": "boolean"},
                    },
                    "required": ["execution_id"],
                },
            ),
            _tool(
                "n8n_diff_workflow_update",
                "Compare the current workflow with a proposed full JSON update without applying it.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "workflow": {"type": "object"},
                    },
                    "required": ["workflow_id", "workflow"],
                },
            ),
            _tool(
                "n8n_latest_failed_executions",
                "List the latest failed executions, optionally scoped to one workflow.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 250},
                    },
                },
            ),
            _tool(
                "n8n_rename_workflow",
                "Rename a workflow without manually editing a full workflow JSON payload.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "new_name": {"type": "string"},
                    },
                    "required": ["workflow_id", "new_name"],
                },
            ),
            _tool(
                "n8n_update_workflow_full_json",
                "Replace a workflow in n8n using the provided full workflow JSON. Saves a local backup first.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                        "workflow": {"type": "object"},
                    },
                    "required": ["workflow_id", "workflow"],
                },
            ),
            _tool(
                "n8n_list_workflow_backups",
                "List local backups created before workflow updates.",
                {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string"},
                    },
                },
            ),
            _tool(
                "n8n_restore_workflow_backup",
                "Restore a workflow by re-applying a saved local backup.",
                {
                    "type": "object",
                    "properties": {
                        "backup_id": {"type": "string"},
                    },
                    "required": ["backup_id"],
                },
            ),
        ]

    def _health_check(self, _: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        return self.client.health_check()

    def _list_workflows(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        payload = self.client.list_workflows(
            active=arguments.get("active"),
            tags=arguments.get("tags"),
            limit=arguments.get("limit"),
            cursor=arguments.get("cursor"),
        )
        workflows = payload.get("data") or []
        return {
            "data": [_compact_workflow_summary(workflow) for workflow in workflows],
            "nextCursor": payload.get("nextCursor"),
        }

    def _get_workflow(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        return self.client.get_workflow(arguments["workflow_id"])

    def _list_executions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        payload = self.client.list_executions(
            workflow_id=arguments.get("workflow_id"),
            status=arguments.get("status"),
            include_data=arguments.get("include_data", False),
            limit=arguments.get("limit"),
            cursor=arguments.get("cursor"),
        )
        executions = payload.get("data") or []
        return {
            "data": [_compact_execution_summary(item) for item in executions],
            "nextCursor": payload.get("nextCursor"),
        }

    def _get_execution(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        return self.client.get_execution(
            arguments["execution_id"],
            include_data=arguments.get("include_data", True),
        )

    def _update_workflow_full_json(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        workflow_id = arguments["workflow_id"]
        current = self.client.get_workflow(workflow_id)
        backup = self.backup_store.save_backup(workflow_id, current)
        updated = self.client.update_workflow(workflow_id, arguments["workflow"])
        return {
            "workflow_id": workflow_id,
            "backup": backup,
            "updated_workflow": updated,
        }

    def _diff_workflow_update(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        workflow_id = arguments["workflow_id"]
        current = self.client.get_workflow(workflow_id)
        proposed = arguments["workflow"]
        return {"diff": _workflow_diff(current, proposed, workflow_id)}

    def _latest_failed_executions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        payload = self.client.list_executions(
            workflow_id=arguments.get("workflow_id"),
            status="error",
            include_data=False,
            limit=arguments.get("limit"),
            cursor=None,
        )
        executions = payload.get("data") or []
        return {
            "data": [_compact_execution_summary(item) for item in executions],
            "nextCursor": payload.get("nextCursor"),
        }

    def _rename_workflow(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        workflow_id = arguments["workflow_id"]
        current = self.client.get_workflow(workflow_id)
        backup = self.backup_store.save_backup(workflow_id, current)
        updated = self.client.rename_workflow(workflow_id, arguments["new_name"])
        return {
            "workflow_id": workflow_id,
            "backup": backup,
            "updated_workflow": updated,
        }

    def _list_workflow_backups(self, arguments: dict[str, Any]) -> dict[str, Any]:
        backups = self.backup_store.list_backups(arguments.get("workflow_id"))
        return {"backups": backups}

    def _restore_workflow_backup(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_client()
        loaded = self.backup_store.load_backup(arguments["backup_id"])
        metadata = loaded["metadata"]
        restored = self.client.update_workflow(metadata["workflow_id"], loaded["workflow"])
        return {
            "restored_from": metadata["backup_id"],
            "workflow_id": metadata["workflow_id"],
            "restored_workflow": restored,
        }

    def _result(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

    def _tool_error(self, request_id: Any, message: str) -> dict[str, Any]:
        return self._result(
            request_id,
            {
                "content": [{"type": "text", "text": message}],
                "structuredContent": {"error": message},
                "isError": True,
            },
        )

    def _require_client(self) -> None:
        if self.client is None:
            raise RuntimeError(
                "n8n is not configured. Set N8N_BASE_URL and N8N_API_KEY before calling discovery tools."
            )


def _read_message() -> dict[str, Any] | list[dict[str, Any]] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return {}
    return json.loads(line)


def _write_message(payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def build_server_from_env() -> N8nMcpServer:
    base_url = os.environ.get("N8N_BASE_URL")
    api_key = os.environ.get("N8N_API_KEY")
    api_version = os.environ.get("N8N_API_VERSION", "v1")
    backup_root = pathlib.Path(
        os.environ.get("N8N_BACKUP_DIR", str(PLUGIN_ROOT / "backups"))
    )
    client = None
    if base_url and api_key:
        client = N8nClient(
            N8nConfig(base_url=base_url, api_key=api_key, api_version=api_version)
        )
    return N8nMcpServer(client=client, backup_store=WorkflowBackupStore(backup_root))


def main() -> int:
    server = build_server_from_env()

    while True:
        try:
            message = _read_message()
            if message is None:
                return 0
            if message == {}:
                continue
            if isinstance(message, list):
                _write_message(server.handle_message_batch(message))
            else:
                response = server.handle_request(message)
                if response:
                    _write_message(response)
        except json.JSONDecodeError as exc:
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
            )
        except Exception as exc:  # pragma: no cover
            traceback.print_exc(file=sys.stderr)
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32000, "message": f"{exc.__class__.__name__}: {exc}"},
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
