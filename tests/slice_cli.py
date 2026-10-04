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

print()
if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("PASS — slice.py CLI is intact")
