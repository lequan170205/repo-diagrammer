# Architecture profile

## Semantic contract
- One C4 abstraction level per static view.
- Context: people + software systems; no low-level technology noise.
- Container: separately running applications/data stores + direct external systems.
- Component: one container's components + immediate collaborators.
- Dynamic: one runtime story using elements from the static model.
- Every relationship is unidirectional and labelled with intent.
- Inter-process relations include protocol/technology when evidenced.
- Real boundaries require evidence.

## Presentation contract
- Title states type + scope; legend explains non-obvious notation.
- Context: system-in-focus visually dominant, externals peripheral.
- Container/high-level: use polished overview hierarchy when applicable.
- Component: container boundary obvious; externals outside.
- Short responsibility text, no paragraphs in boxes.
- Names remain identical across architecture views.

## Renderer
Mermaid flowchart + ELK preferred. Use PlantUML when UML/C4-PlantUML is explicitly
needed. High-level views also load `high-level-architecture-style.md`.

## Blocking
Mixed abstraction; unlabelled relationship; missing inter-process protocol; false
boundary; cross-view renaming; static/runtime/deployment concerns crammed into one view.
