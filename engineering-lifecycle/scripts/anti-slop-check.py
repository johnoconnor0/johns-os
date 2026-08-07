#!/usr/bin/env python3
"""Find the mechanically detectable anti-slop patterns in generated UI.

Only the subset that can be established by inspection. Everything in
`references/anti-slop-register.md` that needs judgement is deliberately absent:
a checker that guesses produces noise, and noise gets ignored.

Findings are advisory. Each names the register entry so the override condition
can be checked before changing anything.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from eng_common import SCAN_PRUNE_DIRS, emit_json, engineering_root, relpath, repo_root, resolve_cli_root, workspace_exists, write_json

UI_SUFFIXES = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".css", ".scss", ".php"}

# (id, pattern, message, register section)
_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "em-dash",
        re.compile(r"[—–]"),
        "Em-dash or en-dash in visible copy. Use a period, comma, colon, or hyphen for ranges.",
        "6. Production Tells",
    ),
    (
        "pure-black",
        re.compile(r"#000000\b|#000\b(?![0-9a-fA-F])", re.IGNORECASE),
        "Pure black. Nothing physical is pure black; it reads as unset. Use zinc-950 or #0A0A0A.",
        "3. Colour",
    ),
    (
        "screen-height-hero",
        re.compile(r"\bh-screen\b|height:\s*100vh\b"),
        "Full-viewport height jumps on mobile when browser chrome collapses. Use min-h-[100dvh] / 100dvh.",
        "4. Layout",
    ),
    (
        "flex-percentage-math",
        re.compile(r"w-\[calc\(\s*\d+%"),
        "Flexbox percentage arithmetic where a grid expresses the intent. Use CSS Grid.",
        "4. Layout",
    ),
    (
        "placeholder-names",
        re.compile(r"\b(John|Jane)\s+(Doe|Smith)\b|\bSarah\s+Chan\b", re.IGNORECASE),
        "Placeholder name shipped as content. Use realistic, locale-appropriate names.",
        "5. Content Realism",
    ),
    (
        "placeholder-brands",
        re.compile(r"\b(Acme|Nexus|SmartFlow|Cloudly|Widgets?\s+Inc)\b", re.IGNORECASE),
        "Generated-sounding brand name. Invent one that sounds real in that market.",
        "5. Content Realism",
    ),
    (
        "lorem-ipsum",
        re.compile(r"\blorem\s+ipsum\b", re.IGNORECASE),
        "Lorem ipsum in a deliverable. Write plausible copy for the actual product.",
        "5. Content Realism",
    ),
    (
        "filler-verbs",
        re.compile(r"\b(elevate|seamless(?:ly)?|unleash|next-gen|revolutioni[sz]e|supercharge)\b", re.IGNORECASE),
        "Filler marketing verb that says nothing concrete.",
        "5. Content Realism",
    ),
    (
        "round-metrics",
        re.compile(r"\b99\.99%|\b1,?234,?567\b"),
        "Suspiciously round or sequential metric. Real data is messy.",
        "5. Content Realism",
    ),
    (
        "scroll-cue",
        re.compile(r">\s*(?:&darr;|↓)?\s*scroll(?:\s+(?:to\s+explore|down))?\s*<", re.IGNORECASE),
        "Scroll cue. The reader knows what scrolling is.",
        "6. Production Tells",
    ),
    (
        "section-number-eyebrow",
        re.compile(r">\s*0\d\s*[/·.\-]\s*[A-Za-z]", re.IGNORECASE),
        "Section-number eyebrow (001 / Capabilities). Name the topic in plain language.",
        "6. Production Tells",
    ),
    (
        "hand-rolled-icon",
        re.compile(r"<svg\b(?![^>]*\baria-hidden=\"false\")[^>]*>\s*<path\b"),
        "Hand-rolled SVG icon. Use one icon library (Phosphor, Hugeicons, Radix, Tabler).",
        "6. Production Tells",
    ),
    (
        "middle-dot-run",
        re.compile(r"·[^<\n]{1,40}·[^<\n]{1,40}·"),
        "Middle dot used as the universal separator. Maximum one per metadata line.",
        "6. Production Tells",
    ),
    (
        "version-stamp",
        re.compile(r">\s*v\d+\.\d+\.\d+(?:-\w+)?\s*<|>\s*Build\s+\d{3,}\s*<"),
        "Version stamp on a marketing surface. That is a devtool fixture.",
        "6. Production Tells",
    ),
]

# Three equal columns of the same fixed width is the classic feature row.
_THREE_EQUAL_CARDS = re.compile(r"grid-cols-3\b|repeat\(\s*3\s*,\s*(?:1fr|minmax)")


def scan_targets(root: Path, explicit: list[str]) -> list[Path]:
    if explicit:
        return [Path(item) if Path(item).is_absolute() else root / item for item in explicit]
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or len(found) >= 400:
            continue
        if set(path.parts) & SCAN_PRUNE_DIRS:
            continue
        if path.suffix.lower() in UI_SUFFIXES:
            found.append(path)
    return sorted(found)


def check_text(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    lines = text.splitlines()
    for rule_id, pattern, message, section in _RULES:
        for index, line in enumerate(lines, start=1):
            match = pattern.search(line)
            if match:
                findings.append(
                    {
                        "id": rule_id,
                        "line": index,
                        "match": match.group(0)[:80],
                        "message": message,
                        "register_section": section,
                    }
                )
                break  # one finding per rule per file is enough to act on
    for index, line in enumerate(lines, start=1):
        if _THREE_EQUAL_CARDS.search(line):
            findings.append(
                {
                    "id": "three-equal-cards",
                    "line": index,
                    "match": line.strip()[:80],
                    "message": (
                        "Three equal columns. Confirm the content genuinely has three peers of equal weight; "
                        "otherwise use a 2-column zig-zag, asymmetric grid, or horizontal scroll."
                    ),
                    "register_section": "1. The Default Reach",
                }
            )
            break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files to check. Defaults to UI files under --root.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--hook", action="store_true", help="Stay silent when nothing is found")
    args = parser.parse_args()
    root = resolve_cli_root(args.root).root

    results: list[dict[str, Any]] = []
    for path in scan_targets(root, args.paths):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings = check_text(text)
        if findings:
            results.append({"path": relpath(path, root), "findings": findings})

    total = sum(len(item["findings"]) for item in results)
    payload = {
        "files_with_findings": len(results),
        "finding_count": total,
        "results": results,
        "reference": "references/anti-slop-register.md",
        "note": "Advisory. Check each register entry's override condition before changing anything.",
    }
    if workspace_exists(root) and results:
        write_json(engineering_root(root) / "reports" / "validation" / "anti-slop.json", payload)
    if args.hook and not results:
        return 0
    emit_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
