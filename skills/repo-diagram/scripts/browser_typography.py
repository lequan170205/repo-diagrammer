#!/usr/bin/env python3
"""Measure rendered SVG typography with a real headless browser.

Uses SVG getBBox() inside Chrome/Chromium. No Puppeteer package is required.
When no browser is available the checker reports an explicit unverified fallback
unless --required is supplied.
"""
from __future__ import annotations

import argparse
import glob
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_browser():
    explicit = os.environ.get("CHROME_BIN")
    if explicit and Path(explicit).exists():
        return explicit

    names = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "chrome-headless-shell",
    ]
    for name in names:
        found = shutil.which(name)
        if found:
            return found

    common = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
    ]
    for candidate in common:
        if Path(candidate).exists():
            return candidate

    cache_patterns = [
        str(Path.home() / ".cache/puppeteer/chrome-headless-shell/*/*/chrome-headless-shell"),
        str(Path.home() / ".cache/puppeteer/chrome/*/*/chrome"),
    ]
    for pattern in cache_patterns:
        matches = sorted(glob.glob(pattern), reverse=True)
        if matches:
            return matches[0]
    return None


JS = r"""
(async function () {
  try {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }
    const svg = document.querySelector("svg");
    const findings = [];
    const measured = {nodes: 0, edgeLabels: 0, regions: 0, texts: 0};

    function box(el) {
      const b = el.getBBox();
      return {x: b.x, y: b.y, width: b.width, height: b.height,
              right: b.x + b.width, bottom: b.y + b.height};
    }
    function contains(outer, inner, pad) {
      return inner.x >= outer.x + pad &&
             inner.right <= outer.right - pad &&
             inner.y >= outer.y + pad &&
             inner.bottom <= outer.bottom - pad;
    }
    function intersects(a, b, pad) {
      return Math.min(a.right, b.right) - Math.max(a.x, b.x) > pad &&
             Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > pad;
    }
    function add(code, severity, message, ids) {
      findings.push({code, severity, message, ids: ids || []});
    }

    const vb = svg.viewBox && svg.viewBox.baseVal
      ? {x: svg.viewBox.baseVal.x, y: svg.viewBox.baseVal.y,
         width: svg.viewBox.baseVal.width, height: svg.viewBox.baseVal.height}
      : {x: 0, y: 0, width: svg.clientWidth, height: svg.clientHeight};
    vb.right = vb.x + vb.width;
    vb.bottom = vb.y + vb.height;

    for (const group of svg.querySelectorAll("[data-node-id]")) {
      const id = group.getAttribute("data-node-id");
      const rect = group.querySelector("rect");
      const texts = Array.from(group.querySelectorAll("text"));
      if (!rect) continue;
      measured.nodes += 1;
      const rb = box(rect);
      const textBoxes = [];
      for (const text of texts) {
        const tb = box(text);
        textBoxes.push(tb);
        const fontSize = parseFloat(getComputedStyle(text).fontSize || "0");
        if (!contains(rb, tb, 5)) {
          add("TEXT_OVERFLOW", "blocking",
              "node " + id + " text extends outside its box", [id]);
        }
        if (fontSize > 0 && fontSize < 8.5) {
          add("TEXT_TOO_SMALL", "blocking",
              "node " + id + " text renders at " + fontSize.toFixed(1) + "px", [id]);
        }
      }
      for (let i = 0; i < textBoxes.length; i++) {
        for (let j = i + 1; j < textBoxes.length; j++) {
          if (intersects(textBoxes[i], textBoxes[j], 0.5)) {
            add("TEXT_LINE_COLLISION", "blocking",
                "node " + id + " text lines overlap", [id]);
          }
        }
      }
    }

    for (const group of svg.querySelectorAll("[data-edge-label-id]")) {
      const id = group.getAttribute("data-edge-label-id");
      const rect = group.querySelector("rect");
      const text = group.querySelector("text");
      if (!rect || !text) continue;
      measured.edgeLabels += 1;
      const rb = box(rect);
      const tb = box(text);
      const fontSize = parseFloat(getComputedStyle(text).fontSize || "0");
      if (!contains(rb, tb, 3)) {
        add("EDGE_LABEL_TEXT_OVERFLOW", "blocking",
            "edge label " + id + " text extends outside its label box", [id]);
      }
      if (fontSize > 0 && fontSize < 9) {
        add("EDGE_LABEL_TEXT_TOO_SMALL", "blocking",
            "edge label " + id + " renders at " + fontSize.toFixed(1) + "px", [id]);
      }
    }

    const regionHeaderBoxes = [];
    for (const group of svg.querySelectorAll("[data-region-kind]")) {
      const id = group.getAttribute("data-boundary-id") ||
                 group.getAttribute("data-group-id") || "region";
      const rect = group.querySelector("rect");
      const text = group.querySelector("text");
      if (!rect || !text) continue;
      measured.regions += 1;
      const rb = box(rect);
      const tb = box(text);
      const fontSize = parseFloat(getComputedStyle(text).fontSize || "0");
      const header = {x: rb.x, y: rb.y, width: rb.width,
                      height: Math.min(24, rb.height),
                      right: rb.right, bottom: rb.y + Math.min(24, rb.height)};
      if (!contains(header, tb, 3)) {
        add("REGION_TEXT_OVERFLOW", "blocking",
            "region " + id + " header text does not fit", [id]);
      }
      if (fontSize > 0 && fontSize < 8.5) {
        add("REGION_TEXT_TOO_SMALL", "blocking",
            "region " + id + " header renders at " + fontSize.toFixed(1) + "px", [id]);
      }
      regionHeaderBoxes.push({id, box: tb});
    }
    for (let i = 0; i < regionHeaderBoxes.length; i++) {
      for (let j = i + 1; j < regionHeaderBoxes.length; j++) {
        if (intersects(regionHeaderBoxes[i].box, regionHeaderBoxes[j].box, 0.5)) {
          add("REGION_HEADER_TEXT_COLLISION", "blocking",
              "region headers overlap: " + regionHeaderBoxes[i].id + " / " +
              regionHeaderBoxes[j].id,
              [regionHeaderBoxes[i].id, regionHeaderBoxes[j].id]);
        }
      }
    }

    const roleMinimums = {
      "title": 20,
      "subtitle": 10.5,
      "row-heading": 9,
      "legend": 9,
    };
    const hierarchyByRole = {};
    for (const text of svg.querySelectorAll("[data-text-role]")) {
      const role = text.getAttribute("data-text-role") || "";
      const minSize = roleMinimums[role];
      if (minSize) {
        const fontSize = parseFloat(getComputedStyle(text).fontSize || "0");
        if (fontSize > 0 && fontSize < minSize) {
          add(role.toUpperCase().replaceAll("-", "_") + "_TEXT_TOO_SMALL",
              "blocking",
              role + " text renders at " + fontSize.toFixed(1) + "px", [role]);
        }
      }
      if (["title", "subtitle", "row-heading", "legend"].includes(role)) {
        if (!hierarchyByRole[role]) hierarchyByRole[role] = [];
        hierarchyByRole[role].push(box(text));
      }
    }

    const titleBoxes = hierarchyByRole["title"] || [];
    const subtitleBoxes = hierarchyByRole["subtitle"] || [];
    for (const a of titleBoxes) {
      for (const b of subtitleBoxes) {
        if (intersects(a, b, 0.5)) {
          add("TITLE_SUBTITLE_COLLISION", "blocking",
              "title and subtitle text overlap", ["title", "subtitle"]);
        }
      }
    }
    for (const [role, code] of [
      ["row-heading", "ROW_HEADING_COLLISION"],
      ["legend", "LEGEND_TEXT_COLLISION"],
    ]) {
      const boxes = hierarchyByRole[role] || [];
      for (let i = 0; i < boxes.length; i++) {
        for (let j = i + 1; j < boxes.length; j++) {
          if (intersects(boxes[i], boxes[j], 0.5)) {
            add(code, "blocking", role + " text elements overlap", [role]);
          }
        }
      }
    }

    for (const text of svg.querySelectorAll("text")) {
      measured.texts += 1;
      const tb = box(text);
      if (tb.x < vb.x - 1 || tb.y < vb.y - 1 ||
          tb.right > vb.right + 1 || tb.bottom > vb.bottom + 1) {
        add("TEXT_OUTSIDE_CANVAS", "blocking",
            "rendered text lies outside SVG viewBox", []);
      }
    }

    const report = {
      available: true,
      browser: navigator.userAgent,
      findings,
      measured,
    };
    document.getElementById("repo-metrics").textContent = JSON.stringify(report);
  } catch (error) {
    document.getElementById("repo-metrics").textContent = JSON.stringify({
      available: true,
      internalError: String(error && error.stack || error),
      findings: []
    });
  }
})();
"""


