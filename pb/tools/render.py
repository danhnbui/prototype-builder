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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registry_to_figma as _r2f  # noqa: E402  (sibling; per-component node JSON for the DS site)


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


def load_specs(reg, base_dir):
    """Resolve `specSrc` file references into in-memory anatomy/spec/usage/uiLogic fields.

    Schema 10 moves those four handoff fields out of the registry into
    spec/{components,screens}/<id>.json sidecars referenced by `specSrc` (mirrors renderSrc /
    load_bodies). The spec drawer in prototype.html reads them client-side off the inlined
    PB_REGISTRY, so they must be re-inlined here BEFORE build_html serializes the registry.
    Sidecar fields win over any stray inline copy.

    A `specSrc` pointing at a missing file raises RenderError (NS6 — never silently drop the
    handoff docs). Returns a NEW dict; the input is not mutated.
    """
    reg = copy.deepcopy(reg)
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            src = item.get("specSrc")
            if not src:
                continue
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        item[k] = v
            except FileNotFoundError:
                raise RenderError(
                    "specSrc not found for %s %r: %s" % (kind[:-1], item.get("id"), src))
    return reg


def _escape_body(body):
    """Escape `</` -> `<\\/` inside an emitted render body.

    A render body is JS that builds HTML in string literals (return '<div></div>';).
    Inside a <script>, only the literal `</script` ends the element — but `</` -> `<\\/`
    is semantically identical inside a JS string literal (\\/ === /) and uniformly kills
    the page-killer for ALL close tags. lint_registry.py's R-SCRIPT still flags a literal
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


def _render_fn_bodies(reg):
    """Emit `window[renderFn] = function(props){…}` for every component/screen render body.
    Shared by build_html (prototype) and build_ds_html (design system) so both sites get the
    SAME callable render functions. Returns (bodies_str, missing_fn_names)."""
    parts, missing = [], []
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            fn = item.get("renderFn")
            if not fn:
                continue
            if "render" in item and item["render"]:
                escaped = _escape_body(item["render"])
                if escaped.lstrip().startswith('function '):
                    parts.append('%s\n    window[%s] = %s;' % (escaped, json.dumps(fn), fn))
                else:
                    parts.append('    window[%s] = function(props){\n%s\n    };' % (json.dumps(fn), escaped))
            else:
                missing.append(fn)
    bodies = ""
    if parts:
        bodies = ("\n\n    /* ===== generated render bodies — from registry; do not hand-edit, "
                  "edit the `render` field in registry.json and re-run /pb:build --render ===== */\n"
                  + "\n".join(parts) + "\n")
    return bodies, missing


def _strip_render(reg):
    """A deep copy of reg with the bulky `render` strings removed (they're emitted separately)."""
    reg_inline = copy.deepcopy(reg)
    for kind in ("components", "screens"):
        for item in reg_inline.get(kind, []):
            item.pop("render", None)
    return reg_inline


def build_html(reg, shell, version="unknown"):
    """Render a registry dict + shell HTML string into the populated prototype HTML.

    Pure: no file I/O, no globals. This is the single source of render truth — the
    CLI (render_file) and the preview dev server (serve.py) both go through here, so
    the live preview uses the same render logic as `/pb:build --render`. (render_file
    adds a stamp() drift-comment to the on-disk artifact only, so the disk file differs
    from the in-memory preview by exactly that one comment.)

    Returns (html, missing) where `missing` lists renderFn names that had no `render`
    body (rendered as empty). Raises RenderError if the shell lacks an anchor.
    """
    # 1) generated render-fn bodies (from components[].render / screens[].render)
    bodies, missing = _render_fn_bodies(reg)

    # 2) inline the registry (without the bulky render strings) into PB_REGISTRY
    reg_inline = _strip_render(reg)
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
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    reg = load_bodies(reg, base_dir)
    reg = load_specs(reg, base_dir)  # resolve specSrc sidecars (schema 10)
    version = plugin_version()
    html, missing = build_html(reg, shell, version)
    html = stamp(html, version)
    open(out_path, "w", encoding="utf-8").write(html)
    return reg, html, missing


# ── design-system site (the second render target) ───────────────────────────────────────

def _default_props(comp):
    """A component's default variant props (from properties[].default) — for the push node."""
    p = {}
    for pr in comp.get("properties", []) or []:
        if isinstance(pr, dict) and pr.get("id") and pr.get("default") is not None:
            p[pr["id"]] = pr["default"]
    return p


def _find_catalog(base_dir, reg):
    """Locate a Scan DS `ds-catalog.json` (publish keys/variables) for the push snippets, or None."""
    import glob as _glob
    name = (reg.get("meta") or {}).get("designSystem", {}).get("name")
    cands = ([os.path.join(base_dir, "design-system", name, "ds-catalog.json")] if name else []) \
        + _glob.glob(os.path.join(base_dir, "design-system", "*", "ds-catalog.json"))
    for p in cands:
        if os.path.isfile(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
    return None


def build_ds_html(reg, ds_shell, runtime_js, nodes_by_id, version="unknown"):
    """Render the design-system site (component workbench) from the registry. Pure. Injects the
    shared runtime, the emitted window[renderCmp*], the inlined registry, and per-component node
    JSON (PB_NODES). Returns (html, missing). Raises RenderError on a missing marker."""
    bodies, missing = _render_fn_bodies(reg)
    inlined = json.dumps(_strip_render(reg), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    nodes = json.dumps(nodes_by_id, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    for marker in ("/*__PB_REGISTRY_START__*/", "/*__PB_NODES_START__*/", "/*__PB_RUNTIME__*/", "/*__PB_RENDER_FNS__*/"):
        if marker not in ds_shell:
            raise RenderError("design-system shell is missing the %s marker" % marker)
    html = re.sub(r"/\*__PB_REGISTRY_START__\*/.*?/\*__PB_REGISTRY_END__\*/",
                  lambda m: "/*__PB_REGISTRY_START__*/" + inlined + "/*__PB_REGISTRY_END__*/",
                  ds_shell, count=1, flags=re.S)
    html = re.sub(r"/\*__PB_NODES_START__\*/.*?/\*__PB_NODES_END__\*/",
                  lambda m: "/*__PB_NODES_START__*/" + nodes + "/*__PB_NODES_END__*/",
                  html, count=1, flags=re.S)
    html = html.replace("/*__PB_RUNTIME__*/", runtime_js, 1)
    html = html.replace("/*__PB_RENDER_FNS__*/", bodies, 1)
    html = html.replace("{{PB_SHELL_VERSION}}", version)
    return html, missing


def build_ds(reg, ds_shell, runtime_js, catalog=None, version="unknown"):
    """Pure: a loaded registry (bodies resolved) + DS shell + runtime.js → the DS-site HTML.
    Pre-computes each component's push node JSON. The single DS render truth — both the CLI
    (render_ds_file) and the preview server (serve.py) go through here. Returns (html, missing)."""
    nodes_by_id = {}
    for c in reg.get("components", []) or []:
        cid = c.get("id")
        if not cid:
            continue
        try:
            nodes_by_id[cid] = _r2f.build_component_nodes(reg, cid, catalog=catalog, props=_default_props(c))
        except Exception as e:  # a bad component must not take down the whole DS render
            nodes_by_id[cid] = {"error": str(e), "roots": [], "gaps": []}
    return build_ds_html(reg, ds_shell, runtime_js, nodes_by_id, version)


def render_ds_file(reg_path, ds_shell_path, runtime_path, out_path, catalog_path=None):
    """Read registry + design-system shell + runtime.js, render + stamp + write the DS site.
    Returns (reg, html, missing)."""
    reg = json.load(open(reg_path, encoding="utf-8"))
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    reg = load_bodies(reg, base_dir)
    reg = load_specs(reg, base_dir)
    ds_shell = open(ds_shell_path, encoding="utf-8").read()
    runtime_js = open(runtime_path, encoding="utf-8").read()
    catalog = (json.load(open(catalog_path, encoding="utf-8"))
               if (catalog_path and os.path.isfile(catalog_path)) else _find_catalog(base_dir, reg))
    version = plugin_version()
    html, missing = build_ds(reg, ds_shell, runtime_js, catalog, version)
    html = stamp(html, version)
    open(out_path, "w", encoding="utf-8").write(html)
    return reg, html, missing


def main():
    args = sys.argv[1:]
    # design-system site: render.py --ds <registry> <design-system.html> <runtime.js> <out> [ds-catalog.json]
    if args and args[0] == "--ds":
        rest = args[1:]
        if len(rest) not in (4, 5):
            sys.exit("usage: render.py --ds <registry.json> <design-system.html> <runtime.js> <out.html> [ds-catalog.json]")
        try:
            reg, html, missing = render_ds_file(rest[0], rest[1], rest[2], rest[3], rest[4] if len(rest) == 5 else None)
        except json.JSONDecodeError as e:
            sys.exit("error: %s is not valid JSON (line %d, column %d): %s" % (rest[0], e.lineno, e.colno, e.msg))
        except FileNotFoundError as e:
            sys.exit("error: file not found: %s" % (e.filename or e))
        except RenderError as e:
            sys.exit("error: %s" % e)
        name = (reg.get("meta") or {}).get("name") or "(unnamed)"
        print("rendered design system for %s: %d components, %d tokens -> %s (%d bytes)" % (
            name, len(reg.get("components", [])), len(reg.get("tokens", {})), rest[3], len(html)))
        return

    if len(args) != 3:
        sys.exit("usage: render.py <registry.json> <shell.html> <out.html>  |  "
                 "render.py --ds <registry.json> <design-system.html> <runtime.js> <out.html> [ds-catalog.json]")
    try:
        reg, html, missing = render_file(args[0], args[1], args[2])
    except json.JSONDecodeError as e:
        print("error: %s is not valid JSON (line %d, column %d): %s"
              % (args[0], e.lineno, e.colno, e.msg), file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError as e:
        print("error: file not found: %s" % (e.filename or e), file=sys.stderr)
        sys.exit(2)
    except RenderError as e:
        sys.exit("error: %s" % e)
    name = (reg.get("meta") or {}).get("name") or "(unnamed)"
    msg = "rendered %s: %d components, %d screens, %d tokens -> %s (%d bytes)" % (
        name, len(reg.get("components", [])), len(reg.get("screens", [])),
        len(reg.get("tokens", {})), args[2], len(html))
    if missing:
        msg += "\n  note: %d render fn(s) had no `render` body and will be empty: %s" % (len(missing), ", ".join(missing))
    print(msg)


if __name__ == "__main__":
    main()
