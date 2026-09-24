#!/usr/bin/env python3
"""Deterministic high-level architecture SVG renderer for Repo Diagrammer.

Reads an evidence spec and produces a geometry-owned SVG. The renderer optimizes
layer ordering with barycentric sweeps, emits orthogonal routes, and includes native
metadata consumed by visual_analyze_svg.py.
"""
from __future__ import annotations

import argparse
import html
import math
import sys
from pathlib import Path

from geometry_router import place_label, route_edge
from layout_optimizer import optimize_rows
from text_metrics import estimate_text_width, fit_font_size, wrap_text

try:
    import yaml
except ImportError:
    print("ARCH-RENDERER unavailable: install PyYAML", file=sys.stderr)
    raise SystemExit(2)

ROLE_ORDER = ["clients", "ingress", "api", "realtime", "messaging",
              "processing", "domain", "data", "observability", "external"]
PALETTE = {
    "clients": ("#EAF3FF", "#2F80ED"),
    "ingress": ("#EAF3FF", "#2F80ED"),
    "api": ("#F5F0FF", "#8B5CF6"),
    "realtime": ("#FFF1F2", "#F87171"),
    "messaging": ("#FFF7E6", "#F59E0B"),
    "processing": ("#EFF6FF", "#3B82F6"),
    "domain": ("#ECFDF5", "#34A853"),
    "observability": ("#ECFDF9", "#14B8A6"),
    "data": ("#F8FAFC", "#64748B"),
    "external": ("#FFF5F5", "#EF4444"),
}
ROLE_LABELS = {
    "clients": "Clients",
    "ingress": "Ingress",
    "api": "API",
    "realtime": "Realtime",
    "messaging": "Messaging",
    "processing": "Processing",
    "domain": "Domain",
    "data": "Data",
    "observability": "Observability",
    "external": "External",
}


def esc(s):
    return html.escape(str(s or ""))


def node_role(n):
    return str(n.get("semantic_role") or n.get("kind") or "domain")


def display_parts(n):
    vals = [n.get("display_label") or n.get("label") or n.get("id"),
            n.get("tech"), n.get("responsibility")]
    return [str(v).strip() for v in vals if str(v or "").strip()][:3]


def width_for(n, text_width_scale=1.0):
    parts = display_parts(n)
    if not parts:
        return 160
    title_w = estimate_text_width(parts[0], 13, "700") * text_width_scale + 28
    tech_w = estimate_text_width(parts[1], 10.5) * text_width_scale + 28 if len(parts) > 1 else 0
    # Responsibilities should wrap rather than forcing poster-width nodes.
    responsibility_target = min(
        300,
        estimate_text_width(parts[2], 10.5) * text_width_scale + 28 if len(parts) > 2 else 0,
    )
    return max(160, min(340, max(title_w, tech_w, responsibility_target, 160)))


def node_lines(n, width, text_width_scale=1.0):
    parts = display_parts(n)
    if not parts:
        return []
    inner = max(40, width-28)
    safe_inner = inner / max(text_width_scale, 1.0)
    title_size = fit_font_size(parts[0], safe_inner, 13, 9.5)
    result = [("title", parts[0], title_size)]
    if len(parts) > 1:
        tech_size = fit_font_size(parts[1], safe_inner, 10.5, 8.5)
        result.append(("detail", parts[1], tech_size))
    if len(parts) > 2:
        wrapped = wrap_text(parts[2], safe_inner, 10.5, max_lines=3) or [parts[2]]
        for line in wrapped:
            size = fit_font_size(line, safe_inner, 10.5, 8.5)
            result.append(("detail", line, size))
    return result


def height_for(n, width, text_width_scale=1.0):
    return max(88, 34 + 18*len(node_lines(n, width, text_width_scale)))


