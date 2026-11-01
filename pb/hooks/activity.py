#!/usr/bin/env python3
"""UserPromptSubmit / PostToolUse / Stop hook: tell the open preview whether Claude is working.

Reads the hook JSON on stdin and, inside a pb project whose `.preview/` folder already exists (a preview has
run there), writes `.preview/activity.json` atomically:

    {"state": "working" | "idle", "at": <epoch seconds>, "event": "UserPromptSubmit" | "Stop"}

`UserPromptSubmit` means Claude has started on a prompt (working); `Stop` means it has finished the turn (idle,
so it is the person's turn). The preview server watches that one file, tells every open page, and the page's
progress item says Working / Your turn. Every finished tool call (`PostToolUse`) writes "working" again, so a
long turn stays Working. A turn cancelled with Esc fires no Stop, so the page does not trust "working" for more
than 90 s after the last write (pb/template/prototype.html, pbProgStatus).

It only reports. It never prints (so it adds nothing to the model's context), never blocks, never decides a
permission, and any error, bad stdin or a folder that is not a pb project with a `.preview/` writes nothing and
exits 0. It does not create `.preview/`: a project nobody has previewed gets no new folder.
Silent outside a pb project (see `bash_advice.pb_project`). Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bash_advice import pb_project  # noqa: E402  (shared: one definition of "a pb project")

# PostToolUse renews "working" on every finished tool call: a real pb turn runs for minutes, and the page's 90 s
# fallback would otherwise read Waiting while Claude is still at work. A turn cancelled with Esc makes no more tool
# calls, so the fallback still catches it.
STATES = {"UserPromptSubmit": "working", "PostToolUse": "working", "Stop": "idle"}
FILE = os.path.join(".preview", "activity.json")


def write_activity(base, event):
    """Replace <base>/.preview/activity.json with the state `event` stands for. False when there is nowhere to write."""
    state = STATES.get(event)
    folder = os.path.join(base, ".preview")
    if state is None or not os.path.isdir(folder):
        return False
    body = json.dumps({"state": state, "at": round(time.time(), 3), "event": event})
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
    return True


def main():
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
