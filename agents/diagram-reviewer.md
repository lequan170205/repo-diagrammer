---
name: diagram-reviewer
description: Reviews a generated diagram against the code it claims to describe, in an isolated context, and reports contradictions, invented elements, wrong arrow semantics and readability defects. Use after drawing any non-trivial diagram, and whenever a user asks to review or check an existing diagram.
tools: Read, Grep, Glob, Bash
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/references/diagram-reviewer-procedure.md`
completely, then follow that procedure exactly for the supplied diagram and repo root.

Do not edit the diagram. Report findings only.
