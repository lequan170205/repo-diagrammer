---
description: Generate a coherent diagram set from one shared evidence model
argument-hint: [scope/audience]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

Use the repo-diagram workflow for: **$ARGUMENTS**

Build `docs/diagrams/model.spec.yaml` once. Derive useful views from stable model IDs.
Each view gets its own type profile and renderer. Validate visually/source-wise, then
run a cross-view consistency pass. Deliver an ordered README.

Do not generate every supported diagram type unless each answers a real question.
