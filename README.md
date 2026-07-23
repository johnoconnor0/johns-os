# johns-os

`johns-os` is a public-ready Claude Code and Codex plugin marketplace for practical software delivery, business development, and AI-assisted repository work.

Website: [weblifter.com.au](https://weblifter.com.au)
Repository: [github.com/johnoconnor0/johns-os](https://github.com/johnoconnor0/johns-os)

## Active plugins

- `engineering-lifecycle`: structured discovery, requirements, UX, architecture, implementation, testing, release, and repository-hygiene workflows.
- `business-development`: interview-first Service Outline generation and updating.
- `ai-utilities`: Claude Code extension authoring/review and plan-completion auditing utilities.

Plugin candidates under `_unreleased/` are intentionally excluded from active marketplace metadata until they are reviewed and promoted.

## Installation

### Claude Code

```text
/plugin marketplace add johnoconnor0/johns-os
/plugin install engineering-lifecycle@johns-os
```

Install `business-development` or `ai-utilities` by substituting the plugin name. For local development:

```text
/plugin marketplace add ./johns-os
```

### Codex

The Codex marketplace manifests are `marketplace.json` and `.agents/plugins/marketplace.json`. Use the marketplace discovery flow supported by your Codex installation against a clone of this repository.

## Repository architecture

| Surface | Location | Role |
| --- | --- | --- |
| Claude Code marketplace | `.claude-plugin/marketplace.json` | Authoritative Claude marketplace metadata. |
| Codex marketplace | `marketplace.json`, `.agents/plugins/marketplace.json` | Codex discovery metadata. |
| Local catalog | `marketplace/catalog.json`, `marketplace/plugins/` | Deterministic repository discovery and validation. |
| Active plugins | `engineering-lifecycle/`, `business-development/`, `ai-utilities/` | Self-contained plugin source and manifests. |
| Public docs | `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md` | Contribution, safety, and support guidance. |
| Generated lifecycle state | `.project/` | Local-only state; ignored and not required for installation. |

## Development setup

Requires Python 3.12 or newer and Git.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pre-commit install --install-hooks
```

On macOS/Linux, activate the environment with `source .venv/bin/activate`.

## Quality checks

Run the complete deterministic suite from the repository root:

```powershell
pre-commit run --all-files
python scripts/validate-repo.py
```

Individual checks:

```powershell
ruff check .
ruff format --check .
yamllint .
python scripts/johns-os-marketplace.py validate
python engineering-lifecycle/bin/eng-life validate
python -m unittest discover -s tests
python -m unittest discover -s engineering-lifecycle/tests
python -m compileall -q .
```

The deterministic suite does not require API keys or external services. Optional live council adapters are configured through local environment variables described in `.env.example`; never commit real values.

## Documentation and support

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Licence

This repository is released under the MIT licence. See [LICENSE](LICENSE).
