# Generic Harness Helper Host

> Helper-only surface. This directory is not repo canon.

Canonical rules:

- `AGENTS.md`: thin routing
- `docs/standards/01-ai-execution-system.md`: current execution standard
- app/service leaf standards: local authority

Buckets:

- `templates/`: lightweight B1/B2 helpers
- `context/`: optional historical context snapshots
- `plans/`: historical or explicitly archived plans; not a default active-change host
- `reports/`: repo-level or cross-change evidence
- `logs/`, `state/`: optional runtime acceleration only

Persisted B2 changes and all B3 changes live in `openspec/changes/`. Do not duplicate
them under `.harness/plans/`.

Rules:

- protocol-only B1/B2 work must remain usable without an accelerator
- helpers cannot define domain policy or override leaf standards
- historical `.omx/` content is transition/history only
