# Diagram types

## Contents
- [Decision path](#decision-path)
- [Per-type rules](#per-type-rules)
- [Level discipline](#level-discipline)
- [Anti-patterns](#anti-patterns)
- [Common requests → what to actually draw](#common-requests--what-to-actually-draw)

## Decision path

Start from the verb in the request.

- "what is / who uses / what does it integrate with" → **C4 Context**
- "what are the moving parts / what do we deploy" → **C4 Container**
- "what's inside <service>" → **C4 Component**
- "what happens when / walk me through / trace / debug" → **Sequence**
- "what's the data model" → **ER**
- "what's the type hierarchy" → **Class**
- "what states / lifecycle" → **State machine**
- "where does data come from and go" → **Dataflow**
- "where does it run / infra" → **Deployment**
- "what calls this" → **Call graph**
- "who can do what / what can each role do" → **Use case**
- "what's the process / who approves what" → **Flowchart**

When two fit, ask: is the question about **structure** (what exists) or **behaviour**
(what happens over time)? Structure → C4/class/ER/use case. Behaviour →
sequence/state/flowchart/dataflow.

## Per-type rules

### C4 Context
Your system as one box, surrounded by people and external systems. **No technology
anywhere.** ≤8 boxes. Audience: stakeholders, day-one joiners.
Sources: `.env.example`, third-party SDKs in manifests, auth config.

### C4 Container
Separately deployed or separately running things: web app, API, worker, scheduler,
database, cache, broker. A library is not a container; a cron worker is. Every arrow
gets protocol + purpose (`JSON/HTTPS — creates orders`). This is the most useful
diagram in most repos.
Sources: `docker-compose.yml`, k8s manifests, `Procfile`, CI deploy jobs, multiple
entrypoints under `cmd/`.

For a generic "high-level architecture", "backend architecture" or "system overview"
request, keep C4-container truth but use the `polished-overview` presentation profile.
Presentation groups may visually cluster related containers, but they are not
architectural boundaries and may not receive edges. If grouping would hide which
container an edge targets, keep the containers visible inside the group.

### C4 Component
Inside **one** container: controllers, services, repositories, gateways, adapters.
Don't show other containers' internals. Group by responsibility, not by folder, when
the folders lie.
Sources: DI registrations, annotations, package structure.

Skip C4 Level 4 — use a class diagram if you truly need code level. Usually you don't;
the IDE does it better.

### Sequence
One scenario, time-ordered. Name it ("Checkout — happy path", "Checkout — payment
declined"). Include activation bars, real `alt/opt/loop/par`, async arrows for events,
and returns that matter. Exclude getters, logging, DTO mapping.

Two diagrams beat one diagram with six `alt` blocks — the happy path disappears
otherwise.

Show the queue as a participant rather than drawing publisher→consumer directly. The
decoupling *is* the architecture.

### Class
Only when type relationships carry meaning: domain models, plugin hierarchies,
strategy/adapter structures. Show only members relevant to the question — a class
diagram with every field is a worse version of the source file.
Extract with a tool (see `extraction.md`), then cut and group.

### ER
From migrations, schema dump, or ORM models — never from memory. Mark PK/FK/UK, real
cardinality from constraints. Include join tables as entities. Split by bounded
context past ~15 entities.

### State machine
For entities with an explicit status field and transition logic. Every transition
needs a trigger, plus a `[guard]` where the code has a condition. Mark initial and
terminal states.
Find them: `rg -n "enum .*(Status|State)|status =|transition|createMachine"`.

If the code permits a transition the business doesn't intend, draw it and flag it.
That's a finding.

### Dataflow
For ETL, streaming, analytics. Nodes = transformations, edges = datasets with format
and frequency where known. Mark batch vs stream explicitly.

### Deployment
Infrastructure nodes: region, cluster, node, container, with replicas, scaling, ports.
Only from real infra code. Never from imagination.

### Call graph
One root, ≤4 levels. Good for "what breaks if I change this". State explicitly
whether it is static (from a tool) or hand-traced, and note that static graphs miss
interface dispatch, DI and reflection.

### Use case
Actors and the goals they can achieve. From code, derive it like this — and be honest
that the derivation is partly inference:

- **Actors** from auth: roles, permissions, guards, policies.
  `rg -n "role|ROLE_|@PreAuthorize|can\(|ability|policy|guard"`
- **Use cases** from entry points the actor can reach: routes, CLI commands, UI
  screens, scheduled jobs (actor = "System" or "Scheduler").
- **`<<include>>`** when one flow always calls another internally.
- **`<<extend>>`** for conditional/optional variants.

Keep to ≤12 use cases and ≤5 actors, at the goal level ("Place an order"), not the
endpoint level ("POST /orders/:id/items"). Mermaid has no native use-case notation —
draw it as a flowchart with actors on the left and a system boundary subgraph, or use
PlantUML, which does have it. Template in `notation.md`.

Say plainly in Gaps that use cases inferred from routes may not match the product's
actual intent; the product owner is the authority, not the router.

## Level discipline

Exactly one level of abstraction per diagram. Test: could each box be opened into its
own diagram of the level below? If one box would expand into 30 things and another
into 2, the levels are mixed.

Mixing is the strongest tell of an AI-generated diagram — a Kubernetes cluster, a Java
class and an HTTP header on the same canvas.

## Anti-patterns

| Anti-pattern | Why it's bad | Instead |
|---|---|---|
| The everything diagram | unreadable, never updated | split by question |
| Boxes named "Business Logic", "Core", "Utils" | says nothing | real names, or collapse and name by responsibility |
| Unlabelled arrows | reader can't tell RPC from import | protocol + intent on every edge |
| Invented infrastructure | actively misleading | only what's in code/config |
| 15-participant sequence | nobody can follow | split scenarios, collapse to subsystems |
| ERD from memory of the models | FK direction and cardinality usually wrong | read migrations |
| Raw tool output pasted in | over budget, under-abstracted | cut, group, label |
| Folder tree redrawn as architecture | folders ≠ architecture | group by responsibility and dependency direction |

## Common requests → what to actually draw

- **"Vẽ sơ đồ hệ thống" / "high-level architecture" / "backend architecture"** →
  C4 Container truth + `polished-overview` presentation by default. Offer Context as
  a companion if there are real external systems.
- **"Vẽ flow của API /orders"** → Sequence, happy path; add a second for the main
  failure if the audience is engineering.
- **"Vẽ database"** → ER from migrations. Over 15 tables, ask which context, or lead
  with a grouped overview then detail one area.
- **"Feature X hoạt động thế nào"** → C4 Component for the module **plus** one
  sequence for its primary flow. Two small diagrams answer this far better than one
  big one.
- **"Onboarding cho dev mới"** → a set: Context → Container → one sequence of the core
  journey, with a paragraph between each.
