export const meta = {
  name: 'verify-done-gate',
  description: 'Tiered acceptance gate: conformance proofs + independent scenarios + advisory quality',
  phases: [
    { title: 'Conformance', detail: 'run every Done-when proof + build/test/regression' },
    { title: 'Scenarios', detail: 'generate scenarios from the original intent, run the runnable ones' },
    { title: 'Quality', detail: 'advisory maintainability pass (only if behaviour works)' },
    { title: 'Synthesis', detail: 'DONE / NOT-DONE + buckets' },
  ],
}

// ── args (assembled by SKILL.md) ──
//   doneWhenProofs    : [{id, title, cmd}] — from `Done when:` lines, or derived from
//                       a prose plan. May be [] — then the verdict leans on Tier 2.
//   buildCmd, testCmd, regressionCmd : string|null
//   intentNotes       : the ORIGINAL intent text — Tier-2 grounding
//   deep              : bool (--deep; default false = light)
//   blockOnQuality    : bool (--block-on-quality; default false = advisory)
//   qualityPromptPath : path to roles/quality-review.md (the agent reads it itself)
//   where             : directory to run in (default '.', the working tree as-is)
const a = args || {}
const deep = !!a.deep
const where = a.where || '.'
const MODEL = 'opus'
const MAX_SCENARIO_RUNS = deep ? 24 : 10

const PROOF = {
  type: 'object', additionalProperties: false,
  required: ['id', 'verdict', 'evidence'],
  properties: {
    id: { type: 'string' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNKNOWN'] },
    evidence: { type: 'string', description: 'cmd + exit code + last lines, or why UNKNOWN' },
  },
}
const SCEN = {
  type: 'object', additionalProperties: false,
  required: ['scenario', 'risk', 'category', 'verdict', 'confidence', 'evidence', 'groundedIn'],
  properties: {
    scenario: { type: 'string' },
    risk: { type: 'string', enum: ['high', 'med', 'low'] },
    category: { type: 'string', enum: ['user-case', 'edge', 'adversarial'] },
    verdict: { type: 'string', enum: ['PASS', 'FAIL', 'UNKNOWN'] },
    confidence: { type: 'string', enum: ['high', 'med', 'low'] },
    evidence: { type: 'string' },
    groundedIn: { type: 'string', description: 'quote/ref from the original intent' },
  },
}
const SCEN_GEN = {
  type: 'object', additionalProperties: false,
  required: ['scenarios', 'discarded'],
  properties: {
    scenarios: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['scenario', 'risk', 'category', 'runnable', 'groundedIn'],
        properties: {
          scenario: { type: 'string' },
          risk: { type: 'string', enum: ['high', 'med', 'low'] },
          category: { type: 'string', enum: ['user-case', 'edge', 'adversarial'] },
          runnable: { type: 'boolean', description: 'can this be executed with a shell/test command here?' },
          groundedIn: { type: 'string', description: 'quote/ref from the original intent (REQUIRED — ungrounded ⇒ discard)' },
        },
      },
    },
    discarded: { type: 'integer', description: 'candidate scenarios dropped as ungrounded/out-of-scope' },
  },
}
const QUALITY = {
  type: 'object', additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['severity', 'category', 'location', 'finding', 'remedy'],
        properties: {
          severity: { type: 'string', enum: ['high', 'med', 'low'] },
          category: { type: 'string', enum: ['file-size', 'spaghetti', 'indirection', 'type-boundary', 'layer-leak', 'orchestration', 'duplication'] },
          location: { type: 'string' },
          finding: { type: 'string' },
          remedy: { type: 'string' },
        },
      },
    },
  },
}

const RAILS = `Honesty rails (mandatory):
- UNKNOWN ≠ pass and ≠ fail. If you cannot actually run the check here (no runnable env / missing deps / server down), return verdict "UNKNOWN" with the reason — never guess PASS or FAIL.
- Quote real output as evidence. No command run ⇒ UNKNOWN.`

const proofPrompt = (p) => `You are verifying ONE acceptance proof of an already-built change, in: ${where}.
Task: ${p.title || p.id}
Run exactly this and judge it: \`${p.cmd}\`
Return PASS if it succeeds as intended, FAIL if it fails, UNKNOWN if it can't be run here. Use id "${p.id}".
${RAILS}`

const suitePrompt = (cmd) => `Run the project check \`${cmd}\` in ${where} and report PASS/FAIL/UNKNOWN with the tail of its output as evidence. Use id "${cmd}".
${RAILS}`

