# Sequence profile

## Semantic contract
- One named scenario per diagram.
- Start from a real entrypoint and trace execution order.
- Participants are real runtime actors/containers/components.
- Sync and async messages are visually distinct.
- Show broker/queue as participant when it creates the async boundary.
- `alt/opt/loop/par/break` only when code supports the control flow.
- Returns only when they matter.
- Error scenario becomes a separate diagram when it buries the happy path.

## Presentation contract
Caller/actor left; downstream systems progress right. ≤8 participants and ≤25
meaningful messages. Labels are verbs/actions, not DTO dumps. Use phase dividers for
long flows. Keep colour restrained; time is the primary visual channel.

## Renderer
Mermaid for simple flows; PlantUML for several nested fragments, complex activation,
or UML-heavy styling.

## Blocking
Invented message; async drawn blocking; meaningful broker omitted; branch without
condition evidence; participant ordering causes constant backtracking; multiple
scenarios collapsed into one timeline.
