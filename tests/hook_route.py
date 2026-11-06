#!/usr/bin/env python3
"""
hook_route.py — route.py forces pb's usage rules through the safe path at call time, and never decides a permission.

pb/hooks/route.py is one script for PreToolUse and PostToolUse (dispatch on hook_event_name + tool_name).
Checked here with fake payloads on stdin, in throw-away folders, with no browser and no Claude Code:

  R0  hooks.json registers it (PreToolUse "Bash|Agent|Task|Read|Edit|Write|MultiEdit|NotebookEdit",
      PostToolUse "Bash|Edit|Write|MultiEdit"); PB_AGENTS equals pb/agents/*.md; the source never
      names the decision "allow" (or "deny").
  R1  Agent/Task with no model: a full-copy updatedInput + model (haiku for Explore, else sonnet) and no
      permissionDecision in every mode but "auto", where it only advises; pb: / bare pb agents, a given
      model and a fork are left alone (a fork gets one advice line).
  R2  inline parsing of registry.json -> slice.py find / get --fields, first time and every 10th; pb tools exempt.
  R3  grep -r, rg, sed -n, cat of a big file -> Grep / Read with a limit (own counter, same rhythm).
  R4  registry write guard: stash before, validate after; a corrupted write is restored (bytes identical),
      a valid one is left alone, no stash = nothing happens, advise reports without restoring, a
      registry over 20 MB is not stashed, the stash is always deleted.
  R5  an edit in another pb project / git work tree / CLAUDE_PLUGIN_ROOT asks once per (session, root);
      scratch folders never trigger it; no session project = silent.
  R6  touch registry.json -> not needed.   R7  Read of registry.json / prototype.html with no limit -> slice.py get.
  M   doctor.json "enforce" route | advise | off, and PB_ENFORCE over it.
  A   a session started one folder above the registry (child folders; not dot-folders, not node_modules).
  L   .preview/route.log: one JSON line per action, only where .preview/ exists, trimmed past 256 KB.
  F   garbage stdin, a broken temp folder, other events: nothing printed, exit 0.
  N   "allow" is never printed, in any case above; the median of 20 runs is under 150 ms.

Usage:  python3 tests/hook_route.py
Exit:   0 = pass · 1 = a failure
"""
import ast
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "pb", "hooks")
ROUTE = os.path.join(HOOKS, "route.py")

FAILS = []
ALL_OUT = []                                            # every stdout the hook produced, for the "never allow" sweep
FIX = tempfile.mkdtemp(prefix="pb-route-fx-")           # the projects under test
STATE = tempfile.mkdtemp(prefix="pb-route-state-")      # TMPDIR of the hook: counters, ask marks and stashes live here
EXTRA_DIRS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def run(payload, env_extra=None, raw=None, cwd=None):
    """Run route.py with `payload` (a dict, or `raw` text) on stdin. -> (exit code, stdout, stderr)."""
    env = dict(os.environ)
    env["TMPDIR"] = STATE
    env["PB_ROUTE_SCRATCH"] = ""                       # no scratch folders: the fixtures live in the real temp folder
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("PB_ENFORCE", None)
    for k, v in (env_extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    stdin = raw if raw is not None else json.dumps(payload)
    p = subprocess.run([sys.executable, "-S", "-B", ROUTE], input=stdin, env=env, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    ALL_OUT.append(p.stdout)
    return p.returncode, p.stdout, p.stderr


def pre(tool, ti, cwd, sid="s1", tuid=None, mode="default"):
    p = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": ti, "cwd": cwd,
         "session_id": sid, "permission_mode": mode}
    if tuid:
        p["tool_use_id"] = tuid
    return p


def post(tool, ti, cwd, sid="s1", tuid=None):
    p = {"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": ti, "tool_response": {},
         "cwd": cwd, "session_id": sid}
    if tuid:
        p["tool_use_id"] = tuid
    return p


def hso(out):
    try:
        return json.loads(out)["hookSpecificOutput"]
    except Exception:  # noqa: BLE001
        return None


def ctx(out):
    return (hso(out) or {}).get("additionalContext")


def real(p):
    return os.path.realpath(p)


def reg_doc(**over):
    d = {"_about": "x", "meta": {"name": "demo"}, "tokens": {}, "components": [{"id": "btn"}, {"id": "card"}],
         "screens": [{"id": "home"}], "flow": {}, "erd": {}}
    d.update(over)
    return d


def dump(d):
    return (json.dumps(d, indent=2) + "\n").encode("utf-8")


def make_pb(folder, doc=None, doctor=None, preview=False):
    os.makedirs(os.path.join(folder, "render"), exist_ok=True)
    with open(os.path.join(folder, "registry.json"), "wb") as f:
        f.write(dump(doc if doc is not None else reg_doc()))
    if doctor is not None:
        os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
        with open(os.path.join(folder, "memory", "doctor.json"), "w", encoding="utf-8") as f:
            f.write(doctor if isinstance(doctor, str) else json.dumps(doctor))
    if preview:
        os.makedirs(os.path.join(folder, ".preview"), exist_ok=True)
    return folder


def set_doctor(folder, value):
    os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
    with open(os.path.join(folder, "memory", "doctor.json"), "w", encoding="utf-8") as f:
        f.write(value if isinstance(value, str) else json.dumps(value))


def read(path):
    with open(path, "rb") as f:
        return f.read()


def write(path, data):
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def state_files(tuid=None):
    d = os.path.join(STATE, "pb-hooks-%s" % (os.getuid() if hasattr(os, "getuid") else "u"))
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.startswith("route-") and f.endswith((".meta", ".stash"))
                  and (tuid is None or tuid in f))


# ------------------------------------------------------------------------------------------ fixtures
S = make_pb(os.path.join(FIX, "S"))                     # the session's project
PLAIN = os.path.join(FIX, "plain")
os.makedirs(PLAIN)
AGENT = {"description": "find x", "prompt": "look for x in the repo", "subagent_type": "general-purpose",
         "run_in_background": True}

