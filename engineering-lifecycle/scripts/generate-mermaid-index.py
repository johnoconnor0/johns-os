#!/usr/bin/env python3
"""Generate a Markdown index of Mermaid diagrams in the engineering workspace."""

from __future__ import annotations

import argparse

from eng_common import WORKSPACE, engineering_root, resolve_cli_root, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None)
    parser.add_argument("--out", default=str(WORKSPACE / "reports" / "mermaid-index.md").replace("\\", "/"))
    args = parser.parse_args()
    root = resolve_cli_root(args.root).root
    diagrams = sorted(engineering_root(root).rglob("*.mmd"))
    lines = ["# Mermaid Diagram Index", ""]
    if diagrams:
        for path in diagrams:
            rel = str(path.relative_to(root)).replace("\\", "/")
            lines.append(f"- `{rel}`")
    else:
        lines.append("No Mermaid diagrams found.")
    write_text(root / args.out, "\n".join(lines) + "\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
