#!/usr/bin/env python3
"""
render_escape.py — the narrow `</script` escape in render.py (v1.11.1 P0 regression guard).

render.py's _escape_body used to blanket-escape every `</` in a render body to `<\\/`. That is
right for the one sequence that can end a <script> element — the literal `</script` — but WRONG
for the JS regex literal /</g, the standard HTML-escape idiom `.replace(/</g, '&lt;')`. It became
/<\\/g: an unterminated regex that killed the whole inline script. A real project with 17 such
bodies rendered blank on BOTH routes. The fix escapes `</script` alone.

Asserts, on both render targets (prototype shell + design-system shell):
  1. _escape_body leaves /</g alone and still escapes </script in any case  (the unit probe)
  2. a body using /</g survives build_html() / build_ds() unmangled
  3. a body containing a literal '</script>' string is escaped, so the emitted page has exactly
     as many `</script` closers as the shell it was built from (no premature termination)
  4. (if `node` is on PATH) the emitted <script> block containing the bodies PARSES as JS, and —
     the negative control — the same body under the old blanket escape does NOT

Pure stdlib; node is optional (its sub-checks report SKIPPED when absent).

Usage:  python3 tests/render_escape.py
Exit:   0 = clean · 1 = a regression
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "pb", "template")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load_render():
    path = os.path.join(ROOT, "pb", "tools", "render.py")
    spec = importlib.util.spec_from_file_location("render", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A body that uses the /</g idiom (the thing the blanket escape broke) …
BODY_REGEX = (
    "function renderCmpEscUtil(props) {\n"
    "  props = props || {};\n"
    "  var s = String(props.text == null ? '' : props.text);\n"
    "  s = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;');\n"
    "  return '<span class=\"esc\">' + s + '</span>';\n"
    "}\n"
)
# … and a body that carries the real page-killer as a string literal, in both cases.
BODY_CLOSER = (
    "function renderCmpCloserAtom(props) {\n"
    "  return '<div class=\"c\">' + 'a</div>' + '<code>' + '</script>' + '</SCRIPT>' + '</code></div>';\n"
    "}\n"
)


def registry():
    return {
        "meta": {"name": "escape-guard", "schemaVersion": 10, "device": "laptop",
                 "designSystem": {"name": "x", "linked": False}},
        "tokens": {"danger": {"$value": "#dc2626", "$type": "color"}},
        "components": [
            {"id": "esc-util", "name": "EscUtil", "renderFn": "renderCmpEscUtil",
             "scope": "local", "level": "atom", "properties": [], "render": BODY_REGEX},
            {"id": "closer-atom", "name": "CloserAtom", "renderFn": "renderCmpCloserAtom",
             "scope": "local", "level": "atom", "properties": [], "render": BODY_CLOSER},
        ],
        "screens": [],
        "staleness": {}, "flow": {"populated": False}, "erd": {"populated": False},
    }


_CLOSE = re.compile(r"</script", re.IGNORECASE)
_SCRIPT_BLOCKS = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)


def _node_check(js_text):
    """Return (ok, detail). ok=None when node is unavailable."""
    node = shutil.which("node")
    if not node:
        return None, "node not on PATH"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js_text)
        path = f.name
    try:
        r = subprocess.run([node, "--check", path], capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stderr or r.stdout).strip().splitlines()[-1:] or ["ok"]
    finally:
        os.unlink(path)


def main():
    render = _load_render()
    reg = registry()

    print("1 · unit probe on _escape_body")
    kept = render._escape_body("var re = /</g; var s = '</div>';")
    check(kept == "var re = /</g; var s = '</div>';", "regex literal /</g and inert '</div>' left untouched: %r" % kept)
    check(render._escape_body("</script>") == "<\\/script>", "literal </script> escaped to <\\/script>")
    check(render._escape_body("x</SCRIPT >y") == "x<\\/SCRIPT >y", "escape is case-insensitive (</SCRIPT)")
    check(render._escape_body("</scripting>") == "</scripting>", "word boundary: </scripting> is not a closer")

    targets = []
    with open(os.path.join(TPL, "prototype.html"), encoding="utf-8") as f:
        shell = f.read()
    html, missing = render.build_html(reg, shell)
    targets.append(("prototype", shell, html, missing))
    ds_shell_p, runtime_p = os.path.join(TPL, "design-system.html"), os.path.join(TPL, "runtime.js")
    if os.path.isfile(ds_shell_p) and os.path.isfile(runtime_p):
        with open(ds_shell_p, encoding="utf-8") as f:
            ds_shell = f.read()
        with open(runtime_p, encoding="utf-8") as f:
            runtime_js = f.read()
        ds_html, ds_missing = render.build_ds(reg, ds_shell, runtime_js)
        targets.append(("design-system", ds_shell, ds_html, ds_missing))
    else:
        print("  (design-system shell not present — prototype target only)")

    for name, shell_txt, out, miss in targets:
        print("\n2 · %s target — bodies survive the render" % name)
        check(miss == [], "no missing render fns (%r)" % miss)
        check('window["renderCmpEscUtil"]' in out, "esc-util emitted")
        check("/</g" in out, "regex literal /</g present in the emitted page")
        check("/<\\/g" not in out, "mangled /<\\/g ABSENT from the emitted page")

        print("3 · %s target — the page-killer is neutralised" % name)
        check("<\\/script>" in out and "<\\/SCRIPT>" in out, "literal </script> and </SCRIPT> strings escaped")
        n_shell, n_out = len(_CLOSE.findall(shell_txt)), len(_CLOSE.findall(out))
        check(n_out == n_shell, "exactly as many </script closers as the shell (%d == %d) — no premature termination" % (n_out, n_shell))

        print("4 · %s target — the emitted script parses as JavaScript" % name)
        block = next((b for b in _SCRIPT_BLOCKS.findall(out) if 'renderCmpEscUtil' in b), None)
        check(block is not None, "found the inline <script> block that carries the bodies")
        if block is not None:
            ok, detail = _node_check(block)
            if ok is None:
                print("  – SKIPPED (%s)" % detail)
            else:
                check(ok, "node --check passes on the emitted block (%s)" % "; ".join(detail))

    print("\n5 · negative control — the OLD blanket escape must be detectable")
    blanket = BODY_REGEX.replace("</", "<\\/")
    check("/<\\/g" in blanket, "blanket escape does mangle /</g (so the assertions above are meaningful)")
    ok, detail = _node_check(blanket)
    if ok is None:
        print("  – SKIPPED (%s)" % detail)
    else:
        check(ok is False, "node --check FAILS on the blanket-escaped body (%s)" % "; ".join(detail))

    print()
    if fails:
        print("✗ %d render-escape check(s) failed" % len(fails))
        sys.exit(1)
    print("✓ render escape clean — narrow </script-only escape holds on every target")


if __name__ == "__main__":
    main()
