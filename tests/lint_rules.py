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
import re
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import lint_registry as L  # noqa: E402  (in-process, for the rule-level corpus below)

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

# ── L3 · --sync-elements is a locked, atomic read-modify-write ────────────────────────
print("L3 — --sync-elements takes the registry lock, reads inside it, and writes atomically")
import importlib  # noqa: E402
import time  # noqa: E402
pbslice = importlib.import_module("slice")        # `import slice` would shadow the builtin
with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t"}, "tokens": {},
           "components": [cmp_("kid", level="atom"), cmp_("other", level="atom")],
           "screens": [{"id": "s", "name": "S", "level": "page",
                        "renderFn": "renderScreenS", "renderSrc": "render/screens/s.js", "elements": []}]}
    sp = os.path.join(d, "render", "screens", "s.js")
    os.makedirs(os.path.dirname(sp), exist_ok=True)
    open(sp, "w").write("function renderScreenS(props) {\n  return pbUse('kid', {}) + pbUse('other', {});\n}\n")
    p = write(d, reg, {"kid": body("kid"), "other": body("other")})
    os.chmod(p, 0o640)
    with pbslice.registry_lock(p, "a test holding the lock"):
        held = open(p, "rb").read()
        r = subprocess.run([sys.executable, LINT, "--sync-elements", p], capture_output=True, text=True,
                           env=dict(os.environ, PB_LOCK_TIMEOUT="0.4"))
        check(r.returncode == 2 and "being written" in r.stderr and "a test holding the lock" in r.stderr
              and "Traceback" not in r.stderr,
              "a held registry lock refuses --sync-elements, naming the holder (exit %d)" % r.returncode)
        check(open(p, "rb").read() == held, "…and registry.json is byte-identical")
    waiter = subprocess.Popen([sys.executable, LINT, "--sync-elements", p], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=dict(os.environ, PB_LOCK_TIMEOUT="30"))
    with pbslice.registry_lock(p, "a test holding the lock again"):
        time.sleep(1.5)
        waiting = waiter.poll() is None
        mid = json.load(open(p, encoding="utf-8"))
        mid["meta"]["editedWhileLocked"] = "yes"
        pbslice._write(p, mid)
        ino = os.stat(p).st_ino
    out, err = waiter.communicate(timeout=60)
    after = json.load(open(p, encoding="utf-8"))
    check(waiting, "a writer that finds the lock held WAITS for it (an unlocked one would already have finished)")
    check(waiter.returncode == 0 and after["meta"].get("editedWhileLocked") == "yes",
          "…then reads the registry afresh: the edit saved meanwhile is not overwritten (%s)" % err.strip()[:80])
    check([e["orgId"] for e in after["screens"][0]["elements"]] == ["kid", "other"], "…and its own append is there")
    check(os.stat(p).st_ino != ino and stat.S_IMODE(os.stat(p).st_mode) == 0o640
          and [f for f in os.listdir(d) if f.endswith(".tmp")] == [],
          "the write replaced the file (a new inode), kept its mode, and left no temp file")
    r = subprocess.run([sys.executable, LINT, "--sync-elements", os.path.join(d, "nope.json")], capture_output=True, text=True)
    check(r.returncode == 2 and "R-IO" in r.stderr and not os.path.exists(os.path.join(d, "nope.json.lock")),
          "a missing registry is reported (R-IO) before any lock file is made")

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


# ─────────────────────────────────────────────────────────────────────────────
# R-TOKENREF — a var(--x) nothing will ever set.
#
# Half of this is a FALSE-POSITIVE CORPUS, and it is the larger half on purpose: the first
# draft of this rule reported every component in the golden fixture and both demo screens,
# because it knew only one of the three things that legitimately set a custom property.
# Each case below is a shape that MUST stay silent.
# ─────────────────────────────────────────────────────────────────────────────
print("R-TOKENREF · a custom property nothing sets")


