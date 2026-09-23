---
description: Check renderer versions/capabilities and repo-specific extraction tools
allowed-tools: Bash, Read
---

Run `bash ${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/check_deps.sh`.
Report Mermaid version/browser, native use-case/swimlane eligibility, PlantUML,
Graphviz, and preferred/fallback renderer coverage from `renderer-strategy.md`.
Recommend only extraction tools relevant to the current repo. Do not install without
explicit permission.
