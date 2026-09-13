#!/usr/bin/env bash
# summarize-url.sh — lightweight metadata fetch for extract-links LIGHT mode.
# Prints labelled metadata to stdout for the caller (the model) to condense into
# a one-line summary. Does NOT download full content: no subtitles, no pandoc
# conversion, nothing written to disk.
#
# Usage: summarize-url.sh <url>
# Output: labelled lines (TYPE / TITLE / UPLOADER / DURATION / TEXT / DESC)
#         or an "ERROR: <reason>" line.
# Exit:   always 0 — failures are reported as an ERROR: line so the caller keeps
#         going through the remaining URLs.

set -uo pipefail

URL="${1:?usage: summarize-url.sh <url>}"
UA='Mozilla/5.0 (compatible; as-extract-links/1.0)'
MAXLEN=400

# Strip tags, decode common entities, collapse whitespace, truncate.
clip() {
  # Block-level tags become spaces (otherwise sentences glue together), inline
  # tags vanish, then entities — named AND numeric (&#33;, &#x41;) — are decoded.
  sed -E 's#</?(p|div|br|li|tr|h[1-6]|section|article)[^>]*>#\n#g' \
    | sed 's/<[^>]*>//g' \
    | python3 -c 'import html,sys; sys.stdout.write(html.unescape(sys.stdin.read()))' \
    | tr '\n' ' ' \
    | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//' \
    | cut -c "1-${MAXLEN}"
}

case "$URL" in
  *youtube.com/watch*|*youtu.be/*)
    echo "TYPE: youtube"
    if ! command -v yt-dlp >/dev/null 2>&1; then echo "ERROR: yt-dlp not installed"; exit 0; fi
    json="$(timeout 45 yt-dlp --skip-download --no-warnings --no-playlist \
             --socket-timeout 15 --retries 1 -J "$URL" 2>/dev/null || true)"
    [ -n "$json" ] || { echo "ERROR: yt-dlp fetch failed or timed out (private/age-gated/removed/offline?)"; exit 0; }
    title="$(printf '%s' "$json" | jq -r '.title // empty')"
    uploader="$(printf '%s' "$json" | jq -r '.uploader // empty')"
    dur="$(printf '%s' "$json" | jq -r '.duration_string // empty')"
    desc="$(printf '%s' "$json" | jq -r '.description // empty' | clip)"
    [ -n "$title" ]    && echo "TITLE: $title"
    [ -n "$uploader" ] && echo "UPLOADER: $uploader"
    [ -n "$dur" ]      && echo "DURATION: $dur"
    [ -n "$desc" ]     && echo "DESC: $desc"
    [ -z "$title$desc" ] && echo "ERROR: no metadata found"
    ;;
  *t.me/*)
    echo "TYPE: telegram"
    html="$(curl -s -A "$UA" --max-time 15 "${URL%/}?embed=1&mode=tme" || true)"
    [ -n "$html" ] || { echo "ERROR: telegram fetch failed"; exit 0; }
    if printf '%s' "$html" | grep -qE 'tgme_widget_message_error|Channel is private|Post not found'; then
      echo "ERROR: telegram post not accessible (private or deleted)"; exit 0
    fi
    text="$(printf '%s' "$html" \
      | awk 'BEGIN{p=0} /<div class="tgme_widget_message_text/{p=1} p; /<\/div>/{if(p){p=0; print "---END---"}}' \
      | awk '/---END---/{exit} {print}' | clip)"
    if [ -n "$text" ]; then
      echo "TEXT: $text"
    elif printf '%s' "$html" | grep -q 'tgme_widget_message_photo\|tgme_widget_message_video\|message_media_not_supported'; then
      echo "NOTE: media-only post (no text)"
    else
      echo "ERROR: no telegram preview text"
    fi
    ;;
  *)
    echo "TYPE: html"
    html="$(curl -sL -A "$UA" --max-time 20 "$URL" || true)"
    [ -n "$html" ] || { echo "ERROR: html fetch failed"; exit 0; }
    title="$(printf '%s' "$html" | grep -oiE "<title[^>]*>[^<]+</title>" | head -1 | clip)"
    metatag="$(printf '%s' "$html" | tr '\n' ' ' \
      | grep -oiE "<meta[^>]+(name=[\"']description[\"']|property=[\"']og:description[\"'])[^>]*>" | head -1)"
    desc="$(printf '%s' "$metatag" | grep -oiE "content=[\"'][^\"']*" | head -1 | sed -E "s/^content=[\"']//" | clip)"
    [ -n "$title" ] && echo "TITLE: $title"
    [ -n "$desc" ]  && echo "DESC: $desc"
    [ -z "$title$desc" ] && echo "ERROR: no title/description found (JS-SPA, paywall, or blocked?)"
    ;;
esac
exit 0
