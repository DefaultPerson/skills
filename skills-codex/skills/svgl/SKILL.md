---
name: svgl
description: >
  Fetch brand/tech logos as SVG files from the svgl.app public API — by name,
  by category, or list categories. Handles light/dark variants and wordmarks.
  Public catalogue only (~670 logos, growing). Use when you want one or more
  brand/tech logos as local SVG files; not for non-SVG assets, private logos,
  or as a general image downloader. With --json it only prints metadata.
  Triggers: "svgl", "get logo", "fetch logo", "svg logo", "download logo",
  "логотип", "svg иконка", "достань логотип".
allowed-tools: [Bash, Read, Glob]
---

# svgl

Search svgl.app, pick the right logo, download the `.svg` files into the project.

## Usage

Arguments (one of):

```
<name> [name2 ...] [flags]
--category <Category> [flags]
--list-categories
```

Flags: `--theme light|dark|both` (default `both`), `--out <dir>` (default `./svgl/`), `--wordmark`, `--json` (metadata only, no download), `--limit N` (client-side cap), `--all` (take every match, no questions), `--force` (overwrite existing files).

## API gotchas (verified 2026-09-13)

- `limit` combined with `search` or `/category` makes the API **drop the search** and return N arbitrary logos. Never add `&limit=` to those URLs — `svgl.sh` slices client-side.
- No match = HTTP 404 (`SVG not found`), not an error. `svgl.sh` returns `[]`.
- `route` and `wordmark` are a string **or** `{light, dark}`; `category` is a string **or** an array; `wordmark` is usually absent. Branch on type:
  ```bash
  jq -r 'if (.route|type)=="object" then .route.light, .route.dark else .route end'
  jq -r '(.category | if type=="array" then .[] else . end)'
  ```
- Search is a literal case-insensitive substring: `nextjs` → 404, `next` → Next.js.
- `/category/<name>` is case-sensitive beyond simple capitalisation (`ai` → 404, `sync engine` → 404). Always resolve the user's word against `svgl.sh categories` first.
- Rate limit is undocumented; big `--all` dumps may hit 429 (the script retries twice with backoff). Prefer `--limit`.

## Script

`bash scripts/svgl.sh <subcommand>` — the `scripts/` directory sits next to this SKILL.md (use the skill's path from the skills list). curl + jq, no auth, base URL `https://api.svgl.app`.

| Subcommand | Output |
|---|---|
| `categories` | TSV `category<TAB>total`, sorted by total |
| `search <query> [limit]` | JSON array, sliced client-side |
| `category <Name> [limit]` | JSON array (exact category name) |
| `download <url> <outfile>` | `saved <outfile>` or `ERROR: …` — validates it is SVG, never leaves a partial file |

## Conventions

- Filename slug = title lowercased, runs of non-`[a-z0-9]` → `-` (`D3.js` → `d3-js`).
- `<slug>.svg`; theme variants `<slug>-light.svg` / `<slug>-dark.svg`; wordmarks `<slug>-wordmark[-<theme>].svg`.
- Exact case-insensitive title match wins. Otherwise more than one match → show up to 4 candidates (title — category) as a numbered list and ask in prose (numbers / "all" / "cancel"); `--all` skips the question. Confirm before a bulk category download.
- Existing files are skipped unless `--force`.
- Report every term as `saved` / `exists` / `error (<reason>)` / `not found`, plus one aggregate line.
- Never commit, never touch `.gitignore` or other project files.

## Codex differences

- Under `codex exec` (no TTY) there is nobody to ask: on an ambiguous match stop with an explicit error instead of taking the first hit.
