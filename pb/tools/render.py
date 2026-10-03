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
import json, sys, re, copy, os, glob
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registry_to_figma as _r2f  # noqa: E402  (sibling; per-component node JSON for the DS site)


class RenderError(Exception):
    """A render precondition failed (e.g. the shell is missing a placeholder).

    Raised by build_html so callers — the CLI and the preview dev server (serve.py) —
    can handle it: the CLI exits, the dev server shows a recoverable error page.
    """


def load_bodies(reg, base_dir, overrides=None):
    """Resolve `renderSrc` file references into in-memory `render` strings.

    v1.4 (schema 4) moves render bodies out of the registry into real `.js` files
    (render/components/<id>.js, render/screens/<id>.js) referenced by `renderSrc`.
    This reader keeps build_html PURE (no file I/O there): callers resolve bodies here
    first, then hand the resulting registry — with `render` strings populated — to
    build_html. Precedence: renderSrc > legacy `render` (renderSrc overwrites it).

    A `renderSrc` pointing at a missing file raises RenderError (NS6 — never silently
    an empty function). Returns a NEW dict; the input is not mutated.

    `overrides` ({renderSrc: other path, both relative to base_dir}) reads a body from somewhere
    else WITHOUT touching the registry: `/pb:explore` renders each candidate this way, against the
    real registry and the real base_dir. It used to render a temporary registry copy instead, and
    because every relative path resolves against the registry's own folder, a copy written anywhere
    else failed on its first renderSrc — and the model fell back to writing the HTML by hand.
    """
    reg = copy.deepcopy(reg)
    swap = {os.path.normpath(k): v for k, v in (overrides or {}).items()}
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            src = item.get("renderSrc")
            if not src:
                continue
            src = swap.get(os.path.normpath(src), src)
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    item["render"] = f.read()
            except FileNotFoundError:
                raise RenderError(
                    "renderSrc not found for %s %r: %s" % (kind[:-1], item.get("id"), src))
        # The optional stylesheet beside a body (render/styles/<id>.css) — where a component or
        # screen says how it changes across device sizes. Inline style="" cannot hold a container
        # query, so without this a body had no way to be responsive at all.
        for item in reg.get(kind, []):
            src = item.get("styleSrc")
            if not src:
                continue
            src = swap.get(os.path.normpath(src), src)
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    item["style"] = f.read()
            except FileNotFoundError:
                raise RenderError(
                    "styleSrc not found for %s %r: %s" % (kind[:-1], item.get("id"), src))
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


_AUTHORED_HALF = re.compile(r'"(?:writes|affordances)"\s*:\s*\[\s*[^\]\s]')


def load_contracts(reg, base_dir):
    """Read the schema-11 logic contracts — `logic/{components,screens}/<id>.json` via `logicSrc`.

    Mirrors load_specs, with one deliberate difference: the contract is NOT re-inlined into
    the registry. It is view + handoff data for the Logic tab, which reads it off PB_LOGIC,
    and the registry is the thing schema 10 just spent a version getting small. So this
    returns a separate map, `"<kind>/<id>" -> contract`, which load_logic hangs off the graph.

    The contract has two halves (D-28). Derived and rewritten on every
    `logic_extract.py --contracts` run: `seam`, `handlers`, `disclosure`. Hand-authored and
    never touched by a tool: `writes[]` and `affordances[].why` — the one thing static
    derivation cannot see, because the mutations happen inside store helpers.

    Two of the sidecar's keys are carried into the graph, and only those two: `writes` and
    `affordances`. The derived half is a reprojection of `handlers`/`items`, which the graph
    already has. `notes[]` is copied prose whose original is still in `uiLogic`, which
    load_specs re-inlines into PB_REGISTRY — carrying it here would ship the same paragraphs a
    third time. The full sidecar stays on disk, which is where a hand-off reader wants it.

    A missing sidecar is reported and skipped, never raised: load_logic's whole contract is
    that a logic graph is not worth failing a render over. Returns {} when nothing is declared.
    """
    authored = ("writes", "affordances")
    out = {}
    for kind in ("components", "screens"):
        for item in reg.get(kind, []) if isinstance(reg, dict) else []:
            src = item.get("logicSrc")
            if not src:
                continue
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    raw = f.read()
            except OSError as exc:                                  # noqa: PERF203
                print("pb-render: logic contract skipped for %s %r (%s)"
                      % (kind[:-1], item.get("id"), exc))
                continue
            # Most contracts are derived-only: nobody has authored writes or affordances yet.
            # Parsing all of them to discover that costs ~100 ms on a 143-item project, on every
            # render and every preview reload, so the raw text is tested first.
            if not _AUTHORED_HALF.search(raw):
                continue
            try:
                data = json.loads(raw)
            except ValueError as exc:
                print("pb-render: logic contract skipped for %s %r (%s)"
                      % (kind[:-1], item.get("id"), exc))
                continue
            if not isinstance(data, dict):
                continue
            half = {k: data[k] for k in authored if data.get(k)}
            if half:
                out["%s/%s" % (kind, item.get("id"))] = half
    return out


