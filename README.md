# repo-diagrammer

**Repo Diagrammer** is an evidence-backed codebase diagram workflow for **Claude Code**
and **OpenAI Codex**.

Give it a repository and ask for an architecture, sequence, class, ER, state,
dataflow, deployment, call graph, or use case diagram. The workflow traces the code,
builds a spec with `file:line` evidence for every node and edge, validates Mermaid
when a renderer is available, and runs a tech-lead review pass before delivery.

Supported diagram types:

- C4 Context / Container / Component
- Sequence
- Class
- ER
- State machine
- Dataflow
- Deployment
- Call graph
- Use case

---

## Install

### Claude Code

Add this repository as a marketplace:

```text
/plugin marketplace add lequan170205/repo-diagrammer
/plugin install repo-diagrammer@repo-diagrammer-marketplace
```

Start a new Claude Code session after installation.

Claude Code entrypoints:

```text
/diagram
/diagram-review
/diagram-set
/diagram-doctor
```

Natural-language requests also trigger the core `repo-diagram` skill.

### OpenAI Codex

Add the same repository as a Codex marketplace:

```bash
codex plugin marketplace add lequan170205/repo-diagrammer
```

Then start Codex:

```bash
codex
```

Open the plugin browser:

```text
/plugins
```

Find **Repo Diagrammer** and install it. Start a new Codex chat after installation.

Codex can trigger the workflow naturally, or explicitly through the bundled skills:

```text
$repo-diagram
$diagram
$diagram-review
$diagram-set
$diagram-doctor
```

Codex may ask you to review/trust the bundled hook before it runs. If you do not
trust the hook, the workflow still works; automatic Mermaid validation after file
writes is simply skipped.

### Direct-copy fallback

Plugin installation is preferred because it wires the bundled hook and MCP config.

For a skills-only install:

```bash
# Claude Code — user scope
bash install.sh --claude

# Codex — user scope (~/.codex/skills)
bash install.sh --codex

# Both
bash install.sh --both

# Project scope
bash install.sh --claude ./my-project
bash install.sh --codex ./my-project
```

Project-scoped Codex skills are copied to `.agents/skills/`.

---

## Mermaid renderer

Install once if you want local render validation:

```bash
npm i -g @mermaid-js/mermaid-cli
npx puppeteer browsers install chrome-headless-shell
```

A missing headless browser often looks like a Mermaid syntax failure. The workflow
distinguishes environment failures from diagram syntax failures.

Run the doctor after installation:

- Claude Code: `/diagram-doctor`
- Codex: `$diagram-doctor`

---

## Usage

Natural language works on both hosts:

```text
draw a sequence diagram for the checkout flow
draw a class diagram for the payments module
draw an ERD from the migrations
how does the notification module work? draw it
draw a use case diagram for this system
draw the backend architecture
```

Vietnamese works too:

```text
vẽ sequence diagram cho luồng checkout
vẽ use case diagram của luồng nhắn tin
vẽ kiến trúc backend của repo này
```

Tell the agent the intended audience when it matters. An onboarding diagram should
hide most failure paths; an incident/debugging diagram should emphasize them.

### Explicit workflow entrypoints

| Goal | Claude Code | Codex |
|---|---|---|
| One diagram | `/diagram <request>` | `$diagram <request>` |
| Diagram set | `/diagram-set <scope>` | `$diagram-set <scope>` |
| Review a diagram | `/diagram-review <file>` | `$diagram-review <file>` |
| Check tooling | `/diagram-doctor` | `$diagram-doctor` |
| Core automatic skill | natural language | `$repo-diagram` or natural language |

---

## Workflow

The core workflow is the same on Claude Code and Codex:

1. **Locate the feature** with `feature_trace.sh` and repository mapping.
2. **Extract deterministically** with language-aware tools where possible.
3. **Write the spec first** using `spec.template.yaml`.
4. **Choose one diagram type and abstraction level** with explicit size budgets.
5. **Render from the spec**, not from memory.
6. **Validate and review** against source code.
7. **Deliver** the diagram, evidence table, gaps, and the saved spec.

The central rule is:

> **No evidence, no element.**