def _tokenref(body, tokens=None):
    """Lint a one-component registry whose body is `body`; return its R-TOKENREF messages."""
    reg = {
        "meta": {"name": "t", "schemaVersion": 11},
        "tokens": tokens or {},
        "components": [{"id": "c", "name": "C", "level": "atom", "renderFn": "renderCmpC",
                        "render": body}],
        "screens": [],
    }
    return [f.msg for f in L.check(reg) if f.code == "R-TOKENREF"]


# — true positives —
hits = _tokenref("return '<i style=\"gap:var(--nope-not-a-token)\"></i>';")
check(len(hits) == 1 and "nothing sets it" in hits[0],
      "no fallback + no producer anywhere is a finding")

hits = _tokenref("return '<i style=\"color:var(--ghost, red)\"></i>';",
                 {"ghost": {"$value": "   ", "$type": "color"}})
check(len(hits) == 1 and "does NOT fall back" in hits[0],
      "a token that exists but resolves to nothing IS a finding, fallback or not "
      "— the browser drops the declaration instead of falling back")

# — the false-positive corpus: every one of these must stay silent —
check(_tokenref("return '<i style=\"color:var(--brand)\"></i>';",
                {"brand": {"$value": "#4f46e5", "$type": "color"}}) == [],
      "FP: a name the project's own tokens define")

check(_tokenref("return '<i style=\"border:1px solid var(--border)\"></i>';") == [],
      "FP: a name the SHELL declares (58 of them) — the first draft reported all of these")

check(_tokenref("return '<i style=\"--pb-x: 4px; padding:var(--pb-x)\"></i>';") == [],
      "FP: a component-scoped property the body sets and reads itself")

check(_tokenref("return '<i style=\"max-width:var(--pb-tt-max, 240px)\"></i>';") == [],
      "FP: a fallback on a name meant to be set by a parent at runtime — that is the "
      "design working, not a defect")

check(_tokenref("return '<i style=\"background:var(--bg-' + tone + '-muted)\"></i>';") == [],
      "FP: a name composed at runtime — counted as information, never a finding")

check(_tokenref("return '<i class=\"x\"></i>';") == [], "FP: a body with no var(--…) at all")

# — the guard that switches the rule off rather than guessing —
_saved = L._SHELL_PROPS_CACHE[:]
L._SHELL_PROPS_CACHE[:] = [None]
check(_tokenref("return '<i style=\"gap:var(--nope-not-a-token)\"></i>';") == [],
      "with no shell to read the rule does not run — a check blind to one of its three "
      "producers is worse than no check")
L._SHELL_PROPS_CACHE[:] = _saved

# ── R-RETIRED · meta.others / meta.tradeoffs (D-33) ───────────────────────────────────
print("R-RETIRED — advisory, never an error, never the reason for an exit code")
GOLDEN_REG = os.path.join(ROOT, "fixtures", "golden", "registry.json")


_DANGER = {"danger": {"$value": "#d92d20", "$type": "color"}}      # the runtime-required token: keeps the base registry warning-free


def _retired_reg(**meta_extra):
    return {"meta": dict({"name": "t"}, **meta_extra), "tokens": dict(_DANGER), "screens": [], "components": []}


def _findings(reg, strict=False):
    return [f for f in L.check(reg, strict=strict) if f.code == "R-RETIRED"]


for strict in (False, True):
    tag = "--strict" if strict else "default"
    got = _findings(_retired_reg(others={"live": [1, 2]}, tradeoffs=[{"title": "x"}]), strict)
    check(sorted(f.where for f in got) == ["meta.others", "meta.tradeoffs"] and all(f.severity == "WARN" for f in got),
          "%s: both fields fire, as WARN (never promoted to ERROR)" % tag)
    check(all("still works" in f.msg and f.where in f.msg for f in got) and
          any("runtime module" in f.msg for f in got if f.where == "meta.others") and
          any("ia.rules[]" in f.msg for f in got if f.where == "meta.tradeoffs"),
          "%s: the message names the field, says it still works, and where to move the data" % tag)
    check(_findings(_retired_reg(others=None, tradeoffs=[]), strict) == [] and
          _findings(_retired_reg(others={}, tradeoffs=""), strict) == [] and
          _findings(_retired_reg(), strict) == [],
          "%s: absent, null, [] , {} and '' are not data — nothing fires" % tag)

