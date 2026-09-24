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
  "$core/references/visual-compiler.md"
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
  "$core/references/standards/coverage-matrix.md"
)

for f in "${required[@]}"; do
  [ -s "$f" ] || { echo "missing required file: $f" >&2; exit 1; }
done

for f in "$core"/scripts/*.sh; do bash -n "$f"; done
python3 -m py_compile "$core/scripts/visual_lint_svg.py" "$core/scripts/visual_analyze_svg.py" "$core/scripts/render_architecture_svg.py" "$core/scripts/validate_spec.py"

if python3 -c 'import yaml' >/dev/null 2>&1; then
  expect_pass() {
    local fixture="$1"
    echo "EXPECT PASS: $(basename "$fixture")"
    if ! python3 "$core/scripts/validate_spec.py" "$fixture"; then
      echo "expected valid fixture failed: $fixture" >&2
      exit 1
    fi
  }

  expect_fail() {
    local fixture="$1"
    echo "EXPECT FAIL: $(basename "$fixture")"
    if python3 "$core/scripts/validate_spec.py" "$fixture"; then
      echo "expected invalid fixture passed: $fixture" >&2
      exit 1
    fi
  }

  expect_pass "$core/tests/fixtures/valid-sequence.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-usecase.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-c4.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-sequence.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-class.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-chen.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-strict-iso42010.spec.yaml"
  expect_pass "$core/tests/fixtures/valid-polished-sidecars.spec.yaml"

  expect_fail "$core/tests/fixtures/invalid-missing-evidence.spec.yaml"
  expect_fail "$core/tests/fixtures/invalid-strict-usecase.spec.yaml"
  expect_fail "$core/tests/fixtures/invalid-strict-er.spec.yaml"
  expect_fail "$core/tests/fixtures/invalid-strict-iso42010.spec.yaml"
  expect_fail "$core/tests/fixtures/invalid-layout-reference.spec.yaml"
fi

if python3 -c 'import yaml' >/dev/null 2>&1; then
  tmp_visual="$(mktemp -d)"
  python3 "$core/scripts/render_architecture_svg.py"     "$core/tests/fixtures/valid-polished-sidecars.spec.yaml"     "$tmp_visual/architecture.svg" >/dev/null
  python3 "$core/scripts/visual_analyze_svg.py" "$tmp_visual/architecture.svg" --strict --max-crossings 0 >/dev/null
  grep -q 'data-node-id="external" data-layout-zone="right"' "$tmp_visual/architecture.svg"

  cat > "$tmp_visual/bad.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 180">
  <g data-node-id="a"><rect x="20" y="20" width="80" height="50"/></g>
  <g data-node-id="b"><rect x="110" y="65" width="80" height="50"/></g>
  <g data-node-id="c"><rect x="200" y="110" width="80" height="50"/></g>
  <g data-edge-id="e" data-source-id="a" data-target-id="c"><path d="M 60,45 L 240,135"/></g>
</svg>
SVG
  if python3 "$core/scripts/visual_analyze_svg.py" "$tmp_visual/bad.svg" --strict >/dev/null 2>&1; then
    echo "expected edge-through-node defect was not detected" >&2
    exit 1
  fi

  cat > "$tmp_visual/overlap.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
  <g data-edge-id="e1"><path d="M 20,80 L 280,80"/></g>
  <g data-edge-id="e2"><path d="M 60,80 L 240,80"/></g>
</svg>
SVG
  python3 "$core/scripts/visual_analyze_svg.py" "$tmp_visual/overlap.svg" --strict >"$tmp_visual/overlap.out" 2>&1 || true
  grep -q "EDGE_EDGE_OVERLAP" "$tmp_visual/overlap.out"

  cat > "$tmp_visual/label-cross.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
  <g data-edge-label-id="e1-label"><rect x="120" y="70" width="80" height="24"/></g>
  <g data-edge-id="e1"><path d="M 40,50 L 100,50"/></g>
  <g data-edge-id="e2"><path d="M 160,20 L 160,140"/></g>
</svg>
SVG
  python3 "$core/scripts/visual_analyze_svg.py" "$tmp_visual/label-cross.svg" --strict >"$tmp_visual/label-cross.out" 2>&1 || true
  grep -q "EDGE_LABEL_COLLISION" "$tmp_visual/label-cross.out"
  rm -rf "$tmp_visual"
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
grep -q "visual-compiler.md" "$core/SKILL.md"
grep -q "validate_spec.py" "$core/SKILL.md"
grep -q "visual review" "$core/references/diagram-reviewer-procedure.md"
grep -q "textbook-strict" "$core/SKILL.md"
grep -q "documented-subset" "$core/references/standards/README.md"

echo "repo-diagrammer self-test: PASS"