_LOGIC_CACHE = {"key": None, "graph": None}


def _logic_key(base_dir):
    """A fingerprint of everything logic_extract reads: the registry and every render body —
    AND the extractor itself.

    The extractor's own mtime is load-bearing, not belt-and-braces. Without it the key covers
    only the DATA, so teaching logic_extract.py to derive something new leaves a long-running
    `/pb:preview` serving the old graph forever: the project files never changed, so the cache
    never missed, so the new field never appeared. Found exactly that way.

    Returns None if the tree cannot be stat'd, which disables the cache rather than risking a
    stale hit. Stat'ing ~150 files costs under a millisecond against the 367 the parse costs.
    """
    try:
        parts = []
        paths = [os.path.join(base_dir, "registry.json")] + sorted(
            glob.glob(os.path.join(glob.escape(base_dir), "render", "**", "*.js"), recursive=True))
        paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logic_extract.py"))
        for path in paths:
            st = os.stat(path)
            parts.append((path, st.st_mtime_ns, st.st_size))
        return tuple(parts)
    except OSError:
        return None


def load_logic(base_dir, reg=None):
    """Derive the logic graph for the project at `base_dir`, or None.

    Mirrors load_specs in spirit but derives rather than reads: logic_extract.py scans the
    render bodies and the shell and returns the graph the UX Design tab's Information
    Architecture and Logic views draw from. Authored input is only what the registry
    already carries (`ia`, and any declared rules); everything else — the handler graph,
    the store slices, the navigation layers, the overlays — is computed here so it can
    never drift from the code it describes.

    FAILS OPEN, ALWAYS. This is a view enhancement, not a render input: a project with no
    render bodies, a missing extractor, or a malformed body must still render its four
    tabs. The two views that read it degrade to an honest empty state on None. A logic
    graph is never worth failing a render over.
    """
    try:
        import logic_extract  # sibling; sys.path already carries this directory
    except ImportError:
        return None
    # Derivation is the expensive half of a render — 367 of 405 ms on a 143-item project,
    # because it parses every render body. It depends on exactly one thing: those files. The
    # preview server re-renders on every registry save, so without a cache the common edit
    # (a prop, a label, a token) pays for a re-parse of code that did not change. The key
    # covers every input the extractor reads, so a stale hit is not possible.
    key = _logic_key(base_dir)
    if key is not None and _LOGIC_CACHE.get("key") == key:
        graph = copy.deepcopy(_LOGIC_CACHE["graph"])
    else:
        try:
            graph = logic_extract.extract(base_dir)
        except Exception as exc:                                    # noqa: BLE001
            print("pb-render: logic graph skipped (%s: %s)" % (type(exc).__name__, exc))
            return None
        if key is not None:
            _LOGIC_CACHE["key"], _LOGIC_CACHE["graph"] = key, copy.deepcopy(graph)
    if reg is not None:
        contracts = load_contracts(reg, base_dir)
        if contracts:
            graph["contracts"] = contracts
        # The authored half rides along beside the derived half, so the shell reads one object.
        ia = reg.get("ia")
        if isinstance(ia, dict):
            graph["ia"] = ia
        rules = (ia or {}).get("rules") if isinstance(ia, dict) else None
        if isinstance(reg.get("rules"), list):
            rules = reg["rules"]
        if rules:
            graph["rules"] = rules
    return graph