with tempfile.TemporaryDirectory() as d:
    clean_p = write(d, _retired_reg(others=None, tradeoffs=[]))
    for flags in ((), ("--strict",)):
        r = run(*flags, clean_p)
        check(r.returncode == 0 and "R-RETIRED" not in r.stdout, "a clean registry %s: exit 0, no finding" % (" ".join(flags) or "(default)"))
    for flags in ((), ("--strict",)):
        with tempfile.TemporaryDirectory() as d2:
            p2 = write(d2, _retired_reg(others={"live": "data"}, tradeoffs=[{"title": "t"}]))
            r = run(*flags, p2)
            label = " ".join(flags) or "(default)"
            check("WARN [R-RETIRED]" in r.stdout and "ERROR [R-RETIRED]" not in r.stdout,
                  "%s: printed as WARN" % label)
            check(r.returncode == 0, "%s: the SAME exit code as the clean registry — 0, the rule alone raises nothing (rc=%d)"
                  % (label, r.returncode))
            check("advisory" in r.stdout and "0 warning" not in r.stdout.replace("advisory", ""),
                  "%s: the summary says the findings are advisory" % label)
    # …but a real warning beside it still exits 1, and still counts only itself
    with tempfile.TemporaryDirectory() as d3:
        reg3 = {"meta": {"name": "t", "others": {"live": 1}}, "tokens": dict(_DANGER), "screens": [],
                "components": [cmp_("hexy", level="atom")]}
        p3 = write(d3, reg3, {"hexy": "function renderCmpHexy(props) {\n  return '<i style=\"color:#ff0000\"></i>';\n}\n"})
        r = run(p3)
        check(r.returncode == 1 and "WARN [R-HEX]" in r.stdout and "1 warning(s) (1 advisory" in r.stdout,
              "a genuine WARN next to it still exits 1, and the count is its own (rc=%d)" % r.returncode)
r = run("--strict", GOLDEN_REG)
check(r.returncode == 0 and "WARN [R-RETIRED] meta.tradeoffs" in r.stdout,
      "the CI command (--strict fixtures/golden/registry.json) still exits 0 although the golden keeps a trade-off in the retired field")

# ── R-ENTRY · R-PERM — the demo model (v2.5) ──────────────────────────────────────────
print("R-ENTRY / R-PERM — only when the project declares a demo model")
DEMO_REG = os.path.join(ROOT, "fixtures", "demo-model", "registry.json")


def _dm_reg(screens=None, comps=None, runtime=None, **meta_extra):
    """A small valid demo model; a test overrides the one field it breaks ("<drop>" removes one)."""
    meta = {"name": "t",
            "roles": [{"id": "admin", "name": "Admin", "isAdmin": True},
                      {"id": "staff", "name": "Staff"}, {"id": "guest", "name": "Guest"}],
            "permissions": {"levels": ["none", "view", "approve"],
                            "matrix": {"staff": {"request": "approve", "report": "view"}}},
            "personas": [{"id": "staff-a", "name": "Staff A", "role": "staff", "scope": {"region": "n"}},
                         {"id": "guest-a", "name": "Guest A", "role": "guest"}],
            "demo": {"seeds": ["empty", {"id": "full", "name": "Full"}],
                     "entries": [{"id": "start", "name": "Start", "screen": "home", "role": "staff",
                                  "persona": "staff-a", "seed": "empty", "default": True}]}}
    meta.update(meta_extra)
    for k in [k for k, v in meta.items() if v == "<drop>"]:
        del meta[k]
    reg = {"meta": meta, "tokens": dict(_DANGER), "components": comps or [],
           "screens": screens or [{"id": "home", "name": "Home", "renderFn": "renderScreenHome", "render": "return '';"},
                                  {"id": "vault", "name": "Vault", "renderFn": "renderScreenVault", "render": "return '';",
                                   "roles": ["admin", "staff"]},
                                  {"id": "gated", "name": "Gated", "renderFn": "renderScreenGated", "render": "return '';",
                                   "roles": ["admin"]}]}
    if runtime is not None:
        reg["runtime"] = runtime
    return reg


