# Verification Evidence

- Status: Complete
- Disposition: Pending acceptance
- Pre-apply review: Pending
- Execution band: B3 Governed
- Owning locus: repository-level AI execution governance

## Pre-apply Review Gate

This bootstrap change was implemented while OpenSpec itself was being installed, before
the repository had a persisted pre-apply gate. Do not rewrite that history as approved.
Owner acceptance must explicitly choose whether to grant a recorded bootstrap waiver;
without that decision, this change cannot be accepted or archived.

## Verification Plan

- Local: validate the custom router Skill, OpenSpec artifacts, documentation checker,
  and Python syntax.
- Shortest chain: verify generated Codex Skills, project configuration, standards, and
  CI rules agree on routing and completion gates.
- Formal/human: owner reviews the B3 artifacts, bootstrap waiver, evidence, and archive
  disposition.

## Evidence Log

| Proof level | Command / check | Input | Result | Evidence note |
| --- | --- | --- | --- | --- |
| Local | `quick_validate.py .codex/skills/route-project-change` | project Skill | Pass | Reported `Skill is valid!` |
| Local | `openspec validate --all --strict --no-interactive` | active OpenSpec changes | Pass | Reported 1 passed and 0 failed |
| Local | `python3 scripts/check_docs.py` | tracked and untracked Markdown/change state | Pass | Reported `Documentation checks passed.` |
| Local | targeted temporary-directory negative checks | plan, evidence, archive sync, and local-path violations | Pass | All eight rejection/allowance cases passed |
| Local | `python3 -m py_compile scripts/check_docs.py` | documentation checker | Pass | Exited zero |
| Local | `git diff --check` | worktree diff | Pass | Exited zero |
| Shortest chain | manual authority and generated-Skill review | root rules, project config, Skills | Pass | Repo gates consistently override permissive generated apply/archive behavior |

## Inputs And Outputs

- Inputs exercised: repository standards, project OpenSpec config, generated official
  Skills, custom router Skill, active/archived planning paths, and path examples for
  macOS, Linux, and Windows.
- Outputs expected: deterministic routing rules, persisted evidence, one active change
  source, strict OpenSpec validation, and CI failures for prohibited states.
- Failure behavior checked: active Harness plans, missing evidence, accepted unsynced
  archives, and macOS/Linux/Windows local paths were rejected; explicit path
  placeholders were allowed.

## Residual Risk

- A fresh Codex process still needs to discover and invoke `$route-project-change`
  after restart.
- Application runtime behavior is outside scope because this change only affects the
  repository development Harness.
- Owner acceptance and the bootstrap waiver decision remain intentionally open.

## Docs And Archive Decision

- Docs/runbooks updated: Yes, current Harness and human usage documents are updated.
- Spec sync: Pending owner acceptance; do not sync or archive yet.
