# Verification Evidence Template

> Helper template only — not repo canon.

## When to use
Use after implementation to record proof in locus-first order:
1. local/minimal proof,
2. shortest relevant chain,
3. formal chain only if the locus and band require it.

## Template
```md
# Verification Evidence — <task>
- Status: <Pending|Complete>
- Disposition: <Pending acceptance|Accepted|Rejected|Abandoned>
- Pre-apply review: <Pending|Approved|Waived>
- Review owner / evidence: <...>
- Execution band: <B1|B2|B3>
- Owning locus / layer: <...>
- Standards loaded: <...>

## Verification plan summary
- Goal: <what the proof must show>
- Scope: <what this verification covers>
- Not-do list:
  - <what this proof does not claim>

## Evidence log
| Proof level | Command / check | Input mode | Result | Evidence path / note |
| --- | --- | --- | --- | --- |
| Local/minimal | <test/lint/manual check> | <fixture|local|real> | <pass/fail> | <path or note> |
| Shortest relevant chain | <integration/boundary check> | <fixture|local|real> | <pass/fail|n/a> | <path or note> |
| Formal chain | <governed chain validation> | <real|n/a> | <pass/fail|not required> | <path or note> |

## I/O contract evidence
- Inputs exercised: <...>
- Outputs observed: <...>
- Forbidden/default/failure behavior checked: <...>

## Acceptance criteria check
- [ ] <criterion> — <evidence>
- [ ] <criterion> — <evidence>

## Residual risk / gap
- Remaining gap: <none|...>
- Why acceptable or why follow-up is required: <...>

## Retro / doc decision
- Docs/runbooks updated: <yes/no>
- If no, why not: <...>
```

## Usage notes
- **B1:** one short local proof may be enough if the task stays inside one locus.
- **B2:** expect local proof plus the shortest real boundary chain.
- **B3:** include explicit governed-surface evidence and note any real-input gating.
