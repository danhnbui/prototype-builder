#!/usr/bin/env python3
"""
migration_guide.py — the release's migration guide is derived correctly, and its gate bites.

Builds a scratch git repo (never this one: its tags and changelog move every release) with three
releases — v1.2.0 (schema 2, commands build data check-drift), v1.3.0 (schema 3, check-drift
retired) — and a working tree at v2.0.0 (schema 4, data retired), then drives .github/scripts/migration_guide.py --root against it:

  1. `check` fails before `write`: the guide is missing, the major has no `### Upgrading`, and a
     retired command has no replacement — each named.
  2. With those supplied, `write` then `check` pass.
  3. The guide states what the history says: a row per distinct starting point, the schema steps it
     runs, the release that retired each command, the carried upgrade notes, the changelog section.
  4. Editing the changelog after `write` makes `check` fail as out of date.
  5. A patch with no schema change and nothing removed needs no `### Upgrading`.
  6. Once the version is tagged, `check` passes untouched and `write` leaves the shipped guide alone.
  7. `print --release` turns the guide's relative links into links at the tag; changelog links
     written from the repo root are rebased so they resolve from docs/migrations/.

Usage:  python3 tests/migration_guide.py
Exit:   0 = clean · 1 = a failure
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, ".github", "scripts", "migration_guide.py")

_fail = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        _fail.append(msg)


MANIFEST = '''
import importlib.util, os
CURRENT_SCHEMA = {schema}
_REGISTRY = {registry}
def _load(stem):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), stem + ".py")
    spec = importlib.util.spec_from_file_location(stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
'''

STEP = '''
FROM, TO = {f}, {t}
def up(reg, base_dir=None): return reg
def down(reg, base_dir=None): return reg
def describe(): return "schema {f} → {t}: step {n}"
'''


class Scratch:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="pb-migration-guide-")

    def write(self, rel, text):
        p = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def rm(self, rel):
        os.remove(os.path.join(self.dir, rel))

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                       cwd=self.dir, check=True, capture_output=True)

    def release(self, version, schema, commands, changelog, tag=True):
        self.write(".claude-plugin/plugin.json", json.dumps({"version": version}))
        steps = [(n, n + 1, f"000{n - 1}_s{n}") for n in range(2, schema)]
        self.write("pb/migrations/manifest.py", MANIFEST.format(schema=schema, registry=repr(steps)))
        for f, t, stem in steps:
            self.write(f"pb/migrations/{stem}.py", STEP.format(f=f, t=t, n=stem[:4]))
        cdir = os.path.join(self.dir, "pb", "commands")
        if os.path.isdir(cdir):
            shutil.rmtree(cdir)
        for c in commands:
            self.write(f"pb/commands/{c}.md", f"# /pb:{c}\n")
        self.write("changelog.md", changelog)
        if tag:
            self.git("add", "-A")
            self.git("commit", "-qm", f"release: v{version}")
            self.git("tag", f"v{version}")

    def run(self, *args):
        r = subprocess.run([sys.executable, SCRIPT, *args, "--root", self.dir],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def read(self, rel):
        with open(os.path.join(self.dir, rel), encoding="utf-8") as f:
            return f.read()


LOG_13 = """# Changelog

## [1.3.0] — 2026-01-02

- Did a thing.

### Removed

- `/pb:check-drift` — it was never used.

## [1.2.0] — 2026-01-01

- First.
"""

LOG_20 = """# Changelog

## [2.0.0] — 2026-02-01

- The big one. Rules: [AGENTS.md](AGENTS.md).

