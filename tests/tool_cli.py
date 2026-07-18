#!/usr/bin/env python3
"""
tool_cli.py — the registry-taking tools accept the registry BOTH positionally and via --registry.

The command docs (pull-ds.md, check-drift.md §5, init.md 6c) invoke clone_ds.py / resolve_frame.py
with the registry as a positional arg; other tools (snapshot.py, render_react.py, ds_serve.py) already
did. This guards that uniform CLI so a doc-vs-tool mismatch can't silently reappear.

Usage:  python3 tests/tool_cli.py
Exit:   0 = clean · 1 = a regression
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
DS_EXPORT = os.path.join(ROOT, "fixtures", "ds-export.json")
FRAME = os.path.join(ROOT, "fixtures", "frame-export.json")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def run(*args, cwd):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True).returncode


with tempfile.TemporaryDirectory() as d:
    reg = os.path.join(d, "registry.json")
    json.dump(json.load(open(TEMPLATE)), open(reg, "w"))
    clone = os.path.join(TOOLS, "clone_ds.py")
    resolve = os.path.join(TOOLS, "resolve_frame.py")

    print("clone_ds.py — positional and --registry both accepted")
    check(run(clone, "--from", DS_EXPORT, "registry.json", cwd=d) == 0, "clone_ds --from … registry.json (positional, the doc form)")
    check(run(clone, "--drift", DS_EXPORT, "--registry", reg, cwd=d) == 0, "clone_ds --drift … --registry PATH (flag form)")

    print("resolve_frame.py — positional and --registry both accepted")
    check(run(resolve, "--from", FRAME, "registry.json", cwd=d) == 0, "resolve_frame --from … registry.json (positional, the doc form)")
    check(run(resolve, "--from", FRAME, "--registry", reg, cwd=d) == 0, "resolve_frame --from … --registry PATH (flag form)")

print()
if fails:
    print(f"✗ {len(fails)} tool-CLI check(s) failed")
    sys.exit(1)
print("✓ tool-CLI uniform")
