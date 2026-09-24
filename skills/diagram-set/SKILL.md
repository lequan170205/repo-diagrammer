---
name: diagram-set
description: Generate a coherent repository diagram set from one shared evidence model.
---

# Diagram Set

1. Read the core `repo-diagram` skill, `semantic-ir.md`, and profile index.
2. Map/scout once and create `docs/diagrams/model.spec.yaml`.
3. Select only views that add value; do not mechanically generate every type. For a
   dense polished architecture view, use the density planner to derive overview/detail
   views automatically without inventing nodes.
4. Derive every view from stable model IDs.
5. Load each view's own quality profile and renderer strategy.
6. Render + visually review + source-review every view.
7. For generated split views, preserve stable IDs, record context/suppressed nodes,
   and validate every selected node/relation against the shared model. The complete
   generated set must cover every source node and relation at least once; use bounded
   integration views for cross-cluster relations that do not fit detail context.
   Evidence-backed boundaries must also be covered truthfully: generate a dedicated
   full-membership boundary view when it fits the budget, otherwise disclose the
   oversized boundary in the manifest. Never render a partial real boundary.
8. Cross-view consistency gate: names, kinds, relation direction/semantics, real
   boundaries, palette/legend meaning.
9. Deliver an ordered `docs/diagrams/README.md`.

A set is several views of one model, not independent pictures.
