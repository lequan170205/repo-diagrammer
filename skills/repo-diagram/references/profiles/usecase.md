# Use-case profile

## Semantic contract
Actors are external roles/people/systems, not internal classes. Use cases are user
goals, not routes. Keep a real system boundary. `include` means always-included
behavior; `extend` means optional/conditional extension; generalization requires
genuine specialization. Route evidence does not by itself prove product intent.

## Presentation contract
Actors outside the boundary; primary actors left, supporting actors may sit right.
Group by goal proximity, not controller folder. ≤5 actors and ≤12 use cases. Keep
labels short and verb-first; avoid decorative include/extend webs.

## Renderer
Native Mermaid use-case when Mermaid >=12; otherwise PlantUML. Flowchart fallback is
last resort and must be labelled as use-case-like.

## Blocking
Internal service as actor; endpoint labels as goals; include/extend guessed; actor
permission unsupported; system boundary missing.