def make_html(svg_text):
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{margin:0;padding:0}</style></head><body>"
        + svg_text
        + "<pre id='repo-metrics'></pre><script>"
        + JS
        + "</script></body></html>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", type=Path)
    ap.add_argument("--json", dest="json_path", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--required", action="store_true")
    args = ap.parse_args()

    browser = find_browser()
    if not browser:
        report = {
            "available": False,
            "browser": None,
            "findings": [],
            "message": "Chrome/Chromium unavailable; glyph estimator remains the fallback",
        }
        if args.json_path:
            args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("BROWSER-TYPOGRAPHY: unavailable — estimator fallback only")
        return 2 if args.required else 0

    svg_text = args.svg.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="repo-diagrammer-browser-") as tmp:
        html_path = Path(tmp) / "measure.html"
        html_path.write_text(make_html(svg_text), encoding="utf-8")
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--allow-file-access-from-files",
            "--virtual-time-budget=2000",
            "--dump-dom",
            html_path.resolve().as_uri(),
        ]
        attempts = [
            (cmd, 25),
            ([arg if arg != "--headless=new" else "--headless" for arg in cmd], 40),
        ]
        proc = None
        timeout_errors = []
        for attempt_no, (attempt_cmd, timeout_seconds) in enumerate(attempts, start=1):
            try:
                proc = subprocess.run(
                    attempt_cmd,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                timeout_errors.append(
                    f"attempt {attempt_no} timed out after {timeout_seconds}s"
                )
                continue
            if proc.returncode == 0:
                break

    if proc is None:
        print(
            "BROWSER-TYPOGRAPHY ERROR: browser execution timed out; "
            + "; ".join(timeout_errors),
            file=sys.stderr,
        )
        return 2

    if proc.returncode != 0:
        detail = "; ".join(timeout_errors)
        suffix = f" after {detail}" if detail else ""
        print(
            "BROWSER-TYPOGRAPHY ERROR: browser execution failed" + suffix,
            file=sys.stderr,
        )
        if proc.stderr:
            print(proc.stderr[-2000:], file=sys.stderr)
        return 2

    match = re.search(
        r'<pre id="repo-metrics">(.*?)</pre>',
        proc.stdout,
        flags=re.DOTALL,
    )
    if not match:
        print("BROWSER-TYPOGRAPHY ERROR: measurement payload missing", file=sys.stderr)
        return 2

    try:
        report = json.loads(html_lib.unescape(match.group(1)))
    except Exception as exc:
        print(f"BROWSER-TYPOGRAPHY ERROR: invalid payload: {exc}", file=sys.stderr)
        return 2

    if report.get("internalError"):
        print("BROWSER-TYPOGRAPHY ERROR: " + report["internalError"], file=sys.stderr)
        return 2

    report["browser_executable"] = browser
    findings = report.get("findings") or []
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    measured = report.get("measured") or {}
    print(
        "BROWSER-TYPOGRAPHY: "
        f"{measured.get('nodes', 0)} nodes, "
        f"{measured.get('edgeLabels', 0)} edge labels, "
        f"{measured.get('regions', 0)} regions, "
        f"{measured.get('texts', 0)} text elements"
    )
    for finding in findings:
        print(
            f"  {str(finding.get('severity', 'warning')).upper()} "
            f"{finding.get('code')}: {finding.get('message')}"
        )
    if not findings:
        print("  PASS: actual browser text bounds fit their containers and canvas")

    blocking = [f for f in findings if f.get("severity") == "blocking"]
    if args.strict and blocking:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
