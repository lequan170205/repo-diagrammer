#!/usr/bin/env bash
# check_deps.sh — report which extraction/render tools are available.
set -uo pipefail
have() { command -v "$1" >/dev/null 2>&1; }
row() { if have "$1"; then printf '  [x] %-22s %s\n' "$1" "$2"; else printf '  [ ] %-22s %s  -> %s\n' "$1" "$2" "$3"; fi; }

echo "=== RENDER / VALIDATE (at least one required) ==="
row mmdc     "mermaid-cli renderer"      "npm i -g @mermaid-js/mermaid-cli"
row npx      "can run mmdc via npx"      "install Node.js 18+"
row plantuml "PlantUML renderer"         "brew install plantuml / apt install plantuml"
row dot      "Graphviz"                  "brew install graphviz / apt install graphviz"

echo
echo "=== SEARCH (much faster recon) ==="
row rg "ripgrep" "brew install ripgrep / apt install ripgrep"
row fd "fd-find" "brew install fd / apt install fd-find"
row jq "jq"      "brew install jq / apt install jq"

echo
echo "=== EXTRACTION (per language, only what your repo needs) ==="
row pyreverse "Python UML + packages"  "pip install pylint"
row madge     "JS/TS module graph"     "npx madge (no install needed)"
row tsc       "TypeScript"             "npm i -g typescript"
row go        "Go deps"                "install Go"
row jdeps     "Java class deps"        "part of the JDK"
row mvn       "Maven dep tree"         "install Maven"
row psql      "PostgreSQL schema"      "install postgresql-client"
row dotnet    ".NET / EF Core"         "install .NET SDK"

echo
if have mmdc || have npx; then
  echo "OK: a Mermaid renderer is reachable — diagrams can be validated."
  # mermaid-cli drives a headless browser; a missing one looks like a syntax error.
  if ls "${PUPPETEER_CACHE_DIR:-$HOME/.cache/puppeteer}"/chrome* >/dev/null 2>&1 \
     || have google-chrome || have chromium || have chromium-browser; then
    echo "OK: a headless browser is present."
  else
    echo "WARNING: no headless browser found for mermaid-cli. Run once:"
    echo "  npx puppeteer browsers install chrome-headless-shell"
  fi
else
  echo "WARNING: no Mermaid renderer. Diagrams cannot be validated."
  echo "Install with: npm i -g @mermaid-js/mermaid-cli"
  echo "Until then, state in every delivery that the diagram was NOT validated."
fi