A cache, queue, auth service, load balancer, database, or relationship does not appear
on the canvas merely because it would make architectural sense. It needs evidence in
the repository.

### Polished high-level architecture

Generic requests such as "draw the backend architecture", "high-level architecture"
and "system overview" also use a `polished-overview` presentation profile.

That profile adds a second quality gate without weakening traceability:

- evidence still controls every real node and edge;
- presentation groups may only contain evidenced nodes and never receive edges;
- clients → ingress → core services → messaging/support → data/observability is the
  default visual hierarchy when the repo supports those lanes;
- semantic pastel roles, concise labels and a compact legend keep the diagram
  presentation-ready;
- the reviewer treats ugly/unbalanced high-level renders as Blocking `VISUAL`
  findings and requires another render pass.

See `skills/repo-diagram/references/high-level-architecture-style.md`.

---

## Cross-host behavior

The repository keeps one source of truth for the workflow.

### Shared

`skills/repo-diagram/` contains:

- `SKILL.md` — the seven-step workflow
- `references/diagram-types.md`
- `references/extraction.md`
- `references/notation.md`
- `references/layout-quality.md`
- `references/high-level-architecture-style.md`
- `references/repo-scout-procedure.md`
- `references/diagram-reviewer-procedure.md`
- `assets/spec.template.yaml`
- extraction and Mermaid validation scripts

Both Claude Code and Codex use these same files.

### Claude Code-specific adapters

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `commands/` for slash commands
- `agents/` as Claude subagent wrappers

### Codex-specific adapters

- `.codex-plugin/plugin.json`
- `skills/*/agents/openai.yaml` for Codex-facing skill metadata
- `$diagram`, `$diagram-review`, `$diagram-set`, and `$diagram-doctor` wrapper
  skills

The core skill does **not** require a provider-specific subagent API. Claude Code can
use its Task subagents. Codex can use multi-agent/subagent tooling when available.
If neither is available, the same bounded scout/reviewer procedures run inline.

---

## Why it is stricter than asking for a diagram directly

### 1. Static extraction before freehand reading

The workflow prefers pyreverse, madge, dependency-cruiser, `go list`, jdeps,
database schema tools, Prisma schemas, and route extraction before hand-tracing code.

### 2. Spec before Mermaid

Every node and edge gets evidence before it can be rendered. Unsupported ideas go in
**Gaps**, not on the canvas.

### 3. Render validation

`validate_mermaid.sh` renders real Mermaid blocks and distinguishes syntax errors
from a missing browser/runtime.

The bundled `PostToolUse` hook supports both Claude Code writes and Codex
`apply_patch` writes.

### 4. Source-backed review

The reviewer checks cited source lines, missing boundaries, reversed arrows, async
edges drawn as sync, ER cardinality, abstraction mixing, and readability.

---

## Limitations

- **Use case diagrams are partly inferred.** Actors come from roles/permissions and
  use cases from reachable entrypoints. Product intent still belongs to the product
  owner.
- **Static call graphs miss dynamic dispatch.** Interfaces, DI, reflection, event
  buses, and framework wiring may require manual tracing.
- **Sequence diagrams require runtime reasoning.** Static tools can provide anchors
  but cannot reconstruct the whole execution order reliably.
- **PlantUML does not render natively on GitHub.** Mermaid remains the default unless
  textbook UML/C4 notation is specifically needed.

---

## Repository structure

```text
repo-diagrammer/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .codex-plugin/
│   └── plugin.json
├── .mcp.json
├── commands/                         Claude Code slash-command adapters
├── agents/                           Claude Code subagent adapters
├── hooks/
│   ├── hooks.json
│   └── validate_on_write.sh          Claude Write/Edit + Codex apply_patch
├── install.sh
└── skills/
    ├── repo-diagram/                  shared source-of-truth workflow
    │   ├── SKILL.md
    │   ├── agents/openai.yaml
    │   ├── references/
    │   ├── assets/spec.template.yaml
    │   └── scripts/
    ├── diagram/                       Codex-friendly explicit wrapper
    ├── diagram-review/
    ├── diagram-set/
    └── diagram-doctor/
```

MIT.
