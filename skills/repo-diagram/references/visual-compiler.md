# Visual compiler

Repo Diagrammer separates **semantic correctness** from **geometric correctness**.

The evidence IR answers *what exists and what relates*. The visual compiler answers
*where it is placed, how edges are routed, and whether the result is readable*.

## Pipeline

```text
Evidence IR
  → view model
  → layout rows / ordering
  → renderer
  → geometry analyzer
  → automatic presentation repair
  → render again
  → visual acceptance
```

A visual review is not considered complete merely because source syntax parses.

## Native high-level architecture renderer

For static C4/high-level architecture views using `presentation.style:
polished-overview`, prefer `render_architecture_svg.py` when PyYAML is available.

It owns node geometry instead of delegating the entire composition to Mermaid:

- deterministic layered placement;
- declaration-order-aware barycentric ordering plus adjacent-swap hill climbing;
- candidate-scored orthogonal edge routing;
- obstacle-aware perimeter routing for long cross-layer edges;
- route scoring that penalizes node hits, crossings, long shared corridors, bends and route length;
- geometry-aware label placement that avoids nodes, labels and unrelated edges;
- distributed edge ports for high-degree nodes instead of one congested center port;
- primary-flow-aware layout, routing and emphasis across every contiguous run in `view.primary_paths` (with `view.primary_path` kept for backward compatibility);
- adaptive node height with glyph-aware width estimation and wrapped responsibility copy;
- optional real-browser typography verification using SVG `getBBox()`;
- adaptive canvas sizing to reduce dead whitespace on small views;
- semantic legends inferred from the encodings actually present: primary flow, sync/async relations, and visible node roles, with automatic wrapping;
- stable `data-node-id` and `data-edge-id` metadata for machine inspection.

Use Mermaid/PlantUML/Graphviz for diagram types where their notation semantics are
the main value. The native renderer is intentionally not a replacement for Sequence,
Class, ER, State, or rich UML Deployment notation.

## Density planning and automatic splitting

Before a polished architecture render, measure source-view density. By default a view
is split when it exceeds the readability budget (currently >20 nodes, >32 edges on a
non-trivial graph, or a high-degree hub above the configured threshold).

Automatic splitting is semantics-preserving:

- generated views reuse original node/edge IDs and evidence;
- no synthetic subsystem/service nodes are invented;
- the overview selects real primary/focus/high-degree nodes only;
- detail views contain a bounded core plus a few real one-hop context nodes;
- if bounded context would leave source relations unrepresented, the planner adds bounded integration views containing only the real endpoints of those uncovered edges;
- evidence-backed boundaries and presentation groups are shown only when their full
  membership is visible in that generated view;
- omitted elements are recorded in `view.suppress`;
- context elements are recorded in `view.context_nodes`;
- primary-flow emphasis never bridges omitted nodes: split views preserve contiguous source runs in `view.primary_paths` and use the longest run for backward-compatible `view.primary_path`.

The default generated set is an overview plus bounded detail views. The manifest
records why splitting happened and explicitly states that stable IDs were preserved
and no architecture elements were invented. Before any generated view is rendered,
`validate_split_set.py` requires generated nodes, edges and real boundaries to be
verbatim source elements, protects immutable source/conformance metadata, verifies
presentation groups are source-derived, validates focus/context classification,
enforces per-view readability budgets recorded in the manifest, and requires 100%
source node/edge coverage across the generated set.

Use `density_planner.py <spec> <outdir> --check` to inspect the density decision, or
let `render_polished.py` automatically create `<output-stem>.set/` when splitting is
required.

## Automatic repair loop

Use `render_polished.py` as the default entry point for polished static architecture.
It runs the native renderer and strict geometry analyzer, then performs
defect-directed presentation search. Crossing/overlap defects trigger alternate node
ordering and routing-order variants; collision defects increase spacing; typography
defects increase text safety margins.

Repair passes may change only presentation geometry. They must never change node
identity, relation direction, grouping membership, protocol, evidence, or architectural
boundaries.

The loop stops immediately for defects such as unrelated-node region capture or
ambiguous region overlap because those require model/grouping correction rather than
more whitespace.

## Browser-measured typography

The glyph-aware estimator keeps the renderer portable, but a real browser is the
stronger final typography gate. When Chrome/Chromium/headless-shell is available,
`browser_typography.py` loads the rendered SVG and measures actual text bounds with
`getBBox()`.

It checks node copy, edge-label copy, region headers, title/subtitle hierarchy, row
headings, legend text, line collisions, minimum readable font sizes, hierarchy
collisions, and text escaping the SVG canvas. `render_polished.py` retries geometry
only for typography defects that can plausibly be fixed by more room; font-size and
hierarchy-collision defects stop immediately instead of wasting spacing passes.

Browser verification is opportunistic by default and must report
`typography=fallback-estimator` when unavailable. Use
`--require-browser-typography` in CI or standards-sensitive delivery when typography
must be mechanically browser-verified.

## Geometry gate

Run:

```bash
python3 scripts/visual_analyze_svg.py diagram.svg --strict --max-crossings 0
```

The analyzer checks:

- node overlap;
- edge passing through unrelated nodes;
- edge/edge crossings;
- long edge/edge overlaps (ambiguous shared corridors);
- non-orthogonal native routes;
- high-degree port congestion;
- label/node, label/label and label/edge collisions;
- extremely tight node gaps;
- suspiciously long routes;
- extreme canvas aspect ratios;
- global horizontal imbalance, sparse composition and excess bottom whitespace;
- region member containment, unrelated-node capture, header collisions and ambiguous region overlap.

Native SVG metadata can produce Blocking findings. Third-party renderer DOMs are
version-dependent, so Mermaid/Graphviz geometry is heuristic and warning-only by
default. Use `--strict-heuristic` only after verifying the renderer version.

## Crossing budgets

Default targets:

- ≤10 nodes: 0 avoidable crossings;
- 11–20 nodes: at most 2 avoidable crossings;
- >20 nodes: split the view before increasing the crossing budget unless the graph
  itself is the subject.

A budget is not permission to accept an edge through a node. Edge/node crossings are
always Blocking for native high-level architecture output.

## Repair order

When the geometry gate fails, repair in this order:

1. reorder nodes within layers;
2. move a node to the correct semantic layer if the evidence/view permits it;
3. use a side/perimeter channel for a long edge;
4. shorten labels that distort node width;
5. change direction only when the story remains natural;
6. split the view if density remains high.

Never repair readability by changing architectural meaning, reversing direction,
merging distinct evidenced nodes, or inventing a boundary.

## Acceptance invariant

For a polished high-level architecture diagram, delivery requires all three:

1. evidence spec passes;
2. geometry analyzer has no Blocking finding;
3. browser typography has no Blocking finding when a browser is available/required;
4. the final rendered image is inspected at 100% for typography, hierarchy and
   subjective balance that geometry checks cannot fully measure.

Machine checks and automatic repair reduce visual mistakes; they do not replace human/agent visual review.
Composition findings are warnings by default because asymmetric architectures can be
legitimate; region ambiguity and containment defects are Blocking for native output.
