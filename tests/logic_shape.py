#!/usr/bin/env python3
"""
logic_shape.py (tests) — prose rules name the visual they would become.

Pins pb/tools/logic_shape.py (suggest / suggest_all / CLI), the L-SHAPE information finding in
logic_check.py, BLOCK_REQUIRES covering every block type, and handoff_docs rendering every block
type of the generic fixture (fixtures/logic/registry.json) without error.

Stdlib only. Usage: python3 tests/logic_shape.py   ·   Exit 0 = pass · 1 = a failure
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import logic_shape as LS    # noqa: E402
import logic_check as LC    # noqa: E402
import handoff_docs as HD   # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def types(rule, roles=None):
    return [s["type"] for s in LS.suggest(rule, roles)]


def prose(text, **kw):
    r = {"id": "x", "title": "T", "summary": text}
    r.update(kw)
    return r


print("logic_shape.py — positives, one per type")
POS = {
    "lifecycle": "An invoice moves Draft → Sent → Paid.",
    "steps": "Steps s0 to s4 run in order and there are never fewer steps than four.",
    "nav": "The bottom bar holds three tabs and a detail is pushed over the current tab.",
    "branches": "When the list is empty it shows a prompt, otherwise it shows the rows.",
    "async": "The save is pending, then either succeeded or failed.",
    "cases": "If total >= 500 then shipping is free. If total >= 100 then shipping is 5.",
    "timeline": "A reminder is sent 3 days before the due date.",
    "matrix": "Admin can approve and Viewer cannot.",
    "order": "The list sorts by status then by updated date, oldest first.",
    "ladder": "The contact falls back to the billing contact.",
    "placement": "Totals are never on Home.",
    "scope": "Voiding only changes one order; other orders stay untouched.",
    "validation": "A bad quantity fails with QTY_RANGE.",
    "gate": "Submit stays disabled until every line has a quantity.",
    "formula": "total = lines × (1 + tax)",
    "params": "The undo window is 10 s and a row is 48 px tall.",
    "inputs": "Shift-click selects a range and Cmd+K opens search.",
    "effects": "Approving shows a toast.",
    "edges": "The list has an empty state and an offline banner.",
}
for t, text in POS.items():
    got = LS.suggest(prose(text))
    check(t in [g["type"] for g in got], "%s detected from %r" % (t, text[:50]))
    check(all(len(g["why"]) <= 80 and g["why"] for g in got), "  why is non-empty and <= 80 chars")
check(len(POS) == 19, "every detector has a positive case (19)")
check(set(POS) <= set(LS.TYPE_ORDER) and set(LS.TYPE_ORDER) <= set(POS), "TYPE_ORDER matches the cases")

print("logic_shape.py — negatives")
check(types(prose("The list is shown once a user signs in.")) == [], "plain prose suggests nothing")
check("steps" not in types(prose("Then it saves.")), "one weak keyword (then) is not enough")
check("edges" not in types(prose("Show an error.")), "one weak keyword (error) is not enough")
check("nav" not in types(prose("Open the tab.")), "one weak keyword (tab) is not enough")
check("inputs" not in types(prose("Enter your email.")), "a lone Enter is not a keymap")
check("params" not in types(prose("It waits 10 s.")), "one number + unit is not a params table")
check("matrix" not in types(prose("Admin can approve.")), "one role is not a matrix")
check("lifecycle" not in types(prose("Go from A → B.")), "a single arrow is not a lifecycle")
check(types(prose(POS["lifecycle"], blocks=[{"type": "steps", "items": ["a"]}])) == ["lifecycle"], "a different block does not hide it")
check("lifecycle" not in types(prose(POS["lifecycle"], kind="state-machine", states=[{"key": "a"}])), "state-machine kind covers lifecycle")
check("matrix" not in types(prose(POS["matrix"], kind="matrix")), "kind matrix covers matrix")
for t, text in POS.items():
    if t in ("lifecycle", "matrix"):
        continue
    blocks = [{"type": t}]
    check(t not in types(prose(text, blocks=blocks)), "a %s block present -> no %s suggestion" % (t, t))
check("validation" not in types(prose("It must be required.", invariants=[{"must": "a field is required"}])),
      "invariants[] already carry validation")
check("validation" in types(prose("Fails with QTY_RANGE.", invariants=[{"must": "x"}])), "an error code in the prose still counts")
check(types(prose("Admin can approve; Viewer cannot.", )) == types(prose("Admin can approve; Viewer cannot.")), "deterministic")
check(types(prose("Reviewer can edit and Owner may delete."), ["Reviewer", "Owner"]) == ["matrix"], "roles come from meta.roles when given")
check(len(LS.suggest(prose(" ".join(POS.values())))) <= LS.MAX_SUGGESTIONS, "suggestions are capped")
check(LS.suggest(None) == [] and LS.suggest({}) == [], "garbage in -> empty")

print("logic_shape.py — the generic fixture")
FIX = os.path.join(ROOT, "fixtures", "logic", "registry.json")
reg = json.load(open(FIX, encoding="utf-8"))
rules = reg["ia"]["rules"]
shapes = LS.suggest_all(reg)
check("reminder-flow" in shapes, "the prose rule gets suggestions")
check({"lifecycle", "timeline"} <= {s["type"] for s in shapes.get("reminder-flow", [])}, "  lifecycle + timeline named")
blocks_all = {b["type"] for r in rules for b in r.get("blocks", [])}
check(len(blocks_all) == 23, "the fixture carries all 23 block types (%d)" % len(blocks_all))
check(blocks_all <= set(LC.BLOCK_REQUIRES), "BLOCK_REQUIRES covers every fixture block type")
check({r["kind"] for r in rules} >= {"state-machine", "matrix", "constraint", "decision"}, "every rule kind is present")
check(LS.suggest_all(reg) == shapes, "suggest_all is deterministic")
check(all(r.get("status") != "superseded" or r["id"] not in shapes for r in rules), "superseded rules are skipped")
f = LC.check_shape(reg)
check([x.where for x in f] == ["rule='reminder-flow'"] and f[0].severity == "INFO" and f[0].code == "L-SHAPE",
      "L-SHAPE fires once, as INFO, on the prose rule")
check("/pb:clarify" in f[0].msg, "  and names /pb:clarify")
check(LC.check_blocks(reg) == [], "no L-BLOCK on the fixture")
bad = {"id": "r", "blocks": [{"type": t} for t in ("states", "nav", "branches", "async", "timeline", "order", "ladder", "gate", "inputs", "edges")]}
check(len(LC.check_blocks({"ia": {"rules": [bad]}})) == 10, "each new block type needs its required key")
check(set(LC.BLOCK_REQUIRES) >= {"states", "nav", "branches", "async", "timeline", "order", "ladder", "gate", "inputs", "edges"},
      "BLOCK_REQUIRES has the new types")

print("logic_shape.py — CLI")
run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "pb", "tools", "logic_shape.py")] + list(a),  # noqa: E731
                                capture_output=True, text=True)
p = run(FIX, "--json")
check(p.returncode == 0 and "reminder-flow" in json.loads(p.stdout), "--json prints the map")
p = run(FIX, "--rule", "reminder-flow")
check(p.returncode == 0 and "lifecycle" in p.stdout, "--rule prints one rule")
p = run(FIX, "--rule", "snap-nothing")
check(p.returncode == 0 and "no shape" in p.stdout, "an unknown rule prints nothing found")

print("handoff_docs.py — every block type renders")
for r in rules:
    for b in r.get("blocks", []):
        try:
            md = "\n".join(HD._block_md(b))
            check(len(md.strip()) > 0, "%s block -> markdown" % b["type"])
        except Exception as e:                                       # noqa: BLE001
            check(False, "%s block raised %s: %s" % (b["type"], type(e).__name__, e))
md = HD.build_rules_md(reg, {"rules": rules, "ia": reg["ia"]})
for needle in ("guard: Editor or Admin", "back to: Review lines", "Outcome", "Tie-break", "Last resort", "stays disabled until",
               "Toast", "invented", "Scoped to:** one order", "Field:", "Split:", "Rows are roles", "Otherwise", "Retries on reconnect",
               "Late fee", "Interaction states"):
    check(needle in md, "rules.md carries %r" % needle)
check(HD.build_rules_md(reg, {"rules": rules, "ia": reg["ia"]}) == md, "rules.md is deterministic")

print("\n%s" % ("FAIL: %d" % len(FAIL) if FAIL else "PASS"))
sys.exit(1 if FAIL else 0)