# ------------------------------------------------------------------------------------------ R0
print("R0 · registration, agent list, no decision but ask")
try:
    with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:  # noqa: BLE001
    cfg = {}
    check(False, "hooks.json parses (%s)" % e)


def groups(event):
    return [g for g in cfg.get("hooks", {}).get(event, [])
            if any(a.endswith("/hooks/route.py") for h in g.get("hooks", []) for a in h.get("args", []))]


pre_g, post_g = groups("PreToolUse"), groups("PostToolUse")
check(len(pre_g) == 1 and pre_g[0].get("matcher") == "Bash|Agent|Task|Read|Edit|Write|MultiEdit|NotebookEdit",
      "PreToolUse registers route.py for Bash|Agent|Task|Read|Edit|Write|MultiEdit|NotebookEdit")
check(len(post_g) == 1 and post_g[0].get("matcher") == "Bash|Edit|Write|MultiEdit",
      "PostToolUse registers route.py for Bash|Edit|Write|MultiEdit")
for g in pre_g + post_g:
    for h in g["hooks"]:
        check(h.get("type") == "command" and h.get("command") == "python3"
              and h.get("args", [])[:2] == ["-S", "-B"] and "onFailure" not in h and isinstance(h.get("timeout"), int),
              "  an exec-style `python3 -S -B` command with a timeout, no onFailure")
desc = cfg.get("description", "")
check("never denies" in desc and "never auto-approves" in desc, "hooks.json description says it never denies and never auto-approves")
check(os.path.isfile(ROUTE), "pb/hooks/route.py exists")
sys.dont_write_bytecode = True                          # importing the hook must not leave a __pycache__ in pb/hooks/
sys.path.insert(0, HOOKS)
import route  # noqa: E402
names = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, "pb", "agents")) if f.endswith(".md"))
check(sorted(route.PB_AGENTS) == names and len(names) == 9, "PB_AGENTS equals pb/agents/*.md (%s)" % ", ".join(names))
with open(ROUTE, encoding="utf-8") as f:
    tree = ast.parse(f.read())
consts = [getattr(n, "value", getattr(n, "s", None)) for n in ast.walk(tree)
          if isinstance(n, getattr(ast, "Constant", ())) or n.__class__.__name__ == "Str"]
check("allow" not in consts and "deny" not in consts, 'the source has no "allow" or "deny" string constant')
check("ask" in consts, 'the only decision constant is "ask"')

# ------------------------------------------------------------------------------------------ R1
print("R1 · subagent calls set a model")
for mode in ("default", "acceptEdits", "plan", "bypassPermissions", "dontAsk"):
    code, out, err = run(pre("Agent", AGENT, S, mode=mode))
    h = hso(out)
    check(code == 0 and h is not None and h.get("updatedInput") == dict(AGENT, model="sonnet")
          and "permissionDecision" not in h and h.get("hookEventName") == "PreToolUse",
          "permission_mode %s: updatedInput is a full copy + model=sonnet, no permissionDecision" % mode)
check("model=sonnet" in (ctx(out) or "") and "\n" not in (ctx(out) or ""), "  one additionalContext line says what was set")
code, out, err = run(pre("Agent", dict(AGENT, subagent_type="Explore"), S))
check((hso(out) or {}).get("updatedInput") == dict(AGENT, subagent_type="Explore", model="haiku"), "Explore gets model=haiku")
no_type = {k: v for k, v in AGENT.items() if k != "subagent_type"}
code, out, err = run(pre("Task", no_type, S))
check((hso(out) or {}).get("updatedInput") == dict(no_type, model="sonnet"), "Task with no subagent_type gets sonnet")
code, out, err = run(pre("Agent", dict(AGENT, model=""), S))
check((hso(out) or {}).get("updatedInput") == dict(AGENT, model="sonnet"), "an empty model counts as none")
for st in ("other-plugin:some-agent", "project-agent"):
    code, out, err = run(pre("Agent", dict(AGENT, subagent_type=st), S))
    check(code == 0 and out.strip() == "",
          "a named agent (%s) may pin its own model in frontmatter: left untouched" % st)
code, out, err = run(pre("Agent", dict(AGENT, subagent_type="Plan"), S))
check((hso(out) or {}).get("updatedInput") == dict(AGENT, subagent_type="Plan", model="sonnet"),
      "the built-in Plan type gets sonnet")
AUTO = "pb: set model on Agent calls (sonnet; haiku for Explore) — this one runs on the session model"
code, out, err = run(pre("Agent", AGENT, S, mode="auto"))
h = hso(out)
check(code == 0 and h is not None and "updatedInput" not in h and "permissionDecision" not in h and h.get("additionalContext") == AUTO,
      "permission_mode auto: no rewrite (the classifier would block it), one advice line")
code, out, err = run(pre("Agent", dict(AGENT, subagent_type="Explore"), S, mode="auto"))
check("updatedInput" not in (hso(out) or {}) and ctx(out) == AUTO, "  auto + Explore: the same advice")
for st in ["pb:pb-builder", "pb:pb-explorer", "pb:anything"] + sorted(route.PB_AGENTS):
    code, out, err = run(pre("Agent", dict(AGENT, subagent_type=st), S))
    check(code == 0 and out == "", "pb agent %s: untouched, silent" % st)
code, out, err = run(pre("Agent", dict(AGENT, model="opus"), S))
check(code == 0 and out == "", "a call that names a model: untouched, silent")
for mode in ("default", "auto"):
    code, out, err = run(pre("Agent", dict(AGENT, subagent_type="fork"), S, mode=mode))
    h = hso(out)
    check(h is not None and "updatedInput" not in h and "permissionDecision" not in h and "fork" in h.get("additionalContext", ""),
          "fork (%s): one advice line, no rewrite" % mode)
code, out, err = run(pre("Agent", AGENT, PLAIN))
check(code == 0 and out == "", "outside a pb project: silent")
code, out, err = run(pre("Agent", {}, S))
check(code == 0 and out == "", "an empty tool_input is never rewritten")

