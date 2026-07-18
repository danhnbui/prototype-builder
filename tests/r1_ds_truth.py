#!/usr/bin/env python3
"""
r1_ds_truth.py — the R1 "DS truth" acceptance, fixture-driven (no real DS / MCP needed):

  1. clone_ds.py materializes fixtures/ds-export.json into a fresh project: registry tokens
     seeded, meta.dsSource/platform set, design-system/<name>/<name>.md + .source.json written.
  2. ds_serve.py renders that clone (tokens as swatches + component catalog).
  3. clone_ds.py --drift reports IN SYNC (exit 0) against the unchanged source, then reports
     DRIFT (exit 3) after one token changes at source — naming the changed token.
  4. Migration 0003 adds meta.platform + meta.dsSource and is up→down reversible; the shipped
     registry template carries them at schemaVersion == CURRENT_SCHEMA.

Usage:  python3 tests/r1_ds_truth.py
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
TOOLS = os.path.join(ROOT, "pb", "tools")
CLONE = os.path.join(TOOLS, "clone_ds.py")
DS_SERVE = os.path.join(TOOLS, "ds_serve.py")
EXPORT = os.path.join(ROOT, "fixtures", "ds-export.json")
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


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    shutil.copy(TEMPLATE, reg)
    export = os.path.join(d, "export.json")
    shutil.copy(EXPORT, export)

    print("1 · clone materializes the export")
    r = subprocess.run([sys.executable, CLONE, "--from", export, "--registry", reg], capture_output=True, text=True)
    check(r.returncode == 0, f"clone_ds exits 0 ({r.stderr.strip()[:60]})")
    reg_data = json.load(open(reg))
    src = json.load(open(export))
    check(all(t in reg_data["tokens"] for t in src["tokens"]), "all export tokens merged into registry")
    check(reg_data["meta"]["dsSource"] and reg_data["meta"]["dsSource"]["type"] == "figma", "meta.dsSource recorded")
    check(reg_data["meta"]["platform"] == "web", "meta.platform set")
    dsdir = os.path.join(d, "design-system", src["name"])
    check(os.path.isfile(os.path.join(dsdir, f"{src['name']}.md")), "DS reference .md written")
    check(os.path.isfile(os.path.join(dsdir, ".source.json")), ".source.json snapshot written")

    print("2 · ds_serve renders the clone")
    r = subprocess.run([sys.executable, DS_SERVE, reg, "--print"], capture_output=True, text=True)
    html = r.stdout
    check(r.returncode == 0 and html.startswith("<!doctype"), "ds_serve --print returns HTML")
    check("--color-brand" in html and "button" in html and "Component catalog" in html,
          "HTML contains tokens + component catalog")

    print("3 · drift: in-sync then detected")
    r0 = subprocess.run([sys.executable, CLONE, "--drift", export, "--registry", reg], capture_output=True, text=True)
    check(r0.returncode == 0, f"in-sync source → exit 0 ({r0.stdout.strip()[:50]})")
    src["tokens"]["color-brand"]["value"] = "#7c3aed"  # change one token at source
    json.dump(src, open(export, "w"))
    r3 = subprocess.run([sys.executable, CLONE, "--drift", export, "--registry", reg], capture_output=True, text=True)
    check(r3.returncode == 3 and "color-brand" in r3.stdout, "changed source token → exit 3, names color-brand")

print("4 · migration 0003 + template")
man = _load("manifest")
m3 = _load("0003_ds_source")
v4 = {"meta": {"name": "X", "schemaVersion": 4}, "tokens": {}, "components": [], "screens": []}
up = m3.up(v4)
check(up["meta"].get("platform") == "web" and "dsSource" in up["meta"] and up["meta"]["schemaVersion"] == 5,
      "up adds platform+dsSource, stamps 5")
check(m3.down(up) == v4, "down is reversible")
tmpl = json.load(open(TEMPLATE))
check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check("platform" in tmpl["meta"] and "dsSource" in tmpl["meta"], "template carries platform + dsSource")

print()
if fails:
    print(f"✗ {len(fails)} R1 DS-truth check(s) failed")
    sys.exit(1)
print("✓ R1 DS-truth clean")
