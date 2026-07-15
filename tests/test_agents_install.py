#!/usr/bin/env python3
"""
test_agents_install.py — unit tests for pb/tools/agents_install.py.

Pure Python: installs the pb-*.md agent roster into a temp project's .claude/agents/, asserts
all 8 land, that a pre-existing NON-pb file is never touched (own-only discipline), and that a
second run is idempotent.

Usage:  python3 tests/test_agents_install.py
Exit:   0 = all passed · 1 = a failure
"""
import glob
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "pb", "tools", "agents_install.py")
SRC_COUNT = len(glob.glob(os.path.join(ROOT, "pb", "agents", "pb-*.md")))

_failures = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _failures.append(msg)


def main():
    print("agents_install.py:")
    check(SRC_COUNT == 8, f"source roster has 8 pb-*.md (found {SRC_COUNT})")

    with tempfile.TemporaryDirectory() as d:
        agents_dir = os.path.join(d, ".claude", "agents")
        os.makedirs(agents_dir)
        foreign = os.path.join(agents_dir, "my-custom.md")
        with open(foreign, "w", encoding="utf-8") as f:
            f.write("keep me\n")

        p1 = subprocess.run([sys.executable, INSTALL, "--project-dir", d],
                            capture_output=True, text=True)
        check(p1.returncode == 0, f"first run exits 0 (got {p1.returncode}; {p1.stderr.strip()[:120]})")
        installed = glob.glob(os.path.join(agents_dir, "pb-*.md"))
        check(len(installed) == SRC_COUNT, f"all {SRC_COUNT} pb-*.md installed (found {len(installed)})")
        check(os.path.exists(foreign) and open(foreign).read() == "keep me\n",
              "pre-existing non-pb file left untouched (own-only discipline)")

        p2 = subprocess.run([sys.executable, INSTALL, "--project-dir", d],
                            capture_output=True, text=True)
        check(p2.returncode == 0, f"second run exits 0 (idempotent; got {p2.returncode})")
        check(len(glob.glob(os.path.join(agents_dir, "pb-*.md"))) == SRC_COUNT,
              "still exactly the roster after a second run (no duplication)")
        check(os.path.exists(foreign) and open(foreign).read() == "keep me\n",
              "foreign file still intact after the second run")

    print()
    if _failures:
        print(f"✗ {len(_failures)} agents_install assertion(s) failed.")
        sys.exit(1)
    print("✓ All agents_install assertions passed.")


if __name__ == "__main__":
    main()