def _dm(reg, code, strict=False):
    return [f for f in L.check(reg, strict=strict) if f.code == code]


def _entry(**kw):
    e = {"id": "e2", "name": "Second", "screen": "home"}
    e.update(kw)
    return e


def _with_entries(*extra):
    reg = _dm_reg()
    reg["meta"]["demo"]["entries"] += list(extra)
    return reg


check(_dm(_dm_reg(), "R-ENTRY") == [] and _dm(_dm_reg(), "R-PERM") == [],
      "the base demo model used below is itself clean (so each finding is the one thing broken)")

ENTRY_CASES = [
    ("unknown screen", _entry(screen="nowhere"), "screen 'nowhere'"),
    ("unknown role", _entry(role="ghost"), "role 'ghost'"),
    ("unknown persona", _entry(persona="ghost"), "persona 'ghost'"),
    ("unknown seed", _entry(seed="ghost"), "seed 'ghost'"),
    ("missing id", {"name": "N", "screen": "home"}, "'id'"),
    ("missing name", {"id": "e2", "screen": "home"}, "'name'"),
    ("missing screen", {"id": "e2", "name": "N"}, "'screen'"),
    ("duplicate entry id", _entry(id="start"), "'start' is used twice"),
    ("a second default", _entry(default=True), "2 entries have default: true"),
    ("persona of another role", _entry(role="staff", persona="guest-a"), "persona 'guest-a' belongs to role 'guest'"),
    ("role the screen does not allow", _entry(screen="gated", role="staff"), "role 'staff' cannot see screen 'gated'"),
]
for label, entry, needle in ENTRY_CASES:
    got = _dm(_with_entries(entry), "R-ENTRY")
    check(len(got) == 1 and needle in got[0].msg and got[0].severity == "WARN" and got[0].where.startswith("meta.demo.entries"),
          "R-ENTRY, %s: one WARN naming the value (%s)" % (label, got[0].msg[:60] if got else "none"))
    got = _dm(_with_entries(entry), "R-ENTRY", strict=True)
    check(len(got) == 1 and got[0].severity == "ERROR", "R-ENTRY, %s: ERROR under --strict" % label)
check(any("id='e2'" in f.where for f in _dm(_with_entries(_entry(screen="nowhere")), "R-ENTRY")),
      "R-ENTRY names the entry id in the location")
check(_dm(_with_entries(_entry(screen="gated", role="admin")), "R-ENTRY") == [] and
      _dm(_with_entries(_entry(screen="vault", role="staff")), "R-ENTRY") == [] and
      _dm(_with_entries(_entry(screen="home", role="guest")), "R-ENTRY") == [],
      "R-ENTRY: an isAdmin role is allowed everywhere, a listed role on its screen, any role on a screen with no roles[]")
reg = _dm_reg()
reg["meta"]["demo"]["seeds"] = ["empty", {"id": "empty", "name": "Again"}]
got = _dm(reg, "R-ENTRY")
check(len(got) == 1 and "seed id 'empty' is used twice" in got[0].msg,
      "R-ENTRY: a duplicate seed id (the string and {id, name} forms count as one id space)")
reg = _dm_reg()
reg["meta"]["demo"]["entries"] = [_entry(seed="a-seed")]
reg["meta"]["demo"]["seeds"] = ["a-seed", {"id": "b-seed"}]
check(_dm(reg, "R-ENTRY") == [], "R-ENTRY: seeds may be strings or {id, name}; an entry may omit role, persona and seed")

