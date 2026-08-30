---
name: deepagent-common-workflow
description: Use this skill for engineering tasks that require planning with write_todos, controlled file edits, and final verification.
---

# DeepAgent Common Workflow

## Overview

Use this workflow whenever the user asks for implementation or documentation work.

## Instructions

1. Create or update a todo plan with `write_todos`.
2. Use filesystem tools (`ls`, `glob`, `grep`, `read_file`, `edit_file`, `write_file`) to gather and change evidence.
3. If a focused research pass is needed, delegate with `task`.
4. Re-read the changed files and verify consistency.
5. Return a concise final update with completed todo items and remaining risks.
