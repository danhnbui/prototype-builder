#!/usr/bin/env python3
"""
research_wiring.py — the research slice as seen by every OTHER tool. research_tool.py pins research.py itself.

  1. slice.py reads the slice, and `list research studies` gives the ids
  2. lint: R-RESEARCH warns on a bad id, a bad status, a dangling target and a missing evidence file, stays
     quiet on a clean study and on a project with no research, and never fails --strict
  3. security_scan.py reads evidence files (a planted key in a transcript is found) and skips the
     other folders under memory/research/
  5. clean.py --apply with every keep flag leaves memory/research/ byte-identical
  6. report.py's facts carry nothing from a transcript

Usage: python3 tests/research_wiring.py · Exit 0/1.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
sys.path.insert(0, TOOLS)

import security_scan  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "pb", "migrations"))
from manifest import CURRENT_SCHEMA  # noqa: E402

FAIL = []
MARKER = "the-courier-said-this-only-in-the-raw-file"
# Assembled at run time so no scanner reads this source as a real credential.
PLANTED = "AKIA" + "IOSFODNN7" + "EXAMPLE"


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def run(tool, *args, cwd=None):
    return subprocess.run([sys.executable, os.path.join(TOOLS, tool), *args], cwd=cwd,
                          capture_output=True, text=True)


def tree_hash(path):
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            h.update(os.path.relpath(full, path).encode())
            with open(full, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


def project(tmp):
    """A small synthetic project with one analysed interview study."""
    ev_dir = os.path.join(tmp, "memory", "research", "rs-cod", "evidence")
    os.makedirs(ev_dir)
    with open(os.path.join(ev_dir, "e1-p01.txt"), "w", encoding="utf-8") as f:
        f.write("I always collect the cash first. " + MARKER + "\n")
    reg = {
        "meta": {"name": "Parcel demo", "schemaVersion": CURRENT_SCHEMA, "roles": [{"id": "courier"}]},
        "tokens": {}, "components": [], "screens": [],
        "ia": {"populated": True,
               "jobs": [{"id": "pay-cod", "roles": ["courier"], "priority": "P1", "when": "a parcel arrives",
                         "want": "collect cash", "so": "the parcel is released", "screens": []}],
               "rules": [{"id": "cash-first", "title": "Cash is collected before release", "kind": "decision",
                          "summary": "Cash comes first."}]},
        "research": {"populated": True, "studies": [{
            "id": "rs-cod", "title": "Cash order", "question": "Do couriers collect first?",
            "method": "interview", "status": "analysed", "audience": {"roles": ["courier"], "segment": "", "targetN": 5},
            "targets": [{"kind": "job", "id": "pay-cod"}],
            "evidence": [{"id": "e1", "file": "memory/research/rs-cod/evidence/e1-p01.txt", "kind": "transcript",
                          "consent": "yes", "participant": "P01", "dropped": None}],
            "findings": [{"id": "f1", "text": "Couriers collect cash before handing over.", "hypotheses": ["h1"],
                          "targets": [{"kind": "rule", "id": "cash-first"}],
                          "evidence": [{"evidence": "e1", "quote": "I always collect the cash first.", "participant": "P01"}]}],
        }]},
    }
    path = os.path.join(tmp, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    return path, reg


def lint_output(path, *flags):
    r = run("lint_registry.py", path, *flags)
    return r.returncode, r.stdout + r.stderr


def main():
    tmp = tempfile.mkdtemp()
    try:
        path, reg = project(tmp)

        print("1 · slice.py")
        r = run("slice.py", "list", "research", "studies", "--registry", path)
        check(r.returncode == 0 and "rs-cod" in r.stdout, "list research studies gives the id")
        r = run("slice.py", "get", "research", "studies.rs-cod", "--registry", path)
        check(r.returncode == 0 and json.loads(r.stdout).get("method") == "interview", "get reads one study")

        print("2 · lint R-RESEARCH")
        _, out = lint_output(path)
        check("R-RESEARCH" not in out, "a clean study draws no R-RESEARCH")
        bad = copy.deepcopy(reg)
        study = bad["research"]["studies"][0]
        study["id"], study["status"] = "cod", "done"
        study["targets"] = [{"kind": "job", "id": "gone"}, {"kind": "feature", "id": "free text is never checked"}]
        study["evidence"][0]["file"] = "memory/research/rs-cod/evidence/missing.txt"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bad, f, ensure_ascii=False)
        _, out = lint_output(path)
        check(out.count("R-RESEARCH") == 4, "bad id, status, target and file are each found (%d)" % out.count("R-RESEARCH"))
        check("free text" not in out, "a feature target is free text and never checked")
        _, strict = lint_output(path, "--strict")
        strict_research = [ln for ln in strict.splitlines() if "R-RESEARCH" in ln]
        check(strict_research and not any("ERROR" in ln for ln in strict_research), "R-RESEARCH stays a warning under --strict")
        none = copy.deepcopy(reg)
        del none["research"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(none, f, ensure_ascii=False)
        _, out = lint_output(path)
        check("R-RESEARCH" not in out, "no research, no finding")
        # a recording the hand-off left out on purpose is absent by design; the same row without `withheld` is a real gap
        gone = copy.deepcopy(reg)
        gone["research"]["studies"][0]["evidence"].append(
            {"id": "e2", "file": "memory/research/rs-cod/evidence/e2-screen.webm", "kind": "recording", "consent": "yes",
             "participant": "P01", "sha256": "ab" * 32, "dropped": None})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gone, f, ensure_ascii=False)
        _, out = lint_output(path)
        check(out.count("R-RESEARCH") == 1 and "'e2' is missing on disk" in out, "a missing recording without `withheld` still warns (%d)" % out.count("R-RESEARCH"))
        gone["research"]["studies"][0]["evidence"][1]["withheld"] = {"at": "2026-11-07T08:00:00Z", "reason": "hand-off without recordings"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gone, f, ensure_ascii=False)
        _, out = lint_output(path)
        check("R-RESEARCH" not in out, "a withheld recording whose file is absent draws no R-RESEARCH")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)

        print("3 · security_scan")
        clean = security_scan.scan(reg, tmp)
        check(not any("research" in f.where and "evidence" in f.where for f in clean), "a clean transcript draws nothing")
        planted = os.path.join(tmp, "memory", "research", "rs-cod", "evidence", "e2-p02.txt")
        with open(planted, "w", encoding="utf-8") as f:
            f.write("Then they read out aws_access_key_id = " + PLANTED + "\n")
        hits = security_scan.scan(reg, tmp)
        check(any("e2-p02.txt" in f.where for f in hits), "a key in a transcript is found")
        os.remove(planted)
        elsewhere = os.path.join(tmp, "memory", "research", "rs-cod", "note.txt")
        with open(elsewhere, "w", encoding="utf-8") as f:
            f.write("aws_access_key_id = " + PLANTED + "\n")
        check(not any("note.txt" in f.where for f in security_scan.scan(reg, tmp)), "only evidence/ folders are read")
        os.remove(elsewhere)

        print("5 · clean.py")
        research_dir = os.path.join(tmp, "memory", "research")
        before = tree_hash(research_dir)
        r = run("clean.py", path, "--apply", "--keep-backups", "1", "--keep-closed", "1", "--keep-patches", "1")
        check(r.returncode == 0, "clean ran (%d)" % r.returncode)
        check(tree_hash(research_dir) == before, "memory/research/ is byte-identical after it")

        print("6 · report.py")
        out_file = os.path.join(tmp, "facts.md")
        r = run("report.py", "--project", tmp, "--out", out_file)
        check(r.returncode == 0, "report ran (%d) %s" % (r.returncode, r.stderr[:200]))
        with open(out_file, encoding="utf-8") as f:
            check(MARKER not in f.read(), "the facts file carries nothing from a transcript")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if FAIL:
        print("FAIL — %d" % len(FAIL))
        return 1
    print("PASS — the research slice is wired into slice, lint, scan, hand-off, clean and report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