PERM_CASES = [
    ("levels empty", {"permissions": {"levels": [], "matrix": {}}}, "levels must be a non-empty list"),
    ("levels not a list", {"permissions": {"levels": "none", "matrix": {}}}, "levels must be a non-empty list"),
    ("levels not unique", {"permissions": {"levels": ["a", "a"], "matrix": {}}}, "unique"),
    ("levels with a non-string", {"permissions": {"levels": ["a", 2], "matrix": {}}}, "levels must be a non-empty list"),
    ("matrix row for an undeclared role", {"permissions": {"levels": ["none", "view"], "matrix": {"ghost": {"x": "view"}}}},
     "role 'ghost'"),
    ("cell with an undeclared level", {"permissions": {"levels": ["none", "view"], "matrix": {"staff": {"x": "godmode"}}}},
     "'godmode'"),
    ("persona without id", {"personas": [{"name": "N", "role": "staff"}]}, "'id'"),
    ("persona without name", {"personas": [{"id": "p", "role": "staff"}]}, "'name'"),
    ("persona without role", {"personas": [{"id": "p", "name": "N"}]}, "'role'"),
    ("duplicate persona id", {"personas": [{"id": "p", "name": "N", "role": "staff"}, {"id": "p", "name": "M", "role": "staff"}]},
     "persona id 'p' is used twice"),
    ("persona with an undeclared role", {"personas": [{"id": "p", "name": "N", "role": "ghost"}]}, "role 'ghost'"),
    ("persona scope not an object", {"personas": [{"id": "p", "name": "N", "role": "staff", "scope": "north"}]},
     "scope that is not an object"),
]
for label, meta_extra, needle in PERM_CASES:
    reg = _dm_reg(**dict(meta_extra, demo="<drop>"))
    got = _dm(reg, "R-PERM")
    check(len(got) >= 1 and any(needle in f.msg for f in got) and all(f.severity == "WARN" for f in got),
          "R-PERM, %s: WARN naming the value (%s)" % (label, got[0].msg[:60] if got else "none"))
    strict_got = _dm(reg, "R-PERM", strict=True)
    check(bool(strict_got) and all(f.severity == "ERROR" for f in strict_got), "R-PERM, %s: ERROR under --strict" % label)
check(any("id='p'" in f.where for f in _dm(_dm_reg(personas=[{"id": "p", "name": "N", "role": "ghost"}], demo="<drop>"), "R-PERM")),
      "R-PERM names the persona id in the location")
check(_dm(_dm_reg(permissions="<drop>", demo="<drop>"), "R-PERM") == [] and
      len(_dm(_dm_reg(personas=[{"id": "p", "name": "N", "role": "ghost"}], permissions="<drop>", demo="<drop>"), "R-PERM")) == 1,
      "R-PERM: personas alone (no permissions) are checked — clean is silent, a bad role fires")
check(_dm(_dm_reg(personas="<drop>", demo="<drop>", permissions={"levels": ["none"], "matrix": {"staff": {"x": "none"}}}), "R-PERM") == [],
      "R-PERM: permissions alone (no personas) is checked, and a clean one is silent")

