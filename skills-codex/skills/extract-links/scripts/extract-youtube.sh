#!/usr/bin/env bash
# Extract YouTube subtitles to a slug-named directory.
# Usage: extract-youtube.sh <url> <output-dir>
# Output: <output-dir>/subtitles.{en,ru}.txt + metadata.json
# Exit: 0 on success, 1 on yt-dlp error, 2 on no subtitles found

set -euo pipefail

URL="${1:?usage: extract-youtube.sh <url> <output-dir>}"
OUT="${2:?usage: extract-youtube.sh <url> <output-dir>}"

mkdir -p "$OUT"

# Metadata first (cheap, gives us title etc. before subtitle work)
timeout 60 yt-dlp --dump-json --no-warnings --socket-timeout 15 --retries 1 "$URL" 2>"$OUT/.yt-dlp.log" \
  | jq '{title, uploader, duration, upload_date, id, webpage_url}' \
  > "$OUT/metadata.json" || { echo "yt-dlp metadata failed or timed out: $URL ($(tail -1 "$OUT/.yt-dlp.log" 2>/dev/null))" >&2; exit 1; }

# Subtitles: prefer manual (en, ru), fall back to auto-generated
timeout 300 yt-dlp \
  --skip-download \
  --socket-timeout 15 \
  --retries 1 \
  --write-subs \
  --write-auto-subs \
  --sub-langs "en,ru" \
  --sub-format "vtt/srt" \
  -o "$OUT/raw.%(ext)s" \
  --no-warnings \
  "$URL" >/dev/null 2>>"$OUT/.yt-dlp.log" || { echo "yt-dlp subtitle fetch failed or timed out: $URL ($(tail -1 "$OUT/.yt-dlp.log" 2>/dev/null))" >&2; exit 1; }

# Track whether we got manual or auto-generated
sub_source="manual"
shopt -s nullglob
vtt_files=("$OUT"/raw*.vtt)
srt_files=("$OUT"/raw*.srt)
if [ "${#vtt_files[@]}" -eq 0 ] && [ "${#srt_files[@]}" -eq 0 ]; then
  echo "no subtitles available: $URL" >&2
  exit 2
fi

# Normalize: strip vtt/srt artifacts (timestamps, cue numbers, WEBVTT headers)
# Result: plain text, one paragraph per cue, blank lines collapsed.
clean_subtitle_file() {
  local src="$1" dst="$2"
  if [[ "$src" == *.vtt ]]; then
    # VTT: drop WEBVTT header, timestamps, cue settings; keep text
    grep -v -E '^(WEBVTT|NOTE|Kind:|Language:|\s*$|[0-9]+:[0-9]+:|[0-9]+\s*$|<[^>]+>)' "$src" \
      | sed 's/<[^>]*>//g' \
      | awk 'NF' \
      > "$dst"
  else
    # SRT: drop cue numbers + timestamps; keep text
    grep -v -E '^([0-9]+|[0-9]+:[0-9]+:[0-9]+,[0-9]+|\s*$)' "$src" \
      | sed 's/<[^>]*>//g' \
      | awk 'NF' \
      > "$dst"
  fi
}

# Detect language from filename (yt-dlp names like raw.en.vtt)
for src in "${vtt_files[@]}" "${srt_files[@]}"; do
  lang=$(basename "$src" | sed -E 's/^raw\.([a-z]+).*/\1/')
  if [[ "$src" == *".auto."* ]] || [[ "$src" == *"-orig"* ]]; then
    sub_source="auto-generated"
  fi
  clean_subtitle_file "$src" "$OUT/subtitles.$lang.txt"
done

# Annotate metadata with subtitle_source
tmp="$(mktemp)"
jq --arg src "$sub_source" '. + {subtitle_source: $src}' "$OUT/metadata.json" > "$tmp" && mv "$tmp" "$OUT/metadata.json"

# Cleanup raw files
rm -f "$OUT"/raw*.vtt "$OUT"/raw*.srt "$OUT/.yt-dlp.log"

# Report
wc -w "$OUT"/subtitles.*.txt 2>/dev/null | tail -n +1
