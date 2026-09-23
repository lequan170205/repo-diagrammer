#!/usr/bin/env bash
# validate_on_write.sh — PostToolUse guard.
# When Claude writes a file containing Mermaid, render it. If a block fails to
# parse, exit 2 so the failure is fed back and Claude fixes it before moving on.
#
# Designed to be silent and harmless: no Mermaid, no renderer, or an environment
# problem all exit 0 rather than nagging.
set -uo pipefail

PAYLOAD=$(cat 2>/dev/null || true)

# Pull the file path out of the hook payload without requiring jq.
FILE=""
if command -v jq >/dev/null 2>&1; then
  FILE=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)
fi
if [ -z "$FILE" ]; then
  FILE=$(printf '%s' "$PAYLOAD" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0
case "$FILE" in
  *.md|*.markdown|*.mmd|*.mermaid) ;;
  *) exit 0 ;;
esac
grep -q '```[[:space:]]*mermaid' "$FILE" 2>/dev/null || case "$FILE" in *.mmd|*.mermaid) ;; *) exit 0 ;; esac

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../skills/repo-diagram/scripts" 2>/dev/null && pwd)/validate_mermaid.sh"
[ -f "$SCRIPT" ] || exit 0

OUT=$(bash "$SCRIPT" "$FILE" 2>&1)
CODE=$?

# 2 = renderer or headless browser unavailable. Not the diagram's fault; stay quiet.
[ "$CODE" -eq 2 ] && exit 0
[ "$CODE" -eq 0 ] && exit 0

{
  echo "Mermaid validation failed for $FILE — fix the diagram before continuing."
  echo "$OUT"
} >&2
exit 2
