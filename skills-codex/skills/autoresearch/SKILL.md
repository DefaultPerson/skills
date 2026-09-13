---
name: autoresearch
description: >
  Autonomous keep-or-revert experiment loop: one atomic change per iteration,
  commit before verify, keep it when the metric improved, revert it when it
  did not. Needs a git repo and a metric command that prints one number. Use
  it when you have a numeric objective (pass rate, latency, benchmark score,
  line count) and want many small experiments run against it, each one
  committed or reverted on its measurement; not for one-off fixes, not for
  goals no single command can score, not outside a git repo. Triggers:
  "autoresearch", "optimize metric", "keep or revert loop",
  "автоисследование", "оптимизируй метрику".
allowed-tools: [Bash, Read, Edit, Write, Glob, Grep]
---

# autoresearch

One atomic change per iteration → commit → measure → keep or revert. The run's memory is two files on disk, re-read at the start of every iteration, so context compaction cannot derail it. Arguments: a goal, `--continue` (resume, skipping Setup) or `--abort`.

## Rails

- Requires a git repo — without one, stop and say: run `git init && git add -A && git commit -m 'baseline'` first.
- Commit before verify. A failed iteration is undone with `git revert --no-edit HEAD` — never `--amend`, never rebase, never a second attempt on the same commit. History is append-only.
- Never edit `metric_cmd`, `guard_cmd`, or anything outside `scope`.
- `mktemp` a fresh log **per measurement**, inside the step that measures. A path assigned during Setup is gone on `--continue`, which skips Setup. Only the extracted number enters the context.
- A step that blows up is reverted and logged, never silently retried, and never ends the run.

## Setup

Skip on `--continue`. If `autoresearch-scratchpad.md` already exists, it belongs to another run: resume it only when its `status` is `active` and its goal matches, otherwise ask before touching it.

1. Ask in one prose message: `scope` (paths that may be modified), `metric_cmd`, `guard_cmd` (optional sanity check, e.g. the test suite), `direction` (higher or lower is better), `max_iterations` (default 20). Under `codex exec` with no TTY nobody can answer: scope = the paths the goal names, direction inferred from the goal, no guard, 20 iterations — print what you assumed.
2. Validate the metric once, here. Run `metric_cmd` into a `mktemp` log and read the number out of it. Contract: it prints exactly one number to stdout and exits 0. No number, several numbers, or a non-zero exit → fix the command with the user before starting. Every later iteration trusts this contract.
3. `git status --porcelain` must be empty, then `git checkout -b autoresearch/<slug>` (slug = the goal lowercased, runs of non-`[a-z0-9]` collapsed to `-`, trimmed to 40 chars).
4. Write both state files with the baseline as iteration 0, **commit them** (`autoresearch: baseline`), then print the card: goal, scope, metric + direction + baseline, guard, max iterations, branch, and `--abort` to stop.

## State contract

Both files live in the project root on the experiment branch, written atomically (temp file in the same directory, then `mv`) and committed at the end of every iteration — the loop requires a clean tree, and an uncommitted pair would stall it on the first read.

`autoresearch-scratchpad.md` frontmatter: `goal` · `scope` · `metric_cmd` · `guard_cmd` · `direction` (`higher_is_better` | `lower_is_better`) · `best_metric` · `best_commit` · `iteration` · `max_iterations` · `status` (`active` | `complete` | `aborted`). Unknown fields are kept as-is. Body: four sections of terse bullets — `## What worked`, `## What failed`, `## Next to try`, `## Blocked ideas`.

`autoresearch-history.tsv` — append-only, tab-separated, header `iteration	commit	metric	delta	status	description`, one row per iteration. `status` is BASELINE, KEEP, DISCARD, CRASH or GUARD_FAIL; `commit` is the hash on KEEP and `REVERTED` otherwise.

## Iteration

