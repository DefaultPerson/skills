# as

Lean, battle-tested skills for AI coding agents — Claude Code and Codex CLI. Only the ones actually used, kept to what the model can't know on its own: contracts, verified gotchas, safety rails.

> Formerly `iron-skills`. Existing installs migrate automatically (`renames` in the marketplace). Remove the old marketplace once: `claude plugin marketplace remove iron-skills`.

## Install

Claude Code:

```bash
claude plugin marketplace add DefaultPerson/skills && claude plugin install as@as
```

Then `/plugin` → **Marketplaces** → `as` → **Enable auto-update** (third-party marketplaces don't auto-update by default).

Codex CLI (≥ 0.154):

```bash
codex plugin marketplace add DefaultPerson/skills && codex plugin add as@as
```

Codex has no auto-update — to update: `codex plugin marketplace upgrade as && codex plugin add as@as`, then start a new session.

Local checkout: `claude --plugin-dir /path/to/skills`, or `codex plugin marketplace add ./ && codex plugin add as@as` from inside the repo.

## Skills

- `/as:cleanup` — losslessly reorganize a messy notes/chat dump into clean sectioned markdown; three-level gap detection proves nothing was lost.
- `/as:extract-links` — annotate every URL in a note with a one-line gist (default), or pull YouTube subtitles / Telegram posts / articles to disk with `--full`.
- `/as:verify-done` — acceptance gate for finished work: re-runs `Done when:` proofs, tests independent scenarios, advisory quality pass. Read-only; answers DONE / NOT-DONE.
- `/as:autoresearch` — keep-or-revert metric loop: one atomic change per iteration, commit before verify, revert what doesn't help.
- `/as:svgl` — brand/tech logos as SVG files from svgl.app.
- `/as:babysit` *(Claude Code only)* — watch a running service on a `/loop` cadence: fix → deploy → re-check, escalate only when stuck.

Run `/skill-doctor` to see what each skill costs in context.

## Prerequisites

`git`, `bash`, `jq`, `python3`. `extract-links --full` needs `yt-dlp` (YouTube) and `pandoc` (HTML). Scripts don't run under `claude --restricted`.

Release history: [CHANGELOG.md](CHANGELOG.md).
