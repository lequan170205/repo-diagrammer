#!/usr/bin/env python3
"""Validate generated split views against the source evidence spec."""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("SPLIT-VALIDATOR unavailable: install PyYAML")



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


def core_quality(node_ids, source_edges):
    core = set(str(x) for x in node_ids)
    adjacency = {nid: set() for nid in core}
    internal_edges = 0
    boundary_edges = 0
    for edge in source_edges.values():
        a, b = str(edge.get("from")), str(edge.get("to"))
        a_in, b_in = a in core, b in core
        if a_in and b_in:
            internal_edges += 1
            adjacency[a].add(b)
            adjacency[b].add(a)
        elif a_in ^ b_in:
            boundary_edges += 1

    unseen = set(core)
    components = 0
    while unseen:
        components += 1
        start = next(iter(unseen))
        stack = [start]
        unseen.remove(start)
        while stack:
            nid = stack.pop()
            for neighbor in adjacency.get(nid, set()) & unseen:
                unseen.remove(neighbor)
                stack.append(neighbor)

    denominator = internal_edges + boundary_edges
    cohesion = round(internal_edges / denominator, 4) if denominator else 1.0
    return {
        "connected_components": components,
        "internal_edges": internal_edges,
        "boundary_edges": boundary_edges,
        "cohesion": cohesion,
    }


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
    source_groups = [
        g for g in ((source.get("presentation") or {}).get("groups") or [])
        if isinstance(g, dict)
    ]
    source_primary = [str(x) for x in ((source.get("view") or {}).get("primary_path") or [])]
    errors = []

    if manifest.get("stable_ids") is not True:
        errors.append("manifest.stable_ids must be true")
    if manifest.get("invented_architecture_elements") is not False:
        errors.append("manifest.invented_architecture_elements must be false")

    budgets = manifest.get("budgets") or {}
    required_budget_fields = {
        "overview_nodes",
        "detail_core_nodes",
        "detail_context_nodes",
        "detail_total_nodes",
        "integration_nodes",
    }
    if not isinstance(budgets, dict):
        errors.append("manifest.budgets must be a mapping")
        budgets = {}
    else:
        missing_budget_fields = required_budget_fields - set(budgets)
        if missing_budget_fields:
            errors.append(
                f"manifest.budgets missing field(s): {sorted(missing_budget_fields)}"
            )

    density_thresholds = manifest.get("density_thresholds") or {}
    required_density_fields = {"max_nodes", "max_edges", "max_degree"}
    if not isinstance(density_thresholds, dict):
        errors.append("manifest.density_thresholds must be a mapping")
        density_thresholds = {}
    else:
        missing_density_fields = required_density_fields - set(density_thresholds)
        if missing_density_fields:
            errors.append(
                f"manifest.density_thresholds missing field(s): {sorted(missing_density_fields)}"
            )
        for field in sorted(required_density_fields):
            value = density_thresholds.get(field)
            if not isinstance(value, int) or value <= 0:
                errors.append(
                    f"manifest.density_thresholds.{field}: expected positive integer, got {value!r}"
                )

    seen_view_ids = set()
    seen_spec_paths = set()
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
        spec_key = str(spec_rel)
        if spec_key in seen_spec_paths:
            errors.append(f"{vid}: duplicate generated spec path {spec_key!r}")
        seen_spec_paths.add(spec_key)

        spec_path = args.manifest.parent / spec_key
        if not spec_path.exists():
            errors.append(f"{vid}: generated spec missing: {spec_path}")
            continue

        doc = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
        nodes = by_id(doc.get("nodes"))
        edges = by_id(doc.get("edges"))
        boundaries = by_id(doc.get("boundaries"))
        groups = [
            g for g in ((doc.get("presentation") or {}).get("groups") or [])
            if isinstance(g, dict)
        ]

        # Derived views may alter scope/title/layout/view metadata, but immutable
        # source identity and conformance metadata must survive verbatim.
        for field in ("question", "type", "audience", "commit", "conformance",
                      "architecture_description", "gaps"):
            if doc.get(field) != source.get(field):
                errors.append(
                    f"{vid}: immutable source field {field!r} changed during split"
                )

        if view.get("node_count") != len(nodes):
            errors.append(
                f"{vid}: manifest node_count {view.get('node_count')!r} != actual {len(nodes)}"
            )
        if view.get("edge_count") != len(edges):
            errors.append(
                f"{vid}: manifest edge_count {view.get('edge_count')!r} != actual {len(edges)}"
            )
        covered_node_ids.update(nodes)
        covered_edge_ids.update(edges)

        for nid, node in nodes.items():
            original = source_nodes.get(nid)
            if original is None:
                errors.append(f"{vid}: invented node {nid!r}")
                continue
            if node != original:
                errors.append(
                    f"{vid}: node {nid!r} differs from source element; "
                    "split views must reuse source nodes verbatim"
                )

        for eid, edge in edges.items():
            original = source_edges.get(eid)
            if original is None:
                errors.append(f"{vid}: invented edge {eid!r}")
                continue
            if edge != original:
                errors.append(
                    f"{vid}: edge {eid!r} differs from source element; "
                    "split views must reuse source relations verbatim"
                )
            if str(edge.get("from")) not in nodes or str(edge.get("to")) not in nodes:
                errors.append(f"{vid}: edge {eid!r} endpoint missing from generated view")

        for bid, boundary in boundaries.items():
            original = source_boundaries.get(bid)
            if original is None:
                errors.append(f"{vid}: invented boundary {bid!r}")
                continue
            if boundary != original:
                errors.append(
                    f"{vid}: boundary {bid!r} differs from source element; "
                    "real boundaries must be reused verbatim"
                )

        for group in groups:
            if group not in source_groups:
                gid = group.get("id") or group.get("label") or "<unnamed>"
                errors.append(
                    f"{vid}: presentation group {gid!r} was invented or changed during split"
                )

        view_meta = doc.get("view") or {}
        if view_meta.get("split_generated") is not True:
            errors.append(f"{vid}: generated spec missing view.split_generated=true")
        split_kind = str(view_meta.get("split_kind") or "")
        if vid == "overview" and split_kind != "overview":
            errors.append(f"{vid}: expected split_kind='overview', got {split_kind!r}")
        if vid.startswith("integration-") and split_kind != "integration":
            errors.append(f"{vid}: expected split_kind='integration', got {split_kind!r}")
        if vid != "overview" and not vid.startswith("integration-") and split_kind != "detail":
            errors.append(f"{vid}: expected split_kind='detail', got {split_kind!r}")

        node_count = len(nodes)
        if vid == "overview":
            limit = budgets.get("overview_nodes")
            if isinstance(limit, int) and node_count > limit:
                errors.append(
                    f"{vid}: {node_count} nodes exceeds overview budget {limit}"
                )
        elif vid.startswith("integration-"):
            limit = budgets.get("integration_nodes")
            if isinstance(limit, int) and node_count > limit:
                errors.append(
                    f"{vid}: {node_count} nodes exceeds integration budget {limit}"
                )
            integration_core = {str(x) for x in (view.get("core_nodes") or [])}
            quality = core_quality(integration_core, source_edges)
            if len(integration_core) > 1 and quality["connected_components"] != 1:
                errors.append(
                    f"{vid}: integration core is disconnected "
                    f"({quality['connected_components']} components)"
                )
        else:
            total_limit = budgets.get("detail_total_nodes")
            core_limit = budgets.get("detail_core_nodes")
            context_limit = budgets.get("detail_context_nodes")
            if isinstance(total_limit, int) and node_count > total_limit:
                errors.append(
                    f"{vid}: {node_count} nodes exceeds detail total budget {total_limit}"
                )
            core_nodes = {str(x) for x in (view.get("core_nodes") or [])}
            if isinstance(core_limit, int) and len(core_nodes) > core_limit:
                errors.append(
                    f"{vid}: {len(core_nodes)} core nodes exceeds detail core budget {core_limit}"
                )

            expected_quality = core_quality(core_nodes, source_edges)
            declared_quality = view.get("cluster_quality")
            if declared_quality != expected_quality:
                errors.append(
                    f"{vid}: cluster_quality mismatch; "
                    f"expected {expected_quality!r}, got {declared_quality!r}"
                )
            if len(core_nodes) > 1 and expected_quality["connected_components"] != 1:
                errors.append(
                    f"{vid}: detail core is disconnected "
                    f"({expected_quality['connected_components']} components)"
                )
            if not str(view.get("cluster_source") or "").strip():
                errors.append(f"{vid}: missing cluster_source provenance")

            declared_context = {
                str(x) for x in ((doc.get("view") or {}).get("context_nodes") or [])
            }
            if isinstance(context_limit, int) and len(declared_context) > context_limit:
                errors.append(
                    f"{vid}: {len(declared_context)} context nodes exceeds detail context budget {context_limit}"
                )

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

        manifest_core = {str(x) for x in (view.get("core_nodes") or [])}
        if manifest_core != focus:
            errors.append(
                f"{vid}: manifest core_nodes must match generated view.focus; "
                f"{sorted(manifest_core)} != {sorted(focus)}"
            )
        if focus | context != included:
            errors.append(
                f"{vid}: every included node must be classified as focus or context; "
                f"unclassified={sorted(included - (focus | context))}"
            )

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
