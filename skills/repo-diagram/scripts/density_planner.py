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


def _split_members(members, adjacency, degree, max_size):
    remaining = set(members)
    chunks = []
    while remaining:
        seed = max(remaining, key=lambda x: (degree.get(x, 0), x))
        chunk = [seed]
        remaining.remove(seed)
        while remaining and len(chunk) < max_size:
            def affinity(nid):
                links = sum(1 for x in chunk if x in adjacency.get(nid, set()))
                chunk_neighbor_degree = sum(
                    1 for x in adjacency.get(nid, set()) if x in set(members)
                )
                return (links, chunk_neighbor_degree, degree.get(nid, 0), nid)
            candidate = max(remaining, key=affinity)
            # Prefer connected growth. If none connect, deterministic fill is still better
            # than leaving many singleton fragments from the same semantic seed.
            chunk.append(candidate)
            remaining.remove(candidate)
        chunks.append(chunk)
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
                _, _, j = max(candidates)
                if j == i:
                    continue
                target = expanded[j]
                target["members"].extend(cluster["members"])
                target["members"] = sorted(set(target["members"]))
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


def make_view(doc, core_ids, label, context_limit=DEFAULT_CONTEXT_NODES, overview=False):
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
    primary = [str(x) for x in (view.get("primary_path") or []) if str(x) in included]
    view["primary_path"] = primary
    view["focus"] = sorted(core)
    view["context_nodes"] = context
    view["suppress"] = sorted(all_ids - included)
    view["split_generated"] = True
    view["split_kind"] = "overview" if overview else "detail"
    clone["view"] = view

    clone["scope"] = f"{doc.get('scope') or 'architecture'} / {label}"
    return clone


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
            "spec": make_view(
                doc,
                cluster["members"],
                cluster["label"],
                context_limit=context_nodes,
                overview=False,
            ),
        })
    return views


def write_plan(spec_path, outdir, force=False, max_nodes=DEFAULT_MAX_NODES,
               max_detail_nodes=DEFAULT_DETAIL_NODES,
               overview_nodes=DEFAULT_OVERVIEW_NODES,
               context_nodes=DEFAULT_CONTEXT_NODES):
    doc = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8")) or {}
    needs_split, reasons, metrics = should_split(doc, max_nodes=max_nodes)
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
        manifest_views.append({
            "id": view["id"],
            "label": view["label"],
            "spec": filename,
            "core_nodes": view["core"],
            "node_count": len(view["spec"].get("nodes") or []),
            "edge_count": len(view["spec"].get("edges") or []),
        })

    manifest = {
        "source_spec": str(Path(spec_path)),
        "split_trigger": reasons or ["forced"],
        "source_metrics": metrics,
        "stable_ids": True,
        "invented_architecture_elements": False,
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
    ap.add_argument("--detail-nodes", type=int, default=DEFAULT_DETAIL_NODES)
    ap.add_argument("--overview-nodes", type=int, default=DEFAULT_OVERVIEW_NODES)
    ap.add_argument("--context-nodes", type=int, default=DEFAULT_CONTEXT_NODES)
    ap.add_argument("--check", action="store_true", help="report density without writing views")
    args = ap.parse_args()

    doc = yaml.safe_load(args.spec.read_text(encoding="utf-8")) or {}
    needs, reasons, metrics = should_split(doc, max_nodes=args.max_nodes)
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
