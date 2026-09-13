---
name: verify-done
description: >
  Acceptance gate for finished work: re-runs the plan's `Done when:` proofs,
  generates and runs independent scenarios grounded in the original intent, and
  adds an advisory maintainability pass. Read-only — it reports DONE / NOT-DONE
  and a gap list, it never fixes anything. Use when a plan or task is finished
  (or at a milestone) and you want one honest verdict on whether the result
  actually works; not for a single small change or diff-level bug hunting.
  Triggers: "verify-done", "acceptance gate", "is this actually done",
  "приёмка", "проверь что готово".
allowed-tools: [Bash, Glob, Grep, Read]
---

# verify-done

Does the built thing do what it was meant to do, including what the plan didn't think of? A gate, not a fixer: it reports and hands its findings back.

`--deep` widens scenario generation from the top risks to everything. `--block-on-quality` lets high-severity maintainability findings flip the verdict.

## Inputs

Two shapes, and the first one that applies wins:

- **A file with `Done when:` lines** — every such line is a proof (the command in it is what gets re-run), and the surrounding prose is the intent. That is a grep contract, not a format: a task list, a charter with an audit table, or a hand-written checklist all work. Any unresolved blocking question in it goes straight to the not-covered bucket — an open decision means the work isn't acceptable yet, so never bless around it.
- **Prose intent** — an approved plan, an inline description, or "here's the diff and what it was supposed to do". Derive two or three concrete shell proofs from what it promises, and treat the prose itself as the intent.

Also pick up the repo's build / test / regression commands if they're obvious. If nothing identifies the real intent, ask once; if there is nobody to ask, state the intent you assumed in the verdict header and carry on.

## Tiers

Run in this order, in the working tree as it is (a fresh worktree holds the last commit, not the uncommitted work under test):

1. **Conformance** — every proof plus build/test/regression, each `PASS` / `FAIL` / `UNKNOWN`.
2. **Scenarios** — derive risk-ranked user, edge and adversarial cases from the original intent, then run the runnable ones. This is what catches what the plan's own proofs missed.
3. **Quality** — advisory maintainability findings using the prompt in `roles/quality-review.md` (next to this SKILL.md), last, and only when behaviour already works.

## Honesty rails

1. **UNKNOWN is not a pass and not a fail.** Nothing runnable → everything UNKNOWN → `NOT-DONE, could not verify`. Never a hopeful DONE, never a FAIL for something you couldn't exercise.
2. **Every scenario is grounded** in a quote from the original intent. "It doesn't do X" where X was never asked for is UNKNOWN plus "confirm with a human", not a failure. Ungrounded candidates are discarded and counted.
3. **No silent truncation.** Everything unrun or unknown is listed in the not-covered bucket.

## Output

```
VERDICT: DONE | NOT-DONE — <reason>
  Conformance: N/M PASS, K UNKNOWN
  Scenarios:   G generated (D discarded), R ran; confirmed gaps: …
  Quality:     F findings (advisory | blocking)
  NOT covered (check manually): …
```

DONE requires conformance fully passing, no confirmed scenario gap, and quality not blocking. With no proofs at all, the verdict rests on scenarios alone — say so in the reason, it is a softer result than a proof-driven one.

## Codex differences

- No Workflow tool: the three tiers run in-session, in order. Scenario generation and the quality pass belong in a fresh sub-agent (`spawn_agent` / `wait_agent`) or a `codex exec -` subprocess — this session already knows what it built, and a self-review from that context grades itself.
- Never edit anything here. The verdict is the deliverable.
