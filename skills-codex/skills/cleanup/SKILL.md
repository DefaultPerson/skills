---
name: cleanup
description: >
  Losslessly reorganize a messy notes/plan/chat dump into a clean sectioned
  markdown file, with three-level gap detection that proves nothing was lost.
  Use when the input is unstructured (chat export, dumped notes, brainstorm)
  and over ~50 lines. Multiple input files produce one cleaned output each,
  never a merged file. Not for already-structured docs, files under 30 lines,
  or when the user wants a summary. Triggers: "cleanup", "почисти",
  "реорганизуй", "clean up", "rewrite plan", "sort plan".
allowed-tools: [Bash, Glob, Grep, Read, Edit, Write]
---

# cleanup

Sort → rewrite → prove nothing was lost. The proof is the point: a cleaned file whose gap detection was skipped is just a rewrite.

Each input file goes through the pipeline independently. N inputs → N outputs, never a merge: merging loses provenance, and a keyword from one file then fluke-matches in another's grep and masks a real gap.

## Pipeline

1. **Back up** every source to `<file>.bak`.
2. **Sort sections in place.** Parse `## ` sections and move misplaced lines into the right one. Move lines, never rewrite them.
3. **Check the sort.** Every non-empty source line must still be present: `comm -23 <(sed 's/[[:space:]]*$//' <file>.bak | grep . | sort) <(sed 's/[[:space:]]*$//' <sorted> | grep . | sort)` must print nothing. If it doesn't, restore from `.bak` and stop.
4. **Rewrite cleanly** into `<basename>.rewritten.<ext>`: fix grammar, drop exact duplicates, add `### ` subsections, fold chat noise into "Key takeaways" blocks. Preserve every idea. Don't bury critical content in `<details>` blocks.
5. **Find what was lost** — the three levels below. Output: `<basename>.gaps.md`.
6. **Stop and show the gaps.** Wait for the user's go-ahead before applying anything. Skip the wait only when there are zero gaps.
7. **Apply their decisions.** `[MISSING]`/`[UNCOVERED]` → insert, `[PARTIAL]` → augment, `[REVERSED]` → fix. Delete the gaps file.
8. **Final check against the ORIGINAL backup** (a different surface than the sorted file, so don't reuse step 5's results): run both scripts against `<file>.bak`, verify the survivors, then `mv <basename>.rewritten.<ext> <file>`. The `.bak` stays as the rollback.
9. **Report** per-source metrics plus an aggregate, then: `Cleanup done.` Recommend nothing downstream.

Inputs over ~2000 lines get expensive in step 5 — suggest splitting first.

## Gap detection

Three levels, in order, all mandatory. Each catches a class the others can't: the script sees only exact URLs, the section agents see ideas but only in their own section, the fuzzy net sweeps every line but only reports "missing", never "partial" or "reversed".

- **a — URLs, deterministic.** `python3 scripts/verify-rewrite.py <sorted> <rewritten>` (the `scripts/` and `roles/` directories sit next to this SKILL.md). Missing URLs go straight into the gaps file as `[MISSING]`.
- **b — per-section semantic.** Pre-filter with grep (2-3 distinctive keywords per line, searched **only within that source's own file** — this scoping is what keeps multi-file runs honest), then run one fresh agent per 1-2 sections with the `roles/gap-detector.md` prompt, placeholders filled in. Skip this level only for a single file under 50 lines; in multi-file mode it always runs, at least one agent per source. Findings merge in as `[MISSING]`/`[PARTIAL]`/`[REVERSED]`.
- **c — fuzzy net.** `python3 scripts/verify-coverage.py <sorted> <rewritten> <gaps>` writes unmatched lines to a `.uncovered.tmp` file (it prints the path — use that, don't construct it). Verify them in batches of ~100 with `roles/coverage-verifier.md`; only `TRUE_MISSING` lines become `[UNCOVERED]` gaps. Delete the temp file afterwards.

In step 8, run the same two scripts against `<file>.bak`. When step 5c found zero true gaps and the sorted file differs from the backup only by added headers, one agent over the whole uncovered list is enough (`loose`); otherwise batch as usual (`strict`).

## Outputs

Per source: `<source>.bak` (untouched original), `<source>` (overwritten at step 8), plus the transient `<basename>.rewritten.<ext>`, `<basename>.gaps.md` and `*.uncovered.tmp`, all gone by the end.

Ship only when no `[MISSING]`/`[PARTIAL]`/`[REVERSED]`/`[UNCOVERED]` marker is left, both final checks pass, and the `.bak` files are in place. cleanup does not commit — the user owns their git history.

## Rails

- A finding needs a quote from **both** files. If you can't quote the rewritten equivalent, it is missing.
- Never apply gaps without the step 6 confirmation.
- Never merge multiple inputs into one output.
- Does not extract link content (run extract-links first), does not handle JSON/YAML/code dumps, does not summarize.

## Codex differences

- Gap detection must run in **fresh context**, not inline: this session already holds both the original and the rewrite, so it will "see" coverage that isn't there. Run each check as its own `codex exec -` subprocess (or `spawn_agent`) fed the substituted role file — sequentially, or in parallel with `xargs -P 4`. Correctness over latency.
- Substitute the role placeholders with `sed` (`sed -e 's|{sorted_path}|…|g' …`) — `envsubst` only expands `$VAR`, not the `{brace}` placeholders these roles use.
- Step 6 needs a person. Under `codex exec` with no TTY, stop with an explicit error instead of auto-applying the gaps.