# ------------------------------------------------------------------------------------------ R2 / R3 / R6
print("R2 · inline parse of registry.json")
R2_POS = [
    "python3 -c \"import json; d=json.load(open('registry.json')); print(d['meta'])\"",
    "python3 - <<'EOF'\nimport json\nd = json.load(open('.prototype/registry.json'))\nEOF",
    "python3 <<EOF\nimport json; json.loads(open('registry.json').read())\nEOF",
    "jq '.screens | length' registry.json",
    "cat registry.json | head -50",
    "cat .prototype/registry.json",
    "python3.11 -c \"import pathlib, json; json.loads(pathlib.Path('registry.json').read_text())\"",
]
for i, cmd in enumerate(R2_POS):
    code, out, err = run(pre("Bash", {"command": cmd}, S, sid="r2-%d" % i))
    c = ctx(out) or ""
    check(code == 0 and "slice.py find" in c and "--fields" in c and "permissionDecision" not in (hso(out) or {}),
          "advises slice.py find / get --fields: %s" % cmd.splitlines()[0][:60])
R2_NEG = [
    "python3 /x/pb/tools/slice.py get meta name",
    "python3 ${CLAUDE_PLUGIN_ROOT}/tools/slice.py find card",
    "python3 pb/tools/lint_registry.py registry.json",
    "python3 pb/tools/render.py registry.json",
    "python3 pb/tools/slice.py get meta name | python3 -c \"import json,sys; json.load(sys.stdin)\"; cat registry.json",
    "ls -la", "git status", "python3 build.py registry.json", "python3 -c \"print(1)\"", "echo registry.json",
]
for i, cmd in enumerate(R2_NEG):
    code, out, err = run(pre("Bash", {"command": cmd}, S, sid="r2n-%d" % i))
    check(code == 0 and out == "", "silent: %s" % cmd.splitlines()[0][:70])
code, out, err = run(pre("Bash", {"command": R2_POS[0]}, PLAIN, sid="r2-plain"))
check(code == 0 and out == "", "silent outside a pb project")
spoke = [i for i in range(1, 22) if ctx(run(pre("Bash", {"command": R2_POS[0]}, S, sid="r2-rate"))[1])]
check(spoke == [1, 10, 20], "speaks on the 1st use in a session, then every 10th (%s)" % spoke)

print("R3 · grep -r / rg / sed -n / cat of a big file")
write(os.path.join(S, "big.txt"), "x" * (300 * 1024))
write(os.path.join(S, "small.txt"), "x" * 100)
R3_POS = ["grep -rn \"foo\" .", "grep -R foo src", "grep -ir foo .", "egrep -r 'a|b' .", "rg foo", "cd x && rg -n foo",
          "sed -n '1,40p' render/screens/home.js", "cat big.txt", "cat big.txt | head -5", "cat -n big.txt"]
for i, cmd in enumerate(R3_POS):
    code, out, err = run(pre("Bash", {"command": cmd}, S, sid="r3-%d" % i))
    c = ctx(out) or ""
    check(code == 0 and "Grep tool" in c and "Read tool" in c and "permissionDecision" not in (hso(out) or {}),
          "advises the Grep / Read tools: %s" % cmd[:60])
R3_NEG = ["grep foo file.txt", "grep -n foo file.txt", "git grep -n foo", "sed -i 's/a/b/' f", "sed 's/a/b/' f", "cat small.txt",
          "cat > notes.txt <<EOF\nhi\nEOF", "echo rg", "ls -la", "python3 pb/tools/shot.py registry.json --eval \"1\"",
          "python3 pb/tools/slice.py get meta name | grep -r x ."]
for i, cmd in enumerate(R3_NEG):
    code, out, err = run(pre("Bash", {"command": cmd}, S, sid="r3n-%d" % i))
    check(code == 0 and out == "", "silent: %s" % cmd.splitlines()[0][:70])
code, out, err = run(pre("Bash", {"command": "rg foo"}, PLAIN, sid="r3-plain"))
check(code == 0 and out == "", "silent outside a pb project")
spoke = [i for i in range(1, 22) if ctx(run(pre("Bash", {"command": "rg foo"}, S, sid="r3-rate"))[1])]
check(spoke == [1, 10, 20], "rule 3 speaks on the 1st use, then every 10th (%s)" % spoke)
code, out, err = run(pre("Bash", {"command": "rg foo"}, S, sid="r2-rate"))
check(ctx(out) is not None, "  its counter is its own: the session that used up rule 2 still hears rule 3 first time")

print("R6 · touch registry.json")
TOUCH = "pb: not needed — the preview reloads on registry.json, render/, runtime/, spec/ and logic/ changes."
for cmd in ("touch registry.json", "touch .prototype/registry.json && echo x", "cd p && touch registry.json"):
    code, out, err = run(pre("Bash", {"command": cmd}, S, sid="r6"))
    check(code == 0 and ctx(out) == TOUCH and "permissionDecision" not in hso(out), "says not needed (every time): %s" % cmd)
code, out, err = run(pre("Bash", {"command": "touch notes.txt"}, S, sid="r6"))
check(code == 0 and out == "", "touch of another file: silent")
code, out, err = run(pre("Bash", {"command": "touch registry.json"}, PLAIN, sid="r6"))
check(code == 0 and out == "", "touch outside a pb project: silent")

# ------------------------------------------------------------------------------------------ R7
print("R7 · Read of registry.json / prototype.html with no limit")
for rel in ("registry.json", "prototype.html", "design-system.html"):
    code, out, err = run(pre("Read", {"file_path": os.path.join(S, rel)}, S))
    c = ctx(out) or ""
    check(code == 0 and "slice.py get" in c and "--fields" in c and "permissionDecision" not in hso(out),
          "advises slice.py get --fields: Read %s" % rel)
