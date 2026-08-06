# Tiny Plan

A deliberately small plan used as the audit's functional fixture. It exercises the
`numbered-headings` extractor, which is the shape the only real plan on record used
and the shape a checkbox-only parser finds nothing in.

## 1. Data layer

### 1.1 Add the greeting helper

Implement `greet` in the source tree.

### 1.2 Add the farewell helper

Implement `farewell`. Deliberately not implemented, so the fixture has one
`not-started` item to assert against.

## 2. Verification

### 2.1 Cover both helpers with tests

The fixture ships one test, covering only the first helper.

## Open Questions

- Should the fixture grow a third helper once the audit handles partial items?
