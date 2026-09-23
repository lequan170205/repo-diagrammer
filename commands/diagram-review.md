---
description: Review an existing diagram against the code it claims to describe
argument-hint: [path to diagram file, or paste the mermaid]
allowed-tools: Read, Grep, Glob, Bash, Task
---

Review this diagram against the codebase: **$ARGUMENTS**

Launch the `diagram-reviewer` subagent with the diagram and the repo root. While it
works, run `${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/validate_mermaid.sh` on the file yourself so a syntax
failure is caught immediately.

Report its findings grouped as Blocking / Should fix / Optional, then offer to apply
the fixes. Do not edit the diagram without being asked.

If the diagram has no evidence table, say so first — an unverifiable diagram can only
be reviewed for semantics and readability, not for truth, and that limitation should
be stated rather than glossed over.
