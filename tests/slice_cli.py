#!/usr/bin/env python3
"""
slice_cli.py — guards pb/tools/slice.py: read/write ONE registry slice by id without
dragging the whole file into context (token lever #1 at scale).

  1. get  — components/screens by id, tokens/meta by dotted key; missing id/key exits non-zero.
  2. list — enumerates ids (components/screens), leaf paths (tokens), keys (meta).
  3. set  — an empty patch is byte-identical (idempotent, canonical format); a real patch
            merges into only the targeted entry and leaves every other slice untouched.
  4. writes are atomic and serialised (round 3): `set` replaces the file through a temp file in the
     same directory (a new inode, mode kept, a symlinked registry replaced at its target, no temp
     file left, even when it fails), and takes the advisory lock `<registry>.lock` around its whole
     read-modify-write — N parallel `set`s lose no update, a second writer past the timeout is
     refused with a message naming the holder and the file is untouched, and a `set` that exits on
     a bad patch leaves no lock behind.

Fixture-driven off registry.demo.json (no MCP / project needed).

Usage:  python3 tests/slice_cli.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLICE = os.path.join(ROOT, "pb", "tools", "slice.py")
DEMO = os.path.join(ROOT, "registry.demo.json")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def run(*args, stdin=None):
    return subprocess.run(
        [sys.executable, SLICE, *args],
        input=stdin, capture_output=True, text=True,
    )


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    shutil.copy2(DEMO, reg)
    R = ["--registry", reg]

    print("get — slice extraction")
    r = run("get", "components", "button", *R)
    check(r.returncode == 0 and json.loads(r.stdout).get("id") == "button", "get components button → the button entry")
    r = run("get", "meta", "name", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == json.load(open(DEMO))["meta"]["name"], "get meta name → the meta.name value")
    r = run("get", "tokens", "brand", *R)
    check(r.returncode == 0 and json.loads(r.stdout).get("$value"), "get tokens brand → the DTCG token object")
    check(run("get", "components", "does-not-exist", *R).returncode != 0, "get on a missing id exits non-zero")
    check(run("get", "meta", "nope", *R).returncode != 0, "get on a missing dotted key exits non-zero")

    print("get — --no-prose projection (D-17)")
    full_button = json.loads(run("get", "components", "button", *R).stdout)
    r = run("get", "components", "button", *R, "--no-prose")
    noprose_button = json.loads(r.stdout)
    check(r.returncode == 0, "--no-prose on a component returns 0")
    check(
        "anatomy" not in noprose_button and "spec" not in noprose_button and "uiLogic" not in noprose_button,
        "--no-prose drops anatomy/spec/uiLogic from a component",
    )
    check(
        set(noprose_button) == set(full_button) - {"anatomy", "spec", "uiLogic"},
        "--no-prose on a component keeps every non-prose key",
    )
    check(noprose_button.get("id") == "button", "--no-prose keeps ordinary field values intact")

    full_login = json.loads(run("get", "screens", "login", *R).stdout)
    r = run("get", "screens", "login", *R, "--no-prose")
    noprose_login = json.loads(r.stdout)
    check(r.returncode == 0, "--no-prose on a screen returns 0")
    check("logicNotes" not in noprose_login, "--no-prose drops logicNotes from a screen")
    check(
        set(noprose_login) == set(full_login) - {"logicNotes"},
        "--no-prose on a screen keeps every non-prose key",
    )

    print("get — --fields projection (D-17)")
    r = run("get", "components", "button", *R, "--fields", "level,id,name")
    fields_button = json.loads(r.stdout)
    check(r.returncode == 0, "--fields on a component returns 0")
    check(list(fields_button.keys()) == ["level", "id", "name"], "--fields emits exactly the named keys, in the caller's order")
    check(fields_button == {"level": "atom", "id": "button", "name": "Button"}, "--fields values match the source entry")

    print("get — --fields + --no-prose combined (D-17)")
    r = run("get", "components", "button", *R, "--fields", "id,anatomy,level", "--no-prose")
    combined = json.loads(r.stdout)
    check(r.returncode == 0, "--fields + --no-prose together return 0")
    check(list(combined.keys()) == ["id", "level"], "--no-prose drops a prose key that --fields selected, keeping the rest in order")
    check("anatomy" not in combined, "the selected prose key (anatomy) does not survive --no-prose")

    print("get — --fields with an unknown key (D-17: erroring, not a silent partial/empty result)")
    r = run("get", "components", "button", *R, "--fields", "id,does-not-exist")
    check(r.returncode != 0, "an unknown --fields name exits non-zero")
    check(r.stdout.strip() == "", "an unknown --fields name prints nothing to stdout (no silent partial object)")

    print("get — projection never writes")
    before_bytes = open(reg, "rb").read()
    run("get", "components", "button", *R, "--no-prose")
    run("get", "screens", "login", *R, "--fields", "id,name")
    run("get", "components", "button", *R, "--fields", "id,anatomy", "--no-prose")
    run("get", "components", "button", *R, "--fields", "nope")  # even an error path must not write
    after_bytes = open(reg, "rb").read()
    check(after_bytes == before_bytes, "get — plain or projected — never mutates the registry file")

    print("list — enumeration")
    r = run("list", "components", *R)
    check(r.returncode == 0 and "button" in r.stdout and "[atom]" in r.stdout, "list components shows ids + level")
    r = run("list", "tokens", *R)
    check(r.returncode == 0 and "brand" in r.stdout, "list tokens shows leaf token names")

    print("set — empty patch is byte-identical")
    before = open(reg, encoding="utf-8").read()
    r = run("set", "components", "button", *R, stdin="")
    after = open(reg, encoding="utf-8").read()
    check(r.returncode == 0 and after == before, "empty-patch set leaves the file byte-identical")

    print("set — real patch touches only the target")
    orig = json.load(open(reg))
    r = run("set", "components", "text-input", *R, stdin='{"name":"TextField"}')
    check(r.returncode == 0, "set returns 0 on a valid patch")
    now = json.load(open(reg))
    ti = next(c for c in now["components"] if c["id"] == "text-input")
    check(ti["name"] == "TextField", "the targeted entry got the patch")
    # every other slice is byte-for-byte the pre-patch value
    def without_ti(reg_dict):
        clone = json.loads(json.dumps(reg_dict))
        clone["components"] = [c for c in clone["components"] if c["id"] != "text-input"]
        return clone
    check(without_ti(orig) == without_ti(now), "no other component/screen/meta/token slice changed")

    print("set — dotted meta write")
    r = run("set", "meta", "name", *R, stdin='"Renamed"')
    check(r.returncode == 0 and json.load(open(reg))["meta"]["name"] == "Renamed", "set meta name replaces the leaf")

    print("set — a non-object patch on a list kind is rejected")
    check(run("set", "components", "button", *R, stdin='"oops"').returncode != 0, "scalar patch on components exits non-zero")

    # D-29: /pb:build's auto-sync reads flow/erd narrowly. `get flow mermaid` must return the
    # diagram WITHOUT stories[] riding along — that projection is the whole point.
    print("flow / erd — the auto-sync read path")
    r = run("get", "flow", "mermaid", *R)
    check(r.returncode == 0 and "flowchart" in r.stdout, "get flow mermaid returns the diagram")
    check("scenarios" not in r.stdout, "get flow mermaid does NOT drag stories[].scenarios[] along")
    check(run("get", "erd", "table", *R).returncode == 0, "get erd table returns the rows")
    check(run("get", "flow", "nope", *R).returncode != 0, "an unknown flow key exits non-zero")

    # Regression guard: list's fallback branch used to hardcode the tokens tree, so every
    # dict kind but `meta` silently listed token names.
    print("list — each dict kind lists its own keys, not tokens'")
    out = run("list", "flow", *R).stdout.split()
    check("mermaid" in out and "stories" in out, "list flow shows flow's own keys")
    check("brand" not in out, "list flow does not fall through to the tokens tree")
    check("table" in run("list", "erd", *R).stdout.split(), "list erd shows erd's own keys")
    check("brand" in run("list", "tokens", *R).stdout.split(), "list tokens still walks DTCG leaves")

    # The Content tab's slice: a glossary + a wording deck, read the same narrow way. Reading
    # `content terms` must not drag the (much longer) wording deck along.
    print("content — the glossary / wording-deck slice")
    r = run("get", "content", "terms", *R)
    terms = json.loads(r.stdout)
    check(r.returncode == 0 and isinstance(terms, list) and terms, "get content terms returns the glossary")
    check("action.sign-in" not in r.stdout, "get content terms does NOT drag strings[] along")
    check(json.loads(run("get", "content", "strings", *R).stdout)[0]["key"], "get content strings returns the wording deck")
    out = run("list", "content", *R).stdout.split()
    check("terms" in out and "strings" in out and "brand" not in out, "list content shows content's own keys")
    check(run("get", "content", "nope", *R).returncode != 0, "an unknown content key exits non-zero")

    print("set — dotted flow write leaves siblings intact")
    before_stories = json.load(open(reg))["flow"]["stories"]
    r = run("set", "flow", "mermaid", *R, stdin='"flowchart LR\\n  A --> B"')
    now = json.load(open(reg))["flow"]
    check(r.returncode == 0 and now["mermaid"] == "flowchart LR\n  A --> B", "set flow mermaid replaces the leaf")
    check(now["stories"] == before_stories, "set flow mermaid leaves stories[] untouched")


    print("set — atomic write: a new inode, the mode kept, no temp file, nothing half-written")
    spec = importlib.util.spec_from_file_location("pb_slice_under_test", SLICE)
    sl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sl)
    os.chmod(reg, 0o640)
    ino = os.stat(reg).st_ino
    r = run("set", "meta", "name", *R, stdin='"Atomic"')
    check(r.returncode == 0 and os.stat(reg).st_ino != ino, "set replaced the file (a new inode) rather than rewriting it in place")
    check(stat.S_IMODE(os.stat(reg).st_mode) == 0o640, "the file's mode survives the replace")
    check([f for f in os.listdir(d) if f.endswith(".tmp")] == [], "no temp file is left behind")
    link = os.path.join(d, "via-link.json")
    os.symlink(reg, link)
    r = run("set", "meta", "name", "--registry", link, stdin='"Through the link"')
    check(r.returncode == 0 and os.path.islink(link) and json.load(open(reg))["meta"]["name"] == "Through the link",
          "a symlinked registry is replaced at its target; the link stays a link")
    os.unlink(link)
    before = open(reg, "rb").read()
    try:
        sl._write(reg, {"meta": {"name": "a\ud800b"}})            # a lone surrogate cannot be written as UTF-8
        check(False, "a value that cannot be encoded raises")
    except UnicodeEncodeError:
        check(open(reg, "rb").read() == before and [f for f in os.listdir(d) if f.endswith(".tmp")] == [],
              "a write that fails leaves the registry byte-identical and no temp file")

    print("set — the advisory lock")
    env = dict(os.environ, PB_LOCK_TIMEOUT="0.5")
    def run_env(*args, stdin=None):
        return subprocess.run([sys.executable, SLICE, *args], input=stdin, capture_output=True, text=True, env=env)
    before = open(reg, "rb").read()
    with sl.registry_lock(reg, "a test holding the lock"):
        t0 = time.time()
        r = run_env("set", "meta", "name", *R, stdin='"Blocked"')
        waited = time.time() - t0
        check(r.returncode != 0 and "being written" in r.stderr and "a test holding the lock" in r.stderr,
              "a second writer is refused, and the message names the holder (%r)" % r.stderr.strip()[:140])
        check("Traceback" not in r.stderr, "…as a message, not a traceback")
        check(0.4 < waited < 5, "…after a short wait (%.1fs)" % waited)
        check(run_env("get", "meta", "name", *R).returncode == 0, "a read is not blocked by the lock")
    check(open(reg, "rb").read() == before, "the refused set left the file untouched")
    r = run_env("set", "meta", "name", *R, stdin='"After"')
    check(r.returncode == 0 and json.load(open(reg))["meta"]["name"] == "After", "once released, the same set goes through")
    check(os.path.isfile(reg + ".lock") and os.path.getsize(reg + ".lock") == 0,
          "the lock file stays, empty, as an anchor (a re-run leaves the directory byte-identical)")
    r = run_env("set", "components", "button", *R, stdin='"oops"')
    check(r.returncode != 0, "a set that exits on a bad patch…")
    r = run_env("set", "meta", "name", *R, stdin='"Lock was released"')
    check(r.returncode == 0, "…does not leave the lock held")
    r = run_env("set", "meta", "name", "--registry", os.path.join(d, "nope.json"), stdin='"x"')
    check(r.returncode != 0 and "no registry" in r.stderr and not os.path.exists(os.path.join(d, "nope.json.lock")),
          "a missing registry is reported before any lock file is made")
    try:
        with sl.registry_lock(reg, "outer"):
            with sl.registry_lock(reg, "inner", timeout=0.2):
                pass
        check(False, "a nested lock on the same file waits and is refused (it is not re-entrant)")
    except sl.RegistryLocked as e:
        check("outer" in str(e), "a nested lock on the same file is refused too — taking it around only the write would be a bug (%s)" % str(e)[:60])

    print("set — the lock file is never followed or truncated (L2)")
    os.unlink(reg + ".lock")
    victim = os.path.join(d, "victim.txt")
    open(victim, "w").write("do not touch\n")
    os.symlink(victim, reg + ".lock")
    before = open(reg, "rb").read()
    r = run_env("set", "meta", "name", *R, stdin='"Through the lock link"')
    check(r.returncode != 0 and "not a regular file" in r.stderr and "Traceback" not in r.stderr,
          "a symlinked registry.json.lock is refused with a message (%r)" % r.stderr.strip()[:110])
    check(open(victim).read() == "do not touch\n", "…and the file it pointed at was neither written nor truncated")
    check(open(reg, "rb").read() == before and os.path.islink(reg + ".lock"),
          "…the registry is untouched and the symlink is left where it was")
    try:
        with sl.registry_lock(reg, "through a symlink"):
            check(False, "registry_lock refuses a symlinked lock file")
    except sl.LockFileUnsafe as e:
        check(isinstance(e, sl.RegistryLocked) and "not a regular file" in str(e),
              "registry_lock raises LockFileUnsafe — a RegistryLocked, so every caller already stops on it")
    check(open(victim).read() == "do not touch\n", "…also in-process: still untouched")
    os.unlink(reg + ".lock")
    ghost = os.path.join(d, "ghost.txt")
    os.symlink(ghost, reg + ".lock")                              # dangling: O_CREAT would have made the target
    r = run_env("set", "meta", "name", *R, stdin='"Through a dangling link"')
    check(r.returncode != 0 and "not a regular file" in r.stderr and not os.path.exists(ghost),
          "a dangling symlink is refused too, and nothing is created at its target")
    os.unlink(reg + ".lock")
    os.mkfifo(reg + ".lock")
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, SLICE, "set", "meta", "name", *R], input='"Through a fifo"',
                           capture_output=True, text=True, env=env, timeout=15)
        check(r.returncode != 0 and "not a regular file" in r.stderr and time.time() - t0 < 10,
              "a FIFO in its place is refused, not waited on (%.1fs)" % (time.time() - t0))
    except subprocess.TimeoutExpired:
        check(False, "a FIFO in the lock's place made the writer hang")
    os.unlink(reg + ".lock")
    os.mkdir(reg + ".lock")
    r = run_env("set", "meta", "name", *R, stdin='"Through a directory"')
    check(r.returncode != 0 and "not a regular file" in r.stderr and "Traceback" not in r.stderr,
          "a directory in its place is refused with the same message")
    os.rmdir(reg + ".lock")
    check(open(reg, "rb").read() == before, "none of those four touched the registry")
    r = run_env("set", "meta", "name", *R, stdin='"Lock file is ordinary again"')
    check(r.returncode == 0 and json.load(open(reg))["meta"]["name"] == "Lock file is ordinary again"
          and os.path.isfile(reg + ".lock") and not os.path.islink(reg + ".lock") and os.path.getsize(reg + ".lock") == 0,
          "with an ordinary file (or none) the same set goes through, and re-creates the empty anchor")

    print("set — parallel writers lose no update")
    N = 10
    procs = [subprocess.Popen([sys.executable, SLICE, "set", "meta", "par%d" % i, *R], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ, PB_LOCK_TIMEOUT="20"))
             for i in range(N)]
    outs = [(p.communicate('"v%d"' % i), p.returncode) for i, p in enumerate(procs)]
    meta = json.load(open(reg))["meta"]
    check(all(rc == 0 for _o, rc in outs), "all %d parallel sets succeed (%r)" % (N, [o[0][1][:60] for o in outs if o[1]]))
    check(all(meta.get("par%d" % i) == "v%d" % i for i in range(N)),
          "every one of the %d keys is in the file (without the lock, read-modify-write loses some)" % N)
    check(json.load(open(reg)) is not None and [f for f in os.listdir(d) if f.endswith(".tmp")] == [],
          "the file is whole JSON and no temp file is left")

print("ia + list-element paths — get / set / list, append, byte-level isolation")
with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    R = ["--registry", reg]
    base = {
        "meta": {"name": "T"},
        "ia": {"jobs": [{"id": "j1", "when": "a", "want": "b", "so": "c"}, {"id": "j2", "when": "x"}],
               "rules": [{"id": "r1", "title": "One", "text": "é — first", "decision": {"why": "z"}},
                         {"id": "r2", "title": "Two", "text": "second"},
                         {"id": "r3", "title": "Three", "text": "third"}]},
        "flow": {"mermaid": "graph TD", "stories": [{"id": "s1", "title": "S1", "scenarios": [{"id": "a"}]},
                                                     {"id": "s2", "title": "S2"}]},
        "content": {"terms": [{"id": "t1", "term": "Order"}, {"id": "t2", "term": "Item"}]},
        "plain": [],
    }
    base["flow"]["extra"] = ["no", "ids"]

    def dump(reg_obj):
        with open(reg, "w", encoding="utf-8") as f:
            f.write(json.dumps(reg_obj, indent=2, ensure_ascii=False) + "\n")

    dump(base)
    r = run("get", "ia", "rules.r2", *R)
    check(r.returncode == 0 and json.loads(r.stdout)["title"] == "Two", "get ia rules.r2 → that rule")
    r = run("get", "ia", "rules.r1", "--fields", "title,decision", *R)
    check(r.returncode == 0 and list(json.loads(r.stdout)) == ["title", "decision"], "--fields works on a list element")
    r = run("get", "ia", "rules.r1", "--no-prose", "--fields", "id,usage", *R)
    check(r.returncode != 0, "--fields naming a missing key still fails on a list element")
    r = run("get", "flow", "stories.s1.scenarios.a", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == {"id": "a"}, "get flow stories.s1.scenarios.a → nested list element")
    r = run("get", "content", "terms.t2", *R)
    check(r.returncode == 0 and json.loads(r.stdout)["term"] == "Item", "get content terms.t2")
    r = run("get", "flow", "extra.1", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == "ids", "a numeric segment indexes a list without ids")
    r = run("get", "ia", "rules.nope", *R)
    check(r.returncode != 0 and "Traceback" not in r.stderr and len(r.stderr.strip().splitlines()) == 1, "get a missing element → one line, non-zero")
    r = run("get", "ia", "jobs.0", *R)
    check(r.returncode != 0, "a numeric segment does not index a list whose elements carry ids")

    print("list — optional path")
    r = run("list", "ia", *R)
    check(r.stdout.split() == ["jobs", "rules"], "list ia → top-level keys")
    r = run("list", "ia", "rules", *R)
    check([l.split()[0] for l in r.stdout.splitlines()] == ["r1", "r2", "r3"] and "Two" in r.stdout, "list ia rules → ids (and titles)")
    r = run("list", "flow", "stories", *R)
    check([l.split()[0] for l in r.stdout.splitlines()] == ["s1", "s2"], "list flow stories → ids")
    r = run("list", "flow", *R)
    check(r.stdout.split() == ["mermaid", "stories", "extra"], "list flow (no path) unchanged")

    print("set — merge into one element, byte-level isolation")
    before_text = open(reg, encoding="utf-8").read()
    before_obj = json.loads(before_text)
    r = run("set", "ia", "rules.r2", *R, stdin='{"title": "Two!", "status": "open"}')
    check(r.returncode == 0 and "patched" in r.stdout, "set ia rules.r2 → patched (%s)" % r.stdout.strip())
    after_text = open(reg, encoding="utf-8").read()
    after = json.loads(after_text)
    check(after["ia"]["rules"][1] == {"id": "r2", "title": "Two!", "text": "second", "status": "open"}, "the patch merged into r2 (existing keys kept)")
    ser = lambda o: json.dumps(o, indent=2, ensure_ascii=False)
    check(ser(after["ia"]["rules"][0]) == ser(before_obj["ia"]["rules"][0])
          and ser(after["ia"]["rules"][2]) == ser(before_obj["ia"]["rules"][2])
          and ser(after["ia"]["jobs"]) == ser(before_obj["ia"]["jobs"])
          and ser(after["flow"]) == ser(before_obj["flow"]) and ser(after["content"]) == ser(before_obj["content"]),
          "every other element serialises byte-for-byte the same")
    ind = lambda o: "\n".join("      " + ln for ln in ser(o).splitlines())   # an element of ia.rules sits at depth 3
    sa, sb = ind(before_obj["ia"]["rules"][0]), ind(before_obj["ia"]["rules"][2])
    check(sa in after_text and sb in after_text and sa in before_text and sb in before_text,
          "and those bytes sit unchanged in the file text")
    check([id_["id"] for id_ in after["ia"]["rules"]] == ["r1", "r2", "r3"], "element order is unchanged")
    r = run("set", "ia", "rules.r2", *R, stdin='{"status": "open"}')
    check(r.returncode == 0 and "no change" in r.stdout and open(reg, encoding="utf-8").read() == after_text, "re-applying the patch → no change, file byte-identical")
    r = run("set", "ia", "rules.r2", *R, stdin='')
    check(r.returncode == 0 and open(reg, encoding="utf-8").read() == after_text, "an empty patch on an element is byte-identical")
    r = run("set", "flow", "stories.s1.scenarios.a", *R, stdin='{"title": "A"}')
    check(r.returncode == 0 and json.load(open(reg))["flow"]["stories"][0]["scenarios"][0] == {"id": "a", "title": "A"}, "set reaches a nested list element")
    r = run("set", "content", "terms.t1", *R, stdin='{"rule": "r1"}')
    check(r.returncode == 0 and json.load(open(reg))["content"]["terms"][0]["rule"] == "r1", "set content terms.t1")

    print("set — missing elements and lists")
    snap = open(reg, encoding="utf-8").read()
    r = run("set", "ia", "rules.r9", *R, stdin='{"title": "New"}')
    check(r.returncode != 0 and "Traceback" not in r.stderr and len(r.stderr.strip().splitlines()) == 1 and open(reg, encoding="utf-8").read() == snap,
          "set a missing element without a matching id → one-line error, nothing written")
    r = run("set", "ia", "rules.r9", *R, stdin='{"id": "other"}')
    check(r.returncode != 0 and open(reg, encoding="utf-8").read() == snap, "a patch with a different id does not append")
    r = run("set", "ia", "rules.r9", *R, stdin='{"id": "r9", "title": "New"}')
    check(r.returncode == 0 and [x["id"] for x in json.load(open(reg))["ia"]["rules"]] == ["r1", "r2", "r3", "r9"], "a patch carrying the same id appends")
    snap = open(reg, encoding="utf-8").read()
    r = run("set", "ia", "layers.l1", *R, stdin='{"id": "l1"}')
    check(r.returncode != 0 and open(reg, encoding="utf-8").read() == snap, "a missing list (ia.layers) is never created")
    r = run("set", "ia", "rules.r1", *R, stdin='"text"')
    check(r.returncode != 0 and open(reg, encoding="utf-8").read() == snap, "a non-object patch on an element is refused")
    r = run("set", "ia", "intent", *R, stdin='"x"')
    check(r.returncode == 0 and json.load(open(reg))["ia"]["intent"] == "x", "set ia <plain key> works like the other dict kinds")

    print("set — ia is locked like every other write")
    with open(reg + ".lock", "w") as lk:
        import fcntl as _fcntl
        _fcntl.flock(lk, _fcntl.LOCK_EX)
        snap = open(reg, encoding="utf-8").read()
        r = subprocess.run([sys.executable, SLICE, "set", "ia", "rules.r1", *R], input='{"title": "L"}', capture_output=True, text=True,
                           env=dict(os.environ, PB_LOCK_TIMEOUT="0.3"))
        check(r.returncode != 0 and "another pb process" in r.stderr and open(reg, encoding="utf-8").read() == snap,
              "a held lock refuses a list-element set and leaves the file untouched")

print("set — --create-list, a redundant leading kind, mixed id lists, appending a component / screen")
with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    R = ["--registry", reg]
    TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
    OLD = {"meta": {"name": "T"}, "ia": {"populated": False, "jobs": [], "layers": [], "rules": []},
           "flow": {"populated": False}, "components": [{"id": "btn", "name": "Btn"}], "screens": []}

    def dump(obj):
        with open(reg, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    # the fresh template already holds the lists the build commands append to
    shutil.copy(TEMPLATE, reg)
    r = run("set", "content", "terms.t1", *R, stdin='{"id": "t1", "term": "Order"}')
    check(r.returncode == 0 and json.load(open(reg))["content"]["terms"] == [{"id": "t1", "term": "Order"}],
          "fresh template: set content terms.t1 appends (the list is seeded)")
    r = run("set", "flow", "stories.s1", *R, stdin='{"id": "s1", "title": "S"}')
    check(r.returncode == 0 and json.load(open(reg))["flow"]["stories"][0]["id"] == "s1",
          "fresh template: set flow stories.s1 appends (the list is seeded)")

    # an older registry has neither list: refused as before, created with --create-list
    dump(OLD)
    snap = open(reg, encoding="utf-8").read()
    for kind, path, patch in (("content", "terms.t1", '{"id": "t1", "term": "Order"}'),
                              ("flow", "stories.s1", '{"id": "s1", "title": "S"}')):
        r = run("set", kind, path, *R, stdin=patch)
        check(r.returncode != 0 and "--create-list" in r.stderr and len(r.stderr.strip().splitlines()) == 1
              and open(reg, encoding="utf-8").read() == snap, f"without --create-list, set {kind} {path} is refused and writes nothing")
    r = run("set", "content", "terms.t1", "--create-list", *R, stdin='{"id": "t1", "term": "Order"}')
    r2 = run("set", "flow", "stories.s1", "--create-list", *R, stdin='{"id": "s1", "title": "S"}')
    got = json.load(open(reg))
    check(r.returncode == 0 and r2.returncode == 0 and got["content"]["terms"] == [{"id": "t1", "term": "Order"}]
          and got["flow"]["stories"] == [{"id": "s1", "title": "S"}] and got["flow"]["populated"] is False,
          "with --create-list, both lists (and the missing `content` object) are created and appended to")
    r = run("set", "content", "strings", "--create-list", *R, stdin='[{"key": "a.b", "text": "x", "kind": "action"}]')
    check(r.returncode == 0 and json.load(open(reg))["content"]["strings"][0]["key"] == "a.b",
          "--create-list on a list leaf takes a whole-list patch")
    r = run("set", "content", "terms.t1", "--create-list", *R, stdin='{"definition": "d"}')
    check(r.returncode == 0 and json.load(open(reg))["content"]["terms"][0] == {"id": "t1", "term": "Order", "definition": "d"},
          "--create-list on an existing list still merges into the element")

    # a redundant leading kind
    dump(OLD)
    r = run("set", "ia", "ia.jobs", *R, stdin='[{"id": "j1"}]')
    got = json.load(open(reg))
    check(r.returncode == 0 and "ia" not in got["ia"] and got["ia"]["jobs"] == [{"id": "j1"}],
          "set ia ia.jobs behaves as set ia jobs: no stray ia.ia key")
    r = run("get", "ia", "ia.jobs", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == [{"id": "j1"}], "get ia ia.jobs behaves as get ia jobs")
    r = run("set", "meta", "meta.name", *R, stdin='"Renamed"')
    check(r.returncode == 0 and json.load(open(reg))["meta"]["name"] == "Renamed" and "meta" not in json.load(open(reg))["meta"],
          "the same holds for meta (set meta meta.name → meta.name)")
    dump({"meta": {"name": "T"}, "ia": {"ia": {"x": 1}, "jobs": []}})
    r = run("get", "ia", "ia.x", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == 1, "a slice that really has a key named like the kind keeps it (ia.ia.x)")

    # a list with some ids and some without: the id-less one is reachable by position
    dump({"flow": {"stories": [{"title": "old"}, {"id": "s9", "title": "new"}]}})
    r = run("get", "flow", "stories.0", *R)
    check(r.returncode == 0 and json.loads(r.stdout) == {"title": "old"}, "an id-less element in a mixed list is reachable by position")
    r = run("get", "flow", "stories.1", *R)
    check(r.returncode != 0, "…but an element that has an id is reached by that id only")
    r = run("set", "flow", "stories.0.scenarios", *R, stdin='[{"text": "t", "category": "function"}]')
    check(r.returncode == 0 and json.load(open(reg))["flow"]["stories"][0]["scenarios"][0]["text"] == "t",
          "set reaches a key of an id-less story by position")

    # DONE WHEN 6: a new component / screen is appended when the patch carries the same id
    dump(OLD)
    snap = open(reg, encoding="utf-8").read()
    r = run("set", "components", "card", *R, stdin='{"name": "Card"}')
    check(r.returncode != 0 and "no component with id" in r.stderr and open(reg, encoding="utf-8").read() == snap,
          "set components <new id> with no \"id\" in the patch → still the error, nothing written")
    r = run("set", "components", "card", *R, stdin='{"id": "other", "name": "Card"}')
    check(r.returncode != 0 and open(reg, encoding="utf-8").read() == snap, "…and a patch carrying a different id does not append either")
    r = run("set", "components", "card", *R, stdin='{"id": "card", "name": "Card", "level": "molecule"}')
    got = json.load(open(reg))
    check(r.returncode == 0 and "appended" in r.stdout and [c["id"] for c in got["components"]] == ["btn", "card"],
          "set components <new id> with a matching \"id\" appends the entry after the others")
    r = run("set", "screens", "home", *R, stdin='{"id": "home", "name": "Home"}')
    check(r.returncode == 0 and json.load(open(reg))["screens"] == [{"id": "home", "name": "Home"}], "the same for screens (an empty list)")
    r = run("set", "screens", "home", *R, stdin='{"id": "home", "name": "Home 2"}')
    got = json.load(open(reg))
    check(r.returncode == 0 and "patched" in r.stdout and len(got["screens"]) == 1 and got["screens"][0]["name"] == "Home 2",
          "an id that exists is merged, not appended twice")

    # ── line by line (v2.6): --draft, append, drafts ────────────────────────────────────────────
    print("set --draft — a line nobody has approved: the same paths, a different file")
    drafts = os.path.join(d, ".preview", "drafts.json")
    dump({"meta": {"name": "T"}, "ia": {"jobs": [{"id": "j0", "want": "real"}]}, "content": {"terms": []}, "erd": {"populated": False}})
    snap = open(reg, encoding="utf-8").read()
    r = run("set", "ia", "jobs.j1", "--draft", *R, stdin='{"id": "j1", "want": "drafted"}')
    check(r.returncode == 0 and "drafted" in r.stdout and open(reg, encoding="utf-8").read() == snap,
          "set --draft writes nothing to registry.json (byte-identical)")
    check(json.load(open(drafts)) == {"ia": {"jobs": [{"id": "j1", "want": "drafted"}]}}, "…it goes to .preview/drafts.json in the registry's own shape")
    r = run("set", "ia", "jobs.j1", "--draft", *R, stdin='{"so": "merged"}')
    check(r.returncode == 0 and json.load(open(drafts))["ia"]["jobs"] == [{"id": "j1", "want": "drafted", "so": "merged"}],
          "a second --draft set on the same path merges into the same draft element")
    r = run("set", "ia", "sitemap.n1", "--draft", *R, stdin='{"id": "n1", "name": "Home", "depth": 0}')
    check(r.returncode == 0 and json.load(open(drafts))["ia"]["sitemap"][0]["name"] == "Home", "--draft creates a missing list (ia.sitemap) with no --create-list")
    r = run("set", "ia", "jobs.j2", *R, stdin='{"id": "j2", "want": "no"}')
    check(r.returncode == 0 and [j["id"] for j in json.load(open(reg))["ia"]["jobs"]] == ["j0", "j2"], "a plain set is the real write, and it does not touch the drafts")
    r = run("set", "components", "x", "--draft", *R, stdin='{"id": "x"}')
    check(r.returncode != 0 and "--draft covers" in r.stderr, "--draft on a component or screen is refused: they are built, not drafted")
    stray = os.path.join(d, ".preview", "stray")
    open(stray, "w").write("kept")
    check(os.path.isfile(stray), "(a file beside drafts.json is not the tool's to touch)")

    print("the drafts are folded into what the preview shows — never into a file on disk")
    sl = importlib.util.spec_from_file_location("pbslice", SLICE)
    pbslice = importlib.util.module_from_spec(sl)
    sl.loader.exec_module(pbslice)
    real = json.load(open(reg))
    merged = pbslice.overlay_drafts(real, pbslice.load_drafts(drafts))
    check([j["id"] for j in merged["ia"]["jobs"]] == ["j0", "j2", "j1"] and merged["ia"]["jobs"][2].get("_draft") is True
          and "_draft" not in merged["ia"]["jobs"][0], "overlay_drafts appends a draft element and marks it _draft; real ones are not marked")
    check(real == json.load(open(reg)) and "_draft" not in json.dumps(real), "…the registry it was given is not changed")
    check(pbslice.overlay_drafts(real, {}) == real, "no drafts → an equal copy")
    check(pbslice.draft_summary(pbslice.load_drafts(drafts))["count"] == 2, "draft_summary counts the draft lines")
    open(drafts, "w").write("{not json")
    check(pbslice.load_drafts(drafts) == {} and pbslice.overlay_drafts(real, pbslice.load_drafts(drafts)) == real,
          "a corrupt drafts file is no drafts, not an error")
    # the render does not see them: same registry on disk → same HTML, drafts or none
    sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
    import render as _render
    shell = open(os.path.join(ROOT, "pb", "template", "prototype.html"), encoding="utf-8").read()
    html_a, _ = _render.build_html(json.load(open(reg)), shell, "t")
    run("set", "ia", "jobs.j9", "--draft", *R, stdin='{"id": "j9", "want": "late draft"}')
    html_b, _ = _render.build_html(json.load(open(reg)), shell, "t")
    check(html_a == html_b and "late draft" not in html_b, "render.build_html is byte-identical with a draft written (determinism holds)")

    print("drafts --clear / --list")
    r = run("drafts", "--list", *R)
    check(r.returncode == 0 and "j9" in r.stdout, "drafts --list prints what they hold")
    r = run("drafts", "--clear", *R)
    check(r.returncode == 0 and "cleared" in r.stdout and json.load(open(drafts)) == {}, "drafts --clear empties them")
    check(run("drafts", "--clear", *R).stdout.startswith("· no drafts"), "…and clearing nothing says so")
    check(os.path.isfile(stray) and open(reg, encoding="utf-8").read().count("j9") == 0, "…leaving every other file, and the registry, alone")
    os.remove(drafts)
    check(run("drafts", "--list", *R).stdout.startswith("· no drafts"), "with no drafts file at all, --list says so")

    print("append — one element onto a list that has no ids")
    dump({"meta": {"name": "T"}, "content": {"strings": []}, "erd": {"populated": False},
          "flow": {"stories": [{"id": "s1", "title": "S", "scenarios": []}]}})
    r = run("append", "content", "strings", *R, stdin='{"key": "a.b", "text": "x"}')
    check(r.returncode == 0 and json.load(open(reg))["content"]["strings"] == [{"key": "a.b", "text": "x"}], "append adds one element to a list")
    r = run("append", "content", "strings", *R, stdin='{"key": "c.d", "text": "y"}')
    check([s["key"] for s in json.load(open(reg))["content"]["strings"]] == ["a.b", "c.d"], "…and a second one after it")
    r = run("append", "content", "strings", "--key", "key", *R, stdin='{"key": "a.b", "text": "x2"}')
    got = json.load(open(reg))["content"]["strings"]
    check(r.returncode == 0 and "merged" in r.stdout and got[0]["text"] == "x2" and len(got) == 2, "--key makes a repeat of the same line a merge, not a duplicate")
    r = run("append", "erd", "table", *R, stdin='{"entity": "E", "field": "f", "type": "text"}')
    check(r.returncode == 0 and json.load(open(reg))["erd"]["table"] == [{"entity": "E", "field": "f", "type": "text"}], "append creates a missing list (erd.table)")
    r = run("append", "flow", "stories.s1.scenarios", *R, stdin='{"text": "does X"}')
    check(r.returncode == 0 and json.load(open(reg))["flow"]["stories"][0]["scenarios"] == [{"text": "does X"}], "append reaches a story's scenarios through the story id")
    r = run("append", "flow", "stories.nope.scenarios", *R, stdin='{"text": "x"}')
    check(r.returncode != 0 and "no element 'nope'" in r.stderr, "…and an unknown story is an error")
    r = run("append", "content", "strings", *R, stdin='["not", "an", "object"]')
    check(r.returncode != 0 and "one JSON object" in r.stderr, "append takes one object, not a list")
    r = run("append", "components", "x", *R, stdin="{}")
    check(r.returncode != 0, "append does not take components or screens (argparse refuses the kind)")
    snap = open(reg, encoding="utf-8").read()
    r = run("append", "content", "strings", "--draft", *R, stdin='{"key": "z.z", "text": "draft wording"}')
    check(r.returncode == 0 and open(reg, encoding="utf-8").read() == snap
          and json.load(open(drafts))["content"]["strings"] == [{"key": "z.z", "text": "draft wording"}], "append --draft goes to the drafts, not the registry")
    r = run("append", "flow", "stories.s1.scenarios", "--draft", *R, stdin='{"text": "x"}')
    check(r.returncode != 0 and "draft the parent first" in r.stderr, "append --draft under a story the drafts do not hold says to draft the parent first")
    if os.path.exists(drafts):
        os.remove(drafts)

print()
if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("PASS — slice.py CLI is intact")
