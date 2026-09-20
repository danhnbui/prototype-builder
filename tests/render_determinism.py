#!/usr/bin/env python3
"""
render_determinism.py — the same registry renders to the same bytes, stamp aside.

Lever 2 says the render is deterministic: same registry in, same HTML out, no model
and no randomness. One thing in the output is *deliberately* not fixed — the shell
stamp `<!-- pb-shell vX · rendered <ISO-8601 Z> -->`, which carries a wall-clock time
so /pb:test --drift and docs/upgrading.md can tell a stale render from a fresh one.

That makes a naive `sha256(a) == sha256(b)` a coin flip: it passes when both renders
land inside the same second and fails when they straddle one. CI hit exactly that —
green on the PR, red on main twenty seconds later, both files 522,777 bytes.

So: compare with the timestamp normalized, and separately assert the stamp is present
and well-formed, so "ignore the stamp" can never quietly become "ignore a missing one".

  1. Two renders of the golden differ ONLY in the stamp's timestamp.
  2. Both carry a well-formed stamp naming the current plugin version.
  3. Renders separated by a real second boundary still satisfy (1) — the case that
     actually broke, so it is the case that gets exercised.

Usage:  python3 tests/render_determinism.py
Exit:   0 = clean · 1 = a failure
"""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "pb", "tools", "render.py")
REGISTRY = os.path.join(ROOT, "fixtures", "golden", "registry.json")
SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")

STAMP = re.compile(r"<!-- pb-shell (\S+) \xb7 rendered (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) -->")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def render(out):
    r = subprocess.run([sys.executable, RENDER, REGISTRY, SHELL, out],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise SystemExit("render.py failed (exit %d)" % r.returncode)
    with open(out, encoding="utf-8") as fh:
        return fh.read()


def normalized(text):
    """The render with its one intentionally-variable field pinned."""
    return hashlib.sha256(
        STAMP.sub("<!-- pb-shell <v> \xb7 rendered <ts> -->", text).encode("utf-8")
    ).hexdigest()


def plugin_version():
    import json
    p = os.path.join(ROOT, "pb", ".claude-plugin", "plugin.json")
    return json.load(open(p, encoding="utf-8")).get("version")


tmp = tempfile.mkdtemp(prefix="pb-determinism-")
a_path = os.path.join(tmp, "a.html")
b_path = os.path.join(tmp, "b.html")
c_path = os.path.join(tmp, "c.html")

print("1 · two back-to-back renders agree once the stamp is pinned")
a = render(a_path)
b = render(b_path)
check(normalized(a) == normalized(b), "same registry -> same bytes (stamp normalized)")
check(len(a) == len(b), "both renders are the same length (%d vs %d)" % (len(a), len(b)))

print("2 · the stamp is present and well-formed")
ver = plugin_version()
for name, text in (("a", a), ("b", b)):
    m = STAMP.search(text)
    check(m is not None, "render %s carries a pb-shell stamp" % name)
    if m:
        stamped = m.group(1).lstrip("v")          # the stamp writes "v2.0.0"; plugin.json holds "2.0.0"
        check(stamped == ver,
              "render %s stamps the plugin version (%s == %s)" % (name, stamped, ver))

print("3 · a render across a second boundary is still equal (the case CI hit)")
# Land the next render in a different wall-clock second on purpose. Without the
# normalization above this is the exact comparison that failed on main.
time.sleep(1.05)
c = render(c_path)
ma, mc = STAMP.search(a), STAMP.search(c)
check(ma and mc and ma.group(2) != mc.group(2),
      "the two renders really are in different seconds (%s vs %s)"
      % (ma.group(2) if ma else "?", mc.group(2) if mc else "?"))
check(normalized(a) == normalized(c), "and they are still byte-equal apart from the stamp")

print()
if fails:
    print("FAIL — %d problem(s)" % len(fails))
    sys.exit(1)
print("PASS — the render is deterministic; only the stamp varies")
