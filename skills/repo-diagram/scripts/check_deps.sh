#!/usr/bin/env bash
set -uo pipefail
have(){ command -v "$1" >/dev/null 2>&1; }
row(){ if have "$1"; then printf '  [x] %-20s %s\n' "$1" "$2"; else printf '  [ ] %-20s %s -> %s\n' "$1" "$2" "$3"; fi; }
echo "=== RENDERERS ==="
row mmdc "Mermaid CLI" "npm i -g @mermaid-js/mermaid-cli"
row npx "Mermaid fallback" "install Node.js 18+"
row plantuml "PlantUML" "brew install plantuml / apt install plantuml"
row dot "Graphviz dot" "brew install graphviz / apt install graphviz"
echo
echo "=== CAPABILITIES ==="
if have mmdc; then echo "  Mermaid: $(mmdc --version 2>/dev/null | head -1 || echo unknown)"
else echo "  Mermaid local version: unavailable/unknown"; fi
if have plantuml; then plantuml -version 2>/dev/null | head -2 | sed 's/^/  /'; fi
if have dot; then dot -V 2>&1 | sed 's/^/  /'; fi
echo "  Mermaid >=11.16: native swimlane eligible"
echo "  Mermaid >=12: native use-case eligible"
echo
echo "=== SEARCH ==="
row rg "ripgrep" "brew install ripgrep / apt install ripgrep"
row fd "fd-find" "brew install fd / apt install fd-find"
row jq "jq" "brew install jq"
echo
echo "=== EXTRACTION ==="
row pyreverse "Python UML" "pip install pylint"
row madge "JS/TS deps" "npx madge"
row tsc "TypeScript" "npm i -g typescript"
row go "Go deps" "install Go"
row jdeps "Java deps" "install JDK"
row mvn "Maven deps" "install Maven"
row psql "PostgreSQL schema" "install postgresql-client"
row dotnet ".NET / EF" "install .NET SDK"
echo
if have mmdc || have npx; then
  if ls "${PUPPETEER_CACHE_DIR:-$HOME/.cache/puppeteer}"/chrome* >/dev/null 2>&1 || have google-chrome || have chromium || have chromium-browser; then
    echo "OK: Mermaid validation path + browser appear available."
  else
    echo "WARNING: Mermaid path exists but no headless browser detected."
    echo "  npx puppeteer browsers install chrome-headless-shell"
  fi
else echo "WARNING: Mermaid renderer unavailable."; fi
