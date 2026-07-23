## Summary

<!-- What changed and why? -->

## Scope

- [ ] Marketplace or plugin metadata
- [ ] Runtime/plugin behavior
- [ ] Documentation
- [ ] Development tooling or workflow

## Validation

```text
python -m pip install -r requirements-dev.txt
pre-commit run --all-files
python scripts/validate-repo.py
```

Paste the actual results or explain any unavailable check.

## Public-repo safety

- [ ] No secrets, credentials, private URLs, or personal data added.
- [ ] `_unreleased/` and `.project/` remain outside the public source boundary.
- [ ] Marketplace versions, names, paths, and manifests are consistent.
