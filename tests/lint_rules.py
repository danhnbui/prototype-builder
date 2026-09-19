#!/usr/bin/env python3
"""tests/lint_rules.py — the W1-a lint changes (D-10, D-11, D-22, D-26).

Half of this file is a FALSE-POSITIVE CORPUS. That is deliberate and it is the point:
every rule here was changed because its first version was wrong on a real project, and
the numbers in the comments are what it was wrong by. A rule that cries wolf gets
ignored, and then it masks the real hit.

Exit: 0 pass, 1 fail.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")

_fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        _fails.append(msg)


def run(*args):
    return subprocess.run([sys.executable, LINT, *args], capture_output=True, text=True)


def write(d, reg, bodies=None):
    """Write a registry + its render bodies into dir `d`; return the registry path."""
    for ident, src in (bodies or {}).items():
        p = os.path.join(d, "render", "components", ident + ".js")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(src)
    path = os.path.join(d, "registry.json")
    open(path, "w", encoding="utf-8").write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    return path


def cmp_(ident, level="molecule", scope="local", **kw):
    c = {"id": ident, "name": ident.title(), "level": level, "scope": scope,
         "renderFn": "renderCmp" + "".join(w.title() for w in ident.split("-")),
         "renderSrc": f"render/components/{ident}.js"}
    c.update(kw)
    return c


def body(ident, inner=""):
    fn = "renderCmp" + "".join(w.title() for w in ident.split("-"))
    return "function %s(props) {\n  props = props || {};\n  return '<div>' + %s + '</div>';\n}\n" % (
        fn, inner or "''")


# ── D-10 · R-NEST accepts a local child ───────────────────────────────────────────────
print("D-10 — R-NEST")
with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", anatomy={"parts": [{"n": 1, "name": "Kid", "orgId": "kid"}]}),
                          cmp_("kid", level="atom", scope="local")]}
    p = write(d, reg, {"host": body("host", "pbUse('kid', {})"), "kid": body("kid")})
    r = run(p)
    check("R-NEST" not in r.stdout,
          "a part orgId pointing at a LOCAL component is legal (was an ERROR; it contradicted "
          "R-COMPOSE-MATCH — 39 of 57 carriers on a real project were blocked outright)")

with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", anatomy={"parts": [{"n": 1, "name": "Ghost", "orgId": "nope"}]})]}
    p = write(d, reg, {"host": body("host")})
    r = run(p)
    check("R-NEST" in r.stdout and r.returncode == 2,
          "an orgId resolving to NO component is still an ERROR")

# ── D-10 · R-NEST-HINT is whole-token, longest-match, prose-rejecting ─────────────────
print("D-10 — R-NEST-HINT false-positive corpus")
PROSE = [
    ("Toolbar — search + three filter comboboxes + download", "combobox"),
    ("Hidden input carrying the value", "input"),
    ("Page header — trail, title + status chip, subtitle, optional tabs", "tabs"),
    ("Delegate row — avatar + name + trash", "avatar"),
]
with tempfile.TemporaryDirectory() as d:
    parts = [{"n": i, "name": nm} for i, (nm, _) in enumerate(PROSE, 1)]
    globals_ = [cmp_(g, level="atom", scope="global") for _, g in PROSE]
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", anatomy={"parts": parts})] + globals_}
    p = write(d, reg, dict({"host": body("host")}, **{g: body(g) for _, g in PROSE}))
    r = run(p)
    check("R-NEST-HINT" not in r.stdout,
          "a PROSE part name never hints (4 fixtures; 6 of 12 hints on a real project were this)")

with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", anatomy={"parts": [{"n": 1, "name": "Select"}]}),
                          cmp_("select", level="atom", scope="global")]}
    p = write(d, reg, {"host": body("host"), "select": body("select")})
    r = run(p)
    check("R-NEST-HINT" in r.stdout and "'select'" in r.stdout,
          "a bare component-shaped name DOES hint — the rule still works")

with tempfile.TemporaryDirectory() as d:
    # 'Toggle Input' must not be advised to use the global `input`: the local `toggle-input`
    # is the better match, and since D-10 makes a local orgId legal, `input` is wrong advice.
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", anatomy={"parts": [{"n": 1, "name": "Toggle Input"}]}),
                          cmp_("input", level="atom", scope="global"),
                          cmp_("toggle-input", level="atom", scope="local")]}
    p = write(d, reg, {"host": body("host"), "input": body("input"),
                       "toggle-input": body("toggle-input")})
    r = run(p)
    check("R-NEST-HINT" not in r.stdout,
          "no hint when a LOCAL component is the better match — silence beats wrong advice")

# ── D-26 · R-PROPTYPE ─────────────────────────────────────────────────────────────────
print("D-26 — R-PROPTYPE")
with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [], "components": [
        cmp_("a", properties=[{"id": "rows", "type": "array", "default": "[]"}]),
        cmp_("b", properties=[{"id": "tiles", "type": "string", "default": "[]"}]),
        cmp_("c", properties=[{"id": "rows", "type": "array", "default": []}]),
        cmp_("e", properties=[{"id": "label", "type": "string", "default": "Hello"}]),
    ]}
    p = write(d, reg, {k: body(k) for k in "abce"})
    out = run(p).stdout
    check("id='a'" in out and "R-PROPTYPE" in out, "array type with a STRING default is flagged")
    check(any("id='b'" in l for l in out.splitlines() if "R-PROPTYPE" in l),
          "string type with a collection-literal default is flagged")
    check(not any("id='c'" in l for l in out.splitlines() if "R-PROPTYPE" in l),
          "array type with a REAL list default is clean (false-positive guard)")
    check(not any("id='e'" in l for l in out.splitlines() if "R-PROPTYPE" in l),
          "an ordinary string prop is clean (false-positive guard)")

# ── D-11 · --sync-elements is append-only and idempotent ─────────────────────────────
print("D-11 — --sync-elements")
with tempfile.TemporaryDirectory() as d:
    keep = {"id": "kept", "label": "a hand-written label nobody can reproduce",
            "orgId": "kid", "state": "default", "tokens": ["--x"]}
    reg = {"meta": {"name": "t"}, "tokens": {},
           "components": [cmp_("kid", level="atom"), cmp_("other", level="atom")],
           "screens": [{"id": "s", "name": "S", "level": "page",
                        "renderFn": "renderScreenS", "renderSrc": "render/screens/s.js",
                        "elements": [dict(keep)]}]}
    sp = os.path.join(d, "render", "screens", "s.js")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    open(sp, "w").write("function renderScreenS(props) {\n  return pbUse('kid', {}) + pbUse('other', {});\n}\n")
    p = write(d, reg, {"kid": body("kid"), "other": body("other")})

    before = open(p, "rb").read()
    r1 = run(p, "--sync-elements")
    after = json.load(open(p, encoding="utf-8"))
    els = after["screens"][0]["elements"]
    check(r1.returncode == 0 and "1 appended" in r1.stdout, "appends exactly the missing orgId")
    check(els[0] == keep, "the pre-existing entry survives byte-for-byte, still first")
    check(len(els) == 2 and els[1]["orgId"] == "other", "the appended entry lands at the END")
    check("(auto)" in els[1]["label"], "the appended label marks itself auto-generated")

    mid = open(p, "rb").read()
    r2 = run(p, "--sync-elements")
    check(r2.returncode == 0 and open(p, "rb").read() == mid,
          "a second run is a byte-for-byte no-op (idempotent)")
    check(before != mid, "the first run did write")

with tempfile.TemporaryDirectory() as d:
    # declared-but-not-composed is REPORTED, never deleted.
    reg = {"meta": {"name": "t"}, "tokens": {}, "components": [cmp_("kid", level="atom")],
           "screens": [{"id": "s", "name": "S", "level": "page", "renderFn": "renderScreenS",
                        "renderSrc": "render/screens/s.js",
                        "elements": [{"id": "ghost", "label": "planned", "orgId": "kid",
                                      "state": "default"}]}]}
    sp = os.path.join(d, "render", "screens", "s.js")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    open(sp, "w").write("function renderScreenS(props) {\n  return '';\n}\n")
    p = write(d, reg, {"kid": body("kid")})
    r = run(p, "--sync-elements")
    after = json.load(open(p, encoding="utf-8"))
    check(len(after["screens"][0]["elements"]) == 1 and "0 removed" in r.stdout,
          "a declared-but-not-composed entry is reported, never deleted")

# ── D-22 · --report ranks and never gates ────────────────────────────────────────────
print("D-22 — --report")
with tempfile.TemporaryDirectory() as d:
    # `host` is reached ONLY by a direct renderCmpHost call, never by pbUse. The naive
    # orphan check called this an orphan; on a real project that mistake produced 36
    # orphans where the true count is 0.
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [cmp_("host", level="atom"), cmp_("caller")]}
    p = write(d, reg, {
        "host": body("host"),
        "caller": "function renderCmpCaller(props) {\n  return window['renderCmpHost']({});\n}\n"})
    r = run(p, "--report")
    check(r.returncode == 0, "--report always exits 0, whatever the findings say")
    check("components reached by nothing      0" in r.stdout,
          "a component reached by a DIRECT renderCmp* call is not an orphan (the guard)")
    check("findings by code" in r.stdout and "fix first" in r.stdout,
          "--report prints the histogram and the ranked list")

with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [],
           "components": [{"id": "Bad Id", "level": "nope"}]}
    p = write(d, reg)
    r = run(p, "--report")
    check(r.returncode == 0, "--report exits 0 even with ERROR-severity findings present")
    check(run(p).returncode == 2, "...while a plain run of the same registry still exits 2")

print()
if _fails:
    print("FAIL — %d check(s):" % len(_fails))
    for f in _fails:
        print("   - " + f)
    sys.exit(1)
print("PASS — lint rule changes (D-10, D-11, D-22, D-26) behave")
