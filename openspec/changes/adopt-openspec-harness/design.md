## Context

The repository already has root routing, leaf authority, B1/B2/B3 execution bands,
and progressive verification. It also has historical `.harness/plans/` artifacts but
no installed spec lifecycle. OpenSpec provides delta specs and generated Codex skills,
so the integration should fill only the persistence gap.

## Goals / Non-Goals

**Goals:**

- Make durable B2 and all B3 changes reviewable, executable, and archivable.
- Preserve lightweight B1 work and the existing locus/verification rules.
- Keep the integration portable through versioned repository files.

**Non-Goals:**

- Backfill specifications for unchanged code.
- Replace root or leaf standards with OpenSpec artifacts.
- Create a custom schema, an implicitly invoked router, or a second plan hierarchy.

## Decisions

1. **Harness remains the control plane; OpenSpec is the persisted change engine.**
   OpenSpec does not know this repository's service ownership or required verification
   depth. Treating it as the whole Harness would lose those constraints. Keeping it as
   the artifact lifecycle also avoids duplicating proposal/spec/task machinery.
2. **Use the official `core` profile and `spec-driven` schema.** The generated
   `explore`, `propose`, `update`, `apply`, `sync`, and `archive` skills cover the
   current need. A custom schema has no repeated evidence behind it.
3. **Keep B1 outside the change lifecycle and make B2 conditional.** Requiring four
   artifacts for every local fix would create more maintenance than evidence. B2 enters
   OpenSpec when durable behavior, review, or handoff makes persistence valuable.
4. **Version generated OpenSpec skills, not machine-local Codex state.** Selective
   `.gitignore` rules keep `.codex/hooks.json` local while allowing official
   `.codex/skills/openspec-*` files to travel with the repository.
5. **Keep verification in Harness.** The core OpenSpec profile has no separate verify
   skill, and task completion alone is not evidence across this monorepo's boundaries.
6. **Keep Ponytail and Caveman auxiliary.** Ponytail constrains implementation scope;
   Caveman compresses communication. Neither owns routing, artifacts, verification, or
   human gates, and automatic Skill matching is not a deterministic policy mechanism.
7. **Provide one explicit thin router Skill.** `route-project-change` reads existing
   authority, emits the five intake fields, and delegates durable B2/B3 work to official
   OpenSpec Skills. `allow_implicit_invocation: false` keeps normal coding requests on
   the automatic `AGENTS.md` path and avoids duplicate orchestration.
8. **Use `verification.md` as the durable closure record.** The default OpenSpec schema
   has no verification artifact and task checkboxes cannot preserve commands, inputs,
   results, gaps, review decisions, or disposition. A repo convention plus CI provides
   this evidence without forking the schema.
9. **Make accepted sync-before-archive enforceable.** Archived accepted delta specs
   must have corresponding current capability requirements under `openspec/specs/`.
   Rejected or abandoned work can archive without sync when its disposition is explicit.

Rejected alternatives:

- OpenSpec for every B1/B2 task: rejected because it creates routine document churn.
- An implicitly invoked router Skill: rejected because `AGENTS.md` already loads
  automatically and Skill matching is not a reliable governance gate.
- A forked schema with review/test artifacts: rejected until multiple real changes
  demonstrate that project config rules are insufficient.

## Risks / Trade-offs

- [B2 classification remains judgment-based] -> Keep concrete persistence triggers in
  the current standard and review the first few changes.
- [Generated skills can drift after CLI upgrades] -> Run `openspec update` after
  upgrading and review the generated diff.
- [OpenSpec and `.harness` may be duplicated by habit] -> Treat `.harness/plans/` as
  history-only and enforce one active source during review.
- [The core profile lacks a verify command] -> Retain Harness verification and run
  `openspec validate --all --strict --no-interactive` as structural validation only.
- [Optional Skills may not auto-trigger] -> Document explicit invocation and keep all
  mandatory rules in `AGENTS.md`, current standards, tests, and CI.
- [Official archive allows skipping sync] -> Root policy and CI reject accepted archives
  whose delta requirements are absent from current capability specs.
- [A bootstrap change cannot have retrospective pre-apply approval] -> Record the gap
  as Pending and require an explicit owner waiver before accepted archive.

## Migration Plan

1. Install OpenSpec and initialize the repository for Codex.
2. Add concise project context and artifact rules in `openspec/config.yaml`.
3. Update the current standard, human guide, and helper lifecycle.
4. Validate this first real B3 change and leave it active for owner review.
5. Archive it only after owner acceptance; let archived delta specs establish the first
   current capability spec.

Rollback requires removing the OpenSpec integration and restoring the previous routing
text. No application data, API, or runtime migration is involved.

## Open Questions

- After two or three real B2/B3 changes, does the default schema repeatedly omit any
  evidence that cannot be expressed through project rules and Harness verification?
