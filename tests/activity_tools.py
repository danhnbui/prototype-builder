#!/usr/bin/env python3
"""
activity_tools.py — the activity strip's "which tool, how many subagents" half: pb/hooks/activity.py -> .preview/agents.json
-> serve.py's /__pb_data `activity.tools`.

  1  the verb map (tool_name -> one word), and nothing but a verb is stored
  2  PreToolUse / PostToolUse / PostToolUseFailure pair up (running, doneAt); running floors at 0
  3  SubagentStart / SubagentStop move `agents` and floor at 0
  4  two sessions stay apart: a Stop or a new prompt in one leaves the other; the last Stop removes the file
  5  activity.json is written only by UserPromptSubmit / PostToolUse / Stop; the hook prints nothing; no .preview/ or no pb project: nothing
  6  serve.read_tools: sums agents over fresh sessions (< 600 s), skips stale ones, picks the freshest running session,
     else the last finished one, else blanks; a bad file or bad numbers never raise; a bad verb reads as ''
  7  serve.data_current: `activity.tools` rides on a valid activity.json only; a malformed agents.json is ignored
  8  hooks.json lists activity.py for all seven events; the watcher classifies agents.json like activity.json

Usage:  python3 tests/activity_tools.py
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


def fire(folder, event, sid="s1", tool=None, raw=None):
    payload = {"hook_event_name": event, "cwd": folder, "session_id": sid}
    if tool is not None:
        payload["tool_name"] = tool
    if sid is None:
        del payload["session_id"]
    p = subprocess.run([sys.executable, "-S", "-B", ACTIVITY], input=raw if raw is not None else json.dumps(payload),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    return p.returncode, p.stdout, p.stderr


def make_pb(folder, preview=True):
    os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
    with open(os.path.join(folder, "registry.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    with open(os.path.join(folder, "memory", "constitution.md"), "w", encoding="utf-8") as f:
        f.write("# c\n")
    if preview:
        os.makedirs(os.path.join(folder, ".preview"))


def load(folder, name="agents.json"):
    try:
        with open(os.path.join(folder, ".preview", name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def sess(folder, sid="s1"):
    doc = load(folder)
    return (doc or {}).get("sessions", {}).get(sid)


def put(folder, doc, name="agents.json"):
    with open(os.path.join(folder, ".preview", name), "w", encoding="utf-8") as f:
        if isinstance(doc, str):
            f.write(doc)
        else:
            json.dump(doc, f)


def main():
    tmp = tempfile.mkdtemp(prefix="pb-activity-tools-")
    try:
        live = os.path.join(tmp, "live")
        make_pb(live)

        # 1 · the verb map
        print("1 · verb map")
        want = {"Read": "Reading", "Edit": "Editing", "MultiEdit": "Editing", "NotebookEdit": "Editing", "Write": "Writing",
                "Bash": "Running", "Grep": "Searching", "WebSearch": "Searching", "Glob": "Finding", "Agent": "Delegating",
                "Task": "Delegating", "WebFetch": "Fetching", "Skill": "Loading", "TodoWrite": "Planning",
                "TaskCreate": "Planning", "TaskUpdate": "Planning", "mcp__x__y": "Using", "Whatever": "Using", "": "Using"}
        for tool, verb in want.items():
            fire(live, "UserPromptSubmit")
            fire(live, "PreToolUse", tool=tool)
            check((sess(live) or {}).get("verb") == verb, "%r -> %s (%s)" % (tool, verb, sess(live)))
        fire(live, "UserPromptSubmit")
        fire(live, "PreToolUse", tool="Bash", raw=json.dumps({"hook_event_name": "PreToolUse", "cwd": live, "session_id": "s1",
                                                              "tool_name": "Bash", "tool_input": {"command": "rm -rf secret-file"}}))
        body = open(os.path.join(live, ".preview", "agents.json"), encoding="utf-8").read()
        check("secret-file" not in body and "tool_input" not in body, "no command / file name is stored")
        check(sorted(sess(live)) == ["agents", "at", "doneAt", "running", "verb"], "a record is exactly at / verb / running / doneAt / agents")

        # 2 · Pre / Post pairing
        print("2 · PreToolUse / PostToolUse pairing")
        fire(live, "UserPromptSubmit")
        check(sess(live)["running"] == 0 and sess(live)["verb"] == "" and sess(live)["doneAt"] == 0, "UserPromptSubmit resets the record")
        fire(live, "PreToolUse", tool="Read")
        fire(live, "PreToolUse", tool="Grep")
        s = sess(live)
        check(s["running"] == 2 and s["verb"] == "Searching" and s["doneAt"] == 0, "two parallel calls: running 2, the last verb (%s)" % s)
        t0 = time.time()
        fire(live, "PostToolUse", tool="Read")
        s = sess(live)
        check(s["running"] == 1 and abs(s["doneAt"] - t0) < 15 and s["doneAt"] > 0, "PostToolUse: running 1, doneAt = now (%s)" % s)
        fire(live, "PostToolUseFailure", tool="Grep")
        check(sess(live)["running"] == 0, "PostToolUseFailure counts as finished")
        fire(live, "PostToolUse", tool="Grep")
        check(sess(live)["running"] == 0, "running floors at 0")
        check(isinstance(sess(live)["at"], float) and abs(sess(live)["at"] - time.time()) < 15, "`at` is an epoch float")

        # 3 · subagents
        print("3 · SubagentStart / SubagentStop")
        fire(live, "UserPromptSubmit")
        fire(live, "SubagentStart")
        fire(live, "SubagentStart")
        check(sess(live)["agents"] == 2, "two started: agents 2")
        fire(live, "SubagentStop")
        check(sess(live)["agents"] == 1, "one stopped: agents 1")
        fire(live, "SubagentStop")
        fire(live, "SubagentStop")
        check(sess(live)["agents"] == 0, "agents floors at 0")
        fire(live, "SubagentStart")
        fire(live, "UserPromptSubmit")
        check(sess(live)["agents"] == 0, "a new prompt resets agents")

        # 4 · two sessions apart
        print("4 · sessions stay apart")
        fire(live, "UserPromptSubmit", sid="A")
        fire(live, "UserPromptSubmit", sid="B")
        fire(live, "PreToolUse", sid="A", tool="Edit")
        fire(live, "SubagentStart", sid="B")
        fire(live, "SubagentStart", sid="B")
        check(sess(live, "A")["verb"] == "Editing" and sess(live, "A")["agents"] == 0 and sess(live, "B")["agents"] == 2,
              "A edits, B has 2 agents")
        fire(live, "UserPromptSubmit", sid="B")
        check(sess(live, "A")["running"] == 1, "a new prompt in B leaves A's counts")
        fire(live, "Stop", sid="B")
        check(sess(live, "B") is None and sess(live, "A")["running"] == 1, "Stop removes B only")
        fire(live, "PreToolUse", sid=None, tool="Read")
        check(sess(live, "unknown") and sess(live, "unknown")["verb"] == "Reading", "no session_id -> 'unknown'")
        fire(live, "Stop", sid="unknown")
        fire(live, "Stop", sid="A")
        check(sess(live, "s1") is not None, "…the earlier session s1 is still there")
        fire(live, "Stop", sid="s1")
        check(load(live) is None and not [f for f in os.listdir(os.path.join(live, ".preview")) if f.endswith(".tmp")],
              "the last Stop removes agents.json, no temp file is left")
        put(live, {"sessions": {"old": {"at": time.time() - 4000, "verb": "Reading", "running": 1, "doneAt": 0, "agents": 3}}})
        fire(live, "UserPromptSubmit", sid="new")
        check(sorted(load(live)["sessions"]) == ["new"], "a record untouched for 30 minutes is dropped")
        for bad in ("not json", "[]", '{"sessions": 5}', '{"sessions": {"s1": 7}}', '{"sessions": {"s1": {"running": true, "agents": -3, "at": 1}}}'):
            put(live, bad)
            code, out, err = fire(live, "PreToolUse", tool="Read")
            check(code == 0 and out == "" and err == "" and sess(live)["running"] == 1, "a malformed file on disk is rebuilt (%r)" % bad)

        # 5 · activity.json untouched by the new events; silence; no .preview/
        print("5 · activity.json, silence, scope")
        os.remove(os.path.join(live, ".preview", "agents.json"))
        fire(live, "UserPromptSubmit")
        act_before = open(os.path.join(live, ".preview", "activity.json"), encoding="utf-8").read()
        mt = os.path.getmtime(os.path.join(live, ".preview", "activity.json"))
        time.sleep(0.05)
        for ev, kw in (("PreToolUse", {"tool": "Read"}), ("PostToolUseFailure", {}), ("SubagentStart", {}), ("SubagentStop", {})):
            code, out, err = fire(live, ev, **kw)
            check(code == 0 and out == "" and err == "", "%s: exit 0, nothing printed" % ev)
        check(open(os.path.join(live, ".preview", "activity.json"), encoding="utf-8").read() == act_before
              and os.path.getmtime(os.path.join(live, ".preview", "activity.json")) == mt,
              "PreToolUse / PostToolUseFailure / SubagentStart / SubagentStop leave activity.json untouched")
        for ev in ("UserPromptSubmit", "PostToolUse", "Stop"):
            code, out, err = fire(live, ev)
            check(code == 0 and out == "" and err == "", "%s: exit 0, nothing printed" % ev)
        check(load(live, "activity.json")["event"] == "Stop", "the three old events still write activity.json")
        for raw in ("", "not json", "[]", "null", '{"cwd": 5}', json.dumps({"hook_event_name": "SessionStart", "cwd": live})):
            code, out, err = fire(live, None, raw=raw)
            check(code == 0 and out == "" and err == "", "bad / foreign input is silent, exit 0 (%r)" % raw[:20])
        cold = os.path.join(tmp, "cold")
        make_pb(cold, preview=False)
        fire(cold, "PreToolUse", tool="Read")
        check(not os.path.exists(os.path.join(cold, ".preview")), "no .preview/ -> none is created")
        plain = os.path.join(tmp, "plain")
        os.makedirs(plain)
        fire(plain, "PreToolUse", tool="Read")
        check(os.listdir(plain) == [], "outside a pb project -> nothing written")

        # 6 · serve.read_tools
        print("6 · serve.read_tools")
        import serve
        pb = os.path.join(tmp, "srv")
        make_pb(pb)

        class St:
            tools_path = os.path.join(pb, ".preview", "agents.json")
            hook_path = os.path.join(pb, ".preview", "activity.json")

        def tools(doc, now=None):
            put(pb, doc)
            return serve.read_tools(St(), now)

        now = time.time()

        def rec(age=1, verb="Reading", running=0, done_age=None, agents=0):
            return {"at": now - age, "verb": verb, "running": running, "doneAt": 0 if done_age is None else now - done_age,
                    "agents": agents}

        check(serve.read_tools(St()) is None, "no file -> None")
        for bad in ("not json", "[]", "null", '{"sessions": []}', '{"sessions": {}}', '{"x": 1}'):
            check(tools(bad) is None, "malformed / empty -> None (%r)" % bad)
        got = tools({"sessions": {"a": rec(running=1, agents=2), "b": rec(age=5, verb="Editing", running=1, agents=1),
                                  "c": rec(age=2, verb="Writing", running=0, done_age=2, agents=4)}})
        check(got and got["agents"] == 7, "agents are summed over sessions (%s)" % got)
        check(got["verb"] == "Reading" and got["running"] == 1 and abs(got["at"] - (now - 1)) < 1e-6,
              "the running session with the greatest `at` wins (%s)" % got)
        got = tools({"sessions": {"a": rec(age=30, verb="Reading", running=1), "b": rec(age=3, verb="Editing", running=0, done_age=3),
                                  "c": rec(age=40, verb="Writing", running=2)}})
        check(got["verb"] == "Reading" and got["running"] == 1, "a running session beats a newer finished one; of two running, the freshest (%s)" % got)
        got = tools({"sessions": {"a": rec(age=30, verb="Reading", done_age=30), "b": rec(age=10, verb="Editing", done_age=10),
                                  "c": rec(age=40, verb="Writing", done_age=5)}})
        check(got["verb"] == "Writing" and got["running"] == 0 and abs(got["doneAt"] - (now - 5)) < 1e-6,
              "none running -> the greatest doneAt (%s)" % got)
        got = tools({"sessions": {"a": rec(verb="Reading", agents=1)}})
        check(got == {"agents": 1, "verb": "", "running": 0, "at": 0, "doneAt": 0}, "no running, no doneAt -> blanks, agents kept (%s)" % got)
        got = tools({"sessions": {"old": rec(age=600, running=1, agents=5), "older": rec(age=5000, agents=9),
                                  "ok": rec(age=599, verb="Finding", running=1, agents=1)}})
        check(got["agents"] == 1 and got["verb"] == "Finding", "a session at 600 s or more is excluded from the sums (%s)" % got)
        check(tools({"sessions": {"old": rec(age=600, running=1, agents=5)}}) is None, "only stale sessions -> None")
        check(tools({"sessions": {"a": rec(age=100, running=1, agents=2)}}, now=now + 1000) is None, "freshness is against the clock `now`")
        for verb in ("x" * 21, "Rea\nding", "Re\x00ad", 5, None, ["Reading"]):
            got = tools({"sessions": {"a": rec(verb=verb, running=1, agents=1)}})
            check(got and got["verb"] == "" and got["running"] == 1 and got["agents"] == 1, "a bad verb reads as '' (%r)" % (verb,))
        check(tools({"sessions": {"a": rec(verb="x" * 20, running=1)}})["verb"] == "x" * 20, "a 20-character verb is fine")
        for field, val in (("running", True), ("running", -1), ("running", 1.5), ("agents", True), ("agents", -2), ("agents", "3"),
                           ("at", True), ("at", "1"), ("at", None), ("doneAt", -1), ("doneAt", True), ("doneAt", "x")):
            r = rec(running=1, agents=1)
            r[field] = val
            got = tools({"sessions": {"bad": r, "good": rec(age=2, verb="Editing", running=1, agents=2)}})
            check(got and got["agents"] == 2 and got["verb"] == "Editing", "a bad %s=%r skips that session (%s)" % (field, val, got))
        put(pb, '{"sessions": {"a": {"at": Infinity, "verb": "Reading", "running": 1, "doneAt": 0, "agents": 1}, '
                '"b": {"at": NaN, "verb": "Reading", "running": 1, "doneAt": 0, "agents": 1}}}')
        check(serve.read_tools(St()) is None, "Infinity / NaN never count as fresh")

        # 7 · data_current: tools ride on a valid activity.json only
        print("7 · /__pb_data activity.tools")
        run_state = serve.State(os.path.join(pb, "registry.json"), os.path.join(ROOT, "pb", "template", "prototype.html"),
                                os.path.join(pb, "prototype.html"), False)
        for need in ("hook_path", "tools_path"):
            check(hasattr(run_state, need), "State has %s" % need)
        reg = {"meta": {"name": "t"}, "screens": [], "components": []}
        with open(os.path.join(pb, "registry.json"), "w", encoding="utf-8") as f:
            json.dump(reg, f)
        put(pb, {"state": "working", "at": now, "event": "PostToolUse"}, "activity.json")
        put(pb, {"sessions": {"a": rec(verb="Editing", running=1, agents=2)}})
        data, err = serve.data_current(run_state)
        act = (data or {}).get("activity") or {}
        check(data is not None and act.get("state") == "working" and act.get("tools", {}).get("verb") == "Editing"
              and act["tools"]["agents"] == 2 and sorted(act["tools"]) == ["agents", "at", "doneAt", "running", "verb"],
              "activity.tools = {agents, verb, running, at, doneAt} (%s / %s)" % (act, err))
        print("   example activity: " + json.dumps(act))
        put(pb, '{"sessions": {broken')
        data, err = serve.data_current(run_state)
        act = (data or {}).get("activity")
        check(data is not None and act and act.get("state") == "working" and "tools" not in act, "a malformed agents.json is ignored: no tools, no error (%s)" % err)
        os.remove(run_state.tools_path)
        data, err = serve.data_current(run_state)
        check(data and "tools" not in (data["activity"] or {}), "no agents.json: no tools key")
        put(pb, {"sessions": {"a": rec(verb="Editing", running=1)}})
        put(pb, "garbage", "activity.json")
        data, err = serve.data_current(run_state)
        check(data is not None and data["activity"] is None, "an invalid activity.json: activity stays null even with tools on file")

        # 8 · hooks.json and the watcher
        print("8 · hooks.json and watching")
        with open(os.path.join(ROOT, "pb", "hooks", "hooks.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for ev in ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop", "Stop"):
            groups = [g for g in hooks.get(ev, []) if not g.get("matcher") and any(
                h.get("args", [])[-1:] == ["${CLAUDE_PLUGIN_ROOT}/hooks/activity.py"] and h.get("timeout") == 3 for h in g["hooks"])]
            check(len(groups) == 1, "hooks.json: %s runs activity.py (matcher-less, timeout 3)" % ev)
        check(run_state.hook_path in run_state.watched and run_state.tools_path in run_state.watched, "both hook files are watched")
        v0 = run_state.hook_version
        v_page = run_state.version
        run_state.seen = None
        serve.refresh(run_state)                 # take the baseline
        time.sleep(0.05)
        put(pb, {"sessions": {"a": rec(verb="Reading", running=1)}})
        changed = serve.refresh(run_state)
        check(run_state.tools_path in changed and run_state.hook_version == v0 + 1 and run_state.version == v_page,
              "a change to agents.json bumps hook_version and re-renders nothing")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


try:
    main()
except Exception as e:  # a crash is a failure, with the reason
    import traceback
    traceback.print_exc()
    FAILS.append("crashed: %r" % (e,))

if FAILS:
    print("FAIL: activity_tools (%d of %d checks failed)" % (len(FAILS), N))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("PASS: activity_tools (%d checks)" % N)
