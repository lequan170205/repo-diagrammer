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


def esc(s):
    return html.escape(str(s or ""))


def node_role(n):
    return str(n.get("semantic_role") or n.get("kind") or "domain")


def display_lines(n):
    vals = [n.get("display_label") or n.get("label") or n.get("id"),
            n.get("tech"), n.get("responsibility")]
    return [str(v).strip() for v in vals if str(v or "").strip()][:3]


def width_for(n):
    longest = max([len(x) for x in display_lines(n)] or [10])
    return max(160, min(260, 110+longest*5.2))


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


def barycentric_order(rows, edges):
    pos = {nid: i for row in rows for i, nid in enumerate(row["nodes"])}
    adj = {nid: [] for row in rows for nid in row["nodes"]}
    for e in edges:
        a, b = e.get("from"), e.get("to")
        if a in adj and b in adj:
            adj[a].append(b)
            adj[b].append(a)

    for _ in range(5):
        for forward in (True, False):
            seq = range(1, len(rows)) if forward else range(len(rows)-2, -1, -1)
            for ri in seq:
                target = ri-1 if forward else ri+1
                target_set = set(rows[target]["nodes"])
                old = {nid: i for i, nid in enumerate(rows[ri]["nodes"])}

                def score(nid):
                    vals = [pos.get(x, 0) for x in adj[nid] if x in target_set]
                    return (sum(vals)/len(vals) if vals else old[nid], old[nid])

                rows[ri]["nodes"].sort(key=score)
                for i, nid in enumerate(rows[ri]["nodes"]):
                    pos[nid] = i
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()
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

    nmap = {n["id"]: n for n in nodes}
    layout = doc.get("layout") or {}
    raw_sidecars = layout.get("sidecars") or {}
    sidecars = {
        zone: [nid for nid in (raw_sidecars.get(zone) or []) if nid in nmap]
        for zone in ("left", "right", "bottom")
    }
    sidecar_ids = {nid for members in sidecars.values() for nid in members}
    core_nodes = [n for n in nodes if n["id"] not in sidecar_ids]
    if not core_nodes:
        core_nodes = nodes
        sidecars = {"left": [], "right": [], "bottom": []}
        sidecar_ids = set()

    rows = barycentric_order(parse_rows(doc, core_nodes), edges)

    margin = 70
    row_gap = 105
    node_gap = 34
    sidecar_gap = 70
    sidecar_stack_gap = 28
    header = 112
    node_h = 88
    row_widths = []
    for row in rows:
        ws = [width_for(nmap[x]) for x in row["nodes"]]
        row_widths.append(sum(ws)+node_gap*max(0, len(ws)-1))

    def zone_width(zone):
        return max([width_for(nmap[nid]) for nid in sidecars[zone]] or [0])

    left_w, right_w = zone_width("left"), zone_width("right")
    left_reserve = left_w+sidecar_gap if left_w else 0
    right_reserve = right_w+sidecar_gap if right_w else 0
    bottom_ws = [width_for(nmap[nid]) for nid in sidecars["bottom"]]
    bottom_width = sum(bottom_ws)+node_gap*max(0, len(bottom_ws)-1)

    core_width = max(row_widths, default=0)
    canvas_w = max(
        980,
        core_width+margin*2+left_reserve+right_reserve,
        bottom_width+margin*2,
    )
    core_left = margin+left_reserve
    core_right = canvas_w-margin-right_reserve
    core_span = max(core_width, core_right-core_left)

    y = header
    boxes = {}
    row_index = {}
    node_zone = {}
    for ri, row in enumerate(rows):
        total = row_widths[ri]
        x = core_left+(core_span-total)/2
        for nid in row["nodes"]:
            w = width_for(nmap[nid])
            boxes[nid] = (x, y, w, node_h)
            row_index[nid] = ri
            node_zone[nid] = "core"
            x += w+node_gap
        y += node_h+row_gap
    core_bottom = y-row_gap

    side_stack_bottom = core_bottom
    for zone in ("left", "right"):
        sy0 = header
        for nid in sidecars[zone]:
            w = width_for(nmap[nid])
            x = margin if zone == "left" else canvas_w-margin-w
            boxes[nid] = (x, sy0, w, node_h)
            node_zone[nid] = zone
            sy0 += node_h+sidecar_stack_gap
        side_stack_bottom = max(side_stack_bottom, sy0-sidecar_stack_gap if sidecars[zone] else core_bottom)

    if sidecars["bottom"]:
        by = max(core_bottom, side_stack_bottom)+row_gap
        total = bottom_width
        x = (canvas_w-total)/2
        for nid in sidecars["bottom"]:
            w = width_for(nmap[nid])
            boxes[nid] = (x, by, w, node_h)
            row_index[nid] = len(rows)
            node_zone[nid] = "bottom"
            x += w+node_gap
        content_bottom = by+node_h
    else:
        content_bottom = max(core_bottom, side_stack_bottom)

    # Sidecars align semantically with the median connected core row so edges enter
    # horizontally whenever possible instead of making unnecessary cross-layer arcs.
    middle_row = max(0, (len(rows)-1)//2)
    for zone in ("left", "right"):
        for nid in sidecars[zone]:
            neighbor_rows = []
            for edge in edges:
                other = None
                if edge.get("from") == nid:
                    other = edge.get("to")
                elif edge.get("to") == nid:
                    other = edge.get("from")
                if other in row_index and node_zone.get(other) == "core":
                    neighbor_rows.append(row_index[other])
            if neighbor_rows:
                vals = sorted(neighbor_rows)
                row_index[nid] = vals[len(vals)//2]
                target_y = header+row_index[nid]*(node_h+row_gap)
                x0, _, w, h = boxes[nid]
                boxes[nid] = (x0, target_y, w, h)
            else:
                row_index[nid] = middle_row

    content_bottom = max([y0+h for x0, y0, w, h in boxes.values()] or [content_bottom])
    legend_h = 70 if ((doc.get("presentation") or {}).get("legend") or {}).get("show") else 20
    canvas_h = max(620, content_bottom+margin+legend_h)
    title = (doc.get("presentation") or {}).get("title") or "Architecture overview"
    subtitle = (doc.get("presentation") or {}).get("subtitle") or doc.get("scope") or ""

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w:.0f}" height="{canvas_h:.0f}" '
               f'viewBox="0 0 {canvas_w:.0f} {canvas_h:.0f}" role="img">')
    out.append('<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
               '<path d="M0,0 L8,4 L0,8 z" fill="#475569"/></marker></defs>')
    out.append('<rect width="100%" height="100%" fill="#FFFFFF"/>')
    out.append(f'<text x="{margin}" y="46" font-family="Inter,Arial,sans-serif" font-size="26" '
               f'font-weight="700" fill="#0F172A">{esc(title)}</text>')
    if subtitle:
        out.append(f'<text x="{margin}" y="72" font-family="Inter,Arial,sans-serif" font-size="13" '
                   f'fill="#64748B">{esc(subtitle)}</text>')

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
        out.append(f'<g class="boundary" data-boundary-id="{esc(bid)}"><rect x="{bx:.1f}" y="{by:.1f}" '
                   f'width="{bw:.1f}" height="{bh:.1f}" rx="16" fill="none" stroke="#64748B" '
                   'stroke-width="1.4" stroke-dasharray="8 6"/>'
                   f'<text x="{bx+12:.1f}" y="{by+16:.1f}" font-family="Inter,Arial,sans-serif" '
                   f'font-size="10.5" font-weight="700" fill="#475569">{esc(name)}</text></g>')

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
        out.append(f'<g class="presentation-group" data-group-id="{esc(gid)}"><rect x="{gx:.1f}" y="{gy:.1f}" '
                   f'width="{gw:.1f}" height="{gh:.1f}" rx="14" fill="#F8FAFC" fill-opacity="0.55" '
                   'stroke="#CBD5E1" stroke-width="1"/>'
                   f'<text x="{gx+12:.1f}" y="{gy+15:.1f}" font-family="Inter,Arial,sans-serif" '
                   f'font-size="10" font-weight="600" fill="#64748B">{esc(name)}</text></g>')

    for row in rows:
        if not row.get("label") or not row["nodes"]:
            continue
        ry = boxes[row["nodes"][0]][1]-18
        out.append(f'<text x="{margin}" y="{ry:.1f}" font-family="Inter,Arial,sans-serif" font-size="11" '
                   f'font-weight="600" fill="#94A3B8" letter-spacing="0.6">{esc(row["label"].upper())}</text>')

    # Allocate distinct ports before routing so multiple edges incident to the same
    # node do not collapse into one ambiguous stem.
    port_groups = {}
    edge_sides = {}
    for ei, e in enumerate(edges):
        sid, tid = e.get("from"), e.get("to")
        if sid not in boxes or tid not in boxes:
            continue
        sx, sy, sw, sh = boxes[sid]
        tx, ty, tw, th = boxes[tid]
        sri, tri = row_index[sid], row_index[tid]
        if sri == tri:
            if sx+sw/2 <= tx+tw/2:
                ss, ts = "right", "left"
            else:
                ss, ts = "left", "right"
        elif tri > sri:
            ss, ts = "bottom", "top"
        else:
            ss, ts = "top", "bottom"
        edge_sides[ei] = (ss, ts)
        port_groups.setdefault((sid, ss), []).append(ei)
        port_groups.setdefault((tid, ts), []).append(ei)

    def port_for(nid, side, ei):
        x, y0, w, h = boxes[nid]
        group = port_groups.get((nid, side), [ei])
        idx = group.index(ei)
        frac = (idx+1)/(len(group)+1)
        if side == "top":
            return x+w*frac, y0
        if side == "bottom":
            return x+w*frac, y0+h
        if side == "left":
            return x, y0+h*frac
        return x+w, y0+h*frac

    same_row_count = {}
    cross_count = {}
    for ei, e in enumerate(edges):
        sid, tid = e["from"], e["to"]
        if sid not in boxes or tid not in boxes:
            continue
        sx, sy, sw, sh = boxes[sid]
        tx, ty, tw, th = boxes[tid]
        sri, tri = row_index[sid], row_index[tid]
        dashed = (e.get("sync") is False) or e.get("relation") in {
            "publishes", "emits", "consumes", "async", "event"
        }
        dash = ' stroke-dasharray="7 6"' if dashed else ""

        source_side, target_side = edge_sides[ei]
        if sri == tri:
            k = same_row_count.get(sri, 0)
            same_row_count[sri] = k+1
            x1, y1 = port_for(sid, source_side, ei)
            x2, y2 = port_for(tid, target_side, ei)
            lift = 32+18*k
            midy = min(sy, ty)-lift
            pts = [(x1, y1), (x1, midy), (x2, midy), (x2, y2)]
        else:
            downward = tri > sri
            x1, y1 = port_for(sid, source_side, ei)
            x2, y2 = port_for(tid, target_side, ei)
            key = (min(sri, tri), max(sri, tri))
            k = cross_count.get(key, 0)
            cross_count[key] = k+1
            mid = (y1+y2)/2 + ((k % 5)-2)*9
            pts = [(x1, y1), (x1, mid), (x2, mid), (x2, y2)]

            # If the route spans layers and would pass through an intermediate node,
            # move it to a perimeter channel. A longer unambiguous route is better
            # than an edge visually passing through a box.
            lo, hi = sorted((sri, tri))
            intermediate = [bid for bid, bri in row_index.items() if lo < bri < hi]

            def seg_hits_box(a, b, box):
                bx, by, bw, bh = box
                if abs(a[0]-b[0]) < 0.01:
                    xx = a[0]
                    ya, yb = sorted((a[1], b[1]))
                    return bx < xx < bx+bw and max(ya, by) < min(yb, by+bh)
                if abs(a[1]-b[1]) < 0.01:
                    yy = a[1]
                    xa, xb = sorted((a[0], b[0]))
                    return by < yy < by+bh and max(xa, bx) < min(xb, bx+bw)
                return False

            blocked = any(seg_hits_box(a, b, boxes[bid])
                          for bid in intermediate
                          for a, b in zip(pts, pts[1:]))
            if blocked:
                # Use the nearest perimeter, not the opposite side of the canvas.
                # Multiple blocked edges get adjacent lanes inside the outer margin.
                lane = k % 3
                if (x1+x2)/2 > canvas_w/2:
                    channel = canvas_w-(32+lane*12)
                else:
                    channel = 32+lane*12
                stub1 = y1+(18 if downward else -18)
                stub2 = y2+(-18 if downward else 18)
                pts = [(x1, y1), (x1, stub1), (channel, stub1),
                       (channel, stub2), (x2, stub2), (x2, y2)]

        d = "M " + " L ".join(f"{x:.1f},{yy:.1f}" for x, yy in pts)
        eid = str(e.get("id") or f"edge-{ei}")
        out.append(f'<g class="edge" data-edge-id="{esc(eid)}" data-source-id="{esc(sid)}" '
                   f'data-target-id="{esc(tid)}"><path d="{d}" fill="none" stroke="#475569" '
                   f'stroke-width="1.7"{dash} marker-end="url(#arrow)"/></g>')
        label = str(e.get("label") or e.get("protocol") or "").strip()
        if label:
            # Place labels on the longest route segment and give them a measurable
            # background box so collision analysis is deterministic.
            segs = list(zip(pts, pts[1:]))
            a, b = max(segs, key=lambda ab: math.dist(ab[0], ab[1]))
            mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
            lw = max(34, min(210, 14+len(label)*5.8))
            lh = 20
            if abs(a[0]-b[0]) < abs(a[1]-b[1]):
                lx, ly = mx+7, my-lh/2
            else:
                lx, ly = mx-lw/2, my-lh-5
            out.append(f'<g class="edge-label" data-edge-label-id="{esc(eid)}-label">'
                       f'<rect x="{lx:.1f}" y="{ly:.1f}" width="{lw:.1f}" height="{lh}" rx="5" '
                       'fill="#FFFFFF" fill-opacity="0.94"/>'
                       f'<text x="{lx+7:.1f}" y="{ly+13.5:.1f}" font-family="Inter,Arial,sans-serif" '
                       f'font-size="10.5" fill="#64748B">{esc(label)}</text></g>')

    for nid, (x, yy, w, h) in boxes.items():
        node = nmap[nid]
        role = node_role(node)
        fill, stroke = PALETTE.get(role, ("#F8FAFC", "#64748B"))
        lines = display_lines(node)
        zone = node_zone.get(nid, "core")
        out.append(f'<g class="node" data-node-id="{esc(nid)}" data-layout-zone="{esc(zone)}"><rect x="{x:.1f}" y="{yy:.1f}" '
                   f'width="{w:.1f}" height="{h:.1f}" rx="12" fill="{fill}" stroke="{stroke}" '
                   f'stroke-width="1.5"/>')
        base = yy+27
        for li, line in enumerate(lines):
            size = 13 if li == 0 else 10.5
            weight = "700" if li == 0 else "400"
            color = "#0F172A" if li == 0 else "#475569"
            out.append(f'<text x="{x+14:.1f}" y="{base+li*20:.1f}" font-family="Inter,Arial,sans-serif" '
                       f'font-size="{size}" font-weight="{weight}" fill="{color}">{esc(line)}</text>')
        out.append("</g>")

    if ((doc.get("presentation") or {}).get("legend") or {}).get("show"):
        ly = canvas_h-34
        out.append(f'<g class="legend"><line x1="{margin}" y1="{ly}" x2="{margin+34}" y2="{ly}" '
                   'stroke="#475569" stroke-width="1.7"/>'
                   f'<text x="{margin+42}" y="{ly+4}" font-family="Inter,Arial,sans-serif" '
                   'font-size="10.5" fill="#64748B">sync</text>')
        out.append(f'<line x1="{margin+100}" y1="{ly}" x2="{margin+134}" y2="{ly}" '
                   'stroke="#475569" stroke-width="1.7" stroke-dasharray="7 6"/>'
                   f'<text x="{margin+142}" y="{ly+4}" font-family="Inter,Arial,sans-serif" '
                   'font-size="10.5" fill="#64748B">async/event</text></g>')

    out.append("</svg>")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out), encoding="utf-8")
    print(f"rendered: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
