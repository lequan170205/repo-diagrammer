---
description: Read the codebase and draw an accurate, evidence-backed diagram of a feature
argument-hint: [diagram type and/or feature, e.g. "sequence cho luồng checkout"]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

Use the `repo-diagram` skill to draw: **$ARGUMENTS**

Follow its workflow in full — this is the whole point of the command, so do not
shortcut to writing Mermaid:

1. **Locate the feature.** Run `${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/feature_trace.sh` with 2–3 keyword
   variants. For whole-system scope, run `repo_map.sh` first. On a large repo, or when
   the diagram spans several subsystems, launch `repo-scout` subagents in parallel —
   one per subsystem — rather than exploring inline.
2. **Extract deterministically.** Run `${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/extract_structure.sh` in the
   mode the diagram type needs (classes / deps / routes / schema). Read code by hand
   only for what no tool can give you: runtime flow, event wiring, intent.
3. **Write the spec first.** Fill `assets/spec.template.yaml` with `path:line` or
   `tool:<command>` evidence for every node and edge. Mark async edges. No evidence →
   Gaps, not the canvas.
4. **Check type, level and budget** against `references/diagram-types.md`. For a
   generic high-level/backend/system architecture request, load
   `references/high-level-architecture-style.md` and set the spec presentation
   profile to `polished-overview`.
5. **Render** per `references/notation.md`, declaring nodes explicitly in reading
   order per `references/layout-quality.md`. Plan rows before Mermaid; keep exact
   identifiers visible; presentation groups may not receive edges.
6. **Validate and visually review** with
   `${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/validate_mermaid.sh`. Inspect
   the rendered result at 100%, iterate until the visual acceptance gate passes, then
   launch the `diagram-reviewer` subagent. Fix every Blocking finding, including
   `VISUAL`, before delivering.
7. **Deliver** to `docs/diagrams/<slug>.md` with the diagram, a How-to-read section,
   the Evidence table, and Gaps. Save the spec as `docs/diagrams/<slug>.spec.yaml`.

If the request does not say which diagram type, pick the one that answers the
question and say in one line why. If scope or audience is genuinely ambiguous, ask
one question — no more — before starting.