code, out, err = run(pre("Read", {"file_path": "registry.json"}, S))
check("slice.py get" in (ctx(out) or ""), "a relative path is resolved against cwd")
code, out, err = run(pre("Read", {"file_path": os.path.join(S, "render", "deep", "prototype.html")}, PLAIN))
check("slice.py get" in (ctx(out) or ""), "the project is found by walking up from the target (cwd outside it)")
for ti in ({"file_path": os.path.join(S, "registry.json"), "limit": 100},
           {"file_path": os.path.join(S, "registry.json"), "offset": 10, "limit": 50},
           {"file_path": os.path.join(S, "notes.md")},
           {"file_path": os.path.join(PLAIN, "registry.json")}):
    code, out, err = run(pre("Read", ti, S))
    check(code == 0 and out == "", "silent: %s" % json.dumps({k: (os.path.basename(v) if k == "file_path" else v) for k, v in ti.items()}))

# ------------------------------------------------------------------------------------------ R4
print("R4 · registry write guard")
RW = make_pb(os.path.join(FIX, "rw"))
REGP = os.path.join(RW, "registry.json")
ORIG = read(REGP)
VALID_NEW = dump(reg_doc(meta={"name": "renamed"}))
BASH_WRITE = "python3 -c \"import json; d=json.load(open('registry.json')); json.dump(d, open('registry.json','w'))\""


def guarded(tool, ti, mutate, tuid, sid="g1", env=None, cwd=None, raw_pre=None):
    cwd = cwd or RW
    code, pre_out, _ = run(pre(tool, ti, cwd, sid=sid, tuid=tuid), env_extra=env)
    stashed = state_files(tuid)
    mutate()
    code2, post_out, _ = run(post(tool, ti, cwd, sid=sid, tuid=tuid), env_extra=env)
    return pre_out, post_out, stashed, state_files(tuid)


# a corrupted Bash write is restored byte for byte
write(REGP, ORIG)
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(REGP, b"{broken"), "tu-corrupt")
check(len(stashed) == 2, "Bash write: the registry is stashed before it (a .stash and a .meta)")
check("slice.py set" in (ctx(pre_out) or "") and "restored" in (ctx(pre_out) or ""), "  the Pre call advises slice.py set")
check(ctx(post_out) == "pb: registry.json was invalid after this write (not valid JSON); restored the previous version. Use slice.py set.",
      "  Post: says it was invalid and restored (%s)" % ctx(post_out))
check(read(REGP) == ORIG, "  the registry is byte-identical to before")
check(left == [], "  the stash is deleted")
check(hso(post_out).get("hookEventName") == "PostToolUse" and "permissionDecision" not in hso(post_out), "  PostToolUse output, no decision")
check(not [f for f in os.listdir(RW) if f.endswith(".tmp")], "  no temp file left beside the registry")

# a valid write is left alone
write(REGP, ORIG)
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(REGP, VALID_NEW), "tu-valid")
check(len(stashed) == 2 and post_out == "" and read(REGP) == VALID_NEW and left == [],
      "a valid write: stashed, Post silent, the new file kept, stash deleted")

# the Edit tool: lost key, array top level, new duplicate ids, a missing file
CASES = [
    ("a top-level key lost", lambda: write(REGP, dump({k: v for k, v in reg_doc().items() if k != "screens"})),
     "top-level key lost: screens"),
    ("an array at the top level", lambda: write(REGP, b"[1, 2]"), "the top level is not an object"),
    ("a new duplicate id in components", lambda: write(REGP, dump(reg_doc(components=[{"id": "btn"}, {"id": "btn"}]))),
     "duplicate id in components/screens: components:btn"),
    ("a new duplicate id in screens", lambda: write(REGP, dump(reg_doc(screens=[{"id": "home"}, {"id": "home"}]))),
     "duplicate id in components/screens: screens:home"),
    ("an empty file", lambda: write(REGP, b""), "not valid JSON"),
    ("the file deleted", lambda: os.unlink(REGP), "file missing"),
]
for tool in ("Edit", "Write", "MultiEdit"):
    for label, mutate, reason in CASES[:1] if tool != "Edit" else CASES:
        write(REGP, ORIG)
        tuid = "tu-%s-%s" % (tool, reason[:8].replace(" ", "_"))
        ti = {"file_path": REGP, "old_string": "a", "new_string": "b"}
        pre_out, post_out, stashed, left = guarded(tool, ti, mutate, tuid)
        check(len(stashed) == 2 and ("(%s)" % reason) in (ctx(post_out) or "") and read(REGP) == ORIG and left == [],
              "%s: %s -> restored, stash deleted" % (tool, label))
check(ctx(pre_out) is None, "an Edit of registry.json gets no Pre advice (only the guard)")

# duplicate ids the file already had are not the write's doing
DUP_DOC = reg_doc(components=[{"id": "btn"}, {"id": "btn"}])
write(REGP, dump(DUP_DOC))
NEW_DUP = dump(dict(DUP_DOC, meta={"name": "other"}))
pre_out, post_out, stashed, left = guarded("Edit", {"file_path": REGP, "old_string": "a", "new_string": "b"},
                                           lambda: write(REGP, NEW_DUP), "tu-olddup")
check(post_out == "" and read(REGP) == NEW_DUP, "duplicates that were already there are left alone")

# no stash: nothing happens, even to a broken file
write(REGP, b"{garbage")
code, out, err = run(post("Bash", {"command": BASH_WRITE}, RW, tuid="tu-never-stashed"))
check(code == 0 and out == "" and read(REGP) == b"{garbage", "no stash (Post alone): silent, the file is not touched")
write(REGP, ORIG)
before_files = state_files()
code, out, err = run(pre("Bash", {"command": BASH_WRITE}, RW))               # no tool_use_id
check("slice.py set" in (ctx(out) or "") and "restored" not in (ctx(out) or "") and state_files() == before_files,
      "no tool_use_id: advice (without promising a restore) but no stash")

