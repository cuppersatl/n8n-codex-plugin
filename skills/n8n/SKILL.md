---
name: n8n
description: Use the local n8n MCP tools to inspect workflows and executions, apply full workflow JSON updates, and restore local backups.
---

# n8n Plugin Skill

Use this skill when the user wants help with their self-hosted n8n instance through the local plugin.

## What this plugin can do

- Inspect connectivity with `n8n_health_check`
- List workflows with `n8n_list_workflows`
- Inspect one workflow with `n8n_get_workflow`
- List executions with `n8n_list_executions`
- Inspect one execution with `n8n_get_execution`
- List the latest failures with `n8n_latest_failed_executions`
- Rename a workflow with `n8n_rename_workflow`
- Replace a workflow with full JSON via `n8n_update_workflow_full_json`
- List local backups with `n8n_list_workflow_backups`
- Restore a backup with `n8n_restore_workflow_backup`

## Working style

- Start with `n8n_list_workflows` for discovery.
- Use `n8n_latest_failed_executions` for the quickest debugging pass.
- Use `n8n_get_workflow` before proposing workflow edits.
- Use `n8n_rename_workflow` when the user only wants a name change.
- For updates, prefer minimal changes to an existing workflow JSON instead of rebuilding the whole object from scratch.
- Remind the user that updates create a local backup automatically.
- If the user wants rollback, use `n8n_list_workflow_backups` and `n8n_restore_workflow_backup`.

## Guardrails

- Treat `n8n_get_workflow` as the source of truth before editing.
- Do not assume the full GET response can be sent back unchanged; the plugin sanitizes workflow updates before sending them.
- Prefer explaining risky edits before applying them when the user has not explicitly asked for immediate changes.

## Good prompts

- "List my active n8n workflows and tell me which one looks like the meeting processor."
- "Show me the latest failed executions for workflow `eDFN7wmr8hNw2Ujp`."
- "Fetch workflow `eDFN7wmr8hNw2Ujp`, rename it, and update it."
- "Rename workflow `eDFN7wmr8hNw2Ujp` to `Meeting Memory`."
- "Show the latest failed executions for workflow `eDFN7wmr8hNw2Ujp`."
- "Restore the most recent backup for workflow `eDFN7wmr8hNw2Ujp`."
