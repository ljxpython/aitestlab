## Why

The repository Harness already classifies work as B1/B2/B3, but it lacks an
installed, portable lifecycle for changes that need durable requirements and review.
Adopting official OpenSpec support closes that gap without forcing every small change
to produce planning files.

## What Changes

- Initialize OpenSpec with its official Codex integration, `core` profile, and
  `spec-driven` schema.
- Define one Harness execution loop for every band while varying artifact persistence
  and verification depth by risk.
- Allow B2 to use OpenSpec when behavior, acceptance criteria, multi-session work, or
  handoff needs durable alignment; require OpenSpec for B3.
- Version only OpenSpec's generated Codex skills while keeping machine-local Codex
  state ignored.
- Document Ponytail and Caveman as optional implementation and communication controls,
  not as Harness or OpenSpec lifecycle components.
- Add an explicitly invoked `route-project-change` Skill as a thin Harness intake
  router that delegates persisted B2/B3 work to official OpenSpec Skills.
- Require a persisted B3 pre-apply owner decision and executable verification evidence.
- Require accepted delta specs to sync before archive, while allowing unsynced archive
  only for explicitly rejected or abandoned changes.
- Enforce one active planning source and cross-platform local-path checks in CI.
- Retire `.harness/plans/` as an active change host and prohibit duplicate plans.
- Non-goals: backfilling specs for existing code, creating a custom schema, implicitly
  invoking the router, or requiring OpenSpec changes for B1 work.

## Capabilities

### New Capabilities

- `ai-change-governance`: Route AI-assisted changes through the repository Harness
  and persist spec-driven artifacts only when the selected band requires them.

### Modified Capabilities

None. No existing OpenSpec capability specs are present.

## Impact

- Owning locus: repository-level AI execution governance.
- Affected chain: root routing, repository standard, human guide, helper lifecycle,
  OpenSpec configuration, and generated Codex skills.
- Execution band: B3 Governed because the repository execution policy changes.
- Standards loaded: `AGENTS.md` and
  `docs/standards/01-ai-execution-system.md`.
- Compatibility: application runtime behavior and public APIs are unchanged.
- Rollback: remove the OpenSpec integration files and restore the previous Harness
  documentation policy; no data or service migration is required.
