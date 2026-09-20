#!/usr/bin/env python3
"""
command_refs.py — every /pb:* reference resolves, and the router table matches what ships.

The gap this closes: nothing guarded command cross-links. `skill_refs_lint.py` checks that a
skill a command invokes exists; no test checked that a COMMAND another file points at exists.
So the merge — 24 commands down to 12 — could have left `/pb:flow`, `/pb:check-drift` and
`/pb:handoff-close` referenced from 36 files with a green sweep, and the first person to follow
one would hit a command that is not there.

  1. Every `/pb:<name>` in a live file resolves to pb/commands/<name>.md, or is a name this
     test declares RETIRED (which documents the retirement where it can go stale loudly).
  2. Every RETIRED name really is gone — no command file, so nothing resolves it by accident.
  3. Every relative .md link inside pb/commands/ points at a file that exists.
  4. CLAUDE.md's router table and pb/commands/*.md agree, BOTH ways: no shipped command missing
     a row, no row naming a command that does not ship.

changelog.md and docs/ are excluded: they are a historical record of what pb was at the time,
and rewriting history to keep a linter happy is worse than the dangling link.

Usage:  python3 tests/command_refs.py
Exit:   0 = clean · 1 = a dangling reference or a table mismatch
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMD_DIR = os.path.join(ROOT, "pb", "commands")

# Retired when 24 commands merged into 13. They may still be NAMED (a retirement note, an
# "absorbs the former X" aside) but must not exist as files, and must not be presented as runnable.
RETIRED = {
    "flow", "data", "sync-flow", "sync-erd",                             # → /pb:plan --flow / --data
    "check-drift",                                                       # → /pb:test --drift
    "handoff-close", "handoff-dev", "hand-off", "build-figma-handoff",   # → /pb:handoff
    "build-check-design-system",                                         # → /pb:build §3a
    "preview-ds",                                                        # → /pb:preview §2b
    "validate",                                                          # → /pb:handoff --tier=host
}

SKIP_PREFIX = ("changelog.md", "docs/", ".venv/")
REF = re.compile(r"/pb:([a-z][a-z0-9-]*)")
MD_LINK = re.compile(r"\]\(([A-Za-z0-9_.-]+\.md)\)")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout
    return [f for f in out.split()
            if f.endswith((".md", ".py", ".json", ".html")) and not f.startswith(SKIP_PREFIX)]


shipped = {os.path.basename(f)[:-3] for f in os.listdir(CMD_DIR) if f.endswith(".md")}
print("shipped commands (%d): %s" % (len(shipped), ", ".join(sorted(shipped))))
print()

print("1 · every /pb:* reference resolves")
dangling = {}
for rel in tracked():
    path = os.path.join(ROOT, rel)
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        continue
    for name in set(REF.findall(text)):
        if name in shipped or name in RETIRED:
            continue
        dangling.setdefault(name, []).append(rel)
check(not dangling, "no unknown /pb:<name> anywhere (%d found)" % len(dangling))
for name, where in sorted(dangling.items()):
    print("      /pb:%s ← %s" % (name, ", ".join(sorted(where)[:4])))

print("2 · retired commands are actually gone")
still_here = sorted(RETIRED & shipped)
check(not still_here, "no retired command still ships a file (%s)" % (still_here or "none"))

print("3 · relative .md links inside pb/commands/ resolve")
bad_links = []
for fn in sorted(os.listdir(CMD_DIR)):
    if not fn.endswith(".md"):
        continue
    text = open(os.path.join(CMD_DIR, fn), encoding="utf-8").read()
    for target in set(MD_LINK.findall(text)):
        if not os.path.exists(os.path.join(CMD_DIR, target)):
            bad_links.append("%s → %s" % (fn, target))
check(not bad_links, "every command-to-command link resolves (%d broken)" % len(bad_links))
for b in bad_links:
    print("      " + b)

print("4 · CLAUDE.md's router table matches what ships")
claude = open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8").read()
rows = set(re.findall(r"(?m)^\| `/pb:([a-z][a-z0-9-]*)`", claude))
missing_row = sorted(shipped - rows)
orphan_row = sorted(rows - shipped)
check(not missing_row, "every shipped command has a table row (missing: %s)" % (missing_row or "none"))
check(not orphan_row, "every table row names a shipped command (orphan: %s)" % (orphan_row or "none"))

print()
if fails:
    print("FAIL — %d problem(s)" % len(fails))
    sys.exit(1)
print("PASS — %d commands, every reference and table row resolves" % len(shipped))
