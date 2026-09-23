---
name: diagram-review
description: Review an existing repository diagram against the source code, checking evidence, arrow semantics, async boundaries, abstraction, readability, and render validity. Use when the user asks to audit, verify, or review a diagram.
---

# Diagram Review

Resolve paths relative to this skill directory.

1. Read `../repo-diagram/SKILL.md` and use its evidence and validation rules.
2. Read the diagram and its evidence table/spec if present.
3. Validate Mermaid with `../repo-diagram/scripts/validate_mermaid.sh` when a local renderer is available.
4. Apply the review procedure from `../../agents/diagram-reviewer.md`.
5. If isolated subagent tooling is available, run the review in an isolated context. Otherwise perform the same review inline.
6. Report findings as Blocking / Should fix / Optional. Do not edit the diagram unless the user asked for fixes.
