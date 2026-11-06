#!/usr/bin/env python3
"""
hook_advice.py — the plugin's two advisory hooks say the right thing, in the right place, and nothing else.

pb/hooks/ puts the key operating rules in front of the model in any pb project, because a rule
written only in a command file never reached a free-form session. Checked here, with no browser:

  H1  hooks.json parses, declares SessionStart (startup|resume|clear|compact) and PreToolUse (Bash),
      and every script it names exists under ${CLAUDE_PLUGIN_ROOT}/hooks/. (route.py and housekeep.py,
      the fourth and fifth scripts, are checked in tests/hook_route.py and tests/hook_housekeep.py; here
      they only have to be named and exist.)
  H2  session_rules.py in a pb-shaped folder (and in `.prototype/`) prints valid JSON whose
      additionalContext is at most 25 lines and 1,600 characters, names the canon, the three
      tools, `--ensure`, `slice.py find|get --fields` and the subagent model rule; in a non-pb
      folder it prints nothing. A session one folder above the registry gets it too. Exit 0 always.
  H3  bash_advice.py: table-driven positives (each names the right tool) and negatives
      (normal commands, `json.load`, `json.dumps`, `slice.py` writes, `shot.py`, and the registry
      writes route.py owns now); silent in a non-pb folder; output is valid JSON, never carries
      `permissionDecision`, exit 0. A session one folder above the registry counts as a pb project.
  H5  browser_advice.py: names shot.py --no-png --eval and --selector inside a pb project, silent
      outside; speaks on the first call of a session and every 25th, not between; a broken counter
      folder is silent with exit 0; no permissionDecision; hooks.json matches the MCP tool names.
  H4  bad stdin, empty stdin, a missing command and a non-object payload print nothing and exit 0.
  H6  activity.py (UserPromptSubmit / PostToolUse / Stop): writes .preview/activity.json {state, at} atomically, only inside a
      pb project whose .preview/ already exists, prints nothing, ignores any other event, exits 0 on anything;
      hooks.json declares both events (the preview's activity strip reads that file).

Usage:  python3 tests/hook_advice.py
Exit:   0 = pass · 1 = a failure
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "pb", "hooks")
SESSION = os.path.join(HOOKS, "session_rules.py")
BASH = os.path.join(HOOKS, "bash_advice.py")
BROWSER = os.path.join(HOOKS, "browser_advice.py")

FAILS = []
TMP_FOR_HOOKS = tempfile.mkdtemp(prefix="pb-hook-test-")   # the counter files live here, not in the real temp folder


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def run(script, stdin="", cwd=None, env_extra=None):
    env = dict(os.environ)
    env["TMPDIR"] = TMP_FOR_HOOKS
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "-S", "-B", script], input=stdin, cwd=cwd, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    return p.returncode, p.stdout, p.stderr


def make_pb(folder, how="render"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "registry.json"), "w", encoding="utf-8") as f:
        f.write("{}")
    if how == "render":
        os.makedirs(os.path.join(folder, "render"))
    else:
        os.makedirs(os.path.join(folder, "memory"))
        with open(os.path.join(folder, "memory", "constitution.md"), "w", encoding="utf-8") as f:
            f.write("# c\n")


def hook_json(out):
    """Parse hook stdout; return (additionalContext, event) or (None, None)."""
    try:
        d = json.loads(out)
        h = d["hookSpecificOutput"]
        return h["additionalContext"], h["hookEventName"]
    except Exception:
        return None, None


# ---------------------------------------------------------------- H1
print("H1 · hooks.json")
cfg_path = os.path.join(HOOKS, "hooks.json")
cfg = None
try:
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:  # noqa: BLE001
    check(False, "hooks.json parses (%s)" % e)
if cfg:
    check(True, "hooks.json parses")
    hooks = cfg.get("hooks", {})
    ss, pt = hooks.get("SessionStart", []), hooks.get("PreToolUse", [])
    check(bool(ss) and ss[0].get("matcher") == "startup|resume|clear|compact",
          "SessionStart matcher is startup|resume|clear|compact")
    check(bool(pt) and pt[0].get("matcher") == "Bash", "PreToolUse matcher is Bash")
    import re as _re
    mcp = [g.get("matcher") for g in pt if g.get("matcher", "").startswith("mcp__")]
    check(bool(mcp) and all(_re.match(mcp[0] + "$", t) for t in (
        "mcp__chrome-devtools__take_screenshot", "mcp__plugin_x_chrome-devtools__click",
        "mcp__claude-in-chrome__navigate")) and not _re.match(mcp[0] + "$", "mcp__posthog__exec"),
        "browser matcher fits the DevTools and claude-in-chrome tools only")
    named = []
    for group in ss + pt:
        for h in group.get("hooks", []):
            check(h.get("type") == "command" and "args" in h, "hook is an exec-style command with args")
            check("onFailure" not in h, "hook sets no onFailure")
            for a in h.get("args", []):
                if a.startswith("${CLAUDE_PLUGIN_ROOT}/"):
                    named.append(a.replace("${CLAUDE_PLUGIN_ROOT}/", ""))
    check(sorted(named) == ["hooks/bash_advice.py", "hooks/browser_advice.py", "hooks/housekeep.py",
                            "hooks/route.py", "hooks/session_rules.py"],
          "SessionStart + PreToolUse name exactly five scripts (%s)" % ", ".join(named))
    check(any(h.get("args", [])[-1:] == ["${CLAUDE_PLUGIN_ROOT}/hooks/housekeep.py"] for h in ss[0].get("hooks", [])),
          "SessionStart (same matcher as session_rules) also runs housekeep.py")
    check(any(g.get("matcher") == "mcp__.*(chrome-devtools|claude-in-chrome).*" for g in pt),
          "PreToolUse has the browser MCP matcher")
    for rel in named:
        check(os.path.isfile(os.path.join(ROOT, "pb", rel)), "named script exists: pb/" + rel)

with tempfile.TemporaryDirectory() as tmp:
    pb_dir = os.path.join(tmp, "proj")
    pb_mem = os.path.join(tmp, "proj-mem")
    inner = os.path.join(tmp, "repo")
    plain = os.path.join(tmp, "plain")
    half = os.path.join(tmp, "half")           # registry.json but neither render/ nor constitution
    make_pb(pb_dir, "render")
    make_pb(pb_mem, "memory")
    make_pb(os.path.join(inner, ".prototype"), "render")
    os.makedirs(plain)
    os.makedirs(half)
    with open(os.path.join(half, "registry.json"), "w", encoding="utf-8") as f:
        f.write("{}")

    # ------------------------------------------------------------ H2
    print("H2 · session_rules.py")
    for label, folder in (("render/ folder", pb_dir), ("memory/constitution.md", pb_mem),
                          (".prototype/ inside a repo", inner)):
        code, out, err = run(SESSION, "", cwd=folder)
        ctx, event = hook_json(out)
        check(code == 0 and ctx is not None, "pb project (%s): exit 0 and valid JSON" % label)
        if ctx is None:
            continue
        check(event == "SessionStart", "  hookEventName is SessionStart")
        check(len(ctx.splitlines()) <= 25, "  at most 25 lines (%d)" % len(ctx.splitlines()))
        check(len(ctx) <= 1600, "  at most 1,600 characters (%d)" % len(ctx))
        check(os.path.join(ROOT, "pb", "docs", "canon.md") in ctx, "  names the canon by absolute path")
        for tool in ("serve.py", "shot.py", "slice.py"):
            check(os.path.join(ROOT, "pb", "tools", tool) in ctx, "  names %s by absolute path" % tool)
        check("--ensure" in ctx and "/pb:explore" in ctx and "/pb:build" in ctx,
              "  names --ensure, /pb:explore and /pb:build")
        check("slice.py find" in ctx and "--fields" in ctx and "subagent call sets model" in ctx,
              "  names slice.py find|get --fields and that subagent calls set a model")
        check("permissionDecision" not in out, "  no permissionDecision")
    code, out, err = run(SESSION, "", cwd=pb_dir, env_extra={"CLAUDE_PLUGIN_ROOT": "/x/plugin"})
    ctx, _ = hook_json(out)
    check(ctx is not None and "/x/plugin/tools/serve.py" in ctx, "CLAUDE_PLUGIN_ROOT, when set, is the expanded root")
    for label, folder in (("no registry.json", plain), ("registry.json without render/ or constitution", half)):
        code, out, err = run(SESSION, "", cwd=folder)
        check(code == 0 and out == "", "non-pb folder (%s): silent, exit 0" % label)
    code, out, err = run(SESSION, "not json at all", cwd=pb_dir)
    check(code == 0 and hook_json(out)[0] is not None, "session_rules ignores stdin entirely")
    above = os.path.join(tmp, "above")         # a session started one folder above the registry
    make_pb(os.path.join(above, "app"), "render")
    code, out, err = run(SESSION, "", cwd=above)
    ctx, event = hook_json(out)
    check(code == 0 and ctx is not None and event == "SessionStart" and os.path.join(above, "app") in ctx,
          "a session one folder above the registry gets the digest, naming that project")
    make_pb(os.path.join(above, "app2", ".prototype"), "render")
    code, out, err = run(SESSION, "", cwd=os.path.join(above, "app2"))
    check(code == 0 and hook_json(out)[0] is not None, "  and a child's .prototype/ is found through bash_advice too")
    os.makedirs(os.path.join(tmp, "above-empty", "x"))
    code, out, err = run(SESSION, "", cwd=os.path.join(tmp, "above-empty"))
    check(code == 0 and out == "", "a folder above no registry stays silent")

    # ------------------------------------------------------------ H3
    print("H3 · bash_advice.py")
    PLAY = "shot.py"
    positives = [
        ("python3 - <<'EOF'\nfrom playwright.sync_api import sync_playwright\nEOF", PLAY),
        ("node -e \"require('playwright').chromium.launch()\"", PLAY),
        ("python3 s.py  # p.chromium.launch(headless=True)", PLAY),
        ("python3 pb/tools/serve.py registry.json --idle-exit 0", "--ensure"),
        ("python3 serve.py registry.json --idle-exit=0 --no-open", "--ensure"),
        ("nohup python3 pb/tools/serve.py registry.json > /dev/null 2>&1", "--ensure"),
        ("python3 pb/tools/serve.py registry.json &", "--ensure"),
        ("python3 pb/tools/serve.py registry.json --no-open &\nsleep 2", "--ensure"),
        ("pkill -f serve.py", "--stop"),
        ("kill $(lsof -ti :8000)", "--stop"),
        ("lsof -ti:8000 | xargs kill -9", "--stop"),
        ("kill 4242 && echo port 8000 freed", "--stop"),
    ]
    negatives = [
        "ls -la",
        "git status",
        "git commit -m 'kill the port conflict'",
        "python3 pb/tools/serve.py registry.json --ensure",
        "python3 pb/tools/serve.py --status",
        "python3 pb/tools/serve.py --stop",
        "python3 pb/tools/serve.py registry.json --idle-exit 30",
        "python3 pb/tools/serve.py registry.json --idle-exit 0.5",
        "python3 pb/tools/shot.py registry.json --screen home",
        "python3 pb/tools/test_run.py registry.json --all",
        "python3 pb/tools/shot.py registry.json --eval \"chromium.launch\"",
        "grep -rn sync_playwright pb/tools",
        "python3 -c \"import json; print(json.load(open('registry.json'))['meta'])\"",
        "python3 -c \"import json; print(json.dumps(json.load(open('registry.json'))['meta']))\"",
        "python3 -c \"import json; d={}; json.dump(d, open('out.json','w'))\"",
        "python3 pb/tools/slice.py set components card < patch.json",
        "python3 -c \"import json; json.dump({}, open('registry.json','w'))\" # via slice.py",
        "cat registry.json | head",
        "python3 build.py > build.log 2>&1 &&  echo done",
        "kill 4242",
        "npm run dev &",
        # hand writes of registry.json moved to route.py (tests/hook_route.py); bash_advice no longer speaks to them
        "python3 -c \"import json; d=json.load(open('registry.json')); json.dump(d, open('registry.json','w'))\"",
        "python3 -c \"open('registry.json','w').write('{}')\"",
        "python3 -c \"from pathlib import Path; Path('registry.json').write_text('{}')\"",
        "echo '{}' > registry.json",
        "cat patch.json > .prototype/registry.json",
        "jq . x | tee registry.json",
    ]
    for cmd, tool in positives:
        stdin = json.dumps({"cwd": pb_dir, "tool_name": "Bash", "tool_input": {"command": cmd}})
        code, out, err = run(BASH, stdin, cwd=plain)
        ctx, event = hook_json(out)
        label = cmd.splitlines()[0][:70]
        check(code == 0 and ctx is not None and event == "PreToolUse" and tool in ctx,
              "advises (%s): %s" % (tool, label))
        check("permissionDecision" not in out and "decision" not in json.loads(out or "{}"),
              "  no permission decision: %s" % label)
        check(ctx is None or ("\n" not in ctx and len(ctx) < 400), "  short, one line: %s" % label)
        # the same command in a non-pb folder stays silent
        code, out, err = run(BASH, json.dumps({"cwd": plain, "tool_input": {"command": cmd}}), cwd=plain)
        check(code == 0 and out == "", "  silent outside a pb project: %s" % label)
    for cmd in negatives:
        stdin = json.dumps({"cwd": pb_dir, "tool_name": "Bash", "tool_input": {"command": cmd}})
        code, out, err = run(BASH, stdin, cwd=plain)
        check(code == 0 and out == "", "silent: %s" % cmd.splitlines()[0][:80])
    # cwd taken from the process when the payload carries none
    code, out, err = run(BASH, json.dumps({"tool_input": {"command": "pkill -f serve.py"}}), cwd=pb_dir)
    check(code == 0 and hook_json(out)[0] is not None, "no cwd in the payload: falls back to the process folder")
    code, out, err = run(BASH, json.dumps({"cwd": inner, "tool_input": {"command": "pkill -f serve.py"}}), cwd=plain)
    check(code == 0 and hook_json(out)[0] is not None, ".prototype/ inside the payload cwd counts as a pb project")
    above = os.path.join(tmp, "above")                  # a session one folder above the registry
    make_pb(os.path.join(above, "child"), "render")
    os.makedirs(os.path.join(tmp, "above-hidden", ".dot"))
    make_pb(os.path.join(tmp, "above-hidden", ".dot", "p"), "render")
    make_pb(os.path.join(tmp, "above-hidden", "node_modules", "p"), "render")
    code, out, err = run(BASH, json.dumps({"cwd": above, "tool_input": {"command": "pkill -f serve.py"}}), cwd=plain)
    check(code == 0 and hook_json(out)[0] is not None, "an immediate child folder that is a pb project counts (session one folder above)")
    code, out, err = run(BASH, json.dumps({"cwd": os.path.join(tmp, "above-hidden"), "tool_input": {"command": "pkill -f serve.py"}}), cwd=plain)
    check(code == 0 and out == "", "dot-folders and node_modules are not scanned for a project")

    # ------------------------------------------------------------ H5
    print("H5 · browser_advice.py")

    def call(sid, cwd_payload, extra_env=None):
        payload = {"cwd": cwd_payload, "session_id": sid, "tool_name": "mcp__chrome-devtools__take_screenshot",
                   "tool_input": {}}
        return run(BROWSER, json.dumps(payload), cwd=plain, env_extra=extra_env)

    spoke = []
    for i in range(1, 52):
        code, out, err = call("sess-a", pb_dir)
        ctx, event = hook_json(out)
        if code != 0 or (out and ctx is None):
            check(False, "call %d: exit 0 and valid JSON" % i)
        if ctx:
            spoke.append(i)
            if i == 1:
                check(event == "PreToolUse", "  hookEventName is PreToolUse")
                check("--no-png --eval" in ctx and "--selector" in ctx and "network or performance" in ctx
                      and "user asked" in ctx, "  names --no-png --eval, --selector and when DevTools fits")
                check("\n" not in ctx and len(ctx) < 600, "  one short line")
                check("permissionDecision" not in out and "decision" not in json.loads(out),
                      "  no permission decision")
    check(spoke == [1, 25, 50], "speaks on calls 1, 25 and 50 only (%s)" % spoke)
    code, out, err = call("sess-b", pb_dir)
    check(hook_json(out)[0] is not None, "a new session speaks on its first call")
    code, out, err = call("sess-b", inner)
    check(code == 0 and out == "", "a second call in that session is silent (.prototype/ counts as a project)")
    code, out, err = call("sess-c", plain)
    check(code == 0 and out == "", "silent outside a pb project")
    broken = os.path.join(tmp, "broken-tmp")      # a temp folder whose per-user counter folder is a file
    os.makedirs(broken)
    with open(os.path.join(broken, "pb-hooks-%s" % os.getuid()), "w", encoding="utf-8") as f:
        f.write("x")
    code, out, err = call("sess-d", pb_dir, {"TMPDIR": broken})
    check(code == 0 and out == "", "a broken counter folder: silent, exit 0")
    for stdin in ("", "not json", "[]", "{}", '{"cwd": 5}'):
        code, out, err = run(BROWSER, stdin, cwd=plain)
        check(code == 0 and out == "", "browser_advice silent, exit 0 on %r" % stdin)

    # ------------------------------------------------------------ H6
    print("H6 · activity.py (UserPromptSubmit / PostToolUse / Stop → .preview/activity.json)")
    ACTIVITY = os.path.join(HOOKS, "activity.py")
    live = os.path.join(tmp, "live")                    # a pb project whose preview has run (.preview/ exists)
    cold = os.path.join(tmp, "cold")                    # a pb project nobody has previewed
    make_pb(live, "memory")
    make_pb(cold, "memory")
    os.makedirs(os.path.join(live, ".preview"))
    act = os.path.join(live, ".preview", "activity.json")

    def ev(name, cwd):
        return json.dumps({"hook_event_name": name, "cwd": cwd, "session_id": "s"})

    t0 = __import__("time").time()
    code, out, err = run(ACTIVITY, ev("UserPromptSubmit", live), cwd=plain)
    got = json.load(open(act, encoding="utf-8")) if os.path.isfile(act) else {}
    check(code == 0 and out == "" and err == "", "UserPromptSubmit: exit 0 and nothing printed (nothing added to the model's context)")
    check(got.get("state") == "working" and got.get("event") == "UserPromptSubmit" and abs(got.get("at", 0) - t0) < 15,
          "…writes {state: working, at: now} to .preview/activity.json (%s)" % got)
    code, out, err = run(ACTIVITY, ev("Stop", live), cwd=plain)
    check(code == 0 and out == "" and json.load(open(act, encoding="utf-8")).get("state") == "idle", "Stop: writes {state: idle}")
    check(sorted(os.listdir(os.path.join(live, ".preview"))) == ["activity.json"], "…atomically: no temp file is left in .preview/")
    code, out, err = run(ACTIVITY, ev("PostToolUse", live), cwd=plain)
    got = json.load(open(act, encoding="utf-8"))
    check(code == 0 and out == "" and got.get("state") == "working" and got.get("event") == "PostToolUse",
          "PostToolUse: a finished tool call writes {state: working} again (a long turn never reads Waiting)")
    code, out, err = run(ACTIVITY, ev("Stop", live), cwd=plain)
    code, out, err = run(ACTIVITY, ev("SessionStart", live), cwd=plain)
    check(code == 0 and json.load(open(act, encoding="utf-8")).get("state") == "idle", "any other event is ignored")
    # `since`: when the turn began — set by UserPromptSubmit, kept by PostToolUse (while working) and by Stop
    _time = __import__("time")

    def read_act():
        return json.load(open(act, encoding="utf-8"))
    t1 = _time.time()
    run(ACTIVITY, ev("UserPromptSubmit", live), cwd=plain)
    s1 = read_act()
    check(isinstance(s1.get("since"), (int, float)) and abs(s1["since"] - t1) < 15 and s1["since"] <= s1["at"],
          "since: UserPromptSubmit writes since ≈ now, never after `at` (%s)" % s1)
    _time.sleep(0.05)
    run(ACTIVITY, ev("PostToolUse", live), cwd=plain)
    s2 = read_act()
    check(s2.get("state") == "working" and s2.get("since") == s1["since"] and s2["at"] > s1["at"],
          "…a following PostToolUse keeps the same since (and moves `at`)")
    run(ACTIVITY, ev("Stop", live), cwd=plain)
    s3 = read_act()
    check(s3.get("state") == "idle" and s3.get("since") == s1["since"], "…Stop keeps the same since")
    _time.sleep(0.05)
    run(ACTIVITY, ev("PostToolUse", live), cwd=plain)
    s4 = read_act()
    check(s4.get("state") == "working" and isinstance(s4.get("since"), (int, float)) and s4["since"] >= s1["since"]
          and s4["since"] != s1["since"] and s4["since"] <= s4["at"],
          "…a PostToolUse after Stop (idle on file) starts a fresh turn: a newer since (%s)" % s4)
    with open(act, "w", encoding="utf-8") as f:
        json.dump({"state": "working", "at": 1, "event": "PostToolUse", "since": "yesterday"}, f)
    code, out, err = run(ACTIVITY, ev("PostToolUse", live), cwd=plain)
    s5 = read_act()
    check(code == 0 and isinstance(s5.get("since"), (int, float)) and not isinstance(s5.get("since"), bool),
          "…a non-number since on file does not crash PostToolUse and is replaced by a number (%s)" % s5)
    with open(act, "w", encoding="utf-8") as f:
        json.dump({"state": "working", "at": 1, "event": "UserPromptSubmit", "since": "yesterday"}, f)
    code, out, err = run(ACTIVITY, ev("UserPromptSubmit", live), cwd=plain)
    s6 = read_act()
    check(code == 0 and isinstance(s6.get("since"), (int, float)) and abs(s6["since"] - _time.time()) < 15,
          "…a non-number since does not crash UserPromptSubmit: the next one writes a numeric since (%s)" % s6)
    code, out, err = run(ACTIVITY, ev("Stop", live), cwd=plain)
    code, out, err = run(ACTIVITY, ev("UserPromptSubmit", cold), cwd=plain)
    check(code == 0 and out == "" and not os.path.exists(os.path.join(cold, ".preview")),
          "a project with no .preview/ gets no new folder (nobody has previewed it)")
    code, out, err = run(ACTIVITY, ev("UserPromptSubmit", plain), cwd=plain)
    check(code == 0 and out == "" and not os.path.exists(os.path.join(plain, ".preview")), "silent outside a pb project")
    code, out, err = run(ACTIVITY, json.dumps({"cwd": inner}) , cwd=plain)
    check(code == 0 and out == "", "no event name and no argument: silent, exit 0")
    os.makedirs(os.path.join(inner, ".prototype", ".preview"), exist_ok=True)
    code, out, err = run(ACTIVITY, ev("UserPromptSubmit", inner), cwd=plain)
    check(code == 0 and os.path.isfile(os.path.join(inner, ".prototype", ".preview", "activity.json")),
          ".prototype/ inside a repo is a pb project: its .preview/ is written")
    for stdin in ("", "not json", "[]", "null", '{"cwd": 5}'):
        code, out, err = run(ACTIVITY, stdin, cwd=plain)
        check(code == 0 and out == "", "activity.py silent, exit 0 on %r" % stdin)
    if cfg:
        hooks = cfg.get("hooks", {})
        for event in ("UserPromptSubmit", "PostToolUse", "Stop"):
            # PostToolUse also carries route.py and housekeep.py behind their own matchers (tests/hook_route.py,
            # tests/hook_housekeep.py): activity.py is the matcher-less group
            groups = [g for g in hooks.get(event, [])
                      if not any(a.endswith(("/hooks/route.py", "/hooks/housekeep.py"))
                                 for h in g.get("hooks", []) for a in h.get("args", []))]
            cmds = [h for g in groups for h in g.get("hooks", [])]
            check(len(cmds) == 1 and cmds[0].get("type") == "command" and "args" in cmds[0]
                  and any(a == "${CLAUDE_PLUGIN_ROOT}/hooks/activity.py" for a in cmds[0]["args"]),
                  "hooks.json declares %s → activity.py (an exec-style command with args)" % event)
            check(all("matcher" not in g for g in groups) and "onFailure" not in (cmds[0] if cmds else {}),
                  "  no matcher, no onFailure")

    # ------------------------------------------------------------ H4
    print("H4 · bad input never breaks anything")
    bad = ["", "not json", "[]", "null", "{}", '{"tool_input": null}', '{"tool_input": {"command": 7}}',
           '{"tool_input": {"command": ""}}', '{"cwd": 5, "tool_input": {"command": "pkill serve.py"}}']
    for stdin in bad:
        code, out, err = run(BASH, stdin, cwd=plain if stdin != bad[-1] else plain)
        check(code == 0 and out == "", "bash_advice silent, exit 0 on %r" % stdin[:40])

import shutil
shutil.rmtree(TMP_FOR_HOOKS, ignore_errors=True)
print()
if FAILS:
    print("FAILED: %d check(s)" % len(FAILS))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all hook checks passed")
