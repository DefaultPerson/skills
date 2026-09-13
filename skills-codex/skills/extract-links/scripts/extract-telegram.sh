#!/usr/bin/env bash
# Extract content from a public Telegram channel post.
# Usage: extract-telegram.sh <url> <output-dir>
# Supports t.me/channel/post-id URLs only (public channels).
# Output: <output-dir>/post.md + media/ (if any media URLs)
# Exit: 0 on success, 1 on fetch failure, 2 on unsupported/inaccessible URL,
#       3 when the post exists but has no text (media-only)

set -euo pipefail

URL="${1:?usage: extract-telegram.sh <url> <output-dir>}"
OUT="${2:?usage: extract-telegram.sh <url> <output-dir>}"

mkdir -p "$OUT/media"

# Parse URL: expect https://t.me/<channel>/<post-id>
if [[ ! "$URL" =~ ^https?://t\.me/([A-Za-z0-9_]+)/([0-9]+) ]]; then
  echo "unsupported telegram URL (need t.me/channel/post-id): $URL" >&2
  exit 2
fi
CHANNEL="${BASH_REMATCH[1]}"
POST_ID="${BASH_REMATCH[2]}"

# Strategy: fetch the public embed page (t.me's web view).
# Note: tchan exists for channel-wide exports (CSV), not single-post pulls,
# so we skip it for this script and go straight to the embed-page scrape,
# which works for any public channel post without auth.
EMBED_URL="https://t.me/${CHANNEL}/${POST_ID}?embed=1&mode=tme"
HTML="$(curl -s -A 'Mozilla/5.0 (compatible; as-extract-links/1.0)' --max-time 15 --connect-timeout 10 "$EMBED_URL" || true)"

if [ -z "$HTML" ]; then
  echo "curl failed: $EMBED_URL" >&2
  exit 1
fi

# Channel may be private / post deleted / 404'd — detect "post not found"
if echo "$HTML" | grep -qE 'tgme_widget_message_error|Channel is private|Post not found'; then
  echo "telegram post not accessible: $URL (private channel or deleted)" >&2
  exit 2
fi

# Extract message text. The post text lives in .tgme_widget_message_text in the embed page.
# Light HTML stripping via sed/awk — not robust against weird formatting, but works for plain posts.
# Block tags become newlines (otherwise sentences glue together); entities —
# named and numeric — are decoded by python's html.unescape.
echo "$HTML" \
  | awk 'BEGIN{p=0} /<div class="tgme_widget_message_text/{p=1} p; /<\/div>/{if(p){p=0; print "---END---"}}' \
  | awk '/---END---/{exit} {print}' \
  | sed -E 's#<br[^>]*>#\n#g; s#</?(p|div)[^>]*>#\n#g' \
  | sed 's/<[^>]*>//g' \
  | python3 -c 'import html,sys; sys.stdout.write(html.unescape(sys.stdin.read()))' \
  > "$OUT/post.md"

# Extract media URLs (photos, videos) for separate download
echo "$HTML" \
  | grep -oE 'background-image:url\([^)]+\)' \
  | sed -E "s/background-image:url\(['\"]?([^'\")]+)['\"]?\)/\1/" \
  | sort -u \
  > "$OUT/media/urls.txt"

if [ -s "$OUT/post.md" ]; then
  echo "extracted: $URL → $(wc -w < "$OUT/post.md") words, $(wc -l < "$OUT/media/urls.txt") media URLs"
  exit 0
elif [ -s "$OUT/media/urls.txt" ]; then
  # A photo/video post with no caption is not a failure — there is simply no text.
  echo "media-only post (no text): $URL → $(wc -l < "$OUT/media/urls.txt") media URLs"
  exit 3
else
  echo "no content extracted: $URL" >&2
  exit 1
fi
