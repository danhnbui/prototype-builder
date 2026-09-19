#!/usr/bin/env python3
"""
slice_cli.py — guards pb/tools/slice.py: read/write ONE registry slice by id without
dragging the whole file into context (token lever #1 at scale).

  1. get  — components/screens by id, tokens/meta by dotted key; missing id/key exits non-zero.
  2. list — enumerates ids (components/screens), leaf paths (tokens), keys (meta).
  3. set  — an empty patch is byte-identical (idempotent, canonical format); a real patch
            merges into only the targeted entry and leaves every other slice untouched.

Fixture-driven off registry.demo.json (no MCP / project needed).

Usage:  python3 tests/slice_cli.py
Exit:   0 = clean · 1 = a regression
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

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

    print("set — dotted flow write leaves siblings intact")
    before_stories = json.load(open(reg))["flow"]["stories"]
    r = run("set", "flow", "mermaid", *R, stdin='"flowchart LR\\n  A --> B"')
    now = json.load(open(reg))["flow"]
    check(r.returncode == 0 and now["mermaid"] == "flowchart LR\n  A --> B", "set flow mermaid replaces the leaf")
    check(now["stories"] == before_stories, "set flow mermaid leaves stories[] untouched")


print()
if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("PASS — slice.py CLI is intact")