const genPrompt = (notes) => `You generate acceptance SCENARIOS to test whether a built change actually works for real usage — independently of the task list, which may have blind spots.

ORIGINAL INTENT (ground every scenario in THIS — not in a task list):
"""
${notes || '(none provided — generate only what the change visibly implies; be conservative)'}
"""

Rules:
- Generate ${deep ? 'a thorough set across all requirements + adversarial inputs' : 'a LIGHT set: the top high/med-risk user-cases plus a couple of edge/adversarial cases'}.
- Every scenario MUST be grounded: put a quote or reference from the ORIGINAL INTENT in groundedIn. Do NOT invent requirements the intent never stated — drop those and count them in "discarded".
- Mark "runnable": true only if it can be checked here with a shell/test command in "${where}".
- Rank by risk. Categories: user-case / edge / adversarial.`

const runPrompt = (s) => `Execute this acceptance scenario against the built change in ${where} and judge it:
SCENARIO: ${s.scenario}
(grounded in: ${s.groundedIn}; risk ${s.risk}; ${s.category})
Return PASS/FAIL/UNKNOWN + evidence + your confidence. A FAIL that merely reflects a feature the intent never asked for is NOT a fail — return UNKNOWN with confidence low and note "out-of-scope, confirm with human".
${RAILS}`

const qualityPrompt = () => `${a.qualityPromptPath
  ? `Read the review instructions at ${a.qualityPromptPath} and follow them exactly.`
  : 'Audit the change for maintainability: structural simplification, oversized files, ad-hoc conditionals, needless indirection, unclear type boundaries, layer leaks, duplication. Findings only.'}

Audit target: the changes just built in ${where}. Start from \`git diff HEAD\` (and \`git diff --stat\`); if the tree is clean, audit the most recent commit's diff (\`git show --stat HEAD\`). Judge only what that diff touches.

Emit the structured findings the instructions define. Findings only — no prose verdict.`

// ── Tier 1 — Conformance ──
phase('Conformance')
const proofs = a.doneWhenProofs || []
const suites = [a.buildCmd, a.testCmd, a.regressionCmd].filter(Boolean)
const t1Items = [...proofs.map((p) => ({ kind: 'proof', p })), ...suites.map((cmd) => ({ kind: 'suite', cmd }))]
const t1Raw = await pipeline(t1Items, (item) => item.kind === 'proof'
  ? agent(proofPrompt(item.p), { label: `proof:${item.p.id}`, phase: 'Conformance', schema: PROOF, model: MODEL })
  : agent(suitePrompt(item.cmd), { label: `suite:${item.cmd}`, phase: 'Conformance', schema: PROOF, model: MODEL }))
const t1 = t1Raw.filter(Boolean)
// An agent that errored, was stopped, or was dropped for budget comes back null.
// Those checks did NOT pass — they were never run, and must not vanish.
const t1Dropped = t1Items.filter((_, i) => !t1Raw[i]).map((item) => ({
  id: item.kind === 'proof' ? item.p.id : item.cmd,
  evidence: 'check did not run (agent dropped, stopped, or over budget)',
}))
const t1Ran = t1.length > 0
const tier1Pass = t1Ran && t1Dropped.length === 0 && t1.every((r) => r.verdict === 'PASS')
const tier1Unknown = t1.some((r) => r.verdict === 'UNKNOWN')
log(`Conformance: ${t1.filter((r) => r.verdict === 'PASS').length}/${t1Items.length} PASS, ${t1.filter((r) => r.verdict === 'UNKNOWN').length} UNKNOWN, ${t1Dropped.length} did not run`)

// ── Tier 2 — Independent scenarios ──
phase('Scenarios')
const gen = await agent(genPrompt(a.intentNotes), { label: 'scenario-gen', phase: 'Scenarios', schema: SCEN_GEN, model: MODEL })
const scenarios = (gen && gen.scenarios) || []
const runnable = scenarios.filter((s) => s.runnable)
const picked = runnable
  .slice()
  .sort((x, y) => ({ high: 0, med: 1, low: 2 }[x.risk] - { high: 0, med: 1, low: 2 }[y.risk]))
  .slice(0, MAX_SCENARIO_RUNS)
const dropped = runnable.length - picked.length
if (dropped > 0) log(`Scenarios: ${dropped} runnable scenario(s) over the ${MAX_SCENARIO_RUNS} cap — reported as not covered, not as passing`)
const ranRaw = await pipeline(picked, (s) =>
  agent(runPrompt(s), { label: `scenario`, phase: 'Scenarios', schema: SCEN, model: MODEL }))
