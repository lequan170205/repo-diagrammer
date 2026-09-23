---
name: diagram-doctor
description: Diagnose Repo Diagrammer tooling for the current repository, including Mermaid rendering, headless browser availability, search tools, and language-specific static-analysis extractors.
---

# Diagram Doctor

Resolve paths relative to this skill directory.

1. Run `../repo-diagram/scripts/check_deps.sh`.
2. Detect the languages actually present in the current repository.
3. Recommend only extraction tools relevant to those languages.
4. Clearly distinguish a missing Mermaid renderer from a missing headless browser.
5. Until rendering works, require delivered diagrams to be marked unvalidated.
6. Do not install dependencies unless the user explicitly asks.
