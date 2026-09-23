---
name: diagram
description: Force the full evidence-backed repo-diagram workflow for one requested architecture, sequence, class, ER, state, dataflow, deployment, call graph, or use case diagram. Use when the user explicitly asks to run the diagram workflow rather than only discuss a diagram.
---

# Diagram

Resolve paths relative to this skill directory.

1. Read `../repo-diagram/SKILL.md` completely.
2. Apply that workflow to the user's current diagram request.
3. Do not shortcut directly to Mermaid. Locate the feature, extract deterministically where possible, write the evidence spec first, render, validate, review, then deliver.
4. If isolated subagent tooling is unavailable, perform the bounded scout/reviewer passes inline rather than skipping them.
