#!/usr/bin/env python3
"""
logic_contract.py — schema 11: the logic contract (0009), registry.runtime[], and the two
runtime verbs that earned a place (D-28).

  1. 0009 up (pure dict) stamps 11, seeds `ia` + `runtime[]`, and sets logicSrc where there
     is prose to carry. Nothing is deleted: every `logicNotes` / `uiLogic` is still there.
  2. 0009 up (file mode) writes one sidecar per item with prose, carrying each piece VERBATIM
     into notes[] beside a `source` pointer at where the original still lives.
  3. down removes exactly what up created — sidecars, logicSrc, the two empty slices — and the
     project comes back byte-for-byte. A sidecar edited since is KEPT, not deleted.
  4. logic_extract --contracts refreshes the derived half, preserves the authored half, is
     idempotent, and points the registry at any contract it does not yet reference.
  5. render: registry.runtime[] modules inline BEFORE the render bodies, a declared `url`
     becomes a <script src> in the head, and load_contracts carries the authored half only.
  6. the two verbs are present in runtime.js, byte-identical in prototype.html's copy, and
     wired in both shells.
  7. the chain reaches CURRENT_SCHEMA == 11 and the shipped template carries it.

Self-contained: the fixture is built here, never read from a project. Exit 0/1.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import render as R  # noqa: E402

TPL = os.path.join(ROOT, "pb", "template")
RUNTIME_JS = os.path.join(TPL, "runtime.js")
SHELL = os.path.join(TPL, "prototype.html")
DS_SHELL = os.path.join(TPL, "design-system.html")
EXTRACT = os.path.join(ROOT, "pb", "tools", "logic_extract.py")
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


MIG = _load("0009_logic_contract")
MAN = _load("manifest")

# Non-ASCII on purpose: the runner used to escape it to \uXXXX and rewrite every line that
# had any, which is what made a lossless rollback impossible to prove by diffing.
PROSE_A = ["Điều kiện: chỉ hiện khi chu kỳ đang mở — 2026-07-31", "second note"]
PROSE_B = "RESTRUCTURED 2026-08-10 — the drawer owns the save, not the row."


def fixture(d):
    """A two-component, one-screen project with prose in both fields it can land in."""
    os.makedirs(os.path.join(d, "render", "components"), exist_ok=True)
    os.makedirs(os.path.join(d, "render", "screens"), exist_ok=True)
    os.makedirs(os.path.join(d, "spec", "components"), exist_ok=True)
    for rel, body in (
        ("render/components/badge.js", "function renderCmpBadge(p){ return '<b>'+pbEscape(p.text||'')+'</b>'; }\n"),
        ("render/components/panel.js", "function renderCmpPanel(p){ return pbUse('badge',{text:p.t}); }\n"),
        ("render/screens/home.js", "function renderScrHome(){ return pbUse('panel',{t:'hi'}); }\n"),
    ):
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write(body)
    with open(os.path.join(d, "spec/components/panel.json"), "w", encoding="utf-8") as f:
        json.dump({"anatomy": ["shell"], "uiLogic": PROSE_B}, f, indent=2, ensure_ascii=False)
        f.write("\n")
    reg = {
        "meta": {"name": "fixture", "schemaVersion": 10},
        "tokens": {},
        "components": [
            {"id": "badge", "name": "Badge", "level": "atom", "scope": "local",
             "renderFn": "renderCmpBadge", "renderSrc": "render/components/badge.js",
             "logicNotes": PROSE_A},
            {"id": "panel", "name": "Panel", "level": "molecule", "scope": "local",
             "renderFn": "renderCmpPanel", "renderSrc": "render/components/panel.js",
             "specSrc": "spec/components/panel.json"},
        ],
        "screens": [
            {"id": "home", "name": "Home", "level": "page",
             "renderFn": "renderScrHome", "renderSrc": "render/screens/home.js"},
        ],
        "flow": {"populated": False}, "erd": {"populated": False},
    }
    with open(os.path.join(d, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return reg


def snapshot(d):
    """Every file under d, by relative path -> bytes. The byte-equality gate reads this."""
    out = {}
    for base, _dirs, files in os.walk(d):
        for name in files:
            path = os.path.join(base, name)
            with open(path, "rb") as f:
                out[os.path.relpath(path, d)] = f.read()
    return out


print("1 · 0009 up (pure dict) — additive, nothing deleted")
reg0 = fixture(tempfile.mkdtemp())
up_pure = MIG.up(json.loads(json.dumps(reg0)))
check(up_pure["meta"]["schemaVersion"] == 11, "up stamps schemaVersion 11")
check(up_pure.get("ia") == {"populated": False}, "seeds the `ia` slice, unpopulated")
check(up_pure.get("runtime") == [], "seeds registry.runtime[] empty")
badge = up_pure["components"][0]
check(badge.get("logicSrc") == "logic/components/badge.json", "logicSrc points at the sidecar")
check(badge.get("logicNotes") == PROSE_A, "logicNotes is left exactly where it was")
check("logicSrc" not in up_pure["screens"][0], "an item with no prose gets no contract")

print("2 · 0009 up (file mode) — prose copied VERBATIM with a source pointer")
d = tempfile.mkdtemp()
orig = fixture(d)
before = snapshot(d)
up = MIG.up(json.loads(json.dumps(orig)), base_dir=d)
with open(os.path.join(d, "logic/components/badge.json"), encoding="utf-8") as f:
    c_badge = json.load(f)
check([n["text"] for n in c_badge["notes"]] == PROSE_A, "each list element is one note, verbatim")
check(c_badge["notes"][0]["source"] == "registry.json#/components/badge/logicNotes/0",
      "the source pointer names where the original still is")
check(c_badge["writes"] == [] and c_badge["affordances"] == [],
      "the hand-authored half is created empty, never guessed")
with open(os.path.join(d, "logic/components/panel.json"), encoding="utf-8") as f:
    c_panel = json.load(f)
check(c_panel["notes"][0]["text"] == PROSE_B and c_panel["notes"][0]["source"].endswith("#/uiLogic"),
      "uiLogic is read out of the schema-10 spec sidecar and copied too")
with open(os.path.join(d, "spec/components/panel.json"), "rb") as f:
    check(f.read() == before["spec/components/panel.json"], "the spec sidecar is not touched")
check(not any(k in c_badge for k in ("seam", "handlers", "disclosure")),
      "the migration writes no derived fields — a tool owns those and rewrites them")

print("3 · down — removes exactly what up created; the project comes back")
json.dump(up, open(os.path.join(d, "registry.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
open(os.path.join(d, "registry.json"), "a", encoding="utf-8").write("\n")
down = MIG.down(json.loads(json.dumps(up)), base_dir=d)
json.dump(down, open(os.path.join(d, "registry.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
open(os.path.join(d, "registry.json"), "a", encoding="utf-8").write("\n")
check(down["meta"]["schemaVersion"] == 10, "down stamps schemaVersion 10")
check("ia" not in down and "runtime" not in down, "the two seeded slices go away while still empty")
check(not os.path.exists(os.path.join(d, "logic")), "the logic/ tree is gone")
after = snapshot(d)
check(after == before, "every file is byte-for-byte what it was before the migration")

d2 = tempfile.mkdtemp()
orig2 = fixture(d2)
up2 = MIG.up(json.loads(json.dumps(orig2)), base_dir=d2)
edited = os.path.join(d2, "logic/components/badge.json")
with open(edited, encoding="utf-8") as f:
    hand = json.load(f)
hand["writes"] = ["cycle"]
with open(edited, "w", encoding="utf-8") as f:
    json.dump(hand, f, indent=2, ensure_ascii=False)
MIG.down(json.loads(json.dumps(up2)), base_dir=d2)
check(os.path.exists(edited), "a contract edited since the migration is KEPT, not deleted")

print("4 · logic_extract --contracts — derived half refreshed, authored half untouched")
d3 = tempfile.mkdtemp()
orig3 = fixture(d3)
up3 = MIG.up(json.loads(json.dumps(orig3)), base_dir=d3)
with open(os.path.join(d3, "registry.json"), "w", encoding="utf-8") as f:
    json.dump(up3, f, indent=2, ensure_ascii=False)
    f.write("\n")
with open(os.path.join(d3, "logic/components/badge.json"), encoding="utf-8") as f:
    hand = json.load(f)
hand["writes"] = ["cycle"]
hand["affordances"] = [{"id": "dismiss", "why": "a toast the user never asked for"}]
with open(os.path.join(d3, "logic/components/badge.json"), "w", encoding="utf-8") as f:
    json.dump(hand, f, indent=2, ensure_ascii=False)
r1 = subprocess.run([sys.executable, EXTRACT, d3, "--contracts"], capture_output=True, text=True)
check(r1.returncode == 0, "--contracts exits 0")
with open(os.path.join(d3, "logic/components/badge.json"), encoding="utf-8") as f:
    c = json.load(f)
check(all(k in c for k in ("seam", "handlers", "disclosure")), "the derived half is written")
check(c["writes"] == ["cycle"] and c["affordances"][0]["why"].startswith("a toast"),
      "the hand-authored half survives a refresh untouched")
check(c["disclosure"]["composedBy"] == ["panel"], "disclosure is derived from the real code")
with open(os.path.join(d3, "registry.json"), encoding="utf-8") as f:
    reg3 = json.load(f)
check(reg3["screens"][0].get("logicSrc") == "logic/screens/home.json",
      "an item the migration skipped is pointed at its new contract")
r2 = subprocess.run([sys.executable, EXTRACT, d3, "--contracts"], capture_output=True, text=True)
check("refreshed 0 contract(s)" in r2.stdout, "a second run rewrites nothing — idempotent")

print("5 · render — runtime modules, declared deps, and the authored half only")
os.makedirs(os.path.join(d3, "runtime"), exist_ok=True)
with open(os.path.join(d3, "runtime/store.js"), "w", encoding="utf-8") as f:
    f.write("function pbFixtureStore(k){ return k; }\n")
reg3["runtime"] = [
    {"id": "store", "src": "runtime/store.js", "why": "the fixture's session store"},
    {"id": "sheetjs", "url": "https://cdn.example/xlsx.js?a=1&b=2", "why": "xlsx parsing"},
]
with open(os.path.join(d3, "registry.json"), "w", encoding="utf-8") as f:
    json.dump(reg3, f, indent=2, ensure_ascii=False)
    f.write("\n")
_reg, html, missing = R.render_file(os.path.join(d3, "registry.json"), SHELL,
                                    os.path.join(d3, "prototype.html"))
check(missing == [], "the project renders with no missing bodies or modules")
i_mod, i_body = html.find("function pbFixtureStore"), html.find('window["renderCmp')
check(0 < i_mod < i_body, "a declared module is inlined BEFORE every render body")
check('<script src="https://cdn.example/xlsx.js?a=1&amp;b=2"></script>' in html,
      "a declared url becomes a <script src> with its query string escaped")
check("<!--__PB_RUNTIME_DEPS__-->" not in html, "the deps marker is consumed")
contracts = R.load_contracts(reg3, d3)
check(contracts == {"components/badge": {"writes": ["cycle"],
                                         "affordances": [{"id": "dismiss",
                                                          "why": "a toast the user never asked for"}]}},
      "load_contracts carries the authored half only — not notes, not the derived half")
check('"contracts"' in html and "a toast the user never asked for" in html,
      "the authored half reaches the shell")
bad = {"components": [{"id": "x", "logicSrc": "logic/components/nope.json"}]}
check(R.load_contracts(bad, d3) == {}, "a missing contract is skipped, never raised")
missing_mod = dict(reg3, runtime=[{"id": "ghost", "src": "runtime/ghost.js"}])
check(R.load_runtime(missing_mod, d3)[2] == ["ghost (runtime/ghost.js)"],
      "a module that does not resolve is reported, not raised")

print("5b · the derived graph is cached on the body files, and only on them")
g1 = R.load_logic(d3)
key1 = R._logic_key(d3)
check(key1 is not None and R._logic_key(d3) == key1, "the fingerprint is stable while nothing changes")
g2 = R.load_logic(d3)
check(g2 == g1, "a warm call returns the same graph")
g2["stats"]["handlers"] = -1
check(R.load_logic(d3)["stats"]["handlers"] != -1, "the cache hands out a copy, not its own object")
with open(os.path.join(d3, "render/components/badge.js"), "a", encoding="utf-8") as f:
    f.write("\nfunction pbBadgeLater(){ return 1; }\n")
check(R._logic_key(d3) != key1, "editing a body changes the fingerprint")
names = {h["name"] for h in R.load_logic(d3)["handlers"]}
check("pbBadgeLater" in names, "and the re-derived graph sees the new function")

print("6 · the two verbs — in runtime.js, mirrored verbatim, wired in both shells")
rt = open(RUNTIME_JS, encoding="utf-8").read()
shell = open(SHELL, encoding="utf-8").read()
ds = open(DS_SHELL, encoding="utf-8").read()
for fn in ("function pbPreserve(", "function pbPreserveCapture(", "function pbPreserveRestore(",
           "function pbSetStep(", "function pbSyncMachines(", "function pbStepClick("):
    check(fn in rt, "runtime.js defines %s…)" % fn[9:-1])
# The whole runtime BODY, not three canary lines: runtime.js minus its header comment must
# appear verbatim in the shell, or a helper added to one silently misses the other.
lines = rt.split("\n")
i = 0
while i < len(lines) and (lines[i].startswith("/*") or lines[i].startswith(" *")):
    i += 1
body = "\n".join(lines[i:]).rstrip("\n")
check(body in shell, "prototype.html carries the ENTIRE runtime.js body, byte-identical")
check("pbStepClick(e.target)" in shell and "pbSyncMachines(document.getElementById('proto-frame'))" in shell,
      "the prototype shell wires step clicks and syncs machines after each render")
check("pbStepClick(e.target)" in ds and "pbSyncMachines(document.getElementById('ds-root'))" in ds,
      "the design-system shell does too, so a wizard can demo")
check("[data-step-pane][hidden]" in shell and "[data-step-pane][hidden]" in ds,
      "both shells state the hidden-pane rule at a strength a project's CSS cannot beat")

print("7 · schema constant + template")
check(MAN.CURRENT_SCHEMA == 11, "CURRENT_SCHEMA == 11")
check((10, 11, "0009_logic_contract") in MAN._REGISTRY, "0009 is registered in the migration chain")
tmpl = json.load(open(os.path.join(TPL, "registry.template.json"), encoding="utf-8"))
check(tmpl["meta"]["schemaVersion"] == 11, "the shipped template is stamped 11")
check(tmpl.get("ia") == {"populated": False} and tmpl.get("runtime") == [],
      "the template seeds both new slices")

print()
if fails:
    print("FAIL — %d regression(s)" % len(fails))
    sys.exit(1)
print("PASS — the logic contract (0009), registry.runtime[], and the two runtime verbs")
