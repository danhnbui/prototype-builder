#!/usr/bin/env python3
"""
r3_figma_entry.py — the R3 "Figma-frame entry" acceptance, fixture-driven (no real Figma / MCP):

  1. resolve_frame.py maps a frame-export's layers to DS components that already exist and emits a
     registry screen patch: mapped layers → elements with `orgId`; unmapped layers → labeled
     placeholders + a gaps.md entry. Sets meta.entry = "figma".
  2. DS fidelity at entry: every emitted `orgId` is a KNOWN component id — nothing is invented. Every
     unmapped layer is accounted for (placeholder element AND a gaps.md line), never silently dropped.
  3. Migration 0005 adds meta.entry (schema 6→7), is up→down reversible, and the template tracks CURRENT_SCHEMA.

Usage:  python3 tests/r3_figma_entry.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOLVE = os.path.join(ROOT, "pb", "tools", "resolve_frame.py")
FRAME = os.path.join(ROOT, "fixtures", "frame-export.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
KNOWN = {"button", "text-input"}  # the DS components present in the test project
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem, os.path.join(ROOT, "pb", "migrations", stem + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    data = json.load(open(TEMPLATE))
    data["meta"]["name"] = "FrameTest"
    data["components"] = [{"id": "button"}, {"id": "text-input"}]  # the known DS components
    json.dump(data, open(reg, "w"))
    shutil.copy(FRAME, os.path.join(d, "frame.json"))

    print("1 · resolve maps layers → screen patch")
    r = subprocess.run([sys.executable, RESOLVE, "--from", os.path.join(d, "frame.json"), "--registry", reg],
                       capture_output=True, text=True)
    check(r.returncode == 0, f"resolve_frame exits 0 ({r.stderr.strip()[:60]})")
    out = json.load(open(reg))
    screens = out.get("screens", [])
    check(len(screens) == 1 and screens[0]["id"] == "checkout", "one screen 'checkout' emitted")
    check(out["meta"].get("entry") == "figma", "meta.entry set to figma")
    els = screens[0]["elements"]
    mapped = [e for e in els if e.get("orgId")]
    placeholders = [e for e in els if e.get("placeholder")]
    check(len(els) == 4 and len(mapped) == 2 and len(placeholders) == 2,
          f"4 layers → 2 mapped + 2 placeholders (got {len(mapped)}/{len(placeholders)})")
    check(screens[0].get("figmaFrameId") == "10:5", "screen keeps the Figma frame id")

    print("2 · DS fidelity — nothing invented, nothing dropped")
    orgids = {e["orgId"] for e in mapped}
    check(orgids <= KNOWN, f"every orgId is a known DS component (got {orgids})")
    check(all("orgId" not in e for e in placeholders), "placeholders carry NO orgId (not invented)")
    gaps_path = os.path.join(d, "gaps.md")
    check(os.path.isfile(gaps_path), "gaps.md written")
    gaps = open(gaps_path).read() if os.path.isfile(gaps_path) else ""
    check("Promo Banner" in gaps and "Live Chat Bubble" in gaps, "both unmapped layers logged to gaps.md")
    check(gaps.count("\n- ") == 2, "exactly the 2 unmapped layers are logged (none extra, none missing)")

print("3 · migration 0005 + schema")
man = _load("manifest")
m5 = _load("0005_entry")
v6 = {"meta": {"name": "X", "schemaVersion": 6}, "tokens": {}, "components": [], "screens": []}
up = m5.up(v6)
check(up["meta"].get("entry") == "prd" and up["meta"]["schemaVersion"] == 7, "up adds entry=prd, stamps 7")
check(m5.down(up) == v6, "down is reversible")
tmpl = json.load(open(TEMPLATE))
check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check(tmpl["meta"].get("entry") == "prd", "template carries entry=prd")

print()
if fails:
    print(f"✗ {len(fails)} R3 figma-entry check(s) failed")
    sys.exit(1)
print("✓ R3 figma-entry clean")
