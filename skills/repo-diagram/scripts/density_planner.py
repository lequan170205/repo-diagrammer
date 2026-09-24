#!/usr/bin/env python3
"""Density analysis and semantics-preserving view splitting for architecture specs.

The planner never invents architecture elements. Every generated view reuses original
node/edge IDs and evidence. Overview views omit detail; detail views may include a
small number of real one-hop context nodes so cross-cluster relations remain legible.
"""
from __future__ import annotations

import argparse
import copy
import re
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit("DENSITY-PLANNER unavailable: install PyYAML")

DEFAULT_MAX_NODES = 20
DEFAULT_MAX_EDGES = 32
DEFAULT_MAX_DEGREE = 9
DEFAULT_DETAIL_NODES = 12
DEFAULT_OVERVIEW_NODES = 12
DEFAULT_CONTEXT_NODES = 3


def _nodes(doc):
    return [n for n in (doc.get("nodes") or []) if isinstance(n, dict) and n.get("id")]


def _edges(doc):
    return [
        e for e in (doc.get("edges") or [])
        if isinstance(e, dict) and e.get("from") and e.get("to")
    ]


def graph_data(doc):
    nodes = _nodes(doc)
    ids = {str(n["id"]) for n in nodes}
    edges = [e for e in _edges(doc) if str(e["from"]) in ids and str(e["to"]) in ids]
    adjacency = {nid: set() for nid in ids}
    degree = {nid: 0 for nid in ids}
    for edge in edges:
        a, b = str(edge["from"]), str(edge["to"])
        adjacency[a].add(b)
        adjacency[b].add(a)
        degree[a] += 1
        degree[b] += 1
    return nodes, edges, adjacency, degree


def density_metrics(doc):
    nodes, edges, _, degree = graph_data(doc)
    n = len(nodes)
    e = len(edges)
    max_degree = max(degree.values(), default=0)
    edge_ratio = e / max(n, 1)
    possible = max(n * (n - 1) / 2, 1)
    graph_density = e / possible
    return {
        "nodes": n,
        "edges": e,
        "max_degree": max_degree,
        "edges_per_node": round(edge_ratio, 3),
        "graph_density": round(graph_density, 4),
    }


def split_reasons(
    doc,
    max_nodes=DEFAULT_MAX_NODES,
    max_edges=DEFAULT_MAX_EDGES,
    max_degree=DEFAULT_MAX_DEGREE,
):
    m = density_metrics(doc)
    reasons = []
    if m["nodes"] > max_nodes:
        reasons.append(f"nodes {m['nodes']} > {max_nodes}")
    if m["edges"] > max_edges and m["nodes"] > 10:
        reasons.append(f"edges {m['edges']} > {max_edges}")
    if m["max_degree"] > max_degree and m["nodes"] > 12:
        reasons.append(f"max degree {m['max_degree']} > {max_degree}")
    return reasons


def should_split(doc, **kwargs):
    reasons = split_reasons(doc, **kwargs)
    return bool(reasons), reasons, density_metrics(doc)


def slugify(value):
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip()).strip("-").lower()
    return text or "view"


def _seed_clusters(doc):
    """Return non-overlapping semantic/presentation seeds, strongest first."""
    ids = {str(n["id"]) for n in _nodes(doc)}
    assigned = set()
    clusters = []

    # Evidence-backed boundaries have first priority.
    for boundary in doc.get("boundaries") or []:
        if not isinstance(boundary, dict):
            continue
        members = [str(x) for x in (boundary.get("contains") or []) if str(x) in ids]
        available = [x for x in members if x not in assigned]
        if len(available) >= 2:
            label = boundary.get("name") or boundary.get("id") or "Boundary"
            clusters.append({"label": str(label), "members": available, "source": "boundary"})
            assigned.update(available)

    # Presentation groups are useful only for nodes not already owned by a real boundary.
    for group in ((doc.get("presentation") or {}).get("groups") or []):
        if not isinstance(group, dict):
            continue
        members = [str(x) for x in (group.get("contains") or []) if str(x) in ids]
        available = [x for x in members if x not in assigned]
        if len(available) >= 2:
            label = group.get("label") or group.get("name") or group.get("id") or "Group"
            clusters.append({"label": str(label), "members": available, "source": "group"})
            assigned.update(available)

    # Remaining nodes use semantic roles, which preserves the renderer's layer vocabulary.
    by_role = defaultdict(list)
    for node in _nodes(doc):
        nid = str(node["id"])
        if nid in assigned:
            continue
        role = str(node.get("semantic_role") or node.get("kind") or "domain")
        by_role[role].append(nid)
    for role in sorted(by_role):
        members = by_role[role]
        clusters.append({
            "label": role.replace("-", " ").title(),
            "members": members,
            "source": "semantic-role",
        })
        assigned.update(members)

    return clusters


