---
name: repo-diagram
description: Read a real codebase and produce accurate, evidence-backed diagrams of any feature or subsystem — C4 context/container/component, sequence, class, ER, state machine, dataflow, deployment, call graph, use case — in Mermaid or PlantUML. Use this skill whenever the user asks to draw, sketch, visualise, map, diagram or explain the architecture, flow, structure, lifecycle or data model of code, including phrasings like "vẽ sơ đồ", "vẽ diagram", "sơ đồ kiến trúc", "sequence diagram cho luồng X", "ERD", "class diagram", "module này gọi gì", "how does feature X work end to end", and also when a picture would carry the answer to an "explain the architecture" question. Use it even when the user does not name a diagram type.
---

# Repo Diagram

Draw the way a tech lead does: find the code first, claim only what the code
supports, extract deterministically where a tool can do it better than reading,
pick the abstraction level that answers the question, keep it small enough to read,
and prove it renders.

The failure this skill exists to prevent is a **plausible-looking diagram that is
wrong** — invented services, missing async boundaries, arrows pointing the wrong way,
a 40-node blob nobody can read. A wrong diagram is worse than none, because teams act
on it.

Write prose in whatever language the user writes in. Keep node labels in the
identifiers the code actually uses — never translate `OrderService`.

---

## Five rules that override everything else

1. **No evidence, no element.** Every box and arrow traces to something real: a file,
   a symbol, a route, a migration, a config key. Anything you cannot point at goes in
   the Gaps section, not on the canvas. Never add a Cache, Queue, Load Balancer or
   Auth Service because the shape feels incomplete.
2. **Prefer a tool over reading.** If a static-analysis tool can extract the relation
   (class hierarchies, import graphs, DB schema, route tables), run it. Reading code
   and recalling it is where hallucinated edges come from. See
   `references/extraction.md`.
3. **One question per diagram.** If the picture tries to show structure *and* runtime
   *and* deployment, it answers nothing.
4. **Budget, then split.** Over budget means the abstraction level is wrong, not that
   you should cram. Budgets in Step 4.
5. **It must render.** Validate before delivering (Step 6). Never claim a diagram was
   validated when it wasn't.

---

## Workflow

Scripts live in `scripts/` next to this file. Reference files live in `references/`.

### Host portability

This skill must work in both Claude Code and OpenAI Codex.

- For plugin installs, resolve the plugin root with `${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}`.
  Codex sets `PLUGIN_ROOT` and also exposes `CLAUDE_PLUGIN_ROOT` for compatibility;
  Claude Code exposes `CLAUDE_PLUGIN_ROOT`.
- If both variables are unavailable because the skill was installed standalone, use
  the actual directory containing this `SKILL.md` as the skill root.
- Do not require one provider's subagent API. When isolated subagent tooling exists,
  use it; otherwise perform the same bounded scout/review procedure inline.
- Claude Code slash commands are convenience wrappers only. Codex may invoke the
  bundled skills directly (for example `$repo-diagram` or `$diagram`) or trigger
  them from natural language.

### Step 0 — Fix the question

If the request is specific ("sequence diagram cho luồng checkout"), go straight to
Step 1. Do not interrogate.

Ask at most **one** question, and only when genuinely ambiguous, covering scope
(whole system / one module / one flow) and audience (onboarding / architecture review
/ debugging an incident / stakeholder). Audience changes the output more than
anything else: an onboarding diagram hides error paths, an incident diagram is mostly
error paths.

### Step 1 — Locate the feature

Most requests name a *feature*, not a file. Turn the feature name into code anchors
before anything else:

```bash
bash "${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/feature_trace.sh" <keyword> [repo_root]
```

It searches routes, handlers, services, models, tables, events, jobs, config and
tests for the keyword and its common variants, and prints grouped hits with
`file:line`. Run it with 2–3 synonyms (`checkout`, `order`, `cart`) rather than one.

If it returns nothing useful, the feature is named differently in code than in the
product. Ask the user for one concrete anchor: an endpoint, a screen, a table name,
or a class. That one question saves ten wrong guesses.

