"""
others_refs — which of a project's own files read `meta.others`.

`meta.others` is retired (D-33) but it can still be LIVE data: a render body or a runtime module may
read it (`((reg.meta || {}).others || {}).dataSlice`, `PB_REGISTRY.meta.others.layers`). Emptying it
then silently empties that prototype. Migration 0012 (moves it to memory/others.md) and the
R-RETIRED-DATA lint both ask this module first, so they agree.

`others_readers(base_dir, reg)` → sorted list of paths, relative to `base_dir` with `/` separators,
of the files whose text references `meta.others`. It scans render/**/*.js, render/**/*.css,
runtime/**/*.js and every `registry.runtime[]` entry's `src`. A match is `.others` (a word end) or
`['others']` / `["others"]`; comments and strings are not stripped, so a false positive is possible —
that only makes a caller keep the field, which is the safe side.

Stdlib only, no imports from the rest of pb (a migration loads it by path).
"""
import os
import re

_READ = re.compile(r"""\.others\b|\[\s*['"]others['"]\s*\]""")
_GLOBS = (("render", (".js", ".css")), ("runtime", (".js",)))


def _walk(base_dir, folder, exts):
    root = os.path.join(base_dir, folder)
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(exts):
                yield os.path.join(dirpath, name)


def _reads(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(_READ.search(f.read()))
    except OSError:
        return False


def others_readers(base_dir, reg):
    if not base_dir:
        return []
    base = os.path.abspath(base_dir)
    paths = set()
    for folder, exts in _GLOBS:
        paths.update(_walk(base, folder, exts))
    runtime = reg.get("runtime") if isinstance(reg, dict) else None
    for entry in runtime if isinstance(runtime, list) else []:
        src = entry.get("src") if isinstance(entry, dict) else None
        if isinstance(src, str) and src:
            paths.add(os.path.normpath(os.path.join(base, src)))
    out = set()
    for p in paths:
        if os.path.isfile(p) and _reads(p):
            out.add(os.path.relpath(p, base).replace(os.sep, "/"))
    return sorted(out)


def summarize(files, limit=3):
    """'a.js, b.js, c.js' or 'a.js, b.js, c.js +2 more'."""
    shown = ", ".join(files[:limit])
    return shown + (" +%d more" % (len(files) - limit) if len(files) > limit else "")