def _connected_components(members, adjacency):
    """Return deterministic connected components inside one semantic seed."""
    allowed = set(members)
    unseen = set(members)
    components = []
    while unseen:
        start = min(unseen)
        stack = [start]
        unseen.remove(start)
        component = []
        while stack:
            nid = stack.pop()
            component.append(nid)
            neighbors = sorted(
                (adjacency.get(nid, set()) & allowed) & unseen,
                reverse=True,
            )
            for neighbor in neighbors:
                unseen.remove(neighbor)
                stack.append(neighbor)
        components.append(sorted(component))
    components.sort(key=lambda xs: (-len(xs), xs[0] if xs else ""))
    return components


def _split_connected_component(members, adjacency, degree, max_size):
    remaining = set(members)
    chunks = []
    member_set = set(members)
    while remaining:
        seed = max(remaining, key=lambda x: (degree.get(x, 0), x))
        chunk = [seed]
        remaining.remove(seed)
        frontier = set(adjacency.get(seed, set())) & remaining
        while remaining and len(chunk) < max_size:
            candidates = frontier or {
                nid for nid in remaining
                if any(x in adjacency.get(nid, set()) for x in chunk)
            }
            if not candidates:
                break

            def affinity(nid):
                links = sum(1 for x in chunk if x in adjacency.get(nid, set()))
                component_degree = sum(
                    1 for x in adjacency.get(nid, set()) if x in member_set
                )
                return (links, component_degree, degree.get(nid, 0), nid)

            candidate = max(candidates, key=affinity)
            chunk.append(candidate)
            remaining.remove(candidate)
            frontier.discard(candidate)
            frontier.update(adjacency.get(candidate, set()) & remaining)
        chunks.append(sorted(chunk))
    return chunks


def _split_members(members, adjacency, degree, max_size):
    """Split a seed without mixing disconnected graph components."""
    chunks = []
    for component in _connected_components(members, adjacency):
        chunks.extend(
            _split_connected_component(component, adjacency, degree, max_size)
        )
    return chunks


def _cross_edges(a, b, edge_pairs):
    aa, bb = set(a), set(b)
    return sum(1 for x, y in edge_pairs if (x in aa and y in bb) or (x in bb and y in aa))


def build_clusters(doc, max_detail_nodes=DEFAULT_DETAIL_NODES):
    nodes, edges, adjacency, degree = graph_data(doc)
    seeds = _seed_clusters(doc)
    expanded = []
    for seed in seeds:
        parts = _split_members(seed["members"], adjacency, degree, max_detail_nodes)
        for idx, members in enumerate(parts, start=1):
            suffix = f" {idx}" if len(parts) > 1 else ""
            expanded.append({
                "label": seed["label"] + suffix,
                "members": members,
                "source": seed["source"],
            })

    # Merge tiny fragments when they have a strong connection to another cluster.
    edge_pairs = [(str(e["from"]), str(e["to"])) for e in edges]
    changed = True
    while changed:
        changed = False
        for i, cluster in enumerate(list(expanded)):
            if len(cluster["members"]) >= 3 or len(expanded) <= 1:
                continue
            candidates = []
            for j, other in enumerate(expanded):
                if i == j:
                    continue
                if len(cluster["members"]) + len(other["members"]) > max_detail_nodes:
                    continue
                candidates.append((
                    _cross_edges(cluster["members"], other["members"], edge_pairs),
                    -len(other["members"]),
                    j,
                ))
            if candidates:
                cross_edges, _, j = max(candidates)
                if cross_edges <= 0 or j == i:
                    continue
                target = expanded[j]
                target["members"].extend(cluster["members"])
                target["members"] = sorted(set(target["members"]))
                target["source"] = (
                    target["source"]
                    if target["source"] == cluster["source"]
                    else "graph-connected-merge"
                )
                expanded.pop(i)
                changed = True
                break

    # Stable deterministic ordering: primary-path cluster first, then size, then label.
    primary = [str(x) for x in ((doc.get("view") or {}).get("primary_path") or [])]
    primary_set = set(primary)
    expanded.sort(
        key=lambda c: (
            -sum(1 for x in c["members"] if x in primary_set),
            -len(c["members"]),
            c["label"].lower(),
        )
    )
    for idx, cluster in enumerate(expanded, start=1):
        cluster["id"] = f"view-{idx:02d}-{slugify(cluster['label'])}"
        members = set(cluster["members"])
        internal_edges = sum(
            1 for edge in edges
            if str(edge["from"]) in members and str(edge["to"]) in members
        )
        boundary_edges = sum(
            1 for edge in edges
            if (str(edge["from"]) in members) ^ (str(edge["to"]) in members)
        )
        components = _connected_components(cluster["members"], adjacency)
        denominator = internal_edges + boundary_edges
        cluster["quality"] = {
            "connected_components": len(components),
            "internal_edges": internal_edges,
            "boundary_edges": boundary_edges,
            "cohesion": round(internal_edges / denominator, 4) if denominator else 1.0,
        }
    return expanded


