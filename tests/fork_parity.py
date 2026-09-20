#!/usr/bin/env python3
"""
fork_parity.py — the five things a real project forked the shell to get.

A live pb project could not use stock pb: it ran on a hand-patched plugin cache plus its own
copy of prototype.html carrying five hunks. That fork is the sharpest list anyone has of what pb
was missing, because each hunk is a capability someone needed badly enough to maintain a fork for.
All five are stock as of v1.12.0. This test keeps them that way.

  1. ERD `origin` — rows carried over from an existing product are tinted, not left to prose
  2. `meta.shell: 'none'` — a flat screen; the browser metaphor is set dressing on a back-office
     tool, and the fork hid the chrome in its own stylesheet to be rid of it
  3. `registry.runtime[]` with a `url` — the fork hand-edited a <script src> into the shell,
     because pb had no way to declare a third-party dependency
  4. `test.roles` scopes the SHELL's scenario list, not just test_run.py's execution
  5. a Mermaid `[[subprocess]]` node is painted subprocess-grey, not input-purple

Structural, so it runs everywhere; e2e_smoke.py drives 2, 4 and 5 in a browser, and
logic_contract.py covers 3 end to end. Usage: python3 tests/fork_parity.py · Exit 0/1.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = open(os.path.join(ROOT, "pb", "template", "prototype.html"), encoding="utf-8").read()
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


print("1 · ERD origin — a kept/renamed row is visible as such")
check(".erd-row--keep" in SHELL and ".erd-row--rename" in SHELL,
      "both origin states are styled (the fork had `keep` only)")
check("(r.origin || '').toLowerCase()" in SHELL and 'class="erd-row--${org}"' in SHELL,
      "the table renderer reads erd.table[].origin and tints the row")
check("pbErdOriginLegend" in SHELL, "and a legend says what the tints mean")

print("2 · meta.shell: 'none' — a flat screen")
check("['none', 'None']" in SHELL, "the chrome toggle offers a third option")
check(re.search(r"if\s*\(shell === 'none'\)\s*return", SHELL) is not None,
      "protoChrome emits nothing for it on desk-sized frames")
check("protoStatusBar()" in (re.search(r"if \(shell === 'none'\).*", SHELL).group(0)),
      "tablet and mobile keep their status bar — that is a phone, not a browser")
check(".proto-shell--none:not(.proto-frame--tablet):not(.proto-frame--mobile)" in SHELL,
      "and the window frame flattens only on the desk-sized devices")
check("PB_SHELLS[meta.shell]" in SHELL, "meta.shell still sets the default")

print("3 · registry.runtime[] — a declared dependency, not a shell edit")
check("<!--__PB_RUNTIME_DEPS__-->" in SHELL, "the shell carries the marker render.py fills")
render = open(os.path.join(ROOT, "pb", "tools", "render.py"), encoding="utf-8").read()
check('<script src="%s"></script>' in render, "render.py emits a tag per declared url")

print("4 · test.roles scopes the shell's scenario list")
fn = re.search(r"function pbTestScenarioTitles\(\)\s*\{.*?\n    \}", SHELL, re.S)
check(fn is not None, "pbTestScenarioTitles is present")
if fn:
    body = fn.group(0)
    check("sc.test.roles" in body, "it reads the scenario's own roles[]")
    check("state.activeRole" in body, "and filters against the active role")
    check("roles && roles.length" in body,
          "an untagged scenario still shows for everyone — nothing authored before this disappears")

print("5 · a [[subprocess]] node is not painted as an input")
check(re.search(r"pts\.length >= 8\)\s*\{\s*key = 'sub';", SHELL) is not None,
      "the 10-point polygon branch keys 'sub' before stripping the bracket points")

print()
if fails:
    print("FAIL — %d regression(s); a project would have to fork the shell again" % len(fails))
    sys.exit(1)
print("PASS — all five fork hunks are stock")
