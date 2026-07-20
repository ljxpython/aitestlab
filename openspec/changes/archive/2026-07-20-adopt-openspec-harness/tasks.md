## 1. Install And Configure OpenSpec

- [x] 1.1 Install the official `@fission-ai/openspec` CLI and verify its version
- [x] 1.2 Initialize the repository with the official Codex `core` profile and `spec-driven` schema
- [x] 1.3 Add project context and artifact rules without forking the schema or generated skills
- [x] 1.4 Version generated OpenSpec skills while keeping machine-local Codex state ignored

## 2. Align Harness Documentation

- [x] 2.1 Define the shared Harness execution loop for B1, B2, and B3
- [x] 2.2 Define conditional B2 persistence and mandatory B3 OpenSpec usage
- [x] 2.3 Update the human guide with Codex Skill, CLI, verification, and human-gate usage
- [x] 2.4 Retire `.harness/plans/` as an active persisted-change host
- [x] 2.5 Document Ponytail and Caveman roles, triggers, and governance boundaries
- [x] 2.6 Explain intake fields in plain language with project-specific B1/B2/B3 examples
- [x] 2.7 Add an explicit-only `route-project-change` Skill and document its invocation
- [x] 2.8 Add persisted pre-apply review, verification evidence, and sync-before-archive rules
- [x] 2.9 Reject active `.harness/plans` and cross-platform local paths in CI
- [x] 2.10 Archive superseded Harness plans and create this change's verification record

## 3. Verify And Accept

- [x] 3.1 Run OpenSpec doctor, status, and strict validation
- [x] 3.2 Run repository documentation checks and whitespace validation
- [x] 3.3 Review generated files, ignored-file boundaries, and active change status
- [x] 3.4 Obtain owner acceptance or an explicit bootstrap waiver before archiving the change
