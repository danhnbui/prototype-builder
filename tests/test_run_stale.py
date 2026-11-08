#!/usr/bin/env python3
"""
test_run_stale.py — `test_run.py --functional --stale / --screen <id>` selects only the scenarios
whose verdict is out of date, so a build turn re-runs a handful instead of the whole suite.

  pure half   select_scenarios(): a fresh result is excluded · a changed body is included · a missing
              result is included · a failed or blocked result is included · --screen filters ·
              --story combines · no digests = only never-run, failed and blocked
  CLI half    an empty selection prints `0 scenarios selected (nothing stale)`, exits 0 and launches
              neither a browser (PB_BROWSER_TRACE stays empty) nor a preview server; a --screen id
              that is no screen prints `unknown screen: <id>` and exits 2, also without a browser

Hermetic, no browser.  Usage:  python3 tests/test_run_stale.py     Exit: 0 = pass · 1 = a failure
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
sys.path.insert(0, TOOLS)
for var in ("PB_BROWSER_TRACE", "PB_BROWSER_SLOTS", "PB_BROWSER_WAIT"):
    os.environ.pop(var, None)

import test_run as tr  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def sc(text, start, result=None):
    d = {"text": text, "test": {"start": start, "steps": [], "expect": []}}
    if result is not None:
        d["lastResult"] = result
    return d


def registry():
    return {"flow": {"stories": [
        {"id": "s1", "title": "Sign in", "scenarios": [
            sc("fresh", "login", {"status": "pass", "inputs": {"login": "h1"}}),
            sc("changed", "login", {"status": "pass", "inputs": {"login": "OLD"}}),
            sc("never", "login"),
            sc("noinputs", "login", {"status": "pass"}),
            {"text": "prose only", "test": "do it"},
        ]},
        {"id": "s2", "title": "Checkout", "scenarios": [
            sc("cart fresh", "cart", {"status": "pass", "inputs": {"cart": "c1"}}),
            sc("cart changed", "cart", {"status": "fail", "inputs": {"cart": "OLD"}}),
        ]},
    ]}}


def names(sel):
    return sorted(s[1]["text"] for s in sel)


def main():
    reg, hashes = registry(), {"login": "h1", "cart": "c1"}
    print("pure selection")
    check(len(tr.select_scenarios(reg, hashes)) == 6, "no flags: every runnable scenario (prose-only skipped)")
    st = names(tr.select_scenarios(reg, hashes, stale=True))
    check("fresh" not in st and "cart fresh" not in st, "a fresh result is excluded")
    check("changed" in st and "cart changed" in st, "a changed body is included")
    check("never" in st, "a missing result is included")
    check("noinputs" in st, "a result with no recorded inputs is included (re-run records them)")
    check(names(tr.select_scenarios(reg, hashes, screen="cart")) == ["cart changed", "cart fresh"],
          "--screen keeps only scenarios touching that screen")
    check(names(tr.select_scenarios(reg, hashes, stale=True, screen="cart")) == ["cart changed"],
          "--stale and --screen combine")
    check(names(tr.select_scenarios(reg, hashes, story_filter="s2", stale=True)) == ["cart changed"],
          "--story combines with --stale")
    check(tr.select_scenarios(reg, hashes, stale=True, screen="nowhere") == [], "an unknown screen selects nothing")
    check(names(tr.select_scenarios(reg, {}, stale=True)) == ["cart changed", "never"],
          "no digests available: the never-run and the failed scenario are selected")

    print("failed and blocked results are re-run")
    reg2 = {"flow": {"stories": [{"id": "s1", "title": "T", "scenarios": [
        sc("failed same", "login", {"status": "fail", "inputs": {"login": "h1"}}),
        sc("blocked same", "login", {"status": "blocked", "inputs": {"login": "h1"}}),
        sc("passed same", "login", {"status": "pass", "inputs": {"login": "h1"}}),
        sc("skipped same", "login", {"status": "skip", "inputs": {"login": "h1"}}),
    ]}]}}
    check(names(tr.select_scenarios(reg2, {"login": "h1"}, stale=True)) == ["blocked same", "failed same"],
          "fail and blocked with unchanged inputs are selected; pass and skip are not")
    check(names(tr.select_scenarios(reg2, {}, stale=True)) == ["blocked same", "failed same"],
          "fail and blocked are selected even with no digests to compare")

    print("empty selection (CLI)")
    d = tempfile.mkdtemp(prefix="pb-stale-")
    try:
        r = registry()
        r["screens"] = [{"id": "login"}, {"id": "cart"}]
        for story in r["flow"]["stories"]:
            for s in story["scenarios"]:
                if isinstance(s.get("test"), dict) and "lastResult" not in s:
                    s["lastResult"] = {"status": "pass"}     # nothing missing, and no digests to compare
        path = os.path.join(d, "registry.json")
        with open(path, "w") as fh:
            json.dump(r, fh)
        trace = os.path.join(d, "trace.log")
        env = dict(os.environ, PB_BROWSER_TRACE=trace)
        p = subprocess.run([sys.executable, os.path.join(TOOLS, "test_run.py"), path,
                            "--functional", "--stale", "--screen", "login"],
                           capture_output=True, text=True, env=env, timeout=60, cwd=d)
        check(p.returncode == 0, "exit 0 (got %s)" % p.returncode)
        check("0 scenarios selected (nothing stale)" in p.stdout, "prints the message")
        check(not os.path.exists(trace) or not open(trace).read().strip(), "no browser launch recorded")
        check("serve.py" not in p.stdout and "booting" not in p.stdout.lower(), "no preview server booted")

        print("an unknown screen id (CLI)")
        if os.path.exists(trace):
            os.remove(trace)
        for extra in ([], ["--stale"]):
            p = subprocess.run([sys.executable, os.path.join(TOOLS, "test_run.py"), path,
                                "--functional", "--screen", "logn"] + extra,
                               capture_output=True, text=True, env=env, timeout=60, cwd=d)
            check(p.returncode == 2, "exit 2 for a typo'd --screen%s (got %s)" % (" with --stale" if extra else "", p.returncode))
            check("unknown screen: logn" in p.stdout, "prints `unknown screen: logn`")
            check("nothing stale" not in p.stdout, "does not claim there is nothing stale")
        check(not os.path.exists(trace) or not open(trace).read().strip(), "no browser launch recorded")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%s" % ("FAIL: %d" % len(FAIL) if FAIL else "all passed"))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
