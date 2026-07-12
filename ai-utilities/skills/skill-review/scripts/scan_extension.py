#!/usr/bin/env python3
"""
scan_extension.py — deterministic static scanner for Claude Code extensions.

Inventories a marketplace / plugin / skill and emits the mechanical signals the
skill-review workflow reasons over: manifest & frontmatter validity, declared
tools, MCP servers, network endpoints, dangerous code patterns, and candidate
secrets. Stdlib-only, cross-platform (Windows/macOS/Linux). Read-only.

Usage:
    python3 scan_extension.py <path> [--json]

Exit codes: 0 = scan completed (findings may still exist), 2 = bad usage/path.
This is a signal generator, NOT a verdict. The model applies the rubric.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
URL = re.compile(r"https?://[^\s\"'`)>\]]+", re.I)

# Files worth scanning for code-level signals.
CODE_EXT = {".py", ".js", ".ts", ".mjs", ".cjs", ".sh", ".bash", ".zsh",
            ".ps1", ".rb", ".go", ".json", ".md", ".yaml", ".yml", ".toml"}

# Dangerous code patterns → (rule_id, gate, description). Gate maps to framework hard-fails.
DANGER_PATTERNS = [
    (re.compile(r"curl\s+[^\n|]*\|\s*(sh|bash|zsh)", re.I), "REMOTE_EXEC_CURL", "G2", "pipe curl into a shell"),
    (re.compile(r"wget\s+[^\n|]*\|\s*(sh|bash|zsh)", re.I), "REMOTE_EXEC_WGET", "G2", "pipe wget into a shell"),
    (re.compile(r"\beval\s*\(", re.I), "EVAL_CALL", "G2", "eval() — check if input is remote/untrusted"),
    (re.compile(r"\bexec\s*\(", re.I), "EXEC_CALL", "G2", "exec() — check if input is remote/untrusted"),
    (re.compile(r"subprocess\.[a-z_]+\([^)]*shell\s*=\s*True", re.I), "SHELL_TRUE", "G4", "subprocess shell=True"),
    (re.compile(r"os\.system\s*\(", re.I), "OS_SYSTEM", "G4", "os.system() shell call"),
    (re.compile(r"\b(pip|pip3)\s+install\b", re.I), "RUNTIME_PIP", "G2", "runtime pip install (pin & vet source)"),
    (re.compile(r"\bnpm\s+(install|i)\b", re.I), "RUNTIME_NPM", "G2", "runtime npm install (pin & vet source)"),
    (re.compile(r"import\s*\(\s*[\"'`]https?://", re.I), "DYNAMIC_URL_IMPORT", "G2", "dynamic import from URL"),
    (re.compile(r"base64\.\w*decode\w*\([^)]*\)\s*\)?\s*(?:\.decode\(\))?\s*", re.I), "BASE64_DECODE", "none", "base64 decode — inspect what is decoded"),
    (re.compile(r"\brm\s+-rf\b", re.I), "RM_RF", "G4", "rm -rf — destructive"),
    (re.compile(r"\b(DROP|TRUNCATE|DELETE)\s+(TABLE|FROM)\b", re.I), "SQL_DESTRUCTIVE", "G4", "destructive SQL"),
    (re.compile(r"169\.254\.169\.254"), "METADATA_IP", "none", "cloud metadata endpoint reference"),
    (re.compile(r"pickle\.loads?\s*\(", re.I), "PICKLE_LOAD", "none", "unsafe deserialisation (pickle)"),
]

# Candidate secret patterns → (rule_id, description). Regex-based; model confirms.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "PRIVATE_KEY", "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS_ACCESS_KEY", "AWS access key id"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "OPENAI_KEY", "sk- style API key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"), "ANTHROPIC_KEY", "Anthropic api key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "GITHUB_PAT", "GitHub personal access token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), "SLACK_TOKEN", "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "GOOGLE_API_KEY", "Google API key"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "JWT", "JWT (may be a live token)"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"), "GENERIC_SECRET", "assigned secret-like literal"),
]

# Assignment-context guards to reduce false positives on obvious placeholders.
PLACEHOLDER = re.compile(r"(?i)(your[_-]?|example|placeholder|dummy|xxxx|<[^>]+>|\.\.\.|changeme|redacted|\bENV\b|process\.env|os\.environ)")

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_frontmatter(text: str):
    """Minimal YAML frontmatter parser (flat keys), matching the validator style."""
    if not text.startswith("---\n"):
        return None, "missing YAML frontmatter"
    end = text.find("\n---", 4)
    if end == -1:
        return None, "unterminated YAML frontmatter"
    raw = text[4:end]
    data = {}
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip().strip('"').strip("'")
    return data, None


def split_tools(val: str):
    if not val:
        return []
    return [t.strip() for t in val.split(",") if t.strip()]


def scan_file_signals(p: Path, rel: str):
    """Return (dangers, secrets, endpoints) for one file."""
    dangers, secrets, endpoints = [], [], []
    text = read_text(p)
    if not text:
        return dangers, secrets, endpoints
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for rx, rule, gate, desc in DANGER_PATTERNS:
            if rx.search(line):
                dangers.append({"rule": rule, "gate": gate, "desc": desc,
                                "ref": f"{rel}:{i}", "line": line.strip()[:200]})
        for rx, rule, desc in SECRET_PATTERNS:
            m = rx.search(line)
            if m and not PLACEHOLDER.search(line):
                secrets.append({"rule": rule, "desc": desc, "ref": f"{rel}:{i}",
                                "match": m.group(0)[:12] + "…"})
    for m in URL.finditer(text):
        endpoints.append(m.group(0).rstrip(".,);"))
    return dangers, secrets, endpoints


def collect_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in CODE_EXT or p.name in {"SKILL.md", "plugin.json", "marketplace.json"}:
            yield p


def scan_skill(skill_dir: Path, root: Path):
    md = skill_dir / "SKILL.md"
    rel = str(md.relative_to(root)) if md.is_relative_to(root) else str(md)
    entry = {"type": "skill", "path": str(skill_dir), "skill_md": rel,
             "name": None, "description": None, "allowed_tools": [],
             "argument_hint": None, "issues": []}
    if not md.exists():
        entry["issues"].append("missing SKILL.md")
        return entry
    fm, err = parse_frontmatter(read_text(md))
    if err:
        entry["issues"].append(f"frontmatter: {err}")
        return entry
    entry["name"] = fm.get("name")
    entry["description"] = fm.get("description")
    entry["argument_hint"] = fm.get("argument-hint")
    entry["allowed_tools"] = split_tools(fm.get("allowed-tools", ""))
    if entry["name"] and not KEBAB.match(entry["name"]):
        entry["issues"].append(f"name not kebab-case: {entry['name']}")
    if entry["name"] and skill_dir.name != entry["name"]:
        entry["issues"].append(f"dir '{skill_dir.name}' != name '{entry['name']}'")
    if not entry["description"]:
        entry["issues"].append("missing description")
    # Unrestricted Bash / broad tool flags
    for t in entry["allowed_tools"]:
        if t == "Bash" or t.strip() == "Bash(*)" or t == "Bash(*:*)":
            entry["issues"].append(f"unrestricted Bash tool grant: {t}")
    line_count = len(read_text(md).splitlines())
    if line_count > 500:
        entry["issues"].append(f"SKILL.md {line_count} lines (>500)")
    return entry


def scan_plugin(plugin_root: Path, root: Path):
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    entry = {"type": "plugin", "path": str(plugin_root), "name": None,
             "version": None, "mcp_servers": [], "components": {}, "issues": []}
    try:
        data = json.loads(read_text(manifest))
    except Exception as e:
        entry["issues"].append(f"invalid plugin.json: {e}")
        return entry
    entry["name"] = data.get("name")
    entry["version"] = data.get("version")
    if not entry["name"] or not KEBAB.match(str(entry["name"])):
        entry["issues"].append("plugin name missing/not kebab-case")
    if entry["version"] and not SEMVER.match(str(entry["version"])):
        entry["issues"].append(f"version not semver: {entry['version']}")
    mcp = data.get("mcpServers")
    if isinstance(mcp, dict):
        entry["mcp_servers"] = list(mcp.keys())
    elif isinstance(mcp, str):
        entry["mcp_servers"] = [mcp]
    for key in ["skills", "agents", "hooks", "commands", "mcpServers", "lspServers"]:
        v = data.get(key)
        if isinstance(v, str):
            exists = (plugin_root / v).exists()
            entry["components"][key] = {"path": v, "exists": exists}
            if not exists:
                entry["issues"].append(f"{key} path missing: {v}")
    return entry


def scan_marketplace(mp_path: Path):
    entry = {"type": "marketplace", "path": str(mp_path), "plugins": [], "issues": []}
    try:
        data = json.loads(read_text(mp_path))
    except Exception as e:
        entry["issues"].append(f"invalid marketplace.json: {e}")
        return entry
    plugins = data.get("plugins") or data.get("entries") or []
    if isinstance(plugins, list):
        for pl in plugins:
            if isinstance(pl, dict):
                src = pl.get("source") or pl.get("url") or pl.get("path") or ""
                mutable = bool(re.search(r"(latest|main|master|@)\b", str(src))) and "#" not in str(src)
                entry["plugins"].append({"name": pl.get("name"), "source": src,
                                         "mutable_source": mutable})
                if mutable:
                    entry["issues"].append(f"mutable/unpinned source for {pl.get('name')}: {src}")
    else:
        entry["issues"].append("plugins field is not a list")
    return entry


def main(argv):
    args = [a for a in argv[1:] if a != "--json"]
    if len(args) != 1:
        print("usage: scan_extension.py <path> [--json]", file=sys.stderr)
        return 2
    root = Path(args[0]).resolve()
    if not root.exists():
        print(f"ERROR: path does not exist: {root}", file=sys.stderr)
        return 2

    result = {"root": str(root), "marketplaces": [], "plugins": [], "skills": [],
              "dangers": [], "secrets": [], "endpoints": [], "summary": {}}

    # Marketplaces
    for mp in list(root.rglob("marketplace.json")):
        if any(part in IGNORE_DIRS for part in mp.parts):
            continue
        result["marketplaces"].append(scan_marketplace(mp))

    # Plugins
    for manifest in list(root.rglob("plugin.json")):
        if manifest.parent.name != ".claude-plugin":
            continue
        result["plugins"].append(scan_plugin(manifest.parent.parent, root))

    # Skills
    for md in list(root.rglob("SKILL.md")):
        if any(part in IGNORE_DIRS for part in md.parts):
            continue
        result["skills"].append(scan_skill(md.parent, root))

    # File-level signals
    endpoints = set()
    for p in collect_files(root):
        rel = str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
        d, s, e = scan_file_signals(p, rel)
        result["dangers"].extend(d)
        result["secrets"].extend(s)
        endpoints.update(e)
    result["endpoints"] = sorted(endpoints)

    result["summary"] = {
        "marketplaces": len(result["marketplaces"]),
        "plugins": len(result["plugins"]),
        "skills": len(result["skills"]),
        "danger_hits": len(result["dangers"]),
        "gate_hits": sorted({d["gate"] for d in result["dangers"] if d["gate"] != "none"}),
        "secret_candidates": len(result["secrets"]),
        "unique_endpoints": len(result["endpoints"]),
        "manifest_issues": sum(len(x["issues"]) for x in
                               result["marketplaces"] + result["plugins"] + result["skills"]),
    }

    if "--json" in argv:
        print(json.dumps(result, indent=2))
    else:
        s = result["summary"]
        print(f"Scanned: {root}")
        print(f"  marketplaces={s['marketplaces']} plugins={s['plugins']} skills={s['skills']}")
        print(f"  danger_hits={s['danger_hits']} gates={s['gate_hits']} "
              f"secret_candidates={s['secret_candidates']} endpoints={s['unique_endpoints']} "
              f"manifest_issues={s['manifest_issues']}")
        if result["dangers"]:
            print("\nDanger patterns:")
            for d in result["dangers"][:50]:
                print(f"  [{d['gate']:4}] {d['rule']} @ {d['ref']} — {d['desc']}")
        if result["secrets"]:
            print("\nSecret candidates (confirm manually):")
            for sc in result["secrets"][:50]:
                print(f"  {sc['rule']} @ {sc['ref']} ({sc['match']}) — {sc['desc']}")
        print("\nNOTE: signals only, not a verdict. Apply the rubric in evaluation-framework.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
