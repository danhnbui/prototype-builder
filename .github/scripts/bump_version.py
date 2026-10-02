#!/usr/bin/env python3
"""
bump_version.py — the version step of the release flow (.github/workflows/pipeline.yml).

The bump lands IN THE PR, before merge: main is protected by required checks, and nothing the
pipeline's own GITHUB_TOKEN pushes can earn them, so main only ever receives a version through a
reviewed PR. Run `auto` on your branch, commit the result; the PR check (`check`) fails until you do.

Every place that states "the current version" moves together, so a release can't ship with the two
plugin.json files disagreeing (tests/command_refs.py check 6) or a README naming the last release:

  .claude-plugin/plugin.json      "version" + "Product Builder vX" in the description
  pb/.claude-plugin/plugin.json   "version" + "Product Builder vX" in the description
  .claude-plugin/marketplace.json "Product Builder vX" (twice)
  README.md · CLAUDE.md           the "# Product Builder vX" title line

changelog.md is hand-written and stays that way: a leading `## [Unreleased]` section is renamed to
the new version and today's date; otherwise this warns that the release has no entry. DESIGN.md's
"Status: vX · last reviewed <date>" is deliberately NOT bumped — it records a review.

The bump a change needs comes from the Conventional Commit subjects since the last vX.Y.Z tag:
  `type!:` or a `BREAKING CHANGE:` footer → major · `feat:` → minor · `fix:` / `perf:` → patch.
Anything else (docs, ci, chore, test, refactor, merge commits) needs no release.

Usage:  python3 .github/scripts/bump_version.py auto|patch|minor|major|check
  auto     stamp the bump the commits ask for (no-op if already bumped enough, or none is needed)
  patch…   force that bump from the current version
  check    read-only: stamps agree, and the version is at least what the commits ask for.
           Writes `version=` to $GITHUB_OUTPUT — the unreleased version, or empty if main's
           version is already tagged (nothing to release).
Exit:   0 = ok · 1 = needs a bump, stamps disagree, bad input, or no vX.Y.Z tag to measure from
"""
import datetime
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = ".claude-plugin/plugin.json"   # release-tag checks the tag against this one

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
RANK = {"patch": 1, "minor": 2, "major": 3}
BREAKING_SUBJECT = re.compile(r"^\w+(\([^)]*\))?!:")
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE:", re.M)
MINOR_SUBJECT = re.compile(r"^feat(\([^)]*\))?:")
PATCH_SUBJECT = re.compile(r"^(fix|perf)(\([^)]*\))?:")
FIX_HINT = "python3 .github/scripts/bump_version.py auto"


def stamps(v):
    """(file, regex) for every place that must state version v — each must match at least once."""
    e = re.escape(v)
    field = r'"version":\s*"' + e + '"'
    title = r"Product Builder v" + e + r"\b"
    heading = r"^# Product Builder v" + e + r"\b"
    return [
        (".claude-plugin/plugin.json", [field, title]),
        ("pb/.claude-plugin/plugin.json", [field, title]),
        (".claude-plugin/marketplace.json", [title]),
        ("README.md", [heading]),
        ("CLAUDE.md", [heading]),
    ]


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def vt(v):
    m = SEMVER.match(v)
    if not m:
        sys.exit(f"::error::version {v!r} is not bare SemVer X.Y.Z")
    return tuple(int(g) for g in m.groups())


def bump(version, part):
    major, minor, patch = vt(version)
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def last_tag():
    r = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*.[0-9]*.[0-9]*", "HEAD")
    if r.returncode != 0:
        sys.exit("::error::no vX.Y.Z tag is reachable from HEAD — nothing to measure the bump "
                 "from (shallow clone? fetch with tags)")
    return r.stdout.strip()


def required_part(tag):
    """The largest bump any commit since `tag` asks for, or None — plus the commits that asked."""
    log = git("log", "--format=%h%x1f%B%x1e", f"{tag}..HEAD").stdout
    best, why = None, []
    for entry in filter(None, (e.strip() for e in log.split("\x1e"))):
        sha, _, body = entry.partition("\x1f")
        subject = body.split("\n", 1)[0]
        if BREAKING_SUBJECT.match(subject) or BREAKING_FOOTER.search(body):
            part = "major"
        elif MINOR_SUBJECT.match(subject):
            part = "minor"
        elif PATCH_SUBJECT.match(subject):
            part = "patch"
        else:
            continue
        why.append(f"  {part:5}  {sha} {subject}")
        if best is None or RANK[part] > RANK[best]:
            best = part
    return best, why


