---
name: verify-done
description: >
  Acceptance gate for finished work: re-runs the plan's `Done when:` proofs,
  generates and runs independent scenarios grounded in the original intent, and
  adds an advisory maintainability pass. Read-only — it reports DONE / NOT-DONE
  and a gap list, it never fixes anything. Triggers: "verify-done",
  "/as:verify-done", "acceptance gate", "is this actually done", "приёмка",
  "проверь что готово".
when_to_use: >
  A plan or task is finished (or at a milestone) and you want one honest verdict
  on whether the result actually works — not whether the checkboxes are ticked.
  NOT for a single small change (use /verify), not for diff-level bug hunting
  (use /code-review). Run it at the end, not per stage.
argument-hint: "[<plan file>] [--deep] [--block-on-quality]"
allowed-tools: [Bash, Glob, Grep, Read, Agent, Workflow, AskUserQuestion]
---

# verify-done

Does the built thing do what it was meant to do, including what the plan didn't think of? A gate, not a fixer: it has no Edit or Write, and hands its findings back.

`--deep` widens scenario generation from the top risks to everything. `--block-on-quality` lets high-severity maintainability findings flip the verdict.

## Inputs

Two shapes, and the first one that applies wins:

- **A file with `Done when:` lines** — every such line is a proof (the command in it is what gets re-run), and the surrounding prose is the intent. That is a grep contract, not a format: a task list, a charter with an audit table, or a hand-written checklist all work. Any unresolved blocking question in it goes straight to the not-covered bucket — an open decision means the work isn't acceptable yet, so never bless around it.
- **Prose intent** — an approved plan-mode plan, an inline description, or "here's the diff and what it was supposed to do". Derive two or three concrete shell proofs from what it promises, and pass the prose itself as the intent.

Also pick up the repo's build / test / regression commands if they're obvious. If nothing identifies the real intent, ask once; if there is nobody to ask, state the intent you assumed in the verdict header and carry on.

⚠️ The workflow's subagents cannot see this conversation. A plan that exists only in the transcript must be passed to them in `intentNotes` — otherwise scenario generation silently has nothing to ground itself in.

## Run

```
Workflow({ scriptPath: "${CLAUDE_SKILL_DIR}/workflows/verify-done.workflow.js", args: {
  doneWhenProofs, buildCmd, testCmd, regressionCmd, intentNotes,
  deep, blockOnQuality,
  qualityPromptPath: "${CLAUDE_SKILL_DIR}/roles/quality-review.md",
  where } })
```

`where` is normally `.` — proofs must exercise the code as it is, and a fresh git worktree contains the last commit, not the uncommitted work under test. Use a worktree only when the change is committed **and** a proof mutates state you don't want touched; create it under `.claude/worktrees/` so it doesn't stop to ask.

If the Workflow tool is unavailable, run the same three tiers with `Agent(subagent_type: "fork")` calls instead — same schemas, sequential, and a fork also sees the conversation, which solves the intent-passing problem above.

## Tiers

1. **Conformance** — every proof plus build/test/regression, each `PASS` / `FAIL` / `UNKNOWN`.
2. **Scenarios** — one agent reads the original intent and writes risk-ranked user, edge and adversarial cases; the runnable ones execute. This is what catches what the plan's own proofs missed.
3. **Quality** — advisory maintainability findings, last, and only when behaviour already works.

## Honesty rails

1. **UNKNOWN is not a pass and not a fail.** Nothing runnable → everything UNKNOWN → `NOT-DONE, could not verify`. Never a hopeful DONE, never a FAIL for something you couldn't exercise.
2. **Every scenario is grounded** in a quote from the original intent. "It doesn't do X" where X was never asked for is UNKNOWN plus "confirm with a human", not a failure. Ungrounded candidates are discarded and counted.
3. **No silent truncation.** Everything unrun or unknown is listed in the not-covered bucket, including anything dropped to stay inside the agent budget.

## Output

```
VERDICT: DONE | NOT-DONE — <reason>
  Conformance: N/M PASS, K UNKNOWN
  Scenarios:   G generated (D discarded), R ran; confirmed gaps: …
  Quality:     F findings (advisory | blocking)
  NOT covered (check manually): …
```

DONE requires conformance fully passing, no confirmed scenario gap, no high-risk scenario left unrun, and quality not blocking. With no proofs at all, the verdict rests on scenarios alone — say so in the reason, it is a softer result than a proof-driven one.

Confirmed failures go back to whoever is building; quality findings go to `/simplify`.