def parse_rows(doc, nodes):
    ids = {n["id"] for n in nodes}
    rows = (doc.get("layout") or {}).get("rows") or []
    out = []
    used = set()
    for row in rows:
        if isinstance(row, dict):
            members = [x for x in (row.get("nodes") or row.get("contains") or [])
                       if x in ids and x not in used]
            label = str(row.get("label") or row.get("id") or "")
        elif isinstance(row, list):
            members = [x for x in row if x in ids and x not in used]
            label = ""
        else:
            continue
        if members:
            out.append({"label": label, "nodes": members})
            used.update(members)

    leftovers = [n for n in nodes if n["id"] not in used]
    by = {}
    for n in leftovers:
        by.setdefault(node_role(n), []).append(n["id"])
    for role in ROLE_ORDER:
        if by.get(role):
            out.append({"label": role.replace("-", " ").title(), "nodes": by.pop(role)})
    for role, members in by.items():
        out.append({"label": role.replace("-", " ").title(), "nodes": members})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--spacing-scale", type=float, default=1.0,
                    help="presentation-only spacing multiplier used by auto-repair")
    ap.add_argument("--text-width-scale", type=float, default=1.0,
                    help="conservative text-width multiplier used by browser repair")
    ap.add_argument("--layout-variant", type=int, default=0,
                    help="deterministic node-order variant used by auto-repair")
    ap.add_argument("--routing-variant", type=int, default=0,
                    help="deterministic edge routing-order variant used by auto-repair")
    args = ap.parse_args()
    spacing_scale = max(0.85, min(1.8, args.spacing_scale))
    text_width_scale = max(1.0, min(1.5, args.text_width_scale))
    doc = yaml.safe_load(args.spec.read_text(encoding="utf-8"))

    dtype = str(doc.get("type") or "")
    if dtype not in {"c4-landscape", "c4-context", "c4-container", "c4-component"}:
        print(f"ARCH-RENDERER: unsupported type {dtype!r}; native renderer is only for static architecture views",
              file=sys.stderr)
        return 2

    nodes = [n for n in (doc.get("nodes") or []) if isinstance(n, dict) and n.get("id")]
    edges = [e for e in (doc.get("edges") or []) if isinstance(e, dict) and e.get("from") and e.get("to")]
    if not nodes:
        print("ARCH-RENDERER: no nodes", file=sys.stderr)
        return 1

    layout = doc.get("layout") or {}
    view = doc.get("view") or {}
    focus_ids = {str(x) for x in (view.get("focus") or [])}
    context_ids = {str(x) for x in (view.get("context_nodes") or [])}
    primary_path = [str(x) for x in (view.get("primary_path") or [])]
    raw_primary_paths = view.get("primary_paths") or []
    primary_paths = [
        [str(x) for x in path]
        for path in raw_primary_paths
        if isinstance(path, list) and path
    ]
    if not primary_paths and primary_path:
        primary_paths = [primary_path]
    primary_pairs = {
        pair
        for path in primary_paths
        for pair in zip(path, path[1:])
    }

    def edge_is_async(edge):
        return (edge.get("sync") is False) or edge.get("relation") in {
            "publishes", "emits", "consumes", "async", "event"
        }

    rows, layout_metrics = optimize_rows(
        parse_rows(doc, nodes),
        edges,
        declaration_order=layout.get("declaration_order") or [],
        primary_path=primary_path,
        primary_paths=primary_paths,
        variant=args.layout_variant,
    )
    nmap = {n["id"]: n for n in nodes}
    title = (doc.get("presentation") or {}).get("title") or "Architecture overview"
    subtitle = (doc.get("presentation") or {}).get("subtitle") or doc.get("scope") or ""

    margin = 70
    row_gap = 105 * spacing_scale
    node_gap = 34 * spacing_scale
    header = 112
    node_dims = {}
    row_widths = []
    row_heights = []
    for row in rows:
        dims = []
        for nid in row["nodes"]:
            w = width_for(nmap[nid], text_width_scale)
            h = height_for(nmap[nid], w, text_width_scale)
            node_dims[nid] = (w, h)
            dims.append((w, h))
        row_widths.append(sum(w for w, _ in dims)+node_gap*max(0, len(dims)-1))
        row_heights.append(max([h for _, h in dims] or [88]))

    header_w = max(
        estimate_text_width(title, 26, "700") * text_width_scale,
        estimate_text_width(subtitle, 13) * text_width_scale if subtitle else 0,
        max(
            [estimate_text_width(str(row.get("label") or ""), 11, "600") * text_width_scale
             for row in rows] or [0]
        ),
    ) + margin*2
    canvas_w = max(760, max(row_widths, default=0)+margin*2, header_w)

    presentation = doc.get("presentation") or {}
    legend_cfg = presentation.get("legend") or {}
    legend_show = bool(legend_cfg.get("show"))
    legend_items = []
    if legend_show:
        actual_pairs = {
            (str(edge.get("from") or ""), str(edge.get("to") or ""))
            for edge in edges
        }
        if primary_pairs & actual_pairs:
            legend_items.append({
                "key": "primary-flow",
                "kind": "edge-primary",
                "label": "Primary flow",
            })
        if any(not edge_is_async(edge) for edge in edges):
            legend_items.append({
                "key": "sync",
                "kind": "edge-sync",
                "label": "Sync",
            })
        if any(edge_is_async(edge) for edge in edges):
            legend_items.append({
                "key": "async-event",
                "kind": "edge-async",
                "label": "Async / event",
            })
        if context_ids:
            legend_items.append({
                "key": "context-node",
                "kind": "context-node",
                "label": "Context node",
            })

        present_roles = {node_role(node) for node in nodes}
        ordered_roles = sorted(
            present_roles,
            key=lambda role: (
                ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER),
                role,
            ),
        )
        for role in ordered_roles:
            legend_items.append({
                "key": f"role:{role}",
                "kind": "role",
                "role": role,
                "label": ROLE_LABELS.get(role, role.replace("-", " ").title()),
            })

    def legend_item_width(item):
        return 54 + estimate_text_width(item["label"], 10.5) * text_width_scale

    legend_rows = []
    if legend_show and legend_items:
        current = []
        used = 0.0
        available = max(240.0, canvas_w - margin*2)
        for item in legend_items:
            item = dict(item)
            item["width"] = legend_item_width(item)
            if current and used + item["width"] > available:
                legend_rows.append(current)
                current = []
                used = 0.0
            current.append(item)
            used += item["width"]
        if current:
            legend_rows.append(current)

    legend_h = (48 + len(legend_rows)*28) if legend_show else 20
    y = header
    boxes = {}
    row_index = {}
    for ri, row in enumerate(rows):
        total = row_widths[ri]
        row_h = row_heights[ri]
        x = (canvas_w-total)/2
        for nid in row["nodes"]:
            w, h = node_dims[nid]
            ny = y + (row_h-h)/2
            boxes[nid] = (x, ny, w, h)
            row_index[nid] = ri
            x += w+node_gap
        y += row_h+row_gap

    canvas_h = max(420, y-row_gap+margin+legend_h)

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
               f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" role="img" '
               f'aria-labelledby="diagram-svg-title diagram-svg-desc" '
               f'data-layout-variant="{args.layout_variant % 4}" '
               f'data-routing-variant="{args.routing_variant % 4}" '
               f'data-estimated-crossings="{layout_metrics.get("estimated_crossings", 0)}">')
    out.append(f'<title id="diagram-svg-title">{esc(title)}</title>')
    diagram_desc = subtitle or str(doc.get("scope") or "Architecture diagram")
    out.append(f'<desc id="diagram-svg-desc">{esc(diagram_desc)}</desc>')
    out.append('<defs>'
               '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
               '<path d="M0,0 L8,4 L0,8 z" fill="#475569"/></marker>'
               '<marker id="arrow-primary" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
               '<path d="M0,0 L8,4 L0,8 z" fill="#1E293B"/></marker>'
               '</defs>')
    out.append('<rect width="100%" height="100%" fill="#FFFFFF"/>')
    out.append(f'<text data-text-role="title" x="{margin}" y="46" font-family="Inter,Arial,sans-serif" font-size="26" '
               f'font-weight="700" fill="#0F172A">{esc(title)}</text>')
    if subtitle:
        out.append(f'<text data-text-role="subtitle" x="{margin}" y="72" font-family="Inter,Arial,sans-serif" font-size="13" '
                   f'fill="#64748B">{esc(subtitle)}</text>')

    # Edge labels must avoid not only nodes but also region header strips.
    label_obstacles = dict(boxes)

    # Regions are visual containers only. Real boundaries come from evidence-backed
    # boundaries; presentation groups remain softer and never become edge endpoints.
    def region_rect(member_ids, pad=18):
        rs = [boxes[x] for x in member_ids if x in boxes]
        if not rs:
            return None
        left = min(x for x, y0, w, h in rs)-pad
        top = min(y0 for x, y0, w, h in rs)-pad-14
        right = max(x+w for x, y0, w, h in rs)+pad
        bottom = max(y0+h for x, y0, w, h in rs)+pad
        return left, top, right-left, bottom-top

    for boundary in doc.get("boundaries") or []:
        if not isinstance(boundary, dict):
            continue
        rr = region_rect(boundary.get("contains") or [], 24)
        if not rr:
            continue
        bx, by, bw, bh = rr
        bid = str(boundary.get("id") or "")
        name = str(boundary.get("name") or bid)
        members = ",".join(str(x) for x in (boundary.get("contains") or []))
        label_obstacles[f"boundary:{bid}:header"] = (bx, by, bw, min(24.0, bh))
        region_font = fit_font_size(name, max(40, (bw-24)/text_width_scale), 10.5, 8.5)
        out.append(f'<g class="boundary" data-boundary-id="{esc(bid)}" data-region-kind="boundary" '
                   f'data-members="{esc(members)}"><rect x="{bx:.1f}" y="{by:.1f}" '
                   f'width="{bw:.1f}" height="{bh:.1f}" rx="16" fill="none" stroke="#64748B" '
                   'stroke-width="1.4" stroke-dasharray="8 6"/>'
                   f'<text data-text-role="region-header" x="{bx+12:.1f}" y="{by+13:.1f}" font-family="Inter,Arial,sans-serif" '
                   f'font-size="{region_font:.1f}" font-weight="700" fill="#475569">{esc(name)}</text></g>')

    groups = ((doc.get("presentation") or {}).get("groups") or [])
    for group in groups:
        if not isinstance(group, dict):
            continue
        rr = region_rect(group.get("contains") or [], 16)
        if not rr:
            continue
        gx, gy, gw, gh = rr
        gid = str(group.get("id") or "")
        name = str(group.get("label") or group.get("name") or gid)
        members = ",".join(str(x) for x in (group.get("contains") or []))
        label_obstacles[f"group:{gid}:header"] = (gx, gy, gw, min(24.0, gh))
        group_font = fit_font_size(name, max(40, (gw-24)/text_width_scale), 10, 8.5)
        out.append(f'<g class="presentation-group" data-group-id="{esc(gid)}" data-region-kind="presentation" '
                   f'data-members="{esc(members)}"><rect x="{gx:.1f}" y="{gy:.1f}" '
                   f'width="{gw:.1f}" height="{gh:.1f}" rx="14" fill="#F8FAFC" fill-opacity="0.55" '
                   'stroke="#CBD5E1" stroke-width="1"/>'
                   f'<text data-text-role="region-header" x="{gx+12:.1f}" y="{gy+18:.1f}" font-family="Inter,Arial,sans-serif" '
                   f'font-size="{group_font:.1f}" font-weight="600" fill="#64748B">{esc(name)}</text></g>')

    for row in rows:
        if not row.get("label") or not row["nodes"]:
            continue
        ry = boxes[row["nodes"][0]][1]-18
        out.append(f'<text data-text-role="row-heading" x="{margin}" y="{ry:.1f}" font-family="Inter,Arial,sans-serif" font-size="11" '
                   f'font-weight="600" fill="#94A3B8" letter-spacing="0.6">{esc(row["label"].upper())}</text>')

    def is_primary(edge):
        pair = (str(edge.get("from") or ""), str(edge.get("to") or ""))
        return pair in primary_pairs

    degree = {nid: 0 for nid in boxes}
    for edge in edges:
        for nid in (str(edge.get("from") or ""), str(edge.get("to") or "")):
            if nid in degree:
                degree[nid] += 1

    def routing_key(item):
        index, edge = item
        sid = str(edge.get("from") or "")
        tid = str(edge.get("to") or "")
        span = abs(row_index.get(sid, 0)-row_index.get(tid, 0))
        endpoint_degree = degree.get(sid, 0)+degree.get(tid, 0)
        primary_rank = 0 if is_primary(edge) else 1
        variant = args.routing_variant % 4
        if variant == 1:
            return (primary_rank, -span, -endpoint_degree, index)
        if variant == 2:
            return (primary_rank, span, -endpoint_degree, index)
        if variant == 3:
            return (primary_rank, -endpoint_degree, -span, index)
        return (primary_rank, index)

    ordered_edges = sorted(enumerate(edges), key=routing_key)
    incident = {nid: [] for nid in boxes}
    for original_index, edge in ordered_edges:
        eid = str(edge.get("id") or f"edge-{original_index}")
        for nid in (edge.get("from"), edge.get("to")):
            if nid in incident:
                incident[nid].append(eid)

    def port_slot(nid, eid):
        ids = incident.get(nid) or []
        if len(ids) <= 1:
            return 0.0
        idx = ids.index(eid)
        return (idx/(len(ids)-1))*2.0 - 1.0

    route_lane_count = {}
    existing_routes = []
    routed_edges = []

    # Phase 1: route every edge. Labels are deliberately deferred because a label
    # cannot avoid an edge that has not been routed yet.
    for ei, e in ordered_edges:
        sid, tid = e["from"], e["to"]
        if sid not in boxes or tid not in boxes:
            continue
        sri, tri = row_index[sid], row_index[tid]
        key = (min(sri, tri), max(sri, tri))
        lane_index = route_lane_count.get(key, 0)
        route_lane_count[key] = lane_index + 1
        eid = str(e.get("id") or f"edge-{ei}")
        pts = route_edge(
            boxes, row_index, sid, tid, canvas_w, existing_routes, lane_index,
            port_slot(sid, eid), port_slot(tid, eid)
        )
        if len(pts) < 2:
            continue
        record = {"id": eid, "source": sid, "target": tid, "points": pts, "edge": e}
        existing_routes.append(record)
        routed_edges.append(record)

    # Phase 2: render all routed edges now that global route geometry is known.
    for record in routed_edges:
        e = record["edge"]
        eid = record["id"]
        sid, tid = record["source"], record["target"]
        pts = record["points"]
        dashed = edge_is_async(e)
        dash = ' stroke-dasharray="7 6"' if dashed else ""
        d = "M " + " L ".join(f"{x:.1f},{yy:.1f}" for x, yy in pts)
        primary = is_primary(e)
        stroke = "#1E293B" if primary else "#475569"
        stroke_width = "2.8" if primary else "1.7"
        marker = "arrow-primary" if primary else "arrow"
        primary_attr = ' data-primary="true"' if primary else ""
        sync_value = "false" if dashed else "true"
        relation = str(e.get("relation") or "relation")
        edge_label = str(e.get("label") or e.get("protocol") or relation)
        edge_accessible = f"{sid} to {tid}: {edge_label}; {'async' if dashed else 'sync'}"
        out.append(f'<g class="edge" data-edge-id="{esc(eid)}" data-source-id="{esc(sid)}" '
                   f'data-target-id="{esc(tid)}" data-sync="{sync_value}" role="img" '
                   f'aria-label="{esc(edge_accessible)}"{primary_attr}><path d="{d}" fill="none" stroke="{stroke}" '
                   f'stroke-width="{stroke_width}"{dash} marker-end="url(#{marker})"/></g>')

    # Phase 3: place labels against the complete edge set.
    placed_labels = []
    for record in routed_edges:
        e = record["edge"]
        eid = record["id"]
        pts = record["points"]
        label = str(e.get("label") or e.get("protocol") or "").strip()
        if not label:
            continue
        lw = max(34, min(300, 14+estimate_text_width(label, 10.5)*text_width_scale))
        lh = 20
        lx, ly, _, _ = place_label(
            pts, lw, lh, label_obstacles, placed_labels, existing_routes, eid, canvas_w, canvas_h
        )
        placed_labels.append((lx, ly, lw, lh))
        out.append(f'<g class="edge-label" data-edge-label-id="{esc(eid)}-label">'
                   f'<rect x="{lx:.1f}" y="{ly:.1f}" width="{lw:.1f}" height="{lh}" rx="5" '
                   'fill="#FFFFFF" fill-opacity="0.94"/>'
                   f'<text data-text-role="edge-label" x="{lx+7:.1f}" y="{ly+13.5:.1f}" font-family="Inter,Arial,sans-serif" '
                   f'font-size="10.5" fill="#64748B">{esc(label)}</text></g>')

    for nid, (x, yy, w, h) in boxes.items():
        node = nmap[nid]
        role = node_role(node)
        fill, stroke = PALETTE.get(role, ("#F8FAFC", "#64748B"))
        if nid in context_ids:
            visual_scope = "context"
        elif nid in focus_ids:
            visual_scope = "focus"
        else:
            visual_scope = "default"
        is_context = visual_scope == "context"
        fill_opacity = "0.38" if is_context else "1"
        stroke_opacity = "0.65" if is_context else "1"
        dash = ' stroke-dasharray="5 4"' if is_context else ""
        lines = node_lines(node, w, text_width_scale)
        node_label = str(node.get("display_label") or node.get("label") or nid)
        node_tech = str(node.get("tech") or "").strip()
        node_resp = str(node.get("responsibility") or "").strip()
        accessible_parts = [node_label, f"role {role}"]
        if node_tech:
            accessible_parts.append(node_tech)
        if node_resp:
            accessible_parts.append(node_resp)
        node_accessible = "; ".join(accessible_parts)
        out.append(
            f'<g class="node" data-node-id="{esc(nid)}" data-node-role="{esc(role)}" '
            f'data-row-index="{row_index[nid]}" data-visual-scope="{visual_scope}" '
            f'role="group" aria-label="{esc(node_accessible)}">'
            f'<rect x="{x:.1f}" y="{yy:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="12" fill="{fill}" fill-opacity="{fill_opacity}" stroke="{stroke}" '
            f'stroke-opacity="{stroke_opacity}" stroke-width="1.5"{dash}/>'
        )
        base = yy+27
        for li, (kind, line, size) in enumerate(lines):
            weight = "700" if kind == "title" else "400"
            if is_context:
                color = "#475569" if kind == "title" else "#64748B"
            else:
                color = "#0F172A" if kind == "title" else "#475569"
            text_role = "node-title" if kind == "title" else "node-detail"
            out.append(f'<text data-text-role="{text_role}" x="{x+14:.1f}" y="{base+li*18:.1f}" font-family="Inter,Arial,sans-serif" '
                       f'font-size="{size}" font-weight="{weight}" fill="{color}">{esc(line)}</text>')
        out.append("</g>")

    if legend_show:
        legend_top = canvas_h-legend_h+16
        out.append('<g class="legend" data-legend="semantic">')
        out.append(
            f'<text data-text-role="legend-heading" x="{margin}" y="{legend_top+11:.1f}" '
            'font-family="Inter,Arial,sans-serif" font-size="9.5" font-weight="700" '
            'fill="#64748B" letter-spacing="0.7">LEGEND</text>'
        )
        for row_idx, legend_row in enumerate(legend_rows):
            item_y = legend_top+34+row_idx*28
            item_x = float(margin)
            for item in legend_row:
                key = str(item["key"])
                kind = item["kind"]
                label = str(item["label"])
                out.append(f'<g class="legend-item" data-legend-key="{esc(key)}">')
                if kind == "role":
                    role = str(item.get("role") or "")
                    fill, stroke = PALETTE.get(role, ("#F8FAFC", "#64748B"))
                    out.append(
                        f'<rect x="{item_x:.1f}" y="{item_y-10:.1f}" width="18" height="12" '
                        f'rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
                    )
                    text_x = item_x+26
                elif kind == "context-node":
                    out.append(
                        f'<rect x="{item_x:.1f}" y="{item_y-10:.1f}" width="18" height="12" '
                        'rx="4" fill="#F8FAFC" fill-opacity="0.38" stroke="#64748B" '
                        'stroke-opacity="0.65" stroke-width="1.2" stroke-dasharray="4 3"/>'
                    )
                    text_x = item_x+26
                else:
                    stroke = "#1E293B" if kind == "edge-primary" else "#475569"
                    width = "2.8" if kind == "edge-primary" else "1.7"
                    dash = ' stroke-dasharray="7 6"' if kind == "edge-async" else ""
                    out.append(
                        f'<line x1="{item_x:.1f}" y1="{item_y-4:.1f}" '
                        f'x2="{item_x+28:.1f}" y2="{item_y-4:.1f}" '
                        f'stroke="{stroke}" stroke-width="{width}"{dash}/>'
                    )
                    text_x = item_x+36
                out.append(
                    f'<text data-text-role="legend" x="{text_x:.1f}" y="{item_y:.1f}" '
                    'font-family="Inter,Arial,sans-serif" font-size="10.5" '
                    f'fill="#64748B">{esc(label)}</text>'
                )
                out.append('</g>')
                item_x += float(item["width"])
        out.append('</g>')

    out.append("</svg>")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out), encoding="utf-8")
    print(f"rendered: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
