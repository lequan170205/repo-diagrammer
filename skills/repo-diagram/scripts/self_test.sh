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
  "$core/references/standards/README.md"
  "$core/references/standards/uml-2.5.1.md"
  "$core/references/standards/architecture.md"
  "$core/references/standards/erd.md"
)

for f in "${required[@]}"; do
  [ -s "$f" ] || { echo "missing required file: $f" >&2; exit 1; }
done

for f in "$core"/scripts/*.sh; do bash -n "$f"; done
python3 -m py_compile "$core/scripts/visual_lint_svg.py" "$core/scripts/validate_spec.py"

if python3 -c 'import yaml' >/dev/null 2>&1; then
  python3 "$core/scripts/validate_spec.py" "$core/tests/fixtures/valid-sequence.spec.yaml" >/dev/null
  python3 "$core/scripts/validate_spec.py" "$core/tests/fixtures/valid-strict-usecase.spec.yaml" >/dev/null
  python3 "$core/scripts/validate_spec.py" "$core/tests/fixtures/valid-strict-c4.spec.yaml" >/dev/null
  for bad in     "$core/tests/fixtures/invalid-missing-evidence.spec.yaml"     "$core/tests/fixtures/invalid-strict-usecase.spec.yaml"     "$core/tests/fixtures/invalid-strict-er.spec.yaml"; do
    if python3 "$core/scripts/validate_spec.py" "$bad" >/dev/null 2>&1; then
      echo "invalid spec fixture unexpectedly passed: $bad" >&2
      exit 1
    fi
  done
fi

if command -v dot >/dev/null 2>&1; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  printf 'digraph G { A -> B; }\n' > "$tmp/smoke.dot"
  bash "$core/scripts/render_any.sh" "$tmp/smoke.dot" "$tmp/smoke.svg" >/dev/null
  [ -s "$tmp/smoke.svg" ]
fi

grep -q "No evidence, no element" "$core/SKILL.md"
grep -q "semantic-ir.md" "$core/SKILL.md"
grep -q "renderer-strategy.md" "$core/SKILL.md"
grep -q "validate_spec.py" "$core/SKILL.md"
grep -q "visual review" "$core/references/diagram-reviewer-procedure.md"
grep -q "textbook-strict" "$core/SKILL.md"
grep -q "documented-subset" "$core/references/standards/README.md"

echo "repo-diagrammer self-test: PASS"
