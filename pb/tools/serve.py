#!/usr/bin/env python3
"""
pb-serve — the preview dev server for the registry → prototype.html loop.

The build loop edits `registry.json`; `prototype.html` is a deterministic render of it
(see render.py). Statically serving the *file* means a manual `/pb:build --render` + a
browser refresh after every tweak. This server closes that gap:

  * watches  registry.json (+ the shell template + render.py),
  * renders  through the SAME build_html() path render.py uses (rule #2: one render
             truth — the preview uses the same render logic as `/pb:build --render`; the
             on-disk artifact additionally carries a stamp() drift comment the preview omits),
  * reloads  every connected browser over Server-Sent Events the instant a watched
             file changes.

It renders IN MEMORY and never touches `prototype.html` on disk (rule #1: the HTML is
never the source of truth, never hand-edited) — so the git-tracked render stays under
your explicit control. Pass --write to ALSO keep prototype.html fresh on each change
(a watch-mode `/pb:build --render`).

A bad registry mid-edit (invalid JSON, a missing anchor) shows a recoverable error page
with the traceback instead of crashing the server; fix + save and it reloads clean.

Stdlib only — no pip install, matching render.py and the project's no-heavy-deps stance.

Routes (one server, one port): /  the prototype · /design-system  the component workbench ·
/explore/<target>  a /pb:explore compare-and-rate page · /explore/<target>/<slot>  one option,
rendered in memory with its candidate bodies swapped in (a page round: /explore/<target>/<path> is
the file memory/explore/<target>/<path>) · POST /__pb_explore/<target>/scores · GET /__pb_health
which registry this server shows — what `explore.py link` checks, beside the .preview/server.json
record this server writes next to the registry on start and removes on exit ·
POST /api/meta  the Project settings dialog's save (localhost + same-origin only; see Handler). Written
under slice.py's registry lock and replace-atomically; every bad request is a 400 with a message, a
busy registry a 503, a response may carry `warnings`.

Usage:
  python3 serve.py [registry.json] [--port N] [--host H] [--shell PATH]
                   [--write [--out PATH]] [--no-open]
"""
import argparse, glob, importlib, json, mimetypes, os, re, signal, socket, sys, threading, time, traceback, unicodedata, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from html import escape as _esc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # import sibling render.py
import render
import explore  # /pb:explore's manifests — served at /explore/<target> on this same port
# slice.py is the registry's one write path for a targeted patch. Imported by name through
# importlib because `import slice` would shadow the builtin of the same name in this module.
pbslice = importlib.import_module("slice")


def log(msg):
    print("pb-serve · " + msg, flush=True)


# The live-reload client. Injected before </body> in the served HTML only — never written
# to disk, so a --write'd prototype.html stays free of the reload client, like a plain
# `/pb:build --render` (both are stamped on disk for drift detection).
LIVE_RELOAD = """<script>
/* pb-serve live-reload — injected by serve.py, not part of the render */
(function () {
  function connect() {
    var es = new EventSource('/__pb_events');
    es.onmessage = function (e) { if (e.data === 'reload') location.reload(); };
    es.onerror = function () { es.close(); setTimeout(connect, 1000); };
  }
  connect();
})();
</script>
"""


def inject_reload(html):
    i = html.rfind("</body>")
    return html if i == -1 else html[:i] + LIVE_RELOAD + html[i:]


def inject_explore(html, payload):
    """`window.PB_EXPLORE` for the shell's Sandbox → Explore row, set before the shell's own
    script runs. Served HTML only — an exploration is scratch and never reaches prototype.html."""
    tag = "<script>window.PB_EXPLORE=%s;</script>" % json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    i = html.find("<head")
    j = html.find(">", i) if i != -1 else -1
    return html if j == -1 else html[:j + 1] + tag + html[j + 1:]


# What the page needs to know about the server it came from. Its presence is how the Project
# settings dialog tells "served by /pb:preview, so Save can write" from a shared file (file://)
# or a plain static server, where the same dialog is read-only. Served HTML only.
PREVIEW_API = {"meta": "/api/meta"}


def inject_preview_api(html):
    tag = "<script>window.PB_PREVIEW=%s;</script>" % json.dumps(PREVIEW_API, separators=(",", ":"))
    i = html.find("<head")
    j = html.find(">", i) if i != -1 else -1
    return html if j == -1 else html[:j + 1] + tag + html[j + 1:]


