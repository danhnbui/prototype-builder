#!/usr/bin/env python3
"""
skill_refs_lint.py — every skill a /pb:* command invokes must ship in pb/skills/.

Portability guard (refit plan T4.4): a stranger who installs the plugin must hit zero
dangling skill references. This scans pb/commands/*.md for backticked references to any
known pb skill and asserts each resolves to a pb/skills/<name>/SKILL.md entry.

Usage:  python3 tests/skill_refs_lint.py
Exit:   0 = all references resolve · 1 = a dangling reference
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "pb", "skills")
COMMANDS = glob.glob(os.path.join(ROOT, "pb", "commands", "*.md"))

# The vocabulary of skill names pb commands may reference. A reference to any of these
# must resolve to a shipped skill. (Add a name here if a command starts invoking it.)
SKILL_VOCAB = {
    "ref-prd", "ref-blueprint", "think-critique-prd", "think-clarify",
    "think-layout", "think-logic", "design-component-build",
    "agent-orchestrate-tasks", "craft-connect-flow", "craft-research", "figma-use",
    "ref-design-system", "design-component-export", "ref-figma-frame",
}


def shipped():
    return {d for d in os.listdir(SKILLS_DIR)
            if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))}


def main():
    have = shipped()
    print(f"shipped skills ({len(have)}): {', '.join(sorted(have))}")
    dangling = []  # (command_file, skill_name)
    for path in sorted(COMMANDS):
        text = open(path, encoding="utf-8").read()
        backticked = set(re.findall(r"`([a-z][a-z0-9-]+)`", text))
        for name in sorted(backticked & SKILL_VOCAB):
            if name not in have:
                dangling.append((os.path.basename(path), name))

    if dangling:
        print(f"\n✗ {len(dangling)} dangling skill reference(s):")
        for cmd, name in dangling:
            print(f"  {cmd} → `{name}` (not in pb/skills/)")
        sys.exit(1)
    print("✓ every referenced skill resolves to pb/skills/.")


if __name__ == "__main__":
    main()
