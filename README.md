# n8n Codex Plugin

Codex plugin for inspecting n8n workflows and executions, previewing workflow diffs, applying workflow updates, and restoring local backups.

## Quick install

1. Copy this folder into your local Codex `plugins/` directory as `plugins/n8n`.
2. Add a local marketplace entry that points to `./plugins/n8n`.
3. Set your n8n environment variables:

```bash
export N8N_BASE_URL="https://your-instance.example.com"
export N8N_API_KEY="your-n8n-api-key"
export N8N_API_VERSION="v1"
export N8N_BACKUP_DIR="$PWD/backups"
```

4. Restart Codex or reopen the workspace so the plugin is discovered.

## What it does

- List workflows with compact summaries
- Inspect a full workflow by ID
- List executions with compact summaries
- Show the latest failed executions for a workflow
- Preview a workflow diff before applying changes
- Rename a workflow
- Apply full workflow JSON updates
- Save a local backup before updates
- Restore a workflow from a local backup

## Common prompts

- `List my active n8n workflows.`
- `Show recent failed n8n executions.`
- `Show the latest failed executions for workflow eDFN7wmr8hNw2Ujp.`
- `Inspect workflow eDFN7wmr8hNw2Ujp.`
- `Rename workflow eDFN7wmr8hNw2Ujp to Meeting Memory.`
- `Diff this workflow update against eDFN7wmr8hNw2Ujp before applying it.`

## Tools included

- `n8n_health_check`
- `n8n_list_workflows`
- `n8n_get_workflow`
- `n8n_list_executions`
- `n8n_get_execution`
- `n8n_latest_failed_executions`
- `n8n_diff_workflow_update`
- `n8n_rename_workflow`
- `n8n_update_workflow_full_json`
- `n8n_list_workflow_backups`
- `n8n_restore_workflow_backup`

`n8n_list_workflows` and `n8n_list_executions` return compact summaries by default. Use `n8n_get_workflow` and `n8n_get_execution` when you need the full payload.

## Local verification

From the plugin directory:

```bash
cd /path/to/your/plugins/n8n
python3 -m unittest discover -s tests -p 'test_*.py'
```

Smoke test the MCP server:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 scripts/n8n_mcp_server.py
```

Live health check:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"n8n_health_check","arguments":{}}}' | python3 scripts/n8n_mcp_server.py
```

## Update flow

Preview a diff without applying it:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"n8n_diff_workflow_update","arguments":{"workflow_id":"123","workflow":{"name":"Example","nodes":[],"connections":{},"settings":{}}}}}' | python3 scripts/n8n_mcp_server.py
```

Apply an update with automatic backup:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"n8n_update_workflow_full_json","arguments":{"workflow_id":"123","workflow":{"name":"Example","nodes":[],"connections":{},"settings":{}}}}}' | python3 scripts/n8n_mcp_server.py
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
- Full workflow updates are sanitized before being sent, so n8n-managed fields from `get_workflow` are not blindly replayed.
- Backups are stored locally and are not included in this shared export.
- Use your own `N8N_BASE_URL`, `N8N_API_KEY`, and optional `N8N_BACKUP_DIR`.
