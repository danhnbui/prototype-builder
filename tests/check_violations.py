#!/usr/bin/env python3
"""
check_violations.py — asserts pb/tools/lint_registry.py flags EVERY seeded violation.

Runs lint_registry.py --strict on fixtures/violations.json and verifies all twelve seeded
rule codes appear in the output, and that lint_registry.py exits non-zero (error) on it.

Usage:  python3 tests/check_violations.py
Exit:   0 = all twelve caught + non-zero exit · 1 = a miss
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
FIXTURE = os.path.join(ROOT, "fixtures", "violations.json")

EXPECTED = [
    "R-KEBAB", "R-HEX", "R-PX", "R-RENDERFN", "R-SCRIPT",
    "R-DUPID", "R-DTCG-TYPE", "R-DANGER", "R-ORGID",
    "R-LEVEL", "R-COMPOSE", "R-LEVEL-ORDER",
]


def main():
    r = subprocess.run([sys.executable, CHECK, "--strict", FIXTURE],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    sys.stdout.write(out)
    print(f"\n(lint_registry.py exit code: {r.returncode})")

    missing = [code for code in EXPECTED if code not in out]
    if missing:
        print(f"✗ lint_registry.py missed {len(missing)} seeded violation(s): {missing}")
        sys.exit(1)
    if r.returncode == 0:
        print("✗ lint_registry.py --strict must exit non-zero on the violations fixture")
        sys.exit(1)
    print(f"✓ all {len(EXPECTED)} seeded violations caught; lint_registry.py exited {r.returncode}")


if __name__ == "__main__":
    main()
