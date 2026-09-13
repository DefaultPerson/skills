---
name: extract-links
description: >
  Annotate every URL in a notes file with what's behind it. By default writes a
  one-line gist inline next to each link; with --full it pulls the actual
  content (YouTube subtitles, Telegram posts, articles) into a local extracted/
  tree and points at it. Use when a note has 3+ URLs and you want their content
  available without opening each one; not for a single URL you can just open,
  and not for private or paywalled resources. Triggers: "extract-links",
  "развернуть ссылки", "expand links", "fetch URLs", "извлеки контент".
allowed-tools: [Bash, Read, Edit, Glob, Grep]
---

# extract-links

Find every URL in the note, work out what it is, and write that back into the note next to the link. Light by default (a one-line gist per URL, nothing written to disk); `--full` brings the content itself offline.

`--force` re-processes URLs that already carry an annotation.

## Contracts

- **The original URL is never replaced.** The annotation is appended after it: `→ _<gist>_` in light mode, `→ [<local path>](<local path>)` in full mode.
- **Idempotent:** skip a URL that is already followed by either annotation form, unless `--force`. A light pass followed by a full pass must not leave two annotations.
- **Full-mode layout:** `<note-dir>/extracted/<note-basename>/<slug>/`, one shared `extracted/` parent per directory. Slug is `<type>-<short-id>` (`youtube-dQw4w9WgXcQ`, `telegram-durov-342`, `html-blog-example-com`), max 50 chars.
- Per-type output: YouTube → `subtitles.<lang>.txt` + `metadata.json`; Telegram → `post.md` + `media/urls.txt`; HTML → `content.md` + `metadata.json`. Failures append to `<extracted-root>/.errors.log` and the URL stays un-annotated.
- Full mode adds `extracted/` to the `.gitignore` at the **git root**, idempotently. Light mode writes nothing but the note.
- **Report every URL** with a state: `summarised` / `extracted` / `error (<reason>)` / `skipped (reference)` / `skipped (user)`, plus an aggregate.
- Never commit. The note belongs to the user.

## Light mode (default)

For each URL: `bash scripts/summarize-url.sh <url>` (the `scripts/` directory sits next to this SKILL.md) prints labelled metadata (`TYPE` / `TITLE` / `UPLOADER` / `DURATION` / `TEXT` / `DESC`) or an `ERROR:` line. Condense it into one plain sentence — what the link is and why it is probably in this note, ~140 chars — and append `→ _<sentence>_`.

If the script returned `ERROR:`, or only a bare title, say so: `→ _(Telegram post — preview unavailable)_`. **Never invent content you did not fetch.**

## Full mode (`--full`)

Route by URL: YouTube (`watch?v=` / `youtu.be`) → `scripts/extract-youtube.sh`, public Telegram post (`t.me/<channel>/<id>`) → `scripts/extract-telegram.sh`, anything else → `scripts/extract-html.sh`, which needs pandoc and exits non-zero without it.

Some URLs in a note are references, not content — bare hosts, docs landing pages, repo roots, citation links. Flag those and ask once before skipping them; default to skipping. Don't decide silently: judging content you haven't seen is the user's call, not yours.

An error on one URL never stops the run: log it, leave that URL bare, keep going.

## Gotchas

- `yt-dlp` and `curl` can hang on a flaky network — the scripts bound themselves, but report a URL that timed out as an error rather than waiting on it.
- A Telegram post with no text (photo/video only) is not an error — it has no preview text to extract. Say that in the annotation.
- curl does not run JavaScript: single-page apps return a skeleton.
- Long transcripts (a 2h video is ~30k words) will swamp whatever reads the note next. Mention the size rather than silently producing it.
- Private channels, paywalls and login-only pages are out of scope.

## Rails

- Never install a dependency without asking. Missing `yt-dlp` or `pandoc` → offer install / skip those URLs / abort.
- Never fabricate a summary for a fetch that failed.
- Never drop the original URL.
- Every URL ends up in the report with a state.

## Codex differences

- Ask in prose: list the reference-looking URLs as a numbered list and accept numbers / "all" / "none".
- Under `codex exec` (no TTY) nobody can answer: skip the reference URLs, install nothing, and say both in the report.