For whole-repo requests, or when you need the big picture first:

```bash
bash "${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/repo_map.sh" [repo_root]
```

It prints languages, layout, manifests, entrypoints, route files, schemas, infra
files and the biggest source files. Read its output before opening any source file.

**On a large repo, delegate when the host supports isolated subagents.** Use the
`repo-scout` procedure in `references/repo-scout-procedure.md` with the feature
keywords and diagram type. In Claude Code this can be the `repo-scout` Task
subagent; in Codex use the available multi-agent/subagent tooling when enabled. If
the host exposes no isolated subagent tool, perform the same bounded scout procedure
inline rather than skipping it. For several independent subsystems, parallelise one
scout per subsystem when supported — never one per file.

### Step 2 — Extract, don't recall

Before reading source by hand, check whether a tool can produce the relation
deterministically:

```bash
bash "${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/check_deps.sh"
bash "${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/extract_structure.sh" <mode> [path]
```

`extract_structure.sh` auto-detects the language and drives pyreverse, madge,
dependency-cruiser, go list, jdeps and similar, emitting Mermaid or a graph you can
read. Full per-language recipes, including what each tool does and does not catch:
`references/extraction.md`.

Where no tool fits (runtime flows, event wiring, dynamic dispatch), read source — but
read *ranges*, not whole files: find the symbol with `rg -n`, then read ±40 lines.
Budget roughly 30 file reads per diagram.

Stop tracing at these boundaries and record each as a single edge: a network call, a
DB/ORM call, a publish to a queue or bus, a framework dispatch you cannot statically
resolve. Stop at depth 4 or when you reach pure utility code.

### Step 3 — Write the spec before the diagram

**This is what makes the output accurate. Do not skip it.** Copy
`assets/spec.template.yaml` to a scratch file and fill it in from what Steps 1–2
found, then render from the spec. Writing Mermaid directly from a fuzzy memory of the
code is exactly where invented arrows appear.

While filling it in:

- `evidence` is `path:line`, or `path` for config, or `tool:<command>` for anything a
  script extracted. No evidence → move it to `gaps`.
- Mark `sync: false` for anything crossing a queue, event bus, goroutine, worker,
  background job, `@Async`, `setTimeout`, or fire-and-forget publish. **Async edges
  drawn as synchronous calls are the single most damaging error in generated sequence
  diagrams** — they make a decoupled system look like a distributed monolith.
- Record every network hop. Reviewers look at boundaries first.
- Two nodes with the same label but different evidence usually means a duplicated
  abstraction. Say so — that is the kind of thing a tech lead flags.

### Step 4 — Choose type, level and budget

`references/diagram-types.md` has the full decision guide and per-type rules,
including use case diagrams (which come from actors and entry points, not from class
structure). Quick map:

| Question | Diagram |
|---|---|
| What is this system, who uses it, what does it talk to? | C4 Context |
| What do we deploy and how do the pieces talk? | C4 Container |
| What's inside this one service? | C4 Component |
| What happens, in order, when X occurs? | Sequence |
| What's the type/domain structure? | Class |
| What do the tables look like? | ER |
| What states can this entity be in? | State machine |
| How does data get transformed A→Z? | Dataflow |
| Where does it run? | Deployment |
| What calls this / what does this call? | Call graph |
| Who can do what with the system? | Use case |

Budgets — over budget means split or zoom out:

| Diagram | Budget |
|---|---|
| C4 Context | ≤ 8 boxes |
| C4 Container | ≤ 12 containers |
| C4 Component | ≤ 15 components |
| Sequence | ≤ 8 participants, ≤ 25 messages |
| Class | ≤ 12 classes, only relevant members |
| ER | ≤ 15 entities; split by bounded context |
| Call graph | ≤ 4 levels deep |
| Use case | ≤ 12 use cases, ≤ 5 actors |

Collapsing is judgement, not truncation: group by package or bounded context and name
the group after what it does, never "Others".

### Step 5 — Render

