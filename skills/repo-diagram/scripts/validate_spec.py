#!/usr/bin/env python3
"""Validate Repo Diagrammer's evidence IR before rendering."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("SPEC-VALIDATOR unavailable: install PyYAML (python3 -m pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)

if len(sys.argv) != 2:
    print("usage: validate_spec.py <diagram.spec.yaml>", file=sys.stderr)
    raise SystemExit(2)

path = Path(sys.argv[1])
try:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"SPEC INVALID: cannot parse YAML: {exc}", file=sys.stderr)
    raise SystemExit(1)

if not isinstance(doc, dict):
    print("SPEC INVALID: root must be a mapping", file=sys.stderr)
    raise SystemExit(1)

errors: list[str] = []
warnings: list[str] = []

def nonempty(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(nonempty(v) for v in value)
    return value is not None and value != ""

def mapping_list(name: str):
    value = doc.get(name, [])
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{name}: must be a list")
        return []
    return value

nodes = mapping_list("nodes")
edges = mapping_list("edges")
boundaries = mapping_list("boundaries")
gaps = doc.get("gaps") or []
view = doc.get("view") or {}
presentation = doc.get("presentation") or {}

node_ids: set[str] = set()
for i, node in enumerate(nodes):
    prefix = f"nodes[{i}]"
    if not isinstance(node, dict):
        errors.append(f"{prefix}: must be a mapping")
        continue
    node_id = str(node.get("id") or "").strip()
    if not node_id:
        errors.append(f"{prefix}.id: required")
        continue
    if node_id in node_ids:
        errors.append(f"{prefix}.id: duplicate id {node_id!r}")
    node_ids.add(node_id)
    if not nonempty(node.get("label")):
        errors.append(f"{prefix}.label: required")
    if not nonempty(node.get("evidence")):
        errors.append(f"{prefix}.evidence: No evidence, no element")

edge_ids: set[str] = set()
partial = []
for i, edge in enumerate(edges):
    prefix = f"edges[{i}]"
    if not isinstance(edge, dict):
        errors.append(f"{prefix}: must be a mapping")
        continue
    edge_id = str(edge.get("id") or "").strip()
    if not edge_id:
        errors.append(f"{prefix}.id: required")
    elif edge_id in edge_ids:
        errors.append(f"{prefix}.id: duplicate id {edge_id!r}")
    else:
        edge_ids.add(edge_id)
    src, dst = edge.get("from"), edge.get("to")
    if src not in node_ids:
        errors.append(f"{prefix}.from: unknown node {src!r}")
    if dst not in node_ids:
        errors.append(f"{prefix}.to: unknown node {dst!r}")
    if not nonempty(edge.get("relation")):
        errors.append(f"{prefix}.relation: required renderer-neutral semantic")
    if not nonempty(edge.get("evidence")):
        errors.append(f"{prefix}.evidence: No evidence, no relation")
    if edge.get("confidence") == "partial":
        partial.append(prefix)

boundary_ids: set[str] = set()
for i, boundary in enumerate(boundaries):
    prefix = f"boundaries[{i}]"
    if not isinstance(boundary, dict):
        errors.append(f"{prefix}: must be a mapping")
        continue
    bid = str(boundary.get("id") or "").strip()
    if not bid:
        errors.append(f"{prefix}.id: required")
    elif bid in boundary_ids:
        errors.append(f"{prefix}.id: duplicate id {bid!r}")
    else:
        boundary_ids.add(bid)
    if not nonempty(boundary.get("evidence")):
        errors.append(f"{prefix}.evidence: real boundary requires evidence")
    for member in boundary.get("contains") or []:
        if member not in node_ids:
            errors.append(f"{prefix}.contains: unknown node {member!r}")

groups = presentation.get("groups") or []
group_ids: set[str] = set()
if not isinstance(groups, list):
    errors.append("presentation.groups: must be a list")
    groups = []
for i, group in enumerate(groups):
    prefix = f"presentation.groups[{i}]"
    if not isinstance(group, dict):
        errors.append(f"{prefix}: must be a mapping")
        continue
    gid = str(group.get("id") or "").strip()
    if gid:
        if gid in node_ids:
            errors.append(f"{prefix}.id: presentation group collides with real node {gid!r}")
        if gid in group_ids:
            errors.append(f"{prefix}.id: duplicate presentation group {gid!r}")
        group_ids.add(gid)
    for member in group.get("contains") or []:
        if member not in node_ids:
            errors.append(f"{prefix}.contains: unknown real node {member!r}")

# Type/profile consistency.
diagram_type = str(doc.get("type") or "").strip()
profile_for = {
    "c4-landscape": "architecture",
    "c4-context": "architecture",
    "c4-container": "architecture",
    "c4-component": "architecture",
    "c4-dynamic": "architecture",
    "sequence": "sequence",
    "class": "class",
    "er": "er",
    "state": "state",
    "dataflow": "dataflow",
    "deployment": "deployment",
    "callgraph": "callgraph",
    "usecase": "usecase",
    "flowchart": "flowchart",
    "swimlane": "flowchart",
}
expected_profile = profile_for.get(diagram_type)
if not expected_profile:
    errors.append(f"type: unsupported or missing diagram type {diagram_type!r}")
elif view.get("profile") != expected_profile:
    errors.append(
        f"view.profile: expected {expected_profile!r} for type {diagram_type!r}, "
        f"got {view.get('profile')!r}"
    )

if view.get("renderer", "auto") not in {"auto", "mermaid", "plantuml", "graphviz"}:
    errors.append(f"view.renderer: unsupported {view.get('renderer')!r}")
if view.get("fallback_renderer", "auto") not in {"auto", "mermaid", "plantuml", "graphviz"}:
    errors.append(f"view.fallback_renderer: unsupported {view.get('fallback_renderer')!r}")

relations = [e.get("relation") for e in edges if isinstance(e, dict)]
if diagram_type == "class":
    allowed = {"extends", "implements", "composes", "aggregates", "associates", "depends-on"}
    for i, rel in enumerate(relations):
        if rel not in allowed:
            errors.append(f"edges[{i}].relation: {rel!r} is not a class relation")
elif diagram_type == "er":
    for i, edge in enumerate(edges):
        if not nonempty(edge.get("cardinality_from")) or not nonempty(edge.get("cardinality_to")):
            errors.append(f"edges[{i}]: ER relation requires cardinality_from and cardinality_to")
elif diagram_type == "state":
    for i, edge in enumerate(edges):
        if edge.get("relation") != "transitions":
            errors.append(f"edges[{i}].relation: state edges must be 'transitions'")
        if not nonempty(edge.get("label")):
            errors.append(f"edges[{i}].label: state transition requires a trigger")
elif diagram_type in {"sequence", "c4-dynamic"}:
    orders = []
    for i, edge in enumerate(edges):
        order = edge.get("order")
        if not isinstance(order, int):
            errors.append(f"edges[{i}].order: runtime-ordered view requires integer order")
        else:
            orders.append(order)
    if len(orders) != len(set(orders)):
        errors.append("edges.order: duplicate message order")
elif diagram_type == "dataflow":
    for i, edge in enumerate(edges):
        if edge.get("relation") == "flows" and not nonempty(edge.get("data")):
            errors.append(f"edges[{i}].data: dataflow edge must name its dataset/event")
elif diagram_type == "usecase":
    allowed = {"associates", "includes", "extends", "generalizes"}
    for i, edge in enumerate(edges):
        if edge.get("relation") not in allowed:
            errors.append(f"edges[{i}].relation: invalid use-case relation {edge.get('relation')!r}")

for i, edge in enumerate(edges):
    if edge.get("crosses_network") and not nonempty(edge.get("protocol")):
        errors.append(f"edges[{i}].protocol: network edge requires protocol")

if partial and not nonempty(gaps):
    errors.append("gaps: partial-confidence facts exist but uncertainty is not disclosed")

print(
    f"SPEC CHECK: {path.name} — {len(nodes)} nodes, {len(edges)} relations, "
    f"{len(boundaries)} boundaries"
)
for warning in warnings:
    print(f"WARNING: {warning}")
if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"SPEC INVALID: {len(errors)} error(s)", file=sys.stderr)
    raise SystemExit(1)

print("SPEC VALID: evidence and structural invariants passed")
