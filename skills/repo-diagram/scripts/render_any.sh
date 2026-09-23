#!/usr/bin/env bash
# Render Mermaid, PlantUML or Graphviz source and run lightweight SVG sanity checks.
set -euo pipefail
if [ "$#" -lt 1 ]; then echo "usage: $0 <diagram.{mmd,puml,dot,md}> [output.svg]" >&2; exit 2; fi
input="$1"; output="${2:-${input%.*}.svg}"; ext="${input##*.}"
have(){ command -v "$1" >/dev/null 2>&1; }
case "$ext" in
  mmd)
    if have mmdc; then mmdc -i "$input" -o "$output"
    elif have npx; then npx --yes @mermaid-js/mermaid-cli -i "$input" -o "$output"
    else echo "renderer unavailable: Mermaid CLI" >&2; exit 2; fi ;;
  puml|plantuml)
    if ! have plantuml; then echo "renderer unavailable: PlantUML" >&2; exit 2; fi
    plantuml -tsvg "$input"
    generated="${input%.*}.svg"
    if [ "$generated" != "$output" ]; then
      mkdir -p "$(dirname "$output")"
      mv "$generated" "$output"
    fi ;;
  dot)
    if ! have dot; then echo "renderer unavailable: Graphviz" >&2; exit 2; fi
    dot -Tsvg "$input" -o "$output" ;;
  md)
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    bash "$script_dir/validate_mermaid.sh" "$input"; exit 0 ;;
  *) echo "unsupported extension: .$ext" >&2; exit 2 ;;
esac
[ -s "$output" ] || { echo "render failed: $output" >&2; exit 1; }
echo "rendered: $output"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$script_dir/visual_lint_svg.py" ] && have python3; then python3 "$script_dir/visual_lint_svg.py" "$output" || true; fi
