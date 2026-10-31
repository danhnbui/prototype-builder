#!/usr/bin/env python3
"""PreToolUse (Chrome DevTools / claude-in-chrome MCP) hook: name the cheaper pb tool for a browser check.

Reads the hook JSON on stdin and, inside a pb project, prints
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "..."}}` with one line:
`shot.py --no-png --eval` for a fact, `shot.py --selector` for one look, and DevTools only for
network or performance debugging or when the user asked for it.

A check round is many calls, so it speaks on the first such call of a session and then on every 25th,
counted per `session_id` in a small file in a per-user temp folder. If that file cannot be read or
written it stays silent.

It only advises. It never prints `permissionDecision` (that would skip the user's permission prompt),
never exits 2, and any error, bad stdin or no match prints nothing and exits 0.
Silent outside a pb project (see `bash_advice.pb_project`). Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bash_advice import pb_project  # noqa: E402  (shared: one definition of "a pb project")

EVERY = 25
ADVICE = ("pb: to check a render, `shot.py --no-png --eval \"<JS>\" --console` answers a fact (text there, "
          "hidden for a role, overflow, console errors) with no image, and `shot.py --selector <CSS>` is "
          "one look at one width. Chrome DevTools is for network or performance debugging, or when the "
          "user asked for it. Ladder: canon.md § Checking a change.")


def count_call(session_id):
    """Add one to this session's call count and return it; None when it cannot be kept."""
    uid = os.getuid() if hasattr(os, "getuid") else "u"
    folder = os.path.join(tempfile.gettempdir(), "pb-hooks-%s" % uid)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id)[:80] or "session"
    path = os.path.join(folder, "browser-%s.count" % name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            n = int(f.read().strip() or "0")
    except (OSError, ValueError):
        n = 0
    n += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n))
    return n


def main():
    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    folder = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    if not pb_project(folder):
        return
    sid = data.get("session_id")
    n = count_call(sid if isinstance(sid, str) else "")
    if n != 1 and n % EVERY != 0:
        return
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": ADVICE}}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