def _overview_ids(doc, clusters, limit=DEFAULT_OVERVIEW_NODES):
    nodes, edges, _, degree = graph_data(doc)
    all_ids = {str(n["id"]) for n in nodes}
    primary = [str(x) for x in ((doc.get("view") or {}).get("primary_path") or []) if str(x) in all_ids]
    focus = [str(x) for x in ((doc.get("view") or {}).get("focus") or []) if str(x) in all_ids]

    chosen = []
    def add(nid):
        if nid in all_ids and nid not in chosen and len(chosen) < limit:
            chosen.append(nid)

    # Preserve the user's explicit story first.
    for nid in primary:
        add(nid)
    for nid in focus:
        add(nid)

    # One representative per cluster prevents the overview from hiding a whole subsystem.
    for cluster in clusters:
        if len(chosen) >= limit:
            break
        member = max(
            cluster["members"],
            key=lambda x: (degree.get(x, 0), x),
        )
        add(member)

    # Fill remaining slots with high-degree real nodes.
    for nid in sorted(all_ids, key=lambda x: (-degree.get(x, 0), x)):
        add(nid)
    return chosen


def _filter_regions(regions, included):
    out = []
    included = set(included)
    for region in regions or []:
        if not isinstance(region, dict):
            continue
        members = {str(x) for x in (region.get("contains") or [])}
        # Real/presentation regions are shown only when their complete membership is visible.
        if members and members <= included:
            out.append(copy.deepcopy(region))
    return out


def _filter_rows(rows, included):
    included = set(included)
    out = []
    for row in rows or []:
        if isinstance(row, dict):
            clone = copy.deepcopy(row)
            key = "nodes" if "nodes" in clone else "contains"
            members = [str(x) for x in (clone.get(key) or []) if str(x) in included]
            if members:
                clone[key] = members
                out.append(clone)
        elif isinstance(row, list):
            members = [str(x) for x in row if str(x) in included]
            if members:
                out.append(members)
    return out


