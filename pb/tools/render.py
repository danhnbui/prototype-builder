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
import json, sys, re, copy


class RenderError(Exception):
    """A render precondition failed (e.g. the shell is missing a placeholder).

    Raised by build_html so callers — the CLI and the preview dev server (serve.py) —
    can handle it: the CLI exits, the dev server shows a recoverable error page.
    """


def build_html(reg, shell):
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
                parts.append('    window[%s] = function(props){\n%s\n    };' % (json.dumps(fn), item["render"]))
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
    return shell, missing


def render_file(reg_path, shell_path, out_path):
    """Read registry + shell from disk, render, and write out_path. Returns (reg, html, missing)."""
    reg = json.load(open(reg_path, encoding="utf-8"))
    shell = open(shell_path, encoding="utf-8").read()
    html, missing = build_html(reg, shell)
    open(out_path, "w", encoding="utf-8").write(html)
    return reg, html, missing


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: render.py <registry.json> <shell.html> <out.html>")
    try:
        reg, html, missing = render_file(sys.argv[1], sys.argv[2], sys.argv[3])
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
