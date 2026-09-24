#!/usr/bin/env python3
"""Deterministic row-order optimization for layered architecture diagrams."""
from __future__ import annotations

import copy
from collections import defaultdict


def _node_ids(rows):
    return [str(n) for row in rows for n in (row.get("nodes") or [])]


def _graph(edges, ids):
    ids = set(ids)
    adj = {nid: set() for nid in ids}
    degree = {nid: 0 for nid in ids}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        a, b = str(edge.get("from") or ""), str(edge.get("to") or "")
        if a in ids and b in ids and a != b:
            adj[a].add(b)
            adj[b].add(a)
            degree[a] += 1
            degree[b] += 1
    return adj, degree


def _primary_paths(primary_path=None, primary_paths=None):
    paths = []
    for path in primary_paths or []:
        if isinstance(path, (list, tuple)) and path:
            paths.append([str(x) for x in path])
    if not paths and primary_path:
        paths = [[str(x) for x in primary_path]]
    return paths


def _primary_rank(primary_path=None, primary_paths=None):
    rank = {}
    counter = 0
    for path in _primary_paths(primary_path, primary_paths):
        for nid in path:
            if nid not in rank:
                rank[nid] = counter
            counter += 1
        counter += 1000
    return rank


def apply_initial_order(rows, edges, declaration_order=None, primary_path=None,
                        primary_paths=None, variant=0):
    rows = copy.deepcopy(rows)
    ids = _node_ids(rows)
    adj, degree = _graph(edges, ids)
    decl = {str(n): i for i, n in enumerate(declaration_order or [])}
    primary = _primary_rank(primary_path, primary_paths)

    for row in rows:
        original = {str(n): i for i, n in enumerate(row.get("nodes") or [])}

        def key(nid):
            nid = str(nid)
            decl_rank = decl.get(nid, 10**6 + original.get(nid, 0))
            primary_rank = primary.get(nid, 10**6)
            if variant == 1:
                return (-degree.get(nid, 0), decl_rank, original.get(nid, 0), nid)
            if variant == 2:
                return (primary_rank, -degree.get(nid, 0), decl_rank, nid)
            if variant == 3:
                # Reverse the declaration/original tie direction to escape local minima.
                return (decl_rank, -original.get(nid, 0), -degree.get(nid, 0), nid)
            return (decl_rank, original.get(nid, 0), nid)

        row["nodes"] = sorted([str(n) for n in (row.get("nodes") or [])], key=key)
    return rows


def barycentric_order(rows, edges, sweeps=6, reverse_sweep=False):
    rows = copy.deepcopy(rows)
    pos = {nid: i for row in rows for i, nid in enumerate(row["nodes"])}
    adj, _ = _graph(edges, pos)

    directions = (False, True) if reverse_sweep else (True, False)
    for _ in range(max(1, sweeps)):
        for forward in directions:
            seq = range(1, len(rows)) if forward else range(len(rows)-2, -1, -1)
            for ri in seq:
                target = ri-1 if forward else ri+1
                target_set = set(rows[target]["nodes"])
                old = {nid: i for i, nid in enumerate(rows[ri]["nodes"])}

                def score(nid):
                    vals = [pos.get(x, 0) for x in adj.get(nid, ()) if x in target_set]
                    bary = sum(vals)/len(vals) if vals else old[nid]
                    return (bary, old[nid], nid)

                rows[ri]["nodes"].sort(key=score)
                for i, nid in enumerate(rows[ri]["nodes"]):
                    pos[nid] = i
    return rows


def crossing_score(rows, edges, primary_path=None, primary_paths=None):
    """Estimate crossings for edges connecting the same pair of layers."""
    loc = {}
    for ri, row in enumerate(rows):
        for pi, nid in enumerate(row.get("nodes") or []):
            loc[str(nid)] = (ri, pi)

    grouped = defaultdict(list)
    distance = 0
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        a, b = str(edge.get("from") or ""), str(edge.get("to") or "")
        if a not in loc or b not in loc:
            continue
        ra, pa = loc[a]
        rb, pb = loc[b]
        if ra == rb:
            distance += abs(pa-pb)
            continue
        if ra < rb:
            key = (ra, rb)
            grouped[key].append((pa, pb, a, b))
        else:
            key = (rb, ra)
            grouped[key].append((pb, pa, b, a))
        distance += abs(pa-pb)

    crossings = 0
    for items in grouped.values():
        for i, e1 in enumerate(items):
            for e2 in items[i+1:]:
                if e1[2] in {e2[2], e2[3]} or e1[3] in {e2[2], e2[3]}:
                    continue
                if (e1[0]-e2[0]) * (e1[1]-e2[1]) < 0:
                    crossings += 1

    primary_penalty = 0
    paths = _primary_paths(primary_path, primary_paths)
    primary_segments = 0
    for path in paths:
        for a, b in zip(path, path[1:]):
            if a in loc and b in loc:
                ra, pa = loc[a]
                rb, pb = loc[b]
                primary_penalty += abs(ra-rb)*2 + abs(pa-pb)
                primary_segments += 1

    # Crossings dominate; compact routes and a coherent primary path break ties.
    return crossings*10_000 + primary_penalty*20 + distance, {
        "estimated_crossings": crossings,
        "distance_penalty": distance,
        "primary_penalty": primary_penalty,
        "primary_paths": len(paths),
        "primary_segments": primary_segments,
    }


def hill_climb(rows, edges, primary_path=None, primary_paths=None, max_rounds=8):
    rows = copy.deepcopy(rows)
    best_score, _ = crossing_score(
        rows, edges, primary_path=primary_path, primary_paths=primary_paths
    )
    for _ in range(max_rounds):
        improved = False
        for ri, row in enumerate(rows):
            nodes = row.get("nodes") or []
            for i in range(len(nodes)-1):
                candidate = copy.deepcopy(rows)
                cnodes = candidate[ri]["nodes"]
                cnodes[i], cnodes[i+1] = cnodes[i+1], cnodes[i]
                score, _ = crossing_score(
                    candidate, edges,
                    primary_path=primary_path,
                    primary_paths=primary_paths,
                )
                if score < best_score:
                    rows = candidate
                    best_score = score
                    improved = True
        if not improved:
            break
    return rows


def optimize_rows(rows, edges, declaration_order=None, primary_path=None,
                  primary_paths=None, variant=0):
    seeded = apply_initial_order(
        rows, edges,
        declaration_order=declaration_order,
        primary_path=primary_path,
        primary_paths=primary_paths,
        variant=variant % 4,
    )
    swept = barycentric_order(
        seeded, edges,
        sweeps=5 + (variant % 2),
        reverse_sweep=(variant % 4) in {2, 3},
    )
    optimized = hill_climb(
        swept, edges,
        primary_path=primary_path,
        primary_paths=primary_paths,
    )
    score, metrics = crossing_score(
        optimized, edges,
        primary_path=primary_path,
        primary_paths=primary_paths,
    )
    metrics["score"] = score
    metrics["variant"] = variant % 4
    return optimized, metrics
