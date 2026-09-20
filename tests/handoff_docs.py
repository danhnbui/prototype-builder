#!/usr/bin/env python3
"""
handoff_docs.py — the Markdown half of the engineering hand-off (/pb:handoff mode 2).

  1. It emits both files, and both are non-trivial Markdown.
  2. It is DETERMINISTIC — byte-identical across runs. This is the property the whole tool
     exists for: a hand-off regenerated next month has to diff cleanly against this one, so
     no timestamp, no set iteration order, nothing environmental.
  3. The authored half of a contract reaches the page — `writes[]` and `affordances[].why`
     are the two things no tool derives, so a doc that silently dropped them would be worse
     than no doc.
  4. A wide relation is CAPPED with a count, not dumped. One store slice on the reference
     project had 53 readers; an uncapped cell is not information.
  5. An empty `ia.rules` says so in words rather than rendering a blank section — absence of
     a declaration is a fact about the project, not a gap in the doc.

Self-contained: the fixture is built here, never read from a project. Exit 0/1.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import handoff_docs as HD  # noqa: E402

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def fixture(d):
    os.makedirs(os.path.join(d, "render", "components"), exist_ok=True)
    os.makedirs(os.path.join(d, "render", "screens"), exist_ok=True)
    os.makedirs(os.path.join(d, "logic", "components"), exist_ok=True)
    for rel, body in (
        ("render/components/badge.js",
         "function renderCmpBadge(p){ return '<b>'+pbEscape(p.text||'')+'</b>'; }\n"),
        ("render/screens/home.js",
         "function renderScrHome(){ return pbUse('badge',{text:'hi'}); }\n"),
    ):
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write(body)
    with open(os.path.join(d, "logic/components/badge.json"), "w", encoding="utf-8") as f:
        json.dump({"writes": ["cycleSettings", "kpiSets"],
                   "affordances": [{"id": "click", "why": "Opens the rating drawer."}]},
                  f, indent=2, ensure_ascii=False)
    reg = {
        "meta": {"name": "Fixture — hand-off docs", "schemaVersion": 11},
        "tokens": {},
        "components": [{"id": "badge", "name": "Badge", "level": "atom", "scope": "local",
                        "renderFn": "renderCmpBadge", "renderSrc": "render/components/badge.js",
                        "logicSrc": "logic/components/badge.json"}],
        "screens": [{"id": "home", "name": "Home", "level": "page",
                     "renderFn": "renderScrHome", "renderSrc": "render/screens/home.js"}],
        "flow": {"populated": False}, "erd": {"populated": False},
        "ia": {"populated": False}, "runtime": [],
    }
    with open(os.path.join(d, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return reg


print("1 · it emits both documents")
d = tempfile.mkdtemp(prefix="pb-handoff-docs-")
reg = fixture(d)
out1 = os.path.join(d, "out1")
written = HD.write_docs(d, out1)
names = sorted(os.path.basename(p) for p, _ in written)
check(names == ["logic.md", "rules.md"], "logic.md + rules.md (got %s)" % names)
logic = open(os.path.join(out1, "logic.md"), encoding="utf-8").read()
rules = open(os.path.join(out1, "rules.md"), encoding="utf-8").read()
check(logic.startswith("# Fixture — hand-off docs — logic"), "logic.md is titled from meta.name")
check("| Screens + components | 2 |" in logic, "the at-a-glance count is right")
check("### badge — `component`" in logic and "### home — `screen`" in logic,
      "every item gets a section")

print("2 · deterministic — byte-identical across runs")
out2 = os.path.join(d, "out2")
HD.write_docs(d, out2)
same = all(open(os.path.join(out1, n), "rb").read() == open(os.path.join(out2, n), "rb").read()
           for n in ("logic.md", "rules.md"))
check(same, "a second run produces byte-identical files")
check("20" not in logic.split("\n")[2][:40], "no timestamp in the header line")

print("3 · the authored half survives the projection")
check("`store.cycleSettings`" in logic and "`store.kpiSets`" in logic,
      "writes[] reaches the document")
check("Opens the rating drawer." in logic, "affordances[].why reaches it verbatim")

print("4 · a wide relation is capped, with the count kept")
wide = HD._join_cap(["fn%02d" % i for i in range(53)])
check(wide.startswith("53 — "), "leads with the true count (got %r)" % wide[:12])
check(wide.endswith("+45"), "and says how many were left off (got %r)" % wide[-6:])
check(wide.count("`fn") == 8, "naming exactly the cap")
check(HD._join_cap([]) == "—", "empty stays an em dash")
check(HD._join_cap(["only"]) == "`only`", "a single value is not prefixed with a count")

print("5 · no declared rules says so, in words")
check("None declared" in rules and "ia.rules" in rules,
      "rules.md explains the absence instead of rendering a blank section")
check("only in people's heads" in rules, "and is honest about what that means")

print("6 · a pipe in authored prose cannot break a table")
check(HD._esc("a | b") == "a \\| b", "pipes are escaped")
check("\n" not in HD._esc("a\nb"), "newlines are flattened")

print()
if fails:
    print("FAIL — %d regression(s)" % len(fails))
    sys.exit(1)
print("PASS — handoff_docs projects logic + rules deterministically")
