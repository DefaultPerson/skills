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

One atomic change per iteration → commit → measure → keep or revert. The run's
memory is two files on disk, re-read at the start of every iteration, so
context compaction cannot derail it.

## Usage

Arguments (one of):

```
<goal in natural language>
--continue    # resume from the scratchpad, skip Setup
--abort       # mark the run aborted; kept commits stay
```

Iterations run back-to-back in this session; a run that outlives the session
picks up again with `--continue`.

## Invariants

- Requires a git repo. Without one, stop and say: run `git init && git add -A && git commit -m 'baseline'` first.
- ONE atomic change per iteration. "And also" means split it into two iterations.
- Commit before verify. A failed iteration is undone with `git revert --no-edit HEAD` — never `--amend`, never rebase, never a second attempt on the same commit. History is append-only.
- Never edit `metric_cmd`, `guard_cmd`, or anything outside `scope`.
- Re-read state from disk at the start of every iteration; never trust an in-context copy.
- The scratchpad body must change every iteration. Nothing to add to it means nothing was learned — say so and stop.
- Metric and guard output goes to a fresh `mktemp` log per run; only the extracted number enters the context. Never reuse a log path held in a variable set during Setup — `--continue` skips Setup.
- The parent runs metric and guard; the worker never does.
- A step that blows up is reverted and logged, never silently retried, and never ends the run.
- Match the user's language in what you print.

## Setup

Skip entirely on `--continue` or when `autoresearch-scratchpad.md` already exists.

1. Take the goal from the arguments; ask for it if empty.
2. Ask, in one prose message: `scope` (paths that may be modified), `metric_cmd`, `guard_cmd` (optional sanity check, e.g. the test suite), `direction` (higher or lower is better), `max_iterations` (default 20). Unattended, with nobody answering: scope = the paths the goal names, direction inferred from the goal, no guard, 20 iterations — print what you assumed.
3. Validate the metric once, here. Run `metric_cmd` into a `mktemp` log and read the number out of it. Contract: it prints exactly one number to stdout and exits 0. No number, several numbers, or a non-zero exit → fix the command with the user before starting. Every later iteration trusts this contract.
4. `git status --porcelain` must be empty, then `git checkout -b autoresearch/<slug>` (slug = the goal lowercased, runs of non-`[a-z0-9]` collapsed to `-`, trimmed to 40 chars).
5. Baseline = the number from step 3, logged as iteration 0.
6. Write the two state files, then print the card: goal, scope, metric + direction + baseline, guard, max iterations, branch, and `--abort` to stop.

## State contract

Both files live in the project root on the experiment branch, and are written
atomically: temp file in the same directory, then `mv` over the target.

`autoresearch-scratchpad.md` — frontmatter: `goal`, `scope`, `metric_cmd`,
`guard_cmd`, `direction` (`higher_is_better` | `lower_is_better`),
`best_metric`, `best_commit`, `iteration`, `max_iterations`, `status`
(`active` | `complete` | `aborted`). Body: four sections of terse bullets —
`## What worked`, `## What failed`, `## Next to try`, `## Blocked ideas`.
Extra or missing fields left by an older run are tolerated and kept; there is
no migration step.

`autoresearch-history.tsv` — append-only, tab-separated, header
`iteration	commit	metric	delta	status	description`, one row per
iteration. `status` is BASELINE, KEEP, DISCARD, CRASH or GUARD_FAIL; `commit`
is the hash on KEEP and `REVERTED` otherwise.

## Iteration

**1. Read.** Scratchpad frontmatter and body, last 20 rows of the history
file, `git log --oneline -15`. The working tree must be clean — if it is not,
stash and investigate before going on. Count the trailing run of
DISCARD/CRASH/GUARD_FAIL rows.

**2. Ideate.** Exactly one hypothesis, taking the first rung that applies:
last status CRASH → fix the crash before anything new; a recent KEEP →
exploit it with a variation; otherwise → explore the top item of
`## Next to try`; more than 5 consecutive discards → pivot, re-reading the
whole scratchpad and combining near-misses into a structurally different
approach; the last three iterations produced the same diff
(`git show --format= <commit> | md5sum`) or repeated one description →
circuit-break, move that idea to `## Blocked ideas` and pick another. Nothing
left to pick means the run is over — stop and report.

**3. Delegate.** Spawn a sub-agent (`spawn_agent` / `wait_agent`) with the
hypothesis, `scope`, iteration number, goal and a few lines of recent
learnings. It edits and commits; the parent reads no source files and no
diffs, which is what keeps its context flat across iterations. Wait for it to
finish before verifying anything. Its final message is the only return channel:
`result: applied|aborted`, `commit`, `files_changed`, `summary`, `lesson`.
On `result: aborted` nothing was committed — skip Verify and log DISCARD with
its `summary`. A worker cut off by maxTurns or a rate limit returns partial
output, and a final message missing those keys is no better: treat both as
aborted, log DISCARD, note "partial" in the description. Without multi-agent
support, apply the change inline instead — reading only the in-scope files the
hypothesis touches.

**4. Verify.** Metric first: `mktemp` a log, run `metric_cmd` into it, extract
the single number. Non-zero exit or no number → CRASH. Then `guard_cmd`, if
set, into its own fresh log: non-zero exit → GUARD_FAIL, with no rework
attempt. A metric or guard that normally runs longer than ~10 minutes goes
through Bash in the background — wait for its completion notification instead
of blocking a foreground call.

**5. Decide.** KEEP only when the number moved the right way for `direction`
and the guard passed; then update `best_metric` and `best_commit`. Otherwise
`git revert --no-edit HEAD` and record DISCARD, CRASH or GUARD_FAIL.

**6. Log.** Append the history row. Update the scratchpad body — what worked,
what failed and why, ideas pruned and added, dead ends moved to blocked; a
non-empty `lesson` from the worker goes into `## Next to try` prefixed
`[from worker iter N]`. Increment `iteration`, write atomically, print one
line: `iter <N>: <STATUS> — metric <value> (best <best>, delta <d>)`. Then go
back to step 1 unless the run is finished.

## Stuck: rescue

Optional, and only with the `claude` CLI on PATH. After 3 consecutive
DISCARD/CRASH/GUARD_FAIL, pipe a read-only diagnosis prompt (goal,
`metric_cmd`, direction, the last 3 history rows, the scratchpad body, and
"propose one fundamentally different approach, do not edit files") into
`claude -p` via Bash. Append the suggestion to `## Next to try` as
`[from rescue iter N] <one line>`. Never apply a patch it proposes. No second
model on PATH means no rescue; just pivot.

## Finish

`iteration >= max_iterations`, checked after every Log, sets `status: complete`
and prints the summary: best metric against baseline with delta, iterations
run / kept / discarded, best commit, branch, and
`git switch main && git merge autoresearch/<slug>` to take the result. An
early stop (no ideas left, circuit breaker) prints the same summary plus the
reason.

`--continue` re-reads the state files and resumes at step 1. When `status` is
`complete` or `aborted`, or `iteration >= max_iterations`, ask whether to
extend the cap, start fresh, or stop; with nobody to ask, print the state and
stop.

`--abort` sets `status: aborted`, prints the summary and exits. Kept commits
stay on the branch, and both state files stay with them as the record of the
run.

## Codex differences

- Delegation uses Codex's own `spawn_agent` / `wait_agent`; the contract is the
  one packaged for Claude Code as the `as:autoresearch-worker` agent.
- Setup questions are asked in prose; under `codex exec` without a TTY the
  defaults above are printed, never chosen silently.
- Rescue calls `claude -p`, since `codex exec` is this loop's own model.