Default to **Mermaid** — it renders natively on GitHub, GitLab, VS Code, Obsidian.
Use PlantUML only when the user asks, or when they want real C4-PlantUML notation or
a very large diagram needing a stronger layout engine.

Read `references/notation.md` for exact syntax per type plus the parser traps that
cause most render failures, and `references/layout-quality.md` before you commit to
an element order — declaration order, not styling, is what decides whether the
diagram is readable.

Mermaid's `C4Context` block is experimental and lays out poorly. For C4, use a
`flowchart` with `subgraph` boundaries and the C4 styling convention in
`references/notation.md`.

### Step 6 — Validate, then review

```bash
bash "${PLUGIN_ROOT:-$CLAUDE_PLUGIN_ROOT}/skills/repo-diagram/scripts/validate_mermaid.sh" path/to/output.md
```

It extracts every ```mermaid block, renders each with mermaid-cli, and prints the
failing block with line numbers plus the likely cause. If the `mermaid-validator` MCP
server is connected, you can also validate a single block through its
`validateMermaid` tool without writing a file — useful while iterating.

If neither renderer is available, say so in the delivery. Do not claim validation you
did not do.

Then the tech-lead pass. On anything non-trivial, apply the review procedure from
`references/diagram-reviewer-procedure.md`. When isolated subagent tooling is
available, run that review in a clean context (Claude Code: the `diagram-reviewer`
Task subagent; Codex: available multi-agent/subagent tooling). If not, run the same
procedure inline. Fix everything it marks Blocking before delivering:

- [ ] Every node and edge appears in the evidence table
- [ ] Arrow direction = who initiates, not where bytes flow
- [ ] Async edges visually distinct from sync calls
- [ ] Network and trust boundaries visible
- [ ] Within budget, readable at 100% zoom
- [ ] One abstraction level throughout
- [ ] Labels match real code identifiers
- [ ] Error paths present if the audience needs them
- [ ] Nothing added because it "felt like" it should be there
- [ ] Unknowns in Gaps, not quietly smoothed over

### Step 7 — Deliver

Write a Markdown file in this shape:

```markdown
# <Title>

**Question answered:** <one line>
**Scope:** <feature/module/flow>  •  **Level:** <C4 L2 / sequence / …>
**Commit:** <git rev-parse --short HEAD>  •  **Validated:** <yes — mermaid-cli / no — reason>

```mermaid
…
```

## How to read it
<3–6 bullets: legend, boundaries, notable patterns>

## Evidence
| Element | Kind | Source |
|---|---|---|
| OrderService | component | `src/orders/order_service.ts:12` |
| Order→OrderItem | relation | `tool: pyreverse -o mmd src/` |

## Gaps & assumptions
- …

## What I'd look at next
<risks a tech lead would flag: cycles, god objects, chatty boundaries, shared
database, retried async paths without idempotency>
```

The Evidence table is not bureaucracy. It lets a reviewer verify the diagram in a
minute instead of re-reading the repo, and it keeps you honest while drawing.

Default output path: `docs/diagrams/<slug>.md`, with the spec saved beside it as
`docs/diagrams/<slug>.spec.yaml` so the next regeneration starts from the spec and
produces a reviewable diff.

---

## Reference files

- `references/diagram-types.md` — decision guide, per-type rules, anti-patterns
- `references/extraction.md` — static-analysis recipes per language
- `references/notation.md` — Mermaid/PlantUML syntax, parser traps, C4 template
- `references/layout-quality.md` — what makes a diagram readable
- `references/repo-scout-procedure.md` — bounded repository exploration procedure
- `references/diagram-reviewer-procedure.md` — source-backed tech-lead review procedure
- `assets/spec.template.yaml` — the intermediate spec

## Scripts

- `scripts/repo_map.sh` — whole-repo recon
- `scripts/feature_trace.sh` — feature keyword → code anchors
- `scripts/extract_structure.sh` — deterministic extraction (classes/deps/routes/schema)
- `scripts/validate_mermaid.sh` — render check with failure diagnosis
- `scripts/check_deps.sh` — what's installed, what to install
