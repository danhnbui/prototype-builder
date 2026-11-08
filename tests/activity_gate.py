#!/usr/bin/env python3
"""
activity_gate.py — a gated command names its gate on the preview's activity strip.

`pb/hooks/activity.py --gate <G-ID> "<ask>"` adds `gate: {id, ask, at}` to `.preview/activity.json`; the hook events
keep it (PostToolUse, Stop) or drop it (UserPromptSubmit); `serve.read_hook` passes it on only when well formed.
Checked here with no browser (the strip's text is checked in tests/live_fill.py):

  1  the CLI writes the gate, keeps state / at / event / since, prints nothing, exits 0
  2  a bad id, an empty ask, missing args or an over-long ask: nothing written (the long one is capped), exit 0
  3  no `.preview/`, or not a pb project: nothing is created, exit 0; --project names the folder
  4  PostToolUse and Stop keep the gate; UserPromptSubmit drops it; a malformed gate on file is not kept
  5  serve.read_hook passes a valid gate and drops malformed ones (the rest of the activity still passes)

Usage:  python3 tests/activity_gate.py
Exit:   0 = pass · 1 = a failure
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTIVITY = os.path.join(ROOT, "pb", "hooks", "activity.py")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

N = 0
FAILS = []


def check(cond, msg):
    global N
    N += 1
    if not cond:
        FAILS.append(msg)
        print("  FAIL " + msg)


def run(args=None, stdin="", cwd=None):
    p = subprocess.run([sys.executable, "-S", "-B", ACTIVITY] + list(args or []), input=stdin, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    return p.returncode, p.stdout, p.stderr


def event(name, cwd):
    return run(stdin=json.dumps({"hook_event_name": name, "cwd": cwd, "session_id": "s"}), cwd=cwd)


def make_pb(folder, preview=True):
    os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
    with open(os.path.join(folder, "registry.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    with open(os.path.join(folder, "memory", "constitution.md"), "w", encoding="utf-8") as f:
        f.write("# c\n")
    if preview:
        os.makedirs(os.path.join(folder, ".preview"))


def load(folder):
    path = os.path.join(folder, ".preview", "activity.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    tmp = tempfile.mkdtemp(prefix="pb-activity-gate-")
    try:
        live = os.path.join(tmp, "live")
        make_pb(live)
        elsewhere = os.path.join(tmp, "elsewhere")
        os.makedirs(elsewhere)

        # 1 · the CLI writes the gate and leaves the rest of the file alone
        print("1 · the CLI writes the gate")
        event("UserPromptSubmit", live)
        before = load(live)
        t0 = time.time()
        code, out, err = run(["--gate", "G-JTBD", "approve 4 jobs and 3 terms"], cwd=live)
        got = load(live)
        check(code == 0 and out == "" and err == "", "exit 0, nothing printed (%r, %r)" % (out, err))
        check(got and got.get("gate", {}).get("id") == "G-JTBD" and got["gate"].get("ask") == "approve 4 jobs and 3 terms",
              "the file carries the gate id and ask (%s)" % got)
        check(got and abs(got["gate"].get("at", 0) - t0) < 15, "…with the time it was written")
        check(got and all(got.get(k) == before.get(k) for k in ("state", "at", "event", "since")),
              "…and state / at / event / since are as they were (%s → %s)" % (before, got))
        check(sorted(os.listdir(os.path.join(live, ".preview"))) == ["activity.json"], "…atomically: no temp file is left behind")
        code, out, err = run(["--gate", "G-IA", "pick", "one", "of", "3", "groupings"], cwd=live)
        check(code == 0 and load(live)["gate"] == dict(load(live)["gate"], id="G-IA", ask="pick one of 3 groupings"),
              "an unquoted ask is joined with spaces, and a second gate replaces the first")
        code, out, err = run(["--gate", "G-X1-Y", "  approve\n  it  "], cwd=live)
        check(load(live)["gate"]["ask"] == "approve it", "an ask is trimmed to one line (whitespace collapsed)")

        # no file yet: a working file that carries the gate
        fresh = os.path.join(tmp, "fresh")
        make_pb(fresh)
        code, out, err = run(["--gate", "G-STUDY", "approve the study plan", "--project", fresh], cwd=elsewhere)
        got = load(fresh)
        check(code == 0 and got and got.get("state") == "working" and got.get("gate", {}).get("id") == "G-STUDY",
              "no file yet → a working file that carries the gate, and --project names the folder (%s)" % got)

        # 2 · bad input writes nothing
        print("2 · bad input writes nothing")
        event("UserPromptSubmit", live)
        base = load(live)
        for args in (["--gate", "g-jtbd", "ask"], ["--gate", "JTBD", "ask"], ["--gate", "G-", "ask"], ["--gate", "G-jtbd", "ask"],
                     ["--gate", "G-JTBD", ""], ["--gate", "G-JTBD", "   \n "], ["--gate", "G-JTBD"], ["--gate"],
                     ["--gate", "G-JTBD", "ask", "--project"]):
            code, out, err = run(args, cwd=live)
            check(code == 0 and out == "" and load(live) == base, "%r → exit 0, file untouched" % (args,))
        code, out, err = run(["--gate", "G-JTBD", "x" * 400], cwd=live)
        long_ask = (load(live) or {}).get("gate", {}).get("ask", "")
        check(code == 0 and 0 < len(long_ask) <= 160, "an over-long ask is capped at 160 characters (%d)" % len(long_ask))

        # 3 · outside a pb project, or before a preview made .preview/
        print("3 · nothing is created where there is nowhere to write")
        cold = os.path.join(tmp, "cold")
        make_pb(cold, preview=False)
        code, out, err = run(["--gate", "G-JTBD", "approve 4 jobs"], cwd=cold)
        check(code == 0 and not os.path.exists(os.path.join(cold, ".preview")), "no .preview/ → none is created, exit 0")
        code, out, err = run(["--gate", "G-JTBD", "approve 4 jobs"], cwd=elsewhere)
        check(code == 0 and os.listdir(elsewhere) == [], "outside a pb project → nothing written, exit 0")
        code, out, err = run(["--gate", "G-JTBD", "approve 4 jobs", "--project", os.path.join(tmp, "missing")], cwd=elsewhere)
        check(code == 0, "a missing --project folder → exit 0")

        # 4 · the hook events keep or drop it
        print("4 · PostToolUse and Stop keep the gate; UserPromptSubmit drops it")
        run(["--gate", "G-DIRECTION", "approve the direction and 3 bets"], cwd=live)
        gate = load(live)["gate"]
        event("PostToolUse", live)
        got = load(live)
        check(got.get("state") == "working" and got.get("gate") == gate, "PostToolUse (the CLI's own Bash call) keeps the gate")
        event("Stop", live)
        got = load(live)
        check(got.get("state") == "idle" and got.get("gate") == gate and "since" in got, "Stop keeps it, and the turn's since")
        event("UserPromptSubmit", live)
        got = load(live)
        check(got.get("state") == "working" and "gate" not in got, "UserPromptSubmit drops it (the person has replied)")
        event("PostToolUse", live)
        check("gate" not in load(live), "…and it does not come back")
        path = os.path.join(live, ".preview", "activity.json")
        for bad in ({"id": "nope", "ask": "x", "at": 1}, {"id": "G-A", "ask": "", "at": 1}, {"id": "G-A", "ask": "x"},
                    {"id": "G-A", "ask": "x", "at": True}, "G-A", 7, None):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"state": "idle", "at": time.time(), "event": "Stop", "gate": bad}, f)
            event("Stop", live)
            check("gate" not in load(live), "a malformed gate on file is not kept (%r)" % (bad,))

        # 5 · what the preview server passes to the page
        print("5 · serve.read_hook")
        import serve

        class St:
            hook_path = path

        def passes(doc):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            return serve.read_hook(St())

        now = time.time()
        g = {"id": "G-JTBD", "ask": "approve 4 jobs and 3 terms", "at": now}
        out = passes({"state": "idle", "at": now, "since": now - 5, "gate": g})
        check(out and out.get("gate") == g and out.get("state") == "idle" and out.get("since") == now - 5,
              "a valid gate passes through with the rest of the activity (%s)" % out)
        out = passes({"state": "idle", "at": now})
        check(out and "gate" not in out, "no gate → none")
        for bad in ({"id": "jtbd", "ask": "x", "at": 1}, {"id": "G-A", "ask": "", "at": 1}, {"id": "G-A", "ask": "a\nb", "at": 1},
                    {"id": "G-A", "ask": "x" * 161, "at": 1}, {"id": "G-A", "ask": 5, "at": 1}, {"id": "G-A", "ask": "x"},
                    {"id": "G-A", "ask": "x", "at": "1"}, {"id": "G-A", "ask": "x", "at": True}, "G-A", ["G-A"], 3):
            out = passes({"state": "idle", "at": now, "gate": bad})
            check(out and out.get("state") == "idle" and "gate" not in out, "a malformed gate is dropped, the activity stays (%r)" % (bad,))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


try:
    main()
except Exception as e:  # a crash is a failure, with the reason
    FAILS.append("crashed: %r" % (e,))

if FAILS:
    print("FAIL: activity_gate (%d of %d checks failed)" % (len(FAILS), N))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("PASS: activity_gate (%d checks)" % N)
