#!/usr/bin/env python3
"""
r0_hygiene.py — guards the R0 groundwork so it can't silently regress:

  1. The three merged commands exist: plan.md / test.md / handoff.md.
  4. lint_registry.py is the tool; check.py is a working shim (import + CLI, same exit codes).
  5. /pb:handoff writes handoff/ (prototype + bundle + AGENTS.md) and AGENTS.template.md ships.

Sections 2 and 3 checked the v1.5.1 alias stubs (sync-flow / sync-erd / hand-off). Those were
deleted when 24 commands merged into 15, so the checks are gone with them — and their real
successor is tests/command_refs.py, which resolves EVERY /pb:* reference rather than three
named ones, and asserts the retired names ship no file.

Usage:  python3 tests/r0_hygiene.py
Exit:   0 = clean · 1 = a regression
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMDS = os.path.join(ROOT, "pb", "commands")
TOOLS = os.path.join(ROOT, "pb", "tools")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


print("1 · the merged commands exist")
for f in ("plan.md", "test.md", "handoff.md"):
    check(os.path.isfile(os.path.join(CMDS, f)), f"pb/commands/{f}")

print("4 · lint_registry.py tool + check.py shim")
check(os.path.isfile(os.path.join(TOOLS, "lint_registry.py")), "pb/tools/lint_registry.py exists")
check(os.path.isfile(os.path.join(TOOLS, "check.py")), "pb/tools/check.py shim exists")
golden = os.path.join(ROOT, "fixtures", "golden", "registry.json")
r_new = subprocess.run([sys.executable, os.path.join(TOOLS, "lint_registry.py"), "--strict", golden],
                       capture_output=True)
r_old = subprocess.run([sys.executable, os.path.join(TOOLS, "check.py"), "--strict", golden],
                       capture_output=True)
check(r_new.returncode == 0 and r_old.returncode == 0 and r_new.returncode == r_old.returncode,
      f"shim ≡ tool on golden (lint={r_new.returncode}, shim={r_old.returncode})")
imp = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r}); import check; "
                      "assert hasattr(check, 'main') and hasattr(check, 'check')"], capture_output=True)
check(imp.returncode == 0, "`import check` re-exports the API")

print("5 · /pb:handoff writes handoff/ + AGENTS template ships")
hc = open(os.path.join(CMDS, "handoff.md"), encoding="utf-8").read()
check("handoff/" in hc and "bundle/" in hc and "AGENTS.md" in hc,
      "handoff mode 1 names handoff/ + bundle/ + AGENTS.md")
check("handoff-dev/" in hc and "logic.md" in hc and "rules.md" in hc,
      "handoff mode 2 names handoff-dev/ + the two Markdown docs")
check("G-FP6" in hc and "registry_to_figma.py" in hc,
      "handoff mode 3 kept the Figma gates and the deterministic lowering")
check(os.path.isfile(os.path.join(ROOT, "pb", "template", "AGENTS.template.md")), "pb/template/AGENTS.template.md")

print()
if fails:
    print(f"✗ {len(fails)} R0 hygiene check(s) failed")
    sys.exit(1)
print("✓ R0 hygiene clean")