""" + LOG_13.split("\n", 2)[2]

UPGRADING = "### Upgrading\n\nRun `/pb:build` where you ran `/pb:data`.\n\n"


def main():
    s = Scratch()
    try:
        s.git("init", "-q")
        s.release("1.2.0", 2, ["build", "data", "check-drift"], LOG_13.replace("## [1.3.0]", "## [0.0.0]"))
        s.release("1.3.0", 3, ["build", "data"], LOG_13)
        s.release("2.0.0", 4, ["build"], LOG_20, tag=False)

        # 1 · the gate names everything missing
        rc, out = s.run("check")
        check(rc == 1, "check fails before the guide is written")
        check("docs/migrations/v2.0.0.md is missing" in out, "check names the missing guide")
        check("needs a `### Upgrading` subsection" in out and "it is a major" in out
              and "schema moves 3 → 4" in out and "`/pb:data`" in out,
              "check asks for `### Upgrading`, giving all three reasons")
        check("no replacement for `/pb:check-drift`, `/pb:data`" in out, "check names retired commands with no replacement")

        # 2 · supplied, written, green
        s.write("changelog.md", LOG_20.replace(").\n\n", ").\n\n" + UPGRADING, 1))
        s.write("docs/migrations/retired-commands.json",
                json.dumps({"data": "`/pb:build`", "check-drift": "nothing — it is gone"}))
        rc, out = s.run("write")
        check(rc == 0, "write succeeds")
        rc, out = s.run("check")
        check(rc == 0, f"check passes once written (got: {out.strip()[-160:]})")

        # 3 · the guide says what history says
        g = s.read("docs/migrations/v2.0.0.md")
        check("**Kind** major over v1.3.0" in g, "states the kind of release")
        check("| v1.3.0 | 3 → 4 | 1 (0002) | `/pb:data` |" in g, "v1.3.0 row: one schema step, `/pb:data` gone")
        check("| v1.2.0 | 2 → 4 | 2 (0001–0002) | `/pb:check-drift`, `/pb:data` |" in g, "v1.2.0 row: two steps, both commands gone")
        check("| `/pb:check-drift` | v1.3.0 | nothing — it is gone |" in g, "`/pb:check-drift` retired at v1.3.0")
        check("| `/pb:data` | v2.0.0 | `/pb:build` |" in g, "`/pb:data` retired at v2.0.0, with its replacement")
        check("| 0002 | 3 → 4 | v2.0.0 | schema 3 → 4: step 0002 |" in g, "schema step with describe() and its release")
        check("#### Upgrading\n\nRun `/pb:build` where you ran `/pb:data`." in g, "carries this release's upgrade notes")
        check("#### Removed\n\n- `/pb:check-drift`" in g and "[v1.3.0](#notes-v130)" in g,
              "carries an earlier release's Removed notes, linked from the rows that cross it")
        check("## 7 · What changed in v2.0.0\n\n- The big one." in g, "ends with the release's changelog")
        check("[AGENTS.md](../../AGENTS.md)" in g, "root-relative changelog links are rebased to the guide's folder")
        check("- [v2.0.0](v2.0.0.md)" in s.read("docs/migrations/README.md"), "the index lists the guide")

        # 4 · a later changelog edit is caught
        s.write("changelog.md", s.read("changelog.md").replace("The big one.", "The big one, reworded."))
        rc, out = s.run("check")
        check(rc == 1 and "v2.0.0.md is out of date" in out, "check fails when the guide is stale")
        s.run("write")

        # 5 · a plain patch needs no hand-written notes
        s.git("add", "-A"); s.git("commit", "-qm", "release: v2.0.0"); s.git("tag", "v2.0.0")
        s.release("2.0.1", 4, ["build"], "# Changelog\n\n## [2.0.1] — 2026-02-02\n\n- Fixed.\n\n"
                  + s.read("changelog.md").split("\n", 2)[2], tag=False)
        s.run("write")
        rc, out = s.run("check")
        check(rc == 0 and "`### Upgrading` required" not in out, f"a patch passes without `### Upgrading` ({out.strip()[-120:]})")
        g = s.read("docs/migrations/v2.0.1.md")
        check("| v2.0.0 | 4 (current) | none | none |" in g, "patch guide: nothing to do from v2.0.0")
        check("v2.0.1" in s.read("docs/migrations/README.md") and "v2.0.0" in s.read("docs/migrations/README.md"),
              "the index keeps earlier guides")

        # 6 · tagged → frozen
        s.git("add", "-A"); s.git("commit", "-qm", "release: v2.0.1"); s.git("tag", "v2.0.1")
        s.write("changelog.md", s.read("changelog.md").replace("- Fixed.", "- Fixed, later."))
        before = s.read("docs/migrations/v2.0.1.md")
        rc, out = s.run("check")
        check(rc == 0 and "already released" in out, "a released version's check passes untouched")
        s.run("write")
        check(s.read("docs/migrations/v2.0.1.md") == before, "write leaves a shipped guide alone")

        # 7 · release links
        env = dict(os.environ, GITHUB_REPOSITORY="acme/tool")
        r = subprocess.run([sys.executable, SCRIPT, "print", "--release", "--root", s.dir],
                           capture_output=True, text=True, env=env)
        check(r.returncode == 0 and "](https://github.com/acme/tool/blob/v2.0.1/docs/upgrading.md)" in r.stdout,
              "print --release points relative links at the tag")
        check(r.stdout.startswith("## Migrating"), "print --release demotes the title under the release heading")
    finally:
        shutil.rmtree(s.dir, ignore_errors=True)

    print(f"--- {len(_fail)} failure(s) ---")
    sys.exit(1 if _fail else 0)


if __name__ == "__main__":
    main()
