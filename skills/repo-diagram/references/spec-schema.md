# Spec field guide

The YAML spec is a renderer-neutral intermediate representation.

Common node fields:
`id, label, display_label, kind, tech, responsibility, stereotype, semantic_role,
members, attributes, confidence, evidence`.

Common relation fields:
`id, from, to, relation, label, protocol, sync, crosses_network, order, condition,
guard, action, cardinality_from, cardinality_to, data, frequency, confidence, evidence`.

Use only fields relevant to the selected type.

Examples of `relation`:
- architecture: calls, routes-to, publishes, consumes, reads, writes;
- class: extends, implements, composes, aggregates, depends-on;
- ER: references, contains;
- state: transitions;
- use case: associates, includes, extends, generalizes;
- deployment: hosts, routes-to, connects-to;
- dataflow: flows.

View metadata chooses profile/renderer/story/focus/suppression. Suppression hides true
facts from one view but never deletes them from a shared model.

Presentation metadata controls appearance only and cannot add architectural facts.
