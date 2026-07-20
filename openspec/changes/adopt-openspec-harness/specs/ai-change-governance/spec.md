## ADDED Requirements

### Requirement: Shared execution loop

Every non-trivial AI-assisted change SHALL complete analysis, boundary selection,
planning, implementation, verification, any required human gate, and a final summary.
The selected execution band SHALL alter artifact persistence and verification depth,
not remove stages from the loop.

#### Scenario: Local change remains lightweight

- **WHEN** a change is contained in one locus and affects no governed surface
- **THEN** the agent completes the shared loop as B1 without creating an OpenSpec change

### Requirement: Band-routed artifact persistence

The repository SHALL use no persisted plan by default for B1, SHALL use an OpenSpec
change for B2 only when durable behavior or collaboration alignment is needed, and
MUST use an OpenSpec change for B3 before implementation.

#### Scenario: B2 requires durable acceptance criteria

- **WHEN** a B2 change spans sessions or its behavior and acceptance criteria require review
- **THEN** the agent persists the change under `openspec/changes/`

#### Scenario: Governed risk is discovered during implementation

- **WHEN** a B1 or B2 implementation reveals a governed contract, policy, ownership, migration, or release impact
- **THEN** the agent upgrades the work to B3 and creates or updates an OpenSpec change before continuing

### Requirement: Explicit project-change routing

The repository SHALL provide an explicitly invoked `route-project-change` Skill that
reports locus, affected chain, standards loaded, band, and verification plan before
routing work. The Skill MUST remain subordinate to root and leaf standards and MUST
delegate persisted change lifecycle actions to official OpenSpec Skills.

#### Scenario: User explicitly invokes the router

- **WHEN** the user invokes `$route-project-change` with a task description
- **THEN** the Skill prints the routing decision and selects direct, short-plan, or OpenSpec execution without implicitly creating an OpenSpec change for B1

### Requirement: Single active change source

A persisted change MUST have one active source. The same change MUST NOT be maintained
in both `openspec/changes/` and `.harness/plans/`.

#### Scenario: OpenSpec change exists

- **WHEN** a B2 or B3 change is created under `openspec/changes/`
- **THEN** `.harness/plans/` contains no duplicate active PRD, test spec, or task list for that change

### Requirement: Authority and verification remain in Harness

OpenSpec artifacts MUST NOT override root or leaf standards. Completion MUST follow
local verification first, shortest relevant chain verification second, and formal
evidence only when governed risk requires it.

#### Scenario: Tasks are checked but evidence is incomplete

- **WHEN** every OpenSpec task is checked but required Harness verification has not completed
- **THEN** the change remains incomplete and MUST NOT be archived as accepted

### Requirement: B3 pre-apply owner gate

A B3 change MUST stop after proposal, specs, design, and tasks are ready and MUST record
owner review approval before apply. A waiver MUST be explicitly granted by the owner,
recorded with its reason and scope before apply, and MUST NOT be self-issued by an agent.

#### Scenario: B3 artifacts exist without owner review

- **WHEN** proposal, specs, design, and tasks are complete but `verification.md` records the pre-apply review as Pending
- **THEN** implementation MUST NOT begin

### Requirement: Persisted verification evidence

Every persisted change with `tasks.md` MUST maintain `verification.md` containing its
review decision, commands or checks, inputs, results, uncovered boundaries, residual
risk, documentation impact, and final disposition.

#### Scenario: Tasks are complete without evidence

- **WHEN** tasks are checked but `verification.md` is missing or incomplete
- **THEN** the change MUST remain unaccepted and CI MUST reject an invalid archived state

### Requirement: Accepted changes sync before archive

An accepted change with delta specs MUST sync those requirements into
`openspec/specs/` before archive. Archive without sync MUST be limited to changes whose
disposition is explicitly Rejected or Abandoned.

#### Scenario: Accepted delta spec is not synchronized

- **WHEN** an archived accepted change contains an added or modified requirement that is absent from its current capability spec
- **THEN** CI MUST fail

### Requirement: Human-controlled operations

The workflow MUST require human confirmation for unresolved intent, subjective product
acceptance, user-owned inputs, and governed or production-state actions. Git commit and
push operations MUST require explicit user authorization.

#### Scenario: Implementation is verified but commit was not requested

- **WHEN** implementation and verification finish without an explicit commit request
- **THEN** the agent summarizes the result and leaves the worktree uncommitted

### Requirement: Auxiliary Skills do not replace governance

Ponytail and Caveman MAY assist implementation scope and communication style, but they
MUST NOT replace Harness routing, OpenSpec artifacts, verification, or human gates.

#### Scenario: Auxiliary Skill does not trigger

- **WHEN** an optional Skill is installed but not automatically selected for a task
- **THEN** the task still follows all mandatory repository standards and verification gates
