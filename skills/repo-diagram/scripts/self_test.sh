#!/usr/bin/env bash
# Cheap repository self-test for plugin structure and script syntax.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
core="$root/skills/repo-diagram"

required=(
  "$core/SKILL.md"
  "$core/assets/spec.template.yaml"
  "$core/references/semantic-ir.md"
  "$core/references/renderer-strategy.md"
  "$core/references/profiles/architecture.md"
  "$core/references/profiles/sequence.md"
  "$core/references/profiles/class.md"
  "$core/references/profiles/er.md"
  "$core/references/profiles/state.md"
  "$core/references/profiles/dataflow.md"
  "$core/references/profiles/deployment.md"
  "$core/references/profiles/callgraph.md"
  "$core/references/profiles/usecase.md"
  "$core/references/profiles/flowchart.md"
)

for f in "${required[@]}"; do
  [ -s "$f" ] || { echo "missing required file: $f" >&2; exit 1; }
done

for f in "$core"/scripts/*.sh; do bash -n "$f"; done
python3 -m py_compile "$core/scripts/visual_lint_svg.py"

grep -q "No evidence, no element" "$core/SKILL.md"
grep -q "semantic-ir.md" "$core/SKILL.md"
grep -q "renderer-strategy.md" "$core/SKILL.md"
grep -q "visual review" "$core/references/diagram-reviewer-procedure.md"

echo "repo-diagrammer self-test: PASS"
