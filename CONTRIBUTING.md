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

## Working on a plugin you have installed

Claude Code does not run a plugin from your working tree. It installs a
version-pinned copy under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`,
and because the `johns-os` marketplace is a git source, `claude plugin update`
fetches from GitHub rather than from disk.

The practical consequence: **editing a plugin file in this repo has no effect on
your session until the change is committed, pushed, and the plugin updated.** This
looks like aggressive caching, and the `__pycache__/*.pyc` and `.in_use/<pid>`
files in the install directory make it look like a Python problem. It is neither.
`.in_use/<pid>` is Claude Code's own session lock; leave it alone.

To see where the running copy came from and how far behind it is:

```powershell
python engineering-lifecycle/bin/eng-dev status
```

It prints the install path, the pinned commit, how many commits behind your
checkout it is, and the exact command sequence to resync. To clear regenerable
litter (`__pycache__`, `.pytest_cache`, a stray `.project`) from the installed
copy:

```powershell
python engineering-lifecycle/bin/eng-dev clean --apply
```

Hooks and CLI entrypoints invoke Python with `-B` so bytecode is never written
into an install directory in the first place. Keep that flag on any new
`subprocess` call that spawns a plugin script.

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