**1. Read.** Scratchpad frontmatter and body, last 20 rows of the history file, `git log --oneline -15`. The working tree must be clean — if it is not, stash and investigate before going on. Count the trailing run of DISCARD/CRASH/GUARD_FAIL rows.

**2. Ideate.** Exactly one hypothesis, taking the first rung that applies: last status CRASH → fix the crash before anything new; the last three *committed* iterations produced the same diff (`git show --format= <commit> | md5sum`) or repeated one description → circuit-break, move that idea to `## Blocked ideas` and pick another; more than 5 consecutive discards → pivot, re-reading the whole scratchpad and combining near-misses into a structurally different approach; a recent KEEP → exploit it with a variation; otherwise → explore the top item of `## Next to try`. Nothing left to pick means the run is over — stop and report.

**3. Delegate.** Hand the edit to a sub-agent (`spawn_agent`, then `wait_agent`, then `close_agent` — an unreleased slot leaks across a long run) so the parent reads no source files and no diffs, which is what keeps its context flat. Brief it: apply ONE atomic change for the hypothesis, stay strictly inside `scope`, never run the metric or guard, never touch the two state files, never amend or rebase, commit as `autoresearch iter <N>: <one-line hypothesis>`, and abort rather than commit anything that breaks those. It must return five key:value lines and nothing else: `result: applied|aborted`, `commit`, `files_changed`, `summary`, `lesson`. On `result: aborted` nothing was committed — skip Verify and log DISCARD with its `summary`; a truncated or malformed message counts as aborted too, noted "partial". Without multi-agent support, apply the change inline instead, reading only the in-scope files the hypothesis touches.

**4. Verify.** Metric first: `mktemp` a log, run `metric_cmd` into it, extract the single number. Non-zero exit or no number → CRASH. Then `guard_cmd`, if set, into its own fresh log: non-zero exit → GUARD_FAIL, with no rework and no amend.

**5. Decide.** KEEP only when the number moved the right way for `direction` and the guard passed; then update `best_metric` and `best_commit`. Otherwise `git revert --no-edit HEAD` and record DISCARD, CRASH or GUARD_FAIL.

**6. Log.** Append the history row. Update the scratchpad body — what worked, what failed and why, ideas pruned and added, dead ends moved to blocked; a non-empty `lesson` goes into `## Next to try` prefixed `[from worker iter N]`. The body must change every iteration: nothing to add means nothing was learned, so say so and stop. Increment `iteration`, write atomically, commit both files as `autoresearch iter <N>: log` — after the revert, so step 5 always targets the experiment commit — and print one line: `iter <N>: <STATUS> — metric <value> (best <best>, delta <d>)`. Then go back to step 1 unless the run is finished.

## Stuck: rescue

Optional, and only with `claude` on PATH. After 3 consecutive DISCARD/CRASH/GUARD_FAIL, pipe a read-only diagnosis prompt (goal, `metric_cmd`, direction, the last 3 history rows, the scratchpad body, and "propose one fundamentally different approach, do not edit files") into `claude -p` via Bash. Append the suggestion to `## Next to try` as `[from rescue iter N] <one line>`; the explore rung picks it up next. Never apply a patch it proposes.

## Finish

`iteration >= max_iterations`, checked after every Log, sets `status: complete` and prints the summary: best metric against baseline with delta, iterations run / kept / discarded, best commit, branch, and `git switch main && git merge autoresearch/<slug>` to take the result. An early stop (no ideas left, circuit breaker) prints the same summary plus the reason.

Iterations run back-to-back in this session; there is no scheduling primitive here, so a run that outlives the session picks up again with `--continue` in a fresh one.

`--continue` re-reads the state files and resumes at step 1. When `status` is `complete` or `aborted`, or `iteration >= max_iterations`, ask whether to extend the cap, start fresh, or stop; with nobody to ask, print the state and stop.

`--abort` sets `status: aborted`, prints the summary and exits. Kept commits stay on the branch, and both state files stay with them as the record of the run.
