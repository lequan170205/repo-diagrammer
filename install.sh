#!/usr/bin/env bash
# install.sh — direct-copy fallback for Claude Code and OpenAI Codex.
#
# Plugin/marketplace installation is preferred because it also wires hooks + MCP.
#
# Backward compatible:
#   bash install.sh                    # Claude Code, user scope
#   bash install.sh ./myrepo           # Claude Code, project scope
#
# Explicit:
#   bash install.sh --claude [project]
#   bash install.sh --codex  [project]
#   bash install.sh --both   [project]
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="claude"

case "${1:-}" in
  --claude) MODE="claude"; shift ;;
  --codex)  MODE="codex"; shift ;;
  --both)   MODE="both"; shift ;;
esac

PROJECT="${1:-}"

rewrite_skill_root() {
  local skills_root="$1"
  local core="$skills_root/repo-diagram/SKILL.md"
  [ -f "$core" ] || return 0

  # Direct-copy installs do not set PLUGIN_ROOT/CLAUDE_PLUGIN_ROOT. Replace the
  # plugin-root expression with the actual installed repo-diagram skill path.
  python3 - "$core" "$skills_root/repo-diagram" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
root = sys.argv[2]
text = path.read_text()
text = text.replace(
    '${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram',
    root,
)
path.write_text(text)
PY
}

install_claude() {
  local dest scope
  if [ -n "$PROJECT" ]; then
    dest="$(cd "$PROJECT" && pwd)/.claude"
    scope="project: $PROJECT"
  else
    dest="$HOME/.claude"
    scope="user: $HOME"
  fi

  mkdir -p "$dest/skills" "$dest/agents" "$dest/commands"
  cp -R "$SRC/skills/." "$dest/skills/"
  cp "$SRC/agents/"*.md "$dest/agents/"
  cp "$SRC/commands/"*.md "$dest/commands/"
  chmod +x "$dest/skills/repo-diagram/scripts/"*.sh
  rewrite_skill_root "$dest/skills"

  # Claude slash commands reference the plugin env var. Rewrite only the copied
  # standalone commands so they point at the copied skill.
  for f in "$dest/commands/"diagram*.md; do
    [ -f "$f" ] || continue
    sed -i.bak "s|\${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts|$dest/skills/repo-diagram/scripts|g" "$f"
    rm -f "$f.bak"
  done

  echo "Claude Code skills installed to $dest  ($scope)"
}

install_codex() {
  local skills_dest scope
  if [ -n "$PROJECT" ]; then
    skills_dest="$(cd "$PROJECT" && pwd)/.agents/skills"
    scope="project: $PROJECT"
  else
    skills_dest="${CODEX_HOME:-$HOME/.codex}/skills"
    scope="user: ${CODEX_HOME:-$HOME/.codex}"
  fi

  mkdir -p "$skills_dest"
  cp -R "$SRC/skills/." "$skills_dest/"
  chmod +x "$skills_dest/repo-diagram/scripts/"*.sh
  rewrite_skill_root "$skills_dest"

  echo "Codex skills installed to $skills_dest  ($scope)"
}

case "$MODE" in
  claude) install_claude ;;
  codex)  install_codex ;;
  both)   install_claude; install_codex ;;
esac

echo
echo "Direct-copy mode installs skills only."
echo "For hooks + the bundled mermaid-validator MCP, install the repository as a plugin."
echo
case "$MODE" in
  claude)
    echo "Next: restart Claude Code, then run /diagram-doctor or ask naturally."
    ;;
  codex)
    echo "Next: restart Codex, then use $diagram-doctor, $diagram, or ask naturally."
    ;;
  both)
    echo "Next: restart both hosts and run their diagram-doctor entrypoint."
    ;;
esac
