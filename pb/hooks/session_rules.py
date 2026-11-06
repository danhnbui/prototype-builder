#!/usr/bin/env python3
"""SessionStart hook: put Product Builder's key rules in front of the model in a pb project.

A rule written in a command file does not reach a free-form session, so this prints a short digest
(at most 25 lines and 1,600 characters) when the working folder is a pb project, and nothing
anywhere else. It only advises: plain context, no decision, always exit 0.

A pb project = `registry.json` in the working folder (or its `.prototype/`) beside either a
`render/` folder or `memory/constitution.md`, or in one of the working folder's immediate child
folders (bash_advice.pb_project: a session often starts one folder above the registry). No JSON is parsed.

Stdlib only (run as `python3 -S -B`), Python 3.7+.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bash_advice import pb_project  # noqa: E402  (shared: one definition of "a pb project")

MAX_LINES = 25
MAX_CHARS = 1600


def digest(plugin_root, project):
    tools = os.path.join(plugin_root, "tools")
    lines = [
        "Product Builder (pb) project: %s" % project,
        "Rules (canon: %s):" % os.path.join(plugin_root, "docs", "canon.md"),
        "1. State lives in registry.json. Read or patch one slice, never the whole file.",
        "2. prototype.html is rendered from it, never hand-edited, never rendered per tweak.",
        "3. Gate (drift/Stack/DS) only for screen, component or logic changes; tokens, copy, spacing skip it.",
        "Read the registry with slice.py find <text> or get <kind> <id> --fields a,b. Every subagent call sets model (sonnet; haiku to search).",
        "Tools (python3 <path>):",
        "- %s registry.json --ensure   start or reuse the preview, prints the URL" % os.path.join(tools, "serve.py"),
        "- %s registry.json --screen <id>   look at a render" % os.path.join(tools, "shot.py"),
        "- %s get|set <kind> <id>   read or patch the registry" % os.path.join(tools, "slice.py"),
        "NEVER: a hand-written Playwright script; serve.py with & / nohup / --idle-exit 0;",
        "kill a preview (serve.py --stop); json.dump or a redirect into registry.json.",
        "After a change use the lowest check that answers it: none, lint_registry.py --exec, shot.py --no-png --eval,",
        "shot.py --selector, and every width only for a new screen. DevTools is not how pb looks.",
        "Roles, permissions, demo entries: meta.permissions, meta.personas, meta.demo; bodies read pbCan(), not a role module.",
        "Structural work (new feature, flow, revamp): /pb:explore \"<goal>\". Point changes: /pb:build.",
    ]
    text = "\n".join(lines[:MAX_LINES])
    return text[:MAX_CHARS]


def main():
    project = pb_project(os.getcwd())
    if not project:
        return
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                  "additionalContext": digest(root, project)}}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # a broken hook must never get in the way
        pass
    sys.exit(0)
