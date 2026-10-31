#!/usr/bin/env python3
"""
shell_lint.py — static hygiene checks on the shipped shell (pb/template/prototype.html).

Guards the Phase 3 fixes so they can't silently regress:
  T3.1 — no duplicate keys in the CHAT_PROMPTS object; no v0.4 'agent-skill-set' /
         'USER-FLOW-GUIDE' references anywhere in the shell.
  T3.2 — no dead wireflow exports (WIREFLOW_SCREENS / WIREFLOW_NOTES / wfCardHtml).
  T3.4 — no v0.4 'cp template.html' authoring instruction in the header comment.
  SRI  — no third-party <script src=http…> / <link rel=stylesheet href=http…> without integrity=,
         and no fonts.googleapis, in any of the three shells or in a render of fixtures/golden;
         the self-hosted Inter in fonts.css decodes to real woff2 (wOF2 magic).

Usage:  python3 tests/shell_lint.py
Exit:   0 = clean · 1 = a regression
"""
import base64
import importlib.util
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "pb", "template")
SHELL = os.path.join(TPL, "prototype.html")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


_TAG = re.compile(r"<(script|link)\b[^>]*>", re.I)


def unprotected_loads(html):
    """Every external <script src=http…> / <link rel=stylesheet href=http…> tag lacking integrity=,
    plus any fonts.googleapis reference. A same-origin or inline asset is not a third-party load."""
    bad = []
    for m in _TAG.finditer(html):
        tag = m.group(0)
        if m.group(1).lower() == "script":
            ext = re.search(r"\bsrc\s*=\s*[\"']?(?:https?:)?//", tag, re.I)
        else:
            ext = (re.search(r"\brel\s*=\s*[\"']?stylesheet", tag, re.I)
                   and re.search(r"\bhref\s*=\s*[\"']?(?:https?:)?//", tag, re.I))
        if ext and "integrity=" not in tag.lower():
            bad.append(tag[:120])
    if "fonts.googleapis" in html:
        bad.append("fonts.googleapis")
    return bad


def _load(stem, file_path):
    spec = importlib.util.spec_from_file_location(stem, file_path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[stem] = m
    spec.loader.exec_module(m)
    return m


def sri_checks():
    render = _load("render", os.path.join(ROOT, "pb", "tools", "render.py"))

    # the check is live: a bare CDN tag, a bare stylesheet and a Google Fonts link all fail it
    bare = ('<script src="https://cdn.example.net/x.js"></script>'
            '<link rel="stylesheet" href="https://cdn.example.net/x.css">'
            '<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">')
    check(len(unprotected_loads(bare)) == 4, "the SRI check fails on a bare CDN <script>, <link> and fonts.googleapis")
    ok = ('<script src="https://cdn.example.net/x.js" integrity="sha384-abc" crossorigin="anonymous"></script>'
          '<script>var a = 1;</script><script src="runtime.js"></script>')
    check(not unprotected_loads(ok), "the SRI check passes a pinned script, an inline one and a same-origin one")

    for name in ("prototype.html", "design-system.html", "explore-compare.html"):
        html = render.inject_chrome(open(os.path.join(TPL, name), encoding="utf-8").read())
        check(not unprotected_loads(html), f"{name}: no third-party load without integrity (after chrome injection)")

    with tempfile.TemporaryDirectory() as d:
        proto, ds = os.path.join(d, "p.html"), os.path.join(d, "ds.html")
        render.render_file(GOLDEN, os.path.join(TPL, "prototype.html"), proto)
        render.render_ds_file(GOLDEN, os.path.join(TPL, "design-system.html"),
                              os.path.join(TPL, "runtime.js"), ds)
        for label, f in (("prototype render", proto), ("design-system render", ds)):
            html = open(f, encoding="utf-8").read()
            check(not unprotected_loads(html), f"golden {label}: no third-party load without integrity")
            check("@font-face" in html and "font/woff2;base64," in html, f"golden {label}: carries the self-hosted Inter")

    # the fonts are real woff2, not a truncated paste
    css = open(os.path.join(TPL, "fonts.css"), encoding="utf-8").read()
    blobs = re.findall(r"url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)", css)
    check(len(blobs) == 3, f"fonts.css holds three @font-face blocks (found {len(blobs)})")
    for i, b in enumerate(blobs, 1):
        raw = base64.b64decode(b)
        check(raw[:4] == b"wOF2", f"fonts.css block {i} decodes to woff2 (magic {raw[:4]!r}, {len(raw)} bytes)")
    check(os.path.isfile(os.path.join(TPL, "fonts.LICENSE.txt")), "fonts.LICENSE.txt travels with the font")

    # Mermaid is the one pinned CDN script
    proto_src = open(SHELL, encoding="utf-8").read()
    check(re.search(r'mermaid@\d+\.\d+\.\d+/dist/mermaid\.min\.js"[^>]*integrity="sha384-[A-Za-z0-9+/=]+"', proto_src)
          is not None, "Mermaid is pinned to an exact version with a sha384 integrity")


def main():
    src = open(SHELL, encoding="utf-8").read()

    # T3.1 — CHAT_PROMPTS has no duplicate keys
    m = re.search(r"const CHAT_PROMPTS\s*=\s*\{(.*?)\};", src, re.S)
    check(m is not None, "CHAT_PROMPTS block found")
    if m:
        keys = re.findall(r"'(/pb:[a-z-]+)'\s*:", m.group(1))
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        check(not dupes, f"CHAT_PROMPTS has no duplicate keys (dupes: {dupes})")

    # T3.1 — no v0.4 ecosystem references
    for term in ("agent-skill-set", "USER-FLOW-GUIDE"):
        check(term not in src, f"no '{term}' reference in the shell")

    # T3.2 — no dead wireflow exports
    for sym in ("WIREFLOW_SCREENS", "WIREFLOW_NOTES", "wfCardHtml"):
        check(sym not in src, f"no dead wireflow symbol '{sym}' in the shell")

    # T3.4 — no v0.4 'cp template.html' authoring instruction
    check("cp template.html" not in src,
          "no v0.4 'cp template.html' instruction in the header")

    sri_checks()

    print()
    if _fail:
        print(f"✗ {len(_fail)} shell-lint failure(s).")
        sys.exit(1)
    print("✓ shell-lint clean.")


if __name__ == "__main__":
    main()