def _prune_overview_edges(doc, spec):
    """Keep a sparse real-edge backbone for overview readability.

    The full split set still preserves every relation; the overview is a story/navigation
    view, not a compressed copy of all source relations.
    """
    included = {str(n["id"]) for n in (spec.get("nodes") or []) if isinstance(n, dict) and n.get("id")}
    edges = [
        copy.deepcopy(e) for e in (spec.get("edges") or [])
        if isinstance(e, dict) and e.get("id")
    ]
    if len(edges) <= max(8, len(included) - 1):
        return edges, []

    primary = [
        str(x) for x in ((doc.get("view") or {}).get("primary_path") or [])
        if str(x) in included
    ]
    primary_pairs = set(zip(primary, primary[1:]))
    required_ids = {
        str(e["id"]) for e in edges
        if (str(e.get("from")), str(e.get("to"))) in primary_pairs
    }

    parent = {nid: nid for nid in included}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    kept = []
    kept_ids = set()
    by_id = {str(e["id"]): e for e in edges}

    # Primary story edges are mandatory and seed the connectivity forest.
    for eid in sorted(required_ids):
        edge = by_id[eid]
        kept.append(edge)
        kept_ids.add(eid)
        union(str(edge["from"]), str(edge["to"]))

    node_by_id = {
        str(n["id"]): n for n in (doc.get("nodes") or [])
        if isinstance(n, dict) and n.get("id")
    }

    def role(nid):
        n = node_by_id.get(nid) or {}
        return str(n.get("semantic_role") or n.get("kind") or "domain")

    role_order = {
        name: idx for idx, name in enumerate(
            ["clients", "ingress", "api", "realtime", "messaging",
             "processing", "domain", "data", "observability", "external"]
        )
    }

    def edge_score(edge):
        a, b = str(edge["from"]), str(edge["to"])
        ra = role_order.get(role(a), 50)
        rb = role_order.get(role(b), 50)
        role_jump = abs(ra-rb)
        primary_touch = int(a in primary or b in primary)
        return (-primary_touch, role_jump, str(edge["id"]))

    # Add only real edges needed to connect as much of the overview as possible.
    for edge in sorted(edges, key=edge_score):
        eid = str(edge["id"])
        if eid in kept_ids:
            continue
        a, b = str(edge["from"]), str(edge["to"])
        if union(a, b):
            kept.append(edge)
            kept_ids.add(eid)

    omitted = sorted(str(e["id"]) for e in edges if str(e["id"]) not in kept_ids)
    return kept, omitted


def _primary_runs(path, included):
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


def _longest_primary_run(runs):
    if not runs:
        return []
    # Stable tie-breaker: first run in source order wins.
    return max(enumerate(runs), key=lambda item: (len(item[1]), -item[0]))[1]


def make_view(doc, core_ids, label, context_limit=DEFAULT_CONTEXT_NODES, overview=False, split_kind=None):
    core = set(str(x) for x in core_ids)
    nodes, edges, adjacency, degree = graph_data(doc)
    all_ids = {str(n["id"]) for n in nodes}

    context = []
    if not overview and context_limit > 0:
        scores = defaultdict(int)
        for edge in edges:
            a, b = str(edge["from"]), str(edge["to"])
            if a in core and b not in core:
                scores[b] += 1
            elif b in core and a not in core:
                scores[a] += 1
        for nid in sorted(scores, key=lambda x: (-scores[x], -degree.get(x, 0), x)):
            if nid in all_ids and len(context) < context_limit:
                context.append(nid)

    included = core | set(context)
    clone = copy.deepcopy(doc)
    clone["nodes"] = [n for n in nodes if str(n["id"]) in included]
    clone["edges"] = [
        copy.deepcopy(e) for e in edges
        if str(e["from"]) in included and str(e["to"]) in included
    ]
    overview_omitted_edges = []
    if overview:
        clone["edges"], overview_omitted_edges = _prune_overview_edges(doc, clone)
    clone["boundaries"] = _filter_regions(doc.get("boundaries"), included)

    presentation = copy.deepcopy(doc.get("presentation") or {})
    presentation["groups"] = _filter_regions(presentation.get("groups"), included)
    base_title = presentation.get("title") or "Architecture"
    presentation["title"] = f"{base_title} — {label}"
    clone["presentation"] = presentation

    layout = copy.deepcopy(doc.get("layout") or {})
    layout["rows"] = _filter_rows(layout.get("rows"), included)
    clone["layout"] = layout

    view = copy.deepcopy(doc.get("view") or {})
    source_primary = [str(x) for x in (view.get("primary_path") or [])]
    primary_runs = _primary_runs(source_primary, included)
    view["primary_paths"] = [run for run in primary_runs if len(run) >= 2]
    view["primary_path"] = _longest_primary_run(primary_runs)
    view["focus"] = sorted(core)
    view["context_nodes"] = context
    view["suppress"] = sorted(all_ids - included)
    view["split_generated"] = True
    view["split_kind"] = split_kind or ("overview" if overview else "detail")
    view["suppressed_edges"] = overview_omitted_edges if overview else []
    clone["view"] = view

    clone["scope"] = f"{doc.get('scope') or 'architecture'} / {label}"
    return clone


