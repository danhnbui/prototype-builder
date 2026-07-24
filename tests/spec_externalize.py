#!/usr/bin/env python3
"""
spec_externalize.py — the schema 9 → 10 migration (0008) that moves anatomy/spec/usage/uiLogic
out of registry.json into spec/{components,screens}/<id>.json sidecars (specSrc), and render.py's
load_specs re-inlining them for the spec drawer.

  1. up (pure dict) sets schemaVersion 10 + specSrc, preserving fields for down() reversal.
  2. up (file mode) writes one sidecar per item with fields present, deletes the inline fields,
     leaves items with none of the four fields untouched.
  3. down re-inlines from the sidecar and drops specSrc; up→down→up is stable.
  4. render.load_specs re-inlines to SEMANTIC equality with the pre-migration registry
     (ignoring schemaVersion + specSrc), byte-preserving each blob.
  5. lint_registry.py resolves specSrc so anatomy checks see the parts — same verdict as inline.
  6. CURRENT_SCHEMA == 10 and the shipped template carries it.

Fixture-driven off registry.demo.json. Usage: python3 tests/spec_externalize.py  ·  Exit 0/1.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import render as R  # noqa: E402

DEMO = os.path.join(ROOT, "registry.demo.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
FIELDS = ("anatomy", "spec", "usage", "uiLogic")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(stem):
    spec = importlib.util.spec_from_file_location(
        stem, os.path.join(ROOT, "pb", "migrations", stem + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _norm(reg):
    """Registry compared ignoring schemaVersion + specSrc (the only legitimate deltas)."""
    reg = json.loads(json.dumps(reg))
    reg.get("meta", {}).pop("schemaVersion", None)
    for k in ("components", "screens"):
        for it in reg.get(k, []):
            it.pop("specSrc", None)
    return reg


mig = _load("0008_externalize_spec")
man = _load("manifest") if os.path.exists(os.path.join(ROOT, "pb", "migrations", "manifest.py")) else None
orig = json.load(open(DEMO))

print("1 · up/down pure-dict reversibility")
up_pure = mig.up(json.loads(json.dumps(orig)))
check(up_pure["meta"]["schemaVersion"] == 10, "up stamps schemaVersion 10")
check(all("specSrc" in c for c in up_pure["components"]
          if any(f in orig["components"][i] for i, oc in enumerate(orig["components"]) if oc["id"] == c["id"]
                 for f in FIELDS)), "up sets specSrc on items that had fields")
check(_norm(mig.down(up_pure)) == _norm(orig), "down re-inlines to the original (pure dict)")

print("2 · up (file mode) writes sidecars, strips inline fields")
with tempfile.TemporaryDirectory() as d:
    up = mig.up(json.loads(json.dumps(orig)), base_dir=d)
    btn = next(c for c in up["components"] if c["id"] == "button")
    check(os.path.isfile(os.path.join(d, "spec", "components", "button.json")), "sidecar file written")
    check(not any(f in btn for f in FIELDS), "inline fields removed from the entry")
    check(btn.get("specSrc") == "spec/components/button.json", "specSrc points at the sidecar")
    check(all("specSrc" not in s for s in up["screens"]), "screens with no fields are untouched (no specSrc)")

    print("3 · down + up→down→up stability (file mode)")
    check(_norm(mig.down(up, base_dir=d)) == _norm(orig), "down re-inlines from the sidecar")
    up2 = mig.up(mig.down(mig.up(json.loads(json.dumps(orig)), base_dir=d), base_dir=d), base_dir=d)
    check(_norm(up2) == _norm(up), "up→down→up is stable")

print("4 · render.load_specs re-inlines to semantic equality")
with tempfile.TemporaryDirectory() as d:
    up = mig.up(json.loads(json.dumps(orig)), base_dir=d)
    json.dump(up, open(os.path.join(d, "registry.json"), "w"), indent=2, ensure_ascii=False)
    resolved = R.load_specs(json.load(open(os.path.join(d, "registry.json"))), d)
    check(_norm(resolved) == _norm(orig), "load_specs restores every field (ignoring schemaVersion/specSrc)")
    b0 = next(c for c in orig["components"] if c["id"] == "button")["anatomy"]
    b1 = next(c for c in resolved["components"] if c["id"] == "button")["anatomy"]
    check(json.dumps(b0, sort_keys=True) == json.dumps(b1, sort_keys=True), "anatomy blob byte-preserved through the sidecar")
    # a missing sidecar fails closed
    os.remove(os.path.join(d, "spec", "components", "button.json"))
    try:
        R.load_specs(json.load(open(os.path.join(d, "registry.json"))), d)
        check(False, "missing specSrc raises RenderError")
    except R.RenderError:
        check(True, "missing specSrc raises RenderError")

print("5 · lint verdict is identical inline vs externalized")
def lint_counts(path):
    r = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
    return r.returncode
with tempfile.TemporaryDirectory() as d:
    up = mig.up(json.loads(json.dumps(orig)), base_dir=d)
    json.dump(up, open(os.path.join(d, "registry.json"), "w"), indent=2, ensure_ascii=False)
    check(lint_counts(DEMO) == lint_counts(os.path.join(d, "registry.json")),
          "lint exit code matches between schema-9 inline and schema-10 externalized")

print("6 · schema constant + template")
if man:
    check(man.CURRENT_SCHEMA == 10, "CURRENT_SCHEMA == 10")
    check((9, 10, "0008_externalize_spec") in man._REGISTRY, "0008 registered in the migration chain")
    tmpl = json.load(open(TEMPLATE))
    check(tmpl["meta"]["schemaVersion"] == man.CURRENT_SCHEMA, "template schemaVersion == CURRENT_SCHEMA")

print()
if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("PASS — spec externalization (0008) intact")