def write_output(version):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"version={version}\n")


def stamp(old, new):
    """Rewrite every stamp from old to new, textually, so formatting survives byte-for-byte."""
    o = re.escape(old)
    subs = {
        "field": (r'("version":\s*")' + o + '"', r"\g<1>" + new + '"'),
        "title": (r"Product Builder v" + o + r"\b", "Product Builder v" + new),
        "heading": (r"^# Product Builder v" + o + r"\b", "# Product Builder v" + new),
    }
    plan = {".claude-plugin/plugin.json": ["field", "title"],
            "pb/.claude-plugin/plugin.json": ["field", "title"],
            ".claude-plugin/marketplace.json": ["title"],
            "README.md": ["heading"], "CLAUDE.md": ["heading"]}
    for rel, kinds in plan.items():
        text = read(rel)
        for k in kinds:
            text, n = re.subn(subs[k][0], subs[k][1], text)
            if n == 0:
                sys.exit(f"::error::{rel}: no {k} stamp for v{old} — the file changed shape; "
                         f"update .github/scripts/bump_version.py")
        with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  bumped {rel}")

    # changelog: only a LEADING [Unreleased] is the next release (an old one sits deep in history).
    text = read("changelog.md")
    first = re.search(r"^## \[[^\]]+\].*$", text, re.M)
    if first and first.group(0).startswith("## [Unreleased]"):
        today = datetime.date.today().isoformat()
        text = text[:first.start()] + f"## [{new}] — {today}" + text[first.end():]
        with open(os.path.join(ROOT, "changelog.md"), "w", encoding="utf-8") as f:
            f.write(text)
        print("  bumped changelog.md ([Unreleased] -> release)")
    elif not (first and first.group(0).startswith(f"## [{new}]")):
        print(f"::warning::changelog.md has no [{new}] or leading [Unreleased] entry — "
              f"the release ships without a changelog section")


def check(current):
    bad = [f"{rel} does not state v{current}" for rel, pats in stamps(current)
           for p in pats if not re.search(p, read(rel), re.M)]
    if bad:
        sys.exit("::error::version stamps disagree — " + "; ".join(bad) + f". Fix: {FIX_HINT}")

    tag = last_tag()
    base = tag[1:]
    part, why = required_part(tag)
    expected = bump(base, part) if part else base
    print(f"last release {tag} · this tree {current} · commits since ask for: {part or 'nothing'}")
    print("\n".join(why))

    if vt(current) < vt(expected):
        sys.exit(f"::error::these changes need a {part} release (v{expected}) but the version is "
                 f"still {current}. Run `{FIX_HINT}` on your branch and commit the result.")
    released = git("rev-parse", "-q", "--verify", f"refs/tags/v{current}").returncode == 0
    if current != base and released:
        sys.exit(f"::error::v{current} is already released — bump past it: {FIX_HINT}")
    if current == base:
        print("nothing to release")
        write_output("")
    else:
        print(f"releases v{current} on merge")
        write_output(current)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("auto", "patch", "minor", "major", "check"):
        sys.exit("usage: bump_version.py auto|patch|minor|major|check")
    mode = sys.argv[1]
    current = json.loads(read(SOURCE))["version"]
    vt(current)

    if mode == "check":
        return check(current)

    if mode == "auto":
        tag = last_tag()
        part, why = required_part(tag)
        print(f"since {tag}: {part or 'nothing to release'}")
        print("\n".join(why))
        if part is None:
            return
        new = bump(tag[1:], part)
        if vt(current) >= vt(new):
            print(f"already at {current} (needs ≥ {new}) — nothing to do")
            return
    else:
        new = bump(current, mode)

    print(f"{current} -> {new}")
    stamp(current, new)


if __name__ == "__main__":
    main()
