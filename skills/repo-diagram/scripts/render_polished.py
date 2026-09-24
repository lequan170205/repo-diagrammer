#!/usr/bin/env python3
"""Auto-repair loop for polished native architecture renders.

The loop never changes semantic IR. It only retries presentation geometry with
progressively roomier spacing, then accepts the first render that passes the strict
geometry gate.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:
    print("AUTO-REPAIR unavailable: install PyYAML", file=sys.stderr)
    raise SystemExit(2)

from density_planner import (
    DEFAULT_CONTEXT_NODES,
    DEFAULT_DETAIL_NODES,
    DEFAULT_MAX_NODES,
    DEFAULT_OVERVIEW_NODES,
    should_split,
    write_plan,
)

REPAIRABLE = {
    "NODE_OVERLAP",
    "EDGE_NODE_CROSSING",
    "EDGE_EDGE_CROSSING",
    "EDGE_EDGE_OVERLAP",
    "LABEL_NODE_COLLISION",
    "LABEL_LABEL_COLLISION",
    "LABEL_EDGE_COLLISION",
    "REGION_HEADER_COLLISION",
    "PORT_CONGESTION",
    "CROSSING_BUDGET",
}

NON_REPAIRABLE = {
    "REGION_MEMBER_OUTSIDE",
    "REGION_CAPTURES_UNRELATED_NODE",
    "AMBIGUOUS_REGION_OVERLAP",
    "NON_ORTHOGONAL_ROUTE",
}


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--max-passes", type=int, default=4)
    ap.add_argument("--keep-attempts", action="store_true")
    ap.add_argument("--no-auto-split", action="store_true",
                    help="render this already-bounded view without density splitting")
    ap.add_argument("--split-dir", type=Path, default=None)
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    spec_validator = script_dir / "validate_spec.py"
    validated_spec = run([sys.executable, str(spec_validator), str(args.spec)])
    if validated_spec.returncode != 0:
        print(validated_spec.stdout, end="")
        print(validated_spec.stderr, end="", file=sys.stderr)
        print("POLISHED RENDER STOP: source spec failed semantic/type validation.", file=sys.stderr)
        return validated_spec.returncode

    doc = yaml.safe_load(args.spec.read_text(encoding="utf-8")) or {}
    layout = doc.get("layout") or {}
    crossing_target = int(layout.get("crossing_target", 0) or 0)

    auto_split_cfg = layout.get("auto_split", {})
    if auto_split_cfg is False:
        auto_split_cfg = {"enabled": False}
    elif auto_split_cfg is True:
        auto_split_cfg = {"enabled": True}
    elif not isinstance(auto_split_cfg, dict):
        auto_split_cfg = {}
    enabled = bool(auto_split_cfg.get("enabled", True))
    max_nodes = int(auto_split_cfg.get("max_nodes", DEFAULT_MAX_NODES) or DEFAULT_MAX_NODES)
    detail_nodes = int(auto_split_cfg.get("detail_nodes", DEFAULT_DETAIL_NODES) or DEFAULT_DETAIL_NODES)
    overview_nodes = int(auto_split_cfg.get("overview_nodes", DEFAULT_OVERVIEW_NODES) or DEFAULT_OVERVIEW_NODES)
    context_nodes = int(auto_split_cfg.get("context_nodes", DEFAULT_CONTEXT_NODES) or DEFAULT_CONTEXT_NODES)

    if enabled and not args.no_auto_split:
        needs_split, reasons, metrics = should_split(doc, max_nodes=max_nodes)
        if needs_split:
            split_dir = args.split_dir or (args.output.parent / f"{args.output.stem}.set")
            result = write_plan(
                args.spec,
                split_dir,
                force=True,
                max_nodes=max_nodes,
                max_detail_nodes=detail_nodes,
                overview_nodes=overview_nodes,
                context_nodes=context_nodes,
            )
            print(
                "AUTO-SPLIT: "
                + "; ".join(reasons)
                + f" — generating {len(result['views'])} bounded views"
            )
            manifest_path = split_dir / "diagram-set.yaml"
            validator = script_dir / "validate_split_set.py"
            validated = run([
                sys.executable,
                str(validator),
                str(args.spec),
                str(manifest_path),
            ])
            if validated.returncode != 0:
                print(validated.stdout, end="")
                print(validated.stderr, end="", file=sys.stderr)
                return validated.returncode
            print(validated.stdout, end="")

            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            manifest_by_id = {str(v.get("id")): v for v in (manifest.get("views") or [])}

            for view in result["views"]:
                view_id = str(view["id"])
                spec_path = split_dir / str(view["spec"])
                if view_id == "overview":
                    svg_path = args.output
                else:
                    svg_path = split_dir / f"{view_id}.svg"
                cmd = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    str(spec_path),
                    str(svg_path),
                    "--max-passes",
                    str(args.max_passes),
                    "--no-auto-split",
                ]
                if args.keep_attempts:
                    cmd.append("--keep-attempts")
                rendered_view = run(cmd)
                if rendered_view.returncode != 0:
                    print(rendered_view.stdout, end="")
                    print(rendered_view.stderr, end="", file=sys.stderr)
                    return rendered_view.returncode
                entry = manifest_by_id.get(view_id)
                if entry is not None:
                    entry["svg"] = str(svg_path.name if svg_path.parent == split_dir else svg_path)
            manifest["auto_split"] = {
                "enabled": True,
                "reasons": reasons,
                "source_metrics": metrics,
                "overview_output": str(args.output),
            }
            manifest_path.write_text(
                yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            print(
                f"AUTO-SPLIT PASS: overview={args.output}; "
                f"details={split_dir}; manifest={manifest_path}"
            )
            return 0

    renderer = script_dir / "render_architecture_svg.py"
    analyzer = script_dir / "visual_analyze_svg.py"

    scales = [1.0, 1.12, 1.28, 1.48, 1.7][:max(1, args.max_passes)]
    attempts_root = args.output.parent / (args.output.stem + ".repair-attempts")

    with tempfile.TemporaryDirectory(prefix="repo-diagrammer-repair-") as tmp:
        tmpdir = Path(tmp)
        last_findings = []
        best = None
        best_blocking = 10**9

        for idx, scale in enumerate(scales, start=1):
            svg = tmpdir / f"pass-{idx}.svg"
            report = tmpdir / f"pass-{idx}.json"

            rendered = run([
                sys.executable, str(renderer), str(args.spec), str(svg),
                "--spacing-scale", str(scale),
            ])
            if rendered.returncode != 0:
                print(rendered.stdout, end="")
                print(rendered.stderr, end="", file=sys.stderr)
                return rendered.returncode

            checked = run([
                sys.executable, str(analyzer), str(svg), "--strict",
                "--max-crossings", str(crossing_target), "--json", str(report),
            ])
            data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
            findings = data.get("findings") or []
            blocking = [f for f in findings if f.get("severity") == "blocking"]
            codes = {f.get("code") for f in blocking}
            last_findings = findings

            if len(blocking) < best_blocking:
                best_blocking = len(blocking)
                best = svg

            print(
                f"AUTO-REPAIR pass {idx}/{len(scales)}: spacing={scale:.2f}, "
                f"blocking={len(blocking)}, crossings={data.get('crossings', '?')}"
            )
            for finding in blocking:
                print(f"  BLOCKING {finding.get('code')}: {finding.get('message')}")

            if checked.returncode == 0:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(svg, args.output)
                print(f"AUTO-REPAIR PASS: {args.output} after {idx} pass(es)")
                if args.keep_attempts:
                    attempts_root.mkdir(parents=True, exist_ok=True)
                    for candidate in tmpdir.iterdir():
                        shutil.copyfile(candidate, attempts_root / candidate.name)
                return 0

            if codes & NON_REPAIRABLE:
                print(
                    "AUTO-REPAIR STOP: blocking defect requires model/grouping correction, "
                    "not more spacing.",
                    file=sys.stderr,
                )
                break

            if not (codes & REPAIRABLE):
                print(
                    "AUTO-REPAIR STOP: no supported automatic repair applies to remaining defects.",
                    file=sys.stderr,
                )
                break

        if args.keep_attempts:
            attempts_root.mkdir(parents=True, exist_ok=True)
            for candidate in tmpdir.iterdir():
                shutil.copyfile(candidate, attempts_root / candidate.name)

        print(
            f"AUTO-REPAIR FAILED: best pass still has {best_blocking} blocking defect(s).",
            file=sys.stderr,
        )
        for finding in last_findings:
            if finding.get("severity") == "blocking":
                print(
                    f"  {finding.get('code')}: {finding.get('message')}",
                    file=sys.stderr,
                )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