# not guarded: slice.py runs, pb tools, plain reads, a project-less registry
for label, cmd in (("slice.py in the command", "echo '{}' > registry.json  # slice.py"),
                   ("a pb tool", "python3 pb/tools/slice.py set meta name --patch p.json > registry.json"),
                   ("a read", "python3 -c \"import json; json.load(open('registry.json'))\"")):
    tuid = "tu-ng-" + label[:5].replace(" ", "_")
    code, out, err = run(pre("Bash", {"command": cmd}, RW, tuid=tuid))
    check(state_files(tuid) == [], "no stash: %s" % label)
other = os.path.join(FIX, "not-pb")
os.makedirs(other)
write(os.path.join(other, "registry.json"), b"{}")
code, out, err = run(pre("Edit", {"file_path": os.path.join(other, "registry.json")}, PLAIN, tuid="tu-notpb"))
check(state_files("tu-notpb") == [], "no stash for a registry.json outside a pb project")
code, out, err = run(pre("NotebookEdit", {"notebook_path": REGP}, RW, tuid="tu-nb"))
check(state_files("tu-nb") == [], "no stash for NotebookEdit")

# advise: report, do not restore
set_doctor(RW, {"enforce": "advise"})
write(REGP, ORIG)
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(REGP, b"{broken"), "tu-advise")
check("restored" not in (ctx(pre_out) or "") and "slice.py set" in (ctx(pre_out) or ""), "enforce=advise: the Pre advice does not promise a restore")
check("not restored" in (ctx(post_out) or "") and "not valid JSON" in (ctx(post_out) or "") and read(REGP) == b"{broken" and left == [],
      "  Post reports, does not restore, still deletes the stash")
# off: no stash at all
set_doctor(RW, {"enforce": "off"})
write(REGP, ORIG)
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(REGP, b"{broken"), "tu-off")
check(pre_out == "" and stashed == [] and post_out == "" and read(REGP) == b"{broken", "enforce=off: nothing stashed, nothing said, nothing restored")
# PB_ENFORCE over doctor.json
write(REGP, ORIG)
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(REGP, b"{broken"), "tu-envroute",
                                           env={"PB_ENFORCE": "route"})
check("restored the previous version" in (ctx(post_out) or "") and read(REGP) == ORIG, "PB_ENFORCE=route overrides doctor.json off")
os.unlink(os.path.join(RW, "memory", "doctor.json"))

# the registry written from a folder above it, by a relative path and by a bare name
ABOVE = os.path.join(FIX, "above")
PROJ = make_pb(os.path.join(ABOVE, "proj"))
PREG = os.path.join(PROJ, "registry.json")
PORIG = read(PREG)
for cmd, label, tuid in (("echo '{' > proj/registry.json", "a relative path", "tu-above-rel"),
                         ("echo '{' > registry.json", "a bare name", "tu-above-bare")):
    write(PREG, PORIG)
    pre_out, post_out, stashed, left = guarded("Bash", {"command": cmd}, lambda: write(PREG, b"{"), tuid, cwd=ABOVE)
    check(len(stashed) == 2 and "restored" in (ctx(post_out) or "") and read(PREG) == PORIG,
          "session one folder above: %s resolves to the project's registry and is restored" % label)

# a registry over 20 MB is not stashed
BIGP = make_pb(os.path.join(FIX, "bigreg"), doc=reg_doc())
with open(os.path.join(BIGP, "registry.json"), "wb") as f:
    f.write(b'{"meta": {}, "pad": "' + b"x" * (21 * 1024 * 1024) + b'"}')
pre_out, post_out, stashed, left = guarded("Bash", {"command": BASH_WRITE}, lambda: write(os.path.join(BIGP, "registry.json"), b"{"),
                                           "tu-big", cwd=BIGP)
check(stashed == [] and post_out == "" and "slice.py set" in (ctx(pre_out) or "") and "restored" not in (ctx(pre_out) or ""),
      "a registry over 20 MB: advice only, no stash, nothing restored")
shutil.rmtree(BIGP, ignore_errors=True)

# a stash a failed tool call left behind is swept an hour later
old_stash = os.path.join(STATE, "pb-hooks-%s" % os.getuid(), "route-old-x-0.stash")
write(old_stash, b"{}")
os.utime(old_stash, (time.time() - 7200, time.time() - 7200))
write(REGP, ORIG)
guarded("Bash", {"command": BASH_WRITE}, lambda: None, "tu-sweep")
check(not os.path.exists(old_stash), "a stash older than an hour is swept when the next one is made")

# ------------------------------------------------------------------------------------------ R5
print("R5 · edits in another project ask once")
O = make_pb(os.path.join(FIX, "O"))
O2 = make_pb(os.path.join(FIX, "O2"))
G = os.path.join(FIX, "G")
os.makedirs(os.path.join(G, ".git"))
os.makedirs(os.path.join(G, "src"))
ADOPT = os.path.join(FIX, "adopt")
make_pb(os.path.join(ADOPT, ".prototype"))
os.makedirs(os.path.join(ADOPT, ".git"))
os.makedirs(os.path.join(ADOPT, "src"))
TARGET = {"file_path": os.path.join(O, "render", "x.js"), "old_string": "a", "new_string": "b"}
code, out, err = run(pre("Edit", TARGET, S, sid="x1"))
h = hso(out)
check(code == 0 and h is not None and h.get("permissionDecision") == "ask"
      and h.get("permissionDecisionReason") == "pb: this edits %s from %s" % (real(O), real(S)),
      "first edit in another pb project: ask, reason names both roots (%s)" % (h or {}).get("permissionDecisionReason"))
