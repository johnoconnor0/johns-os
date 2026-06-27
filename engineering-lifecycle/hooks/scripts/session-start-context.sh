#!/usr/bin/env sh
set -eu

if [ -d ".project/.engineering" ]; then
  echo "engineering lifecycle: workspace detected at .project/.engineering"
else
  echo "engineering lifecycle: no workspace yet; run scripts/init-workspace.py when needed"
fi
