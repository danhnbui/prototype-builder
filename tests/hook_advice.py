#!/usr/bin/env python3
"""
hook_advice.py — the plugin's two advisory hooks say the right thing, in the right place, and nothing else.

pb/hooks/ puts the key operating rules in front of the model in any pb project, because a rule
written only in a command file never reached a free-form session. Checked here, with no browser:

  H1  hooks.json parses, declares SessionStart (startup|resume|clear|compact) and PreToolUse (Bash),
      and every script it names exists under ${CLAUDE_PLUGIN_ROOT}/hooks/.
  H2  session_rules.py in a pb-shaped folder (and in `.prototype/`) prints valid JSON whose
      additionalContext is at most 25 lines and 1,600 characters, names the canon, the three
      tools and `--ensure`; in a non-pb folder it prints nothing. Exit 0 always.
  H3  bash_advice.py: table-driven positives (each names the right tool) and negatives
      (normal commands, `json.load`, `json.dumps`, `slice.py` writes, `shot.py`); silent in a
      non-pb folder; output is valid JSON, never carries `permissionDecision`, exit 0.
  H5  browser_advice.py: names shot.py --no-png --eval and --selector inside a pb project, silent
      outside; speaks on the first call of a session and every 25th, not between; a broken counter
      folder is silent with exit 0; no permissionDecision; hooks.json matches the MCP tool names.
  H4  bad stdin, empty stdin, a missing command and a non-object payload print nothing and exit 0.

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
    check(len(named) == 3, "hooks.json names exactly three scripts (%s)" % ", ".join(named))
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
        check("permissionDecision" not in out, "  no permissionDecision")
    code, out, err = run(SESSION, "", cwd=pb_dir, env_extra={"CLAUDE_PLUGIN_ROOT": "/x/plugin"})
    ctx, _ = hook_json(out)
    check(ctx is not None and "/x/plugin/tools/serve.py" in ctx, "CLAUDE_PLUGIN_ROOT, when set, is the expanded root")
    for label, folder in (("no registry.json", plain), ("registry.json without render/ or constitution", half)):
        code, out, err = run(SESSION, "", cwd=folder)
        check(code == 0 and out == "", "non-pb folder (%s): silent, exit 0" % label)
    code, out, err = run(SESSION, "not json at all", cwd=pb_dir)
    check(code == 0 and hook_json(out)[0] is not None, "session_rules ignores stdin entirely")

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
        ("python3 -c \"import json; d=json.load(open('registry.json')); json.dump(d, open('registry.json','w'))\"",
         "slice.py set"),
        ("python3 -c \"open('registry.json','w').write('{}')\"", "slice.py set"),
        ("python3 -c \"from pathlib import Path; Path('registry.json').write_text('{}')\"", "slice.py set"),
        ("echo '{}' > registry.json", "slice.py set"),
        ("cat patch.json > .prototype/registry.json", "slice.py set"),
        ("jq . x | tee registry.json", "slice.py set"),
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