code, out, err = run(pre("Edit", TARGET, S, sid="x1"))
check(code == 0 and out == "", "  the same root again, same session: silent")
code, out, err = run(pre("Write", {"file_path": os.path.join(O, "notes.md"), "content": "x"}, S, sid="x1"))
check(code == 0 and out == "", "  any other file in that root: silent")
code, out, err = run(pre("Write", {"file_path": os.path.join(O2, "a.md"), "content": "x"}, S, sid="x1"))
check((hso(out) or {}).get("permissionDecision") == "ask" and real(O2) in hso(out)["permissionDecisionReason"], "a different root asks again")
code, out, err = run(pre("Edit", TARGET, S, sid="x2"))
check((hso(out) or {}).get("permissionDecision") == "ask", "a new session asks again")
code, out, err = run(pre("Edit", {"file_path": os.path.join(G, "src", "a.ts")}, S, sid="x1"))
check((hso(out) or {}).get("permissionDecision") == "ask" and real(G) in hso(out)["permissionDecisionReason"],
      "a git work tree that is not the session's asks")
code, out, err = run(pre("MultiEdit", {"file_path": os.path.join(G, "src", "b.ts"), "edits": []}, S, sid="x1"))
check(out == "", "  (MultiEdit in the same root: silent)")
code, out, err = run(pre("NotebookEdit", {"notebook_path": os.path.join(O, "n.ipynb")}, S, sid="x3"))
check((hso(out) or {}).get("permissionDecision") == "ask", "NotebookEdit is covered (notebook_path)")
code, out, err = run(pre("MultiEdit", {"file_path": os.path.join(O, "m.js"), "edits": []}, S, sid="x4"))
check((hso(out) or {}).get("permissionDecision") == "ask", "MultiEdit is covered")
os.makedirs(os.path.join(O, "render"), exist_ok=True)
code, out, err = run(pre("Edit", {"file_path": "../O/render/rel.js"}, S, sid="x5"), cwd=PLAIN)
check((hso(out) or {}).get("permissionDecision") == "ask" and real(O) in hso(out)["permissionDecisionReason"],
      "a relative path resolves against the payload's cwd (not the process folder)")
for label, ti, cwd in (
        ("a file inside the session project", {"file_path": os.path.join(S, "render", "a.js")}, S),
        ("a new file in a folder that does not exist yet, inside the project", {"file_path": os.path.join(S, "n", "e", "w.js")}, S),
        ("the repo around an adopt-in-place .prototype/", {"file_path": os.path.join(ADOPT, "src", "a.ts")}, ADOPT),
        ("the .prototype/ itself", {"file_path": os.path.join(ADOPT, ".prototype", "render", "a.js")}, ADOPT),
        ("a folder that is neither a project nor a git tree", {"file_path": os.path.join(PLAIN, "a.md")}, S),
        ("no session project (cwd outside any)", {"file_path": os.path.join(O, "a.js")}, PLAIN)):
    code, out, err = run(pre("Edit", ti, cwd, sid="x-same-" + label[:6]))
    check(code == 0 and out == "", "silent: %s" % label)
code, out, err = run(pre("Edit", {"file_path": os.path.join(O, "a.js")}, ABOVE, sid="x-above"))
check((hso(out) or {}).get("permissionDecision") == "ask" and real(PROJ) in hso(out)["permissionDecisionReason"],
      "session one folder above: the single child is the session project")
AMBIG = os.path.join(FIX, "ambig")
make_pb(os.path.join(AMBIG, "c1"))
make_pb(os.path.join(AMBIG, "c2"))
code, out, err = run(pre("Edit", {"file_path": os.path.join(O, "a.js")}, AMBIG, sid="x-ambig"))
check(code == 0 and out == "", "two child projects: no single session project, silent")
PLUGIN = os.path.join(FIX, "plugin")
os.makedirs(os.path.join(PLUGIN, "hooks"))
code, out, err = run(pre("Edit", {"file_path": os.path.join(PLUGIN, "hooks", "route.py")}, S, sid="x-plug"),
                     env_extra={"CLAUDE_PLUGIN_ROOT": PLUGIN})
check((hso(out) or {}).get("permissionDecision") == "ask" and real(PLUGIN) in hso(out)["permissionDecisionReason"],
      "a target under CLAUDE_PLUGIN_ROOT counts as a different root")
code, out, err = run(pre("Edit", {"file_path": os.path.join(PLUGIN, "hooks", "route.py")}, S, sid="x-plug2"))
check(out == "", "  (without CLAUDE_PLUGIN_ROOT that folder is not a root at all)")
# scratch folders
code, out, err = run(pre("Edit", TARGET, S, sid="x-tmp"), env_extra={"PB_ROUTE_SCRATCH": None, "TMPDIR": FIX})
check(code == 0 and out == "", "the temp folder (TMPDIR) is scratch: an edit there never asks")
code, out, err = run(pre("Edit", TARGET, S, sid="x-tmp2"), env_extra={"PB_ROUTE_SCRATCH": FIX})
check(code == 0 and out == "", "  (and so is any folder PB_ROUTE_SCRATCH names)")
code, out, err = run(pre("Edit", TARGET, S, sid="x-tmp3"), env_extra={"PB_ROUTE_SCRATCH": os.path.join(FIX, "elsewhere")})
check((hso(out) or {}).get("permissionDecision") == "ask", "  (control: the same edit asks when its folder is not scratch)")
if os.path.isdir("/tmp"):
    slash = tempfile.mkdtemp(dir="/tmp", prefix="pb-route-slash-")
    EXTRA_DIRS.append(slash)
    make_pb(os.path.join(slash, "P"))
    os.makedirs(os.path.join(slash, "P", ".git"))
    tgt = {"file_path": os.path.join(slash, "P", "render", "a.js")}
    code, out, err = run(pre("Edit", tgt, S, sid="x-slash"), env_extra={"PB_ROUTE_SCRATCH": None})
    check(code == 0 and out == "", "/tmp is scratch: an edit of a project there never asks")
    code, out, err = run(pre("Edit", tgt, S, sid="x-slash2"))
    check((hso(out) or {}).get("permissionDecision") == "ask", "  (control: it asks once /tmp is not scratch)")
