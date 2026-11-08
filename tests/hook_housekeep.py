#!/usr/bin/env python3
"""
hook_housekeep.py — housekeep.py keeps what only grows from growing, reports the rest, and deletes nothing.

pb/hooks/housekeep.py runs on SessionStart and (for Edit|Write|MultiEdit of memory/decisions.md) PostToolUse.
Checked here with fake payloads on stdin, in throw-away projects, with no browser and no Claude Code:

  R0  hooks.json registers it: SessionStart with session_rules' matcher, PostToolUse "Edit|Write|MultiEdit",
      `python3 -S -B` exec style, timeout <= 5, no onFailure; the description says it deletes nothing.
  D   decisions.md over the budget is rotated on SessionStart: every `## ` entry across decisions*.md is
      still there (multiset equal), the live file is under the budget, the notice names the count and the
      file; under the budget nothing happens; memory/doctor.json decisions_kb moves the budget; a second
      run is silent; a session one folder above the registry works; a log over 8 MB is rotated by a
      detached process and the hook says so.
  P   PostToolUse: Edit/Write/MultiEdit of memory/decisions.md over the budget rotates and says so in one
      line; any other file, any other tool, an under-budget log, a file outside a pb project: silent.
  M   enforce "advise": no rotation, no trim, the notice says to run decisions_rotate.py --apply (also on
      PostToolUse); "off": nothing at all; PB_ENFORCE overrides doctor.json.
  W   each warning kind on its own (backups by count and by MB per place, .pb-patches by count, memory files
      over memory_file_kb with at most 3 names, prototype.html / design-system.html tracked by git), each
      naming its fix command; all together stay within 5 lines; a clean project is silent.
  T   .preview/server.log over 1 MB is trimmed in place to its tail, from a line start.
  X   nothing is deleted: a before/after listing of a project with everything piled up shows every file still
      there, backups and .pb-patches byte-identical, and only decisions-<year>.md and memory/.pb-backups/
      files added (plus the trimmed log and the rotated decisions.md changed).
  F   fail open: garbage stdin, other events, a broken doctor.json, a non-UTF-8 log, an unwritable memory/:
      exit 0, nothing printed, files untouched.
  N   SessionStart median over 20 runs on a project with 50 backup folders is under 500 ms (printed), and
      the in-process rotation of a 1.2 MB log is timed (printed).

Usage:  python3 tests/hook_housekeep.py
Exit:   0 = pass · 1 = a failure
"""
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "pb", "hooks")
HK = os.path.join(HOOKS, "housekeep.py")

