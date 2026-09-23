---
description: Generate a coherent set of diagrams for onboarding or an architecture review
argument-hint: [scope, e.g. "whole repo, for new devs" or "the payments module"]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

Use the `repo-diagram` skill to produce a **set** of diagrams for: **$ARGUMENTS**

One diagram cannot onboard anyone. Produce an ordered sequence, each answering one
question, with a paragraph of prose between them that carries the reader forward:

1. **C4 Context** — what this system is, who uses it, what it talks to. No technology.
2. **C4 Container** — what we deploy and how the pieces communicate. Protocol on
   every arrow.
3. **One sequence diagram** of the single most important user journey, happy path.
4. **ER diagram** of the core entities — only if the system is data-heavy.
5. **C4 Component** for the one module a new joiner will touch first.

Run `repo_map.sh` once, then launch `repo-scout` subagents in parallel — one per
subsystem you identified — so the exploration does not serialise. Build all specs
before rendering anything, so the diagrams are consistent with each other: the same
component must have the same name and the same boundary in every diagram.

Validate every diagram, run `diagram-reviewer` over the set, and deliver to
`docs/diagrams/` with an `README.md` index that lists them in reading order.
