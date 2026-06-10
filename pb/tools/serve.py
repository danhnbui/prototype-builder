#!/usr/bin/env python3
"""
pb-serve — the preview dev server for the registry → prototype.html loop.

The build loop edits `registry.json`; `prototype.html` is a deterministic render of it
(see render.py). Statically serving the *file* means a manual `/pb:build --render` + a
browser refresh after every tweak. This server closes that gap:

  * watches  registry.json (+ the shell template + render.py),
  * renders  through the SAME build_html() path render.py uses (rule #2: one render
             truth — the preview is byte-identical to what `/pb:build --render` writes),
  * reloads  every connected browser over Server-Sent Events the instant a watched
             file changes.

It renders IN MEMORY and never touches `prototype.html` on disk (rule #1: the HTML is
never the source of truth, never hand-edited) — so the git-tracked render stays under
your explicit control. Pass --write to ALSO keep prototype.html fresh on each change
(a watch-mode `/pb:build --render`).

A bad registry mid-edit (invalid JSON, a missing anchor) shows a recoverable error page
with the traceback instead of crashing the server; fix + save and it reloads clean.

Stdlib only — no pip install, matching render.py and the project's no-heavy-deps stance.

Usage:
  python3 serve.py [registry.json] [--port N] [--host H] [--shell PATH]
                   [--write [--out PATH]] [--no-open]
"""
import argparse, glob, json, mimetypes, os, socket, sys, threading, time, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape as _esc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # import sibling render.py
import render


def log(msg):
    print("pb-serve · " + msg, flush=True)


# The live-reload client. Injected before </body> in the served HTML only — never written
# to disk, so a --write'd prototype.html stays identical to a plain `/pb:build --render`.
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

    def __init__(self, reg_path, shell_path, out_path, write):
        self.reg_path = reg_path
        self.shell_path = shell_path
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

    @property
    def base_dir(self):
        return os.path.dirname(self.reg_path)

    @property
    def body_files(self):
        """The v1.4 render-body files (render/**/*.js next to the registry), if any."""
        root = os.path.join(self.base_dir, "render")
        return sorted(glob.glob(os.path.join(root, "**", "*.js"), recursive=True))

    @property
    def watched(self):
        # body_files is recomputed each poll so newly added/removed .js files are noticed.
        return [self.reg_path, self.shell_path, self.render_path] + self.body_files

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
        html, _missing = render.build_html(reg, shell)
        if state.write and state.out_path:
            try:
                with open(state.out_path, "w", encoding="utf-8") as f:
                    f.write(html)
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

    def _send(self, body, ctype="text/html; charset=utf-8", status=200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self._write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/__pb_events":
            return self.serve_events()
        if path in ("/", "/index.html"):
            return self.serve_preview()
        if path == "/favicon.ico":
            return self._send(b"", ctype="image/x-icon", status=204)
        return self.serve_static(path)

    def serve_preview(self):
        html, err = render_current(self.state)
        body = (error_page(err, self.state.reg_path) if err is not None
                else inject_reload(html)).encode("utf-8")
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
        root = os.path.dirname(os.path.abspath(self.state.reg_path)) or "/"
        full = os.path.normpath(os.path.join(root, path.lstrip("/")))
        if full != root and not full.startswith(root + os.sep):
            return self._send(b"403 forbidden", ctype="text/plain", status=403)
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            return self._send(b"404 not found", ctype="text/plain", status=404)
        try:
            with open(full, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(b"404 not found", ctype="text/plain", status=404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
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

    ap = argparse.ArgumentParser(
        prog="pb-serve",
        description="Preview dev server: watch registry.json → render → live-reload the browser.")
    ap.add_argument("registry", nargs="?", default="registry.json",
                    help="path to registry.json (default: ./registry.json)")
    ap.add_argument("--shell", default=default_shell,
                    help="the shell prototype.html template (default: the plugin template)")
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

    state = State(reg_path, shell_path, out_path, args.write)
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
    log("  shell     %s" % rel(shell_path))
    log("  preview   %s" % url)
    log("  watching  registry.json, shell, render.py, render/**/*.js — saving any reloads the browser")
    log("  to disk   %s" % ("ON → %s" % rel(out_path) if args.write
                            else "off (in-memory preview; --write to update prototype.html)"))

    _html, err = render_current(state)  # render once up front so the banner reflects reality
    if err:
        log("  status    ✗ current registry has a render error — preview shows it")
    log("Ctrl-C to stop.")

    threading.Thread(target=watcher, args=(state,), daemon=True).start()
    if not args.no_open:
        threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.stop.set()
        state.bump()  # wake SSE streams so they exit promptly
        httpd.shutdown()
        log("stopped.")


if __name__ == "__main__":
    main()
