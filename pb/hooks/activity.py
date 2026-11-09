#!/usr/bin/env python3
"""UserPromptSubmit / PreToolUse / PostToolUse / PostToolUseFailure / SubagentStart / SubagentStop / Stop hook: tell the
open preview whether Claude is working, and with which tool.

Reads the hook JSON on stdin and, inside a pb project whose `.preview/` folder already exists (a preview has
run there), writes `.preview/activity.json` atomically:

    {"state": "working" | "idle", "at": <epoch seconds>, "event": "UserPromptSubmit" | "Stop", "since": <epoch s>}

`since` is when the turn began (set by UserPromptSubmit, kept by PostToolUse and Stop): the preview's activity
strip shows the time Claude has been working and, after Stop, how long the turn took. It is absent when unknown.

`UserPromptSubmit` means Claude has started on a prompt (working); `Stop` means it has finished the turn (idle,
so it is the person's turn). The preview server watches that one file, tells every open page, and the page's
progress item says Working / Your turn. Every finished tool call (`PostToolUse`) writes "working" again, so a
long turn stays Working. A turn cancelled with Esc fires no Stop, so the page does not trust "working" for more
than 90 s after the last write (pb/template/prototype.html, pbProgStatus).

A gated command also writes the gate it stopped at, with the same file's one writer (this script, by hand):

    python3 "${CLAUDE_PLUGIN_ROOT}/hooks/activity.py" --gate G-JTBD "approve 4 jobs and 3 terms" [--project <dir>]

which adds `"gate": {"id": "G-JTBD", "ask": "approve 4 jobs and 3 terms", "at": <epoch s>}` to the file and leaves
`state`, `at`, `event` and `since` as they are (no file yet: a working file that carries the gate). The activity
strip then reads "Your turn · G-JTBD — approve 4 jobs and 3 terms — reply in Claude Code" instead of the generic
line. The CLI runs inside a Bash call, so that call's own `PostToolUse` and the turn's `Stop` rewrite the file right
after it: both KEEP the gate. `UserPromptSubmit` DROPS it (the person has replied). The id must look like `G-JTBD`
and the ask must be a non-empty line (whitespace collapsed, at most 160 characters); anything else writes nothing.

The same script also keeps `.preview/agents.json`, one record per Claude Code session (two sessions in one project
must not zero each other), for the strip's "what is Claude doing now" line:

    {"sessions": {"<session_id>": {"at": <epoch s>, "verb": "Editing", "running": 1, "doneAt": <epoch s>, "agents": 2}}}

`UserPromptSubmit` resets that session's record; `PreToolUse` sets the verb for the tool kind (never a file name, command,
pattern or prompt) and counts one more call running; `PostToolUse` and `PostToolUseFailure` count one fewer and set `doneAt`;
`SubagentStart` / `SubagentStop` move `agents`; `Stop` removes the session's record (and the file when it was the last).
A record untouched for 30 minutes is dropped. Only the three events above write `.preview/activity.json`; the new ones write
`.preview/agents.json` only. Parallel tool calls run their hooks at once, so the read-modify-write holds an flock on `.preview/`
itself (skipped where `fcntl` is missing).

It only reports. It never prints (so it adds nothing to the model's context), never blocks, never decides a
permission, and any error, bad stdin or a folder that is not a pb project with a `.preview/` writes nothing and
exits 0. It does not create `.preview/`: a project nobody has previewed gets no new folder.
Silent outside a pb project (see `bash_advice.pb_project`). Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bash_advice import pb_project  # noqa: E402  (shared: one definition of "a pb project")

GATE_ID = re.compile(r"^G-[A-Z][A-Z0-9-]*$")
ASK_MAX = 160

# PostToolUse renews "working" on every finished tool call: a real pb turn runs for minutes, and the page's 90 s
# fallback would otherwise read Waiting while Claude is still at work. A turn cancelled with Esc makes no more tool
# calls, so the fallback still catches it.
STATES = {"UserPromptSubmit": "working", "PostToolUse": "working", "Stop": "idle"}
FILE = os.path.join(".preview", "activity.json")
AGENTS_FILE = os.path.join(".preview", "agents.json")
AGENTS_EVENTS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop", "Stop")
KEEP_S = 1800     # a session record untouched this long is dropped


def turn_since(path, event, now):
    """When the current turn began. UserPromptSubmit starts one; PostToolUse and Stop keep the start the file already
    has, so the page can show how long Claude has been at it and, after Stop, how long the turn took. A PostToolUse
    with no working turn on file (an unreadable file, or one written by an older hook) starts the clock there."""
    if event == "UserPromptSubmit":
        return now
    try:
        with open(path, encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = None
    since = prev.get("since") if isinstance(prev, dict) else None
    ok = isinstance(since, (int, float)) and not isinstance(since, bool) and since <= now
    if event == "Stop":
        return since if ok else None
    return since if ok and prev.get("state") == "working" else now


def clean_ask(ask):
    """The ask as one trimmed line (whitespace runs collapsed), capped; None when it is not a string or is empty."""
    if not isinstance(ask, str):
        return None
    ask = " ".join(ask.split())[:ASK_MAX].strip()
    return ask or None


def clean_gate(gate):
    """A well-formed gate {id, ask, at} from what a file holds, or None."""
    if not isinstance(gate, dict):
        return None
    gid, at = gate.get("id"), gate.get("at")
    if not isinstance(gid, str) or not GATE_ID.match(gid):
        return None
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    ask = clean_ask(gate.get("ask"))
    return {"id": gid, "ask": ask, "at": at} if ask else None


def read_doc(path):
    """The activity file as a dict, or None when it is missing, unreadable or not an object."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def replace_doc(base, doc):
    """Atomically replace <base>/.preview/activity.json with `doc`."""
    folder = os.path.join(base, ".preview")
    body = json.dumps(doc)
    fd, tmp = tempfile.mkstemp(prefix=".activity.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        os.replace(tmp, os.path.join(base, FILE))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_activity(base, event):
    """Replace <base>/.preview/activity.json with the state `event` stands for. False when there is nowhere to write.
    The gate a command wrote this turn is kept by PostToolUse and Stop and dropped by UserPromptSubmit."""
    state = STATES.get(event)
    folder = os.path.join(base, ".preview")
    if state is None or not os.path.isdir(folder):
        return False
    now = round(time.time(), 3)
    path = os.path.join(base, FILE)
    doc = {"state": state, "at": now, "event": event}
    since = turn_since(path, event, now)
    if since is not None:
        doc["since"] = since
    if event != "UserPromptSubmit":
        prev = read_doc(path)
        gate = clean_gate(prev.get("gate")) if prev else None
        if gate:
            doc["gate"] = gate
    replace_doc(base, doc)
    return True


def describe(tool):
    """The one-word verb for a tool call. Nothing about the call itself (file, command, pattern) is kept."""
    if tool == "Read":
        return "Reading"
    if tool in ("Edit", "MultiEdit", "NotebookEdit"):
        return "Editing"
    if tool == "Write":
        return "Writing"
    if tool == "Bash":
        return "Running"
    if tool in ("Grep", "WebSearch"):
        return "Searching"
    if tool == "Glob":
        return "Finding"
    if tool in ("Agent", "Task"):
        return "Delegating"
    if tool == "WebFetch":
        return "Fetching"
    if tool == "Skill":
        return "Loading"
    if tool == "TodoWrite" or tool.startswith("Task"):
        return "Planning"
    return "Using"


def _count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def _stamp(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else 0


def write_agents(base, event, sid, tool):
    """Update this session's record in <base>/.preview/agents.json for `event`. False when there is nowhere to write."""
    folder = os.path.join(base, ".preview")
    if event not in AGENTS_EVENTS or not os.path.isdir(folder):
        return False
    path = os.path.join(base, AGENTS_FILE)
    lock = None
    try:
        import fcntl
        lock = os.open(folder, os.O_RDONLY)
        fcntl.flock(lock, fcntl.LOCK_EX)
    except Exception:       # no fcntl, or a folder that cannot be locked: write without it
        if lock is not None:
            os.close(lock)
        lock = None
    try:
        now = round(time.time(), 3)
        doc = read_doc(path) or {}
        raw = doc.get("sessions") if isinstance(doc.get("sessions"), dict) else {}
        sessions = {k: v for k, v in raw.items()
                    if isinstance(v, dict) and isinstance(v.get("at"), (int, float)) and not isinstance(v.get("at"), bool)
                    and now - v["at"] < KEEP_S}
        me = sessions.get(sid) if isinstance(sessions.get(sid), dict) else {}
        running, agents = _count(me.get("running")), _count(me.get("agents"))
        verb = me.get("verb") if isinstance(me.get("verb"), str) else ""
        done_at = _stamp(me.get("doneAt"))
        if event == "Stop":
            sessions.pop(sid, None)
        else:
            if event == "UserPromptSubmit":
                verb, running, agents, done_at = "", 0, 0, 0
            elif event == "PreToolUse":
                verb, running = describe(tool), running + 1
            elif event in ("PostToolUse", "PostToolUseFailure"):
                running, done_at = max(0, running - 1), now
            elif event == "SubagentStart":
                agents += 1
            else:       # SubagentStop
                agents = max(0, agents - 1)
            sessions[sid] = {"at": now, "verb": verb, "running": running, "doneAt": done_at, "agents": agents}
        if not sessions:        # the last session stopped: leave no file behind
            if os.path.exists(path):
                os.unlink(path)
            return True
        fd, tmp = tempfile.mkstemp(prefix=".agents.", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps({"sessions": sessions}) + "\n")
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    finally:
        if lock is not None:
            os.close(lock)      # releases the flock


def write_gate(base, gate_id, ask):
    """Add the gate a command stopped at to the activity file, leaving state / at / event / since as they are.
    False when the id or the ask is not valid or there is nowhere to write (no `.preview/`)."""
    ask = clean_ask(ask)
    folder = os.path.join(base, ".preview")
    if not isinstance(gate_id, str) or not GATE_ID.match(gate_id) or not ask or not os.path.isdir(folder):
        return False
    now = round(time.time(), 3)
    path = os.path.join(base, FILE)
    prev = read_doc(path)
    ok = (prev and prev.get("state") in ("working", "idle") and not isinstance(prev.get("at"), bool)
          and isinstance(prev.get("at"), (int, float)))
    doc = dict(prev) if ok else {"state": "working", "at": now, "event": "PostToolUse", "since": now}
    doc["gate"] = {"id": gate_id, "ask": ask, "at": now}
    replace_doc(base, doc)
    return True


def gate_cli(args):
    """`--gate <GATE-ID> <ask…> [--project <dir>]`. Never prints on success; a bad line prints one usage line."""
    rest = list(args[1:])
    folder = os.getcwd()
    if "--project" in rest:
        i = rest.index("--project")
        if i + 1 >= len(rest):
            sys.stderr.write("usage: activity.py --gate <G-ID> \"<what the person approves>\" [--project <dir>]\n")
            return
        folder = rest[i + 1]
        del rest[i:i + 2]
    if len(rest) < 2:
        sys.stderr.write("usage: activity.py --gate <G-ID> \"<what the person approves>\" [--project <dir>]\n")
        return
    base = pb_project(folder)
    if base and not write_gate(base, rest[0], " ".join(rest[1:])):
        sys.stderr.write("activity.py --gate: the id must look like G-JTBD and the ask must not be empty\n")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--gate":
        gate_cli(sys.argv[1:])
        return
    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    event = data.get("hook_event_name")
    if not isinstance(event, str) and len(sys.argv) > 1:
        event = {"working": "UserPromptSubmit", "idle": "Stop"}.get(sys.argv[1])
    folder = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    base = pb_project(folder)
    if base and isinstance(event, str):
        try:
            if event in STATES:
                write_activity(base, event)
        finally:
            if event in AGENTS_EVENTS:
                sid = data.get("session_id") if isinstance(data.get("session_id"), str) and data.get("session_id") else "unknown"
                tool = data.get("tool_name") if isinstance(data.get("tool_name"), str) else ""
                write_agents(base, event, sid, tool)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
