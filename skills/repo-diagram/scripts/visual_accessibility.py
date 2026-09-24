#!/usr/bin/env python3
"""Accessibility/readability checks for Repo Diagrammer native SVG output."""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    ids: list[str]


def tag(el):
    return el.tag.rsplit("}", 1)[-1]


def classes(el):
    return set((el.attrib.get("class") or "").split())


def parse_color(value):
    value = str(value or "").strip().lower()
    if value in {"none", "transparent", ""}:
        return None
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return tuple(int(ch * 2, 16) for ch in value[1:])
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    m = re.fullmatch(
        r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
        value,
    )
    if m:
        return tuple(max(0, min(255, int(x))) for x in m.groups())
    return None


def blend(fg, bg, opacity):
    if fg is None:
        return bg
    opacity = max(0.0, min(1.0, float(opacity)))
    return tuple(round(fg[i] * opacity + bg[i] * (1.0-opacity)) for i in range(3))


def channel_luminance(value):
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = [channel_luminance(v) for v in rgb]
    return 0.2126*r + 0.7152*g + 0.0722*b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def descendants(el, wanted):
    return [x for x in el.iter() if tag(x) == wanted]


def first_descendant(el, wanted):
    for x in el.iter():
        if tag(x) == wanted:
            return x
    return None


