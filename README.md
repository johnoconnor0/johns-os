# johns-os

[![npm](https://img.shields.io/npm/v/johns-os?logo=npm)](https://www.npmjs.com/package/johns-os)
[![CI](https://github.com/johnoconnor0/johns-os/actions/workflows/ci.yml/badge.svg)](https://github.com/johnoconnor0/johns-os/actions/workflows/ci.yml)
[![E2E](https://github.com/johnoconnor0/johns-os/actions/workflows/e2e.yml/badge.svg)](https://github.com/johnoconnor0/johns-os/actions/workflows/e2e.yml)
[![License: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

`johns-os` is a public Claude Code and Codex plugin marketplace for practical software delivery, business development, and AI-assisted repository work.

Website: [weblifter.com.au](https://weblifter.com.au)
Repository: [github.com/johnoconnor0/johns-os](https://github.com/johnoconnor0/johns-os)

## Active plugins

| Plugin | Version | Role |
| --- | --- | --- |
| `engineering-lifecycle` | 0.8.0 | Structured discovery, requirements, UX, design systems, architecture, data modelling, API contracts, implementation, review, testing, release, and repository hygiene. |
| `business-development` | 0.2.0 | Interview-first Service Outline generation and updating. |
| `ai-utilities` | 0.1.0 | Claude Code extension authoring/review and plan-completion auditing. |

Plugin candidates under `_unreleased/` are intentionally excluded from active marketplace metadata until they are reviewed and promoted.

## Installation

### CLI (any platform)

The quickest route. Published to npm as [`johns-os`](https://www.npmjs.com/package/johns-os), so it runs without installing anything first:

```bash
npx johns-os install
```

Other commands:

```bash
npx johns-os list
```

```bash
npx johns-os update
```

```bash
npx johns-os init
```

```bash
npx johns-os doctor
```

`install` accepts specific plugin names and a `--scope user|project|local` flag (default `user`). `init` creates the Engineering Lifecycle workspace in the current repository, and `doctor` reports where the running copy came from and whether it is stale. Requires Node.js 18 or newer. See [`cli/README.md`](cli/README.md).

Install it globally instead if you prefer:

```bash
npm install -g johns-os
```

Each release is published from CI with [SLSA build provenance](https://registry.npmjs.org/-/npm/v1/attestations/johns-os@0.3.0), so the package on the registry is verifiable against the commit and workflow that built it:

```bash
npm audit signatures
```

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
| Installer CLI | `cli/` | Source of the [`johns-os`](https://www.npmjs.com/package/johns-os) npm package, published from `publish-cli.yml` with build provenance. |
| Repository tooling | `scripts/`, `tests/` | Cross-surface validation and its test suite. |
| Continuous integration | `.github/workflows/` | `ci.yml` (lint, format, validation, suites), `e2e.yml` (browser coverage), `publish-cli.yml`. |
| Public docs | `CONTRIBUTING.md`, `SECURITY.md`, `SUPPORT.md` | Contribution, safety, and support guidance. |
| Generated lifecycle state | `.project/` | Local-only state; ignored and not required for installation. |

The three marketplace surfaces are deliberately maintained side by side rather than generated from a single file: Claude Code and Codex do not accept identical metadata, and the local catalog exists so discovery and validation stay deterministic without either vendor's tooling. Cross-surface consistency is enforced by `scripts/johns-os-marketplace.py validate`, which runs in CI.

## Development setup

Requires Python 3.12 or newer, Git, and Node.js 18 or newer for the CLI and E2E suites.

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
```

```powershell
python scripts/validate-repo.py
```

Individual checks:

```powershell
ruff check .
```

```powershell
ruff format --check .
```

```powershell
yamllint .
```

```powershell
python scripts/johns-os-marketplace.py validate
```

```powershell
python engineering-lifecycle/bin/eng-life validate
```

```powershell
python -m unittest discover -s tests
```

```powershell
python -m unittest discover -s engineering-lifecycle/tests
```

```powershell
python -m compileall -q .
```

The deterministic suite does not require API keys or external services. Optional live council adapters are configured through local environment variables described in the repository's env template; never commit real values.

Browser coverage for the generated project dashboard lives in `engineering-lifecycle/tests/e2e/` and runs separately, since it needs a browser:

```bash
cd engineering-lifecycle/tests/e2e && npm install && npm run test:install && npm run fixture && npm test
```

## Contributing

CI runs on Ubuntu and Windows across Python 3.12 and 3.13, and `main` is protected: changes land through a pull request with those checks green. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening one.

## Documentation and support

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## Licence

This repository is released under the MIT licence. See [LICENSE](LICENSE).
