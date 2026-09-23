# repo-diagrammer

**Repo Diagrammer** is a source-backed diagram intelligence workflow for **Claude
Code** and **OpenAI Codex**.

It is designed to behave less like “ask an LLM to draw Mermaid” and more like a
technical lead analysing a repository:

```text
question
  → repository evidence
  → semantic IR
  → selected view
  → type-specific quality profile
  → renderer selection
  → rendered visual review
  → source-backed review
```

The invariant is:

> **No evidence, no element.**

A diagram must be both **true** and **professionally communicative**. Passing source
verification does not excuse unreadable auto-layout.

## Supported views

- C4 Landscape / Context / Container / Component / Dynamic
- Sequence
- Class
- ER
- State machine
- Dataflow
- Deployment
- Call graph
- Use case
- Flowchart
- Swimlane

Every type has its own semantic and presentation contract under
`skills/repo-diagram/references/profiles/`.

## Model once, create many views

The workflow uses a renderer-neutral **Evidence IR**. Real facts are traced once with
stable IDs and evidence; diagrams select views from those facts.

For a diagram set:

```text
docs/diagrams/model.spec.yaml
docs/diagrams/context.spec.yaml
docs/diagrams/container.spec.yaml
docs/diagrams/core-flow.sequence.spec.yaml
...
```

This prevents the same service, relation, or boundary from changing meaning between
architecture, sequence, deployment, ER, and other views.

## Renderer strategy

The plugin does not force Mermaid onto every problem.

| Type | Preferred renderer |
|---|---|
| C4 static / dataflow / flowchart | Mermaid + ELK |
| Sequence | Mermaid simple; PlantUML complex |
| Class | PlantUML |
| ER | Mermaid |
| State | Mermaid |
| Deployment | PlantUML |
| Call graph | Graphviz dot |
| Use case | Mermaid >=12; PlantUML fallback |
| Swimlane | Mermaid >=11.16; fallback otherwise |

Fallbacks are allowed only when they preserve semantics.

## Conformance modes

**practical** is the default: source-backed, senior-engineering diagrams using a
curated subset of each notation.

**textbook-strict** is selected when the request explicitly asks for OMG/UML, C4,
ISO 42010, Chen/Crow's Foot, textbook, academic, thesis, or standards-grade output.
It loads the matching files under `references/standards/` and runs mechanical
semantic checks.

Strict mode deliberately claims only a **documented subset**. The plugin never
auto-labels its output "fully UML compliant" or "fully ISO 42010 conformant".

Current standards targets:
- OMG UML 2.5.1 — Use Case, Sequence/Interaction, and Class subset;
- C4 Model — architecture abstraction and notation/review rules;
- ISO/IEC/IEEE 42010:2022 — architecture-description alignment subset;
- Chen 1976 — conceptual ER;
- Information Engineering / Crow's Foot — logical/physical ER.

## Quality gates

### Truth
- every real node/relation has evidence;
- `validate_spec.py` mechanically rejects missing evidence, broken relation endpoints,
  duplicate IDs, invalid profile/type combinations, and selected type invariants;
- directions and protocols match code/config;
- async boundaries remain async;
- cardinality/guards/ownership are not guessed;
- unknowns go to Gaps.

### Type contract
The selected profile checks the semantics that matter for that diagram: message order
for sequence, relation type for class, constraints/cardinality for ER, transitions for
state, topology for deployment, actor goals for use case, ownership for swimlane, etc.

### Visual acceptance
The **rendered** result is inspected at 100%. Layout, hierarchy, crossings, labels,
density and legend semantics can be Blocking defects.

High-level architecture additionally uses the polished technical-poster style from
`high-level-architecture-style.md`.

## Install

### Claude Code

```text
/plugin marketplace add lequan170205/repo-diagrammer
/plugin install repo-diagrammer@repo-diagrammer-marketplace
```

Restart Claude Code after installation.

Entry points:

```text
/diagram
/diagram-review
/diagram-set
/diagram-doctor
```

### OpenAI Codex

```bash
codex plugin marketplace add lequan170205/repo-diagrammer
```

Open `/plugins`, install **Repo Diagrammer**, then start a new Codex chat.

Explicit skills:

```text
$repo-diagram
$diagram
$diagram-review
$diagram-set
$diagram-doctor
```

### Direct-copy fallback

```bash
bash install.sh --claude
bash install.sh --codex
bash install.sh --both
```

Project scope is also supported by passing the project directory.

## Tooling

Recommended renderer coverage:

```bash
npm i -g @mermaid-js/mermaid-cli
npx puppeteer browsers install chrome-headless-shell
# plus PlantUML and Graphviz when their diagram types matter
```

Run `/diagram-doctor` or `$diagram-doctor` to detect renderer versions,
capabilities, headless browser and repo-specific extraction tools.

Mermaid capabilities are version-gated:
- >=11.16: native swimlane;
- >=12: native use-case.

## Usage

```text
draw the backend architecture
draw a sequence diagram for checkout
draw the domain class model for payments
draw a physical ERD from migrations
draw the order lifecycle state machine
draw the ingestion dataflow
draw production deployment topology
show what calls this handler
draw use cases for the admin role
draw the approval process as a swimlane
```

Vietnamese natural language works too.

## Diagram sets

`/diagram-set` / `$diagram-set` builds a shared model once, then derives only
useful views. It runs a cross-view consistency check before delivery.

## Repository structure

```text
repo-diagrammer/
├── commands/                         Claude Code wrappers
├── agents/                           Claude subagent wrappers
├── skills/
│   ├── repo-diagram/
│   │   ├── SKILL.md                 core brain/workflow
│   │   ├── assets/spec.template.yaml
│   │   ├── references/
│   │   │   ├── semantic-ir.md
│   │   │   ├── renderer-strategy.md
│   │   │   ├── profiles/
│   │   │   ├── standards/
│   │   │   ├── layout-quality.md
│   │   │   └── high-level-architecture-style.md
│   │   └── scripts/
│   │       ├── render_any.sh
│   │       ├── validate_spec.py
│   │       ├── visual_lint_svg.py
│   │       └── self_test.sh
│   ├── diagram/
│   ├── diagram-review/
│   ├── diagram-set/
│   └── diagram-doctor/
├── .claude-plugin/
├── .codex-plugin/
└── install.sh
```

## Design basis

The workflow distinguishes normative standards (OMG UML 2.5.1, ISO/IEC/IEEE
42010:2022), the canonical C4 model, academic ER foundations (Chen 1976), textbook
practice, and renderer-specific syntax. See
`skills/repo-diagram/references/research-basis.md` and
`skills/repo-diagram/references/standards/`.

## Limitations

- Runtime sequence and dynamic dispatch still require bounded manual tracing when
  static tools cannot resolve them.
- Use cases derived from routes/roles may not capture full product intent; uncertainty
  must be explicit.
- A missing renderer means visual review is **unverified**, never silently passed.
- Auto-generated extraction is input to curation, not the final diagram.

MIT.