def text_threshold(text_el):
    size_raw = str(text_el.attrib.get("font-size") or "0")
    m = re.search(r"-?\d+(?:\.\d+)?", size_raw)
    size = float(m.group()) if m else 0.0
    weight = str(text_el.attrib.get("font-weight") or "400").lower()
    bold = weight in {"bold", "600", "700", "800", "900"}
    # WCAG large text: >=18pt regular or >=14pt bold. Native SVG uses px, so use
    # conservative 24px / ~18.7px equivalents.
    large = size >= 24.0 or (bold and size >= 18.7)
    return 3.0 if large else 4.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", type=Path)
    ap.add_argument("--json", dest="json_path", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        root = ET.parse(args.svg).getroot()
    except Exception as exc:
        print(f"ACCESSIBILITY ERROR: {exc}", file=sys.stderr)
        return 2

    findings = []
    white = (255, 255, 255)

    if root.attrib.get("role") != "img":
        findings.append(Finding("blocking", "ROOT_ROLE_MISSING",
                                "SVG root must expose role=img", []))
    labelledby = set((root.attrib.get("aria-labelledby") or "").split())
    ids = {el.attrib.get("id") for el in root.iter() if el.attrib.get("id")}
    if not labelledby or not labelledby <= ids:
        findings.append(Finding(
            "blocking", "ROOT_ACCESSIBLE_NAME_MISSING",
            "SVG root aria-labelledby must reference existing title/description IDs", []
        ))

    native_nodes = []
    native_edges = []
    edge_styles = {"true": [], "false": []}
    roles_present = set()

    for el in root.iter():
        if tag(el) != "g":
            continue

        node_id = el.attrib.get("data-node-id")
        if node_id:
            native_nodes.append(node_id)
            role = el.attrib.get("data-node-role")
            if role:
                roles_present.add(role)
            if not (el.attrib.get("aria-label") or "").strip():
                findings.append(Finding(
                    "blocking", "NODE_ACCESSIBLE_NAME_MISSING",
                    f"node {node_id} has no accessible name", [node_id]
                ))
            rect = first_descendant(el, "rect")
            if rect is None:
                continue
            bg = parse_color(rect.attrib.get("fill")) or white
            bg = blend(bg, white, float(rect.attrib.get("fill-opacity") or 1.0))
            for text_el in descendants(el, "text"):
                fg = parse_color(text_el.attrib.get("fill"))
                if fg is None:
                    continue
                ratio = contrast(fg, bg)
                threshold = text_threshold(text_el)
                if ratio + 1e-6 < threshold:
                    role_name = text_el.attrib.get("data-text-role") or "text"
                    findings.append(Finding(
                        "blocking", "LOW_TEXT_CONTRAST",
                        f"node {node_id} {role_name} contrast {ratio:.2f}:1 < {threshold:.1f}:1",
                        [node_id]
                    ))

        edge_id = el.attrib.get("data-edge-id")
        if edge_id:
            native_edges.append(edge_id)
            if not (el.attrib.get("aria-label") or "").strip():
                findings.append(Finding(
                    "blocking", "EDGE_ACCESSIBLE_NAME_MISSING",
                    f"edge {edge_id} has no accessible name", [edge_id]
                ))
            sync = el.attrib.get("data-sync")
            path = first_descendant(el, "path")
            if path is None:
                continue
            stroke = parse_color(path.attrib.get("stroke"))
            if stroke is not None:
                ratio = contrast(stroke, white)
                if ratio < 3.0:
                    findings.append(Finding(
                        "blocking", "LOW_EDGE_CONTRAST",
                        f"edge {edge_id} contrast {ratio:.2f}:1 < 3.0:1",
                        [edge_id]
                    ))
            if sync in edge_styles:
                edge_styles[sync].append({
                    "id": edge_id,
                    "dash": str(path.attrib.get("stroke-dasharray") or "").strip(),
                })

    # Global/native text is rendered against white or nearly-white canvas/regions.
    node_text_ids = {
        id(text_el)
        for group in root.iter()
        if tag(group) == "g" and group.attrib.get("data-node-id")
        for text_el in descendants(group, "text")
    }
    for text_el in root.iter():
        if tag(text_el) != "text" or id(text_el) in node_text_ids:
            continue
        fg = parse_color(text_el.attrib.get("fill"))
        if fg is None:
            continue
        ratio = contrast(fg, white)
        threshold = text_threshold(text_el)
        if ratio + 1e-6 < threshold:
            role_name = text_el.attrib.get("data-text-role") or "text"
            findings.append(Finding(
                "blocking", "LOW_GLOBAL_TEXT_CONTRAST",
                f"{role_name} contrast {ratio:.2f}:1 < {threshold:.1f}:1",
                []
            ))

    # When both sync and async edges exist, async must have a non-colour encoding.
    if edge_styles["true"] and edge_styles["false"]:
        bad_async = [x["id"] for x in edge_styles["false"] if not x["dash"]]
        bad_sync = [x["id"] for x in edge_styles["true"] if x["dash"]]
        if bad_async or bad_sync:
            findings.append(Finding(
                "blocking", "EDGE_SEMANTICS_COLOR_ONLY",
                "sync/async edge semantics must differ by dash pattern, not only colour",
                bad_async + bad_sync
            ))

    # Context nodes already use opacity; require dash as a second channel.
    for el in root.iter():
        if tag(el) != "g" or el.attrib.get("data-visual-scope") != "context":
            continue
        nid = el.attrib.get("data-node-id") or "context"
        rect = first_descendant(el, "rect")
        if rect is not None and not str(rect.attrib.get("stroke-dasharray") or "").strip():
            findings.append(Finding(
                "blocking", "CONTEXT_SEMANTICS_COLOR_ONLY",
                f"context node {nid} must use a non-colour border pattern",
                [nid]
            ))

    report = {
        "file": str(args.svg),
        "nodes": len(native_nodes),
        "edges": len(native_edges),
        "roles": sorted(roles_present),
        "findings": [asdict(f) for f in findings],
    }
    print(
        f"ACCESSIBILITY: {args.svg.name} — {len(native_nodes)} nodes, "
        f"{len(native_edges)} edges, {len(findings)} finding(s)"
    )
    for finding in findings:
        print(f"  {finding.severity.upper()} {finding.code}: {finding.message}")
    if not findings:
        print("  PASS: contrast, accessible names and non-colour semantic encodings passed")

    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.strict and any(f.severity == "blocking" for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
