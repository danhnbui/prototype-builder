#!/usr/bin/env python3
"""
r4_figma_bridge.py — the WS3 code→Figma bridge acceptance, fixture-driven (no Figma / MCP / plugin):

  1. registry_to_figma.build_nodes(golden, ds-catalog) lowers the composition tree to GHN DS Bridge
     node JSON, and the OFFLINE G-FP6 invariants hold on that output:
       · auto-layout on every FRAME (layout.mode != NONE)                         [inv 1]
       · every screen element is an INSTANCE carrying a component.key (comp-first) [inv 5]
       · a local component's anatomy.parts[orgId] is a NESTED INSTANCE, not baked  [inv 7]
     plus: componentProperties map from props/state; spacing → the space token (not a same-valued
     radius); zero gaps when the catalog covers the DS; determinism (same input → same bytes).
  2. A missing DS component / token is FLAGGED as a gap (never invented).

Usage:  python3 tests/r4_figma_bridge.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
CATALOG = os.path.join(ROOT, "fixtures", "ds-catalog.json")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "registry_to_figma", os.path.join(ROOT, "pb", "tools", "registry_to_figma.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _iter_frames(node):
    yield node
    for c in node.get("children", []) or []:
        yield from _iter_frames(c)


r2f = _load_tool()
reg = json.load(open(GOLDEN, encoding="utf-8"))
catalog = json.load(open(CATALOG, encoding="utf-8"))

print("1 · lower the golden composition tree → node JSON")
out = r2f.build_nodes(reg, catalog=catalog, scope="both")
roots = out["roots"]
check(out["meta"]["rootCount"] == 4, f"4 roots (login-card FRAME + 3 screen FRAMEs) — got {out['meta']['rootCount']}")
check(out["meta"]["gapCount"] == 0, f"0 gaps when the catalog covers the DS (got {out['meta']['gapCount']}: {out['gaps']})")

# inv 1 — auto-layout on every FRAME
frames = [n for r in roots for n in _iter_frames(r) if n["type"] == "FRAME"]
bad_layout = [f["name"] for f in frames if (f.get("layout") or {}).get("mode") not in ("VERTICAL", "HORIZONTAL")]
check(not bad_layout, f"auto-layout on every FRAME (mode != NONE) — offenders: {bad_layout}")

# inv 5 — every screen element is an INSTANCE with a component.key
screens = [r for r in roots if r["name"] in ("Login", "Dashboard", "Create Account")]
check(len(screens) == 3, f"3 screen roots — got {[r['name'] for r in screens]}")
el_children = [c for s in screens for c in s.get("children", [])]
non_inst = [c.get("name") for c in el_children if c.get("type") != "INSTANCE" or not (c.get("component") or {}).get("key")]
check(not non_inst, f"every screen element is an INSTANCE with a component.key — offenders: {non_inst}")

# inv 7 — the local login-card's anatomy parts are NESTED INSTANCES (instance, don't bake)
card = next((r for r in roots if r["name"] == "User's Login Card"), None)
check(card is not None and card["type"] == "FRAME", "login-card lowered to a local FRAME")
nested = card.get("children", []) if card else []
check(len(nested) == 2 and all(n["type"] == "INSTANCE" and n["component"].get("key") for n in nested),
      f"login-card nests 2 INSTANCES by key (heading/paragraph) — got {[(n['type'], n['component'].get('key')) for n in nested]}")

print("2 · componentProperties + spacing token mapping")
login = next(r for r in roots if r["name"] == "Login")
by_name = {c["name"]: c for c in login["children"]}
check(by_name["title"]["componentProperties"].get("Text") == "Sign in", "heading instance maps Text='Sign in'")
check(by_name["title"]["componentProperties"].get("Level") == "1", "heading instance maps the Level=1 variant")
check(by_name["create-link"]["componentProperties"].get("Variant") == "Link", "link button maps the Variant=Link axis")
check(by_name["email"]["componentProperties"].get("Placeholder") == "you@example.com", "input instance maps Placeholder")
gapTok = (login["layout"].get("itemSpacingToken") or {}).get("token")
check(gapTok == "space-4", f"layout gap (16px) → the space-4 token, not a same-valued radius (got {gapTok!r})")
check(login["layout"].get("itemSpacing") == 16, "the numeric spacing fallback is emitted alongside the token")

print("3 · gaps are flagged, never invented")
out_nocat = r2f.build_nodes(reg, catalog={}, scope="screens")
check(out_nocat["meta"]["gapCount"] > 0, f"no catalog → components flagged as gaps (got {out_nocat['meta']['gapCount']})")
check(any(g["kind"] == "component" for g in out_nocat["gaps"]), "a gap names an unresolved component")

print("4 · determinism")
a = json.dumps(r2f.build_nodes(reg, catalog=catalog, scope="both"), sort_keys=True)
b = json.dumps(r2f.build_nodes(reg, catalog=catalog, scope="both"), sort_keys=True)
check(a == b, "build_nodes is deterministic (same input → same output)")

print()
if fails:
    print(f"✗ {len(fails)} R4 figma-bridge check(s) failed")
    sys.exit(1)
print("✓ R4 figma-bridge clean")
