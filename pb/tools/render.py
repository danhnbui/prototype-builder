#!/usr/bin/env python3
"""
pb-render — the deterministic batched render (token lever #2).

Turns a project's registry.json + the shell prototype.html into a populated
prototype.html. This is a pure, deterministic codegen step: /pb:build --render and
the hand-off / validate commands invoke it via Bash, so a render costs ~0 MODEL
tokens. The model NEVER hand-writes the HTML (that is the ~2-3x-worse anti-pattern
the G0.5 spike proved catastrophic).

What it does:
  1. Emits each component/screen render function from its `render` body string in the
     registry (window["renderCmpX"] = function(props){ <render> };). The render bodies
     are DATA in the registry — editing one is a registry edit, then --render regenerates.
  2. Inlines the registry (minus the bulky `render` strings) into the shell's PB_REGISTRY
     placeholder; the shell's adapter maps it onto PB_DATA at load.

Usage:  python3 render.py <registry.json> <shell.html> <out.html>
"""
import json, sys, re, copy, os
from datetime import datetime, timezone


class RenderError(Exception):
    """A render precondition failed (e.g. the shell is missing a placeholder).

    Raised by build_html so callers — the CLI and the preview dev server (serve.py) —
    can handle it: the CLI exits, the dev server shows a recoverable error page.
    """


def load_bodies(reg, base_dir):
    """Resolve `renderSrc` file references into in-memory `render` strings.

    v1.4 (schema 4) moves render bodies out of the registry into real `.js` files
    (render/components/<id>.js, render/screens/<id>.js) referenced by `renderSrc`.
    This reader keeps build_html PURE (no file I/O there): callers resolve bodies here
    first, then hand the resulting registry — with `render` strings populated — to
    build_html. Precedence: renderSrc > legacy `render` (renderSrc overwrites it).

    A `renderSrc` pointing at a missing file raises RenderError (NS6 — never silently
    an empty function). Returns a NEW dict; the input is not mutated.
    """
    reg = copy.deepcopy(reg)
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            src = item.get("renderSrc")
            if not src:
                continue
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    item["render"] = f.read()
            except FileNotFoundError:
                raise RenderError(
                    "renderSrc not found for %s %r: %s" % (kind[:-1], item.get("id"), src))
    return reg


def _escape_body(body):
    """Escape `</` -> `<\\/` inside an emitted render body.

    A render body is JS that builds HTML in string literals (return '<div></div>';).
    Inside a <script>, only the literal `</script` ends the element — but `</` -> `<\\/`
    is semantically identical inside a JS string literal (\\/ === /) and uniformly kills
    the page-killer for ALL close tags. check.py's R-SCRIPT still flags a literal
    `</script` so authors are steered away; this is the belt to that suspenders.
    """
    return body.replace("</", "<\\/")


def _version_from(path):
    """Read a plugin.json's `version`. Returns the string, or 'unknown' for a
    missing / unreadable / non-JSON / version-less file. Never raises — a broken
    plugin.json must not take down a render (acceptance: stamp 'unknown')."""
    try:
        with open(path, encoding="utf-8") as f:
            v = json.load(f).get("version")
        return v if isinstance(v, str) and v.strip() else "unknown"
    except Exception:
        return "unknown"


def plugin_version():
    """The installed pb plugin SemVer, read from pb/.claude-plugin/plugin.json
    relative to this file (the self-locating trick migrate_runner.py uses)."""
    here = os.path.dirname(os.path.abspath(__file__))
    return _version_from(os.path.join(here, "..", ".claude-plugin", "plugin.json"))


