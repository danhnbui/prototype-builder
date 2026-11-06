#!/usr/bin/env python3
"""
r2_export_tiers.py — migration 0004 (history), fixture-driven:

  1. Migration 0004 adds meta.outputTier + meta.exportTarget to an old registry and is up→down
     reversible. The migration stays as history: the engineering hand-off (the runnable tiers
     that read these fields) was removed in v3.0.0, so the shipped template no longer carries
     them, and the test asserts that it does not.

Usage:  python3 tests/r2_export_tiers.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
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


print("migration 0004 + schema")
man = _load("manifest")
m4 = _load("0004_export_tier")
v5 = {"meta": {"name": "X", "schemaVersion": 5}, "tokens": {}, "components": [], "screens": []}
up = m4.up(v5)
check(up["meta"].get("outputTier") == "host" and "exportTarget" in up["meta"] and up["meta"]["schemaVersion"] == 6,
      "up adds outputTier+exportTarget, stamps 6")
check(m4.down(up) == v5, "down is reversible")
tmpl = json.load(open(TEMPLATE))
check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check("outputTier" not in tmpl["meta"] and "exportTarget" not in tmpl["meta"],
      "template no longer carries outputTier / exportTarget (the engineering hand-off is gone)")

print()
if fails:
    print(f"✗ {len(fails)} R2 export-tier check(s) failed")
    sys.exit(1)
print("✓ R2 export-tiers clean")
