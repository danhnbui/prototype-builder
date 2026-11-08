#!/usr/bin/env python3
"""
serve_watch.py — the /pb:preview server watches every source file a page is built from, and bounds its log.

  1. watched set    spec/**/*.json, logic/**/*.json (and a newly added one), the explore compare shell,
                    beside the render bodies, runtime modules, shells and the registry
  2. reload kind    a change to a spec, logic or explore-shell file bumps with kind "reload" (the pages
                    reload; only registry.json and the drafts are an in-place "update")
  3. log trim       a start trims .preview/server.log over 1 MB to its last 256 KB, from a line start,
                    leaving a smaller one alone
  4. logic key      render._logic_key changes when a registry.runtime[] module changes

Stdlib only, no browser, no server process: the state and check functions are called directly, on a temp
copy of fixtures/golden.  Usage:  python3 tests/serve_watch.py
Exit: 0 pass · 1 fail
"""
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GOLDEN_DIR = os.path.join(ROOT, "fixtures", "golden")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import serve  # noqa: E402
import render  # noqa: E402
import clean  # noqa: E402

_fail = []


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        _fail.append(what)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def bump_mtime(path):
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def main():
    tmp = tempfile.mkdtemp(prefix="pb-serve-watch-")
    try:
        proj = os.path.join(tmp, "proj")
        shutil.copytree(GOLDEN_DIR, proj)
        reg = os.path.join(proj, "registry.json")
        shell = os.path.join(ROOT, "pb", "template", "prototype.html")
        xshell = os.path.join(tmp, "explore.html")
        write(xshell, "<html></html>")
        write(os.path.join(proj, "spec", "components", "a.json"), "{}")
        write(os.path.join(proj, "logic", "screens", "b.json"), "{}")

        state = serve.State(reg, shell, os.path.join(proj, "prototype.html"), False,
                            explore_shell_path=xshell, idle_exit_min=0, debounce_ms=0)

        # 1. watched set
        w = set(state.watched)
        check(os.path.join(proj, "spec", "components", "a.json") in w, "watched includes spec/**/*.json")
        check(os.path.join(proj, "logic", "screens", "b.json") in w, "watched includes logic/**/*.json")
        check(xshell in w, "watched includes the explore compare shell")
        check(reg in w and shell in w, "watched still includes the registry and shell")
        late = os.path.join(proj, "spec", "screens", "late.json")
        write(late, "{}")
        check(late in set(state.watched), "a spec file added later is picked up on the next poll")
        os.remove(late)
        s2 = serve.State(reg, shell, os.path.join(proj, "prototype.html"), False, idle_exit_min=0)
        check(xshell not in set(s2.watched) and None not in s2.watched, "no explore shell set -> nothing extra watched")

        # 2. reload kind
        serve.refresh(state)  # prime
        for rel in (os.path.join(proj, "spec", "components", "a.json"),
                    os.path.join(proj, "logic", "screens", "b.json"), xshell):
            before = state.version
            bump_mtime(rel)
            changed = serve.refresh(state)
            kind = state.kinds[-1][1] if state.kinds else None
            check(rel in changed and state.version == before + 1 and kind == "reload",
                  "change to %s is a reload-kind bump (got %s)" % (os.path.basename(rel), kind))
        before = state.version
        bump_mtime(reg)
        serve.refresh(state)
        check(state.kinds[-1] == (before + 1, "update"), "registry.json stays an in-place update")

        # 3. log trim
        logp = os.path.join(proj, ".preview", "server.log")
        os.makedirs(os.path.dirname(logp), exist_ok=True)
        lines = [("line %06d " % i + "x" * 80 + "\n") for i in range(15000)]   # ~1.4 MB
        data = "".join(lines).encode()
        with open(logp, "wb") as f:
            f.write(data)
        check(len(data) > clean.LOG_MAX, "fixture log is over 1 MB (%d bytes)" % len(data))
        dropped = serve.trim_server_log(proj)
        out = open(logp, "rb").read()
        check(dropped == len(data) - len(out) and 0 < len(out) <= clean.LOG_KEEP,
              "trimmed to at most 256 KB (%d bytes left)" % len(out))
        check(out == data[-len(out):] and out.startswith(b"line "), "what is left is the newest tail, from a line start")
        check(len(out) > clean.LOG_KEEP - 200, "nearly the whole 256 KB is kept")
        small = b"tiny\n" * 10
        with open(logp, "wb") as f:
            f.write(small)
        check(serve.trim_server_log(proj) == 0 and open(logp, "rb").read() == small, "a log under 1 MB is left alone")
        check(serve.trim_server_log(os.path.join(tmp, "nope")) == 0, "no log -> no error")

        # 4. logic key follows a runtime module
        mod = os.path.join(proj, "runtime", "m.js")
        write(mod, "var a = 1;\n")
        with open(reg, encoding="utf-8") as f:
            r = json.load(f)
        r["runtime"] = [{"id": "m", "src": "runtime/m.js"}]
        write(reg, json.dumps(r))
        k1 = render._logic_key(proj)
        bump_mtime(mod)
        k2 = render._logic_key(proj)
        check(k1 is not None and k1 != k2, "render._logic_key changes when a runtime module changes")
        check(render._logic_key(proj) == k2, "...and is stable when nothing changed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n%s" % ("serve_watch: FAIL (%d)" % len(_fail) if _fail else "serve_watch: PASS"))
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
