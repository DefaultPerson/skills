# Gap detector — per-section semantic comparison

Compare your assigned sections of the sorted file against the rewritten file and report ideas that were lost, weakened, or inverted.

## Inputs

- Sorted file (source of truth): `{sorted_path}`
- Rewritten file (under check): `{rewritten_path}`
- Your sections: `{sections}` (1-2 of them)

## What to do

For every non-empty line in your sections, grep 3-5 distinctive words across the **whole** rewritten file — an idea may legitimately have moved to another section, and that is not a gap. The rewritten file may wrap content in `<details>`, `<summary>` or `<table>`; content inside those tags counts as present, so grep inside them too.

Then classify:

- Same meaning, anywhere in the file → skip.
- Present but a concrete detail is gone → **PARTIAL**. `Pricing: $50/mo, 14-day trial` → `Pricing: $50/mo` loses the trial. `https://example.com/post/123` → `https://example.com` loses the post.
- Meaning changed or inverted → **REVERSED**.
- Nowhere in the file → **MISSING**.

Not gaps: grammar, capitalisation, punctuation, typo fixes, bullet↔checkbox, link-text changes, merged adjacent sentences, or any rephrasing that keeps the idea and its details.

## Evidence is mandatory

Quote the exact text from both files. If you cannot quote the rewritten equivalent, it IS missing. A finding without quotes is not a finding.

## Output

```
SECTION: <header>
TYPE: MISSING|PARTIAL|REVERSED
SORTED_LINE: "<exact quote>"
REWRITTEN_LINE: "<exact quote or NOT_FOUND>"
LOST_DETAIL: "<what was lost>"   (PARTIAL only)
```

No gaps in your sections → one line: `NO GAPS in [sections]`.
