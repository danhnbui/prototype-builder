#!/usr/bin/env python3
"""
pb-preview-register — keep exactly ONE canonical preview entry per project in .claude/launch.json.

The rule (CLAUDE.md → "One preview per project"): a project contributes at most one launch
configuration — the live `/pb:preview` server reading that project's registry.json. This helper makes
that true and idempotent:

  * UPSERTS a single entry named `pb-preview · <folder-slug>` (update in place, never append a duplicate),
  * COLLAPSES any duplicate pb-preview entries for the same project down to one,
  * NEVER touches entries it doesn't own — anything whose name doesn't start with `pb-preview` (your
    hand-made configs, other projects' entries) is left exactly as-is.

It only manages launch.json when the in-app preview pane is used; viewing in a normal browser needs no
launch.json at all. Stdlib only — matching render.py / serve.py and the project's no-deps stance.

Usage:
  python3 preview_register.py --port <N> [--project-dir .] [--registry registry.json]
                              [--launch <path>] [--serve <path>] [--shell <path>]
                              [--name <explicit>] [--dry-run]
"""
import argparse, json, os, re, sys, tempfile

MARKER = "pb-preview"  # an entry is tool-owned iff its name starts with this


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "project"


def load_launch(path):
    """Return (data, created). Tolerate a missing file (fresh skeleton); refuse to clobber a malformed one."""
    if not os.path.exists(path):
        return {"version": "0.0.1", "configurations": []}, True
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit("pb-preview-register: %s is not valid JSON (line %d) — refusing to overwrite." % (path, e.lineno))
    if not isinstance(data, dict) or not isinstance(data.get("configurations"), list):
        sys.exit("pb-preview-register: %s has no 'configurations' array — refusing to overwrite." % path)
    return data, False


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        prog="pb-preview-register",
        description="Keep exactly one canonical pb-preview entry per project in .claude/launch.json.")
    ap.add_argument("--port", type=int, required=True, help="the port the running server bound")
    ap.add_argument("--project-dir", default=".", help="project folder; its basename is the slug")
    ap.add_argument("--registry", default=None, help="registry.json (default: <project-dir>/registry.json)")
    ap.add_argument("--launch", default=None, help="launch.json (default: <project-dir>/.claude/launch.json)")
    ap.add_argument("--serve", default=os.path.join(here, "serve.py"), help="serve.py the entry launches")
    ap.add_argument("--shell", default=os.path.normpath(os.path.join(here, "..", "template", "prototype.html")),
                    help="shell template the entry passes to serve.py")
    ap.add_argument("--name", default=None, help="override the derived entry name")
    ap.add_argument("--dry-run", action="store_true", help="print the planned change; write nothing")
    args = ap.parse_args()

    project_dir = os.path.realpath(args.project_dir)
    slug = slugify(os.path.basename(project_dir))
    name = args.name or ("%s · %s" % (MARKER, slug))
    registry = os.path.abspath(args.registry) if args.registry else os.path.join(project_dir, "registry.json")
    if not os.path.isfile(registry):
        sys.exit("pb-preview-register: registry not found: %s" % registry)
    serve = os.path.abspath(args.serve)
    shell = os.path.abspath(args.shell)
    launch = os.path.abspath(args.launch) if args.launch else os.path.join(project_dir, ".claude", "launch.json")

    entry = {
        "name": name,
        "runtimeExecutable": "python3",
        "runtimeArgs": [serve, registry, "--shell", shell, "--port", str(args.port), "--no-open"],
        "port": args.port,
    }

    data, created = load_launch(launch)

    def ours_this_project(c):
        nm = c.get("name", "")
        if not nm.startswith(MARKER):
            return False  # foreign — never ours
        # ours, and for THIS project if it references this registry (or matches the canonical name)
        return registry in (c.get("runtimeArgs") or []) or nm == name

    kept, replaced, pruned = [], False, 0
    for c in data["configurations"]:
        if ours_this_project(c):
            if not replaced:
                kept.append(entry)   # upsert in place — first match keeps its position
                replaced = True
            else:
                pruned += 1          # dedupe — drop additional matches for this project
        else:
            kept.append(c)           # foreign, or ours-but-another-project — untouched
    if not replaced:
        kept.append(entry)           # none existed → append the one canonical entry

    new_data = dict(data)
    new_data["configurations"] = kept
    new_data.setdefault("version", "0.0.1")

    others = len(kept) - 1
    verb = "would set" if args.dry_run else "set"
    summary = '%s "%s" (port %d)' % (verb, name, args.port)
    if pruned:
        summary += "; pruned %d duplicate%s" % (pruned, "" if pruned == 1 else "s")
    summary += "; %d other entr%s untouched" % (others, "y" if others == 1 else "ies")

    if new_data == data and not created:
        print('pb-preview-register: no change — "%s" already canonical in %s' % (name, launch))
        return
    if args.dry_run:
        print("pb-preview-register (dry-run): " + summary)
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return

    os.makedirs(os.path.dirname(launch), exist_ok=True)
    text = json.dumps(new_data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(launch), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, launch)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print("pb-preview-register: " + summary + " → " + launch)


if __name__ == "__main__":
    main()
