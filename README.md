# n8n Codex Plugin

Codex plugin for discovering workflows and executions in an n8n instance, then applying full workflow JSON updates through a local MCP server with automatic local backups.

## What it includes

- `n8n_health_check`
- `n8n_list_workflows`
- `n8n_get_workflow`
- `n8n_list_executions`
- `n8n_get_execution`
- `n8n_diff_workflow_update`
- `n8n_latest_failed_executions`
- `n8n_rename_workflow`
- `n8n_update_workflow_full_json`
- `n8n_list_workflow_backups`
- `n8n_restore_workflow_backup`

`n8n_list_workflows` returns a compact summary by default so large workflow definitions do not flood the terminal. Use `n8n_get_workflow` for the full workflow JSON.
`n8n_list_executions` also returns a compact summary by default.

## Environment

Set these before using the plugin:

```bash
export N8N_BASE_URL="https://your-instance.example.com"
export N8N_API_KEY="your-n8n-api-key"
export N8N_API_VERSION="v1"
export N8N_BACKUP_DIR="$PWD/backups"
```

`N8N_API_VERSION` is optional and defaults to `v1`.
`N8N_BACKUP_DIR` is optional and defaults to `./backups` inside the plugin root.

## Codex wiring

Register this plugin in your local workspace marketplace and point it at your own `plugins/n8n` path.

If it does not immediately appear in the Codex plugin UI, restart the app or reopen the workspace so the local marketplace is reloaded.

## Local verification

Run the tests from the plugin directory:

```bash
cd /path/to/your/plugins/n8n
python3 -m unittest discover -s tests -p 'test_*.py'
```

Smoke test the server:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 scripts/n8n_mcp_server.py
```

Test a live health check:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"n8n_health_check","arguments":{}}}' | python3 scripts/n8n_mcp_server.py
```

## Backups and restore

- Before every `n8n_update_workflow_full_json` call, the plugin fetches the current workflow and saves it locally.
- Backups are indexed in `backups/index.json` and stored as timestamped JSON files per workflow.
- `n8n_restore_workflow_backup` re-applies a saved backup to n8n.

Example update call:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"n8n_update_workflow_full_json","arguments":{"workflow_id":"123","workflow":{"name":"Example","nodes":[],"connections":{},"settings":{}}}}}' | python3 scripts/n8n_mcp_server.py
```

Preview a diff without applying it:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"n8n_diff_workflow_update","arguments":{"workflow_id":"123","workflow":{"name":"Example","nodes":[],"connections":{},"settings":{}}}}}' | python3 scripts/n8n_mcp_server.py
```

List latest failed executions:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"n8n_latest_failed_executions","arguments":{"workflow_id":"123","limit":5}}}' | python3 scripts/n8n_mcp_server.py
```

Rename a workflow:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":14,"method":"tools/call","params":{"name":"n8n_rename_workflow","arguments":{"workflow_id":"123","new_name":"Example Renamed"}}}' | python3 scripts/n8n_mcp_server.py
```

List backups:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"n8n_list_workflow_backups","arguments":{"workflow_id":"123"}}}' | python3 scripts/n8n_mcp_server.py
```

Restore a backup:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"n8n_restore_workflow_backup","arguments":{"backup_id":"123-20260402T120000Z-abcd1234"}}}' | python3 scripts/n8n_mcp_server.py
```

## Notes

- The server uses the n8n REST API and sends the API key in `X-N8N-API-KEY`.
- Full JSON updates apply directly to the target n8n instance.
- Rotate your API key if it has ever been hard-coded or exposed in logs/chat history.

## Sharing notes

- This export intentionally omits local backups, live workflow dumps, and environment-specific files.
- Review the metadata in `.codex-plugin/plugin.json` before publishing it to others.
- The recipient must provide their own `N8N_BASE_URL`, `N8N_API_KEY`, and optional `N8N_BACKUP_DIR`.
