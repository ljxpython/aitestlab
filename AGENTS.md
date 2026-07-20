# Root AGENTS Routing Surface

This file is the repo's thin AI routing and execution gate. Canonical rules live in
`docs/standards/01-ai-execution-system.md`; human guidance lives in
`docs/ai-execution-system-usage-guide.md`.

For an explicit guided intake, invoke `$route-project-change`. The Skill applies this
routing surface but does not override root or leaf standards.

## 1. Read Order

For non-trivial work:

1. Read this file.
2. Resolve the narrowest authoritative leaf document.
3. Use the repo standard only for cross-leaf routing and escalation.
4. Read knowledge/history only when rationale is needed.

Authority order:

1. leaf-local current standard
2. repo current standard
3. supporting knowledge
4. `.harness` plans/templates/reports

`.harness` and `openspec` help execution; neither may override repo or leaf policy.

## 2. Intake

Resolve these before implementation:

1. **Locus**: which app/service/repo surface owns the change?
2. **Chain**: local, shortest adjacent chain, or governed cross-boundary chain?
3. **Standards**: which narrow leaf documents apply?
4. **Band**: B1 Local, B2 Chain, or B3 Governed?
5. **Verification**: what is the smallest proof that covers the affected boundary?

Every band follows the same execution loop:

`analyze -> scope -> plan -> pre-apply gate when required -> implement -> verify -> accept -> summarize`

The band changes artifact persistence and verification depth, not whether analysis,
planning, or checking happens.

## 3. Execution Bands

| Band | Use when | Artifact | Verification |
| --- | --- | --- | --- |
| B1 Local | one locus, no governed contract | no file or OpenSpec change by default | local/minimal |
| B2 Chain | bounded work in one locus or shortest adjacent chain | short plan; OpenSpec only when durable alignment is needed | local + shortest chain |
| B3 Governed | governed contract, policy, ownership, migration, release, or cross-boundary risk | OpenSpec change | formal evidence at the required boundary |

Code size does not choose the band. A one-line public contract change can be B3.

B3 is required when any of these is true:

- public/governed contract or repo/leaf policy changes
- auth, permission, audit, data ownership, or migration semantics change
- ownership moves across loci
- production rollout/rollback or external compatibility needs formal review
- user-owned secrets, accounts, or datasets are required for trustworthy acceptance
- local and shortest-chain evidence cannot prove the result

Research alone is not B3 unless its decision affects a governed boundary.

## 4. Leaf Resolver

- `platform-web`
  - page/UI archetypes: `apps/platform-web/docs/frontend-development-playbook.md`
  - control-plane behavior: `apps/platform-web/docs/control-plane-page-standard.md`
- `platform-api`
  - module shape: `apps/platform-api/docs/handbook/*.md`
  - permission/audit/operations: `apps/platform-api/docs/standards/*.md`
- `runtime-service`
  - standards: `apps/runtime-service/runtime_service/docs/standards/*.md`
  - executable contracts: `apps/runtime-service/runtime_service/tests/harness/*.py`
- `runtime-web`
  - `apps/runtime-web/docs/standards/runtime-web-debug-standard.md`
- `interaction-data-service`
  - current API: `apps/interaction-data-service/docs/test-case-service-api-design.md`
  - ownership: `apps/interaction-data-service/docs/standards/result-domain-boundary-standard.md`

Load only the documents needed for the current locus and concern.

## 5. OpenSpec

OpenSpec is initialized with the official `core` profile and `spec-driven` schema.
Use its generated skills; do not wrap or fork them without repeated evidence that the
official workflow is insufficient.

`proposal -> specs -> design (when needed) -> tasks -> apply -> verify -> archive`

- B1 may use `openspec-explore` for thinking, but does not create a change by default.
- B2 creates an OpenSpec change only when behavior or acceptance criteria need durable
  review, or when multi-session collaboration/handoff justifies persistence.
- B3 must use an OpenSpec change and stop for owner review before apply. Proposal,
  specs, design, and tasks must be reviewed together. A bypass is allowed only when
  the owner explicitly grants a waiver and its reason is recorded before apply.

Harness owns locus, band, authority, verification depth, and human gates. OpenSpec
owns persisted change artifacts and their lifecycle. Never duplicate one change in
both `openspec/changes/` and `.harness/plans/`.

Every persisted B2/B3 change with `tasks.md` must maintain `verification.md` containing
the pre-apply review decision, commands/checks, inputs, results, uncovered boundaries,
and docs/runbook impact. Checked tasks are not verification evidence.

## 6. Verification And Completion

Verify in order:

1. local/minimal
2. shortest relevant chain
3. formal chain only when the selected band requires it

Do not declare completion until the relevant leaf standard was loaded, required
evidence exists, and doc/runbook impact was considered.

For an accepted change with delta specs, sync the specs to `openspec/specs/` before
archive. Archiving without sync is allowed only for a change explicitly marked
`Rejected` or `Abandoned` in `verification.md`.

Require a human gate when intent is ambiguous, subjective product acceptance is
needed, user-owned inputs are required, or the action changes governed/production
state. Git commit and push remain explicit user-authorized operations.

Do not invent secrets, parameters, datasets, or user decisions. Do not turn helper
artifacts into a shadow standard.

@RTK.md
