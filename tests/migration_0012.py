#!/usr/bin/env python3
"""
migration_0012.py — schema 13 → 14: the retired meta.others moves out to memory/others.md.

  1. A dict, a list and a string each land in memory/others.md (readable half + exact JSON), the
     field is emptied KEEPING ITS TYPE, and schemaVersion is stamped 14.
  2. An empty field (None / {} / [] / "" / absent) writes no file and still stamps 14.
  3. Idempotent: running up() twice appends one section, not two.
  4. up() then down() restores a deep-equal original — non-ASCII, nested values, backticks and a
     code fence inside a string included — and stamps 13.
  5. down() never overwrites a field someone filled since, and does nothing without a block.
  6. Non-empty data with no base_dir raises and leaves the registry untouched (never dropped).
  7. A second move APPENDS (the first section stays); down() restores the latest.
  8. 0012 is in the chain, the chain reaches CURRENT_SCHEMA, the template carries it.
  9. The runner: dry-run writes nothing; --apply moves the data and stamps 14; --rollback and
     --to 13 bring it back.

Usage:  python3 tests/migration_0012.py
Exit:   0 = all passed · 1 = a failure
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIG = os.path.join(ROOT, "pb", "migrations", "0012_others_out.py")
MANIFEST = os.path.join(ROOT, "pb", "migrations", "manifest.py")
RUNNER = os.path.join(ROOT, "pb", "migrations", "migrate_runner.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load(MIG, "m0012")
mf = _load(MANIFEST, "manifest")

DICT = {"Ghi chú": "Luồng tạo chu kỳ — xem lại", "count": 3, "nested": {"a": [1, 2, {"b": None}]},
        "fence": "before ```json\n{\"x\": 1}\n``` after", "tick": "a `code` span"}
LIST = ["first note", {"k": "v"}, 7, ["x", "y"]]
STRING = "Free text.\n\nWith a second paragraph and ```a fence``` inside."


def reg(others, v=13, key=True):
    meta = {"name": "t", "schemaVersion": v}
    if key:
        meta["others"] = copy.deepcopy(others)
    return {"meta": meta, "screens": []}


def others_md(d):
    p = os.path.join(d, "memory", "others.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def tmp():
    return tempfile.mkdtemp(prefix="pb-m0012-")


print("1 · up — dict, list and string move out, keep their type, stamp 14")
for label, value, empty in (("dict", DICT, {}), ("list", LIST, []), ("string", STRING, "")):
    d = tmp()
    out = m.up(reg(value), d)
    check(out["meta"]["others"] == empty and type(out["meta"]["others"]) is type(empty),
          f"{label}: field emptied to {empty!r}, field kept")
    check(out["meta"]["schemaVersion"] == 14, f"{label}: stamped 14")
    md = others_md(d)
    check(md is not None and "## meta.others (moved by migration 0012, " in md, f"{label}: section heading written")
    check(md is not None and "```json" in md and m._MARKER in md, f"{label}: marker + exact-JSON block written")
d = tmp()
m.up(reg(DICT), d)
md = others_md(d)
check("### Ghi chú\n\nLuồng tạo chu kỳ — xem lại" in md, "dict: one ### heading per key, strings as-is (non-ASCII intact)")
check("### nested\n\n```json" in md, "dict: a non-string value is a fenced json block")
d = tmp()
m.up(reg(LIST), d)
md = others_md(d)
check("### Item 1\n\nfirst note" in md and "### Item 2\n\n```json" in md, "list: numbered items, strings as-is, others fenced")
d = tmp()
m.up(reg(STRING), d)
check(STRING in others_md(d), "string: printed as it is")

print("2 · up — an empty field writes no file")
for label, r in (("None", reg(None)), ("{}", reg({})), ("[]", reg([])), ('""', reg("")), ("absent", reg(None, key=False))):
    d = tmp()
    before = copy.deepcopy(r)
    out = m.up(r, d)
    expect = copy.deepcopy(before)
    expect["meta"]["schemaVersion"] = 14
    check(out == expect and others_md(d) is None, f"{label}: only the version changes, no memory/others.md")
check(m.up(reg(None, key=False), None)["meta"]["schemaVersion"] == 14, "empty field + base_dir None is fine")

print("3 · idempotent")
d = tmp()
m.up(reg(DICT), d)
once = others_md(d)
m.up(reg(DICT), d)
check(others_md(d) == once, "the same value again appends nothing")
check(once.count(m._MARKER) == 1, "exactly one section after two runs")

print("4 · up then down restores a deep-equal original")
for label, value in (("dict", DICT), ("list", LIST), ("string", STRING), ("scalar", 42), ("bool", True)):
    d = tmp()
    orig = reg(value)
    mid = m.up(copy.deepcopy(orig), d)
    back = m.down(mid, d)
    check(back == orig, f"{label}: round-trips to the original (incl. schemaVersion 13)")
    check(back["meta"]["schemaVersion"] == 13, f"{label}: down stamps 13")
big = {"k%d" % i: {"txt": "ünïcode ✓ %d" % i, "n": [i, None, True]} for i in range(200)}
d = tmp()
check(m.down(m.up(reg(big), d), d) == reg(big), "a large nested object round-trips")

print("5 · down is careful")
d = tmp()
m.up(reg(DICT), d)
filled = reg({"hand": "written since"}, v=14)
check(m.down(filled, d)["meta"]["others"] == {"hand": "written since"}, "never overwrites a field filled since")
d2 = tmp()
out = m.down(reg({}, v=14), d2)
check(out["meta"]["others"] == {} and out["meta"]["schemaVersion"] == 13, "no memory/others.md -> field left, 13 stamped")
check(m.down(reg({}, v=14), None)["meta"]["schemaVersion"] == 13, "base_dir None -> no crash, 13 stamped")
d3 = tmp()
os.makedirs(os.path.join(d3, "memory"))
open(os.path.join(d3, "memory", "others.md"), "w").write("# Others\n\nhand-written, no 0012 block\n")
check(m.down(reg({}, v=14), d3)["meta"]["others"] == {}, "a file without a 0012 block restores nothing")

print("6 · non-empty data with no base_dir never drops")
r = reg(DICT)
before = copy.deepcopy(r)
try:
    m.up(r, None)
    raised = False
except ValueError as e:
    raised = "memory/others.md" in str(e)
check(raised, "raises a ValueError naming memory/others.md")
check(r == before, "the registry passed in is untouched")

print("7 · a second move appends; down restores the latest")
d = tmp()
m.up(reg(DICT), d)
other = {"second": "value"}
m.up(reg(other), d)
md = others_md(d)
check(md.count(m._MARKER) == 2 and "Luồng tạo chu kỳ" in md, "both sections kept in the file")
check(m.down(reg({}, v=14), d)["meta"]["others"] == other, "down restores the most recent block")
existing = tmp()
os.makedirs(os.path.join(existing, "memory"))
open(os.path.join(existing, "memory", "others.md"), "w", encoding="utf-8").write("# Mine\n\nhand notes, no trailing newline")
m.up(reg(DICT), existing)
md = others_md(existing)
check(md.startswith("# Mine\n\nhand notes, no trailing newline") and md.count("## meta.others") == 1,
      "an existing file is appended to, its text kept")

print("8 · the chain")
check(mf.CURRENT_SCHEMA >= 14, f"CURRENT_SCHEMA is at least 14, 0012's target (got {mf.CURRENT_SCHEMA})")
check((13, 14, "0012_others_out") in mf._REGISTRY, "0012 registered in the chain")
check(max(t for _f, t, _s in mf._REGISTRY) == mf.CURRENT_SCHEMA, "the chain reaches CURRENT_SCHEMA")
check(m.FROM == 13 and m.TO == 14 and isinstance(m.describe(), str) and "\n" not in m.describe(), "FROM/TO and a one-line describe()")
tpl = json.load(open(TEMPLATE, encoding="utf-8"))
check(tpl["meta"]["schemaVersion"] == mf.CURRENT_SCHEMA, "the template is stamped CURRENT_SCHEMA")

print("9 · the runner")
proj = tmp()
rp = os.path.join(proj, "registry.json")
orig = {"meta": {"name": "t", "schemaVersion": 13, "others": DICT}, "tokens": {}, "components": [], "screens": []}
json.dump(orig, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def runner(*a):
    return subprocess.run([sys.executable, RUNNER, rp] + list(a), capture_output=True, text=True, cwd=proj)


before = open(rp, encoding="utf-8").read()
r = runner()
check(r.returncode == 0 and open(rp, encoding="utf-8").read() == before and others_md(proj) is None,
      "dry-run writes nothing (no registry change, no memory/others.md)")
r = runner("--apply")
res = json.load(open(rp, encoding="utf-8"))
check(r.returncode == 0 and res["meta"]["schemaVersion"] == mf.CURRENT_SCHEMA and res["meta"]["others"] == {},
      f"--apply: stamped and emptied (rc={r.returncode})")
check(others_md(proj) is not None and "Luồng tạo chu kỳ" in others_md(proj), "--apply: memory/others.md written")
r = runner("--rollback")
res = json.load(open(rp, encoding="utf-8"))
check(r.returncode == 0 and res["meta"]["others"] == DICT and res["meta"]["schemaVersion"] == 13,
      f"--rollback: the registry is back, others restored (rc={r.returncode})")
r = runner("--apply")
r = runner("--apply", "--to", "13")
res = json.load(open(rp, encoding="utf-8"))
check(r.returncode == 0 and res["meta"]["schemaVersion"] == 13 and res["meta"]["others"] == DICT,
      f"--to 13: down() refills meta.others from memory/others.md (rc={r.returncode})")

print("10 · live data: a file that reads meta.others keeps the field")
READ_BODY = ("function renderCmpMapPanel(props) {\n"
             "  var slice = ((PB_REGISTRY.meta || {}).others || {}).dataSlice || { items: [] };\n"
             "  return '<div>' + slice.items.length + '</div>';\n}\n")
LIVE = {"dataSlice": {"items": [1, 2, 3]}}
for label, rel, text, rt in (
        ("render body", "render/components/map-panel.js", READ_BODY, None),
        ("runtime module (registry.runtime[] src)", "lib/data.js", "var d = PB_REGISTRY.meta[\"others\"];\n",
         [{"id": "data", "src": "lib/data.js"}])):
    d = tmp()
    os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
    open(os.path.join(d, rel), "w", encoding="utf-8").write(text)
    r0 = reg(LIVE)
    if rt:
        r0["runtime"] = rt
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = m.up(copy.deepcopy(r0), d)
    check(out["meta"]["others"] == LIVE and out["meta"]["schemaVersion"] == 14,
          f"{label}: meta.others left exactly as it was, schema stamped 14")
    check(others_md(d) is None, f"{label}: no memory/others.md written")
    msg = buf.getvalue()
    check(rel in msg and "meta.others kept" in msg and "runtime/ module" in msg and msg.count("\n") == 1,
          f"{label}: one line naming {rel} and the fix")

d = tmp()
os.makedirs(os.path.join(d, "render"))
for i in range(5):
    open(os.path.join(d, "render", "r%d.js" % i), "w").write("var o = reg.meta.others;\n")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    m.up(reg(LIVE), d)
check("render/r0.js, render/r1.js, render/r2.js +2 more" in buf.getvalue(), "five readers: three named, then '+2 more'")

d = tmp()
os.makedirs(os.path.join(d, "render"))
open(os.path.join(d, "render", "x.js"), "w").write("// a mention of others, and 'others' alone, is not a read\nvar o = others + 1;\n")
out = m.up(reg(LIVE), d)
check(out["meta"]["others"] == {} and others_md(d) is not None, "no reader: moved to memory/others.md as before")
try:
    m.up(reg(LIVE), None)
    raised = False
except ValueError:
    raised = True
check(raised, "base_dir None with a reader-free but non-empty field still raises")

print("10b · the runner, and how the move is finished")
proj = tmp()
os.makedirs(os.path.join(proj, "render", "components"))
rp = os.path.join(proj, "registry.json")
body_path = os.path.join(proj, "render", "components", "map-panel.js")
open(body_path, "w", encoding="utf-8").write(READ_BODY)
json.dump({"meta": {"name": "t", "schemaVersion": 13, "others": LIVE}, "tokens": {}, "components": [], "screens": []},
          open(rp, "w", encoding="utf-8"), indent=2)
r = subprocess.run([sys.executable, RUNNER, rp, "--apply"], capture_output=True, text=True, cwd=proj)
res = json.load(open(rp, encoding="utf-8"))
check(r.returncode == 0 and res["meta"]["others"] == LIVE and res["meta"]["schemaVersion"] == mf.CURRENT_SCHEMA,
      f"--apply: field kept, schema stamped (rc={r.returncode})")
check("meta.others kept in registry.json — read by render/components/map-panel.js" in r.stdout,
      "--apply prints the guarded line naming the reader")
r = subprocess.run([sys.executable, RUNNER, rp, "--apply"], capture_output=True, text=True, cwd=proj)
check("Already on schema" in r.stdout and json.load(open(rp, encoding="utf-8"))["meta"]["others"] == LIVE,
      "a plain re-run at the current schema does nothing (the line tells the user why)")
open(body_path, "w", encoding="utf-8").write(READ_BODY.replace("((PB_REGISTRY.meta || {}).others || {}).dataSlice", "window.mapData"))
subprocess.run([sys.executable, RUNNER, rp, "--apply", "--to", "13"], capture_output=True, text=True, cwd=proj)
r = subprocess.run([sys.executable, RUNNER, rp, "--apply"], capture_output=True, text=True, cwd=proj)
res = json.load(open(rp, encoding="utf-8"))
check(res["meta"]["others"] == {} and res["meta"]["schemaVersion"] == mf.CURRENT_SCHEMA
      and "Luồng" not in (others_md(proj) or "") and '"dataSlice"' in (others_md(proj) or ""),
      "after the reader is gone: --apply --to 13 then --apply moves the data to memory/others.md (rc=%d)" % r.returncode)

print()
if fails:
    print(f"✗ {len(fails)} failure(s)")
    sys.exit(1)
print("✓ migration 0012 — all checks passed")
