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
  6. the two verbs live once in runtime.js, reach the RENDERED page, and are wired in both shells.
  7. the chain reached 11 and never went back, and the shipped template carries 0009's slices.
     (The current schema constant belongs to the NEWEST migration — tests/tradeoff_rules.py.)

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

print("4b · --contracts writes registry.json under the registry lock, from the registry as it is once it has the lock (L3)")
import importlib  # noqa: E402
import time  # noqa: E402
pbslice = importlib.import_module("slice")        # `import slice` would shadow the builtin
d4 = tempfile.mkdtemp()
fixture(d4)                                        # no logicSrc anywhere: --contracts will point all three
reg4 = os.path.join(d4, "registry.json")
with pbslice.registry_lock(reg4, "a test holding the lock"):
    held = snapshot(d4)
    r = subprocess.run([sys.executable, EXTRACT, d4, "--contracts"], capture_output=True, text=True,
                       env=dict(os.environ, PB_LOCK_TIMEOUT="0.4"))
    check(r.returncode == 1 and "being written" in r.stderr and "a test holding the lock" in r.stderr
          and "Traceback" not in r.stderr, "a held registry lock refuses --contracts, naming the holder (%r)" % r.stderr.strip()[:90])
    check(snapshot(d4) == held, "…and NOTHING was written — no sidecar, no registry change (the refusal comes before the first write)")
