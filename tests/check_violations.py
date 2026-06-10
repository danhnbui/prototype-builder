#!/usr/bin/env python3
"""
check_violations.py — asserts pb/tools/check.py flags EVERY seeded violation.

Runs check.py --strict on fixtures/violations.json and verifies all nine seeded
rule codes appear in the output, and that check.py exits non-zero (error) on it.

Usage:  python3 tests/check_violations.py
Exit:   0 = all nine caught + non-zero exit · 1 = a miss
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "pb", "tools", "check.py")
FIXTURE = os.path.join(ROOT, "fixtures", "violations.json")

EXPECTED = [
    "R-KEBAB", "R-HEX", "R-PX", "R-RENDERFN", "R-SCRIPT",
    "R-DUPID", "R-KIND", "R-DANGER", "R-ORGID",
]


def main():
    r = subprocess.run([sys.executable, CHECK, "--strict", FIXTURE],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    sys.stdout.write(out)
    print(f"\n(check.py exit code: {r.returncode})")

    missing = [code for code in EXPECTED if code not in out]
    if missing:
        print(f"✗ check.py missed {len(missing)} seeded violation(s): {missing}")
        sys.exit(1)
    if r.returncode == 0:
        print("✗ check.py --strict must exit non-zero on the violations fixture")
        sys.exit(1)
    print(f"✓ all {len(EXPECTED)} seeded violations caught; check.py exited {r.returncode}")


if __name__ == "__main__":
    main()
