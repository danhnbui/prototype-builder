#!/usr/bin/env python3
"""
r2_export_tiers.py — the R2 "export tiers" acceptance, fixture-driven:

  1. Migration 0004 adds meta.outputTier + meta.exportTarget, is up→down reversible, and the
     shipped template + golden track CURRENT_SCHEMA == 6.
  2. render_react.py (SCAFFOLD tier) turns the golden registry into a self-contained React+Vite
     app: per-component/screen wrapper (valid `export default function`) whose render import
     resolves to an emitted file, tokens.css with :root vars, a token-mapped tailwind.config.js,
     valid package.json, and an App that mounts a screen. --component exports a single subset.
  3. handoff-dev keeps the hardened tier GATED (not faked) until its inputs exist.

The scaffold "renders one screen" is asserted structurally (valid JSX + resolvable imports) — a
real `npm run dev` render is the manual gate (needs Node, out of scope for this stdlib suite).

Usage:  python3 tests/r2_export_tiers.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
RENDER_REACT = os.path.join(TOOLS, "render_react.py")
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


print("1 · migration 0004 + schema")
man = _load("manifest")
m4 = _load("0004_export_tier")
v5 = {"meta": {"name": "X", "schemaVersion": 5}, "tokens": {}, "components": [], "screens": []}
up = m4.up(v5)
check(up["meta"].get("outputTier") == "host" and "exportTarget" in up["meta"] and up["meta"]["schemaVersion"] == 6,
      "up adds outputTier+exportTarget, stamps 6")
check(m4.down(up) == v5, "down is reversible")
tmpl = json.load(open(TEMPLATE))
check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")
check("outputTier" in tmpl["meta"] and "exportTarget" in tmpl["meta"], "template carries outputTier + exportTarget")

print("2 · scaffold tier emits a runnable React app")
with tempfile.TemporaryDirectory() as out:
    r = subprocess.run([sys.executable, RENDER_REACT, GOLDEN, "--out", out], capture_output=True, text=True)
    check(r.returncode == 0, f"render_react exits 0 ({r.stderr.strip()[:60]})")
    have = set()
    for dp, _, fns in os.walk(out):
        for fn in fns:
            have.add(os.path.relpath(os.path.join(dp, fn), out))
    for req in ("package.json", "vite.config.js", "tailwind.config.js", "index.html",
                "src/main.jsx", "src/App.jsx", "src/tokens.css"):
        check(req in have, f"emits {req}")
    check(json.load(open(os.path.join(out, "package.json"))).get("type") == "module", "package.json is valid + ESM")
    css = open(os.path.join(out, "src", "tokens.css")).read()
    check(css.startswith(":root") and "--brand:" in css, "tokens.css has :root vars")
    check("var(--" in open(os.path.join(out, "tailwind.config.js")).read(), "tailwind.config maps tokens")
    # every emitted .jsx is a valid default-export component whose render import resolves
    jsx = [f for f in have if f.endswith(".jsx")]
    check(len(jsx) >= 4, f"emits component + screen wrappers ({len(jsx)} .jsx)")
    bad = []
    imp_re = re.compile(r"import\s+\w+\s+from\s+'(\./[^']+)'")
    for f in jsx:
        txt = open(os.path.join(out, f)).read()
        if f != "src/main.jsx" and "export default function" not in txt:  # main.jsx is the entry, not a component
            bad.append(f + " (no default fn)")
        for m in imp_re.finditer(txt):
            target = os.path.normpath(os.path.join(os.path.dirname(os.path.join(out, f)), m.group(1)))
            if not os.path.isfile(target):
                bad.append(f + f" (dangling import {m.group(1)})")
    check(not bad, f"all wrappers valid + imports resolve ({bad[:2]})")
    app = open(os.path.join(out, "src", "App.jsx")).read()
    check("screens/" in app and "export default function App" in app, "App mounts a screen")

print("3 · scaffold subset (--component)")
with tempfile.TemporaryDirectory() as out:
    subprocess.run([sys.executable, RENDER_REACT, GOLDEN, "--out", out, "--component", "button"], capture_output=True)
    comp = [f for f in os.listdir(os.path.join(out, "src", "components")) if f.endswith(".jsx")]
    check(comp == ["Button.jsx"], f"--component button exports only Button ({comp})")

print("4 · hardened tier is gated, not faked")
hd = open(os.path.join(ROOT, "pb", "commands", "handoff-dev.md")).read()
check("NOT YET AVAILABLE" in hd and "pb-full-picture" in hd, "handoff-dev defers hardened until inputs exist")

print()
if fails:
    print(f"✗ {len(fails)} R2 export-tier check(s) failed")
    sys.exit(1)
print("✓ R2 export-tiers clean")
