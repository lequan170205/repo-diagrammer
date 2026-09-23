#!/usr/bin/env bash
# install.sh — copy the plugin's parts straight into a Claude Code config dir.
# Use this if you don't want to go through the plugin/marketplace system.
#
#   bash install.sh            # install for the current user (~/.claude)
#   bash install.sh ./myrepo   # install into a project (./myrepo/.claude)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ $# -ge 1 ]; then
  DEST="$(cd "$1" && pwd)/.claude"
  SCOPE="project: $1"
else
  DEST="$HOME/.claude"
  SCOPE="user: $HOME"
fi

mkdir -p "$DEST/skills" "$DEST/agents" "$DEST/commands"
cp -R "$SRC/skills/repo-diagram" "$DEST/skills/"
cp "$SRC/agents/"*.md "$DEST/agents/"
cp "$SRC/commands/"*.md "$DEST/commands/"
chmod +x "$DEST/skills/repo-diagram/scripts/"*.sh

# Commands reference ${CLAUDE_PLUGIN_ROOT}, which only exists for installed plugins.
# Rewrite those paths so the copied commands work standalone.
for f in "$DEST/commands/"diagram*.md; do
  [ -f "$f" ] || continue
  sed -i.bak "s|\${CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts|$DEST/skills/repo-diagram/scripts|g" "$f"
  rm -f "$f.bak"
done

echo "Installed to $DEST  ($SCOPE)"
echo
echo "  skills/repo-diagram   the workflow, references and scripts"
echo "  agents/               repo-scout, diagram-reviewer"
echo "  commands/             /diagram, /diagram-review, /diagram-set, /diagram-doctor"
echo
echo "Not installed by this script (they need the plugin system):"
echo "  .mcp.json    mermaid-validator MCP  -> add manually if you want it:"
echo "               claude mcp add mermaid-validator -- npx -y @rtuin/mcp-mermaid-validator@latest"
echo "  hooks/       auto-validation on write"
echo
echo "Next: restart Claude Code, then run /diagram-doctor to check your tooling."
