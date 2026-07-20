---
name: route-project-change
description: Route a change in ai-agent-platform through its repository Harness by resolving locus, affected chain, loaded standards, B1/B2/B3 band, verification plan, and whether to use OpenSpec. Use only when the user explicitly invokes $route-project-change or explicitly asks to run this project-change router; do not auto-trigger for ordinary coding requests.
---

# Route Project Change

Use this Skill as the explicit intake and routing entry. Keep repository standards as
the authority; this Skill coordinates them and does not redefine them.

## Workflow

1. Resolve the repository root containing both `AGENTS.md` and `openspec/config.yaml`.
   If the current directory is outside that repository, ask for the project path.
2. Read `AGENTS.md` and `docs/standards/01-ai-execution-system.md`.
3. Inspect only the code and documents needed to identify the owning app/service and
   the shortest real call, data, or contract chain.
4. Read the narrowest applicable leaf standard named by the root resolver. Do not load
   the whole documentation tree.
5. Classify the change using boundary and risk, not code size or estimated duration.
6. Define the smallest verification evidence before implementation.
7. Print the routing decision using the required output format below.
8. Follow the selected route only when the user's request includes implementation;
   otherwise stop after routing and wait for direction.

## Routes

- **B1 Local**: Do not create an OpenSpec change. Implement directly when requested,
  then run local/minimal verification and summarize uncovered boundaries.
- **B2 Chain without durable alignment**: Keep a short plan in the conversation.
  Implement when requested, then verify local behavior and the shortest affected chain.
- **B2 Chain with durable alignment**: Use `$openspec-propose` when behavior or
  acceptance criteria need review, or work spans sessions, collaborators, or handoff.
  After tasks are generated, create `verification.md` with the planned evidence and
  review decision. Review artifacts before using `$openspec-apply-change`.
- **B3 Governed**: Use `$openspec-propose` before implementation. Stop after proposal,
  specs, design, and tasks are ready for owner review. Create `verification.md` and
  record `Approved` before apply. Use `Waived` only with explicit owner authorization
  and a recorded reason. Then use `$openspec-apply-change` and complete Harness evidence.
- **Unclear problem**: Use `$openspec-explore` for investigation, then rerun routing.

Never maintain the same change in both `openspec/changes/` and `.harness/plans/`.
Never treat checked OpenSpec tasks as verification evidence. Never commit, push,
publish, migrate, or perform another governed action without the required approval.
For an accepted change, use `$openspec-sync-specs` before `$openspec-archive-change`
when delta specs exist. Skip sync only for a recorded `Rejected` or `Abandoned` change.

## Required Output

```text
Locus: <owning app/service/repo surface>
Affected chain: <shortest real chain>
Standards loaded:
  - <exact relative path>
Band: <B1 Local | B2 Chain | B3 Governed>
Verification plan:
  - local: <evidence>
  - shortest chain: <evidence or not required>
  - formal/human: <evidence or not required>
Artifact decision: <conversation only | short plan | OpenSpec change>
Reason: <concise boundary/risk reason>
Next action: <direct implementation | OpenSpec Skill | wait for review/input>
```

List only standards actually read. State uncertainty instead of inventing owner,
contracts, secrets, datasets, or acceptance decisions.
