#!/usr/bin/env python3
"""
update_version_report.py — /pb:update-version says what the PLUGIN changed, not only the schema.

Most releases (2.2 → 2.6) change no schema, so the old runner answered "Already on schema 13.
Nothing to do." to a project that was several releases behind. The runner now also reports the
installed plugin version against the one the project was last brought to, lists the changelog
entries in between, and names the steps no tool does. `--apply` records `meta.pbVersion`.

  1. A project last brought to an older release: the dry run names both versions, lists every release
     in between from the changelog, and the by-hand steps. It writes nothing.
  2. With no meta.pbVersion it falls back to the prototype.html stamp, and says that is where it looked.
  3. With no record at all it says so, instead of guessing an old version.
  4. A project already on the installed version prints one line and no by-hand steps.
  5. `--apply` on a current schema writes meta.pbVersion (and nothing else), keeps a backup, and a second
     `--apply` writes nothing.
  6. A schema that does need a step still prints the report, and --apply stamps pbVersion after the chain.
  7. The changelog the plugin ships (pb/docs/changelog.md) is the repository's changelog.md, and has an
     entry for the installed version.

Usage:  python3 tests/update_version_report.py
Exit:   0 = clean · 1 = a failure
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "pb", "migrations", "migrate_runner.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
PLUGIN = os.path.join(ROOT, "pb", ".claude-plugin", "plugin.json")

_fail = []


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        _fail.append(msg)


sys.path.insert(0, os.path.join(ROOT, "pb", "migrations"))
import manifest  # noqa: E402

INSTALLED = json.load(open(PLUGIN, encoding="utf-8"))["version"]
CURRENT = manifest.CURRENT_SCHEMA


def run(*args):
    r = subprocess.run([sys.executable, RUNNER] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def project(d, name, pb_version=None, stamp=None, schema=CURRENT):
    p = os.path.join(d, name)
    os.mkdir(p)
    reg = json.load(open(TEMPLATE, encoding="utf-8"))
    reg.setdefault("meta", {})["schemaVersion"] = schema
    if pb_version is not None:
        reg["meta"]["pbVersion"] = pb_version
    else:
        reg["meta"].pop("pbVersion", None)
    path = os.path.join(p, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    if stamp is not None:
        with open(os.path.join(p, "prototype.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n<!-- pb-shell v%s · rendered 2026-01-01T00:00:00Z -->\n<html></html>\n" % stamp)
    return p, path


def snapshot(p):
    # registry.json.lock is the advisory lock any --apply leaves behind; it is not project content
    return {n: open(os.path.join(p, n), "rb").read() for n in sorted(os.listdir(p))
            if os.path.isfile(os.path.join(p, n)) and not n.endswith(".lock")}


with tempfile.TemporaryDirectory() as d:
    # 1 · behind by pbVersion
    p, reg = project(d, "behind", pb_version="2.4.0")
    before, listing = snapshot(p), sorted(os.listdir(p))
    rc, out = run(reg)
    check(rc == 0, "dry run on a project at v2.4.0 exits 0")
    check("v%s is installed" % INSTALLED in out and "v2.4.0" in out and "meta.pbVersion" in out,
          "…names the installed version, the recorded one and where it came from")
    check("v2.5.0" in out and "v2.6.0" in out and "v2.4.0 ·" not in out,
          "…lists the releases after 2.4.0 up to the installed one (not 2.4.0 itself)")
    check("Restart Claude Code" in out and "/pb:preview" in out and "agents_install.py" in out,
          "…and the steps no tool does")
    check("No schema update needed" in out or "Already on schema" in out, "…and still says the schema is current")
    check(snapshot(p) == before and sorted(os.listdir(p)) == listing, "…and writes nothing")

    # 2 · fallback to the stamp
    p, reg = project(d, "stamped", stamp="2.5.0")
    rc, out = run(reg)
    check("v2.5.0" in out and "prototype.html stamp" in out, "no meta.pbVersion → reads the prototype.html stamp and says so")

    # 3 · no record
    p, reg = project(d, "unknown")
    rc, out = run(reg)
    check("no record" in out and "What changed since" in out, "no record at all → says so, and lists the installed release")

    # 4 · already current
    p, reg = project(d, "current", pb_version=INSTALLED)
    rc, out = run(reg)
    check("last brought to v%s" % INSTALLED in out and "By hand" not in out, "already on the installed version → one line, no steps")
    before = snapshot(p)
    rc, out = run("--apply", reg)
    check(rc == 0 and snapshot(p) == before and not os.path.exists(os.path.join(p, ".pb-backups")),
          "…and --apply on it writes nothing and takes no backup")

    # 5 · apply on a current schema
    p, reg = project(d, "apply", pb_version="2.5.0")
    original = json.load(open(reg, encoding="utf-8"))
    rc, out = run("--apply", reg)
    after = json.load(open(reg, encoding="utf-8"))
    check(rc == 0 and after["meta"].get("pbVersion") == INSTALLED, "--apply records meta.pbVersion = the installed version")
    want = copy.deepcopy(original)
    want["meta"]["pbVersion"] = INSTALLED
    check(after == want, "…and changes nothing else in the registry")
    backups = [n for n in os.listdir(os.path.join(p, ".pb-backups")) if n.startswith("registry.")]
    check(len(backups) == 1, "…after keeping a backup of the registry as it was")
    rc, out = run("--apply", reg)
    check(len([n for n in os.listdir(os.path.join(p, ".pb-backups")) if n.startswith("registry.")]) == 1,
          "a second --apply writes nothing more")

    # 6 · a schema that needs a step
    if CURRENT > 2:
        p, reg = project(d, "migrate", pb_version="2.0.0", schema=CURRENT - 1)
        rc, out = run(reg)
        check("Version update plan" in out and "What changed since" in out, "a schema gap prints the plan and the release report")
        rc, out = run("--apply", reg)
        res = json.load(open(reg, encoding="utf-8"))
        check(rc == 0 and res["meta"]["schemaVersion"] == CURRENT and res["meta"].get("pbVersion") == INSTALLED,
              "…and --apply moves the schema and stamps pbVersion (exit %d)" % rc)

# 7 · the shipped changelog
repo = open(os.path.join(ROOT, "changelog.md"), encoding="utf-8").read()
shipped_path = os.path.join(ROOT, "pb", "docs", "changelog.md")
shipped = open(shipped_path, encoding="utf-8").read() if os.path.exists(shipped_path) else None
check(shipped == repo, "pb/docs/changelog.md is changelog.md (fix: cp changelog.md pb/docs/changelog.md)")
check(re.search(r"^## \[%s\]" % re.escape(INSTALLED), repo, re.M) is not None,
      "changelog.md has an entry for the installed version %s" % INSTALLED)

print("\n%s" % ("update_version_report: clean" if not _fail else "update_version_report: %d failure(s)" % len(_fail)))
sys.exit(1 if _fail else 0)
