#!/usr/bin/env python3
"""SessionStart / PostToolUse hook: keep what only grows from growing, and say what else has piled up.

Inside a pb project only (see bash_advice.pb_projects: the working folder, its `.prototype/` or one of its
immediate child folders), and it NEVER deletes a file. Two kinds of work:

  Automatic (lossless, or a log that is meant to be bounded)
    - `memory/decisions.md` over the budget -> `decisions_rotate.rotate(..., apply)`: the oldest entries move
      to `memory/decisions-<year>.md`, a copy of the original is kept in `memory/.pb-backups/`, and the
      tool reads everything back and restores on any mismatch. Done on SessionStart, and on PostToolUse
      right after an Edit/Write/MultiEdit of that file. Over BIG_LOG_BYTES it is spawned detached instead
      (`decisions_rotate.py <path> --apply`, output in `.preview/housekeep.log`) so the hook stays fast.
      A fresh `memory/.decisions.lock` (another rotation is running) means do nothing, silently; the log is
      never written through a symlink or any non-regular file (output then goes nowhere).
    - `.preview/server.log` over 1 MB -> trimmed in place to its last 256 KB (`clean._trim_log`, safe while
      a preview holds the file open).
  Reported only (SessionStart): ONE additionalContext notice of at most 5 lines, each a fact plus the fix
    - decisions rotated (N entries moved to <file>)
    - backups over the count or MB limit, per place   -> /pb:clean --keep-backups N
    - .pb-patches over the count or MB limit          -> /pb:clean --keep-patches N
    - memory/*.md over memory_file_kb (up to 3 names; decisions*.md excluded: rotation owns them)
    - prototype.html / design-system.html tracked by git -> .gitignore + `git rm --cached`
    Backups and .pb-patches are warn-only by user ruling: nothing here prunes them.
  Silent when nothing applies.

Mode: `<project>/memory/doctor.json` key "enforce" ("route" default | "advise" | "off"), PB_ENFORCE over it
(route.enforce_mode). "off": nothing at all. "advise": no rotation and no trim, only the notice lines
(decisions.md over budget -> "run decisions_rotate.py --apply").

Thresholds are the defaults of lint_registry._resources/_size_block (`th` dict) and clean.py, copied here
as constants so this hook need not import lint_registry (heavy); the same memory/doctor.json keys override
them: decisions_kb, backups_count, backups_mb, patches_count, patches_mb, memory_file_kb, server_log_kb.

Any error, bad stdin or nothing to say prints nothing and exits 0. Stdlib only (run as `python3 -S -B`),
Python 3.7+.
"""
import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bash_advice import is_project, pb_projects  # noqa: E402  (shared: one definition of "a pb project")

# Defaults mirror lint_registry.py `th` (~1938) and clean.py (DECISIONS_KB, LOG_MAX).
DEFAULTS = {"decisions_kb": 500, "backups_count": 20, "backups_mb": 50, "patches_count": 30,
            "patches_mb": 50, "memory_file_kb": 64, "server_log_kb": 1024}
BIG_LOG_BYTES = 8 * 1024 * 1024   # a log this large is rotated in a detached process, not in the hook
MAX_LINES = 5
MAX_PROJECTS = 3
GENERATED_HTML = ("prototype.html", "design-system.html")
GIT_BUDGET_S = 2.0


def plugin_root():
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env and os.path.isdir(os.path.join(env, "tools")):
        return env
    return os.path.dirname(HERE)


def tools_dir():
    return os.path.join(plugin_root(), "tools")


def mode_of(proj):
    from route import enforce_mode
    return enforce_mode(proj)