def _edge_ids_in_views(views):
    covered = set()
    for view in views:
        for edge in view["spec"].get("edges") or []:
            if isinstance(edge, dict) and edge.get("id"):
                covered.add(str(edge["id"]))
    return covered


def _integration_batches(doc, uncovered_edge_ids, max_nodes):
    """Group uncovered edges into bounded connected interaction views.

    Disconnected edge pairs are deliberately not packed together: doing so often
    creates avoidable crossings in a view whose only job is preserving relation
    coverage. Connected stars/chains may share a view while they fit the node budget.
    """
    remaining = [
        e for e in _edges(doc)
        if str(e.get("id")) in uncovered_edge_ids
    ]
    batches = []

    while remaining:
        seed = remaining.pop(0)
        current_edges = [seed]
        current_nodes = {str(seed["from"]), str(seed["to"])}

        changed = True
        while changed:
            changed = False
            for edge in list(remaining):
                endpoints = {str(edge["from"]), str(edge["to"])}
                if not (endpoints & current_nodes):
                    continue
                if len(current_nodes | endpoints) > max_nodes:
                    continue
                current_edges.append(edge)
                current_nodes.update(endpoints)
                remaining.remove(edge)
                changed = True

        batches.append({
            "edge_ids": [str(e["id"]) for e in current_edges],
            "nodes": sorted(current_nodes),
        })

    return batches


def plan_views(
    doc,
    max_detail_nodes=DEFAULT_DETAIL_NODES,
    overview_nodes=DEFAULT_OVERVIEW_NODES,
    context_nodes=DEFAULT_CONTEXT_NODES,
):
    clusters = build_clusters(doc, max_detail_nodes=max_detail_nodes)
    overview_ids = _overview_ids(doc, clusters, limit=overview_nodes)
    views = [{
        "id": "overview",
        "label": "Overview",
        "core": overview_ids,
        "spec": make_view(doc, overview_ids, "Overview", context_limit=0, overview=True),
    }]
    for cluster in clusters:
        views.append({
            "id": cluster["id"],
            "label": cluster["label"],
            "core": list(cluster["members"]),
            "cluster_source": cluster.get("source"),
            "cluster_quality": copy.deepcopy(cluster.get("quality") or {}),
            "spec": make_view(
                doc,
                cluster["members"],
                cluster["label"],
                context_limit=context_nodes,
                overview=False,
            ),
        })

    # Bounded context is intentionally lossy for a single detail view, but the whole
    # generated set must never lose a source relation. Add real-node integration views
    # for any edge that is still not represented anywhere.
    source_edge_ids = {
        str(e["id"]) for e in _edges(doc)
        if e.get("id")
    }
    covered = _edge_ids_in_views(views)
    uncovered = source_edge_ids - covered
    for idx, batch in enumerate(
        _integration_batches(doc, uncovered, max_detail_nodes),
        start=1,
    ):
        label = f"Cross-cluster interactions {idx}"
        view_id = f"integration-{idx:02d}"
        spec = make_view(
            doc,
            batch["nodes"],
            label,
            context_limit=0,
            overview=False,
            split_kind="integration",
        )
        # Keep only relations needed to guarantee uncovered-edge coverage plus any
        # directly connecting relations between the same endpoints.
        required = set(batch["edge_ids"])
        spec["view"]["coverage_edges"] = sorted(required)
        views.append({
            "id": view_id,
            "label": label,
            "core": list(batch["nodes"]),
            "coverage_edges": sorted(required),
            "spec": spec,
        })

    return views


