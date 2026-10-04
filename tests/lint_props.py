#!/usr/bin/env python3
"""tests/lint_props.py — the props contract (R-PROP-DECLARED, R-PROP-USED) and the execution
gate (R-EXEC, `lint_registry.py --exec`).

The owner's complaint behind these: a first design shows components whose declared variants the
body never renders, and a body that throws or returns nothing passes `--strict` (seen on a
real project). Half of this file is a FALSE-POSITIVE CORPUS, as in tests/lint_rules.py: every guard in
the rules was added because a real body tripped it, and a rule that cries wolf gets ignored.

The R-EXEC half runs in a folder named `proj [x]` — glob syntax in the path is what broke four
tools on a real `[HR] …` project folder. It needs node; without it that half reports itself skipped
and the file exits 2, so a sweep cannot mistake "did not run" for a pass.

Exit: 0 pass · 1 fail · 2 the node half could not run (everything else still checked).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import lint_registry as L  # noqa: E402

_fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        _fails.append(msg)


def comp(cid, body, properties=None, level="atom"):
    fn = "renderCmp" + "".join(w.title() for w in cid.split("-"))
    return {"id": cid, "name": cid, "level": level, "scope": "local", "renderFn": fn,
            "render": body, "properties": properties or []}


def enum(pid, values, default=None):
    return {"id": pid, "type": "enum", "default": default if default is not None else values[0],
            "options": [{"label": v.title(), "value": v} for v in values]}


def findings(components, strict=False):
    reg = {"meta": {"name": "t"}, "tokens": {}, "screens": [], "components": components}
    return L.check(reg, strict=strict)


def codes(components, code, strict=False):
    return [f for f in findings(components, strict) if f.code == code]


# ── R-PROP-DECLARED ───────────────────────────────────────────────────────────────────────
print("R-PROP-DECLARED — a prop the body reads that properties[] does not declare")
hits = codes([comp("chip", "return '<i>' + pbEscape(props.tone) + '</i>';")], "R-PROP-DECLARED")
check(len(hits) == 1 and "props.tone" in hits[0].msg and hits[0].severity == L.WARN,
      "an undeclared read is a WARN by default")
hits = codes([comp("chip", "return '<i>' + pbEscape(props.tone) + '</i>';")], "R-PROP-DECLARED", True)
check(len(hits) == 1 and hits[0].severity == L.ERROR, "…and an ERROR under --strict")

hits = codes([comp("chip", "var p = props || {};\nreturn '<i>' + pbEscape(p.size) + '</i>';")],
             "R-PROP-DECLARED")
check(len(hits) == 1 and "props.size" in hits[0].msg, "a read through an alias (`var p = props`) counts")

hits = codes([comp("chip", "var { tone, size: s } = props;\nreturn '<i>' + tone + s + '</i>';")],
             "R-PROP-DECLARED")
check(len(hits) == 1 and "props.tone" in hits[0].msg and "props.size" in hits[0].msg,
      "destructured keys count")

# — the false-positive corpus —
WIRING = ("props = props || {};\nvar a = '';\n"
          "if (props.dataNav) a += ' data-nav=\"' + pbEscape(props.dataNav) + '\"';\n"
          "if (props.dataAction) a += ' data-action=\"' + pbEscape(props.dataAction) + '\"';\n"
          "if (props.ariaLabel) a += ' aria-label=\"' + pbEscape(props.ariaLabel) + '\"';\n"
          "return '<button id=\"' + pbEscape(props.id) + '\" class=\"' + pbEscape(props.className) + '\"'"
          " + a + (props.full ? ' style=\"width:100%\"' : '') + '>' + pbEscape(props.label) + '</button>';")
check(codes([comp("btn", WIRING, [{"id": "label", "type": "string", "default": "Go"}])],
            "R-PROP-DECLARED") == [],
      "FP: wiring props (dataX, ariaX, id, className, full) are pass-through attributes, not "
      "variants — the set registry_to_figma drops too (golden button: 9 of them)")
check(codes([comp("chip", "/* props.legacy was retired; see decisions 12 */\n"
                          "// props.old too\nreturn '<i>x</i>';")], "R-PROP-DECLARED") == [],
      "FP: `props.x` inside a comment is prose, not a read")
check(codes([comp("chip", "props = props || {};\n"
                          "return '<i>' + (props.hasOwnProperty('x') ? 'a' : 'b') + '</i>';")],
            "R-PROP-DECLARED") == [],
      "FP: an Object.prototype method is not a prop")
check(codes([comp("chip", "return '<i>' + pbEscape(\"props.tone\") + '</i>';")],
            "R-PROP-DECLARED") == [],
      "FP: `props.x` inside a string literal is not a read")
check(not any(f.code == "R-PROP-DECLARED" for f in L.check(
    {"meta": {}, "tokens": {}, "components": [],
     "screens": [{"id": "s", "renderFn": "renderScreenS", "render": "return pbUse('x', {to: props.route});"}]})),
      "FP: screens carry no properties[] contract, so their reads are not checked")

# ── R-PROP-USED ───────────────────────────────────────────────────────────────────────────
print("R-PROP-USED — a declared option the body never renders")
FAKE = ("function renderCmpCard(props) {\n  props = props || {};\n"
        "  return '<div class=\"card\">' + pbEscape(props.title) + '</div>';\n}\n")
card_props = [{"id": "title", "type": "string", "default": "T"}, enum("state", ["default", "loading"])]
hits = codes([comp("card", FAKE, card_props, level="atom")], "R-PROP-USED", strict=True)
check(len(hits) == 1 and "'loading'" in hits[0].msg and hits[0].severity == L.ERROR
      and "fake interactive" in hits[0].msg,
      "a declared `state` the body never branches on is an ERROR under --strict (golden login-card "
      "shipped exactly this)")
hits = codes([comp("card", FAKE, card_props)], "R-PROP-USED")
check(len(hits) == 1 and hits[0].severity == L.WARN, "…and a WARN without --strict")

tone = [enum("tone", ["default", "brand", "muted"])]
hits = codes([comp("tag", "props = props || {};\nreturn props.tone === 'brand' ? '<i b></i>' : '<i></i>';",
                   tone)], "R-PROP-USED", strict=True)
check(len(hits) == 1 and "'muted'" in hits[0].msg and "'brand'" not in hits[0].msg
      and hits[0].severity == L.WARN,
      "a non-state option never rendered stays a WARN, even under --strict")

WHITELIST = ("var STATES = ['live', 'done'];\n"
             "var state = STATES.indexOf(props.state) >= 0 ? props.state : 'live';\n"
             "return '<div class=\"pc pc--' + state + '\"></div>';")
hits = codes([comp("pcard", WHITELIST, [enum("state", ["live", "done", "joined"])])], "R-PROP-USED")
check(len(hits) == 1 and "'joined'" in hits[0].msg,
      "a membership test is not a pass-through: a declared state the whitelist drops is caught "
      "(a programme card — 'joined' falls back to 'live')")
hits = codes([comp("pcard", "return '<div></div>';", [enum("cta", ["secondary", "primary"])])],
             "R-PROP-USED")
check(len(hits) == 1 and "never reads props.cta at all" in hits[0].msg,
      "a declared prop the body never reads says so")

# — the false-positive corpus —
CLEAN = ("props = props || {};\n"
         "var TONE = { muted: 'var(--text-muted)', brand: 'var(--brand)' };\n"
         "var err = props.state === 'error';\n"
         "return '<span class=\"b b--' + props.variant + '\" style=\"color:' + (TONE[props.tone] || 'inherit')"
         " + '\">' + (err ? '!' : '') + '</span>';")
clean_props = [enum("state", ["default", "error"]), enum("tone", ["default", "muted", "brand"]),
               enum("variant", ["solid", "ghost", "link"])]
cf = [f for f in findings([comp("badge", CLEAN, clean_props)], strict=True)
      if f.code in ("R-PROP-USED", "R-PROP-DECLARED")]
check(cf == [], "a clean body raises neither rule — default fall-through, a branch literal, a lookup "
                "KEY and a class pass-through all count as rendered (%s)" % [f.msg[:60] for f in cf])
check(codes([comp("chart", "props = props || {};\nreturn props.dots ? '<i dots></i>' : '<i></i>';",
                  [enum("dots", ["none", "true"])])], "R-PROP-USED") == [],
      "FP: 'true' on a prop the body tests for truthiness (a line chart)")
check(codes([comp("row", "props = props || {};\nreturn pbUse('dot', { fund: props.fund || 'a' });",
                  [enum("fund", ["a", "b", "c"])], level="molecule")], "R-PROP-USED") == [],
      "FP: a value handed to a child unbranched is the child's to render (a fund 'about' block)")
check(codes([comp("row", "return fundOf(props);\nfunction fundOf(p) { return '<i>' + p.fund + '</i>'; }",
                  [enum("fund", ["a", "b"])])], "R-PROP-USED") == [],
      "FP: props handed WHOLE to a call — the scan cannot see where its values render, so it is silent")
check(codes([comp("chip", "/* 'loading' used to spin here */\nreturn '<i>' + (props.state === 'x' ? 1 : 2) + '</i>';",
                  [enum("state", ["default", "x", "loading"])])], "R-PROP-USED")[0:1] != [],
      "a value named only in a COMMENT is not rendered (comments are stripped first)")

# ── the golden stays clean ────────────────────────────────────────────────────────────────
print("golden — both rules hold on the fixture every other test trusts")
r = subprocess.run([sys.executable, LINT, "--strict", GOLDEN], capture_output=True, text=True)
check(r.returncode == 0 and "R-PROP" not in r.stdout,
      "lint_registry.py --strict on the golden is clean (rc=%d)" % r.returncode)

# ── R-EXEC (--exec) ───────────────────────────────────────────────────────────────────────
print("R-EXEC — run every body, in a folder named `proj [x]`")
BODIES = {
    "ok-atom": "props = props || {};\nreturn '<i>' + pbEscape(props.label || 'ok') + '</i>';",
    "empty-atom": "return '';",
    "throw-atom": "return props.rows.map(function (r) { return r; }).join('');",
    "a2-atom": "/* A header comment, then the declaration form. */\n"
               "function renderCmpA2Atom(props) {\n  return '<i>a2</i>';\n}\n",
    "state-atom": "props = props || {};\n"
                  "if (props.state === 'error') return props.missing.message;\n"
                  "return '<i>' + pbEscape(props.state || 'default') + '</i>';",
    "host-mol": "return '<div>' + pbUse('ok-atom', { label: 'x' }) + pbUse('throw-atom', {}) + '</div>';",
}


def build(project):
    comps = []
    for cid, src in BODIES.items():
        p = os.path.join(project, "render", "components", cid + ".js")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        c = comp(cid, "", level="molecule" if cid.endswith("-mol") else "atom")
        del c["render"]
        c["renderSrc"] = "render/components/%s.js" % cid
        if cid == "state-atom":
            c["properties"] = [enum("state", ["default", "error"])]
        if cid == "host-mol":
            c["anatomy"] = {"parts": [{"n": 1, "name": "A", "orgId": "ok-atom"},
                                      {"n": 2, "name": "B", "orgId": "throw-atom"}]}
        comps.append(c)
    reg = {"meta": {"name": "t", "schemaVersion": 12}, "tokens": {}, "screens": [], "components": comps}
    path = os.path.join(project, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
    return path


def exec_lines(out, cid):
    return [l for l in out.splitlines() if "[R-EXEC]" in l and "id='%s'" % cid in l]


node_ran = False
with tempfile.TemporaryDirectory() as tmp:
    project = os.path.join(tmp, "proj [x]")
    path = build(project)

    # PATH= stands in for a machine without node: one line, the static verdict alone.
    r0 = subprocess.run([sys.executable, LINT, "--exec", path], capture_output=True, text=True,
                        env=dict(os.environ, PATH=""))
    static = subprocess.run([sys.executable, LINT, path], capture_output=True, text=True)
    check("node not found" in r0.stdout and "not a pass" in r0.stdout and "[R-EXEC]" not in r0.stdout,
          "no node on PATH → one line saying no body was executed, and no R-EXEC finding")
    check(r0.returncode == static.returncode,
          "…and the exit code is the static verdict's (%d == %d) — skipped is not failed"
          % (r0.returncode, static.returncode))

    if shutil.which("node"):
        node_ran = True
        r = subprocess.run([sys.executable, LINT, "--exec", path], capture_output=True, text=True)
        out = r.stdout
        check(r.returncode == 2, "--exec exits 2 when a body fails (rc=%d)" % r.returncode)
        check(exec_lines(out, "ok-atom") == [], "a body that returns markup passes")
        e = exec_lines(out, "empty-atom")
        check(len(e) == 1 and "returned an empty string" in e[0], "a body that returns '' fails")
        e = exec_lines(out, "throw-atom")
        check(len(e) == 1 and "{} threw" in e[0], "a body that throws on {} fails, naming the run")
        e = exec_lines(out, "a2-atom")
        check(len(e) == 1 and "returned undefined" in e[0] and "declared and never called" in e[0],
              "a header comment above `function renderX(){}` is caught and explained")
        e = exec_lines(out, "state-atom")
        check(len(e) == 1 and "state=error threw" in e[0] and "{} threw" not in e[0],
              "each `state` option runs on its own — only state=error is reported")
        check(exec_lines(out, "host-mol") == [],
              "pbUse is stubbed: a broken CHILD fails the child, not every parent composing it")
        check("proj [x]" not in out or "not found" not in out,
              "the bracketed project path resolves every body (no 'not found')")
        g = subprocess.run([sys.executable, LINT, "--strict", "--exec", GOLDEN], capture_output=True, text=True)
        check(g.returncode == 0 and "R-EXEC" not in g.stdout,
              "the golden passes --strict --exec (rc=%d)" % g.returncode)
    else:
        print("  ○ node not found — the R-EXEC execution checks did NOT run (blocked, not passed)")

print()
if _fails:
    print("FAIL — %d check(s):" % len(_fails))
    for f in _fails:
        print("   - " + f)
    sys.exit(1)
if not node_ran:
    print("SKIP — the static half passed; the node half did not run")
    sys.exit(2)
print("PASS — R-PROP-DECLARED, R-PROP-USED and R-EXEC behave, false-positive corpus included")