def thresholds(proj):
    th = dict(DEFAULTS)
    try:
        with open(os.path.join(proj, "memory", "doctor.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = None
    if isinstance(cfg, dict):
        for key, default in DEFAULTS.items():
            try:
                v = float(cfg.get(key, default))
            except (TypeError, ValueError):
                continue
            if v == v and v > 0:
                th[key] = v
    return th


def num(x):
    return ("%.0f" % x) if abs(x - round(x)) < 0.05 else ("%.1f" % x)


def import_tool(name):
    d = tools_dir()
    if d not in sys.path:
        sys.path.append(d)
    return __import__(name)


# ---- decisions rotation --------------------------------------------------------------------------
def decisions_path(proj):
    return os.path.join(proj, "memory", "decisions.md")


def over_budget(proj, th):
    try:
        return os.stat(decisions_path(proj)).st_size > th["decisions_kb"] * 1024
    except OSError:
        return False


def open_log_sink(logdir):
    """.preview/housekeep.log opened for append, or None when it must not be written: a symlink (a
    hostile repo could aim it at a user file), a folder, a pipe, anything that is not a regular file.
    The same rule as explore.trim_log. O_NOFOLLOW where the platform has it, and the opened handle is
    checked again, so a swap between the check and the open does not write through."""
    log = os.path.join(logdir, "housekeep.log")
    try:
        if os.path.islink(logdir):
            return None
        os.makedirs(logdir, exist_ok=True)
        try:
            if not stat.S_ISREG(os.lstat(log).st_mode):
                return None
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(log, flags, 0o644)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            return None
        return os.fdopen(fd, "ab")
    except OSError:
        return None


def rotate_decisions(proj, th):
    """Rotate memory/decisions.md. -> a notice line, or None when there was nothing to move or another
    rotation holds memory/.decisions.lock (decisions_rotate takes it; we stay out of its way)."""
    path = decisions_path(proj)
    kb = th["decisions_kb"]
    threshold = int(kb * 1024)
    rotor = os.path.join(tools_dir(), "decisions_rotate.py")
    dr = import_tool("decisions_rotate")
    if dr.lock_is_fresh(path):
        return None
    size = os.stat(path).st_size
    if size > BIG_LOG_BYTES:
        sink = open_log_sink(os.path.join(proj, ".preview")) or subprocess.DEVNULL
        try:
            subprocess.Popen([sys.executable, "-B", rotor, path, "--threshold-kb", num(kb), "--apply"],
                             stdin=subprocess.DEVNULL, stdout=sink, stderr=sink, start_new_session=True,
                             close_fds=True, cwd=proj)
        finally:
            if sink is not subprocess.DEVNULL:
                sink.close()
        return ("pb: memory/decisions.md is %s KB (budget %s KB): rotating it in the background, "
                "losslessly (log: .preview/housekeep.log); nothing is deleted." % (num(size / 1024.0), num(kb)))
    with open(path, encoding="utf-8") as f:
        text = f.read()
    _keep, move = dr.plan(text, threshold)
    if not move:
        return None
    years = sorted({dr.entry_year(e) or "undated" for e in move})
    files = ["memory/decisions-%s.md" % y for y in years]
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        rc = dr.rotate(path, threshold, True)
    if rc == dr.BUSY:
        return None
    if rc != 0:
        return ("pb: rotating memory/decisions.md (%s KB, budget %s KB) failed and was rolled back, nothing "
                "moved: see `python3 %s %s --apply`." % (num(size / 1024.0), num(kb), rotor, path))
    return ("pb: memory/decisions.md was %s KB (budget %s KB): rotated, %d entries moved to %s "
            "(lossless, original kept in memory/.pb-backups/)." % (num(size / 1024.0), num(kb), len(move), ", ".join(files)))


def advise_decisions(proj, th):
    try:
        size = os.stat(decisions_path(proj)).st_size
    except OSError:
        return None
    if size <= th["decisions_kb"] * 1024:
        return None
    return ("pb: memory/decisions.md is %s KB, over the %s KB budget: run `python3 %s %s --apply` (lossless)."
            % (num(size / 1024.0), num(th["decisions_kb"]), os.path.join(tools_dir(), "decisions_rotate.py"),
               decisions_path(proj)))


# ---- reports -------------------------------------------------------------------------------------
def git_tracked(proj, deadline):
    """The generated HTML files git tracks in `proj` (empty on any failure or when the time is up)."""
    out = []
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for name in GENERATED_HTML:
        left = deadline - time.time()
        if left <= 0.05 or not os.path.isfile(os.path.join(proj, name)):
            continue
        try:
            r = subprocess.run(["git", "ls-files", "--error-unmatch", "--", name], cwd=proj, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=left)
        except (OSError, subprocess.SubprocessError):
            return out
        if r.returncode == 0:
            out.append(name)
    return out


def notices(proj, th, clean):
    lines = []
    mb = 1024.0 * 1024.0
    if clean is not None:
        try:
            places = []
            for place in clean.BACKUP_PLACES:
                groups = clean.backups_in(os.path.join(proj, place))
                total = sum(g["bytes"] for g in groups)
                if len(groups) > th["backups_count"] or total / mb > th["backups_mb"]:
                    places.append("%d in %s/ (%s MB)" % (len(groups), place.replace(os.sep, "/"), num(total / mb)))
            if places:
                lines.append("pb: backups are piling up, nothing deletes them: %s (limit %s or %s MB per place). "
                             "To prune: `/pb:clean --keep-backups 10`." % (
                                 "; ".join(places), num(th["backups_count"]), num(th["backups_mb"])))
        except Exception:  # noqa: BLE001
            pass
        try:
            pt = clean.patch_tasks(proj)
            if pt["count"] > th["patches_count"] or pt["bytes"] / mb > th["patches_mb"]:
                lines.append("pb: .pb-patches/ holds %d task folders, %s MB (limit %s or %s MB), nothing deletes "
                             "them. To prune: `/pb:clean --keep-patches 10`." % (
                                 pt["count"], num(pt["bytes"] / mb), num(th["patches_count"]), num(th["patches_mb"])))
        except Exception:  # noqa: BLE001
            pass
    try:
        mem = os.path.join(proj, "memory")
        big = []
        for name in sorted(os.listdir(mem)):
            fp = os.path.join(mem, name)
            if name.endswith(".md") and not name.startswith("decisions") and os.path.isfile(fp):
                size = os.path.getsize(fp)
                if size / 1024.0 > th["memory_file_kb"]:
                    big.append((size, name))
        big.sort(reverse=True)
        if big:
            names = ", ".join("%s (%s KB)" % (n, num(s / 1024.0)) for s, n in big[:3])
            lines.append("pb: memory/ files over %s KB, an agent reading memory/ pays for them every session: %s%s. "
                         "Split them by topic or move the history out." % (
                             num(th["memory_file_kb"]), names, "" if len(big) <= 3 else " and %d more" % (len(big) - 3)))
    except OSError:
        pass
    try:
        tracked = git_tracked(proj, time.time() + GIT_BUDGET_S)
        if tracked:
            lines.append("pb: %s %s tracked by git (derived output, adds its full size to every commit): add %s to "
                         ".gitignore and run `git rm --cached %s`." % (
                             " and ".join(tracked), "is" if len(tracked) == 1 else "are",
                             " and ".join(tracked), " ".join(tracked)))
    except Exception:  # noqa: BLE001
        pass
    return lines


def trim_server_log(proj, th):
    log = os.path.join(proj, ".preview", "server.log")
    try:
        if os.stat(log).st_size <= th["server_log_kb"] * 1024:
            return
    except OSError:
        return
    clean = import_tool("clean")
    clean._trim_log(log, os.path.realpath(proj))


def emit(event, lines):
    lines = [l for l in lines if l][:MAX_LINES]
    if not lines:
        return
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": event,
                                                        "additionalContext": "\n".join(lines)}}))