# the body scan: literal capabilities in a body, a runtime module and a style sheet
SCAN_BODY = (
    "// data-can=\"commented-out\" and pbCan('commented-too')\n"
    "function renderCmpScan(props) {\n"
    "  var ok = pbCan('request', 'approve') && pbCan(\"report\");\n"
    "  var typo = pbCan('reqest');\n"
    "  var lvl = pbCan('request', 'godmode');\n"
    "  var dyn = pbCan(props.cap, 'approve') + pbCan('cap-' + props.x);\n"
    "  return '<a data-can=\"request:approve\">a</a><a data-can=\"report\">b</a>'\n"
    "    + '<a data-can=\"nosuch\">c</a><a data-can=\"request:nope\">d</a><a data-can=\\'single\\'>e</a>'\n"
    "    + '<a data-can=\"' + pbEscape(props.can) + '\" data-can-mode=\"hide\">dyn</a>';\n"
    "}\n"
)
with tempfile.TemporaryDirectory() as d:
    reg = _dm_reg(comps=[cmp_("scan", level="atom")], runtime=[{"id": "mod", "src": "runtime/mod.js"}])
    os.makedirs(os.path.join(d, "runtime"))
    open(os.path.join(d, "runtime", "mod.js"), "w").write("window.x = pbCan('from-module');\n// pbCan('module-comment')\n")
    os.makedirs(os.path.join(d, "render", "styles"))
    open(os.path.join(d, "render", "styles", "scan.css"), "w").write(
        "/* [data-can=\"css-comment\"] */\n.c-scan [data-can=\"from-style\"] { color: var(--danger); }\n")
    reg["components"][0]["styleSrc"] = "render/styles/scan.css"
    p = write(d, reg, {"scan": SCAN_BODY})
    found = [f for f in L.check(json.load(open(p)), base_dir=d) if f.code == "R-PERM"]
    reported = sorted(re.match(r"(?:capability|level) '([^']*)'", f.msg).group(1) for f in found)
    check(reported == sorted(["reqest", "godmode", "nosuch", "nope", "single", "from-module", "from-style"]) and
          all(f.severity == "WARN" for f in found),
          "R-PERM body scan: exactly the seven bad literals, each once, all WARN — not the declared ones, not the commented-out "
          "ones, not the dynamic ones, not `data-can=\"' + …` (got %s)" % reported)
    check(any("runtime[0]" in f.where for f in found) and any("styleSrc" in f.where for f in found) and
          any("components[0] id='scan'" in f.where for f in found),
          "R-PERM body scan: the finding names the component, the runtime module or the style sheet it is in")
    r = run(p)
    check(r.returncode == 1 and "WARN [R-PERM]" in r.stdout and "ERROR [R-PERM]" not in r.stdout,
          "CLI: the body-scan findings are WARN and exit 1 (rc=%d)" % r.returncode)
    r = run("--strict", p)
    check(r.returncode == 2 and "ERROR [R-PERM]" in r.stdout, "CLI --strict: the same findings are ERROR and exit 2 (rc=%d)" % r.returncode)
    # no meta.permissions: the same bodies are not scanned for capabilities at all
    reg2 = json.load(open(p))
    del reg2["meta"]["permissions"]
    check([f for f in L.check(reg2, base_dir=d) if f.code == "R-PERM"] == [],
          "the body scan runs only when meta.permissions is present (personas alone: no capability check)")

# the clean fixture, with and without --strict
for flags in ((), ("--strict",)):
    r = run(*flags, DEMO_REG)
    check(r.returncode == 0 and "R-ENTRY" not in r.stdout and "R-PERM" not in r.stdout,
          "fixtures/demo-model %s: exit 0, no finding" % (" ".join(flags) or "(default)"))
fx = json.load(open(DEMO_REG))
check(not [f for f in L.check(fx, base_dir=os.path.dirname(DEMO_REG)) if f.code in ("R-ENTRY", "R-PERM")],
      "fixtures/demo-model: no R-ENTRY / R-PERM in-process either (its pbCan('request', 'approve') is a declared pair)")
fx["meta"]["demo"]["entries"][0]["screen"] = "nowhere"
fx["meta"]["permissions"]["matrix"]["reviewer"]["report"] = "godmode"
check({f.code for f in L.check(fx, base_dir=os.path.dirname(DEMO_REG))} >= {"R-ENTRY", "R-PERM"},
      "…and breaking two fields of that fixture does fire both (the clean result is not a dead rule)")

# the CLI exit codes: WARN by default (exit 1), ERROR under --strict (exit 2)
with tempfile.TemporaryDirectory() as d:
    reg = _with_entries(_entry(screen="nowhere"))
    reg["meta"]["personas"][0]["role"] = "ghost"
    p = write(d, reg)
    r = run(p)
    check(r.returncode == 1 and "WARN [R-ENTRY]" in r.stdout and "WARN [R-PERM]" in r.stdout and "ERROR [R-" not in r.stdout,
          "CLI default: both rules are WARN and exit 1, not 2 (rc=%d)" % r.returncode)
    r = run("--strict", p)
    check(r.returncode == 2 and "ERROR [R-ENTRY]" in r.stdout and "ERROR [R-PERM]" in r.stdout,
          "CLI --strict: both rules are ERROR and exit 2 (rc=%d)" % r.returncode)

