# Contributing

Thanks for helping improve `johns-os`. The repository contains three active plugins and separate Claude Code, Codex, and local marketplace metadata.

## Development setup

Requires Python 3.12 or newer and Git.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pre-commit install --install-hooks
```

On macOS/Linux, activate the environment with `source .venv/bin/activate`.

## Required checks

```powershell
pre-commit run --all-files
python scripts/validate-repo.py
```

The repository validation command covers marketplace records, plugin/schema validation, both test suites, and Python compilation. Do not claim checks passed unless they were actually run.

## Plugin changes

1. Keep each active plugin self-contained under its own directory.
2. Update both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` when metadata or behavior affects both platforms.
3. Update `.claude-plugin/marketplace.json`, `marketplace.json`, `.agents/plugins/marketplace.json`, and `marketplace/plugins/` when adding or releasing an active plugin.
4. Keep `_unreleased/` out of active marketplace manifests until the plugin has been reviewed and intentionally promoted.
5. Add or update tests and plugin documentation with the change.

## Documentation and safety

- Use Australian English where existing plugin documentation does.
- Document verified commands and mark unknown ownership, deployment, or release details explicitly.
- Never commit credentials, local `.env` files, generated `.project/` state, or private customer data.
- Report security issues privately as described in [SECURITY.md](SECURITY.md).

Pull requests should explain the scope, list actual validation results, and identify any residual risk or unresolved release question.
