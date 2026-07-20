# Execution-Band Artifact Skeletons

> Helper only. Canonical rules live in
> `docs/standards/01-ai-execution-system.md`.

## B1 Local

Default: keep this in the conversation; do not create a file.

```md
- Goal:
- Scope:
- Change:
- Verify:
```

Use when one locus can close the work without changing a governed surface.

## B2 Chain

Keep a short plan in the conversation by default. Use OpenSpec when behavior or
acceptance criteria need durable review, or for multi-session collaboration/handoff.

```md
# <task>

- Goal:
- Scope / non-goals:
- Owning locus:
- Shortest affected chain:
- Standards loaded:
- Implementation steps:
- Acceptance criteria:
- Verification:
  - local:
  - shortest chain:
- Doc decision:
```

B2 should not produce both this short plan and an OpenSpec change.

## B3 Governed

Use OpenSpec:

```text
proposal -> specs -> design (when needed) -> tasks
         -> apply -> verification -> archive
```

Required concerns:

- impact and non-goals
- affected capability/contract
- owner and boundary changes
- acceptance scenarios
- implementation tasks
- verification and rollback expectations

Conditional artifacts:

- design/ADR: real architecture choice
- dedicated Test Spec: complex or high-risk verification matrix
- real-input checklist: user-owned inputs are required
- runbook: deployment or recovery changes
- repo report: cross-change summary

Do not create a duplicate in both `.harness/plans/` and `openspec/changes/`.

## Usage

- B1 is the default for bounded local work.
- B2 covers one locus or the shortest adjacent chain.
- B3 is selected by governed risk, not task size or research alone.
- Always verify local first, then expand only as required.
