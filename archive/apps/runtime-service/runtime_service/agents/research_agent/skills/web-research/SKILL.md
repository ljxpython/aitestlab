---
name: web-research
description: Structured web research workflow with planning, delegated subtopic investigation, and file-based synthesis.
---

# Web Research

## Trigger

Use this skill when the user asks for web research, latest information lookup, option comparison, or a report with citations.

## Required Workflow

1. Create a research folder and write `research_plan.md` first.
2. Split the topic into 2-5 non-overlapping subtopics.
3. Delegate one focused task per subtopic via `task`.
4. Require each delegated task to write findings into `findings_<subtopic>.md`.
5. Read all findings files before writing the final answer.
6. Synthesize direct conclusions, include source URLs, and call out evidence gaps.

## Guardrails

- Keep each subtopic narrow and non-overlapping.
- Avoid over-researching simple questions.
- Do not finalize without reading all generated findings files.
- Prefer concise and evidence-based output.