def stamp(html, version):
    """Insert a `<!-- pb-shell vX · rendered <ISO-8601 Z> -->` comment right after the
    DOCTYPE so /pb:check-drift can detect a stale render. Kept OUT of build_html so the
    pure render stays deterministic (this adds a timestamp)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    comment = "<!-- pb-shell v%s · rendered %s -->" % (version, ts)
    html = re.sub(r"<!-- pb-shell v[^>]*-->\n?", "", html, count=1)  # idempotent: drop any prior stamp
    marker = "<!DOCTYPE html>"
    if marker in html:
        return html.replace(marker, marker + "\n" + comment, 1)
    return comment + "\n" + html


def build_html(reg, shell, version="unknown"):
    """Render a registry dict + shell HTML string into the populated prototype HTML.

    Pure: no file I/O, no globals. This is the single source of render truth — the
    CLI (render_file) and the preview dev server (serve.py) both go through here, so
    a live preview is byte-identical to what `/pb:build --render` writes to disk.

    Returns (html, missing) where `missing` lists renderFn names that had no `render`
    body (rendered as empty). Raises RenderError if the shell lacks an anchor.
    """
    # 1) generated render-fn bodies (from components[].render / screens[].render)
    parts = []
    missing = []
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            fn = item.get("renderFn")
            if not fn:
                continue
            if "render" in item and item["render"]:
                parts.append('    window[%s] = function(props){\n%s\n    };' % (json.dumps(fn), _escape_body(item["render"])))
            else:
                missing.append(fn)
    bodies = ""
    if parts:
        bodies = ("\n\n    /* ===== generated render bodies — from registry; do not hand-edit, "
                  "edit the `render` field in registry.json and re-run /pb:build --render ===== */\n"
                  + "\n".join(parts) + "\n")

    # 2) inline the registry (without the bulky render strings) into PB_REGISTRY
    reg_inline = copy.deepcopy(reg)
    for kind in ("components", "screens"):
        for item in reg_inline.get(kind, []):
            item.pop("render", None)
    # JSON is valid JS, but a literal `</` in a value could close the <script> tag — escape it to
    # `<\/` (identical string in JS, safe in HTML). The re.sub lambda returns its value literally,
    # so no other backslash handling is needed (doubling backslashes here corrupts JSON escapes).
    inlined = json.dumps(reg_inline, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    if "/*__PB_REGISTRY_START__*/" not in shell:
        raise RenderError("shell is missing the PB_REGISTRY placeholder — is this a v1.1.1 prototype.html?")
    shell = re.sub(r"/\*__PB_REGISTRY_START__\*/.*?/\*__PB_REGISTRY_END__\*/",
                   lambda m: "/*__PB_REGISTRY_START__*/" + inlined + "/*__PB_REGISTRY_END__*/",
                   shell, count=1, flags=re.S)

    anchor = "    const PB_DATA = adaptRegistryToPBData(PB_REGISTRY);"
    if anchor not in shell:
        raise RenderError("shell is missing the PB_DATA adapter anchor.")
    shell = shell.replace(anchor, anchor + bodies, 1)

    # Fill the shell's version placeholder (no-op on a shell that lacks it — never blocks).
    shell = shell.replace("{{PB_SHELL_VERSION}}", version)
    return shell, missing


def render_file(reg_path, shell_path, out_path):
    """Read registry + shell from disk, render, stamp, and write out_path.
    Returns (reg, html, missing). `html` is the stamped, on-disk form."""
    reg = json.load(open(reg_path, encoding="utf-8"))
    shell = open(shell_path, encoding="utf-8").read()
    reg = load_bodies(reg, os.path.dirname(os.path.abspath(reg_path)))
    version = plugin_version()
    html, missing = build_html(reg, shell, version)
    html = stamp(html, version)
    open(out_path, "w", encoding="utf-8").write(html)
    return reg, html, missing


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: render.py <registry.json> <shell.html> <out.html>")
    try:
        reg, html, missing = render_file(sys.argv[1], sys.argv[2], sys.argv[3])
    except json.JSONDecodeError as e:
        # Fail closed with a one-line, human-readable message — never a traceback.
        print("error: %s is not valid JSON (line %d, column %d): %s"
              % (sys.argv[1], e.lineno, e.colno, e.msg), file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print("error: file not found: %s" % (e.filename or e), file=sys.stderr)
        sys.exit(2)
    except RenderError as e:
        sys.exit("error: %s" % e)
    name = (reg.get("meta") or {}).get("name") or "(unnamed)"
    msg = "rendered %s: %d components, %d screens, %d tokens -> %s (%d bytes)" % (
        name, len(reg.get("components", [])), len(reg.get("screens", [])),
        len(reg.get("tokens", {})), sys.argv[3], len(html))
    if missing:
        msg += "\n  note: %d render fn(s) had no `render` body and will be empty: %s" % (len(missing), ", ".join(missing))
    print(msg)


if __name__ == "__main__":
    main()
