#!/usr/bin/env python3
"""PreToolUse (Bash) hook: one line of advice when a shell command breaks a pb footprint rule.

Reads the hook JSON on stdin and, inside a pb project, prints
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "..."}}` when the
command is a hand-written Playwright script, `--idle-exit 0`, a detached `serve.py`, a `kill` of a
preview, or a direct write of registry.json, and names the pb tool to use instead.

It only advises. It never prints `permissionDecision` (that would skip the user's permission
prompt), never exits 2, and any error, bad stdin or no match prints nothing and exits 0.
Silent outside a pb project (see `pb_project`). Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import re
import sys

READ_ONLY = re.compile(r"^\s*(?:grep|egrep|rg|cat|head|tail|less|ls|git\s+(?:grep|log|diff|show))\b")
RUNS_PB_BROWSER = re.compile(r"\b(?:shot|test_run)\.py\b")
PLAYWRIGHT = re.compile(r"sync_playwright|chromium\.launch|\.launch\(")
IDLE_EXIT_OFF = re.compile(r"--idle-exit(?:\s+|=)0(?![\d.])")
DETACHED = re.compile(r"\bnohup\b|(?<![&>\d])&\s*(?:$|;)", re.M)
KILL = re.compile(r"(?:^|[;&|(`]|\$\(|\bxargs\s+(?:-\S+\s+)*)\s*(?:sudo\s+)?(?:kill|pkill|killall)\b", re.M)
KILL_TARGET = re.compile(r"serve\.py|\blsof\b|\bport\b|:\d{4,5}\b", re.I)
LSOF_T = re.compile(r"\blsof\s+-\w*t")
JSON_DUMP = re.compile(r"\bjson\.dump\(")
OPEN_W = re.compile(r"open\([^)]*registry\.json[^)]*['\"][wa]")
WRITE_TEXT = re.compile(r"\.write_text\(")
REDIRECT = re.compile(r">>?\s*['\"]?[\w./-]*registry\.json|\btee\b[^|;&\n]*registry\.json")


def pb_project(folder):
    for base in (folder, os.path.join(folder, ".prototype")):
        if not os.path.isfile(os.path.join(base, "registry.json")):
            continue
        if os.path.isdir(os.path.join(base, "render")) or os.path.isfile(
                os.path.join(base, "memory", "constitution.md")):
            return base
    return None


def advise(cmd):
    """The advice lines for this command (empty when it is fine)."""
    out = []
    if PLAYWRIGHT.search(cmd) and not RUNS_PB_BROWSER.search(cmd) and not READ_ONLY.match(cmd):
        out.append("a hand-written Playwright script is not how pb looks at a render: use "
                   "`shot.py registry.json --screen <id>` (or `test_run.py` to test).")
    if IDLE_EXIT_OFF.search(cmd):
        out.append("`--idle-exit 0` makes a preview that never exits: leave the default "
                   "(8 h idle) and start it with `serve.py registry.json --ensure`.")
    if "serve.py" in cmd and DETACHED.search(cmd):
        out.append("do not detach serve.py with nohup or a trailing &: "
                   "`serve.py registry.json --ensure` starts or reuses it and prints the URL.")
    if (KILL.search(cmd) and KILL_TARGET.search(cmd)) or LSOF_T.search(cmd):
        out.append("do not kill a preview or hunt it by port: `serve.py --status` finds it, "
                   "`serve.py --stop` stops it, `serve.py registry.json --ensure` restarts it.")
    if "slice.py" not in cmd and re.search(r"registry", cmd, re.I):
        writes = (JSON_DUMP.search(cmd) or OPEN_W.search(cmd) or REDIRECT.search(cmd)
                  or (WRITE_TEXT.search(cmd) and "registry.json" in cmd))
        if writes:
            out.append("do not write registry.json by hand (it bypasses the registry lock): "
                       "patch one slice with `slice.py set <kind> <id>`.")
    return out


def main():
    data = json.loads(sys.stdin.read())
    if not isinstance(data, dict):
        return
    cmd = (data.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return
    folder = data.get("cwd") if isinstance(data.get("cwd"), str) and data.get("cwd") else os.getcwd()
    if not pb_project(folder):
        return
    lines = advise(cmd)
    if not lines:
        return
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "additionalContext": "pb: " + " ".join(lines)}}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
