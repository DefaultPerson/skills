---
name: svgl
description: >
  Fetch brand/tech logos as SVG files from the svgl.app public API — by name,
  by category, or list categories. Handles light/dark variants and wordmarks.
  Public catalogue only (~670 logos, growing). Triggers: "svgl", "/as:svgl",
  "get logo", "fetch logo", "svg logo", "download logo", "логотип",
  "svg иконка", "достань логотип".
when_to_use: >
  You want one or more brand/tech logos as local SVG files and svgl.app likely
  has them. Not for non-SVG assets, private logos, or as a general image
  downloader. With --json it only prints metadata.
argument-hint: "<name...> | --category <Category> | --list-categories"
allowed-tools: [Bash, Read, Glob, AskUserQuestion]
---

# svgl

Search svgl.app, pick the right logo, download the `.svg` files into the project.

Flags: `--theme light|dark|both` (default `both`), `--out <dir>` (default `./svgl/`), `--wordmark`, `--json` (metadata only, no download), `--limit N` (client-side cap), `--all` (take every match, no questions), `--force` (overwrite existing files).

## API gotchas (verified 2026-09-13)

- `limit` combined with `search` or `/category` makes the API **drop the search** and return N arbitrary logos. Never add `&limit=` to those URLs — the script slices client-side.
- No match = HTTP 404 (`SVG not found`), not an error. The script returns `[]`.
- `route` and `wordmark` are a string **or** `{light, dark}`; `category` is a string **or** an array; `wordmark` is usually absent. The script hands you raw API JSON, so you resolve the download URL yourself:
  ```bash
  jq -r 'if (.route|type)=="object" then .route.light, .route.dark else .route end'
  ```
- Search is a literal case-insensitive substring: `nextjs` → 404, `next` → Next.js.
- `/category/<name>` is case-sensitive beyond simple capitalisation (`ai` → 404, `sync engine` → 404). Always resolve the user's word against the `categories` output first.
- The rate limit is undocumented; a big `--all` dump may hit 429. Search retries twice with backoff, download once. Prefer `--limit`.

## Script

`bash "${CLAUDE_SKILL_DIR}/scripts/svgl.sh" <subcommand>` — curl + jq, no auth, base `https://api.svgl.app`.

`categories` prints TSV `category<TAB>total`. `search <query> [limit]` and `category <Name> [limit]` print a JSON array, sliced client-side. `download <url> <outfile>` prints `saved <outfile>` or `ERROR: …`, validating the payload is SVG and never leaving a partial or clobbered file.

## Conventions

- Filename slug = title lowercased, runs of non-`[a-z0-9]` → `-` (`D3.js` → `d3-js`); `<slug>.svg`, theme variants `<slug>-light.svg` / `<slug>-dark.svg`, wordmarks `<slug>-wordmark[-<theme>].svg`.
- Exact case-insensitive title match wins. Otherwise more than one match → `AskUserQuestion` with up to 4 candidates (title — category); `--all` skips the question. Confirm before a bulk category download.
- Report every term as `saved` / `exists` / `error (<reason>)` / `not found` in your reply text — the user does not see raw command output — plus one aggregate line.
- Never commit, never touch `.gitignore` or other project files.
