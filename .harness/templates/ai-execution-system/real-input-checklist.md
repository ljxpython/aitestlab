# Real-Input Checklist

> Helper checklist only — not repo canon.

## When to use
Use only when trustworthy verification depends on user-owned or environment-owned real inputs.
It is conditional even for B3 and is not required when no such input exists.

## Rule
AI may identify required real inputs, but must not invent or silently substitute them.

## Checklist
```md
# Real-Input Checklist — <task>
- Execution band: <B2|B3>
- Why real inputs are needed: <1 line>

## Required real inputs
| Input | Type | Owner | Where it comes from | Safe placeholder allowed? | Blocking? |
| --- | --- | --- | --- | --- | --- |
| <name> | <secret|dataset|env param|account|endpoint> | <user|ops|team> | <source> | <yes/no> | <yes/no> |

## Handling rules
- Never fabricate: <keys, secrets, production params, datasets>
- Allowed substitutes for early work: <mock/stub/local fixture/none>
- What remains blocked without the real input: <verification or rollout step>

## Verification impact
- Local proof possible without real input: <yes/no — how>
- Shortest real chain needing real input: <...>
- Formal-chain proof needing real input: <...|not required>

## User / owner handoff
- Need from owner:
  - <item>
- Safe next step once supplied:
  - <item>

## Decision
- Proceed with placeholder-safe work only: <yes/no>
- Escalate / pause until real input arrives: <yes/no>
```

## Quick checks
- If the task depends on production-like data or real secrets, surface that immediately.
- If local proof is still possible with fixtures, state the exact boundary where real input becomes mandatory.
