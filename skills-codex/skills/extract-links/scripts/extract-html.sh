#!/usr/bin/env bash
# Fetch a URL and save readable text via pandoc.
# Usage: extract-html.sh <url> <output-dir>
# Output: <output-dir>/content.md + metadata.json
# Exit: 0 on success, 1 on fetch failure, 4 when pandoc is missing.
#
# There is deliberately no sed-based fallback: stripping tags with sed glues
# sentences together and silently produces text that reads like a successful
# extraction. Without pandoc, let the caller use its own fetch tool instead.

set -euo pipefail

URL="${1:?usage: extract-html.sh <url> <output-dir>}"
OUT="${2:?usage: extract-html.sh <url> <output-dir>}"

command -v pandoc >/dev/null 2>&1 || { echo "pandoc not installed — cannot extract HTML: $URL" >&2; exit 4; }

mkdir -p "$OUT"

HTML="$(curl -sL -A 'Mozilla/5.0 (compatible; as-extract-links/1.0)' --connect-timeout 10 --max-time 20 "$URL" || true)"
[ -n "$HTML" ] || { echo "fetch failed: $URL" >&2; exit 1; }

TITLE="$(printf '%s' "$HTML" | grep -oE '<title[^>]*>[^<]+</title>' | head -1 | sed -E 's/<[^>]+>//g' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

printf '%s' "$HTML" | pandoc -f html -t gfm -o "$OUT/content.md" 2>/dev/null || true

jq -n --arg url "$URL" --arg title "${TITLE:-unknown}" \
  '{url: $url, title: $title, fetched_at: now | strftime("%Y-%m-%dT%H:%M:%SZ")}' \
  > "$OUT/metadata.json"

[ -s "$OUT/content.md" ] || { echo "no content extracted (JS-heavy page or blocked?): $URL" >&2; exit 1; }

echo "extracted: $URL → $(wc -w < "$OUT/content.md") words"