for d in ("/private/tmp",):
    if os.path.isdir(d):
        pt = tempfile.mkdtemp(dir=d, prefix="pb-route-ptmp-")
        EXTRA_DIRS.append(pt)
        make_pb(os.path.join(pt, "P"))
        code, out, err = run(pre("Edit", {"file_path": os.path.join(pt, "P", "a.js")}, S, sid="x-ptmp"),
                             env_extra={"PB_ROUTE_SCRATCH": None})
        check(code == 0 and out == "", "/private/tmp is scratch too")

# ------------------------------------------------------------------------------------------ M
print("M · enforce modes")
MP = make_pb(os.path.join(FIX, "modes"))
AG_ONLY = [("Agent", AGENT), ("Bash", {"command": "touch registry.json"})]
set_doctor(MP, {"enforce": "advise"})
code, out, err = run(pre("Agent", AGENT, MP))
h = hso(out)
check(h is not None and "updatedInput" not in h and "permissionDecision" not in h and "model" in h["additionalContext"],
      "advise: the rewrite becomes an additionalContext line")
code, out, err = run(pre("Edit", {"file_path": os.path.join(O, "a.js")}, MP, sid="m-adv"))
h = hso(out)
check(h is not None and "permissionDecision" not in h and h.get("additionalContext") == "pb: this edits %s from %s" % (real(O), real(MP)),
      "advise: the ask becomes an additionalContext line")
code, out, err = run(pre("Bash", {"command": "touch registry.json"}, MP, sid="m-adv"))
check(ctx(out) == TOUCH, "advise: plain advice (rule 6) still speaks")
set_doctor(MP, {"enforce": "off"})
for tool, ti in AG_ONLY + [("Read", {"file_path": os.path.join(MP, "registry.json")}), ("Bash", {"command": R2_POS[0]})]:
    code, out, err = run(pre(tool, ti, MP, sid="m-off"))
    check(code == 0 and out == "", "off: %s prints nothing" % tool)
