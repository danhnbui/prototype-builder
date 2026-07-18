#!/usr/bin/env python3
"""
r0_hygiene.py — guards the v1.5.1 R0 groundwork so it can't silently regress:

  1. Command renames landed: flow.md / data.md / handoff-close.md / snapshot.md exist.
  2. Backward-compat aliases resolve: sync-flow.md / sync-erd.md / hand-off.md are thin
     redirect stubs that name their new target, and the target exists.
  3. No stale /pb: invocations of the old names anywhere but changelog.md + the alias stubs.
  4. lint_registry.py is the tool; check.py is a working shim (import + CLI, same exit codes).
  5. handoff-close writes handoff/ (prototype + bundle + AGENTS.md) and AGENTS.template.md ships.
  6. /pb:snapshot round-trips: take → list (newest-first) → restore.

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


print("1 · renamed command files exist")
for f in ("flow.md", "data.md", "handoff-close.md", "snapshot.md"):
    check(os.path.isfile(os.path.join(CMDS, f)), f"pb/commands/{f}")

print("2 · alias stubs resolve to their new target")
for stub, target in (("sync-flow.md", "flow"), ("sync-erd.md", "data"), ("hand-off.md", "handoff-close")):
    p = os.path.join(CMDS, stub)
    txt = open(p, encoding="utf-8").read() if os.path.isfile(p) else ""
    check(os.path.isfile(p) and f"/pb:{target}" in txt and os.path.isfile(os.path.join(CMDS, f"{target}.md")),
          f"{stub} → /pb:{target} (stub names target, target exists)")

print("3 · no stale /pb: invocations of old names (excl. changelog + alias stubs + alias docs)")
stale_re = re.compile(r"/pb:(sync-flow|sync-erd|hand-off)(?![a-z])")
# A line that documents the mapping (arrow, 'alias', or 'deprecated') is allowed to name the
# old command; a genuine invocation line would not. This keeps the guard meaningful.
alias_doc_re = re.compile(r"→|->|alias|deprecated", re.IGNORECASE)
alias_stubs = {"sync-flow.md", "sync-erd.md", "hand-off.md"}
offenders = []
for path in glob.glob(os.path.join(ROOT, "**", "*.*"), recursive=True):
    if "/.git/" in path or os.path.basename(path) == "changelog.md":
        continue
    if os.path.basename(path) in alias_stubs:
        continue
    if not path.endswith((".md", ".py", ".json", ".html")):
        continue
    try:
        for ln in open(path, encoding="utf-8"):
            if stale_re.search(ln) and not alias_doc_re.search(ln):
                offenders.append(f"{os.path.relpath(path, ROOT)}: {ln.strip()[:70]}")
                break
    except (UnicodeDecodeError, IsADirectoryError):
        pass
check(not offenders, f"clean (offenders: {offenders})")

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

print("5 · handoff-close writes handoff/ + AGENTS template ships")
hc = open(os.path.join(CMDS, "handoff-close.md"), encoding="utf-8").read()
check("handoff/" in hc and "bundle/" in hc and "AGENTS.md" in hc, "handoff-close names handoff/ + bundle/ + AGENTS.md")
check(os.path.isfile(os.path.join(ROOT, "pb", "template", "AGENTS.template.md")), "pb/template/AGENTS.template.md")

print("6 · /pb:snapshot round-trips")
snap = os.path.join(TOOLS, "snapshot.py")
with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    open(reg, "w").write(json.dumps({"meta": {"name": "V1"}}))
    subprocess.run([sys.executable, snap, reg], cwd=d, capture_output=True)
    open(reg, "w").write(json.dumps({"meta": {"name": "V2"}}))
    subprocess.run([sys.executable, snap, reg], cwd=d, capture_output=True)
    lst = subprocess.run([sys.executable, snap, reg, "--list"], cwd=d, capture_output=True, text=True)
    snaps = [ln for ln in lst.stdout.splitlines() if ln.strip()]
    oldest = os.path.join(d, snaps[-1])  # newest-first → last line is oldest = V1
    subprocess.run([sys.executable, snap, reg, "--restore", oldest], cwd=d, capture_output=True)
    restored = json.load(open(reg))["meta"]["name"]
    check(len(snaps) == 2 and restored == "V1", f"take×2, list newest-first, restore oldest→V1 (got {restored})")

print()
if fails:
    print(f"✗ {len(fails)} R0 hygiene check(s) failed")
    sys.exit(1)
print("✓ R0 hygiene clean")
