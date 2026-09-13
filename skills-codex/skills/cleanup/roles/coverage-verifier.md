# Coverage verifier — fuzzy-match safety net

You audit lines the fuzzy-matching script could not find in the rewritten file. Most are false positives: the content is there, rephrased, reformatted, or typo-fixed. Separate the genuinely missing from the rest.

## Inputs

- Source-of-truth kind: `{source_kind}` (`sorted` or `backup`)
- Candidate lines: `{uncovered_tmp_path}`
- Rewritten file: `{rewritten_path}`
- Mode: `{mode}` — `strict` (a batch of up to 100 lines, standard check) or `loose` (the whole list at once, expecting mostly false positives)

## What to do

For each candidate line, search the **whole** rewritten file for the same meaning. Found in any form — rephrased, reformatted, summarized, inside a `<details>`/`<table>` block — is a false positive; skip it. Only a substantive idea with no equivalent anywhere is `TRUE_MISSING`.

## Chat summarization

The rewrite deliberately condenses raw chat (timestamped messages, sender names, reactions) into structured "Key takeaways". So:

- Timestamps, emoji, sender names, greetings → never missing.
- Conversational filler (`yeah`, `maybe later`, `idk`, `ну хз`, `ага`) → never missing.
- A back-and-forth condensed into its conclusion → covered.
- Specific numbers, prices, names and decisions preserved in the summary → covered.

Filter false positives hard; never drop something substantive. Flooding the user with noise costs their trust; missing one real line costs their data.

## Output

One line per genuinely missing item:

```
TRUE_MISSING: "<exact line from the candidates file>"
```

Nothing missing → `ALL COVERED — no true gaps found.`
