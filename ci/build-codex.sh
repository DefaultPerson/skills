#!/usr/bin/env bash
# build-codex.sh — make each Codex skill self-contained for native packaging.
#
# `codex plugin add` copies the plugin tree into its cache and STRIPS symlinks,
# so a Codex skill cannot borrow its scripts/roles/references from the Claude
# tree at runtime — it must carry real copies. This script syncs those shared
# asset subdirs from skills/<name>/ (the source of truth) into
# skills-codex/skills/<name>/.
#
# `workflows/` is intentionally NOT copied — Codex has no Workflow tool.
# The Codex-variant SKILL.md is never touched. Idempotent: re-run after editing
# any shared asset. CI (ci/validate.py) asserts the copies stay byte-identical.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS="references scripts roles"

for d in "$ROOT"/skills-codex/skills/*/; do
  name="$(basename "$d")"
  src="$ROOT/skills/$name"
  for sub in $ASSETS; do
    rm -rf "${d%/}/$sub"
    if [ -d "$src/$sub" ]; then
      cp -R "$src/$sub" "${d%/}/$sub"
    fi
  done
done

find "$ROOT/skills-codex" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "Codex assets synced: skills/ → skills-codex/skills/ ($ASSETS; workflows/ skipped)."
