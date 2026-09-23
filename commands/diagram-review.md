---
description: Review an existing diagram against source, its type contract, and rendered quality
argument-hint: [path to diagram/spec]
allowed-tools: Read, Grep, Glob, Bash, Task
---

Review: **$ARGUMENTS**

Load the core workflow, the diagram's type profile, and its evidence/spec. Render with
`${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/render_any.sh` when possible
(or `validate_mermaid.sh` for Markdown Mermaid). Then run the diagram-reviewer
procedure against source and the rendered output.

Report Blocking / Should fix / Optional plus verification counts, selected profile,
renderer, and visual-review status. Do not edit unless asked.

If no evidence exists, state that truth verification is limited; never silently treat
the picture as source-backed.