# a registry that declares none of the three fields gets nothing, however its bodies read
with tempfile.TemporaryDirectory() as d:
    reg = {"meta": {"name": "t", "roles": [{"id": "a", "name": "A"}], "others": None}, "tokens": dict(_DANGER), "screens": [],
           "components": [cmp_("scan", level="atom")]}
    p = write(d, reg, {"scan": SCAN_BODY})
    for flags in ((), ("--strict",)):
        r = run(*flags, p)
        check("R-ENTRY" not in r.stdout and "R-PERM" not in r.stdout,
              "no meta.permissions / personas / demo %s: not one R-ENTRY or R-PERM, even with data-can and pbCan in a body"
              % (" ".join(flags) or "(default)"))
for absent in ({}, {"permissions": None, "personas": None, "demo": None}):
    reg = _dm_reg(**dict({"permissions": "<drop>", "personas": "<drop>", "demo": "<drop>"}, **absent))
    check(not [f for f in L.check(reg) if f.code in ("R-ENTRY", "R-PERM")],
          "fields absent or null (%s): no finding" % (", ".join(sorted(absent)) or "all dropped"))
check(not [f for f in L.check(json.load(open(GOLDEN_REG))) if f.code in ("R-ENTRY", "R-PERM")],
      "fixtures/golden declares no demo model: no R-ENTRY / R-PERM")

# ── --exec · the context a body runs in cannot reach the host ─────────────────────────
print("--exec — a body is somebody else's code")
import shutil  # noqa: E402

# The harness as it was before the hardening: `console` is a HOST object inside a context built from a host literal.
_OLD_HARNESS = r"""
'use strict';
const vm = require('vm');
const job = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const msg = (e) => String((e && e.message) || e).split('\n')[0].slice(0, 160);
const quiet = { log() {}, info() {}, warn() {}, error() {}, debug() {} };
const ctx = vm.createContext({ console: quiet });
const run = (code, name) => vm.runInContext(code, ctx, { timeout: job.ms, filename: name });
const notes = [];
run(job.prelude + '\nvar PB_REGISTRY = ' + job.registry + ';', 'pb-exec-prelude.js');
try { run(job.runtime, 'runtime.js'); } catch (e) { notes.push(['runtime.js', msg(e)]); }
run(job.stubs, 'pb-exec-stubs.js');
for (const m of job.modules) { try { run(m.js, m.src); } catch (e) { notes.push([m.src, msg(e)]); } }
const results = [];
for (const b of job.bodies) {
  const r = { key: b.key, runs: [] };
  try { run(b.js, b.src); } catch (e) { r.compile = msg(e); results.push(r); continue; }
  for (const p of b.runs) {
    try {
      const out = run('window[' + JSON.stringify(b.fn) + '](JSON.parse(' + JSON.stringify(p.props) + '))', b.src);
      r.runs.push({ label: p.label, type: out === null ? 'null' : typeof out,
                    empty: typeof out === 'string' && !out.trim() });
    } catch (e) { r.runs.push({ label: p.label, error: msg(e) }); }
  }
  results.push(r);
}
process.stdout.write(JSON.stringify({ notes, results }));
"""

# Each probe asks the host a question and returns a NUMBER when the host answered `object` (the escape),
# so the result is visible through R-EXEC's own vocabulary: "returned number, not a string".
_ESC = "var t = %s;\n  return t === 'object' ? 42 : '<i>' + t + '</i>';"
EXEC_BODIES = {
    "esc-console": _ESC % "console.log.constructor('return typeof process')()",
    "esc-this": _ESC % "this.constructor.constructor('return typeof process')()",
    "esc-error": _ESC % "console.error.constructor('return typeof process')()",
    "esc-eval": _ESC % "(0, eval)('typeof process')",
    "esc-newfn": _ESC % "new Function('return typeof process')()",
    "normal-log": "console.log('a'); console.warn('b'); console.info('c'); console.debug('d'); console.error('e');\n"
                  "  return '<div>' + typeof console.log + '</div>';",
    "normal-plain": "props = props || {};\n  return '<div>' + pbEscape(props.label || 'ok') + pbUse('x', {}) + '</div>';",
    "normal-throw": "return props.rows.map(function (r) { return r; }).join('');",
}


