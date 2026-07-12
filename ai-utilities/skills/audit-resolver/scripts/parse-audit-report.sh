#!/usr/bin/env bash
# parse-audit-report.sh — Extract findings from a plan-completion-audit report.
#
# Usage:
#   bash parse-audit-report.sh <report.md>
#
# Output (TSV on stdout): id<TAB>severity<TAB>phase<TAB>file<TAB>line<TAB>description
#
# Heuristic, not a strict parser. The audit report is markdown — we look for:
#   - "## Phase N" or "### Phase N" headings to track current phase
#   - Inline severity tokens: CRITICAL / WARNING / SUGGESTION (case-insensitive)
#   - File:line patterns like `path/file.ext:42`
#   - Table rows where the first cell looks like a numbered ID
#
# Findings not matched by the heuristic are emitted with empty fields rather than dropped.
# The calling skill should sanity-check the output count vs a manual scan.

set -e

REPORT="${1:-}"
if [ -z "$REPORT" ] || [ ! -f "$REPORT" ]; then
  echo "Usage: bash parse-audit-report.sh <report.md>" >&2
  echo "ERROR: report not found: $REPORT" >&2
  exit 1
fi

# State
PHASE=""
ID_COUNTER=0
in_table=0

# Process line by line
while IFS= read -r line; do
  # Track current phase
  if echo "$line" | grep -qE '^##+ Phase [0-9]+'; then
    PHASE=$(echo "$line" | sed -E 's/^##+ Phase ([0-9]+).*$/\1/')
    continue
  fi

  # Detect table rows that look like findings
  # A finding row typically: | (id) | (severity) | (file:line) | (description) |
  if echo "$line" | grep -qE '^\|.+\|.+CRITICAL|^\|.+\|.+WARNING|^\|.+\|.+SUGGESTION'; then
    severity=$(echo "$line" | grep -oiE 'CRITICAL|WARNING|SUGGESTION' | head -1 | tr '[:lower:]' '[:upper:]')
    # Extract file:line — try to find first occurrence of path:line pattern in the row
    fileline=$(echo "$line" | grep -oE '[a-zA-Z0-9_./\\-]+\.[a-zA-Z]+(:[0-9]+)?' | head -1)
    file=""
    line_num=""
    if [ -n "$fileline" ]; then
      file=$(echo "$fileline" | cut -d: -f1)
      line_num=$(echo "$fileline" | cut -d: -f2 -s)
    fi
    # Description = the line stripped of leading | + first 2 cells
    desc=$(echo "$line" | sed -E 's/^\|[^|]*\|[^|]*\|//; s/\|.*$//; s/^ +//; s/ +$//')
    ID_COUNTER=$((ID_COUNTER + 1))
    id=$(printf "F%03d" "$ID_COUNTER")
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$id" "$severity" "$PHASE" "$file" "$line_num" "$desc"
    continue
  fi

  # Detect bullet-style findings (older audit format)
  # Example: - **W1:** `path/to/file.ts:42` — description
  if echo "$line" | grep -qE '^[-*] +\*\*[WCSwcs][0-9]+:?\*\*'; then
    severity_letter=$(echo "$line" | grep -oE '\*\*[WCSwcs][0-9]+' | head -1 | sed -E 's/\*\*//; s/[0-9]+//')
    case "${severity_letter^^}" in
      C) severity="CRITICAL" ;;
      W) severity="WARNING" ;;
      S) severity="SUGGESTION" ;;
      *) severity="UNKNOWN" ;;
    esac
    fileline=$(echo "$line" | grep -oE '`[a-zA-Z0-9_./\\-]+\.[a-zA-Z]+(:[0-9]+)?`' | head -1 | tr -d '`')
    file=""
    line_num=""
    if [ -n "$fileline" ]; then
      file=$(echo "$fileline" | cut -d: -f1)
      line_num=$(echo "$fileline" | cut -d: -f2 -s)
    fi
    desc=$(echo "$line" | sed -E 's/^[-*] +\*\*[WCSwcs][0-9]+:?\*\* *//; s/ +$//')
    ID_COUNTER=$((ID_COUNTER + 1))
    id=$(printf "F%03d" "$ID_COUNTER")
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$id" "$severity" "$PHASE" "$file" "$line_num" "$desc"
    continue
  fi
done < "$REPORT"

if [ "$ID_COUNTER" -eq 0 ]; then
  echo "WARNING: parse-audit-report.sh found 0 findings in $REPORT" >&2
  echo "         The report may use a non-standard format; fall back to inline reading." >&2
fi
