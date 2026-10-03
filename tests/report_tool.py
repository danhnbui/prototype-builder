#!/usr/bin/env python3
"""
report_tool.py — /pb:report's fact gatherer (pb/tools/report.py).

The facts file is what the model reads before it proposes anything to the maintainer, so a wrong
count becomes a wrong proposal. These are the properties that make it trustworthy:

  1. it runs, exits 0, and writes every section heading in the fixed order — `(none)` when empty
  2. it scans a project whose folder name contains `[x]`. `glob.glob` reads `[x]` as a character
     class and matches nothing; that bug left a real project's logic checks passing over zero
     bodies. A body count of 0 here is that bug coming back
  3. the decisions log is parsed by entry: six entries, one undated, the template example inside
     an HTML comment not counted, a `revert` found, a heading repeated three times found
  4. a retired command named in memory is flagged with its replacement; a hand-written memory
     file no command owns is listed
  5. `--json` is valid JSON with the same facts
  6. session transcripts give counts and sequences, and never a word of the messages
  7. READ-ONLY: the project tree hashes the same before and after every run; `--out` outside the
     project creates its own parent and nothing else
  8. no registry.json → exit 2

Usage: python3 tests/report_tool.py · Exit 0/1.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "pb", "tools", "report.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")
_spec = importlib.util.spec_from_file_location("report", TOOL)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def tree_hash(root):
    h = hashlib.sha256()
    for cur, dirs, files in os.walk(root):
        dirs.sort()
        h.update(("D " + os.path.relpath(cur, root) + "\n").encode())
        for f in sorted(files):
            p = os.path.join(cur, f)
            h.update(("F " + os.path.relpath(p, root) + "\n").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def run(*args):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True)


RETIRED = "/pb:" + "check-drift"         # split so tests/command_refs.py does not count a mention here

DECISIONS = """# Decisions — fixture

> The house note. It names a gate override and decisions_rotate.py, as the template does.

<!-- Template entry — copy below this line:

## YYYY-MM-DD — <short title>
- **Decision:** <what was chosen>

-->

## 2026-09-05 — Home action row: shorter labels
- **Decision:** shorter labels
- **Alternatives:** —
- **Rule:** home-labels

## 2026-09-04 — The onboarding carousel is reverted
- **Decision:** reverted to the brief after the owner asked again
- **Alternatives:** keep the new carousel (rejected — off-brief)

## 2026-09-03 — Home action row moves into the page
- **Decision:** moved

## 2026-09-02 — Drift pass
- **Decision:** ran %s and fixed three contradictions

## 2026-09-01 — Home action row icons in discs
- **Decision:** discs

