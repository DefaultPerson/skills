---
name: extract-links
description: >
  Annotate every URL in a notes file with what's behind it. By default writes a
  one-line gist inline next to each link; with --full it pulls the actual
  content (YouTube subtitles, Telegram posts, articles) into a local extracted/
  tree and points at it. Triggers: "extract-links", "/as:extract-links",
  "развернуть ссылки", "expand links", "fetch URLs", "извлеки контент".
when_to_use: >
  A note has 3+ URLs and you want their content available without opening each
  one. NOT for a single URL you can just open, and not for private or
  paywalled resources — those are out of scope and get reported as errors.
argument-hint: "<note.md> [--full] [--force]"
allowed-tools: [Bash, Read, Edit, Glob, Grep, WebFetch, AskUserQuestion]
---

# extract-links

Find every URL in the note, work out what it is, and write that back into the note next to the link. Light by default (a one-line gist per URL, nothing written to disk); `--full` brings the content itself offline.

`--force` re-processes URLs that already carry an annotation.

## Contracts

- **The original URL is never replaced.** The annotation is appended after it: `→ _<gist>_` in light mode, `→ [<local path>](<local path>)` in full mode.
- **Idempotent:** skip a URL already followed by either annotation form, unless `--force`. A light pass then a full pass must not leave two annotations.
- **Full-mode layout:** `<note-dir>/extracted/<note-basename>/<slug>/`, one shared `extracted/` parent per directory, slug `<type>-<short-id>` (`youtube-dQw4w9WgXcQ`, `telegram-durov-342`, `html-blog-example-com`) ≤50 chars. Inside: `subtitles.<lang>.txt` + `metadata.json`, or `post.md` + `media/urls.txt`, or `content.md` + `metadata.json`. Failures append to `<extracted-root>/.errors.log` and leave the URL bare.
- Full mode adds `extracted/` to the `.gitignore` at the **git root**, idempotently. Light mode writes nothing but the note.
- **Report every URL** as `summarised` / `extracted` / `error (<reason>)` / `skipped (reference)` / `skipped (user)`, plus an aggregate — in your reply, since the user never sees the Bash output.

## Light mode (default)

For each URL: `bash "${CLAUDE_SKILL_DIR}/scripts/summarize-url.sh" <url>` prints labelled metadata, a `NOTE:` line for a fetch that succeeded with nothing to show (a media-only Telegram post), or an `ERROR:` line. Condense it into one plain sentence — what the link is and why it is probably in this note, ~140 chars — and append `→ _<sentence>_`.

On `ERROR:`, or metadata too thin to say anything with: say so (`→ _(Telegram post — preview unavailable)_`), never invent content you did not fetch. For an HTML page that came back thin or JavaScript-only, WebFetch is the better second try; for YouTube and Telegram it is not — only the scripts reach those.

## Full mode (`--full`)

Route by URL, all under `${CLAUDE_SKILL_DIR}/scripts/`: YouTube (`watch?v=` / `youtu.be`) → `extract-youtube.sh`, public Telegram post (`t.me/<channel>/<id>`) → `extract-telegram.sh`, anything else → `extract-html.sh`, which exits non-zero without pandoc — fall back to WebFetch for that URL and note it; offer to install pandoc only if the user wants real extraction.

Some URLs in a note are references, not content — bare hosts, docs landing pages, repo roots, citation links. Flag those and ask once, in a single batched question, before skipping them; default to skipping. Don't decide silently: judging content you haven't seen is the user's call, not yours.

An error on one URL never stops the run: log it, leave that URL bare, keep going.

## Gotchas

- `yt-dlp` and `curl` can hang on a flaky network — the scripts bound themselves, but keep a patience budget for a whole-note run and report a URL that timed out as an error rather than waiting on it.
- A Telegram post with no text (photo/video only) is not an error, and neither is a video with no captions. Say so in the annotation and count it as summarised.
- curl does not run JavaScript: single-page apps return a skeleton.
- Long transcripts (a 2h video is ~30k words) will swamp whatever reads the note next. Mention the size rather than silently producing it.
- Needs Bash — this skill can't run under `claude --restricted`.

## Rails

- Never install a dependency without asking.
- Never fabricate a summary for a fetch that failed.
- Never drop the original URL, and never commit — the note belongs to the user.
- Every URL ends up in the report with a state.
- Nobody to ask (a subagent, a scheduled run): skip the reference-looking URLs, install nothing, and say both in the report.