# ---- events --------------------------------------------------------------------------------------
def session_start(data):
    folder = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    projects = pb_projects(folder)[:MAX_PROJECTS]
    if not projects:
        return
    try:
        clean = import_tool("clean")
    except Exception:  # noqa: BLE001
        clean = None
    lines = []
    for proj in projects:
        mine = []
        try:
            mode = mode_of(proj)
            if mode == "off":
                continue
            th = thresholds(proj)
            try:
                if mode == "route":
                    if over_budget(proj, th):
                        mine.append(rotate_decisions(proj, th))
                    trim_server_log(proj, th)
                else:
                    mine.append(advise_decisions(proj, th))
            except Exception:  # noqa: BLE001
                pass
            mine += notices(proj, th, clean)
        except Exception:  # noqa: BLE001
            pass
        mine = [m for m in mine if m]
        if len(projects) > 1:
            tag = os.path.basename(os.path.normpath(proj)) or proj
            mine = [m.replace("pb: ", "pb [%s]: " % tag, 1) for m in mine]
        lines += mine
    emit("SessionStart", lines)


def post_tool_use(data):
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        return
    ti = data.get("tool_input")
    fp = ti.get("file_path") if isinstance(ti, dict) else None
    if not isinstance(fp, str) or os.path.basename(fp) != "decisions.md":
        return
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    fp = os.path.realpath(fp if os.path.isabs(fp) else os.path.join(cwd, fp))
    memdir = os.path.dirname(fp)
    proj = os.path.dirname(memdir)
    if os.path.basename(memdir) != "memory" or not is_project(proj):
        return
    mode = mode_of(proj)
    if mode == "off":
        return
    th = thresholds(proj)
    if not over_budget(proj, th):
        return
    line = rotate_decisions(proj, th) if mode == "route" else advise_decisions(proj, th)
    emit("PostToolUse", [line])


def main():
    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    event = data.get("hook_event_name")
    if event == "SessionStart":
        session_start(data)
    elif event == "PostToolUse":
        post_tool_use(data)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