_SCRIPT_CLOSE_IN_BODY = re.compile(r"</(?=script\b)", re.IGNORECASE)


def _escape_body(body):
    """Escape the literal `</script` -> `<\\/script` inside an emitted render body — and
    ONLY that.

    A render body is JS that builds HTML in string literals (return '<div></div>';).
    Inside a <script>, the one sequence that can end the element is the literal `</script`
    (HTML spec; `</div>` etc. are inert), so that is the page-killer to neutralise.
    `<\\/script` is identical inside a JS string literal (\\/ === /).

    Why NOT the blanket `</` -> `<\\/` this used to do (v1.5.1–v1.11.0): a body is JS, not
    just strings, and `</` also appears in the regex literal /</g — the standard HTML-escape
    idiom `.replace(/</g, '&lt;')`. Blanket-escaping it yields /<\\/g, an unterminated regex
    that kills the WHOLE inline script; a real project with 17 such bodies rendered blank on
    both routes (v1.11.1 P0). tests/render_escape.py guards this; lint_registry.py's
    R-SCRIPT still steers authors away from a literal `</script` (belt and suspenders).
    """
    return _SCRIPT_CLOSE_IN_BODY.sub(lambda m: "<\\/", body)


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
    DOCTYPE so /pb:test --drift can detect a stale render. Kept OUT of build_html so the
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


def load_product_css():
    """pb/template/product.css minus its file header — the project's responsive base (size-class
    utilities, the `pb-screen` containers). Missing file → "" so a stripped-down install renders."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "template", "product.css")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    if text.lstrip().startswith("/*"):
        end = text.find("*/")
        if end >= 0:
            text = text[end + 2:]
    return text.strip("\n")


def _product_css_js(reg):
    """One <style id="pb-product-css">: product.css, then every `styleSrc` sheet (components
    before screens, so a screen can override a component it places). Emitted as a script that
    writes the sheet, because it rides the render-body slot both shells already have — no new
    marker, and the preview server and /pb:explore overlays get it for free. Kept OUT of
    _render_fn_bodies: lint's --exec gate runs those bodies in node, where there is no document."""
    sheets = [load_product_css()]
    for kind in ("components", "screens"):
        for item in reg.get(kind, []):
            if item.get("style"):
                sheets.append("/* %s %s */\n%s" % (kind[:-1], item.get("id"), item["style"]))
    css = "\n".join(s for s in sheets if s)
    if not css:
        return ""
    return ("\n    (function(){var s=document.getElementById('pb-product-css');"
            "if(!s){s=document.createElement('style');s.id='pb-product-css';document.head.appendChild(s);}"
            "s.textContent=%s;})();\n" % json.dumps(css, ensure_ascii=False).replace("</", "<\\/"))


_RUNTIME_DEPS_MARK = "<!--__PB_RUNTIME_DEPS__-->"


def load_runtime(reg, base_dir):
    """Resolve `registry.runtime[]` — the project's own module layer (schema 11).

    Before this existed, a project that needed shared, non-render JS had exactly one way to
    get it into the single script scope: declare a COMPONENT whose render body is
    `return ''` and hang the helpers off it. On the project this was measured against, five
    such fake components carried 3,054 lines and 136 top-level names that render nothing, and
    a third-party parser (SheetJS) had to be hand-injected by editing the shell.

    Each entry declares exactly one source and says why it is there:
      {"id": "app-store", "src": "runtime/app-store.js", "why": "…"}   inlined, in order,
                                                                       BEFORE every render body
      {"id": "sheetjs",   "url": "https://…/xlsx.js",    "why": "…"}   a <script src> in the head

    Order is the declaration order — a module may depend on one declared above it.
    Returns (inline_js, dep_tags, missing). A `src` that does not resolve is collected in
    `missing` rather than raised: the caller reports it the same way it reports a missing
    render body, and the rest of the prototype still renders.
    """
    parts, tags, missing = [], [], []
    for entry in (reg.get("runtime") or []) if isinstance(reg, dict) else []:
        if not isinstance(entry, dict):
            continue
        rid = entry.get("id") or entry.get("src") or entry.get("url") or "?"
        url = entry.get("url")
        if url:
            tags.append('  <script src="%s"></script>' % html_escape_attr(url))
            continue
        src = entry.get("src")
        if not src:
            continue
        path = os.path.normpath(os.path.join(base_dir, src))
        try:
            with open(path, encoding="utf-8") as f:
                body = f.read()
        except OSError:
            missing.append("%s (%s)" % (rid, src))
            continue
        parts.append("    /* --- runtime module: %s (%s) --- */\n%s" % (rid, src, _escape_body(body)))
    inline = ""
    if parts:
        inline = ("\n\n    /* ===== registry.runtime[] — the project's own modules, inlined in "
                  "declaration order BEFORE the render bodies; edit the real files, not this ===== */\n"
                  + "\n".join(parts) + "\n")
    return inline, tags, missing


