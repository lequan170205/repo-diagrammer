#!/usr/bin/env python3
"""Validate generated split views against the source evidence spec."""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("SPLIT-VALIDATOR unavailable: install PyYAML")


NODE_FIELDS = (
    "label", "display_label", "kind", "tech", "responsibility",
    "stereotype", "semantic_role", "confidence",
)
EDGE_FIELDS = (
    "from", "to", "relation", "label", "protocol", "sync", "crosses_network",
    "condition", "guard", "data", "frequency", "confidence",
)
BOUNDARY_FIELDS = ("name", "kind", "contains")


def by_id(items):
    return {
        str(item.get("id")): item
        for item in (items or [])
        if isinstance(item, dict) and item.get("id")
    }


def primary_runs(path, included):
    included = set(included)
    runs = []
    current = []
    for nid in [str(x) for x in (path or [])]:
        if nid in included:
            current.append(nid)
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)
    return runs


def longest_run(runs):
    if not runs:
        return []
    return max(enumerate(runs), key=lambda item: (len(item[1]), -item[0]))[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("manifest", type=Path)
    args = ap.parse_args()

    source = yaml.safe_load(args.source.read_text(encoding="utf-8")) or {}
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8")) or {}

    source_nodes = by_id(source.get("nodes"))
    source_edges = by_id(source.get("edges"))
    source_boundaries = by_id(source.get("boundaries"))
    source_primary = [str(x) for x in ((source.get("view") or {}).get("primary_path") or [])]
    errors = []

    if manifest.get("stable_ids") is not True:
        errors.append("manifest.stable_ids must be true")
    if manifest.get("invented_architecture_elements") is not False:
        errors.append("manifest.invented_architecture_elements must be false")

    seen_view_ids = set()
    covered_node_ids = set()
    covered_edge_ids = set()
    for view in manifest.get("views") or []:
        if not isinstance(view, dict):
            errors.append("manifest contains non-object view")
            continue
        vid = str(view.get("id") or "")
        if not vid:
            errors.append("generated view missing id")
            continue
        if vid in seen_view_ids:
            errors.append(f"duplicate generated view id {vid!r}")
        seen_view_ids.add(vid)

        spec_rel = view.get("spec")
        if not spec_rel:
            errors.append(f"{vid}: missing spec path")
            continue
        spec_path = args.manifest.parent / str(spec_rel)
        if not spec_path.exists():
            errors.append(f"{vid}: generated spec missing: {spec_path}")
            continue

        doc = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        nodes = by_id(doc.get("nodes"))
        edges = by_id(doc.get("edges"))
        boundaries = by_id(doc.get("boundaries"))
        covered_node_ids.update(nodes)
        covered_edge_ids.update(edges)

        for nid, node in nodes.items():
            original = source_nodes.get(nid)
            if original is None:
                errors.append(f"{vid}: invented node {nid!r}")
                continue
            for field in NODE_FIELDS:
                if node.get(field) != original.get(field):
                    errors.append(
                        f"{vid}: node {nid!r} changed {field}: "
                        f"{original.get(field)!r} -> {node.get(field)!r}"
                    )
            if node.get("evidence") != original.get("evidence"):
                errors.append(f"{vid}: node {nid!r} changed evidence")

        for eid, edge in edges.items():
            original = source_edges.get(eid)
            if original is None:
                errors.append(f"{vid}: invented edge {eid!r}")
                continue
            for field in EDGE_FIELDS:
                if edge.get(field) != original.get(field):
                    errors.append(
                        f"{vid}: edge {eid!r} changed {field}: "
                        f"{original.get(field)!r} -> {edge.get(field)!r}"
                    )
            if edge.get("evidence") != original.get("evidence"):
                errors.append(f"{vid}: edge {eid!r} changed evidence")
            if str(edge.get("from")) not in nodes or str(edge.get("to")) not in nodes:
                errors.append(f"{vid}: edge {eid!r} endpoint missing from generated view")

        for bid, boundary in boundaries.items():
            original = source_boundaries.get(bid)
            if original is None:
                errors.append(f"{vid}: invented boundary {bid!r}")
                continue
            for field in BOUNDARY_FIELDS:
                left = boundary.get(field)
                right = original.get(field)
                if field == "contains":
                    left = [str(x) for x in (left or [])]
                    right = [str(x) for x in (right or [])]
                if left != right:
                    errors.append(
                        f"{vid}: boundary {bid!r} changed {field}: {right!r} -> {left!r}"
                    )
            if boundary.get("evidence") != original.get("evidence"):
                errors.append(f"{vid}: boundary {bid!r} changed evidence")

        view_meta = doc.get("view") or {}
        included = set(nodes)
        context = {str(x) for x in (view_meta.get("context_nodes") or [])}
        focus = {str(x) for x in (view_meta.get("focus") or [])}
        suppressed = {str(x) for x in (view_meta.get("suppress") or [])}

        if not context <= included:
            errors.append(f"{vid}: context_nodes contains omitted IDs")
        if not focus <= included:
            errors.append(f"{vid}: focus contains omitted IDs")
        if context & focus:
            errors.append(f"{vid}: node cannot be both focus and context")

        expected_runs_all = primary_runs(source_primary, included)
        expected_primary_paths = [run for run in expected_runs_all if len(run) >= 2]
        expected_primary = longest_run(expected_runs_all)
        actual_primary_paths = [
            [str(x) for x in run]
            for run in (view_meta.get("primary_paths") or [])
            if isinstance(run, list)
        ]
        actual_primary = [str(x) for x in (view_meta.get("primary_path") or [])]
        if actual_primary_paths != expected_primary_paths:
            errors.append(
                f"{vid}: primary_paths broke source continuity; expected "
                f"{expected_primary_paths}, got {actual_primary_paths}"
            )
        if actual_primary != expected_primary:
            errors.append(
                f"{vid}: primary_path must be longest contiguous source run; "
                f"expected {expected_primary}, got {actual_primary}"
            )

        expected_suppressed = set(source_nodes) - included
        if suppressed != expected_suppressed:
            errors.append(
                f"{vid}: suppress set mismatch; expected {sorted(expected_suppressed)}, "
                f"got {sorted(suppressed)}"
            )

        coverage_edges = {str(x) for x in (view.get("coverage_edges") or [])}
        spec_coverage_edges = {str(x) for x in (view_meta.get("coverage_edges") or [])}
        if coverage_edges != spec_coverage_edges:
            errors.append(
                f"{vid}: manifest/spec coverage_edges mismatch; "
                f"{sorted(coverage_edges)} != {sorted(spec_coverage_edges)}"
            )
        for eid in coverage_edges:
            if eid not in source_edges:
                errors.append(f"{vid}: coverage_edges references unknown source edge {eid!r}")
            elif eid not in edges:
                errors.append(f"{vid}: coverage edge {eid!r} missing from generated view")

    missing_nodes = set(source_nodes) - covered_node_ids
    missing_edges = set(source_edges) - covered_edge_ids
    if missing_nodes:
        errors.append(f"split set omits source node(s): {sorted(missing_nodes)}")
    if missing_edges:
        errors.append(f"split set omits source edge(s): {sorted(missing_edges)}")

    coverage = manifest.get("coverage") or {}
    expected_coverage = {
        "nodes_total": len(source_nodes),
        "nodes_covered": len(set(source_nodes) & covered_node_ids),
        "edges_total": len(source_edges),
        "edges_covered": len(set(source_edges) & covered_edge_ids),
        "missing_nodes": sorted(missing_nodes),
        "missing_edges": sorted(missing_edges),
    }
    for field, expected in expected_coverage.items():
        if coverage.get(field) != expected:
            errors.append(
                f"manifest.coverage.{field}: expected {expected!r}, got {coverage.get(field)!r}"
            )

    print(
        f"SPLIT CHECK: {len(manifest.get('views') or [])} generated view(s), "
        f"{len(source_nodes)} source node(s), {len(source_edges)} source edge(s); "
        f"coverage={len(covered_node_ids & set(source_nodes))}/{len(source_nodes)} nodes, "
        f"{len(covered_edge_ids & set(source_edges))}/{len(source_edges)} edges"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"SPLIT INVALID: {len(errors)} error(s)")
        return 1

    print("SPLIT VALID: stable IDs, source semantics, and full node/edge coverage preserved across generated views")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
