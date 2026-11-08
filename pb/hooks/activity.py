#!/usr/bin/env python3
"""UserPromptSubmit / PostToolUse / Stop hook: tell the open preview whether Claude is working.

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
        write_activity(base, event)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
