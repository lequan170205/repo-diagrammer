---
name: diagram-set
description: Generate a coherent evidence-backed set of repository diagrams for onboarding or architecture review, typically C4 Context, C4 Container, a primary sequence, optional ER, and one C4 Component diagram.
---

# Diagram Set

Resolve paths relative to this skill directory.

1. Read `../repo-diagram/SKILL.md` completely.
2. Produce an ordered set where each diagram answers one question:
   - C4 Context
   - C4 Container
   - one primary happy-path sequence
   - ER only when the system is data-heavy
   - one C4 Component diagram for the most relevant module
3. Run repository mapping once, then reuse the evidence inventory across the set.
4. If isolated subagents are available, split independent subsystem scouting across them. Otherwise scout bounded subsystems inline.
5. Build all specs before rendering so names and boundaries stay consistent.
6. Validate every Mermaid diagram and run the tech-lead review pass before delivery.
7. Deliver under `docs/diagrams/` with a README index in reading order.
