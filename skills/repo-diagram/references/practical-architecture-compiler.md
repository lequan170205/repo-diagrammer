# Practical high-level architecture compiler

This contract exists because **practical** must not mean "strict diagram with shorter
labels". Practical mode is a different **view projection** of the same evidence model.

The full semantic model stays detailed. The canvas is intentionally simplified.

## Core rule

> Preserve evidence in the model; reduce information on the canvas.

A practical high-level overview should normally be understood in 2–5 seconds.

## Two layers

### Model layer — complete

Keep real services, stores, queues, externals and their evidence-backed relations.

Example:

```text
conversation-service
call-service
notification-service
media-service
media-processing-service
RabbitMQ
...
```

### Presentation projection — simplified

The canvas may project several evidenced nodes into one **composite presentation card**.

Example:

```text
Realtime communication
conversation-service · call-service · notification-service
Socket.IO · mediasoup · push
```

The composite is not a new architecture fact. It is a view-only summary whose
`members` point to real model node IDs.

Projected edges also require `basis_edges`: the exact model-edge IDs summarized by
the displayed arrow.

This preserves strict traceability while allowing a clean poster-like overview.

## Practical density targets

For a normal high-level backend overview:

- **6–10 visible regions/nodes** on the main canvas;
- **≤14 visible relationships**;
- one primary reading path;
- no more than 2 avoidable crossings;
- no service-level spider web around the broker;
- no individual database/provider/tool nodes when a grouped presentation card answers
  the high-level question just as well.

If the model has >10 real nodes, a polished practical view should usually use
composites rather than rendering all of them individually.

## What to collapse

Good practical composites:

- realtime communication;
- media pipeline;
- service data layer;
- external integrations;
- observability stack;
- a bounded family of workers that share one responsibility.

Do **not** combine services merely because they are nearby in the repository.

A composite needs:
- at least two real model members;
- a short role/responsibility supported by those members;
- exact member IDs preserved in the label/body or evidence companion;
- no invented runtime boundary.

## Projected relationships

A displayed relationship may summarize one or several real model edges.

Example:

```yaml
- id: ingress_realtime
  from: nginx
  to: realtime
  label: Socket.IO realtime
  protocol: WebSocket
  basis_edges:
    - nginx_to_conversation
    - nginx_to_call
```

Every basis edge must:
- exist in the evidence model;
- preserve direction;
- connect an underlying source member to an underlying target member.

A projected arrow may simplify labels but may not reverse or invent semantics.

## Secondary relations

Practical mode is allowed to **omit secondary edges from the canvas** when they do not
change the high-level mental model.

Examples commonly omitted from the main poster:
- one-off internal RPC;
- telemetry fan-out;
- per-service persistence edges when a grouped data layer is shown;
- detailed worker completion callbacks;
- compatibility/legacy queues.

Those relations remain in the spec/evidence model.

## Poster layout contract

Default regions:

```text
                       Clients
                          │
                       Ingress
                          │
          ┌───────────────┼───────────────┐
          │                               │
      API / REST                  Realtime communication
          │                               │
          └──────────── Messaging ────────┘
                          │
                   Supporting pipeline
                          │

       Data layer          Observability          External integrations
```

Allowed region slots:
- top
- ingress
- core
- messaging
- support
- bottom-left
- bottom-center
- bottom-right
- right

Every visible projection node should appear in exactly one region.

## Renderer fidelity

Preferred renderer for practical high-level architecture is the built-in deterministic
poster renderer:

```bash
python3 scripts/render_practical_architecture.py <spec.yaml> <output.svg> [--png output.png]
```

It reads `presentation.projection` and `layout.regions` directly, so the same
evidence-backed view gets the same poster hierarchy across runs.

For `polished-overview`, any fallback rendering must preserve the planned composition,
not only semantic truth.

A fallback is **rejected** when it loses:
- region placement;
- composite cards;
- primary path;
- left/right external placement;
- grouped data/observability panels;
- acceptable crossing count;
- readable aspect ratio.

A semantically correct raw auto-layout is not an acceptable practical fallback.

## Review question

Ask:

> "Can someone who has never seen this repository identify ingress, core runtime,
> messaging, data, observability and external dependencies in five seconds?"

If not, redraw.
