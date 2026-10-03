#!/usr/bin/env python3
"""
skill_refs_lint.py — the skill surface stays internal, and every reference to it resolves.

Portability guard (refit plan T4.4), widened in v2.1.0 after users found `think-clarify`
(the skill, exposed as a command) beside `/pb:clarify` and took it for a duplicate. Four checks:

  S1  every pb/skills/<name>/SKILL.md sets `user-invocable: false` — skills are loaded by
      commands and agents, never typed. (Not `disable-model-invocation`: that would stop the
      commands from loading them.)
  S2  every backticked skill-shaped name in pb/commands/ and pb/agents/ resolves to a shipped
      skill. The vocabulary is DERIVED from pb/skills/ plus the prefixes skills are named with,
      so a new skill — or a typo of one — cannot slip past a hard-coded list.
  S3  the shells (prototype.html, design-system.html, runtime.js) never advertise a skill and
      only name real commands: no `skills:` key in TAB_INFO, every `/pb:<cmd>` is a shipped
      command, and every `/pb:<cmd> --<flag>` is a flag that command's file documents. A
      retired name in a doc is allowed only where the line says it is retired.
  S4  (WARN) a skill description's "loaded by /pb:X" names a command that does not load it —
      directly, or through an agent that wraps that command.

Usage:  python3 tests/skill_refs_lint.py
Exit:   0 = clean (warnings allowed) · 1 = an S1–S3 failure
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "pb", "skills")
COMMANDS_DIR = os.path.join(ROOT, "pb", "commands")
AGENTS_DIR = os.path.join(ROOT, "pb", "agents")
SHELLS = [os.path.join(ROOT, "pb", "template", n)
          for n in ("prototype.html", "design-system.html", "runtime.js")]

# Skill names are capability-prefixed (AGENTS.md §2). A backticked token with one of these
# prefixes is a skill reference, whether or not the skill exists — that is the point.
SKILL_SHAPE = re.compile(r"^(?:think|ref|craft|agent|design-component|sandbox)-[a-z0-9-]+$|^figma-use$")
# Names that once existed (retired commands, skills that never shipped, names the shell used to
# advertise). A doc may mention one only to say it is gone.
RETIRED = {
    "build-check-design-system", "build-figma-handoff", "handoff-close", "handoff-dev", "hand-off",
    "preview-ds", "check-drift", "sync-flow", "sync-data", "build-generate", "build-explore",
    "build-flow", "build-logic", "apply-design-system", "craft-research",
}
# Words that mark a line as documenting a retired name rather than using it.
HISTORY = re.compile(r"\b(former|formerly|old|retired|absorbs|replaces|replaced|was|were|until)\b", re.I)


def shipped_skills():
    return {d for d in os.listdir(SKILLS_DIR)
            if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))}


def shipped_commands():
    return {os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(COMMANDS_DIR, "*.md"))}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    out = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def check_s1(errors):
    for name in sorted(shipped_skills()):
        fm = frontmatter(read(os.path.join(SKILLS_DIR, name, "SKILL.md")))
        if fm.get("user-invocable") != "false":
            errors.append(f"S1 pb/skills/{name}/SKILL.md: missing `user-invocable: false` "
                          f"(it would show as /pb:{name})")
        if fm.get("disable-model-invocation") == "true":
            errors.append(f"S1 pb/skills/{name}/SKILL.md: `disable-model-invocation: true` stops "
                          f"the commands from loading it")


def check_s2(errors):
    have = shipped_skills()
    docs = sorted(glob.glob(os.path.join(COMMANDS_DIR, "*.md")) + glob.glob(os.path.join(AGENTS_DIR, "*.md"))
                  + glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md")))
    for path in docs:
        rel = os.path.relpath(path, ROOT)
        lines = read(path).splitlines()
        for n, line in enumerate(lines, 1):
            for name in re.findall(r"`([a-z][a-z0-9-]+)`", line):
                if SKILL_SHAPE.match(name) and name not in have:
                    errors.append(f"S2 {rel}:{n} → `{name}` is not a shipped skill")
                ctx = (lines[n - 2] if n > 1 else "") + " " + line
                if name in RETIRED and not HISTORY.search(ctx):
                    errors.append(f"S2 {rel}:{n} → `{name}` is retired")


def documented_flags(cmd):
    path = os.path.join(COMMANDS_DIR, cmd + ".md")
    return set(re.findall(r"--[a-z][a-z-]*", read(path))) if os.path.isfile(path) else set()


def check_s3(errors):
    cmds = shipped_commands()
    for path in SHELLS:
        if not os.path.isfile(path):
            continue
        rel = os.path.relpath(path, ROOT)
        text = read(path)
        m = re.search(r"const TAB_INFO = \{(.*?)\n    \};", text, re.S)
        if m and re.search(r"^\s*skills\s*:", m.group(1), re.M):
            errors.append(f"S3 {rel}: TAB_INFO advertises `skills:` — skills are internal; "
                          f"list commands only")
        for n, line in enumerate(text.splitlines(), 1):
            for name in re.findall(r"['\"]([a-z][a-z0-9-]+)['\"]", line):
                if name in RETIRED:
                    errors.append(f"S3 {rel}:{n} → '{name}' is retired and must not reach the shell")
            for cmd, flag in re.findall(r"/pb:([a-z][a-z-]*)(?: (--[a-z][a-z-]*))?", line):
                if cmd not in cmds:
                    if not HISTORY.search(line):
                        errors.append(f"S3 {rel}:{n} → /pb:{cmd} is not a shipped command")
                elif flag and flag not in documented_flags(cmd):
                    errors.append(f"S3 {rel}:{n} → /pb:{cmd} {flag}: pb/commands/{cmd}.md "
                                  f"documents no {flag}")
    # Retired command names inside the docs are fine only where the line says so.
    for path in sorted(glob.glob(os.path.join(COMMANDS_DIR, "*.md")) + glob.glob(os.path.join(AGENTS_DIR, "*.md"))):
        rel = os.path.relpath(path, ROOT)
        lines = read(path).splitlines()
        for n, line in enumerate(lines, 1):
            for cmd in re.findall(r"/pb:([a-z][a-z-]*)", line):
                ctx = (lines[n - 2] if n > 1 else "") + " " + line
                if cmd not in cmds and not HISTORY.search(ctx):
                    errors.append(f"S3 {rel}:{n} → /pb:{cmd} is not a shipped command")


def check_s4(warnings):
    agents = {}
    for path in glob.glob(os.path.join(AGENTS_DIR, "*.md")):
        text = read(path)
        agents[path] = (text, set(re.findall(r"/pb:([a-z][a-z-]*)", text)))
    for name in sorted(shipped_skills()):
        desc = frontmatter(read(os.path.join(SKILLS_DIR, name, "SKILL.md"))).get("description", "")
        m = re.search(r"loaded by (.*?)(?:[.;]| — |$)", desc, re.I)
        if not m:
            continue
        claimed = set(re.findall(r"/pb:([a-z][a-z-]*)", m.group(1)))
        mention = re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")
        loaders = set()
        for cmd_path in glob.glob(os.path.join(COMMANDS_DIR, "*.md")):
            if mention.search(read(cmd_path)):
                loaders.add(os.path.splitext(os.path.basename(cmd_path))[0])
        for text, wraps in agents.values():
            if mention.search(text):
                loaders |= wraps
        for cmd in sorted(claimed - loaders):
            warnings.append(f"S4 pb/skills/{name}: description says loaded by /pb:{cmd}, "
                            f"but neither {cmd}.md nor an agent wrapping it mentions {name}")


def main():
    errors, warnings = [], []
    check_s1(errors)
    check_s2(errors)
    check_s3(errors)
    check_s4(warnings)
    have = shipped_skills()
    print(f"shipped skills ({len(have)}): {', '.join(sorted(have))}")
    for w in warnings:
        print(f"  ⚠ {w}")
    if errors:
        print(f"\n✗ {len(errors)} skill-surface failure(s):")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    print("✓ every skill is internal (user-invocable: false), every reference resolves, "
          "and the shells name commands only.")


if __name__ == "__main__":
    main()
