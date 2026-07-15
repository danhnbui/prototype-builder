#!/usr/bin/env python3
"""
test_security.py — unit tests for pb/tools/security_scan.py.

Pure Python: asserts the scanner flags a seeded hardcoded key + real-looking email in
fixtures/security_bad/, masks the secret (never re-leaks it), and stays clean (exit 0) on the
committed golden.

Usage:  python3 tests/test_security.py
Exit:   0 = all passed · 1 = a failure
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "pb", "tools", "security_scan.py")
BAD = os.path.join(ROOT, "fixtures", "security_bad", "registry.json")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")
LEAKED_SECRET = "sk-abc123DEF456ghi789JKL012mno345"  # the literal seeded in the bad fixture

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


def run(reg):
    return subprocess.run([sys.executable, SCAN, reg], capture_output=True, text=True)


def main():
    print("security_scan.py:")

    p = run(BAD)
    out = p.stdout + p.stderr
    check(p.returncode == 2, f"seeded-secret fixture -> exit 2 (got {p.returncode})")
    check("R-SEC-KEY" in out, "flags the hardcoded API key (R-SEC-KEY)")
    check("R-SEC-EMAIL" in out or "R-SEC-PII" in out, "flags the real-looking email / PII")
    check(LEAKED_SECRET not in out, "masks the secret in output (never re-leaks the literal)")

    p = run(GOLDEN)
    check(p.returncode == 0,
          f"clean golden -> exit 0 (got {p.returncode}; out={(p.stdout + p.stderr).strip()[:240]})")

    print()
    if _failures:
        print(f"✗ {len(_failures)} security assertion(s) failed.")
        sys.exit(1)
    print("✓ All security assertions passed.")


if __name__ == "__main__":
    main()