# POST /api/meta — the three project fields the Project settings dialog edits, and nothing else.
META_MAX_BYTES = 64 * 1024
META_BODY_TIMEOUT = 3.0       # seconds the body of a settings save may take to arrive
SCORES_MAX_BYTES = 1024 * 1024  # POST /__pb_explore/<id>/scores: a sheet of scores + notes is larger than a settings save
JSON_MAX_DEPTH = 64            # a settings save nests 2 deep and a score sheet 4; past this it is not a payload
_JSON_SPECIAL = re.compile(r'[\[\]{}"\\]')   # one character each: linear, whatever the input
FIGMA_FILE_RE = re.compile(r"^https://(www\.)?figma\.com/(file|design)/\S+$")
LOOPBACK_ADDRS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")
# A value that is a name or a link carries no control (Cc), format/invisible (Cf) or lone-surrogate
# (Cs) characters: they are how a line-break, a bidi override or a zero-width space gets into a
# registry field, a command line the read-only dialog prints, or a Figma library name — and a lone
# surrogate cannot even be written as UTF-8.
META_BAD_CATEGORIES = ("Cc", "Cf", "Cs")
META_LINK_WARNING = ("designSystem.designLink: not a figma.com/file/… or figma.com/design/… link — "
                     "kept as it was; hand-off and the Figma push will not use it")


def _json_too_deep(text, limit=JSON_MAX_DEPTH):
    """True when JSON text nests past `limit`, counted before parsing so the answer does not depend on
    the Python version: 3.11's parser raises RecursionError on deep input, 3.14's parses it."""
    depth, in_str, escaped = 0, False, -1
    for m in _JSON_SPECIAL.finditer(text):
        i, ch = m.start(), m.group()
        if i == escaped:                      # the character after a backslash, inside a string
            continue
        if in_str:
            if ch == "\\":
                escaped = i + 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


class MetaError(ValueError):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


def _bad_char(value, categories=META_BAD_CATEGORIES):
    """The first character of `value` in one of the Unicode `categories` (default Cc/Cf/Cs), as
    'U+200B', or None."""
    for ch in value:
        if unicodedata.category(ch) in categories:
            return "U+%04X" % ord(ch)
    return None


def validate_meta_payload(payload, existing_link=None, warnings=None):
    """The dialog's three fields → a meta patch. Raises MetaError with the message the dialog
    shows beside the field; nothing outside these three keys is accepted or written.

    `existing_link` is the designLink already in the registry. A link that is not a Figma file
    link is an error when it is NEW — but one the project already carries, sent back unchanged
    (the dialog always sends all three fields), is kept with a warning appended to `warnings`:
    refusing it would make the project's name and design-system name impossible to edit. That
    exemption comes BEFORE the character check: an existing link that carries a control or invisible
    character must not block saving the names either — it is kept as it was, with the warning. A
    link that is CHANGED (or any Figma link) is still refused for such a character. A lone surrogate
    is refused in every case: the registry cannot be written as UTF-8 with one in it."""
    if not isinstance(payload, dict):
        raise MetaError("payload must be a JSON object")
    extra = sorted(set(payload) - {"name", "designSystem"})
    if extra:
        raise MetaError("unexpected field(s): %s" % ", ".join(extra))
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise MetaError("name: required")
    ds = payload.get("designSystem")
    if not isinstance(ds, dict):
        raise MetaError("designSystem: must be an object with name and designLink")
    extra = sorted(set(ds) - {"name", "designLink"})
    if extra:
        raise MetaError("designSystem: unexpected field(s): %s" % ", ".join(extra))
    ds_name = ds.get("name")
    if not isinstance(ds_name, str) or not ds_name.strip():
        raise MetaError("designSystem.name: Required — hand-off and Figma push need it")
    link = ds.get("designLink", "")
    if link is None:
        link = ""
    if not isinstance(link, str):
        raise MetaError("designSystem.designLink: must be a string")
    name, ds_name, link = name.strip(), ds_name.strip(), link.strip()
    # An unchanged non-Figma link is the one value this check lets through as it is.
    kept_link = bool(link) and not FIGMA_FILE_RE.match(link) and isinstance(existing_link, str) \
        and link == existing_link.strip()
    for field, value in (("name", name), ("designSystem.name", ds_name), ("designSystem.designLink", link)):
        bad = _bad_char(value, ("Cs",) if kept_link and field == "designSystem.designLink" else META_BAD_CATEGORIES)
        if bad:
            raise MetaError("%s: must not contain control, invisible or invalid characters (%s)" % (field, bad))
    if link and not FIGMA_FILE_RE.match(link):
        if kept_link:
            if warnings is not None:
                warnings.append(META_LINK_WARNING)
        else:
            raise MetaError("designSystem.designLink: must be a figma.com/file/… or figma.com/design/… link")
    if len(name) > 200 or len(ds_name) > 200 or len(link) > 2000:
        raise MetaError("a value is too long")
    return {"name": name, "designSystem": {"name": ds_name, "designLink": link}}


