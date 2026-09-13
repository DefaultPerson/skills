#!/usr/bin/env bash
# svgl.sh — svgl.app API helper for the /as:svgl skill.
#
# Subcommands:
#   categories                 -> TSV "category<TAB>total" (sorted desc by total)
#   search <query> [limit]     -> raw JSON array of matching logos
#   category <name> [limit]    -> raw JSON array of logos in a category
#   download <url> <outfile>   -> fetch one SVG to <outfile>, validate, print "saved <outfile>"
#
# Base: https://api.svgl.app  (NOT svgl.app/api — that path returns nothing).
# Deps: curl, jq. No auth. Rate limit is undocumented -> up to two backoff retries on HTTP 429.
# Exit: 0 on success; non-zero with an "ERROR: …" line on stderr otherwise.

set -uo pipefail

API="https://api.svgl.app"
UA="as-svgl/1.0"

# GET <path-and-query> -> JSON on stdout; non-zero + stderr on hard failure.
# Notes on svgl's behaviour:
#   - a search/category with no matches returns HTTP 404 + {"error": "...SVG not found"};
#     that's "no results", not a failure -> we emit an empty array `[]`.
#   - rapid calls can be throttled (HTTP 429, or a non-JSON challenge page);
#     retry 429 with growing backoff and reject any non-JSON 200 body cleanly.
api_get() {
  local url="$API$1" body code tries=0
  while :; do
    body="$(curl -s -A "$UA" --max-time 25 -w $'\n%{http_code}' "$url")" || { echo "ERROR: curl failed for $url" >&2; return 1; }
    code="${body##*$'\n'}"; body="${body%$'\n'*}"
    if [ "$code" = "429" ] && [ "$tries" -lt 2 ]; then tries=$((tries + 1)); sleep "$((tries * 2))"; continue; fi
    break
  done
  [ "$code" = "404" ] && { printf '[]'; return 0; }   # no matches
  [ "$code" = "200" ] || { echo "ERROR: HTTP $code for $url" >&2; return 1; }
  printf '%s' "$body" | jq empty >/dev/null 2>&1 || { echo "ERROR: non-JSON response (throttled?) for $url" >&2; return 1; }
  printf '%s' "$body"
}

urlenc() { jq -rn --arg s "$1" '$s|@uri'; }

# Optional client-side cap. svgl IGNORES the API `limit` param when `search` is
# also sent (limit wins, search is dropped), AND ignores `limit` on /category.
# So never send `limit` to those endpoints — slice the JSON array here instead.
slice() { local n="${1:-}"; if [[ "$n" =~ ^[0-9]+$ ]]; then jq ".[:$n]"; else cat; fi; }

cmd="${1:-}"; shift || true
case "$cmd" in
  categories)
    api_get "/categories" | jq -r 'sort_by(-.total)[] | "\(.category)\t\(.total)"'
    ;;
  search)
    q="${1:?usage: svgl.sh search <query> [limit]}"
    out="$(api_get "/?search=$(urlenc "$q")")" || exit 1
    printf '%s' "$out" | slice "${2:-}"
    ;;
  category)
    name="${1:?usage: svgl.sh category <name> [limit]}"
    out="$(api_get "/category/$(urlenc "$name")")" || exit 1
    printf '%s' "$out" | slice "${2:-}"
    ;;
  download)
    url="${1:?usage: svgl.sh download <url> <outfile>}"; out="${2:?usage: svgl.sh download <url> <outfile>}"
    # Download to a temp file and only move it into place once validated, so a
    # 404 / 429 / challenge page can never clobber an existing good file
    # (`--force` re-downloads over files the user already has).
    dir="$(dirname "$out")"
    tmp="$(mktemp "${TMPDIR:-/tmp}/svgl.XXXXXX")" || { echo "ERROR: mktemp failed" >&2; exit 1; }
    trap 'rm -f "$tmp"' EXIT
    code="$(curl -s -A "$UA" --max-time 25 -w '%{http_code}' -o "$tmp" "$url")" || { echo "ERROR: fetch failed: $url" >&2; exit 1; }
    if [ "$code" = "429" ]; then
      sleep 1.5
      code="$(curl -s -A "$UA" --max-time 25 -w '%{http_code}' -o "$tmp" "$url")" || { echo "ERROR: fetch failed: $url" >&2; exit 1; }
    fi
    [ "$code" = "200" ] || { echo "ERROR: HTTP $code for $url" >&2; exit 1; }
    # Validate it is actually an SVG (allow a leading XML decl / comments / BOM).
    head -c 1024 "$tmp" | grep -qiE '<svg|<\?xml' || { echo "ERROR: not an SVG (no <svg>/<?xml in first 1KB): $url" >&2; exit 1; }
    mkdir -p "$dir" && mv "$tmp" "$out" || { echo "ERROR: cannot write $out" >&2; exit 1; }
    trap - EXIT
    echo "saved $out"
    ;;
  *)
    echo "usage: svgl.sh {categories | search <query> [limit] | category <name> [limit] | download <url> <outfile>}" >&2
    exit 2
    ;;
esac