def html_escape_attr(value):
    """Minimal attribute escape for a declared runtime URL (deterministic, no dependencies)."""
    return (str(value).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _strip_render(reg):
    """A deep copy of reg with the bulky `render` / `style` strings removed (emitted separately)."""
    reg_inline = copy.deepcopy(reg)
    for kind in ("components", "screens"):
        for item in reg_inline.get(kind, []):
            item.pop("render", None)
            item.pop("style", None)
    return reg_inline


# Fields the derived graph carries for TOOLS but the shell never reads. logic_check --freeze
# compares bodyHash; localCalls and shellVerbs feed the undefined-helper and disclosure checks.
# None of the three is touched by prototype.html — and every byte here is inlined into the
# prototype AND into every hand-off of it. Measured on a 143-item project: 38 KB per render.
_LOGIC_SHELL_DROP = {"handlers": ("bodyHash", "localCalls"), "items": ("shellVerbs",)}


def _logic_for_shell(logic):
    """The graph as the shell needs it — the full one minus the keys only tools read."""
    out = dict(logic)
    for key, drop in _LOGIC_SHELL_DROP.items():
        rows = logic.get(key)
        if isinstance(rows, list):
            out[key] = [{k: v for k, v in row.items() if k not in drop}
                        if isinstance(row, dict) else row for row in rows]
    return out


def default_runtime_path():
    """pb/template/runtime.js, resolved from this file so a caller never has to pass it."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "template", "runtime.js")


def load_shared_runtime(path=None):
    """Read runtime.js. Returns "" when it cannot be read, which leaves the marker in place
    rather than failing a render over a comment block."""
    try:
        with open(path or default_runtime_path(), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def shared_runtime(text):
    """runtime.js minus its file header — the header addresses whoever edits runtime.js, and
    shipping it inside a multi-megabyte artifact twice says nothing to the reader of that file."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and (lines[i].startswith("/*") or lines[i].startswith(" *")):
        i += 1
    return "\n".join(lines[i:]).rstrip("\n")


# The tool's own foundation (pb/template/chrome.css), injected into every shell at this marker —
# the same one-copy-on-disk mechanism runtime.js uses. A shell without the marker is an older one
# that carries its own styles: leave it alone (fail open, never block a render).
_CHROME_MARK = "/*__PB_CHROME__*/"


def load_chrome_css():
    """chrome.css minus its file header (the header addresses whoever edits chrome.css, and
    shipping it inside every rendered artifact says nothing to the reader of that file).
    Missing file → "" so a stripped-down install still renders."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "template", "chrome.css")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return ""
    if text.lstrip().startswith("/*"):
        end = text.find("*/")
        if end >= 0:
            text = text[end + 2:]
    return text.strip("\n")


def inject_chrome(shell):
    """Fill a shell's /*__PB_CHROME__*/ marker with the tool foundation. Pure; no marker → no-op."""
    if _CHROME_MARK not in shell:
        return shell
    return shell.replace(_CHROME_MARK, load_chrome_css(), 1)


def build_html(reg, shell, version="unknown", logic=None, runtime_js="",
               project_js="", project_deps=()):
    """Render a registry dict + shell HTML string into the populated prototype HTML.

    Pure: no file I/O, no globals. This is the single source of render truth — the
    CLI (render_file) and the preview dev server (serve.py) both go through here, so
    the live preview uses the same render logic as `/pb:build --render`. (render_file
    adds a stamp() drift-comment to the on-disk artifact only, so the disk file differs
    from the in-memory preview by exactly that one comment.)

    Returns (html, missing) where `missing` lists renderFn names that had no `render`
    body (rendered as empty). Raises RenderError if the shell lacks an anchor.
    """
    # 1) generated render-fn bodies (from components[].render / screens[].render), with the
    #    project's declared runtime modules ahead of them — a module a body calls at load time
    #    must already be defined, and this single insertion point is what guarantees the order.
    bodies, missing = _render_fn_bodies(reg)
    bodies = _product_css_js(reg) + (project_js or "") + bodies

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

    # The shared runtime. One copy on disk (pb/template/runtime.js), injected into BOTH shells —
    # it used to be pasted into prototype.html as well, 291 lines kept in step by a test. A shell
    # without the marker is an older one that still carries its own copy: leave it alone.
    if runtime_js and "/*__PB_RUNTIME__*/" in shell:
        shell = shell.replace("/*__PB_RUNTIME__*/", shared_runtime(runtime_js), 1)
    shell = inject_chrome(shell)

    anchor = "    const PB_DATA = adaptRegistryToPBData(PB_REGISTRY);"
    if anchor not in shell:
        raise RenderError("shell is missing the PB_DATA adapter anchor.")
    shell = shell.replace(anchor, anchor + bodies, 1)

    # Declared third-party dependencies (registry.runtime[] entries with a `url`). An empty
    # list leaves the marker in place — a shell with no marker simply carries no deps.
    if project_deps:
        shell = shell.replace(_RUNTIME_DEPS_MARK, "\n".join(project_deps), 1)

    # Fill the shell's version placeholder (no-op on a shell that lacks it — never blocks).
    shell = shell.replace("{{PB_SHELL_VERSION}}", version)

    # The derived logic graph. Absent (an older shell without the placeholder, or a project
    # with nothing to derive) is a no-op: the shell ships `null` there and the two views that
    # read it render an empty state.
    if logic and "/*__PB_LOGIC_START__*/" in shell:
        inlined_logic = json.dumps(_logic_for_shell(logic), ensure_ascii=False,
                                   separators=(",", ":")).replace("</", "<\\/")
        shell = re.sub(r"/\*__PB_LOGIC_START__\*/.*?/\*__PB_LOGIC_END__\*/",
                       lambda m: "/*__PB_LOGIC_START__*/" + inlined_logic + "/*__PB_LOGIC_END__*/",
                       shell, count=1, flags=re.S)
    return shell, missing


def render_file(reg_path, shell_path, out_path):
    """Read registry + shell from disk, render, stamp, and write out_path.
    Returns (reg, html, missing). `html` is the stamped, on-disk form."""
    reg = json.load(open(reg_path, encoding="utf-8"))
    shell = open(shell_path, encoding="utf-8").read()
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    reg = load_bodies(reg, base_dir)
    reg = load_specs(reg, base_dir)  # resolve specSrc sidecars (schema 10)
    logic = load_logic(base_dir, reg)  # derive the logic graph (fails open → None)
    rt_js, rt_deps, rt_missing = load_runtime(reg, base_dir)   # registry.runtime[] (schema 11)
    version = plugin_version()
    html, missing = build_html(reg, shell, version, logic=logic,
                               runtime_js=load_shared_runtime(),
                               project_js=rt_js, project_deps=rt_deps)
    missing += ["runtime module %s" % m for m in rt_missing]
    html = stamp(html, version)
    open(out_path, "w", encoding="utf-8").write(html)
    return reg, html, missing


# ── design-system site (the second render target) ───────────────────────────────────────

_COLLECTION_DEFAULT = re.compile(r"^\s*[\[{]")


def _coerce_default(value, declared_type):
    """A prop default, as DATA rather than as whatever the author happened to type.

    The design-system site builds each demo from these defaults, so a component whose body
    does `props.rows.map(...)` gets exactly what lands here. Measured on a real project, 11
    of 133 components could not render because they got the two-character STRING `'[]'`, and
    `'[]'.map` is not a function. The prototype never hit it: there a parent passes real
    props via pbUse, so the default never fires.

    Three steps, in order, each only firing when the one before it did not settle it:
      1. already a list/dict → pass through untouched.
      2. declared array/object, or a string that opens like a collection → try to parse it.
      3. parse failed but the declaration says collection → an EMPTY one, never the string.
         An empty table is a poor demo; a thrown exception is not a demo at all.

    A real project also defaults an array prop to unquoted-key pseudo-JSON
    (`[{name:'Đỗ Bảo'}]`), which no parser accepts — hence step 3 rather than step 2 alone.
    `lint_registry.py`'s R-PROPTYPE reports both shapes so they get fixed at the source;
    this keeps the site usable until they are.
    """
    if isinstance(value, (list, dict)):
        return value
    wants_collection = declared_type in ("array", "object")
    if isinstance(value, str) and (wants_collection or _COLLECTION_DEFAULT.match(value)):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            if wants_collection:
                return [] if declared_type == "array" else {}
            if value.lstrip().startswith("["):
                return []
            return {}
    return value


def _default_props(comp):
    """A component's default variant props (from properties[].default) — for the push node."""
    p = {}
    for pr in comp.get("properties", []) or []:
        if isinstance(pr, dict) and pr.get("id") and pr.get("default") is not None:
            p[pr["id"]] = _coerce_default(pr.get("default"), pr.get("type"))
    # A spec sidecar may carry `usage.example` — real sample data authored for the demo,
    # which beats any default. Sidecar wins; defaults only fill the gaps.
    usage = comp.get("usage")
    example = usage.get("example") if isinstance(usage, dict) else None
    if isinstance(example, dict):
        p.update(example)
    return p


def _find_catalog(base_dir, reg):
    """Locate a Scan DS `ds-catalog.json` (publish keys/variables) for the push snippets, or None."""
    import glob as _glob
    name = (reg.get("meta") or {}).get("designSystem", {}).get("name")
    cands = ([os.path.join(base_dir, "design-system", name, "ds-catalog.json")] if name else []) \
        + _glob.glob(os.path.join(_glob.escape(base_dir), "design-system", "*", "ds-catalog.json"))
    for p in cands:
        if os.path.isfile(p):
            try:
                return json.load(open(p, encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
    return None


_PBUSE_RE = re.compile(r"""pbUse\(\s*['"]([^'"]+)['"]""")
# A render body's leading comment, in the convention the bodies use: `/* <id> — <purpose>. props: …`
_PURPOSE_RE = re.compile(r"^\s*/\*+\s*([\w.-]+)\s+[\u2014\u2013]\s+(.+?)(?:\.\s|\.?\s*props:|\.?\s*\*/|\.?\n)")


def _ds_annotations(reg):
    """What the design-system site shows that the registry does not state outright, derived from
    the render bodies (which the inlined registry drops): for each component, the screens that
    render it — directly or through a parent that pbUse()s it — in registry order, and its
    one-line purpose from the body's leading comment when the component has no `description`.
    Pure and deterministic: id → {"usedIn": [...], "bodyPurpose": str?}."""
    comps = [c for c in reg.get("components", []) or [] if isinstance(c, dict) and c.get("id")]
    kids = {c["id"]: set(_PBUSE_RE.findall(c.get("render") or "")) for c in comps}

    def closure(start):
        seen, todo = set(), list(start)
        while todo:
            cid = todo.pop()
            if cid in seen:
                continue
            seen.add(cid)
            todo.extend(kids.get(cid, ()))
        return seen

    out = {c["id"]: {"usedIn": []} for c in comps}
    for s in reg.get("screens", []) or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        for cid in sorted(closure(_PBUSE_RE.findall(s.get("render") or ""))):
            if cid in out:
                out[cid]["usedIn"].append(s["id"])
    for c in comps:
        m = _PURPOSE_RE.match(c.get("render") or "")
        if m and m.group(1) == c["id"]:
            text = m.group(2).strip()
            out[c["id"]]["bodyPurpose"] = text[:1].upper() + text[1:] + ("" if text.endswith(".") else ".")
    return out


def _ds_styles(reg):
    """component id → the text of its `styleSrc` sheet, for the design-system site's Code view.
    `_strip_render` drops `style` from the inlined registry (it is emitted once, as the shared
    <style id="pb-product-css">), so the CSS pane gets its own small map. Pure and deterministic:
    registry order, only components that have a sheet."""
    out = {}
    for c in reg.get("components", []) or []:
        if isinstance(c, dict) and c.get("id") and isinstance(c.get("style"), str) and c["style"].strip():
            out[c["id"]] = c["style"]
    return out


def build_ds_html(reg, ds_shell, runtime_js, nodes_by_id, version="unknown",
                  project_js="", project_deps=()):
    """Render the design-system site (component workbench) from the registry. Pure. Injects the
    shared runtime, the project's declared runtime modules, the emitted window[renderCmp*], the
    inlined registry, and per-component node JSON (PB_NODES). Returns (html, missing). Raises
    RenderError on a missing marker.

    The DS site gets registry.runtime[] for the same reason the prototype does: a component whose
    body calls a project module at render time cannot demo without it, and a demo that throws is
    the failure mode this site exists to catch."""
    bodies, missing = _render_fn_bodies(reg)
    bodies = _product_css_js(reg) + (project_js or "") + bodies
    styles = _ds_styles(reg)
    inline_reg = _strip_render(reg)
    notes = _ds_annotations(reg)
    for c in inline_reg.get("components", []) or []:
        for k, v in notes.get(c.get("id") if isinstance(c, dict) else None, {}).items():
            c.setdefault(k, v)
    inlined = json.dumps(inline_reg, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    nodes = json.dumps(nodes_by_id, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    css_map = json.dumps(styles, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    for marker in ("/*__PB_REGISTRY_START__*/", "/*__PB_NODES_START__*/", "/*__PB_RUNTIME__*/", "/*__PB_RENDER_FNS__*/"):
        if marker not in ds_shell:
            raise RenderError("design-system shell is missing the %s marker" % marker)
    html = re.sub(r"/\*__PB_REGISTRY_START__\*/.*?/\*__PB_REGISTRY_END__\*/",
                  lambda m: "/*__PB_REGISTRY_START__*/" + inlined + "/*__PB_REGISTRY_END__*/",
                  ds_shell, count=1, flags=re.S)
    html = re.sub(r"/\*__PB_NODES_START__\*/.*?/\*__PB_NODES_END__\*/",
                  lambda m: "/*__PB_NODES_START__*/" + nodes + "/*__PB_NODES_END__*/",
                  html, count=1, flags=re.S)
    # The Code view's CSS pane. Optional marker: a shell older than the workbench has none, and its
    # page simply has no CSS to show (fail open, as inject_chrome does).
    html = re.sub(r"/\*__PB_STYLES_START__\*/.*?/\*__PB_STYLES_END__\*/",
                  lambda m: "/*__PB_STYLES_START__*/" + css_map + "/*__PB_STYLES_END__*/",
                  html, count=1, flags=re.S)
    html = html.replace("/*__PB_RUNTIME__*/", shared_runtime(runtime_js), 1)
    html = inject_chrome(html)
    html = html.replace("/*__PB_RENDER_FNS__*/", bodies, 1)
    if project_deps:
        html = html.replace(_RUNTIME_DEPS_MARK, "\n".join(project_deps), 1)
    html = html.replace("{{PB_SHELL_VERSION}}", version)
    return html, missing


def build_ds(reg, ds_shell, runtime_js, catalog=None, version="unknown",
             project_js="", project_deps=()):
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
    return build_ds_html(reg, ds_shell, runtime_js, nodes_by_id, version,
                         project_js=project_js, project_deps=project_deps)


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
    rt_js, rt_deps, rt_missing = load_runtime(reg, base_dir)
    version = plugin_version()
    html, missing = build_ds(reg, ds_shell, runtime_js, catalog, version,
                             project_js=rt_js, project_deps=rt_deps)
    missing += ["runtime module %s" % m for m in rt_missing]
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
            name, len(reg.get("components", [])), len(reg.get("tokens", {})), rest[3],
            len(html.encode("utf-8"))))
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
        len(reg.get("tokens", {})), args[2], len(html.encode("utf-8")))
    if missing:
        msg += "\n  note: %d render fn(s) had no `render` body and will be empty: %s" % (len(missing), ", ".join(missing))
    print(msg)


if __name__ == "__main__":
    main()