def save_meta(reg_path, payload, timeout=None):
    """lock → load → validate against what the registry holds now → merge → atomic write. Returns
    (the fields the dialog shows, warnings). The merge is slice.py's own (deep: every other key
    under meta and meta.designSystem is kept); an emptied Figma link removes the key rather than
    leaving an empty string a tool would read as a link. Raises MetaError (400), RegistryLocked,
    or OSError/ValueError/SystemExit for an unreadable or unwritable registry."""
    with pbslice.registry_lock(reg_path, "preview settings save", timeout=timeout):
        reg = pbslice._load(reg_path)
        meta = reg.setdefault("meta", {})
        current = meta.get("designSystem") if isinstance(meta.get("designSystem"), dict) else {}
        existing = current.get("designLink") if isinstance(current.get("designLink"), str) else None
        warnings = []
        patch = validate_meta_payload(payload, existing_link=existing, warnings=warnings)
        if not isinstance(meta.get("designSystem"), dict):
            meta.pop("designSystem", None)
        pbslice._deep_merge(meta, patch)
        if not meta["designSystem"].get("designLink"):
            meta["designSystem"].pop("designLink", None)
        pbslice._write(reg_path, reg)
    ds = meta["designSystem"]
    return ({"name": meta.get("name", ""),
             "designSystem": {"name": ds.get("name", ""), "designLink": ds.get("designLink", "")}}, warnings)


def error_page(detail, reg_path):
    """A dark, self-reloading error page shown when the current registry won't render."""
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>pb-serve · render error</title><style>"
        "body{margin:0;background:#1c1f22;color:#e6e8eb;"
        "font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace}"
        ".wrap{max-width:920px;margin:8vh auto;padding:0 24px}"
        "h1{font-size:18px;color:#ff8a80;margin:0 0 4px}"
        "p{color:#8a94a0;margin:0 0 20px}code{color:#e6e8eb}"
        "pre{background:#0f1113;border:1px solid #2d343c;border-radius:8px;"
        "padding:16px 18px;overflow:auto;white-space:pre-wrap;word-break:break-word}"
        "</style></head><body><div class=\"wrap\">"
        "<h1>⚠ render error</h1>"
        "<p>Fix <code>" + _esc(reg_path) + "</code> and save — this page reloads itself.</p>"
        "<pre>" + _esc(detail) + "</pre></div>" + LIVE_RELOAD + "</body></html>"
    )


class State:
    """Shared between the watcher thread and the request handler threads."""

    def __init__(self, reg_path, shell_path, out_path, write, ds_shell_path=None, runtime_path=None,
                 explore_shell_path=None):
        self.reg_path = reg_path
        self.shell_path = shell_path
        self.explore_shell_path = explore_shell_path  # the /explore/<target> compare page template
        self._slot_cache = {}                          # (target, slot) -> (version, html, err)
        self.ds_shell_path = ds_shell_path      # the design-system.html template (2nd site)
        self.runtime_path = runtime_path        # shared runtime.js injected into the DS site
        self.out_path = out_path
        self.write = write
        self.render_path = os.path.abspath(render.__file__)
        self.version = 0                  # bumps on any watched-file change
        self.cond = threading.Condition()  # guards version; wakes the SSE streams
        self.stop = threading.Event()
        self._cache_lock = threading.Lock()
        self._cache_version = -1
        self._cache_html = None
        self._cache_err = None
        self._cache_ds_version = -1       # separate cache for the design-system site
        self._cache_ds_html = None
        self._cache_ds_err = None

    @property
    def base_dir(self):
        return os.path.dirname(self.reg_path)

    @property
    def body_files(self):
        """The v1.4 render-body files (render/**/*.js next to the registry) and their optional
        stylesheets (render/**/*.css, via styleSrc), if any."""
        root = os.path.join(self.base_dir, "render")
        return sorted(glob.glob(os.path.join(glob.escape(root), "**", "*.js"), recursive=True)
                      + glob.glob(os.path.join(glob.escape(root), "**", "*.css"), recursive=True))

    @property
    def runtime_files(self):
        """The schema-11 project modules (runtime/**/*.js) — edited like any other source."""
        root = os.path.join(self.base_dir, "runtime")
        return sorted(glob.glob(os.path.join(glob.escape(root), "**", "*.js"), recursive=True))

    @property
    def watched(self):
        # body_files is recomputed each poll so newly added/removed .js files are noticed.
        extra = [p for p in (self.ds_shell_path, self.runtime_path) if p]
        return ([self.reg_path, self.shell_path, self.render_path] + extra
                + self.body_files + self.runtime_files)

    def bump(self):
        with self.cond:
            self.version += 1
            self.cond.notify_all()