const ran = ranRaw.filter(Boolean)
const asUnknown = (s, why) => ({
  scenario: s.scenario, risk: s.risk, category: s.category, groundedIn: s.groundedIn,
  verdict: 'UNKNOWN', confidence: 'low', evidence: why,
})
// Same rule as Tier 1: a scenario whose agent came back null was not executed.
const scenarioDropped = picked.filter((_, i) => !ranRaw[i])
  .map((s) => asUnknown(s, 'scenario did not run (agent dropped, stopped, or over budget)'))
const unrun = scenarios.filter((s) => !picked.includes(s))
  .map((s) => asUnknown(s, s.runnable ? 'over the per-run scenario cap — check manually' : 'not runnable here — check manually'))
const t2 = [...ran, ...scenarioDropped, ...unrun]
const tier2RealGap = t2.some((s) => s.verdict === 'FAIL' && s.confidence !== 'low')
// A high-risk scenario nobody could run is not evidence of success.
const tier2BlindSpot = t2.some((s) => s.verdict === 'UNKNOWN' && s.risk === 'high')
log(`Scenarios: ${scenarios.length} generated (${gen ? gen.discarded : 0} discarded), ${ran.length} ran, ${t2.filter((s) => s.verdict === 'UNKNOWN').length} UNKNOWN`)

// ── Tier 3 — Quality (advisory; only if behaviour works) ──
phase('Quality')
const behaviorWorks = (tier1Pass || !t1Ran) && !tier2RealGap && !tier2BlindSpot
let t3 = { findings: [] }
if (behaviorWorks) {
  t3 = (await agent(qualityPrompt(), { label: 'quality', phase: 'Quality', schema: QUALITY, model: MODEL })) || { findings: [] }
  log(`Quality: ${t3.findings.length} findings (${a.blockOnQuality ? 'blocking on high' : 'advisory'})`)
} else {
  log('Quality skipped — behaviour not confirmed working')
}

// ── Synthesis ──
phase('Synthesis')
const qualityBlocks = !!a.blockOnQuality && (t3.findings || []).some((f) => f.severity === 'high')
// Based on what was ASKED for, not what came back: if every proof agent died,
// that is a failed conformance tier, not a plan that had no proofs.
const scenarioOnly = t1Items.length === 0
// Nothing actually executed is never a pass — that is honesty rail 1.
const nothingRan = !t1Ran && ran.length === 0
const verdict = !nothingRan && (tier1Pass || scenarioOnly) && !tier2RealGap && !tier2BlindSpot && !qualityBlocks
  ? 'DONE' : 'NOT-DONE'
const reason = nothingRan
  ? 'nothing could be run — could not verify (no proofs, no runnable scenarios)'
  : !tier1Pass && !scenarioOnly
  ? (t1Dropped.length ? 'some conformance checks never ran' : tier1Unknown ? 'conformance UNKNOWN — could not verify (no runnable env?)' : 'conformance FAIL')
  : tier2RealGap ? 'a confirmed scenario gap'
  : tier2BlindSpot ? 'a high-risk scenario could not be run — could not verify'
  : qualityBlocks ? 'high-severity quality findings (--block-on-quality)'
  : scenarioOnly ? 'no conformance checks existed — scenario-driven verdict only (softer than proof-driven)'
  : 'all gates passed'
return {
  verdict,
  reason,
  conformance: { pass: tier1Pass, ran: t1Ran, results: t1, didNotRun: t1Dropped },
  scenarios: { realGap: tier2RealGap, blindSpot: tier2BlindSpot, discarded: gen ? gen.discarded : 0, results: t2 },
  quality: { advisory: !a.blockOnQuality, findings: t3.findings || [] },
  notCovered: [   // no silent truncation — every UNKNOWN, dropped, unrun or capped item
    ...t1.filter((r) => r.verdict === 'UNKNOWN').map((r) => ({ tier: 'conformance', id: r.id, evidence: r.evidence })),
    ...t1Dropped.map((r) => ({ tier: 'conformance', id: r.id, evidence: r.evidence })),
    ...t2.filter((s) => s.verdict === 'UNKNOWN').map((s) => ({ tier: 'scenarios', scenario: s.scenario, risk: s.risk, evidence: s.evidence })),
  ],
}
