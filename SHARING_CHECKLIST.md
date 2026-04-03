# n8n Shareable Export Checklist

This copy is scrubbed for sharing.

Removed from the export:

- local backups
- live workflow dumps
- ad hoc update payloads
- machine-specific cache files
- the AMMEGA local-drive workflow files with local path details

Still review before sharing:

- `.codex-plugin/plugin.json`
- `README.md`
- `skills/n8n/SKILL.md`

Recipient setup:

1. Put this folder under their local `plugins/` directory.
2. Add a workspace marketplace entry pointing to `./plugins/n8n`.
3. Set `N8N_BASE_URL` and `N8N_API_KEY`.
4. Restart or reopen Codex so the plugin is discovered.