p4 = subprocess.Popen([sys.executable, EXTRACT, d4, "--contracts"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      text=True, env=dict(os.environ, PB_LOCK_TIMEOUT="30"))
with pbslice.registry_lock(reg4, "a test holding the lock again"):
    time.sleep(1.5)
    waiting = p4.poll() is None
    with open(reg4, encoding="utf-8") as f:
        mid = json.load(f)
    mid["meta"]["editedWhileLocked"] = "yes"
    pbslice._write(reg4, mid)
out4, err4 = p4.communicate(timeout=60)
check(waiting, "a writer that finds the lock held WAITS for it (an unlocked one would already have finished)")
with open(reg4, encoding="utf-8") as f:
    done4 = json.load(f)
check(p4.returncode == 0 and done4["meta"].get("editedWhileLocked") == "yes",
      "…and when it gets the lock it reads the registry afresh: the edit saved meanwhile is NOT overwritten (%s)" % err4.strip()[:80])
check(all(i.get("logicSrc") for i in done4["components"] + done4["screens"]),
      "…while its own change (the logicSrc pointers) is there too")
check([f for f in os.listdir(d4) if f.endswith(".tmp") or f.startswith(".registry.json.")] == [],
      "the registry write is atomic: no temp file is left in the project directory")
shutil.rmtree(d4, ignore_errors=True)

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

print("5a · the shell is inlined only what it reads")
full = R.load_logic(d3)
shell_view = R._logic_for_shell(full)
check("bodyHash" in full["handlers"][0] and "localCalls" in full["handlers"][0],
      "the graph the TOOLS get is complete (logic_check --freeze needs bodyHash)")
check(not any("bodyHash" in h or "localCalls" in h for h in shell_view["handlers"]),
      "the graph the SHELL gets drops the two handler fields it never reads")
check(not any("shellVerbs" in i for i in shell_view["items"]),
      "and the item field it never reads")
check(all(k in shell_view["handlers"][0] for k in ("name", "file", "owners", "reads", "slices")),
      "everything the ripple view draws survives")
_shell_src = open(SHELL, encoding="utf-8").read()
for _dead in ("bodyHash", "localCalls", "shellVerbs"):
    check(("." + _dead) not in _shell_src,
          "the shell really does not read %s — drop it here if that changes" % _dead)

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

print("6 · the two verbs — one copy in runtime.js, injected into both shells")
rt = open(RUNTIME_JS, encoding="utf-8").read()
shell = open(SHELL, encoding="utf-8").read()
ds = open(DS_SHELL, encoding="utf-8").read()
for fn in ("function pbPreserve(", "function pbPreserveCapture(", "function pbPreserveRestore(",
           "function pbSetStep(", "function pbSyncMachines(", "function pbStepClick("):
    check(fn in rt, "runtime.js defines %s…)" % fn[9:-1])
# One copy on disk, injected into both shells. The verbs must reach the RENDERED page — that
# is the only place a project ever sees them, and it is what the old "are the two copies the
# same" check was a proxy for.
body = R.shared_runtime(rt)
check("/*__PB_RUNTIME__*/" in shell and body not in shell,
      "prototype.html carries the marker, not a second copy of runtime.js")
_r, _html, _ = R.render_file(os.path.join(d3, "registry.json"), SHELL, os.path.join(d3, "p.html"))
check(body in _html, "the rendered prototype carries the whole runtime, byte-identical")
check("function pbPreserve(" in _html and "function pbSetStep(" in _html,
      "so both verbs reach a real page")
check("pbStepClick(e.target)" in shell and "pbSyncMachines(document.getElementById('proto-frame'))" in shell,
      "the prototype shell wires step clicks and syncs machines after each render")
check("pbStepClick(e.target)" in ds and "pbSyncMachines(document.getElementById('ds-root'))" in ds,
      "the design-system shell does too, so a wizard can demo")
check("[data-step-pane][hidden]" in shell and "[data-step-pane][hidden]" in ds,
      "both shells state the hidden-pane rule at a strength a project's CSS cannot beat")

print("7 · schema constant + template")
check(MAN.CURRENT_SCHEMA >= 11, f"the chain is at or past 11 (got {MAN.CURRENT_SCHEMA})")
check((10, 11, "0009_logic_contract") in MAN._REGISTRY, "0009 is registered in the migration chain")
tmpl = json.load(open(os.path.join(TPL, "registry.template.json"), encoding="utf-8"))
check(tmpl["meta"]["schemaVersion"] >= 11, f"the shipped template is at or past 11 ({tmpl['meta']['schemaVersion']})")
check((tmpl.get("ia") or {}).get("populated") is False and tmpl.get("runtime") == [],
      "the template seeds both new slices")

print("8 · registry.runtime[] modules share the render bodies' scope")
# The primitive exists to retire the fake component whose render body returns ''. If the
# analyser does not follow the code to its new home, adopting it turns every function those
# files define into an "undefined helper" — measured on a real project at the moment it moved
# five such components out: 68 false L-UNDEF errors and exit 2, from code that never changed.
import logic_extract as LE  # noqa: E402
import logic_check as LC  # noqa: E402

d8 = tempfile.mkdtemp(prefix="pb-runtime-scope-")
fixture(d8)
os.makedirs(os.path.join(d8, "runtime"), exist_ok=True)
with open(os.path.join(d8, "runtime/store.js"), "w", encoding="utf-8") as f:
    f.write("function pbStoreGet(k){ return (window.PB_S||{})[k]; }\n"
            "function pbStoreSet(k,v){ (window.PB_S=window.PB_S||{})[k]=v; }\n")
with open(os.path.join(d8, "render/components/badge.js"), "w", encoding="utf-8") as f:
    f.write("function renderCmpBadge(p){ return '<b>'+pbEscape(pbStoreGet('t')||'')+'</b>'; }\n")
reg8 = json.load(open(os.path.join(d8, "registry.json"), encoding="utf-8"))

# undeclared: the check must still have teeth
_found, _graph = LC.run(d8)
check("pbStoreGet" in _graph.get("undefined", {}),
      "an undeclared module's functions are still reported undefined (the check keeps its teeth)")

# declared: in scope, and not an item
reg8["runtime"] = [{"id": "store", "src": "runtime/store.js", "why": "session store"}]
with open(os.path.join(d8, "registry.json"), "w", encoding="utf-8") as f:
    json.dump(reg8, f, indent=2, ensure_ascii=False)
    f.write("\n")
found2, graph8 = LC.run(d8)
undef2 = [f for f in found2 if f.code == "L-UNDEF"]
check(not undef2, "declaring it in registry.runtime[] puts its functions in scope (%d L-UNDEF)"
      % len(undef2))
check("pbStoreSet" not in graph8.get("undefined", {}),
      "including one the render bodies never call")
check([m for m in LE.runtime_module_paths(reg8, d8)] and
      os.path.basename(LE.runtime_module_paths(reg8, d8)[0][1]) == "store.js",
      "runtime_module_paths resolves a declared src")
check(not [i for i in graph8["items"] if i["id"] == "store"],
      "a runtime module is NOT a registry item — no items[] entry")
LE.write_contracts(d8, graph8)
check(not os.path.exists(os.path.join(d8, "logic", "runtime")),
      "and gets no logic/ sidecar of its own")
# a url-only entry has no local text and must not be reported missing
reg8["runtime"].append({"id": "x", "url": "https://example.test/x.js", "why": "dep"})
check(len(LE.runtime_module_paths(reg8, d8)) == 1,
      "a url-only entry is skipped, not treated as a missing file")
shutil.rmtree(d8, ignore_errors=True)

print()
if fails:
    print("FAIL — %d regression(s)" % len(fails))
    sys.exit(1)
print("PASS — the logic contract (0009), registry.runtime[], and the two runtime verbs")
