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
    """The digest, cut to MAX_CHARS by whole lines. The plugin root is printed four times (the canon and three
    tools, by absolute path so a line can be run as written), so a long install or project path used to push the
    tail past the cap and the last rule was cut mid-line. Each line now has a drop rank: 0 is always kept, and
    while the text is over budget every line of the highest rank left goes (they belong together)."""
    tools = os.path.join(plugin_root, "tools")
    lines = [
        ("Product Builder (pb) project: %s" % project, 0),
        ("Rules (canon: %s):" % os.path.join(plugin_root, "docs", "canon.md"), 0),
        ("1. State lives in registry.json. Read or patch one slice, never the whole file.", 0),
        ("2. prototype.html is rendered from it, never hand-edited, never rendered per tweak.", 0),
        ("3. Gate (drift/Stack/DS) only for screen, component or logic changes; tokens, copy, spacing skip it.", 0),
        ("Read the registry with slice.py find <text> or get <kind> <id> --fields a,b. Every subagent call sets model (sonnet; haiku to search).", 1),
        ("Tools (python3 <path>):", 0),
        ("- %s registry.json --ensure   start or reuse the preview, prints the URL" % os.path.join(tools, "serve.py"), 0),
        ("- %s registry.json --screen <id>   look at a render" % os.path.join(tools, "shot.py"), 0),
        ("- %s get|set <kind> <id>   read or patch the registry" % os.path.join(tools, "slice.py"), 0),
        ("NEVER: a hand-written Playwright script; serve.py with & / nohup / --idle-exit 0;", 0),
        ("kill a preview (serve.py --stop); json.dump or a redirect into registry.json.", 0),
        ("After a change use the lowest check that answers it: none, lint_registry.py --exec, shot.py --no-png --eval,", 2),
        ("shot.py --selector, and every width only for a new screen. DevTools is not how pb looks.", 2),
        ("Roles, permissions, demo entries: meta.permissions, meta.personas, meta.demo; bodies read pbCan(), not a role module.", 3),
        ("Structural work (new feature, flow, revamp): /pb:explore \"<goal>\". Point changes: /pb:build.", 0),
    ][:MAX_LINES]
    while len("\n".join(t for t, _ in lines)) > MAX_CHARS:
        worst = max(r for _, r in lines)
        if worst == 0:
            break
        lines = [(t, r) for t, r in lines if r != worst]
    return "\n".join(t for t, _ in lines)[:MAX_CHARS]   # the hard cut is left only for an absurd path


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