## Notes without a date
- **Decision:** something nobody dated
""" % RETIRED

MANIFEST = {
    "version": 1, "target": "login-card", "kind": "component", "mode": "target", "host": "login",
    "intent": "", "createdAt": "2026-09-03T10:00:00", "status": "open", "baseline": {},
    "options": [{"slot": "opt-1"}, {"slot": "opt-2"}],
    "rubric": [{"id": "hierarchy"}, {"id": "ship"}],
    "scores": {"hierarchy:opt-1": 4, "ship:opt-1": 3}, "notes": {}, "verdict": {"pick": None},
}

SESSION = [
    {"type": "user", "timestamp": "2026-09-02T09:00:00Z", "origin": {"kind": "human"},
     "message": {"role": "user", "content": [{"type": "text", "text": "SECRET-PROMPT-TEXT make the card bigger"}]}},
    {"type": "user", "timestamp": "2026-09-02T09:01:00Z", "origin": {"kind": "human"},
     "message": {"role": "user", "content": "<command-name>/pb:build</command-name>\n<command-args>--render SECRET-ARG-TEXT</command-args>"}},
    {"type": "assistant", "timestamp": "2026-09-02T09:02:00Z",
     "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash",
                 "input": {"command": "touch registry.json && python3 pb/tools/render.py registry.json a b"}}]}},
    {"type": "user", "timestamp": "2026-09-02T09:03:00Z", "origin": {"kind": "human"},
     "message": {"role": "user", "content": [{"type": "text", "text": "SECRET-SECOND-PROMPT"}]}},
    {"type": "assistant", "timestamp": "2026-09-02T09:04:00Z",
     "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill",
                 "input": {"skill": "pb:build", "args": "SECRET-SKILL-ARGS --render"}}]}},
    {"type": "user", "timestamp": "2026-09-02T09:05:00Z", "isSidechain": True,
     "message": {"role": "user", "content": "<command-name>/pb:test</command-name>"}},
]

base = tempfile.mkdtemp()
try:
    proj = os.path.join(base, "proj [x]")
    shutil.copytree(GOLDEN, proj)
    write(os.path.join(proj, "memory", "decisions.md"), DECISIONS)
    write(os.path.join(proj, "memory", "constitution.md"), "# Constitution\n")
    write(os.path.join(proj, "memory", "hand-notes.md"), "# Notes the project wrote itself\n")
    write(os.path.join(proj, "memory", "explore", "login-card.json"), json.dumps(MANIFEST))
    for b in ("2026-09-01-pre-a", "2026-09-02-pre-b"):
        write(os.path.join(proj, "memory", "backups", b, "registry.json"), "{}\n")
    sess = os.path.join(base, "sessions")
    write(os.path.join(sess, "s1.jsonl"), "\n".join(json.dumps(o) for o in SESSION) + "\n")
    before = tree_hash(proj)
    out = os.path.join(base, "out", "nested", "report.md")

    print("1 · it runs and writes every section, in order")
    p = run("--project", proj, "--out", out)
    check(p.returncode == 0, "exits 0 (%d%s)" % (p.returncode, (": " + p.stderr.strip()[-200:]) if p.returncode else ""))
    check(os.path.isfile(out), "the out file exists, and its missing parent was created")
    md = open(out, encoding="utf-8").read() if os.path.isfile(out) else ""
    pos = [md.find("\n## " + title + "\n") for _k, title in R.SECTIONS]
    check(all(i >= 0 for i in pos), "all %d section headings are present" % len(R.SECTIONS))
    check(pos == sorted(pos), "and in the fixed order")
    check("## 8 · Sessions\n\n(none)" in md, "an empty section says (none) — sessions were not requested")

    print("2 · a folder named `[x]` is scanned")
    p = run("--project", proj, "--out", out, "--json")
    try:
        facts = json.loads(p.stdout)
    except ValueError:
        facts = {}
    check(bool(facts), "--json prints valid JSON")
    shape = facts.get("shape", {})
    check(shape.get("renderBodies", 0) > 0, "render bodies found under the bracket path (%s)" % shape.get("renderBodies"))
    check(facts.get("hygiene", {}).get("bodiesScanned", 0) > 0, "and the hygiene scan read them too")

    print("3 · the decisions log is parsed by entry")
    d = facts.get("decisions", {})
    check(d.get("entries") == 6, "six entries — the template example inside <!-- --> is not one (%s)" % d.get("entries"))
    check(d.get("undated") == 1, "one undated entry (%s)" % d.get("undated"))
    vocab = {v["term"]: v["entries"] for v in d.get("vocabulary", [])}
    check(vocab.get("revert") == 1, "the revert is found (%s)" % vocab.get("revert"))
    topics = {t["topic"]: t["entries"] for t in d.get("recurringTopics", [])}
    check(topics.get("home action row") == 3, "the heading repeated three times is a recurring topic (%s)" % topics)
    check(d.get("alternatives", {}).get("empty") == 1, "an `Alternatives: —` counts as empty")

    print("4 · retired commands and hand-written files are flagged")
    cmds = {c["name"]: c for c in facts.get("mentions", {}).get("commands", [])}
    hit = cmds.get(RETIRED[4:], {})
    check(hit.get("status") == "retired" and hit.get("replacement") == "/pb:test --drift",
          "the retired command is flagged with its replacement (%s)" % hit.get("status"))
    check("**retired**" in md and RETIRED in md, "and the markdown shows it")
    check("hand-notes.md" in shape.get("handWritten", []), "memory/hand-notes.md is listed as hand-written")
    check("constitution.md" not in shape.get("handWritten", []), "a template-owned file is not")
    notices = {n["notice"]: n["lines"] for n in facts.get("mentions", {}).get("notices", [])}
    check(notices.get("gate override") == 0, "the log's house note is not counted as a gate override")

    print("5 · explore and backups")
    e = facts.get("explore", {})
    check(len(e.get("rounds", [])) == 1 and e.get("unscored") == 2, "one open round, 2 of 4 cells unscored")
    b = facts.get("backups", {})
    check(b.get("snapshots") == 2 and len(b.get("pre", [])) == 2, "two pre-* backups")

    print("6 · sessions: counts and sequences, never the messages")
    sout = os.path.join(base, "out", "sessions.md")
    p = run("--project", proj, "--out", sout, "--sessions", sess, "--json")
    try:
        sfacts = json.loads(p.stdout).get("sessions", {})
    except ValueError:
        sfacts = {}
    smd = open(sout, encoding="utf-8").read() if os.path.isfile(sout) else ""
    runs = {c["name"]: c for c in sfacts.get("commands", [])}
    check(sfacts.get("scanned") is True, "the transcript folder is scanned")
    check(runs.get("build", {}).get("typed") == 1 and runs.get("build", {}).get("invoked") == 1,
          "one typed and one model-invoked /pb:build")
    check("test" not in runs, "a sidechain line is not a run")
    check(sfacts.get("touchRegistry") == 1, "the `touch registry.json` ritual is counted")
    check(sfacts.get("turnsBetweenBuilds", {}).get("pairs") == 1, "one build → build pair")
    check("SECRET" not in smd and "SECRET" not in p.stdout, "no message text reaches the report or the JSON")
    check("scanned with `--sessions`" in smd, "the report says the sessions were scanned")

    print("7 · read-only on the project")
    check(tree_hash(proj) == before, "the project tree hashes the same after every run")
    check(sorted(os.listdir(os.path.join(base, "out"))) == ["nested", "sessions.md"],
          "only the --out files were created outside it")

    print("8 · no registry.json")
    empty = os.path.join(base, "empty [y]")
    os.makedirs(empty)
    p = run("--project", empty, "--out", os.path.join(base, "x.md"))
    check(p.returncode == 2 and not os.path.exists(os.path.join(base, "x.md")), "exits 2 and writes nothing")
finally:
    shutil.rmtree(base, ignore_errors=True)

print()
if fails:
    print("FAIL — %d check(s)" % len(fails))
    sys.exit(1)
print("PASS — report.py gathers the facts read-only, on a bracket path, without quoting a session")