def render_current(state):
    """Render the registry as it is on disk now → (html, error_str). Cached per version."""
    with state._cache_lock:
        if state._cache_version == state.version:
            return state._cache_html, state._cache_err

    html, err = None, None
    try:
        with open(state.reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        with open(state.shell_path, encoding="utf-8") as f:
            shell = f.read()
        reg = render.load_bodies(reg, state.base_dir)  # resolve renderSrc body files (v1.4)
        reg = render.load_specs(reg, state.base_dir)   # resolve specSrc sidecars (schema 10)
        version = render.plugin_version()
        logic = render.load_logic(state.base_dir, reg)  # derive the logic graph (fails open)
        rt_js, rt_deps, _rt_missing = render.load_runtime(reg, state.base_dir)  # registry.runtime[]
        html, _missing = render.build_html(reg, shell, version, logic=logic,
                                           runtime_js=render.load_shared_runtime(state.runtime_path),
                                           project_js=rt_js, project_deps=rt_deps)
        if state.write and state.out_path:
            try:
                with open(state.out_path, "w", encoding="utf-8") as f:
                    f.write(render.stamp(html, version))  # disk artifact gets the drift stamp
            except OSError as e:
                log("warn: could not write %s (%s)" % (state.out_path, e))
    except FileNotFoundError as e:
        err = "File not found: %s" % e
    except json.JSONDecodeError as e:
        err = "%s is not valid JSON — line %d, column %d:\n  %s" % (
            os.path.basename(state.reg_path), e.lineno, e.colno, e.msg)
    except render.RenderError as e:
        err = "Render error: %s" % e
    except Exception:
        err = traceback.format_exc()

    with state._cache_lock:
        state._cache_version = state.version
        state._cache_html = html
        state._cache_err = err
    return html, err


def render_ds_current(state):
    """Render the design-system site as it is on disk now → (html, error_str). Cached per version.
    Uses the SAME render.build_ds() the CLI (`render.py --ds`) uses, so both sites stay one truth."""
    if not (state.ds_shell_path and state.runtime_path):
        return None, "design-system site not configured (missing --ds-shell / --runtime)"
    with state._cache_lock:
        if state._cache_ds_version == state.version:
            return state._cache_ds_html, state._cache_ds_err

    html, err = None, None
    try:
        with open(state.reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        with open(state.ds_shell_path, encoding="utf-8") as f:
            ds_shell = f.read()
        with open(state.runtime_path, encoding="utf-8") as f:
            runtime_js = f.read()
        reg = render.load_bodies(reg, state.base_dir)
        reg = render.load_specs(reg, state.base_dir)
        catalog = render._find_catalog(state.base_dir, reg)
        rt_js, rt_deps, _rt_missing = render.load_runtime(reg, state.base_dir)
        html, _missing = render.build_ds(reg, ds_shell, runtime_js, catalog, render.plugin_version(),
                                         project_js=rt_js, project_deps=rt_deps)
    except FileNotFoundError as e:
        err = "File not found: %s" % e
    except json.JSONDecodeError as e:
        err = "%s is not valid JSON — line %d, column %d:\n  %s" % (
            os.path.basename(state.reg_path), e.lineno, e.colno, e.msg)
    except render.RenderError as e:
        err = "Render error: %s" % e
    except Exception:
        err = traceback.format_exc()

    with state._cache_lock:
        state._cache_ds_version = state.version
        state._cache_ds_html = html
        state._cache_ds_err = err
    return html, err


def render_slot(state, man, slot):
    """One exploration option rendered in memory with its overlay → (html, err). Cached per
    (target, slot) and invalidated by the same version counter the watcher bumps — a candidate
    body lives under render/, so saving it reloads its frame like any other body."""
    key = (man["target"], slot)
    with state._cache_lock:
        hit = state._slot_cache.get(key)
        if hit and hit[0] == state.version:
            return hit[1], hit[2]
    html, err = None, None
    try:
        if man.get("mode") in ("goal", "ia"):
            raise explore.ExploreError("a %s exploration has no bodies to render — see /explore/%s"
                                       % (man.get("mode"), man["target"]))
        html = explore.render_option(state.reg_path, state.shell_path, man, slot, state.runtime_path)
    except explore.ExploreError as e:
        err = str(e)
    except FileNotFoundError as e:
        err = "File not found: %s" % e
    except render.RenderError as e:
        err = "Render error in %s: %s" % (slot, e)
    except Exception:
        err = traceback.format_exc()
    with state._cache_lock:
        state._slot_cache[key] = (state.version, html, err)
    return html, err


def explore_compare(state, man):
    """The compare-and-rate page: the template with this exploration's manifest inlined."""
    try:
        with open(state.explore_shell_path or "", encoding="utf-8") as f:
            shell = f.read()
    except OSError:
        return error_page("compare template not found: %s" % state.explore_shell_path, state.reg_path)
    try:
        with open(state.reg_path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        reg = {}
    meta = reg.get("meta") or {}
    data = dict(man, projectName=meta.get("name") or "", devices=meta.get("devices") or [],
                averages=explore.averages(man), missing=explore.missing_scores(man))
    if man.get("mode") == "ia":   # each slot's parsed structure + the approved jobs it groups
        data.update(explore.ia_page(state.base_dir, reg, man))
    inlined = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return render.inject_chrome(shell).replace("/*__PB_EXPLORE_SESSION__*/null", inlined, 1)


def explore_index(state, note=""):
    rows = "".join(
        '<li><a href="/explore/%s">%s</a> <span>%s · %d options</span></li>' % (
            _esc(s["target"]), _esc(s["target"]), _esc(s["mode"]), len(s["slots"]))
        for s in explore.sessions(state.base_dir)) or "<li>No open explorations. Start one with <code>/pb:explore &lt;id&gt;</code>.</li>"
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>Explorations</title><style>"
            ":root{--bg:#f7f7f8;--fg:#1d1f23;--dim:#6b7280;--line:#e3e5e8;--accent:#2563eb}"
            "@media (prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e8eaed;--dim:#9aa1ab;--line:#2b2f35;--accent:#7aa2ff}}"
            "body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif}"
            ".wrap{max-width:720px;margin:8vh auto;padding:0 16px}h1{font-size:20px}"
            "ul{list-style:none;padding:0}li{padding:10px 0;border-bottom:1px solid var(--line)}"
            "a{color:var(--accent);font-weight:600;text-decoration:none}span{color:var(--dim);margin-left:8px}"
            "p{color:var(--dim)}</style></head><body><div class=\"wrap\">"
            "<h1>Explorations</h1>%s<ul>%s</ul><p><a href=\"/\">← The live prototype</a></p></div></body></html>"
            % ("<p>%s</p>" % _esc(note) if note else "", rows))


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def watcher(state):
    """Poll watched-file mtimes; on any change bump the version and eagerly re-render (to log)."""
    seen = {p: _mtime(p) for p in state.watched}
    while not state.stop.wait(0.3):
        changed = [p for p in state.watched if _mtime(p) != seen.get(p)]
        if not changed:
            continue
        for p in changed:
            seen[p] = _mtime(p)
        state.bump()
        _html, err = render_current(state)
        what = ", ".join(os.path.basename(p) for p in changed)
        if err:
            log("✗ %s changed — render error (preview shows it; auto-recovers on save)" % what)
        else:
            log("✓ %s changed — re-rendered, reloading browsers" % what)


class Handler(BaseHTTPRequestHandler):
    state = None              # set on the class before the server starts
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):  # silence per-request noise; the watcher logs what matters
        pass

    def _write(self, data):
        try:
            self.wfile.write(data)
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _send(self, body, ctype="text/html; charset=utf-8", status=200, close=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype.replace("\r", "").replace("\n", ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if close:
            # A request body we did not read is still in the socket; on a kept-alive connection
            # its bytes would be parsed as the next request. Say so and hang up.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self._write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/__pb_events":
            return self.serve_events()
        if path == "/__pb_health":   # names a local path, so this machine only (--host may bind wider)
            if self.client_address[0] not in LOOPBACK_ADDRS:
                return self._send(b"404 not found", ctype="text/plain", status=404)
            return self._json({"ok": True, "app": "pb-preview", "registry": self.state.reg_path,
                               "pid": os.getpid(), "version": render.plugin_version()})
        if path in ("/", "/index.html"):
            return self.serve_preview()
        if path in ("/design-system", "/design-system/", "/design-system.html"):
            return self.serve_ds()
        if path == "/explore" or path.startswith("/explore/"):
            return self.serve_explore([p for p in path.split("/")[2:] if p])
        if path == "/favicon.ico":
            return self._send(b"", ctype="image/x-icon", status=204)
        return self.serve_static(path)

    def serve_preview(self):
        html, err = render_current(self.state)
        if err is None:
            html = inject_explore(html, {"sessions": explore.sessions(self.state.base_dir), "current": None})
            html = inject_preview_api(html)
        body = (error_page(err, self.state.reg_path) if err is not None
                else inject_reload(html)).encode("utf-8")
        self._send(body)

    # ── /pb:explore — one compare page per exploration, on this server (never another port) ──
    def serve_explore(self, parts):
        st = self.state
        if not parts:
            return self._send(explore_index(st).encode("utf-8"))
        target = parts[0]
        try:
            man = explore.load_manifest(st.base_dir, target)
        except explore.ExploreError as e:
            return self._send(explore_index(st, str(e)).encode("utf-8"), status=404)
        if len(parts) == 1:
            return self._send(explore_compare(st, man).encode("utf-8"))
        if man.get("mode") == "pages":
            return self.serve_explore_page(man, parts[1:])
        slot = parts[1]
        html, err = render_slot(st, man, slot)
        if err is not None:
            return self._send(error_page(err, st.reg_path).encode("utf-8"),
                              status=404 if err.startswith("no slot") else 200)
        html = inject_explore(html, {"sessions": explore.sessions(st.base_dir),
                                     "current": {"target": target, "slot": slot}})
        self._send(inject_reload(html).encode("utf-8"))

    def serve_explore_page(self, man, rest):
        """A page round's files, as they are on disk under memory/explore/<target>/ — so an option
        page's relative links (its own css, ../shared/…) resolve on this same port. A bare slot
        (/explore/<target>/<slot>, what Sandbox → Explore opens) redirects to that slot's page."""
        target = man["target"]
        opt = next((o for o in man.get("options", []) if o.get("slot") == rest[0]), None) if len(rest) == 1 else None
        if opt and opt.get("page") and opt["page"].strip("/") != rest[0]:
            self.send_response(302)
            self.send_header("Location", "/explore/%s/%s" % (target, opt["page"].lstrip("/")))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        root = os.path.realpath(os.path.join(self.state.base_dir, explore.EXPLORE_DIR, target))
        # realpath expands symlinks and `..` first, so anything that resolves outside the round is refused
        rel = "/".join(urllib.parse.unquote(p) for p in rest).strip("/") or "index.html"
        candidate = os.path.realpath(os.path.join(root, rel))
        if not candidate.startswith(root + os.sep):
            return self._send(b"403 forbidden", ctype="text/plain", status=403)
        if os.path.isdir(candidate):
            candidate = os.path.join(candidate, "index.html")
        try:
            with open(candidate, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(b"404 not found", ctype="text/plain", status=404)
        self._send(data, ctype=mimetypes.guess_type(candidate)[0] or "application/octet-stream")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/meta":
            return self.post_meta()
        parts = [p for p in path.split("/") if p]
        if len(parts) != 3 or parts[0] != "__pb_explore" or parts[2] != "scores":
            return self._send(b"404 not found", ctype="text/plain", status=404, close=True)
        return self.post_scores(parts[1])

    def post_scores(self, target):
        """POST /__pb_explore/<id>/scores — the compare page's save. It writes the exploration's
        manifest, so it is held to the same three doors as POST /api/meta (a loopback peer, a loopback
        Host, this page's own Origin) and reads its body the same way: a Content-Length that is not a
        plain number, a body over the limit or that stops arriving, JSON nested until the parser gives
        up — each a 400 with a message, never a traceback and never a thread held open."""
        self._body_read = False
        try:
            why = self._local_same_origin()
            if why:
                return self._json({"ok": False, "error": why}, status=403, close=True)
            payload = self._meta_body(SCORES_MAX_BYTES)
            if not isinstance(payload, dict):
                raise explore.ExploreError("payload must be a JSON object", explore.EXIT_USAGE)
            with self.state._cache_lock:   # one writer at a time; the manifest write is atomic
                man = explore.load_manifest(self.state.base_dir, target)
                man = explore.apply_scores(man, payload)
                explore.save_manifest(self.state.base_dir, man)
            out = {"ok": True, "missing": explore.missing_scores(man), "averages": explore.averages(man)}
            self._json(out)
        except (explore.ExploreError, ValueError) as e:      # MetaError is a ValueError
            self._json({"ok": False, "error": str(e)},
                       status=getattr(e, "status", 400), close=not self._body_read)
        except OSError as e:
            self._json({"ok": False, "error": "could not write the scores (%s)" % e},
                       status=500, close=not self._body_read)

    def _json(self, obj, status=200, close=False):
        self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   ctype="application/json; charset=utf-8", status=status, close=close)

    def _local_same_origin(self):
        """A write to registry.json is only for the person at this machine, from this page.
        Three checks, each closing a different door: the peer is loopback (another machine on
        the LAN, when --host binds wider); the Host header names a loopback host (DNS rebinding,
        where an attacker's name resolves to 127.0.0.1); and the Origin is this server itself
        (any other page open in the same browser — a cross-site POST carries its own Origin)."""
        if self.client_address[0] not in LOOPBACK_ADDRS:
            return "only accepted from this machine"
        host = (self.headers.get("Host") or "").strip().lower()
        hostname = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        if hostname not in LOOPBACK_HOSTS:
            return "only accepted on a loopback host"
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin != "http://" + host:
            return "only accepted from this preview's own page"
        return None

    def _meta_body(self, max_bytes=META_MAX_BYTES):
        """The request body of a settings or scores POST, read and parsed — or a MetaError with the message
        the dialog shows. Every way a client can get this wrong ends here as a 400: a Content-Length
        that is not a plain number, missing, or over the limit; a body that is not UTF-8 or not
        JSON; JSON nested past JSON_MAX_DEPTH, or a number too long for the parser."""
        raw = (self.headers.get("Content-Length") or "").strip()
        if not re.fullmatch(r"[0-9]{1,12}", raw):
            raise MetaError("Content-Length must be a plain number of bytes" if raw else "payload missing")
        n = int(raw)
        if n <= 0:
            raise MetaError("payload missing")
        if n > max_bytes:
            raise MetaError("payload too large (limit %d KB)" % (max_bytes // 1024))
        # A client that promises n bytes and sends fewer must not hold this thread forever.
        self.connection.settimeout(META_BODY_TIMEOUT)
        try:
            data = self.rfile.read(n)
        except OSError:                       # socket.timeout is one
            data = b""
        finally:
            self.connection.settimeout(None)
        if len(data) < n:
            raise MetaError("payload incomplete: Content-Length said %d bytes, %d arrived" % (n, len(data)))
        self._body_read = True
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise MetaError("payload is not valid JSON")
        if _json_too_deep(text):
            raise MetaError("payload is nested too deeply")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise MetaError("payload is not valid JSON")
        except RecursionError:                # the depth check above should make this unreachable
            raise MetaError("payload is nested too deeply")
        except ValueError:
            raise MetaError("payload is not valid JSON (a number is too long)")

    def post_meta(self):
        """POST /api/meta — {name, designSystem:{name, designLink}} → registry.meta, written
        through slice.py under the registry lock; returns the saved fields (and `warnings`, a list,
        when something was kept that a person should know about). The watcher sees the new mtime
        and live-reloads every open page, so the dialog's own re-render and the reload agree.
        Whatever goes wrong is a JSON error with a message and a status — never a traceback."""
        self._body_read = False
        try:
            why = self._local_same_origin()
            if why:
                return self._json({"ok": False, "error": why}, status=403, close=True)
            payload = self._meta_body()
            meta, warnings = save_meta(self.state.reg_path, payload)
        except MetaError as e:
            return self._json({"ok": False, "error": str(e)}, status=e.status, close=not self._body_read)
        except pbslice.LockFileUnsafe as e:       # not "try again": something is sitting where the lock goes
            return self._json({"ok": False, "error": str(e)}, status=500, close=not self._body_read)
        except pbslice.RegistryLocked as e:
            return self._json({"ok": False, "error": str(e)}, status=503, close=not self._body_read)
        except (OSError, ValueError, SystemExit) as e:
            return self._json({"ok": False, "error": "could not write registry.json (%s)" % e},
                              status=500, close=not self._body_read)
        out = {"ok": True, "meta": meta}
        if warnings:
            out["warnings"] = warnings
        self._json(out)   # the watcher sees the new mtime and reloads pages

    def serve_ds(self):
        """The design-system site (component workbench) — the second projection of the registry."""
        html, err = render_ds_current(self.state)
        body = (error_page(err, self.state.reg_path) if err is not None
                else inject_reload(inject_preview_api(html))).encode("utf-8")
        self._send(body)

    def serve_events(self):
        """One long-lived SSE stream per browser tab; emits `reload` when the version bumps."""
        st = self.state
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # disable proxy buffering
        self.end_headers()
        if not self._write(b": connected\n\n"):
            return
        last = st.version
        while not st.stop.is_set():
            with st.cond:
                st.cond.wait_for(lambda: st.version != last or st.stop.is_set(), timeout=15)
            if st.stop.is_set():
                break
            if st.version != last:
                last = st.version
                ok = self._write(b"data: reload\n\n")
            else:
                ok = self._write(b": ping\n\n")  # heartbeat / dead-client detection
            if not ok:
                break

    def serve_static(self, path):
        """Fall back to files next to the registry (e.g. local assets a render references)."""
        root = Path(self.state.reg_path).resolve().parent
        try:
            # relative_to() raises ValueError on traversal; resolve() expands symlinks first
            rel = (root / path.lstrip("/")).resolve().relative_to(root)
        except ValueError:
            return self._send(b"403 forbidden", ctype="text/plain", status=403)
        # Rebuild from root so the remainder of the function operates on a clean path
        candidate = root / rel
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            return self._send(b"404 not found", ctype="text/plain", status=404)
        try:
            data = candidate.read_bytes()
        except OSError:
            return self._send(b"404 not found", ctype="text/plain", status=404)
        ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self._send(data, ctype=ctype)


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A browser closing a kept-alive or SSE connection raises these mid-request —
        # normal churn for a dev preview, not worth a traceback. Real errors still surface.
        if issubclass(sys.exc_info()[0] or Exception,
                      (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


def make_server(host, port, explicit):
    """Bind `port`; if it wasn't explicitly requested, walk up to find a free one."""
    candidates = [port] if explicit else [port + i for i in range(60)]
    last = None
    for p in candidates:
        try:
            return PreviewServer((host, p), Handler)
        except OSError as e:
            last = e
    if explicit:
        sys.exit("pb-serve: port %d is in use (%s). Pick another with --port." % (port, last))
    sys.exit("pb-serve: no free port near %d (%s)." % (port, last))


def write_server_record(path, rec):
    """.preview/server.json — where `explore.py link` finds this server. Best effort: a read-only
    project still serves; link then starts one of its own."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        log("  ⚠ could not write %s (%s) — explore.py link will not find this server" % (path, e))


def drop_server_record(path):
    """Remove the record on exit — only if it is still ours (another server may have started since)."""
    try:
        with open(path, encoding="utf-8") as f:
            if json.load(f).get("pid") == os.getpid():
                os.remove(path)
    except (OSError, ValueError, AttributeError):
        pass


def startup_summary(reg_path):
    try:
        with open(reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        name = (reg.get("meta") or {}).get("name") or "(unnamed)"
        return "%s — %d components, %d screens, %d tokens" % (
            name, len(reg.get("components", [])), len(reg.get("screens", [])),
            len(reg.get("tokens", {})))
    except Exception:
        return None


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_shell = os.path.normpath(os.path.join(here, "..", "template", "prototype.html"))
    default_ds_shell = os.path.normpath(os.path.join(here, "..", "template", "design-system.html"))
    default_runtime = os.path.normpath(os.path.join(here, "..", "template", "runtime.js"))
    default_explore_shell = os.path.normpath(os.path.join(here, "..", "template", "explore-compare.html"))

    ap = argparse.ArgumentParser(
        prog="pb-serve",
        description="Preview dev server: watch registry.json → render → live-reload the browser. "
                    "Serves TWO projections of the registry: the prototype at / and the design system at /design-system.")
    ap.add_argument("registry", nargs="?", default="registry.json",
                    help="path to registry.json (default: ./registry.json)")
    ap.add_argument("--shell", default=default_shell,
                    help="the shell prototype.html template (default: the plugin template)")
    ap.add_argument("--ds-shell", default=default_ds_shell,
                    help="the design-system.html template served at /design-system")
    ap.add_argument("--runtime", default=default_runtime,
                    help="the shared runtime.js injected into the design-system site")
    ap.add_argument("--port", type=int, default=8000,
                    help="port (default: 8000, auto-incremented if busy)")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
    ap.add_argument("--write", action="store_true",
                    help="also write the rendered prototype.html to disk on every change")
    ap.add_argument("--out", default=None,
                    help="output path for --write (default: prototype.html next to the registry)")
    ap.add_argument("--no-open", action="store_true", help="don't open the browser on start")
    args = ap.parse_args()

    reg_path = os.path.abspath(args.registry)
    shell_path = os.path.abspath(args.shell)
    if not os.path.isfile(reg_path):
        sys.exit("pb-serve: registry not found: %s" % reg_path)
    if not os.path.isfile(shell_path):
        sys.exit("pb-serve: shell template not found: %s" % shell_path)
    out_path = os.path.abspath(args.out) if args.out else os.path.join(
        os.path.dirname(reg_path), "prototype.html")

    # Paths are absolute now, so it's safe to anchor cwd to a dir we can read. A sandboxed
    # launcher (e.g. the macOS preview helper) may hand us an inherited cwd we're not allowed
    # to stat — then any later os.getcwd() (os.path.relpath in the banner, stdlib internals)
    # raises EPERM. chdir here keeps the running server robust to that.
    try:
        os.chdir(here)
    except OSError:
        pass

    ds_shell_path = os.path.abspath(args.ds_shell) if (args.ds_shell and os.path.isfile(args.ds_shell)) else None
    runtime_path = os.path.abspath(args.runtime) if (args.runtime and os.path.isfile(args.runtime)) else None
    state = State(reg_path, shell_path, out_path, args.write, ds_shell_path, runtime_path,
                  default_explore_shell if os.path.isfile(default_explore_shell) else None)
    Handler.state = state

    explicit_port = ("--port" in sys.argv) or any(a.startswith("--port=") for a in sys.argv)
    httpd = make_server(args.host, args.port, explicit_port)
    port = httpd.server_address[1]
    url = "http://%s:%d/" % (args.host, port)

    def rel(p):  # short path when cwd is readable; absolute path if the sandbox forbids getcwd
        try:
            return os.path.relpath(p)
        except OSError:
            return p
    log("Product Builder preview")
    summary = startup_summary(reg_path)
    if summary:
        log("  registry  %s  ·  %s" % (rel(reg_path), summary))
    else:
        log("  registry  %s" % rel(reg_path))
    log("  shell     %s  ·  pb v%s" % (rel(shell_path), render.plugin_version()))
    log("  prototype %s" % url)
    if ds_shell_path and runtime_path:
        log("  design    %sdesign-system  ·  the component workbench" % url)
    log("  explore   %sexplore  ·  /pb:explore options side by side, rated in the page" % url)
    log("  watching  registry.json, shells, render.py, render/**/*.{js,css}, runtime/**/*.js — saving any reloads the browser")
    log("  to disk   %s" % ("ON → %s" % rel(out_path) if args.write
                            else "off (in-memory preview; --write to update prototype.html)"))

    _html, err = render_current(state)  # render once up front so the banner reflects reality
    if err:
        log("  status    ✗ current registry has a render error — preview shows it")
    log("Ctrl-C to stop.")

    threading.Thread(target=watcher, args=(state,), daemon=True).start()
    if not args.no_open:
        threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()

    record = os.path.join(state.base_dir, explore.SERVER_FILE)
    write_server_record(record, {"url": url, "host": args.host, "port": port, "pid": os.getpid(),
                                 "registry": reg_path, "startedAt": explore._now()})
    # A plain kill (SIGTERM) unwinds like Ctrl-C, so the record goes with the server.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        drop_server_record(record)
        state.stop.set()
        state.bump()  # wake SSE streams so they exit promptly
        httpd.shutdown()
        log("stopped.")


if __name__ == "__main__":
    main()