def _exec_findings(harness=None):
    with tempfile.TemporaryDirectory() as d:
        bodies, comps = {}, []
        for cid, inner in EXEC_BODIES.items():
            fn = "renderCmp" + "".join(w.title() for w in cid.split("-"))
            bodies[cid] = "function %s(props) {\n  %s\n}\n" % (fn, inner)
            comps.append(cmp_(cid, level="atom"))
        reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [], "components": comps}
        write(d, reg, bodies)
        saved = L._EXEC_HARNESS
        if harness:
            L._EXEC_HARNESS = harness
        try:
            found, notes = L.check_exec(reg, d)
        finally:
            L._EXEC_HARNESS = saved
    return {re.search(r"id='([^']+)'", f.where).group(1) if re.search(r"id='([^']+)'", f.where) else f.where: f.msg
            for f in found}, notes


import re  # noqa: E402

if not shutil.which("node"):
    print("  - node not on PATH: the --exec escape test was NOT run (skipped, not passed)")
else:
    old, _n = _exec_findings(_OLD_HARNESS)
    new, _n = _exec_findings()
    PROBES = ("esc-console", "esc-this", "esc-error")
    check(all("returned number" in old.get(k, "") for k in PROBES),
          "NEGATIVE CONTROL — the old harness lets a body reach `process` (console.log.constructor, "
          "this.constructor.constructor, console.error.constructor): %s" % {k: old.get(k, "")[:28] for k in PROBES})
    check(all("returned number" not in new.get(k, "") for k in EXEC_BODIES),
          "the hardened harness: no body gets `object` back from `typeof process`")
    check(all("Code generation from strings disallowed" in new.get(k, "") for k in PROBES + ("esc-eval", "esc-newfn")),
          "console.log.constructor(…), this.constructor.constructor(…), eval and new Function all throw an EvalError, "
          "reported as R-EXEC: %s" % {k: new.get(k, "")[:40] for k in ("esc-this", "esc-eval")})
    check("--exec runs a body with eval" in new.get("esc-newfn", ""),
          "…and the finding says why (the gate switches eval / new Function off), so a body that needs them is not a mystery")
    check("normal-log" not in new and "normal-plain" not in new,
          "normal bodies — console.log/warn/info/debug/error, pbEscape, pbUse — still run clean")
    check("normal-throw" in new and "Cannot read properties of undefined" in new["normal-throw"],
          "a body that really throws still reports its own message: %s" % new.get("normal-throw", "")[:60])
    check(set(k for k in new if k.startswith("normal")) == {"normal-throw"} and
          set(k for k in old if k.startswith("normal")) == {"normal-throw"},
          "old and new agree on every normal body")

    # the same through the CLI, on a folder whose name has glob syntax in it
    with tempfile.TemporaryDirectory() as d:
        proj = os.path.join(d, "proj [x]")
        os.makedirs(proj)
        bodies = {"esc-this": "function renderCmpEscThis(props) {\n  %s\n}\n" % (_ESC % "this.constructor.constructor('return typeof process')()")}
        p = write(proj, {"meta": {"name": "t"}, "tokens": {}, "screens": [], "components": [cmp_("esc-this", level="atom")]}, bodies)
        r = run("--exec", p)
        check(r.returncode == 2 and "[R-EXEC]" in r.stdout and "Code generation" in r.stdout and "Traceback" not in r.stderr,
              "CLI: an escape attempt is an R-EXEC finding (exit 2), not a crash")

print()
if _fails:
    print("FAIL — %d check(s):" % len(_fails))
    for f in _fails:
        print("   - " + f)
    sys.exit(1)
print("PASS — lint rule changes (D-10, D-11, D-22, D-26), R-TOKENREF, R-ENTRY and R-PERM behave")
