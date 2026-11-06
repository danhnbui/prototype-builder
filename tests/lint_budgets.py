#!/usr/bin/env python3
"""tests/lint_budgets.py — the size-and-readability rules in lint_registry.py.

Three rules catch the structural causes of an oversized project, and --report shows where the bytes go:

  R-LOGICSRC      a logicSrc that names a file that is not there            ERROR · always
  R-INLINE-DATA   a data: URI / base64 run over 8 KB in a body, sheet or
                  runtime file                                              WARN → ERROR under --strict
  R-RETIRED-DATA  a non-empty meta.others (migration 0012 moves it)        WARN → ERROR under --strict
                  (meta.tradeoffs keeps the advisory R-RETIRED)

and the "Where the size goes" block: registry bytes and ≈ tokens (bytes / 4), the top 5 slices, memory/*.md
above memory_file_kb (default 64, overridable in memory/doctor.json), the decisions logs, and whether
prototype.html / design-system.html are tracked by git.

Each rule gets a positive and a negative case, default and --strict. Hermetic: temp projects, a temp git
repo for the tracked-HTML check (skipped, said so, when git is absent). Exit: 0 pass, 1 fail.
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
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import lint_registry as L  # noqa: E402

_fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        _fails.append(msg)


def run(*args):
    return subprocess.run([sys.executable, LINT, *args], capture_output=True, text=True)


def put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


_DANGER = {"danger": {"$value": "#d92d20", "$type": "color"}}      # the runtime-required token: keeps the base registry warning-free


def fn(ident):
    return "renderCmp" + "".join(w.title() for w in ident.split("-"))


def body(ident, inner="''"):
    return "function %s(props) {\n  props = props || {};\n  return '<div>' + %s + '</div>';\n}\n" % (fn(ident), inner)


def project(d, comps=None, meta=None, bodies=None, files=None, runtime=None, screens=None):
    """A registry in dir d. comps: list of dicts (id + extras); each gets its body (bodies[id] or a plain one)."""
    comp_list = []
    for c in comps or []:
        c = dict(c)
        ident = c["id"]
        c.setdefault("name", ident.title())
        c.setdefault("level", "atom")
        c.setdefault("scope", "local")
        c.setdefault("renderFn", fn(ident))
        c.setdefault("renderSrc", f"render/components/{ident}.js")
        put(os.path.join(d, c["renderSrc"]), (bodies or {}).get(ident, body(ident)))
        comp_list.append(c)
    for rel, text in (files or {}).items():
        put(os.path.join(d, rel), text)
    reg = {"meta": dict({"name": "t"}, **(meta or {})), "tokens": dict(_DANGER),
           "screens": screens or [], "components": comp_list}
    if runtime is not None:
        reg["runtime"] = runtime
    path = os.path.join(d, "registry.json")
    put(path, json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    return path


def codes(findings, code):
    return [f for f in findings if f.code == code]


def lint(reg, strict, base):
    return L.check(reg, strict=strict, base_dir=base)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


KB = 1024
B64_9K = "A" * (9 * KB)
B64_7K = "A" * (7 * KB)

# ── R-LOGICSRC ───────────────────────────────────────────────────────────────────────
print("R-LOGICSRC — a logicSrc that points nowhere")
with tempfile.TemporaryDirectory() as d:
    p = project(d, [{"id": "ghost", "logicSrc": "logic/components/ghost.json"},
                    {"id": "real", "logicSrc": "logic/components/real.json"},
                    {"id": "plain"}],
                screens=[{"id": "home", "name": "Home", "renderFn": "renderHome", "logicSrc": "logic/screens/home.json"}],
                files={"logic/components/real.json": "{}"})
    # screens need a body to avoid unrelated findings; irrelevant to this rule, we read only R-LOGICSRC
    reg = load(p)
    for strict in (False, True):
        tag = "--strict" if strict else "default"
        got = codes(lint(reg, strict, d), "R-LOGICSRC")
        check(sorted(f.where for f in got) == ["components[id='ghost']", "screens[id='home']"] and
              all(f.severity == "ERROR" for f in got),
              "%s: the two dangling pointers fire, as ERROR in both modes" % tag)
        check(all("logicSrc file not found:" in f.msg for f in got) and
              any("logic/components/ghost.json" in f.msg for f in got),
              "%s: the message says 'logicSrc file not found: <path>', like R-SPECSRC" % tag)
        check(not any("real" in f.where or "plain" in f.where for f in got),
              "%s: a logicSrc that exists, and a component without one, are silent" % tag)
    check(codes(L.check(reg, base_dir=None), "R-LOGICSRC") == [],
          "no base_dir (an in-memory registry): nothing to resolve against, nothing fires")
    r = run(p)
    check(r.returncode == 2 and "ERROR [R-LOGICSRC]" in r.stdout, "CLI default: exit 2 (rc=%d)" % r.returncode)
with tempfile.TemporaryDirectory() as d:
    p = project(d, [{"id": "real", "logicSrc": "logic/components/real.json"}], files={"logic/components/real.json": "{}"})
    for flags in ((), ("--strict",)):
        r = run(*flags, p)
        check(r.returncode == 0 and "R-LOGICSRC" not in r.stdout,
              "all logicSrc files present %s: exit 0, no finding" % (" ".join(flags) or "(default)"))

# ── R-INLINE-DATA ────────────────────────────────────────────────────────────────────
print("R-INLINE-DATA — more than 8 KB of data inline")
uri9 = "data:image/png;base64," + B64_9K
uri7 = "data:image/png;base64," + B64_7K
with tempfile.TemporaryDirectory() as d:
    inner = "'<img src=\"" + uri9 + "\">'"
    p = project(d, [{"id": "logo"}], bodies={"logo": body("logo", inner)})
    reg = load(p)
    for strict in (False, True):
        tag = "--strict" if strict else "default"
        got = codes(lint(reg, strict, d), "R-INLINE-DATA")
        check(len(got) == 1 and got[0].severity == ("ERROR" if strict else "WARN"),
              "%s: one data: URI over 8 KB in a renderSrc body → %s" % (tag, "ERROR" if strict else "WARN"))
        if got:
            f = got[0]
            check(f.where == "render/components/logo.js:3" and "9 KB" in f.msg and "asset file" in f.msg,
                  "%s: names the file and line (%s), the size and the fix (asset file)" % (tag, f.where))
    r = run(p)
    check(r.returncode == 1 and "WARN [R-INLINE-DATA]" in r.stdout, "CLI default: exit 1 (rc=%d)" % r.returncode)
    r = run("--strict", p)
    check(r.returncode == 2 and "ERROR [R-INLINE-DATA]" in r.stdout, "CLI --strict: exit 2 (rc=%d)" % r.returncode)

with tempfile.TemporaryDirectory() as d:
    p = project(d, [{"id": "logo"}], bodies={"logo": body("logo", "'<img src=\"" + uri7 + "\">'")})
    check(codes(lint(load(p), True, d), "R-INLINE-DATA") == [],
          "negative: a 7 KB data: URI is under the limit — nothing fires, even under --strict")
    r = run("--strict", p)
    check(r.returncode == 0, "negative CLI --strict: exit 0 (rc=%d)" % r.returncode)

with tempfile.TemporaryDirectory() as d:
    sheet = ".c-pic { background: url(" + uri9 + "); }\n"
    p = project(d, [{"id": "pic", "styleSrc": "styles/pic.css"}], files={
        "styles/pic.css": sheet,
        "runtime/blob.js": "// a module\nwindow.PB_BLOB = '" + B64_9K + "';\n"},
        runtime=[{"id": "blob", "src": "runtime/blob.js"}])
    got = codes(lint(load(p), False, d), "R-INLINE-DATA")
    where = sorted(f.where for f in got)
    check(where == ["runtime/blob.js:2", "styles/pic.css:1"],
          "a styleSrc sheet and a runtime[] src file are scanned too (%s)" % where)
    check(any("base64-looking run" in f.msg for f in got) and any("data: URI" in f.msg for f in got),
          "…and the message tells a data: URI from a bare base64 run")

with tempfile.TemporaryDirectory() as d:
    inner = "'<img src=\"" + uri9 + "\">'"
    p = project(d, [{"id": "a", "renderSrc": "render/shared.js", "renderFn": "renderCmpShared"},
                    {"id": "b", "renderSrc": "render/shared.js", "renderFn": "renderCmpShared"}],
                bodies={"a": body("shared", inner), "b": body("shared", inner)})
    got = codes(lint(load(p), False, d), "R-INLINE-DATA")
    check(len(got) == 1, "one body shared by two items is reported once (got %d)" % len(got))

with tempfile.TemporaryDirectory() as d:
    text = ("function renderCmpPlain(props) {\n  var s = '" + "lorem ipsum dolor sit amet " * (400) + "';\n"
            "  return '<p>' + s + '</p>';\n}\n"
            "// " + "-" * (9 * KB) + "\n// data:image/png;base64,AAAA is only a mention\n")
    p = project(d, [{"id": "plain", "renderFn": "renderCmpPlain"}], bodies={"plain": text})
    check(codes(lint(load(p), True, d), "R-INLINE-DATA") == [],
          "negative: a long prose string, a long dashed rule and a short data: mention are not inline data")

# ── R-RETIRED-DATA ───────────────────────────────────────────────────────────────────
print("R-RETIRED-DATA — meta.others still holds data")


def retired_reg(**meta):
    return {"meta": dict({"name": "t"}, **meta), "tokens": dict(_DANGER), "screens": [], "components": []}


for strict in (False, True):
    tag = "--strict" if strict else "default"
    got = codes(L.check(retired_reg(others={"live": [1, 2]}), strict=strict), "R-RETIRED-DATA")
    check(len(got) == 1 and got[0].where == "meta.others" and got[0].severity == ("ERROR" if strict else "WARN"),
          "%s: non-empty meta.others → R-RETIRED-DATA, %s" % (tag, "ERROR" if strict else "WARN"))
    check(got and "/pb:update-version --apply" in got[0].msg and "0012" in got[0].msg and "memory/others.md" in got[0].msg,
          "%s: points at /pb:update-version --apply (migration 0012) and memory/others.md" % tag)
    check(codes(L.check(retired_reg(others={"live": 1}), strict=strict), "R-RETIRED") == [],
          "%s: meta.others is no longer reported under the advisory R-RETIRED code" % tag)
    for empty in (None, {}, [], ""):
        check(codes(L.check(retired_reg(others=empty), strict=strict), "R-RETIRED-DATA") == [],
              "%s: meta.others = %r is not data — nothing fires" % (tag, empty))
    tr = L.check(retired_reg(tradeoffs=[{"title": "t"}]), strict=strict)
    check(len(codes(tr, "R-RETIRED")) == 1 and codes(tr, "R-RETIRED")[0].severity == "WARN" and codes(tr, "R-RETIRED-DATA") == [],
          "%s: meta.tradeoffs stays the advisory R-RETIRED WARN" % tag)
with tempfile.TemporaryDirectory() as d:
    p = project(d, meta={"others": {"live": "data"}})
    r = run(p)
    check(r.returncode == 1 and "WARN [R-RETIRED-DATA]" in r.stdout and "advisory" not in r.stdout,
          "CLI default: exit 1, counted as a warning (rc=%d)" % r.returncode)
    r = run("--strict", p)
    check(r.returncode == 2 and "ERROR [R-RETIRED-DATA]" in r.stdout, "CLI --strict: exit 2 (rc=%d)" % r.returncode)
with tempfile.TemporaryDirectory() as d:
    p = project(d, meta={"tradeoffs": [{"title": "t"}]})
    r = run("--strict", p)
    check(r.returncode == 0, "meta.tradeoffs alone under --strict: still exit 0 (rc=%d)" % r.returncode)

# ── --report · Where the size goes ───────────────────────────────────────────────────
print("--report — Where the size goes")


def report(proj, *extra):
    r = subprocess.run([sys.executable, LINT, "--report", *extra, os.path.join(proj, "registry.json")],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def block(out):
    return out.split("── where the size goes", 1)[1].split("── resources", 1)[0]


def fix_first(out):
    tail = out.split("── fix first", 1)[1]
    return [ln.strip() for ln in tail.splitlines()[1:] if ln.strip()]


with tempfile.TemporaryDirectory() as d:
    p = project(d, [{"id": "a"}, {"id": "b"}])
    put(os.path.join(d, "memory", "big.md"), "x" * (70 * KB))
    put(os.path.join(d, "memory", "small.md"), "y" * (2 * KB))
    put(os.path.join(d, "memory", "decisions.md"), "z" * (10 * KB))
    put(os.path.join(d, "memory", "decisions-2026-01.md"), "z" * (3 * KB))
    put(os.path.join(d, "memory", "notes.txt"), "w" * (200 * KB))        # not .md: ignored
    rc, out, err = report(d)
    check(rc == 0 and "Traceback" not in err and "size unavailable" not in out, "exit 0, no crash (rc=%d)" % rc)
    check("── where the size goes" in out, "the block is printed")
    b = block(out)
    reg_bytes = os.path.getsize(p)
    check("registry.json" in b and f"{reg_bytes:,d}" in b and f"≈ {reg_bytes // 4:,d} tokens" in b,
          "registry.json bytes (%s) and ≈ tokens (bytes/4 = %s)" % (f"{reg_bytes:,d}", f"{reg_bytes // 4:,d}"))
    slice_rows = [ln for ln in b.split("top slices by bytes", 1)[1].splitlines()[1:] if ln.startswith("    ") and "bytes" in ln]
    check(1 <= len(slice_rows) <= 5 and slice_rows == sorted(
        slice_rows, key=lambda ln: -int(ln.split()[1].replace(",", ""))),
        "top slices: at most 5 rows, largest first (%d rows)" % len(slice_rows))
    check("big.md" in b and "small.md" not in b.split("memory/*.md", 1)[1].split("decisions", 1)[0],
          "memory/*.md: the 70 KB file is listed, the 2 KB one is not")
    check("notes.txt" not in b, "only *.md files are counted")
    check("memory/*.md" in b and "4 file(s)" in b and "85 KB" in b,
          "the memory/*.md total counts every .md file (4 files, 85 KB)")
    check("decisions.md" in b and "decisions-2026-01.md" in b, "decisions*.md files are listed with their sizes")
    check(any("big.md" in ln and "memory file" in ln for ln in fix_first(out)),
          "the oversized memory file is ranked in 'fix first'")

    # threshold override
    put(os.path.join(d, "memory", "doctor.json"), json.dumps({"memory_file_kb": 1}))
    rc, out, _ = report(d)
    check("small.md" in block(out) and "over 1 KB" in block(out), "doctor.json memory_file_kb=1 lists the 2 KB file too")
    put(os.path.join(d, "memory", "doctor.json"), json.dumps({"memory_file_kb": 500}))
    rc, out, _ = report(d)
    check("big.md" not in block(out) and not any("memory file" in ln for ln in fix_first(out)),
          "doctor.json memory_file_kb=500: nothing over, nothing ranked")
    put(os.path.join(d, "memory", "doctor.json"), json.dumps({"memory_file_kb": "lots"}))
    rc, out, err = report(d)
    check(rc == 0 and "Traceback" not in err and "big.md" in block(out),
          "a memory_file_kb that is not a number falls back to 64, no crash")

with tempfile.TemporaryDirectory() as d:
    project(d, [{"id": "a"}])
    rc, out, _ = report(d)
    check(rc == 0 and "(no file over 64 KB)" in block(out) and "0 file(s)" in block(out),
          "a project with no memory/ shows zero files and ranks nothing from the memory check")
    check(not any("memory file" in ln for ln in fix_first(out)), "…nothing ranked")

# default threshold is in the doc table
check(L._th({}, "memory_file_kb", 64) == 64.0, "default memory_file_kb is 64")

# ── generated HTML tracked by git ────────────────────────────────────────────────────
print("--report — generated HTML tracked by git")
GIT = shutil.which("git")
if GIT is None:
    print("  - git is not installed: the tracked-HTML sub-case is skipped")
else:
    genv = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(cwd, *args):
        return subprocess.run([GIT, *args], cwd=cwd, env=genv, capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as d:
        if git(d, "init", "-q").returncode != 0:
            print("  - git init failed here: the tracked-HTML sub-case is skipped")
        else:
            project(d, [{"id": "a"}])
            put(os.path.join(d, "prototype.html"), "<html>" + "p" * 2000 + "</html>")
            put(os.path.join(d, "design-system.html"), "<html>ds</html>")
            git(d, "add", "registry.json", "prototype.html")        # registry + prototype tracked, design-system not
            rc, out, err = report(d)
            b = block(out)
            check(rc == 0 and "Traceback" not in err, "exit 0 in a git work tree (rc=%d)" % rc)
            check("prototype.html" in b and "tracked" in b and
                  any(ln.strip().startswith("prototype.html") and "tracked" in ln and "not tracked" not in ln
                      for ln in b.splitlines()),
                  "prototype.html is shown as tracked")
            check(any(ln.strip().startswith("design-system.html") and "not tracked" in ln for ln in b.splitlines()),
                  "design-system.html is shown as not tracked")
            ff = [ln for ln in fix_first(out) if "tracked by git" in ln]
            check(len(ff) == 1 and "prototype.html" in ff[0] and "design-system.html" not in ff[0]
                  and ".gitignore" in ff[0] and "git rm --cached prototype.html" in ff[0],
                  "only the tracked one is ranked, with the fix (.gitignore + git rm --cached)")
            git(d, "add", "design-system.html")
            rc, out, _ = report(d)
            ff = [ln for ln in fix_first(out) if "tracked by git" in ln]
            check(len(ff) == 1 and "prototype.html" in ff[0] and "design-system.html" in ff[0]
                  and "git rm --cached prototype.html design-system.html" in ff[0],
                  "both tracked: one line names both")

    with tempfile.TemporaryDirectory() as d:
        if git(d, "init", "-q").returncode == 0:
            project(d, [{"id": "a"}])
            put(os.path.join(d, "prototype.html"), "<html></html>")
            put(os.path.join(d, ".gitignore"), "prototype.html\ndesign-system.html\n")
            git(d, "add", ".gitignore", "registry.json")
            rc, out, _ = report(d)
            check(rc == 0 and not [ln for ln in fix_first(out) if "tracked by git" in ln]
                  and "not tracked" in block(out),
                  "negative: ignored, untracked generated HTML is shown as not tracked and never ranked")

    with tempfile.TemporaryDirectory() as d:
        project(d, [{"id": "a"}])
        put(os.path.join(d, "prototype.html"), "<html></html>")
        env_before = dict(os.environ)
        rc, out, err = report(d)
        probably_outside = git(d, "rev-parse", "--is-inside-work-tree").returncode != 0
        if probably_outside:
            check(rc == 0 and "n/a" in block(out) and not [ln for ln in fix_first(out) if "tracked by git" in ln],
                  "negative: outside a git work tree the row says n/a and ranks nothing")
        else:
            print("  - the system temp dir is inside a git work tree here: the n/a sub-case is skipped")

# ── the golden stays clean ───────────────────────────────────────────────────────────
print("the golden copy")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
r = run("--strict", GOLDEN)
check(r.returncode == 0 and not any(c in r.stdout for c in ("R-LOGICSRC", "R-INLINE-DATA", "R-RETIRED-DATA")),
      "fixtures/golden passes --strict with none of the three new codes (rc=%d)" % r.returncode)

print()
if _fails:
    print("FAIL — %d lint_budgets check(s):" % len(_fails))
    for m in _fails:
        print("  - " + m)
    sys.exit(1)
print("PASS — R-LOGICSRC, R-INLINE-DATA, R-RETIRED-DATA and the size block behave")