FAILS = []
FIX = tempfile.mkdtemp(prefix="pb-housekeep-fx-")
ENTRY = re.compile(r"(?m)^## ")
KB = 1024


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def run(payload, env_extra=None, raw=None, cwd=None):
    """-> (exit code, stdout, stderr)"""
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("PB_ENFORCE", None)
    for k, v in (env_extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    stdin = raw if raw is not None else json.dumps(payload)
    p = subprocess.run([sys.executable, "-S", "-B", HK], input=stdin, env=env, cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def start(folder, **kw):
    return run({"hook_event_name": "SessionStart", "source": "startup", "cwd": folder}, cwd=folder, **kw)


def post(proj, tool="Edit", file_path=None, **kw):
    fp = file_path or os.path.join(proj, "memory", "decisions.md")
    return run({"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": fp},
                "tool_response": {}, "cwd": proj, "session_id": "s1"}, cwd=proj, **kw)


def ctx(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:  # noqa: BLE001
        return None


def event(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["hookEventName"]
    except Exception:  # noqa: BLE001
        return None


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode) as f:
        f.write(data)


def make_pb(folder, doctor=None):
    write(os.path.join(folder, "registry.json"), "{}")
    os.makedirs(os.path.join(folder, "render"), exist_ok=True)
    os.makedirs(os.path.join(folder, "memory"), exist_ok=True)
    if doctor is not None:
        write(os.path.join(folder, "memory", "doctor.json"), doctor if isinstance(doctor, str) else json.dumps(doctor))
    return folder


def decisions_text(n, size=6000):
    """n dated entries of about `size` bytes, spread over 2025 and 2026, in file order."""
    out = ["# Decisions\n\n> house format note\n\n"]
    for i in range(n):
        year = 2025 if i < n // 2 else 2026
        month = 1 + (i % 12)
        body = ("decision %d. " % i) * (size // 14)
        out.append("## %d-%02d-%02d · D-%d entry %d\n\n%s\n\n" % (year, month, 1 + (i % 27), i, i, body))
    return "".join(out)


def entries_across(proj):
    """Every `## ` entry across memory/decisions*.md, as a sorted list of full entry texts."""
    mem = os.path.join(proj, "memory")
    found = []
    for name in sorted(os.listdir(mem)):
        if re.fullmatch(r"decisions(-[^.]+)?\.md", name):
            with open(os.path.join(mem, name), encoding="utf-8") as f:
                text = f.read()
            marks = [m.start() for m in ENTRY.finditer(text)]
            bounds = marks + [len(text)]
            found += [text[bounds[i]:bounds[i + 1]] for i in range(len(marks))]
    return sorted(found)


def snap(root):
    """{relative path: sha1} of every file under root, hidden folders included."""
    out = {}
    for cur, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(cur, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha1(fh.read()).hexdigest()
    return out


def size(path):
    return os.path.getsize(path)


def new_project(name, **kw):
    return make_pb(os.path.join(FIX, name), **kw)


def fill_backups(proj, place, n, nbytes=10):
    for i in range(n):
        write(os.path.join(proj, place, "registry.v%02d.20260101T0000%02dZ.json" % (i, i)), "x" * nbytes)


# ------------------------------------------------------------------------------------------ R0
print("R0 · hooks.json")
try:
    with open(os.path.join(HOOKS, "hooks.json"), encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:  # noqa: BLE001
    cfg = {}
    check(False, "hooks.json parses (%s)" % e)


def groups(event_name):
    return [g for g in cfg.get("hooks", {}).get(event_name, [])
            if any(a.endswith("/hooks/housekeep.py") for h in g.get("hooks", []) for a in h.get("args", []))]


ss = cfg.get("hooks", {}).get("SessionStart", [])
rules_group = [g for g in ss if any(a.endswith("/hooks/session_rules.py") for h in g["hooks"] for a in h["args"])]
hk_ss, hk_post = groups("SessionStart"), groups("PostToolUse")
check(len(hk_ss) == 1 and len(rules_group) == 1 and hk_ss[0].get("matcher") == rules_group[0].get("matcher"),
      "SessionStart registers housekeep.py with session_rules' matcher (%s)" % (hk_ss[0].get("matcher") if hk_ss else None))
check(len(hk_post) == 1 and hk_post[0].get("matcher") == "Edit|Write|MultiEdit",
      "PostToolUse registers housekeep.py for Edit|Write|MultiEdit")
for g in hk_ss + hk_post:
    for h in [h for h in g["hooks"] if any(a.endswith("housekeep.py") for a in h["args"])]:
        hk = [a for a in h["args"] if a.endswith("housekeep.py")]
        check(h.get("type") == "command" and h.get("command") == "python3" and h["args"][:2] == ["-S", "-B"]
              and "onFailure" not in h and isinstance(h.get("timeout"), int) and h["timeout"] <= 5 and hk,
              "  an exec-style `python3 -S -B` command, timeout <= 5, no onFailure")
desc = cfg.get("description", "")
check("housekeep.py" in desc and "deletes nothing" in desc and "lossless" in desc,
      "hooks.json description says housekeeping is lossless and deletes nothing")
check(os.path.isfile(HK), "pb/hooks/housekeep.py exists")

# ------------------------------------------------------------------------------------------ D
print("D · decisions rotation on SessionStart")
proj = new_project("rot")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(200))
before_entries = entries_across(proj)
before_size = size(os.path.join(proj, "memory", "decisions.md"))
check(before_size > 1100 * KB and len(before_entries) == 200, "fixture: 200 entries, %d KB" % (before_size // KB))
before_files = snap(proj)
t0 = time.time()
code, out, err = start(proj)
rot_secs = time.time() - t0
text = ctx(out)
after_entries = entries_across(proj)
live = size(os.path.join(proj, "memory", "decisions.md"))
check(code == 0 and text is not None and event(out) == "SessionStart", "over budget: exit 0, SessionStart additionalContext")
check(after_entries == before_entries, "  no entry lost, none altered (%d before, %d after, byte-identical)"
      % (len(before_entries), len(after_entries)))
check(live <= 500 * KB, "  decisions.md is now %d KB, within the 500 KB budget" % (live // KB))
siblings = sorted(f for f in os.listdir(os.path.join(proj, "memory")) if f.startswith("decisions-"))
check(siblings == ["decisions-2025.md", "decisions-2026.md"] or siblings == ["decisions-2025.md"],
      "  the older entries went to decisions-<year>.md (%s)" % ", ".join(siblings))
m = re.search(r"(\d+) entries moved to ([^ ]+)", text or "")
moved = int(m.group(1)) if m else -1
check(bool(m) and moved > 0 and moved + len(entries_across(proj)) - moved == 200 and "rotated" in text
      and "decisions-2025.md" in text,
      "  the notice says rotated, N entries moved, and to which file: %r" % (text or "")[:140])
live_n = len(ENTRY.findall(open(os.path.join(proj, "memory", "decisions.md"), encoding="utf-8").read()))
check(live_n == 200 - moved, "  the moved count is exact (%d kept + %d moved = 200)" % (live_n, moved))
after_files = snap(proj)
removed = sorted(set(before_files) - set(after_files))
added = sorted(set(after_files) - set(before_files))
check(not removed, "  no file removed (%s)" % removed)
check(all(re.fullmatch(r"memory/(decisions-\d{4}\.md|\.pb-backups/.+)", a) for a in added) and added,
      "  only rotation outputs added: %s" % added)
backup = [a for a in added if ".pb-backups" in a]
check(len(backup) == 1 and after_files[backup[0]] == before_files["memory/decisions.md"],
      "  the original is kept byte-identical in memory/.pb-backups/")
code, out, err = start(proj)
check(code == 0 and out == "", "  a second run is silent (already under the budget)")
print("       timing: in-process rotation of a %.1f MB log, whole hook process: %.0f ms" % (before_size / 1048576.0, rot_secs * 1000))

proj = new_project("under")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(40))
b = snap(proj)
code, out, err = start(proj)
check(code == 0 and out == "" and snap(proj) == b, "under the budget: silent, no file touched")

proj = new_project("budget", doctor={"decisions_kb": 100})
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(50))
b_entries = entries_across(proj)
code, out, err = start(proj)
check(code == 0 and "rotated" in (ctx(out) or "") and size(os.path.join(proj, "memory", "decisions.md")) <= 100 * KB
      and entries_across(proj) == b_entries, "doctor.json decisions_kb=100 moves the budget (and loses nothing)")

above = os.path.join(FIX, "above")
proj = make_pb(os.path.join(above, "app"))
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
b_entries = entries_across(proj)
code, out, err = start(above)
check(code == 0 and "rotated" in (ctx(out) or "") and entries_across(proj) == b_entries,
      "a session one folder above the registry rotates the child project's log")
check(size(os.path.join(proj, "memory", "decisions.md")) <= 500 * KB, "  and it is under the budget")

proj = make_pb(os.path.join(FIX, "above2", "app", ".prototype"))
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
b_entries = entries_across(proj)
code, out, err = start(os.path.join(FIX, "above2", "app"))
check(code == 0 and "rotated" in (ctx(out) or "") and entries_across(proj) == b_entries,
      "  .prototype/ inside a repo works the same")

print("D · a log over 8 MB is rotated by a detached process")
proj = new_project("big")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(1400))
b_entries = entries_across(proj)
big_size = size(os.path.join(proj, "memory", "decisions.md"))
check(big_size > 8 * 1024 * KB, "fixture: %.1f MB" % (big_size / 1048576.0))
t0 = time.time()
code, out, err = start(proj)
check(code == 0 and "background" in (ctx(out) or "") and "deleted" in (ctx(out) or ""),
      "  the hook returns at once and says it is rotating in the background (%.0f ms)" % ((time.time() - t0) * 1000))
deadline = time.time() + 40
while time.time() < deadline:
    try:
        if size(os.path.join(proj, "memory", "decisions.md")) <= 500 * KB and entries_across(proj) == b_entries:
            break
    except OSError:
        pass
    time.sleep(0.3)
check(size(os.path.join(proj, "memory", "decisions.md")) <= 500 * KB and entries_across(proj) == b_entries,
      "  the detached run finished: under the budget, every entry still there")
check(os.path.isfile(os.path.join(proj, ".preview", "housekeep.log")), "  its output went to .preview/housekeep.log")

# ------------------------------------------------------------------------------------------ P
print("P · PostToolUse")
for tool in ("Edit", "Write", "MultiEdit"):
    proj = new_project("post-" + tool)
    dpath = os.path.join(proj, "memory", "decisions.md")
    write(dpath, decisions_text(120))
    b_entries = entries_across(proj)
    code, out, err = post(proj, tool)
    c = ctx(out)
    check(code == 0 and event(out) == "PostToolUse" and c and "rotated" in c and "\n" not in c
          and size(dpath) <= 500 * KB and entries_across(proj) == b_entries,
          "%s of decisions.md over the budget: rotated, one line, nothing lost" % tool)
code, out, err = post(proj)
check(code == 0 and out == "", "  under the budget now: silent")
proj = new_project("post-others")
dpath = os.path.join(proj, "memory", "decisions.md")
write(dpath, decisions_text(120))
b = snap(proj)
for label, kw in (("another file", {"file_path": os.path.join(proj, "registry.json")}),
                  ("a decisions.md outside memory/", {"file_path": os.path.join(proj, "decisions.md")}),
                  ("another tool", {"tool": "Read"}), ("Bash", {"tool": "Bash"})):
    code, out, err = post(proj, **kw)
    check(code == 0 and out == "" and snap(proj) == b, "  %s: silent, nothing touched" % label)
plain = os.path.join(FIX, "plain")
write(os.path.join(plain, "memory", "decisions.md"), decisions_text(120))
b = snap(plain)
code, out, err = post(plain)
check(code == 0 and out == "" and snap(plain) == b, "  a decisions.md outside a pb project: silent, untouched")
proj = new_project("post-rel")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
rel = run({"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": "memory/decisions.md"},
           "cwd": proj}, cwd=proj)
check(rel[0] == 0 and "rotated" in (ctx(rel[1]) or ""), "  a relative file_path is resolved against cwd")

# ------------------------------------------------------------------------------------------ M
print("M · modes")
proj = new_project("advise", doctor={"enforce": "advise"})
dpath = os.path.join(proj, "memory", "decisions.md")
write(dpath, decisions_text(120))
write(os.path.join(proj, ".preview", "server.log"), "log line\n" * 200000)
fill_backups(proj, "memory/backups", 25)
b = snap(proj)
code, out, err = start(proj)
c = ctx(out) or ""
check(code == 0 and snap(proj) == b, "advise: SessionStart changes no file (no rotation, no trim)")
check("decisions_rotate.py" in c and "--apply" in c and "over the 500 KB budget" in c,
      "  the notice says decisions.md is over budget: run decisions_rotate.py --apply")
check("--keep-backups" in c, "  the other warnings still show")
code, out, err = post(proj)
check(code == 0 and snap(proj) == b and "--apply" in (ctx(out) or "") and event(out) == "PostToolUse",
      "advise: PostToolUse changes no file and says to run decisions_rotate.py --apply")

proj = new_project("off", doctor={"enforce": "off"})
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
write(os.path.join(proj, ".preview", "server.log"), "log line\n" * 200000)
fill_backups(proj, "memory/backups", 25)
b = snap(proj)
check(start(proj)[1:2] == ("",) and post(proj)[1] == "" and snap(proj) == b,
      "off: SessionStart and PostToolUse print nothing and touch nothing")
code, out, err = start(proj, env_extra={"PB_ENFORCE": "route"})
check("rotated" in (ctx(out) or ""), "PB_ENFORCE=route overrides doctor.json off")
proj = new_project("envoff")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
b = snap(proj)
check(start(proj, env_extra={"PB_ENFORCE": "off"})[1] == "" and snap(proj) == b, "PB_ENFORCE=off over the default: silent")
code, out, err = start(proj, env_extra={"PB_ENFORCE": "advise"})
check("--apply" in (ctx(out) or "") and snap(proj) == b, "PB_ENFORCE=advise over the default: notice only")

# ------------------------------------------------------------------------------------------ W
print("W · each warning kind")
proj = new_project("clean")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(20))
write(os.path.join(proj, "memory", "notes.md"), "small\n")
b = snap(proj)
code, out, err = start(proj)
check(code == 0 and out == "" and snap(proj) == b, "a clean project: silent")

proj = new_project("w-count")
fill_backups(proj, "memory/backups", 21)
fill_backups(proj, ".pb-backups", 3)
c = ctx(start(proj)[1]) or ""
check("21 in memory/backups/" in c and ".pb-backups/" not in c and "/pb:clean --keep-backups 10" in c
      and len(c.splitlines()) == 1, "backups over the count: names the place and /pb:clean --keep-backups N")
proj = new_project("w-count-ok")
fill_backups(proj, "memory/backups", 20)
check(start(proj)[1] == "", "  exactly the limit: silent")
proj = new_project("w-mb", doctor={"backups_mb": 0.001})
fill_backups(proj, ".pb-backups", 2, nbytes=4096)
c = ctx(start(proj)[1]) or ""
check("2 in .pb-backups/" in c and "--keep-backups" in c, "backups over the MB limit (doctor.json backups_mb): reported per place")
proj = new_project("w-places")
fill_backups(proj, "memory/backups", 22)
fill_backups(proj, "memory/.pb-backups", 23)
c = ctx(start(proj)[1]) or ""
check("22 in memory/backups/" in c and "23 in memory/.pb-backups/" in c and len(c.splitlines()) == 1,
      "  two places over: one line naming both")

proj = new_project("w-patches")
for i in range(31):
    write(os.path.join(proj, ".pb-patches", "t%02d" % i, "p.json"), "{}")
c = ctx(start(proj)[1]) or ""
check("31 task folders" in c and "/pb:clean --keep-patches 10" in c, ".pb-patches over the count: /pb:clean --keep-patches N")
proj = new_project("w-patches-ok")
for i in range(30):
    write(os.path.join(proj, ".pb-patches", "t%02d" % i, "p.json"), "{}")
check(start(proj)[1] == "", "  exactly the limit: silent")

proj = new_project("w-mem")
for name, kb in (("a.md", 70), ("b.md", 90), ("c.md", 80), ("d.md", 65), ("small.md", 1)):
    write(os.path.join(proj, "memory", name), "x" * (kb * KB))
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(80, 6000))   # ~480 KB: rotation's job, never named here
c = ctx(start(proj)[1]) or ""
check("b.md (90 KB)" in c and "c.md (80 KB)" in c and "a.md (70 KB)" in c and "d.md" not in c and "small.md" not in c
      and "and 1 more" in c and "decisions" not in c.replace("decisions.md", "") and len(c.splitlines()) == 1,
      "memory/*.md over memory_file_kb: the 3 largest named, 'and 1 more', decisions*.md left to rotation: %r" % c[:160])

git = shutil.which("git")
if git:
    proj = new_project("w-git")
    write(os.path.join(proj, "prototype.html"), "<html></html>")
    write(os.path.join(proj, "design-system.html"), "<html></html>")
    genv = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=proj, env=genv, check=True)
    c = ctx(start(proj)[1]) or ""
    check(c == "", "git work tree, generated HTML present but not tracked: silent")
    subprocess.run(["git", "add", "prototype.html"], cwd=proj, env=genv, check=True)
    c = ctx(start(proj)[1]) or ""
    check("prototype.html is tracked" in c and "design-system.html" not in c and ".gitignore" in c
          and "git rm --cached prototype.html" in c, "prototype.html tracked: names .gitignore and git rm --cached")
    subprocess.run(["git", "add", "design-system.html"], cwd=proj, env=genv, check=True)
    c = ctx(start(proj)[1]) or ""
    check("prototype.html and design-system.html are tracked" in c and "git rm --cached prototype.html design-system.html" in c,
          "  both tracked: one line naming both")
    nogit = new_project("w-nogit")
    write(os.path.join(nogit, "prototype.html"), "<html></html>")
    check(start(nogit, env_extra={"GIT_DIR": os.path.join(nogit, "nope")})[1] == "", "  not in a work tree: quiet")
else:
    print("  skip git-tracked checks (no git on this machine)")

# ------------------------------------------------------------------------------------------ T
print("T · server.log")
proj = new_project("log")
lines = "".join("line %07d %s\n" % (i, "y" * 40) for i in range(30000))        # ~1.7 MB
logp = os.path.join(proj, ".preview", "server.log")
write(logp, lines)
code, out, err = start(proj)
with open(logp, "rb") as f:
    tail = f.read()
check(code == 0 and 200 * KB < len(tail) <= 256 * KB and tail.startswith(b"line ") and tail.endswith(lines.encode()[-40:]),
      "over 1 MB: trimmed in place to its last ~256 KB, from a line start (%d KB left)" % (len(tail) // KB))
check(out == "", "  trimming prints nothing")
write(logp, lines[:900 * KB])
b = snap(proj)
start(proj)
check(snap(proj) == b, "under 1 MB: untouched")

# ------------------------------------------------------------------------------------------ all kinds together + X
print("X · everything piled up: five lines at most, nothing deleted")
proj = new_project("all")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(200))
write(os.path.join(proj, "memory", "notes.md"), "n" * (80 * KB))
write(os.path.join(proj, ".preview", "server.log"), lines)
fill_backups(proj, "memory/backups", 25)
fill_backups(proj, ".pb-backups", 25)
for i in range(32):
    write(os.path.join(proj, ".pb-patches", "t%02d" % i, "p.json"), "{ \"task\": %d }" % i)
if git:
    write(os.path.join(proj, "prototype.html"), "<html></html>")
    subprocess.run(["git", "init", "-q"], cwd=proj, env=genv, check=True)
    subprocess.run(["git", "add", "prototype.html"], cwd=proj, env=genv, check=True)
before_entries = entries_across(proj)
before = snap(proj)
code, out, err = start(proj)
after = snap(proj)
c = ctx(out) or ""
n_lines = len(c.splitlines())
check(code == 0 and 1 <= n_lines <= 5, "all kinds at once: %d lines, at most 5" % n_lines)
for needle in ("rotated", "--keep-backups", "--keep-patches", "notes.md"):
    check(needle in c, "  names %s" % needle)
check(all(l.startswith("pb: ") for l in c.splitlines()), "  every line is a fact with the pb: prefix")
removed = sorted(set(before) - set(after))
added = sorted(set(after) - set(before))
changed = sorted(p for p in before if p in after and before[p] != after[p])
check(not removed, "no file deleted (before %d files, after %d)" % (len(before), len(after)))
check(all(re.fullmatch(r"memory/(decisions-\d{4}\.md|\.pb-backups/decisions\.[0-9TZ]+\.md)", a) for a in added) and added,
      "only rotation outputs added: %s" % added)
check(sorted(changed) == [".preview/server.log", "memory/decisions.md"],
      "only the decisions log (rotated) and the preview log (trimmed) changed: %s" % changed)
check(all(before[p] == after[p] for p in before if p.startswith((".pb-patches/", ".pb-backups/", "memory/backups/"))),
      "backups and .pb-patches are byte-identical")
check(entries_across(proj) == before_entries, "no decisions entry lost (%d)" % len(before_entries))

# ------------------------------------------------------------------------------------------ F
print("F · fail open")
EMPTY = os.path.join(FIX, "empty-cwd")        # a cwd that is no pb project and holds none
os.makedirs(EMPTY)
proj = new_project("fail")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(120))
b = snap(proj)
for raw in ("", "not json", "[]", "null", "5", "{}", '{"hook_event_name": "Stop"}', '{"hook_event_name": 5}',
            '{"hook_event_name": "SessionStart", "cwd": 5}', '{"hook_event_name": "PostToolUse"}',
            '{"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": null}',
            '{"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": 5}}'):
    code, out, err = run(None, raw=raw, cwd=EMPTY)
    check(code == 0 and out == "" and snap(proj) == b, "silent, exit 0, untouched on %r" % raw[:60])
bad = new_project("faildoctor", doctor="{ not json")
write(os.path.join(bad, "memory", "decisions.md"), decisions_text(120))
code, out, err = start(bad)
check(code == 0 and "rotated" in (ctx(out) or "") and size(os.path.join(bad, "memory", "decisions.md")) <= 500 * KB,
      "a broken doctor.json falls back to the defaults")
bad = new_project("faildoctor2", doctor={"decisions_kb": "lots", "backups_count": None})
write(os.path.join(bad, "memory", "decisions.md"), decisions_text(120))
code, out, err = start(bad)
check(code == 0 and "rotated" in (ctx(out) or ""), "doctor.json values that are not numbers fall back to the defaults")
bad = new_project("failutf")
write(os.path.join(bad, "memory", "decisions.md"), b"## 2026-01-01 x\n" + b"\xff\xfe" * 300 * KB)
b = snap(bad)
code, out, err = start(bad)
check(code == 0 and snap(bad) == b, "a non-UTF-8 log: exit 0, file untouched")
if hasattr(os, "geteuid") and os.geteuid() != 0:
    bad = new_project("failro")
    write(os.path.join(bad, "memory", "decisions.md"), decisions_text(120))
    b = snap(bad)
    os.chmod(os.path.join(bad, "memory"), 0o555)
    try:
        code, out, err = start(bad)
        check(code == 0 and snap(bad) == b, "an unwritable memory/: exit 0, nothing changed")
    finally:
        os.chmod(os.path.join(bad, "memory"), 0o755)
code, out, err = start(proj, env_extra={"CLAUDE_PLUGIN_ROOT": os.path.join(FIX, "no-such-plugin")})
check(code == 0 and "rotated" in (ctx(out) or ""), "a CLAUDE_PLUGIN_ROOT with no tools/ falls back to the hook's own plugin")
code, out, err = start(plain)
check(code == 0 and out == "", "a folder that is no pb project: silent")

# ------------------------------------------------------------------------------------------ N
print("N · timing")
proj = new_project("timing")
write(os.path.join(proj, "memory", "decisions.md"), decisions_text(60))
for i in range(50):
    write(os.path.join(proj, "memory", "backups", "registry.v%02d.2026%04dT000000Z.json" % (i, i)), "x" * 2000)
    write(os.path.join(proj, "memory", "backups", "folder-%02d" % i, "a.json"), "y" * 1000)
times = []
for _ in range(20):
    t0 = time.time()
    code, out, err = start(proj)
    times.append((time.time() - t0) * 1000)
    assert code == 0
med = statistics.median(times)
print("       SessionStart, project with 100 backup entries: median %.0f ms, max %.0f ms over 20 runs" % (med, max(times)))
check(med < 500, "median of 20 SessionStart runs is under 500 ms (%.0f ms)" % med)

# ------------------------------------------------------------------------------------------ L
print("L · the rotation lock and the housekeep.log symlink")
LOCK = ".decisions.lock"
proj = new_project("lock")
dpath = os.path.join(proj, "memory", "decisions.md")
write(dpath, decisions_text(120))
write(os.path.join(proj, "memory", LOCK), "999999 held\n")
b = snap(proj)
code, out, err = start(proj)
check(code == 0 and out == "" and snap(proj) == b,
      "a fresh lock (SessionStart, in-process size): silent, nothing rotated, nothing written")
code, out, err = post(proj)
check(code == 0 and out == "" and snap(proj) == b, "  and on PostToolUse")
old = time.time() - 11 * 60
os.utime(os.path.join(proj, "memory", LOCK), (old, old))
b_entries = entries_across(proj)
code, out, err = start(proj)
check(code == 0 and "rotated" in (ctx(out) or "") and entries_across(proj) == b_entries
      and not os.path.exists(os.path.join(proj, "memory", LOCK)),
      "a lock older than 10 minutes is stale: it rotates, loses nothing, and releases the lock")

proj = new_project("lock-big")
dpath = os.path.join(proj, "memory", "decisions.md")
write(dpath, decisions_text(1400))
write(os.path.join(proj, "memory", LOCK), "999999 held\n")
b = snap(proj)
code, out, err = start(proj)
time.sleep(1.0)
check(code == 0 and out == "" and snap(proj) == b and not os.path.exists(os.path.join(proj, ".preview")),
      "a fresh lock over 8 MB: no detached process is spawned (no log, nothing changed)")

if hasattr(os, "symlink"):
    proj = new_project("log-link")
    dpath = os.path.join(proj, "memory", "decisions.md")
    write(dpath, decisions_text(1400))
    b_entries = entries_across(proj)
    victim = os.path.join(FIX, "victim.txt")
    write(victim, "the user's own file\n")
    os.makedirs(os.path.join(proj, ".preview"))
    try:
        os.symlink(victim, os.path.join(proj, ".preview", "housekeep.log"))
    except OSError:
        victim = None
    if victim:
        code, out, err = start(proj)
        deadline = time.time() + 40
        while time.time() < deadline:
            try:
                if size(dpath) <= 500 * KB and entries_across(proj) == b_entries:
                    break
            except OSError:
                pass
            time.sleep(0.3)
        check(code == 0 and "background" in (ctx(out) or "") and size(dpath) <= 500 * KB
              and entries_across(proj) == b_entries, "a symlinked housekeep.log: the rotation still runs, nothing lost")
        with open(victim) as f:
            check(f.read() == "the user's own file\n", "  and the file the symlink pointed at was not written through")
        check(os.path.islink(os.path.join(proj, ".preview", "housekeep.log")), "  the link itself is left alone")
    # a .preview that is itself a link, and a log that is a folder: also refused
    proj = new_project("log-dirlink")
    write(os.path.join(proj, "memory", "decisions.md"), decisions_text(1400))
    elsewhere = os.path.join(FIX, "elsewhere")
    os.makedirs(elsewhere)
    try:
        os.symlink(elsewhere, os.path.join(proj, ".preview"))
        code, out, err = start(proj)
        deadline = time.time() + 40
        while time.time() < deadline and size(os.path.join(proj, "memory", "decisions.md")) > 500 * KB:
            time.sleep(0.3)
        time.sleep(0.5)
        check(code == 0 and os.listdir(elsewhere) == [], "a symlinked .preview/: nothing is written through it")
    except OSError:
        pass
else:
    print("  skip symlink checks (no os.symlink)")

shutil.rmtree(FIX, ignore_errors=True)
print()
if FAILS:
    print("FAILED: %d check(s)" % len(FAILS))
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all housekeep hook checks passed")
