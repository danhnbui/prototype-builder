#!/usr/bin/env python3
"""
shell_lint.py — static hygiene checks on the shipped shell (pb/template/prototype.html).

Guards the Phase 3 fixes so they can't silently regress:
  T3.1 — no duplicate keys in the CHAT_PROMPTS object; no v0.4 'agent-skill-set' /
         'USER-FLOW-GUIDE' references anywhere in the shell.
  T3.2 — no dead wireflow exports (WIREFLOW_SCREENS / WIREFLOW_NOTES / wfCardHtml).
  T3.4 — no v0.4 'cp template.html' authoring instruction in the header comment.

Usage:  python3 tests/shell_lint.py
Exit:   0 = clean · 1 = a regression
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def main():
    src = open(SHELL, encoding="utf-8").read()

    # T3.1 — CHAT_PROMPTS has no duplicate keys
    m = re.search(r"const CHAT_PROMPTS\s*=\s*\{(.*?)\};", src, re.S)
    check(m is not None, "CHAT_PROMPTS block found")
    if m:
        keys = re.findall(r"'(/pb:[a-z-]+)'\s*:", m.group(1))
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        check(not dupes, f"CHAT_PROMPTS has no duplicate keys (dupes: {dupes})")

    # T3.1 — no v0.4 ecosystem references
    for term in ("agent-skill-set", "USER-FLOW-GUIDE"):
        check(term not in src, f"no '{term}' reference in the shell")

    # T3.2 — no dead wireflow exports
    for sym in ("WIREFLOW_SCREENS", "WIREFLOW_NOTES", "wfCardHtml"):
        check(sym not in src, f"no dead wireflow symbol '{sym}' in the shell")

    # T3.4 — no v0.4 'cp template.html' authoring instruction
    check("cp template.html" not in src,
          "no v0.4 'cp template.html' instruction in the header")

    print()
    if _fail:
        print(f"✗ {len(_fail)} shell-lint failure(s).")
        sys.exit(1)
    print("✓ shell-lint clean.")


if __name__ == "__main__":
    main()
