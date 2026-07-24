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


print()
if fails:
    print(f"FAIL — {len(fails)} regression(s)")
    sys.exit(1)
print("PASS — slice.py CLI is intact")
