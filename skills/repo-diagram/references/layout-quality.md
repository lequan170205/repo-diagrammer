# Layout quality

Whether a diagram is readable is decided mostly before you style anything. Three
findings from graph drawing research drive it.

## 1. Declaration order controls layout

Mermaid uses Dagre and PlantUML uses Sugiyama-style layered layout. Both place
elements largely in the order they appear in the source. Reordering declarations
changes the picture more than any styling directive.

So declare in **reading order**:

- actors and entry points first (they end up left in `LR`, top in `TB`)
- then the system's own components, in call order
- then data stores and external systems last (they end up right/bottom)

Declare every node explicitly before declaring edges. Letting nodes be created
implicitly by edge statements scatters them in edge order, which is rarely reading
order.

```
%% bad: nodes created implicitly, in edge order
flowchart LR
  api --> db
  user --> web
  web --> api

%% good: explicit, in reading order
flowchart LR
  user(["User"])
  web["Web"]
  api["API"]
  db[("DB")]
  user --> web
  web --> api
  api --> db
```

Same content, very different picture.

## 2. Edge crossings are the strongest predictor of comprehension difficulty

Helen Purchase's experiments on graph aesthetics found that reducing edge crossings
improves reader accuracy substantially — more than bends, symmetry or angular
resolution do. Treat crossings as the quantity you are minimising.

Practical moves, in order of effect:

1. **Reorder declarations** so connected nodes are adjacent in the source.
2. **Group with subgraphs** so intra-group edges stay short and local.
3. **Flip direction** (`LR` ↔ `TB`) — often removes several crossings at once.
4. **Split the diagram.** If crossings persist after the above, you are over budget.

Set an explicit target before you render: a diagram of this size should have at most
N crossings. Count them on the rendered output. Zero is the goal for ≤10 nodes.

Never insert invisible spacer nodes or `linkStyle` hacks to force a layout. They break
on the next edit and confuse anyone reading the source.

## 3. Proximity beats colour

Gestalt grouping: elements placed near each other are read as related, regardless of
how they are coloured. So grouping must be expressed through layout — `subgraph`
boundaries, adjacency — not through fill colour alone.

Consequences:

- A subgraph that isn't a real boundary (process, network, trust, bounded context)
  actively misleads. Don't group for tidiness.
- Colour is a secondary channel. Use it for one binary distinction at most (internal
  vs external, or sync vs async — not both), and state the mapping in the legend.
- Two elements that must not be confused should be far apart, not merely different
  colours.

## Quick pre-render check

- Are nodes declared explicitly, in reading order?
- Is every subgraph a real boundary?
- Does colour encode exactly one thing, and is it in the legend?
- Direction: `LR` for pipelines and layered flows, `TB` for hierarchies?
- Is the primary path visually straight, with error and secondary paths pushed
  off-axis?
- Any node with more than ~6 edges? That's a hub — consider whether it should be
  split, or whether it's a genuine finding about the system.

## Post-render check

Look at the rendered SVG, not just the source.

- Count crossings. Over target → reorder, don't restyle.
- Any label truncated or overlapping an edge?
- Readable at 100% zoom without scrolling? If a reviewer must zoom out to see it all
  and zoom in to read it, it's too big.
- Does the eye find the entry point within a second? If not, the actor isn't where it
  should be.

If the picture still looks tangled after reordering and grouping, that is usually a
signal about the system rather than the renderer. Say so in "What I'd look at next" —
a diagram that resists layout often means a boundary is in the wrong place.
