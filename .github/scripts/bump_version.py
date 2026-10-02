#!/usr/bin/env python3
"""
bump_version.py — the `bump-version` stage of .github/workflows/pipeline.yml.

Moves every place that states "the current version" from X to the next SemVer, in one step, so a
release can't ship with the two plugin.json files disagreeing (tests/command_refs.py check 6) or
with a README that still names the last release.

  .claude-plugin/plugin.json      "version" + "Product Builder vX" in the description
  pb/.claude-plugin/plugin.json   "version" + "Product Builder vX" in the description
  .claude-plugin/marketplace.json "Product Builder vX" (twice)
  README.md · CLAUDE.md           the "# Product Builder vX" title line

changelog.md is hand-written and stays that way: a leading `## [Unreleased]` section is renamed to
the new version and today's date; otherwise the run warns that the release has no entry.

DESIGN.md's "Status: vX · last reviewed <date>" is deliberately NOT bumped — it records a review,
and a version bump is not one.

Edits are textual (never json.dump), so key order, spacing and the em-dashes survive byte-for-byte.
Every pattern must match at least once: if a file changes shape, this fails rather than silently
skipping it.

Usage:  python3 .github/scripts/bump_version.py patch|minor|major
        Prints the new version; also writes `version=` to $GITHUB_OUTPUT when set.
Exit:   0 = bumped · 1 = bad input or a pattern that no longer matches
"""
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = ".claude-plugin/plugin.json"   # release-tag checks the tag against this one

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bump(version, part):
    m = SEMVER.match(version)
    if not m:
        sys.exit(f"::error::{SOURCE} version {version!r} is not bare SemVer X.Y.Z")
    major, minor, patch = (int(g) for g in m.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def rewrite(rel, subs):
    """Apply (pattern, replacement) pairs to one file; each must match at least once."""
    path = os.path.join(ROOT, rel)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for pattern, repl in subs:
        text, n = re.subn(pattern, repl, text)
        if n == 0:
            sys.exit(f"::error::{rel}: no match for {pattern!r} — the file changed shape; "
                     f"update .github/scripts/bump_version.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  bumped {rel}")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("patch", "minor", "major"):
        sys.exit("usage: bump_version.py patch|minor|major")

    with open(os.path.join(ROOT, SOURCE), encoding="utf-8") as f:
        old = json.load(f)["version"]
    new = bump(old, sys.argv[1])
    o, n = re.escape(old), new
    print(f"{old} -> {new}")

    version_field = (r'("version":\s*")' + o + r'"', r"\g<1>" + n + '"')
    title = (r"Product Builder v" + o + r"\b", "Product Builder v" + n)

    rewrite(".claude-plugin/plugin.json", [version_field, title])
    rewrite("pb/.claude-plugin/plugin.json", [version_field, title])
    rewrite(".claude-plugin/marketplace.json", [title])
    rewrite("README.md", [(r"^# Product Builder v" + o + r"\b", "# Product Builder v" + n)])
    rewrite("CLAUDE.md", [(r"^# Product Builder v" + o + r"\b", "# Product Builder v" + n)])

    # changelog: only a LEADING [Unreleased] is the next release (an old one sits deep in history).
    cl = os.path.join(ROOT, "changelog.md")
    with open(cl, encoding="utf-8") as f:
        text = f.read()
    first = re.search(r"^## \[[^\]]+\].*$", text, re.M)
    if first and first.group(0).startswith("## [Unreleased]"):
        today = datetime.date.today().isoformat()
        text = text[:first.start()] + f"## [{new}] — {today}" + text[first.end():]
        with open(cl, "w", encoding="utf-8") as f:
            f.write(text)
        print("  bumped changelog.md ([Unreleased] -> release)")
    elif not (first and first.group(0).startswith(f"## [{new}]")):
        print(f"::warning::changelog.md has no [{new}] or leading [Unreleased] entry — "
              f"the release ships without a changelog section")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"version={new}\n")


if __name__ == "__main__":
    main()
