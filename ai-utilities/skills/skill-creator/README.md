# Skill Creator

A Claude Code skill for creating, updating, validating, and packaging Claude Code skills and plugins.

This rebuild adds explicit plugin-awareness: skills, agents, hooks, MCP/LSP, monitors, channels, goals, prompt schedules, programmatic usage, plugin dependencies, semantic versioning, and profile-first software assurance plugin patterns.

Run the static validator with:

```bash
python3 scripts/check_claude_extension.py .
```

Official Claude validation should also be run where available:

```bash
claude plugin validate <plugin-path>
```
