#!/usr/bin/env bash
# validate_on_write.sh — PostToolUse guard for Claude Code and Codex.
# Detect Markdown/Mermaid files changed by Write/Edit or Codex apply_patch, then
# render them. Environment/renderer problems stay non-blocking; syntax failures
# are returned to the host so the model can fix them before moving on.
set -uo pipefail

PAYLOAD=$(cat 2>/dev/null || true)
FILES=""

# Prefer Python's stdlib JSON parser because Codex apply_patch carries the patch
# text in tool_input.command and one patch may touch several files.
if command -v python3 >/dev/null 2>&1; then
  FILES=$(printf '%s' "$PAYLOAD" | python3 -c '
import json, re, sys
try:
    payload = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
tool_input = payload.get("tool_input") or {}
seen = set()
for key in ("file_path", "path"):
    value = tool_input.get(key)
    if isinstance(value, str) and value.strip() and value not in seen:
        seen.add(value)
        print(value)
command = tool_input.get("command")
if isinstance(command, str):
    for line in command.splitlines():
        m = re.match(r"^\*\*\* (?:Update|Add) File: (.+)$", line)
        if m:
            value = m.group(1).strip()
            if value and value not in seen:
                seen.add(value)
                print(value)
' 2>/dev/null)
fi

# Lightweight fallback for Claude-style Write/Edit payloads.
if [ -z "$FILES" ] && command -v jq >/dev/null 2>&1; then
  FILES=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null)
fi
if [ -z "$FILES" ]; then
  FILES=$(printf '%s' "$PAYLOAD" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
fi

[ -n "$FILES" ] || exit 0

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../skills/repo-diagram/scripts" 2>/dev/null && pwd)/validate_mermaid.sh"
[ -f "$SCRIPT" ] || exit 0

FAIL=0
while IFS= read -r FILE; do
  [ -n "$FILE" ] || continue
  [ -f "$FILE" ] || continue

  case "$FILE" in
    *.md|*.markdown|*.mmd|*.mermaid) ;;
    *) continue ;;
  esac

  grep -q '```[[:space:]]*mermaid' "$FILE" 2>/dev/null || case "$FILE" in
    *.mmd|*.mermaid) ;;
    *) continue ;;
  esac

  OUT=$(bash "$SCRIPT" "$FILE" 2>&1)
  CODE=$?

  # 2 = renderer/headless browser unavailable. That is an environment issue,
  # not a diagram defect, so the hook must not block the host.
  [ "$CODE" -eq 2 ] && continue
  [ "$CODE" -eq 0 ] && continue

  FAIL=1
  {
    echo "Mermaid validation failed for $FILE — fix the diagram before continuing."
    echo "$OUT"
  } >&2
done <<< "$FILES"

[ "$FAIL" -eq 0 ] && exit 0
exit 2
