#!/usr/bin/env python3
"""
test_orchestrate.py — unit tests for pb/tools/orchestrate.py.

Pure Python (no browser): drives orchestrate.py over sample memory/tasks.md strings and
asserts wave scheduling, cycle / unknown-agent detection, and the --json contract (incl. the
error path always emitting a parseable JSON object).

Usage:  python3 tests/test_orchestrate.py
Exit:   0 = all passed · 1 = a failure
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH = os.path.join(ROOT, "pb", "tools", "orchestrate.py")

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


def run(md, *flags):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md)
        path = f.name
    try:
        return subprocess.run([sys.executable, ORCH, path, *flags],
                              capture_output=True, text=True)
    finally:
        os.unlink(path)


VALID = """## T1 — login screen
- agent: pb-builder
- deps: none
- slice: screen
- acceptance: renders

## T2 — sync flow
- agent: pb-flow
- deps: T1
- slice: flow
- acceptance: mermaid present
"""

CYCLE = """## T1 login
- agent: pb-builder
- deps: T2
- slice: screen

## T2 dashboard
- agent: pb-builder
- deps: T1
- slice: screen
"""

UNKNOWN = "## T1 x\n- agent: pb-nope\n- deps: none\n- slice: screen\n- acceptance: y\n"
LEGACY = "## T1 old task\n- skill: think-layout\n- acceptance: it renders\n"


def main():
    print("orchestrate.py:")

    # 1. valid graph -> exit 0 + topological waves
    p = run(VALID, "--json")
    check(p.returncode == 0, f"valid tasks.md exits 0 (got {p.returncode}; stderr={p.stderr.strip()[:120]})")
    try:
        waves = json.loads(p.stdout)["waves"]
        ok = (len(waves) == 2 and waves[0][0]["id"] == "T1" and waves[1][0]["id"] == "T2")
        check(ok, f"topological waves = [T1] then [T2] (got {[[t['id'] for t in w] for w in waves]})")
    except Exception as e:
        check(False, f"valid --json stdout parses ({e}; stdout={p.stdout.strip()[:120]})")

    # 2. cycle -> exit 2 + O-CYCLE, and --json still emits a JSON object
    p = run(CYCLE)
    check(p.returncode == 2 and "O-CYCLE" in (p.stdout + p.stderr), "cycle -> exit 2 + O-CYCLE")
    p = run(CYCLE, "--json")
    try:
        obj = json.loads(p.stdout)
        check(p.returncode == 2 and obj.get("error") is True,
              "cycle --json -> exit 2 + parseable {error:true} on stdout")
    except Exception as e:
        check(False, f"cycle --json stdout parses on error path ({e}; stdout={p.stdout.strip()[:120]})")

    # 3. unknown agent -> exit 2 + O-AGENT
    p = run(UNKNOWN)
    check(p.returncode == 2 and "O-AGENT" in (p.stdout + p.stderr), "unknown agent -> exit 2 + O-AGENT")

    # 4. legacy tasks.md (no agent/deps/slice) -> handled without a hard error (WARN path)
    p = run(LEGACY)
    out = p.stdout + p.stderr
    check(p.returncode != 2, f"legacy tasks.md not treated as a hard error (got {p.returncode})")
    check("O-LEGACY" in out, "legacy tasks.md flagged O-LEGACY (skill->agent inference)")

    print()
    if _failures:
        print(f"✗ {len(_failures)} orchestrate assertion(s) failed.")
        sys.exit(1)
    print("✓ All orchestrate assertions passed.")


if __name__ == "__main__":
    main()