code, out, err = run(pre("Edit", {"file_path": os.path.join(O, "a.js")}, MP, sid="m-off"))
check(code == 0 and out == "", "off: no ask either")
code, out, err = run(pre("Agent", AGENT, MP), env_extra={"PB_ENFORCE": "route"})
check((hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "PB_ENFORCE=route overrides doctor.json off")
set_doctor(MP, {"enforce": "route"})
code, out, err = run(pre("Agent", AGENT, MP), env_extra={"PB_ENFORCE": "off"})
check(code == 0 and out == "", "PB_ENFORCE=off overrides doctor.json route")
code, out, err = run(pre("Agent", AGENT, MP), env_extra={"PB_ENFORCE": "advise"})
check("updatedInput" not in (hso(out) or {}) and "model" in (ctx(out) or ""), "PB_ENFORCE=advise overrides doctor.json route")
set_doctor(MP, {"enforce": "advise"})
code, out, err = run(pre("Agent", AGENT, MP), env_extra={"PB_ENFORCE": "bogus"})
check("updatedInput" not in (hso(out) or {}) and "model" in (ctx(out) or ""), "an unknown PB_ENFORCE is ignored (doctor.json advise holds)")
for doctor in ("not json", "[]", '{"enforce": "bogus"}', '{"enforce": 5}', "{}"):
    set_doctor(MP, doctor)
    code, out, err = run(pre("Agent", AGENT, MP))
    check((hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "doctor.json %r: the default (route)" % doctor)
os.unlink(os.path.join(MP, "memory", "doctor.json"))
code, out, err = run(pre("Agent", AGENT, MP))
check((hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "no doctor.json: the default (route)")

# ------------------------------------------------------------------------------------------ A
print("A · a session started one folder above the registry")
code, out, err = run(pre("Agent", AGENT, ABOVE))
check((hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "rule 1 applies")
code, out, err = run(pre("Bash", {"command": "python3 -c \"import json; json.load(open('proj/registry.json'))\""}, ABOVE, sid="a1"))
check("slice.py find" in (ctx(out) or ""), "rule 2 applies")
code, out, err = run(pre("Read", {"file_path": os.path.join(PROJ, "registry.json")}, ABOVE))
check("slice.py get" in (ctx(out) or ""), "rule 7 applies (walk up from the target)")
os.makedirs(os.path.join(ABOVE, ".hidden"))
make_pb(os.path.join(ABOVE, ".hidden", "p2"))
make_pb(os.path.join(ABOVE, "node_modules", "p3"))
ABOVE2 = os.path.join(FIX, "above2")
make_pb(os.path.join(ABOVE2, "node_modules", "p3"))
make_pb(os.path.join(ABOVE2, ".hidden", "p2"))
code, out, err = run(pre("Agent", AGENT, ABOVE2))
check(code == 0 and out == "", "dot-folders and node_modules are not scanned")
ADOPTUP = os.path.join(FIX, "adoptup")
make_pb(os.path.join(ADOPTUP, "repo", ".prototype"))
code, out, err = run(pre("Agent", AGENT, ADOPTUP))
check((hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "a child's .prototype/ counts")
GRAND = os.path.join(FIX, "grand")
make_pb(os.path.join(GRAND, "a", "b"))
code, out, err = run(pre("Agent", AGENT, GRAND))
check(code == 0 and out == "", "one level only: a grandchild is not found")

# ------------------------------------------------------------------------------------------ L
print("L · .preview/route.log")
LP = make_pb(os.path.join(FIX, "logged"), preview=True)
LOG = os.path.join(LP, ".preview", "route.log")
code, out, err = run(pre("Bash", {"command": "touch registry.json"}, LP, sid="l1"))
code, out, err = run(pre("Agent", AGENT, LP, sid="l1"))
lines = read(LOG).decode("utf-8").splitlines() if os.path.isfile(LOG) else []
rows = [json.loads(x) for x in lines]
check(len(rows) == 2 and [r["rule"] for r in rows] == [6, 1] and rows[1]["action"] == "rewrite" and rows[0]["sid"] == "l1"
      and all({"t", "event", "tool", "rule", "action"} <= set(r) for r in rows),
      "one JSON line per action, with time, session, tool, rule and action")
check("registry.json" not in read(LOG).decode("utf-8"), "  the log never holds the command text")
NOLOG = make_pb(os.path.join(FIX, "nolog"))
run(pre("Bash", {"command": "touch registry.json"}, NOLOG, sid="l2"))
check(not os.path.exists(os.path.join(NOLOG, ".preview")), "no .preview/: no log and no folder made")
write(LOG, "".join(json.dumps({"t": i, "pad": "p" * 90}) + "\n" for i in range(3000)))
before_size = os.path.getsize(LOG)
run(pre("Agent", AGENT, LP, sid="l3"))
size = os.path.getsize(LOG)
rows = read(LOG).decode("utf-8").splitlines()
ok_json = True
try:
    parsed = [json.loads(x) for x in rows]
except ValueError:
    ok_json = False
check(before_size > 256 * 1024 and 100 * 1024 < size <= 129 * 1024 and ok_json and parsed[-1].get("sid") == "l3",
      "past 256 KB it is trimmed to its last ~128 KB, whole lines, newest last (%d -> %d bytes)" % (before_size, size))

# ------------------------------------------------------------------------------------------ F
print("F · fail open")
GARBAGE = ["", "not json", "[]", "null", "5", '"x"', "{}", '{"hook_event_name": "PreToolUse"}',
           '{"hook_event_name": "PreToolUse", "tool_name": 5}', '{"hook_event_name": "PostToolUse", "tool_name": "Bash"}',
           '{"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": 5, "cwd": 5}',
           '{"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": 7}, "cwd": "%s"}' % S,
           '{"hook_event_name": "PreToolUse", "tool_name": "Edit", "tool_input": {"file_path": 7}, "cwd": "%s"}' % S,
           '{"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": null, "cwd": "%s"}' % S,
           '{"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {}, "tool_use_id": 5, "cwd": "%s"}' % S,
           '{"hook_event_name": "SessionStart", "tool_name": "Bash", "cwd": "%s"}' % S,
           '{"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"x": 1}, "cwd": "/nonexistent/%s"}' % ("x" * 50)]
for stdin in GARBAGE:
    code, out, err = run(None, raw=stdin)
    check(code == 0 and out == "", "silent, exit 0 on %r" % stdin[:60])
for tool in ("Grep", "WebFetch", "mcp__x__y"):
    code, out, err = run(pre(tool, {"pattern": "x"}, S))
    check(code == 0 and out == "", "a tool it does not handle (%s): silent" % tool)
code, out, err = run(None, raw=json.dumps(pre("Agent", AGENT, S)), env_extra={"TMPDIR": "/nonexistent/none"})
check(code == 0 and (hso(out) or {}).get("updatedInput", {}).get("model") == "sonnet", "a missing temp folder does not stop rule 1")
broken = os.path.join(FIX, "broken-tmp")                # a temp folder whose per-user state folder is a file
os.makedirs(broken)
write(os.path.join(broken, "pb-hooks-%s" % os.getuid()), b"x")
code, out, err = run(pre("Bash", {"command": R2_POS[0]}, S, sid="f-broken"), env_extra={"TMPDIR": broken})
check(code == 0 and out == "", "a broken state folder: rate-limited advice stays silent, exit 0")
code, out, err = run(pre("Bash", {"command": BASH_WRITE}, RW, tuid="tu-brokenstate"), env_extra={"TMPDIR": broken})
check(code == 0 and "slice.py set" in (ctx(out) or "") and "restored" not in (ctx(out) or ""),
      "  and a write is still advised, without promising a restore")
code, out, err = run(pre("Edit", TARGET, S, sid="f-broken2"), env_extra={"TMPDIR": broken})
check(code == 0 and out == "", "  and the ask-once mark cannot be kept, so no ask")
rc = subprocess.run([sys.executable, "-S", "-B", ROUTE], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    universal_newlines=True)
check(rc.returncode == 0 and rc.stdout == "" and rc.stderr == "", "`route.py < /dev/null`: nothing printed, exit 0")

# ------------------------------------------------------------------------------------------ N
print("N · never allow; fast")
bad = []
n_ask = 0
for out in ALL_OUT:
    if not out:
        continue
    h = hso(out)
    if h is None:
        bad.append(out[:80])
        continue
    d = h.get("permissionDecision")
    if d == "ask":
        n_ask += 1
    elif d is not None or "decision" in json.loads(out) or "allow" in json.dumps(h.get("permissionDecision", "")):
        bad.append(out[:80])
check(not bad and n_ask >= 5 and len(ALL_OUT) > 150,
      'across %d runs the only decision ever printed is "ask" (%d times); every output parses; none says allow' % (len(ALL_OUT), n_ask))
check(not any('"allow"' in o or '"deny"' in o for o in ALL_OUT), 'no output contains "allow" or "deny"')


def median_ms(payload, n=20):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        run(payload)
        times.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(times)


typical = median_ms(pre("Bash", {"command": "git status --short"}, S, sid="t-typ"))
matching = median_ms(pre("Bash", {"command": "grep -rn foo ."}, S, sid="t-match"))
edit = median_ms(pre("Edit", {"file_path": os.path.join(S, "render", "a.js")}, S, sid="t-edit"))
outside = median_ms(pre("Bash", {"command": "git status --short"}, PLAIN, sid="t-out"))
print("  timing: typical Bash median %.0f ms · matching Bash %.0f ms · Edit in project %.0f ms · outside a project %.0f ms"
      % (typical, matching, edit, outside))
check(typical < 150 and matching < 150 and edit < 150 and outside < 150, "median of 20 runs is under 150 ms in every case")

# ------------------------------------------------------------------------------------------ clean up
shutil.rmtree(FIX, ignore_errors=True)
shutil.rmtree(STATE, ignore_errors=True)
for d in EXTRA_DIRS:
    shutil.rmtree(d, ignore_errors=True)
print()
if FAILS:
    print("FAILED: %d check(s)" % len(FAILS))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all route hook checks passed")
