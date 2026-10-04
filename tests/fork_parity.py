#!/usr/bin/env python3
"""
fork_parity.py — what a real project had to build itself, because pb could not.

A live pb project could not use stock pb: it ran on a hand-patched plugin cache plus its own
copy of prototype.html carrying five hunks. That fork is the sharpest list anyone has of what pb
was missing, because each hunk is a capability someone needed badly enough to maintain a fork for.
All five are stock as of v2.0.0. This test keeps them that way.

  1. ERD `origin` — rows carried over from an existing product are tinted, not left to prose
  2. `meta.shell: 'none'` — a flat screen; the browser metaphor is set dressing on a back-office
     tool, and the fork hid the chrome in its own stylesheet to be rid of it
  3. `registry.runtime[]` with a `url` — the fork hand-edited a <script src> into the shell,
     because pb had no way to declare a third-party dependency
  4. `test.roles` scopes the SHELL's scenario list, not just test_run.py's execution
  5. a Mermaid `[[subprocess]]` node is painted subprocess-grey, not input-purple

Beside the fork it kept 1,076 lines of hand-rolled verification gates, for the same reason.
Each has a pb equivalent now; this checks the equivalents are still wired.

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
check("protoStatusBar(" in (re.search(r"if \(shell === 'none'\).*", SHELL).group(0)),
      "tablet and mobile keep their status bar — that is a phone, not a browser")
check(".proto-shell--none:not(.proto-frame--tablet):not(.proto-frame--mobile)" in SHELL,
      "and the window frame flattens only on the desk-sized devices")
check("PB_SHELLS[meta.shell]" in SHELL, "meta.shell still sets the default")

print("3 · registry.runtime[] — a declared dependency, not a shell edit")
check("<!--__PB_RUNTIME_DEPS__-->" in SHELL, "the shell carries the marker render.py fills")
render = open(os.path.join(ROOT, "pb", "tools", "render.py"), encoding="utf-8").read()
check('<script src="%s"></script>' in render, "render.py emits a tag per declared url")

print("4 · test.roles scopes the shell's scenario list")
fn = re.search(r"function pbTestScenarios\(\)\s*\{.*?\n    \}", SHELL, re.S)
check(fn is not None, "pbTestScenarios is present")
if fn:
    body = fn.group(0)
    # Round 3 reads it through a local (`const test = … sc.test …; test.roles`) so prose-shaped
    # scenarios (`test` is a string) get `{}`; the field is the same one test_run.py reads.
    check("sc.test.roles" in body or (re.search(r"const test = [^;]*sc\.test", body) and "test.roles" in body),
          "it reads the scenario's own roles[]")
    check("state.activeRole" in body, "and filters against the active role")
    check("roles && roles.length" in body,
          "an untagged scenario still shows for everyone — nothing authored before this disappears")

print("5 · a [[subprocess]] node is not painted as an input")
# Round 3 renamed the subprocess palette key 'sub' → 'external' (the canvas tokens' name).
check(re.search(r"pts\.length >= 8\)\s*\{\s*key = '(?:sub|external)';", SHELL) is not None,
      "the 10-point polygon branch keys the subprocess shape before stripping the bracket points")

print("6 · the hand-rolled gates have pb equivalents")
LINT = open(os.path.join(ROOT, "pb", "tools", "lint_registry.py"), encoding="utf-8").read()
LOGIC = open(os.path.join(ROOT, "pb", "tools", "logic_check.py"), encoding="utf-8").read()
TEST = open(os.path.join(ROOT, "pb", "tools", "test_run.py"), encoding="utf-8").read()
check(os.path.isfile(os.path.join(ROOT, "tests", "render_escape.py")),
      "G0 preflight, trap 1 (the blanket `</` escape) — guarded by a test since v1.11.1")
check("def freeze_capture" in LOGIC and "def freeze_compare" in LOGIC,
      "G1 logic_freeze — logic_check.py --freeze, over bodyHash")
check("L-DEADSEAM" in LOGIC,
      "G2 seam_extract — L-DEADSEAM, which asks the cross-check question instead of "
      "diffing a baseline, so it has strictly fewer false-positive modes")
for r in ("L-HAS-R1", "L-HAS-R2", "L-HAS-R3", "L-HAS-R4"):
    check(r in LOGIC, "G3 has_rules %s — ported rule for rule" % r[2:])
check('for key in ("present", "absent")' in TEST and "def _apply_role" in TEST,
      "G4 role_affordances — test.roles + present/absent expects express "
      "(screen, role, selector) as registry scenarios")
check("R-TOKENREF" in LINT, "W0 token_sweep — R-TOKENREF")

print()
if fails:
    print("FAIL — %d regression(s); a project would have to fork the shell again" % len(fails))
    sys.exit(1)
print("PASS — all five fork hunks are stock, and every hand-rolled gate has an equivalent")
