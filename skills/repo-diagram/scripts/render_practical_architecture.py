#!/usr/bin/env python3
"""Deterministic poster renderer for practical high-level architecture views.

Input: Repo Diagrammer YAML spec with presentation.style=polished-overview and
presentation.projection enabled.
Output: SVG; optional PNG when cairosvg is installed.

This renderer is intentionally not a general graph layout engine. It preserves the
poster regions declared in layout.regions so practical fallback rendering cannot
degrade into raw auto-layout.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

import yaml

PALETTE = {
    "clients": ("#EAF3FF", "#2F80ED"),
    "ingress": ("#EAF3FF", "#2F80ED"),
    "api": ("#F5F0FF", "#8B5CF6"),
    "realtime": ("#FFF1F2", "#F87171"),
    "messaging": ("#FFF7E6", "#F59E0B"),
    "processing": ("#EFF6FF", "#3B82F6"),
    "observability": ("#ECFDF9", "#14B8A6"),
    "data": ("#F8FAFC", "#64748B"),
    "external": ("#FFF5F5", "#EF4444"),
    "domain": ("#ECFDF5", "#34A853"),
    "default": ("#F8FAFC", "#64748B"),
}

ROLE_BY_ID = {
    "clients": "clients",
    "nginx": "ingress",
    "api_gateway": "api",
    "rabbitmq": "messaging",
    "monitoring": "observability",
}


def esc(value):
    return html.escape(str(value or ""))


def txt(x, y, value, size=14, weight=400, fill="#0F172A", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="Inter,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{esc(value)}</text>'
    )


def rect(x, y, w, h, fill, stroke, radius=12, width=1.5, extra=""):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{width}" {extra}/>'
    )


def arrow(points, stroke="#2563EB", width=1.5, dash=None):
    d = "M " + " L ".join(f"{x},{y}" for x, y in points)
    marker = (
        "arrow-red"
        if stroke == "#DC2626"
        else "arrow-amber"
        if stroke == "#D97706"
        else "arrow-blue"
    )
    attrs = (
        f'fill="none" stroke="{stroke}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round" '
        f'marker-end="url(#{marker})"'
    )
    if dash:
        attrs += f' stroke-dasharray="{dash}"'
    return f'<path d="{d}" {attrs}/>'


def label(out, x, y, value, color="#334155"):
    if not value:
        return
    width = max(58, min(225, 6.1 * len(str(value)) + 14))
    out.append(rect(x - width / 2, y - 13, width, 22, "#FFFFFF", "#FFFFFF", 6, 0))
    out.append(txt(x, y + 2, value, 9.6, 500, color, "middle"))


def role_for(node_id, node, composite):
    if composite:
        return composite.get("semantic_role") or "default"
    return (
        node.get("semantic_role")
        or ROLE_BY_ID.get(node_id)
        or ("external" if node.get("kind") == "external-system" else "default")
    )


def anchor(pos, side):
    x, y, w, h = pos
    return {
        "top": (x + w / 2, y),
        "bottom": (x + w / 2, y + h),
        "left": (x, y + h / 2),
        "right": (x + w, y + h / 2),
    }[side]


def draw_card(out, node_id, node, composite, pos, nodes, region=None, copy=None):
    x, y, w, h = pos
    copy = copy or {}
    role = role_for(node_id, node, composite)
    fill, stroke = PALETTE.get(role, PALETTE["default"])
    out.append(rect(x, y, w, h, fill, stroke, 12, 1.6, 'filter="url(#shadow)"'))

    title = (
        copy.get("title")
        or (composite or {}).get("label")
        or node.get("display_label")
        or node.get("label")
        or node_id
    )
    out.append(txt(x + w / 2, y + 25, title, 16, 700, "#0F172A", "middle"))

    if composite:
        members = composite.get("members") or []
        if region == "right":
            cy, ch, gap = y + 48, 42, 8
            for member in members:
                member_label = (nodes.get(member) or {}).get("label", member)
                out.append(rect(x + 16, cy, w - 32, ch, "#FFFFFF", stroke, 8, 1.0))
                out.append(
                    txt(x + w / 2, cy + 25, member_label, 10.2, 600, "#334155", "middle")
                )
                cy += ch + gap
        elif len(members) <= 3 and h >= 100:
            gap = 8
            inner_x = x + 12
            inner_w = w - 24
            chip_w = (inner_w - gap * (len(members) - 1)) / max(len(members), 1)
            cy, ch = y + 42, 42
            for index, member in enumerate(members):
                mx = inner_x + index * (chip_w + gap)
                member_label = (nodes.get(member) or {}).get("label", member)
                font_size = 9.3 if len(member_label) > 20 else 10.4
                out.append(rect(mx, cy, chip_w, ch, "#FFFFFF", stroke, 8, 1.0))
                out.append(
                    txt(mx + chip_w / 2, cy + 25, member_label, font_size, 600, "#334155", "middle")
                )
        else:
            member_labels = " · ".join(
                (nodes.get(member) or {}).get("label", member) for member in members
            )
            out.append(txt(x + w / 2, y + 48, member_labels, 10.3, 500, "#334155", "middle"))

        responsibility = composite.get("responsibility") or ""
        if responsibility:
            out.append(
                txt(x + w / 2, y + h - 13, responsibility, 9.8, 400, "#64748B", "middle")
            )
    else:
        tech = copy.get("tech", node.get("tech") or "")
        detail = copy.get("detail", "")
        if tech:
            out.append(txt(x + w / 2, y + 48, tech, 10.5, 500, "#334155", "middle"))
        if detail:
            out.append(txt(x + w / 2, y + 68, detail, 9.7, 400, "#64748B", "middle"))


def assign_positions(regions):
    positions = {}
    for node_id in regions.get("top", []):
        positions[node_id] = (600, 34, 400, 94)
    for node_id in regions.get("ingress", []):
        positions[node_id] = (310, 220, 760, 88)

    core = regions.get("core", [])
    core_slots = [(160, 360, 255, 98), (485, 350, 390, 118), (930, 360, 255, 98)]
    if len(core) == 1:
        core_slots = [(545, 355, 390, 108)]
    elif len(core) == 2:
        core_slots = [(300, 355, 330, 108), (750, 355, 330, 108)]
    for node_id, pos in zip(core, core_slots):
        positions[node_id] = pos

    for index, node_id in enumerate(regions.get("messaging", [])):
        positions[node_id] = (470 + index * 290, 520, 270, 92)

    support_slots = [(315, 655, 390, 112), (735, 655, 390, 112)]
    for node_id, pos in zip(regions.get("support", []), support_slots):
        positions[node_id] = pos

    for node_id in regions.get("right", []):
        positions[node_id] = (1250, 330, 300, 240)
    for node_id in regions.get("bottom-left", []):
        positions[node_id] = (250, 835, 540, 155)
    for node_id in regions.get("bottom-center", []):
        positions[node_id] = (585, 835, 430, 155)
    for node_id in regions.get("bottom-right", []):
        positions[node_id] = (850, 835, 540, 155)

    return positions


def route_edge(source, target, style, positions, region_of):
    sr, tr = region_of.get(source, ""), region_of.get(target, "")
    sp, tp = positions[source], positions[target]

    if style == "media" and sr == "top" and tr == "core":
        p1 = anchor(sp, "right")
        p4 = anchor(tp, "top")
        corridor = 1125
        return [p1, (corridor, p1[1]), (corridor, p4[1] - 20), (p4[0], p4[1] - 20), p4], (1055, 150)

    if tr == "right" and sr == "core":
        p1 = anchor(sp, "top")
        p4 = anchor(tp, "left")
        topcorr, rightcorr = 322, 1170
        return [p1, (p1[0], topcorr), (rightcorr, topcorr), (rightcorr, p4[1]), p4], (1060, topcorr - 9)

    if tr == "right" and sr == "support":
        p1 = anchor(sp, "right")
        p4 = anchor(tp, "bottom")
        rightcorr = 1180
        return [p1, (rightcorr, p1[1]), (rightcorr, p4[1] + 24), (p4[0], p4[1] + 24), p4], (1080, p1[1] - 9)

    if tr == "bottom-left" and sr == "core":
        p1 = anchor(sp, "bottom")
        p4 = anchor(tp, "top")
        corridor, bottomcorr = 820, 806
        return [p1, (corridor, p1[1]), (corridor, bottomcorr), (p4[0], bottomcorr), p4], (610, bottomcorr - 8)

    if tr == "bottom-right":
        p1 = anchor(sp, "bottom")
        p4 = anchor(tp, "top")
        return [p1, (p1[0], p4[1] - 24), (p4[0], p4[1] - 24), p4], ((p1[0] + p4[0]) / 2, p4[1] - 31)

    if sr == "messaging" and tr == "core":
        p1 = anchor(sp, "top")
        p4 = anchor(tp, "bottom")
        return [p1, (p1[0], p4[1] + 28), (p4[0], p4[1] + 28), p4], ((p1[0] + p4[0]) / 2, p4[1] + 21)

    if sr == "messaging" and tr == "support":
        p1 = anchor(sp, "bottom")
        p4 = anchor(tp, "top")
        return [p1, p4], (p1[0] + 55, (p1[1] + p4[1]) / 2)

    # Generic orthogonal fallback inside the already planned poster regions.
    sx, sy, sw, sh = sp
    tx, ty, tw, th = tp
    sc, tc = (sx + sw / 2, sy + sh / 2), (tx + tw / 2, ty + th / 2)
    vx, vy = tc[0] - sc[0], tc[1] - sc[1]
    if abs(vx) > abs(vy) * 1.35:
        ss, ts = ("right", "left") if vx > 0 else ("left", "right")
        p1, p4 = anchor(sp, ss), anchor(tp, ts)
        midx = (p1[0] + p4[0]) / 2
        return [p1, (midx, p1[1]), (midx, p4[1]), p4], (midx, (p1[1] + p4[1]) / 2 - 7)

    ss, ts = ("bottom", "top") if vy > 0 else ("top", "bottom")
    p1, p4 = anchor(sp, ss), anchor(tp, ts)
    midy = (p1[1] + p4[1]) / 2
    return [p1, (p1[0], midy), (p4[0], midy), p4], ((p1[0] + p4[0]) / 2, midy - 7)


def render(spec_path: Path, svg_path: Path, png_path: Path | None = None):
    doc = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    presentation = doc.get("presentation") or {}
    projection = presentation.get("projection") or {}
    if presentation.get("style") != "polished-overview" or projection.get("enabled") is not True:
        raise SystemExit("practical poster renderer requires polished-overview with projection.enabled=true")

    nodes = {node["id"]: node for node in doc.get("nodes", []) if isinstance(node, dict) and node.get("id")}
    composites = {
        composite["id"]: composite
        for composite in projection.get("composites", [])
        if isinstance(composite, dict) and composite.get("id")
    }
    visible = projection.get("visible_nodes") or []
    copy_map = projection.get("copy") or {}
    regions = (doc.get("layout") or {}).get("regions") or {}

    region_of = {}
    for region, ids in regions.items():
        if isinstance(ids, list):
            for node_id in ids:
                region_of[node_id] = region

    positions = assign_positions(regions)
    missing = [node_id for node_id in visible if node_id not in positions]
    if missing:
        raise SystemExit(f"visible projection nodes missing poster region placement: {missing}")

    width, height = 1600, 1040
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1.2" stdDeviation="1.8" flood-color="#0F172A" flood-opacity="0.08"/></filter>',
        '<marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2563EB"/></marker>',
        '<marker id="arrow-amber" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#D97706"/></marker>',
        '<marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#DC2626"/></marker>',
        '</defs>',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
    ]

    title = presentation.get("title") or "Architecture"
    subtitle = presentation.get("subtitle") or ""
    out += [txt(34, 45, title, 26, 750), txt(36, 69, subtitle, 11, 400, "#64748B")]

    # Owned runtime boundary. This is a visual treatment of the real boundary already
    # present in the spec; the renderer never invents new members.
    out.append(
        '<rect x="115" y="180" width="1080" height="610" rx="16" fill="#FFFFFF" '
        'fill-opacity="0.28" stroke="#3B82F6" stroke-width="1.3" stroke-dasharray="8 7"/>'
    )
    out.append(txt(140, 204, "Velora backend · owned runtime", 16, 700, "#1D4ED8"))

    edge_layer, label_layer = [], []
    for edge in projection.get("visible_edges") or []:
        source, target = edge.get("from"), edge.get("to")
        if source not in positions or target not in positions:
            continue
        points, label_pos = route_edge(
            source, target, edge.get("style"), positions, region_of
        )
        style = edge.get("style")
        if style == "async":
            color, line_width, dash, label_color = "#D97706", 1.6, "7 5", "#B45309"
        elif style == "media":
            color, line_width, dash, label_color = "#DC2626", 2.6, None, "#DC2626"
        else:
            color, line_width, dash, label_color = "#2563EB", 1.45, None, "#334155"
        edge_layer.append(arrow(points, color, line_width, dash))
        label(label_layer, label_pos[0], label_pos[1], edge.get("label", ""), label_color)

    out += edge_layer

    for node_id in visible:
        draw_card(
            out,
            node_id,
            nodes.get(node_id, {}),
            composites.get(node_id),
            positions[node_id],
            nodes,
            region_of.get(node_id),
            copy_map.get(node_id),
        )

    out += label_layer

    # Compact legend.
    lx, ly, lw, lh = 30, 855, 180, 126
    out.append(rect(lx, ly, lw, lh, "#FFFFFF", "#CBD5E1", 10, 1.0))
    out.append(txt(lx + 12, ly + 22, "Legend", 12, 700))
    out.append(arrow([(lx + 14, ly + 47), (lx + 52, ly + 47)], "#2563EB", 1.6))
    out.append(txt(lx + 64, ly + 51, "Sync / network", 9.5, 500, "#334155"))
    out.append(arrow([(lx + 14, ly + 74), (lx + 52, ly + 74)], "#D97706", 1.6, "7 5"))
    out.append(txt(lx + 64, ly + 78, "RabbitMQ async", 9.5, 500, "#334155"))
    out.append(arrow([(lx + 14, ly + 101), (lx + 52, ly + 101)], "#DC2626", 2.6))
    out.append(txt(lx + 64, ly + 105, "WebRTC media", 9.5, 500, "#334155"))

    out.append("</svg>")
    svg = "\n".join(out)
    svg_path.write_text(svg, encoding="utf-8")

    if png_path:
        try:
            import cairosvg
        except ImportError:
            print("PNG skipped: cairosvg is not installed", file=sys.stderr)
        else:
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                write_to=str(png_path),
                output_width=width * 2,
                output_height=height * 2,
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    parser.add_argument("svg")
    parser.add_argument("--png")
    args = parser.parse_args()
    render(Path(args.spec), Path(args.svg), Path(args.png) if args.png else None)


if __name__ == "__main__":
    main()