def write_plan(spec_path, outdir, force=False, max_nodes=DEFAULT_MAX_NODES,
               max_edges=DEFAULT_MAX_EDGES, max_degree=DEFAULT_MAX_DEGREE,
               max_detail_nodes=DEFAULT_DETAIL_NODES,
               overview_nodes=DEFAULT_OVERVIEW_NODES,
               context_nodes=DEFAULT_CONTEXT_NODES):
    doc = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8")) or {}
    needs_split, reasons, metrics = should_split(
        doc,
        max_nodes=max_nodes,
        max_edges=max_edges,
        max_degree=max_degree,
    )
    if not needs_split and not force:
        return {"split": False, "reasons": reasons, "metrics": metrics, "views": []}

    views = plan_views(
        doc,
        max_detail_nodes=max_detail_nodes,
        overview_nodes=overview_nodes,
        context_nodes=context_nodes,
    )
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_views = []
    for view in views:
        filename = f"{slugify(view['id'])}.spec.yaml"
        path = outdir / filename
        path.write_text(
            yaml.safe_dump(view["spec"], sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        manifest_entry = {
            "id": view["id"],
            "label": view["label"],
            "spec": filename,
            "core_nodes": view["core"],
            "coverage_edges": view.get("coverage_edges", []),
            "node_count": len(view["spec"].get("nodes") or []),
            "edge_count": len(view["spec"].get("edges") or []),
        }
        if view.get("cluster_source"):
            manifest_entry["cluster_source"] = view["cluster_source"]
        if view.get("cluster_quality"):
            manifest_entry["cluster_quality"] = copy.deepcopy(view["cluster_quality"])
        manifest_views.append(manifest_entry)

    covered_nodes = {
        str(node.get("id"))
        for view in views
        for node in (view["spec"].get("nodes") or [])
        if isinstance(node, dict) and node.get("id")
    }
    covered_edges = _edge_ids_in_views(views)
    source_node_ids = {str(n["id"]) for n in _nodes(doc)}
    source_edge_ids = {str(e["id"]) for e in _edges(doc) if e.get("id")}
    manifest = {
        "source_spec": str(Path(spec_path)),
        "split_trigger": reasons or ["forced"],
        "source_metrics": metrics,
        "stable_ids": True,
        "invented_architecture_elements": False,
        "density_thresholds": {
            "max_nodes": int(max_nodes),
            "max_edges": int(max_edges),
            "max_degree": int(max_degree),
        },
        "budgets": {
            "overview_nodes": int(overview_nodes),
            "detail_core_nodes": int(max_detail_nodes),
            "detail_context_nodes": int(context_nodes),
            "detail_total_nodes": int(max_detail_nodes + context_nodes),
            "integration_nodes": int(max_detail_nodes),
        },
        "coverage": {
            "nodes_total": len(source_node_ids),
            "nodes_covered": len(covered_nodes & source_node_ids),
            "edges_total": len(source_edge_ids),
            "edges_covered": len(covered_edges & source_edge_ids),
            "missing_nodes": sorted(source_node_ids - covered_nodes),
            "missing_edges": sorted(source_edge_ids - covered_edges),
        },
        "views": manifest_views,
    }
    (outdir / "diagram-set.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {"split": True, "reasons": reasons, "metrics": metrics, "views": manifest_views}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    ap.add_argument("--max-edges", type=int, default=DEFAULT_MAX_EDGES)
    ap.add_argument("--max-degree", type=int, default=DEFAULT_MAX_DEGREE)
    ap.add_argument("--detail-nodes", type=int, default=DEFAULT_DETAIL_NODES)
    ap.add_argument("--overview-nodes", type=int, default=DEFAULT_OVERVIEW_NODES)
    ap.add_argument("--context-nodes", type=int, default=DEFAULT_CONTEXT_NODES)
    ap.add_argument("--check", action="store_true", help="report density without writing views")
    args = ap.parse_args()

    doc = yaml.safe_load(args.spec.read_text(encoding="utf-8")) or {}
    needs, reasons, metrics = should_split(
        doc,
        max_nodes=args.max_nodes,
        max_edges=args.max_edges,
        max_degree=args.max_degree,
    )
    print(
        f"DENSITY: nodes={metrics['nodes']} edges={metrics['edges']} "
        f"max_degree={metrics['max_degree']} edges_per_node={metrics['edges_per_node']}"
    )
    if not needs and not args.force:
        print("DENSITY PASS: one view is within the default readability budget")
        return 0
    print("DENSITY SPLIT REQUIRED: " + "; ".join(reasons or ["forced"]))
    if args.check:
        return 3

    result = write_plan(
        args.spec, args.outdir, force=True, max_nodes=args.max_nodes,
        max_edges=args.max_edges, max_degree=args.max_degree,
        max_detail_nodes=args.detail_nodes, overview_nodes=args.overview_nodes,
        context_nodes=args.context_nodes,
    )
    print(f"DENSITY PLAN: wrote {len(result['views'])} views to {args.outdir}")
    for view in result["views"]:
        print(
            f"  {view['id']}: {view['node_count']} nodes, "
            f"{view['edge_count']} edges — {view['label']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
