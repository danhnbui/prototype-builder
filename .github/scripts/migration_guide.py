#!/usr/bin/env python3
"""
migration_guide.py — the migration guide every release ships (.github/workflows/pipeline.yml).

Writes docs/migrations/v<version>.md: how to get to this release from ANY earlier one. Most of it
is derived, so it cannot drift from what actually ships:

  the version you are on      every vX.Y.Z tag merged into HEAD (from v1.2.0, the first with commands)
  registry schema steps       CURRENT_SCHEMA at each tag (pb/migrations/manifest.py) → the chain of
                              migrations /pb:update-version will run, each with its describe()
  retired commands            pb/commands/ at each tag vs now, mapped to what to run instead by
                              docs/migrations/retired-commands.json
  what changed                this release's changelog.md section, verbatim

The one part a person writes is the `### Upgrading` subsection of the release's changelog section:
what a user has to DO that no tool does for them. `check` requires one whenever the release is a
major, changes the registry schema, or removes a command. Earlier releases' `### Upgrading`,
`### Breaking…` and `### Removed…` subsections are carried into the guide for anyone crossing them.

Like the version bump, the guide lands IN THE PR: `bump_version.py auto` runs `write` after it
stamps, and the bump-version check runs `check`. release-tag puts the committed file in the draft
release's notes (`print --release`) and attaches it as MIGRATION-v<version>.md.

Usage:  python3 .github/scripts/migration_guide.py write|check|print [--release] [--root DIR]
  write    regenerate docs/migrations/v<current>.md and docs/migrations/README.md
  check    read-only. For an unreleased version: the changelog has its section, `### Upgrading` is
           there when the release needs one, every retired command has a replacement, and both
           files match what `write` would produce. An already-tagged version passes untouched —
           a shipped guide is frozen.
  print    the committed guide on stdout; --release turns its relative links into links at the tag
Exit:   0 = ok · 1 = a check failed or bad input
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = ".claude-plugin/plugin.json"
GUIDES = "docs/migrations"
RETIRED_FILE = GUIDES + "/retired-commands.json"
FLOOR = (1, 2, 0)                       # first release that shipped pb/commands/
UNSTAMPED_SCHEMA = 2                    # migrate_runner.py: a registry with no schemaVersion is 2
FIX_HINT = "python3 .github/scripts/migration_guide.py write"

SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SECTION = re.compile(r"^## \[(\d+\.\d+\.\d+)\](.*)$", re.M)
SUBSECTION = re.compile(r"^### .*$", re.M)
UPGRADING = re.compile(r"^### Upgrading\b", re.I)
CARRIED = re.compile(r"^### (Upgrading\b|Breaking\b|Removed\b|.*\bBREAKING\b)", re.I)
SCHEMA_LINE = re.compile(r"^CURRENT_SCHEMA\s*=\s*(\d+)", re.M)


def vt(v):
    m = SEMVER.match(v)
    if not m:
        sys.exit(f"::error::version {v!r} is not bare SemVer X.Y.Z")
    return tuple(int(g) for g in m.groups())


def vs(t):
    return "%d.%d.%d" % t


class Repo:
    def __init__(self, root):
        self.root = root

    def path(self, rel):
        return os.path.join(self.root, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as f:
            return f.read()

    def git(self, *args):
        r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def version(self):
        v = json.loads(self.read(SOURCE))["version"]
        vt(v)
        return v

    def tags(self):
        """Released versions in HEAD's history, oldest first."""
        out = self.git("tag", "--merged", "HEAD", "-l", "v[0-9]*.[0-9]*.[0-9]*") or ""
        vers = {vt(t) for t in out.split() if SEMVER.match(t)}
        return sorted(vers)

    def schema_at(self, tag):
        src = self.git("show", f"{tag}:pb/migrations/manifest.py")
        m = SCHEMA_LINE.search(src or "")
        return int(m.group(1)) if m else UNSTAMPED_SCHEMA

    def schema_now(self):
        return int(SCHEMA_LINE.search(self.read("pb/migrations/manifest.py")).group(1))

    def commands_at(self, tag):
        out = self.git("ls-tree", "--name-only", f"{tag}:pb/commands") or ""
        return {n[:-3] for n in out.split() if n.endswith(".md")}

    def commands_now(self):
        d = self.path("pb/commands")
        return {n[:-3] for n in os.listdir(d) if n.endswith(".md")}

    def migrations(self):
        """[(FROM, TO, number, describe, memory_notes)] for the whole chain, from manifest.py."""
        mdir = self.path("pb/migrations")
        spec = importlib.util.spec_from_file_location("pb_manifest", os.path.join(mdir, "manifest.py"))
        manifest = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manifest)
        out = []
        for f, t, stem in manifest._REGISTRY:
            mod = manifest._load(stem)
            notes = getattr(mod, "memory_notes", None)
            out.append((f, t, stem.split("_", 1)[0], mod.describe(), notes() if notes else None))
        return out

    def retired(self):
        p = self.path(RETIRED_FILE)
        if not os.path.exists(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def changelog_sections(text):
    """{version: (heading rest, body)} — only bracketed SemVer headings; [Unreleased] is not one."""
    heads = list(re.finditer(r"^## .*$", text, re.M))
    out = {}
    for i, h in enumerate(heads):
        m = SECTION.match(h.group(0))
        if not m:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.setdefault(m.group(1), (m.group(2).strip(" —-"), text[h.end():end].strip("\n")))
    return out


def subsections(body, pattern):
    """[(heading text, content)] for each ### subsection whose heading matches pattern."""
    heads = list(SUBSECTION.finditer(body))
    out = []
    for i, h in enumerate(heads):
        if pattern.match(h.group(0)):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            out.append((h.group(0)[4:].strip(), body[h.end():end].strip("\n")))
    return out


def rebase(text):
    """Changelog text is written from the repo root; the guide sits two folders down."""
    return re.sub(r"\]\((?!https?:|mailto:|#|/|\.\./)([^)\s]+)\)", r"](../../\1)", text)


def kind(prev, cur):
    if prev is None:
        return "first release"
    if cur[0] != prev[0]:
        return "major"
    return "minor" if cur[1] != prev[1] else "patch"


def cmds(names):
    return ", ".join(f"`/pb:{n}`" for n in sorted(names)) if names else "none"


def facts(repo):
    """Everything the guide and the check are built from, for the version in the tree."""
    cur_s = repo.version()
    cur = vt(cur_s)
    all_tags = repo.tags()
    tags = [t for t in all_tags if t < cur]
    prev = tags[-1] if tags else None
    now_schema, now_cmds = repo.schema_now(), repo.commands_now()
    listed = [t for t in tags if t >= FLOOR]
    at = {t: {"schema": repo.schema_at("v" + vs(t)), "commands": repo.commands_at("v" + vs(t))}
          for t in set(listed) | ({prev} if prev else set())}
    schema_of = {**{t: at[t]["schema"] for t in listed}, cur: now_schema}
    gone = {}                            # retired command -> the first release without it
    timeline = listed + [cur]
    for name in set().union(set(), *(at[t]["commands"] for t in listed)) - now_cmds:
        last = max(t for t in listed if name in at[t]["commands"])
        gone[name] = next(t for t in timeline if t > last)
    return {
        "cur": cur, "cur_s": cur_s, "released": cur in all_tags, "prev": prev, "tags": tags,
        "sections": changelog_sections(repo.read("changelog.md")), "schema": now_schema,
        "commands": now_cmds, "listed": listed, "at": at, "schema_of": schema_of, "gone": gone,
        "retired_map": repo.retired(), "migrations": repo.migrations(),
        "prev_schema": at[prev]["schema"] if prev else None,
        "prev_cmds": at[prev]["commands"] if prev else set(),
    }


def render(F, repo):
    cur, cur_s = F["cur"], F["cur_s"]
    date, body = F["sections"].get(cur_s, ("", ""))
    prev = F["prev"]
    k = kind(prev, cur)
    L = []
    w = L.append

    w(f"# Migrating to Product Builder v{cur_s}")
    w("")
    w("<!-- Generated by .github/scripts/migration_guide.py — do not edit. Edit changelog.md "
      "(its `### Upgrading` subsection) and run `python3 .github/scripts/migration_guide.py write`. -->")
    w("")
    meta = [f"**Release** v{cur_s}" + (f" · {date}" if date else ""),
            f"**Registry schema** {F['schema']}",
            f"**Kind** {k}" + (f" over v{vs(prev)}" if prev else "")]
    w(" · ".join(meta))
    w("")
    w("This page gets a project from **any earlier release** to v" + cur_s + ". Find your version in the "
      "table, follow the five steps, and read the notes for every release your row says you cross.")
    w("")

    # ── find your version ──
    w("## 1 · Find the version you are on")
    w("")
    w("- **Plugin:** the `pb vX.Y.Z` badge in the prototype's meta-nav, the `· pb vX.Y.Z` line in the "
      "`/pb:preview` banner, or the first line of `prototype.html` (`<!-- pb-shell vX.Y.Z · rendered … -->`).")
    w("- **Registry:** `meta.schemaVersion` in your `registry.json`. No field means schema "
      f"{UNSTAMPED_SCHEMA}.")
    w("")

    # ── from-table ──
    w("## 2 · What your upgrade crosses")
    w("")
    w("| You are on | Registry schema | Schema steps `/pb:update-version` runs | Commands that are gone | Read before upgrading |")
    w("|---|---|---|---|---|")
    notes_for, groups = {}, []
    for t in reversed(F["listed"]):       # newest first; neighbours with the same outcome merge
        removed = tuple(sorted(F["at"][t]["commands"] - F["commands"]))
        reads = []
        for v in F["tags"] + [cur]:
            vstr = vs(v)
            subs = subsections(F["sections"].get(vstr, ("", ""))[1], CARRIED) if v > t else None
            if subs:
                notes_for[vstr] = subs
                reads.append(f"[v{vstr}](#notes-v{vstr.replace('.', '')})")
        key = (F["at"][t]["schema"], removed, tuple(reads))
        if groups and groups[-1]["key"] == key:
            groups[-1]["low"] = t
        else:
            groups.append({"key": key, "high": t, "low": t})
    for g in groups:
        sch, removed, reads = g["key"]
        steps = [m for m in F["migrations"] if sch <= m[0] and m[1] <= F["schema"]]
        step_txt = ("none" if not steps else f"1 ({steps[0][2]})" if len(steps) == 1
                    else f"{len(steps)} ({steps[0][2]}–{steps[-1][2]})")
        schema_txt = f"{sch} → {F['schema']}" if sch != F["schema"] else f"{sch} (current)"
        span = f"v{vs(g['high'])}" if g["low"] == g["high"] else f"v{vs(g['low'])} – v{vs(g['high'])}"
        gone_txt = cmds(removed) if len(removed) <= 3 else f"{len(removed)} — see section 6"
        w(f"| {span} | {schema_txt} | {step_txt} | {gone_txt} | {', '.join(reads) or '—'} |")
    w(f"| older than v{vs(FLOOR)} | unstamped → {F['schema']} | every step in section 5 | — | every note in section 4 |")
    w("")
    w("*Registry schema* is what that release wrote. If you skipped `/pb:update-version` back then, your "
      "registry is older; the dry run in step 3 reads the real value and plans from it.")
    w("")

    # ── steps ──
    w("## 3 · Upgrade, in this order")
    w("")
    w("1. **Update the plugin.** `/plugin marketplace update product-builder`, then **restart Claude Code** "
      "so the new commands load. If a same-name marketplace blocks it: uninstall the plugin → remove the "
      "marketplace → add the source again → install.")
    w("2. **Read the notes your row links to** (section 4) and do what they say — renamed commands, changed "
      "defaults, anything no tool does for you. Replace any command your row lists as gone (section 6).")
    w("3. **Bring the registry to schema " + str(F["schema"]) + ".** `/pb:update-version` (a dry run: it "
      "prints the plan and writes nothing), then `/pb:update-version --apply`. It backs up `registry.json` "
      "first. Skip this when your row says *none*.")
    w("4. **Re-render.** `/pb:build --render`, or restart `/pb:preview`. Until you do, `prototype.html` "
      "keeps showing the old shell.")
    w(f"5. **Check it worked.** The badge reads `pb v{cur_s}`; `/pb:test --drift` reports no shell drift; "
      "`/pb:test` runs clean.")
    w("")
    w("**If something goes wrong:** `/pb:update-version --rollback` restores the registry from the backup "
      "step 3 took. It is a file restore, so use it before you build on top; after that, "
      "`/pb:update-version --to <N>` runs the real reverse migrations. Background on the three version "
      "layers: [upgrading.md](../upgrading.md).")
    w("")

    # ── carried notes ──
    w("## 4 · Notes for the releases you cross")
    w("")
    if not notes_for:
        w("No release since v" + vs(FLOOR) + " carries upgrade notes.")
        w("")
    for vstr in sorted(notes_for, key=vt, reverse=True):
        w(f'<a id="notes-v{vstr.replace(".", "")}"></a>')
        w("")
        w(f"### v{vstr}")
        w("")
        for head, content in notes_for[vstr]:
            w(f"#### {head}")
            w("")
            w(rebase(content))
            w("")
        doc = f"docs/upgrade-to-{vt(vstr)[0]}.0.md"
        if vt(vstr)[1:] == (0, 0) and os.path.exists(repo.path(doc)):
            w(f"Full walkthrough: [{os.path.basename(doc)}](../{os.path.basename(doc)}).")
            w("")

    # ── schema steps ──
    w("## 5 · Registry schema steps")
    w("")
    w("`/pb:update-version` runs, in order, every step after your registry's schema. Each is one "
      "migration in `pb/migrations/`.")
    w("")
    w("| Step | Schema | Since | What it does |")
    w("|---|---|---|---|")
    for f, t, num, desc, _ in F["migrations"]:
        since = next((v for v in sorted(F["schema_of"]) if F["schema_of"][v] >= t), None)
        w(f"| {num} | {f} → {t} | {('v' + vs(since)) if since else '—'} | {desc.replace('|', '/')} |")
    w("")
    manual = [(num, n) for f, t, num, _, n in F["migrations"] if n]
    if manual:
        w("<details><summary>Hand-applied notes some steps print at <code>--apply</code> (for "
          "<code>memory/constitution.md</code>, never written for you)</summary>")
        w("")
        for num, n in manual:
            w(f"- **{num}** — " + n.strip().replace("\n", "\n  "))
        w("")
        w("</details>")
        w("")

    # ── retired commands ──
    w("## 6 · Retired commands")
    w("")
    if not F["gone"]:
        w("No command has been retired.")
    else:
        w("An old name is gone, not redirected: running it reports that no such command exists.")
        w("")
        w("| Retired | Gone since | Run instead |")
        w("|---|---|---|")
        for name in sorted(F["gone"], key=lambda n: (F["gone"][n], n)):
            w(f"| `/pb:{name}` | v{vs(F['gone'][name])} | {F['retired_map'].get(name, '*(missing)*')} |")
    w("")

    # ── changelog ──
    w(f"## 7 · What changed in v{cur_s}")
    w("")
    w(rebase(body) if body else "*No changelog entry.*")
    w("")
    return "\n".join(L)


def render_index(repo, cur_s):
    d = repo.path(GUIDES)
    vers = {f[1:-3] for f in os.listdir(d) if SEMVER.match(f[:-3] if f.endswith(".md") else "x")} \
        if os.path.isdir(d) else set()
    vers.add(cur_s)
    L = ["# Migration guides", "",
         "<!-- Generated by .github/scripts/migration_guide.py — do not edit. -->", "",
         "One guide per release. Each covers the upgrade from **every** earlier release, so open the one "
         "for the version you are moving to — normally the newest.", ""]
    for v in sorted(vers, key=vt, reverse=True):
        L.append(f"- [v{v}](v{v}.md)")
    L += ["", "How they are made: `.github/scripts/migration_guide.py`. What to run instead of a retired "
          "command lives in [retired-commands.json](retired-commands.json).", ""]
    return "\n".join(L)


def outputs(repo):
    F = facts(repo)
    return F, {f"{GUIDES}/v{F['cur_s']}.md": render(F, repo), f"{GUIDES}/README.md": render_index(repo, F["cur_s"])}


def cmd_write(repo):
    F, files = outputs(repo)
    if F["released"]:
        print(f"v{F['cur_s']} is already released — its guide is frozen; writing it only if missing")
        files = {p: c for p, c in files.items() if not os.path.exists(repo.path(p))}
    os.makedirs(repo.path(GUIDES), exist_ok=True)
    for rel, text in files.items():
        with open(repo.path(rel), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  wrote {rel}")


def cmd_check(repo):
    F, files = outputs(repo)
    v = F["cur_s"]
    if F["released"]:
        print(f"v{v} is already released — nothing to check (a shipped guide is frozen)")
        return
    errs = []
    sec = F["sections"].get(v)
    if not sec:
        errs.append(f"changelog.md has no `## [{v}]` section — write the release's changelog "
                    f"(a leading `## [Unreleased]` is renamed by bump_version.py)")
    reasons = []
    if F["prev"] and kind(F["prev"], F["cur"]) == "major":
        reasons.append("it is a major")
    if F["prev_schema"] is not None and F["schema"] != F["prev_schema"]:
        reasons.append(f"the registry schema moves {F['prev_schema']} → {F['schema']}")
    gone = F["prev_cmds"] - F["commands"]
    if gone:
        reasons.append(f"it removes {cmds(gone)}")
    if sec and reasons and not subsections(sec[1], UPGRADING):
        errs.append(f"v{v} needs a `### Upgrading` subsection in its changelog section because "
                    f"{' and '.join(reasons)} — say what a user must do that no tool does for them")
    missing = sorted(n for n in F["gone"] if n not in F["retired_map"])
    if missing:
        errs.append(f"{RETIRED_FILE} has no replacement for {cmds(missing)} — add "
                    f'"<name>": "what to run instead"')
    for rel, text in files.items():
        p = repo.path(rel)
        have = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        if have != text:
            errs.append(f"{rel} is {'missing' if have is None else 'out of date'} — run `{FIX_HINT}` "
                        f"and commit the result")
    print(f"v{v} · schema {F['schema']} · {kind(F['prev'], F['cur'])}"
          + (f" over v{vs(F['prev'])}" if F["prev"] else "")
          + (f" · `### Upgrading` required: {', '.join(reasons)}" if reasons else ""))
    if errs:
        for e in errs:
            print(f"::error::{e}")
        sys.exit(1)
    print(f"migration guide for v{v} is present and current")


def cmd_print(repo, release):
    v = repo.version()
    rel = f"{GUIDES}/v{v}.md"
    if not os.path.exists(repo.path(rel)):
        sys.exit(f"::error::{rel} is missing — run `{FIX_HINT}`")
    text = repo.read(rel)
    if release:
        slug = os.environ.get("GITHUB_REPOSITORY")
        if slug:
            base = f"https://github.com/{slug}/blob/v{v}/"
            text = re.sub(r"\]\(\.\./\.\./([^)#\s]+)", lambda m: f"]({base}{m.group(1)}", text)
            text = re.sub(r"\]\(\.\./([^)#\s]+)", lambda m: f"]({base}docs/{m.group(1)}", text)
            text = re.sub(r"\]\((?!https?:|#|\.\./)([^)\s]+\.(?:md|json))", lambda m: f"]({base}{GUIDES}/{m.group(1)}", text)
        text = re.sub(r"^# ", "## ", text, count=1, flags=re.M)
    sys.stdout.write(text)


def main():
    ap = argparse.ArgumentParser(description="Write, check or print the release's migration guide.")
    ap.add_argument("mode", choices=["write", "check", "print"])
    ap.add_argument("--release", action="store_true", help="print: absolute links at the release tag")
    ap.add_argument("--root", default=ROOT, help="repo root (tests point this at a scratch repo)")
    a = ap.parse_args()
    repo = Repo(os.path.abspath(a.root))
    if a.mode == "write":
        cmd_write(repo)
    elif a.mode == "check":
        cmd_check(repo)
    else:
        cmd_print(repo, a.release)


if __name__ == "__main__":
    main()
