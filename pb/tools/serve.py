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

/pb:research's session routes (tools/research_session.py does the work; this file is the door), every one
for a loopback PEER with a loopback Host only — a 403 for any other, whatever --host or --allow-host say
(a tunnel's proxy is a loopback peer, but it arrives with its own name) — and with no live-reload client and no window.PB_PREVIEW in the pages (a participant's page must never reload):
  GET  /research/<id>/session[?p=P01&pilot=1&mode=moderated]   the participant page, sink = this server
  GET  /research/<id>/observer[?p=P01&pilot=1]                 the facilitator's notes window
  GET  /research/<id>/replay/<e3 | pilot-<sessionId>>          a stored session, replayed on the prototype
  GET  /research/<id>/report                                   memory/research/<id>/report/report.html
  GET  /__pb_research/<id>/evidence/<e3 | pilot-<sessionId>[-screen]>
                                the bytes of a session or recording file, sha256 checked first, streamed,
                                one `Range: bytes=a-b | a- | -n` answered 206 (416 when unsatisfiable)
  POST /__pb_research/<id>/session                             a pb-session JSON → 201 {ok, evidence, sessionId, pilot, warnings}
  POST /__pb_research/<id>/media?session=<sessionId>&kind=screen   the screen recording, streamed to
                                memory/research/<id>/.incoming/ in 1 MiB pieces then stored → 201 {ok, evidence, bytes, sha256}
Both POSTs take the same three doors as /api/meta (loopback peer, loopback Host, this page's own Origin),
need a plain Content-Length (a chunked body is a 411), and answer {ok:false, error} — 400 a refusal, 409 a
duplicate, 503 a busy registry, 500 an unusable lock file or anything unforeseen, never a traceback.

Live fill. A change to registry.json or to .preview/drafts.json (the unapproved lines `slice.py set --draft`
keeps) is sent to the open pages as the SSE message `update`, not `reload`: GET /__pb_data returns the registry
exactly as the render inlines it, the drafts folded in (each marked `_draft: true`; nothing is written), the
derived logic graph over that, and the plugin hook's activity (.preview/activity.json — whether Claude is
working, plus `tools` from .preview/agents.json — the verb of the tool running now and the subagents running). The
prototype shell paints it in place (window.pbApplyData); a page without one — the design system, an
explore option — reloads as before. A body, the shell, the runtime or a stylesheet is compiled into the page,
so those stay `reload`; a reload keeps the reader's place (window.pbSavePlace). The hook's files alone (activity.json,
agents.json) send `activity` and re-render nothing.

Who may ask. Every request, GET and POST, is checked first: its Host header must name this server — a
loopback name, the concrete --host it is bound to, or a name given with --allow-host — or it is a 403
that names the flag. That is what stops a page on another site (DNS rebinding: its name resolves to
127.0.0.1) from reading the project through your browser. A request with no Host is accepted from this
machine only. POST /api/meta, POST /__pb_explore/<id>/scores and every /research/ and /__pb_research/
route stay loopback-only on top of that, whatever --allow-host says. Static files beside the registry are assets only: a dot-file or dot-folder
(.git, .env), memory/ and the registry itself are a 403. Every response carries nosniff,
no-referrer, X-Frame-Options SAMEORIGIN and Cross-Origin-Resource-Policy same-origin.

The server looks after its own footprint: with no browser tab connected and no request for
--idle-exit minutes (default 480, eight hours; 0 = never) it stops itself and removes the record, so a
forgotten preview does not run for days — and one in use does not vanish mid-afternoon. It polls the
files every 0.3 s while somebody is looking and every 2 s otherwise (a page request checks
synchronously first, so a page is never stale), and folds a burst of saves into one reload
(--debounce-ms). `--status` and `--stop` read and end the running server without a `kill`.

Without --port a project gets a port of its own — 8100 + a hash of its registry's path, walking up
when that one is busy — so two projects stop fighting over 8000 and a restart keeps the URL.

`--ensure` is the one idempotent start: it prints the URL of this registry's server, starting one
(detached, through explore.py's find-or-start) only when none is running. A server started that way or
by `explore.py link` is *managed*: it records itself in a per-user folder ($PB_PREVIEW_DIR, else a
0700 folder under the temp dir), and at most $PB_PREVIEW_MAX (default 6; 0 = no cap) of them run at
once — starting another stops the longest-idle one with no tab open, never one someone is looking at.
A plain `serve.py`, and the private servers shot.py and test_run.py boot, neither register nor evict.

Usage:
  python3 serve.py [registry.json] [--port N] [--host H] [--allow-host NAME]... [--shell PATH]
                   [--write [--out PATH]] [--no-open] [--idle-exit MINUTES] [--debounce-ms N]
  python3 serve.py [registry.json] --ensure [--json]    exit 0 running / started · 3 could not start
  python3 serve.py [registry.json] --status [--json]    exit 0 running · 1 not
  python3 serve.py [registry.json] --stop [--json]      exit 0 stopped / was not running · 1 could not
"""
import argparse, datetime, glob, hashlib, importlib, json, math, mimetypes, os, re, select, signal, socket, sys, tempfile, threading, time, traceback, unicodedata, urllib.parse, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from html import escape as _esc
import stat as _stat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # import sibling render.py
import render
import explore  # /pb:explore's manifests — served at /explore/<target> on this same port
import browser as pbbrowser  # the per-user 0700 folder check, for the managed-preview records
# slice.py is the registry's one write path for a targeted patch. Imported by name through
# importlib because `import slice` would shadow the builtin of the same name in this module.
pbslice = importlib.import_module("slice")


def log(msg):
    print("pb-serve · " + msg, flush=True)


# How the server spends time when nobody is looking (WP-B of the resource-hygiene release).
FAST_POLL = 0.3            # seconds between file checks while a tab is connected or a request is recent
SLOW_POLL = 2.0            # …and when nobody has asked for anything for WARM_SECONDS
WARM_SECONDS = 60.0
DEBOUNCE_MS = 300          # a burst of saves is one reload: wait this long with no further change…
DEBOUNCE_CAP = 2.0         # …but never longer than this after the first change, so a file that keeps changing still reloads
DEBOUNCE_STEP = 0.05       # how finely the quiet window is watched
IDLE_EXIT_MIN = 480.0      # stop after this many minutes (8 h) with no tab and no request (0 disables); 30 lost people their preview
PORT_BASE, PORT_SPAN = 8100, 800   # a project's own port, absent --port: PORT_BASE + hash(registry path) % PORT_SPAN
PREVIEW_MAX = 6            # managed servers (--ensure, explore.py link) running at once, per user (0 = no cap)
HEALTH_TIMEOUT = 1.0       # seconds a peer's /__pb_health may take when the cap is counted
SSE_SLICE = 1.0           # an SSE stream looks for a vanished client this often; it pings every SSE_PING
SSE_PING = 15.0
STOP_WAIT = 5.0            # --stop waits this long for the server to go away
DRAFTS_FILE = os.path.join(".preview", "drafts.json")    # unapproved lines, written by `slice.py set --draft`
HOOK_FILE = os.path.join(".preview", "activity.json")    # whether Claude is working, written by pb/hooks/activity.py
TOOLS_FILE = os.path.join(".preview", "agents.json")     # which tool Claude runs and how many subagents, per session, same hook
TOOLS_FRESH_S = 600        # a session record older than this is not counted
TOOLS_VERB_MAX = 20
KIND_HISTORY = 256         # bumps remembered, so a stream that missed some can still say update or reload


# The live-reload client. Injected before </body> in the served HTML only — never written
# to disk, so a --write'd prototype.html stays free of the reload client, like a plain
# `/pb:build --render` (both are stamped on disk for drift detection).
LIVE_RELOAD = """<script>
/* pb-serve live-reload — injected by serve.py, not part of the render */
(function () {
  /* A real reload keeps the reader's place: the prototype shell (window.pbSavePlace) writes its tab, segment
     and scroll to sessionStorage first, and reads them back on boot. Pages without one just reload. */
  function reload() {
    try { if (typeof window.pbSavePlace === 'function') window.pbSavePlace(); } catch (e) { /* keep going */ }
    location.reload();
  }
  function connect() {
    var es = new EventSource('/__pb_events');
    es.onmessage = function (e) {
      if (e.data === 'reload') return reload();
      /* `update`: only registry.json or the drafts changed. A page that can take the new data in place
         (the prototype shell: window.pbApplyData) does; any other page — the design system, an explore
         option — reloads, exactly as before. */
      if (e.data === 'update') {
        if (typeof window.pbApplyData !== 'function') return reload();
        try { Promise.resolve(window.pbApplyData()).catch(reload); } catch (err) { reload(); }
        return;
      }
      if (e.data === 'activity' && typeof window.pbApplyActivity === 'function') {
        try { window.pbApplyActivity(); } catch (err) { /* the progress item is a convenience */ }
      }
    };
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
PREVIEW_API = {"meta": "/api/meta", "data": "/__pb_data"}


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
WILDCARD_HOSTS = ("", "0.0.0.0", "::", "[::]")           # a --host that binds every interface names no Host of its own
LOOPBACK_BINDS = ("127.0.0.1", "localhost", "::1", "[::1]")
_HOST_HEADER = re.compile(r"^(\[[0-9a-f:.]+\]|[^\s:/@\[\]]+)(?::[0-9]{0,5})?$")
_ALLOW_NAME = re.compile(r"^(\[[0-9a-f:.]+\]|[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?)$")
SECURITY_HEADERS = (("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                    ("X-Frame-Options", "SAMEORIGIN"), ("Cross-Origin-Resource-Policy", "same-origin"))
# A value that is a name or a link carries no control (Cc), format/invisible (Cf) or lone-surrogate
# (Cs) characters: they are how a line-break, a bidi override or a zero-width space gets into a
# registry field, a command line the read-only dialog prints, or a Figma library name — and a lone
# surrogate cannot even be written as UTF-8.
META_BAD_CATEGORIES = ("Cc", "Cf", "Cs")
META_LINK_WARNING = ("designSystem.designLink: not a figma.com/file/… or figma.com/design/… link — "
                     "kept as it was; hand-off and the Figma push will not use it")


def host_name(header):
    """The host a Host header names — lower-cased, the port dropped, an IPv6 literal kept in its brackets —
    or None when the header is not a plain `host[:port]`. The one reading of that header: the Host guard
    and the Host door of `_local_same_origin` both go through it."""
    m = _HOST_HEADER.match((header or "").strip().lower())
    return m.group(1) if m else None


def parse_allow_host(value):
    """`--allow-host NAME` → the lower-cased name a Host header will carry (an IPv6 literal bracketed).
    A name only: no port, no wildcard, no scheme or path — ArgumentTypeError otherwise."""
    name = (value or "").strip().lower()
    if name.count(":") >= 2 and not name.startswith("["):
        name = "[%s]" % name
    if not _ALLOW_NAME.match(name):
        raise argparse.ArgumentTypeError(
            "%r is not a host name — give the bare name, with no port, scheme, path or wildcard (e.g. my-mac.local)" % value)
    return name


def allowed_hosts(bind_host, extra=()):
    """The Host names this server answers to: the loopback ones, the concrete address it is bound to (not
    a wildcard bind, which names nothing), and each --allow-host."""
    names = set(LOOPBACK_HOSTS) | set(extra)
    bound = (bind_host or "").strip().lower()
    if bound not in WILDCARD_HOSTS:
        names.add("[%s]" % bound if ":" in bound and not bound.startswith("[") else bound)
    return frozenset(names)


def host_warning(bind_host, hosts):
    """The startup line for a --host that reaches beyond this machine, else None."""
    if bind_host in LOOPBACK_BINDS:
        return None
    return ("  ⚠ host    --host %s reaches beyond this machine. Requests are answered only for Host %s; "
            "another device or a tunnel's name needs --allow-host NAME. Saves (POST) stay loopback-only."
            % (bind_host or "''", ", ".join(sorted(hosts))))


def stable_port(reg_path):
    """The port a project gets when --port is not given: PORT_BASE + a hash of its registry's real path,
    so a project keeps its URL across restarts and two projects rarely want the same one."""
    digest = hashlib.sha256(os.fsencode(os.path.realpath(reg_path))).hexdigest()
    return PORT_BASE + int(digest, 16) % PORT_SPAN


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


# ── /pb:research — the parts of the session routes that are not a Handler method ──────────────────
RESEARCH_QUERY_MAX = 256           # a research page's query string is a pseudonym and two flags
RESEARCH_CHUNK = 1 << 20           # an upload is read, and an evidence file streamed, in pieces this size
RESEARCH_CHUNK_TIMEOUT = 30.0      # seconds one 1 MiB piece of an upload has to arrive in (about 35 KB/s)
RESEARCH_SEND_TIMEOUT = 60.0       # seconds one write of an evidence stream may wait on a reader that stopped reading
RESEARCH_REPORT_MAX = 32 * 1024 * 1024
RESEARCH_HASHED_MAX = 32
_RANGE_SPAN = re.compile(r"bytes=([0-9]{1,15})-([0-9]{0,15})")
_RANGE_TAIL = re.compile(r"bytes=-([0-9]{1,15})")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_EVIDENCE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")   # a plain file name: no separator, no leading dot
# Files already hashed in full: (device, inode, size, mtime_ns, sha256). Evidence is read-only, so a
# <video> seeking through a 1 GB recording (one Range request per seek) hashes it once, not once per seek.
_hashed = {}
_hashed_lock = threading.Lock()


class ResearchRequestError(MetaError):
    """A research request refused before it reaches the store: .status and the message the page shows."""


def research_mods():
    """(research_session, research), imported on first use so a preview that never serves a study loads
    neither. `research` is the module research_session raises its ResearchError from — one import by name,
    one class — so `except research.ResearchError` here catches what the store raised."""
    return importlib.import_module("research_session"), importlib.import_module("research")


def research_note_page(title, detail, hint=""):
    """A small page for a research route that cannot show what was asked for. Unlike error_page it carries no
    live-reload client (a participant's page never reloads, and an open stream would hold the idle exit off)
    and does not tell the reader to fix registry.json."""
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>" + _esc(title) + "</title><style>"
            ":root{color-scheme:light dark}body{margin:0;font:15px/1.6 ui-sans-serif,system-ui,sans-serif}"
            ".wrap{max-width:560px;margin:12vh auto;padding:0 24px}h1{font-size:18px;margin:0 0 8px}"
            "p{margin:0 0 12px;opacity:.8}code{font:13px ui-monospace,Menlo,monospace}"
            "</style></head><body><div class=\"wrap\"><h1>" + _esc(title) + "</h1><p>" + _esc(detail) + "</p>"
            + ("<p><code>" + _esc(hint) + "</code></p>" if hint else "") + "</div></body></html>")


def research_query(rs, qs):
    """The query string of a session or observer link → {"participant", "pilot"}, or ValueError with the
    sentence the page shows. `p` is a pseudonym like P01, `pilot` is 0 or 1, `mode` is moderated or
    unmoderated; each at most once. `mode` is checked but not applied: research_session.build_page has no
    mode argument yet (the page takes it from the instrument). Unknown keys are ignored."""
    if len(qs) > RESEARCH_QUERY_MAX:
        raise ValueError("this link is too long")
    try:
        q = urllib.parse.parse_qs(qs, keep_blank_values=True, max_num_fields=8)
    except ValueError:
        raise ValueError("this link's query string cannot be read")
    for k in ("p", "pilot", "mode"):
        if k in q and len(q[k]) != 1:
            raise ValueError("%s is given more than once" % k)
    out = {"participant": None, "pilot": False}
    if "p" in q:
        if not rs.PARTICIPANT_ID.match(q["p"][0]):
            raise ValueError("p must be a pseudonym like P01")
        out["participant"] = q["p"][0]
    if "pilot" in q:
        if q["pilot"][0] not in ("0", "1"):
            raise ValueError("pilot must be 0 or 1")
        out["pilot"] = q["pilot"][0] == "1"
    if "mode" in q and q["mode"][0] not in rs.MODES:
        raise ValueError("mode must be one of %s" % ", ".join(rs.MODES))
    return out


def parse_range(value, size):
    """A `Range` header against a file of `size` bytes → (first, last) inclusive; "unsatisfiable" (answer 416);
    or None — no usable range, send the whole file. Only one range of the `bytes` unit is answered:
    `a-b`, `a-` and `-n`. Several ranges, another unit and a range that ends before it starts (RFC 9110: not
    a range at all) are ignored, which is the answer the RFC gives them. Matched with fullmatch against a
    bounded pattern, so a long or odd header costs nothing."""
    v = (value or "").strip()
    if not v or len(v) > 64:
        return None
    m = _RANGE_SPAN.fullmatch(v)
    if m:
        first = int(m.group(1))
        last = int(m.group(2)) if m.group(2) else None
        if last is not None and last < first:
            return None
        if first >= size:
            return "unsatisfiable"
        return (first, size - 1 if last is None else min(last, size - 1))
    m = _RANGE_TAIL.fullmatch(v)
    if m:
        n = int(m.group(1))
        if n == 0 or size == 0:
            return "unsatisfiable"
        return (max(0, size - n), size - 1)
    return None


def _sha256_of_fd(fd):
    h = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    while True:
        b = os.read(fd, RESEARCH_CHUNK)
        if not b:
            return h.hexdigest()
        h.update(b)


def open_research_file(base, rel_dir, name, sha256=None):
    """(status, fd, size) for the plain file `name` in the folder base/rel_dir (rel_dir like
    memory/research/<id>/evidence). status: ok | missing | unsafe | mismatch. The one path guard: the real path
    of the file must lie inside where that folder is MEANT to be — the real path of `base` plus rel_dir, not
    the real path of the folder itself, which would follow a symlinked evidence/ folder to wherever it points
    and approve what is there. Checked right before the open; the open itself refuses a symlink and anything
    but a regular file. With `sha256` the file is hashed in 1 MiB reads first (never loaded whole: a recording
    can be a gigabyte) and served only if it still matches what the registry recorded. On "ok" the caller
    owns the descriptor."""
    root = os.path.join(os.path.realpath(base), *rel_dir.split("/"))
    path = os.path.join(root, name)
    real = os.path.realpath(path)
    if not real.startswith(root + os.sep) or os.path.islink(path):    # a symlink in the file's own place is refused too
        return "unsafe", None, 0
    try:
        fd = os.open(real, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return "missing", None, 0
    except OSError:
        return "unsafe", None, 0
    ok = False
    try:
        info = os.fstat(fd)
        if not _stat.S_ISREG(info.st_mode):
            return "unsafe", None, 0
        if sha256 is not None:
            key = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, sha256)
            with _hashed_lock:
                known = key in _hashed
            if not known:
                if _sha256_of_fd(fd) != sha256:
                    return "mismatch", None, 0
                with _hashed_lock:
                    if len(_hashed) >= RESEARCH_HASHED_MAX:
                        _hashed.clear()
                    _hashed[key] = True
        ok = True
        return "ok", fd, info.st_size
    except OSError:
        return "unsafe", None, 0
    finally:
        if not ok:
            os.close(fd)


def research_failure(R, e):
    """(status, message) for what the store raised. A held registry lock reaches us as a ResearchError
    (research.locked re-raises RegistryLocked as one, with the original as __context__), so look there too:
    a busy registry is a 503, a lock file that is not a regular file a 500, a duplicate a 409, a study that
    does not exist a 404, any other refusal a 400."""
    lock = e if isinstance(e, pbslice.RegistryLocked) else e.__context__
    if isinstance(lock, pbslice.RegistryLocked):
        return (500 if isinstance(lock, pbslice.LockFileUnsafe) else 503), str(lock)
    if (getattr(e, "data", None) or {}).get("duplicate"):
        return 409, str(e)
    return (404 if getattr(e, "code", None) == R.EXIT_USAGE else 400), str(e)


class State:
    """Shared between the watcher thread and the request handler threads."""

    def __init__(self, reg_path, shell_path, out_path, write, ds_shell_path=None, runtime_path=None,
                 explore_shell_path=None, idle_exit_min=IDLE_EXIT_MIN, debounce_ms=DEBOUNCE_MS):
        self.reg_path = reg_path
        self.shell_path = shell_path
        # — the live-fill files (v2.6): both live in .preview/, beside server.json, and are runtime state —
        self.drafts_path = os.path.join(os.path.dirname(reg_path), DRAFTS_FILE)   # slice.py set --draft writes it
        self.hook_path = os.path.join(os.path.dirname(reg_path), HOOK_FILE)       # the plugin hook writes it
        self.tools_path = os.path.join(os.path.dirname(reg_path), TOOLS_FILE)     # …and this one, same hook
        self.kinds = []                       # [(version, "update" | "reload")], newest last: what each bump was
        self.hook_version = 0                 # bumps when only the hook's file changed — nothing to re-render
        self._cache_data_version = -1
        self._cache_data = None
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
        # — resource hygiene: who is looking, and what changed on disk since anyone last looked —
        self.idle_exit_s = max(0.0, float(idle_exit_min)) * 60.0   # 0 = never exit on idle
        self.debounce_s = max(0, debounce_ms) / 1000.0              # 0 = bump on the first change seen
        self.started_at = explore._now()
        self.last_activity = time.monotonic()  # the last request that was not a health probe
        self.sse_clients = 0                   # open /__pb_events streams
        self._act_lock = threading.Lock()
        self.wake = threading.Event()          # a tab connected: stop sleeping on the slow poll
        self.check_lock = threading.Lock()     # one change check at a time: one bump per change
        self.seen = None                       # {watched path: mtime} as of the last check
        self.exit_reason = None
        self.on_idle = None                    # set by main(): how to stop serve_forever from another thread

    def touch(self):
        self.last_activity = time.monotonic()

    def client_open(self):
        with self._act_lock:
            self.sse_clients += 1
            self.last_activity = time.monotonic()
        self.wake.set()

    def client_close(self):
        with self._act_lock:
            self.sse_clients -= 1
            self.last_activity = time.monotonic()

    def idle_seconds(self):
        return max(0.0, time.monotonic() - self.last_activity)

    def poll_interval(self):
        """0.3 s while a tab is connected or someone asked for something lately, else 2 s."""
        if self.sse_clients > 0 or self.idle_seconds() < WARM_SECONDS:
            return FAST_POLL
        return SLOW_POLL

    def idle_remaining(self):
        """Seconds until the idle exit fires, or None when it cannot (disabled, or a tab is open)."""
        if self.idle_exit_s <= 0 or self.sse_clients > 0:
            return None
        return self.idle_exit_s - self.idle_seconds()

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
    def sidecar_files(self):
        """The handoff sidecars render.py inlines: spec/**/*.json (specSrc, load_specs) and logic/**/*.json
        (logicSrc, load_contracts). Compiled into the page, so a change to one is a reload."""
        out = []
        for sub in ("spec", "logic"):
            root = os.path.join(self.base_dir, sub)
            out += glob.glob(os.path.join(glob.escape(root), "**", "*.json"), recursive=True)
        return sorted(out)

    @property
    def watched(self):
        # body_files / runtime_files / sidecar_files are recomputed each poll so newly added/removed files are noticed.
        extra = [p for p in (self.ds_shell_path, self.runtime_path, self.explore_shell_path) if p]
        return ([self.reg_path, self.shell_path, self.render_path, self.drafts_path, self.hook_path, self.tools_path] + extra
                + self.body_files + self.runtime_files + self.sidecar_files)

    def bump(self, kind="reload"):
        """A watched file changed. `kind` is what the browsers are told: "update" when only data the page can
        take in place changed (registry.json, the drafts), "reload" for anything compiled into the page."""
        with self.cond:
            self.version += 1
            self.kinds.append((self.version, kind))
            del self.kinds[:-KIND_HISTORY]
            self.cond.notify_all()
        self.prune_slot_cache()

    def bump_hook(self):
        """The plugin hook wrote .preview/activity.json or agents.json: tell the pages, render nothing."""
        with self.cond:
            self.hook_version += 1
            self.cond.notify_all()

    def message_since(self, last):
        """What a stream that has seen version `last` must be told now: "update" when every bump since was a
        data-only one, else "reload" — also when the history cannot vouch for a bump (it only keeps the latest)."""
        newer = [k for v, k in self.kinds if v > last]
        if len(newer) < self.version - last or "reload" in newer:
            return "reload"
        return "update"

    def prune_slot_cache(self):
        """Forget the rendered options of an exploration that is no longer open (promoted, rejected)."""
        try:
            open_targets = {s["target"] for s in explore.sessions(self.base_dir)}
        except Exception:
            return
        with self._cache_lock:
            for key in [k for k in self._slot_cache if k[0] not in open_targets]:
                del self._slot_cache[key]


def trim_server_log(base_dir):
    """On start, keep only the last LOG_KEEP bytes of .preview/server.log when it is over LOG_MAX → bytes dropped.
    Uses clean.py's in-place trim (the same limits): this process, or the one that spawned it, holds the
    file open for append, and an atomic replace would leave it writing to an unlinked file."""
    try:
        import clean
        path = os.path.join(base_dir, explore.SERVER_LOG)
        if not os.path.isfile(path):
            return 0
        dropped, _err = clean._trim_log(path, os.path.realpath(base_dir))
        return dropped
    except Exception:
        return 0


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


def read_hook(state):
    """What the plugin hook last wrote to .preview/activity.json — {state: "working"|"idle", at: <epoch s>, since?, gate?} —
    or None when there is none, it is unreadable or it is not that shape. A bad file is no activity, never an error.
    `since` (when the turn began) is passed on only when it is a number no later than `at`; otherwise it is left out.
    `gate` (the human gate a command stopped at) is passed on only when `hook_gate` finds it well formed."""
    try:
        with open(state.hook_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("state") not in ("working", "idle"):
        return None
    at = d.get("at")
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    out = {"state": d["state"], "at": at}
    since = d.get("since")
    if isinstance(since, (int, float)) and not isinstance(since, bool) and since <= at:
        out["since"] = since
    gate = hook_gate(d.get("gate"))
    if gate:
        out["gate"] = gate
    return out


HOOK_GATE_ID = re.compile(r"^G-[A-Z][A-Z0-9-]*$")


def hook_gate(g):
    """The gate a command stopped at — {id: "G-JTBD", ask: "approve 4 jobs and 3 terms", at: <epoch s>} — only when
    it is well formed (an id shaped G-…, a non-empty one-line ask of at most 160 characters, a number); else None."""
    if not isinstance(g, dict):
        return None
    gid, ask, at = g.get("id"), g.get("ask"), g.get("at")
    if not isinstance(gid, str) or not HOOK_GATE_ID.match(gid):
        return None
    if not isinstance(ask, str) or not ask.strip() or len(ask) > 160 or "\n" in ask or "\r" in ask:
        return None
    if isinstance(at, bool) or not isinstance(at, (int, float)):
        return None
    return {"id": gid, "ask": ask.strip(), "at": at}


def _tools_num(v, kind):
    """A non-negative number from agents.json (`kind` int or float), else None. bool, str, NaN and inf are refused."""
    if isinstance(v, bool):
        return None
    if kind == "int":
        return v if isinstance(v, int) and v >= 0 else None
    return v if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 else None


def read_tools(state, now=None):
    """What the plugin hook last wrote to .preview/agents.json, boiled down for the activity strip →
    {agents, verb, running, at, doneAt}, or None when the file is missing, unreadable, malformed or has no fresh
    session. `agents` sums the subagents of every session touched in the last TOOLS_FRESH_S seconds. verb / running /
    at / doneAt come from one of them: the freshest with a tool running, else the one that finished a tool last, else
    blanks. A session record with a bad number is skipped; a bad verb (not a string, over 20 characters, a control
    character) is read as ''. A bad file is no tools, never an error."""
    now = time.time() if now is None else now
    try:
        with open(state.tools_path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    sessions = d.get("sessions") if isinstance(d, dict) else None
    if not isinstance(sessions, dict):
        return None
    fresh = []
    for rec in sessions.values():
        if not isinstance(rec, dict):
            continue
        at, running = _tools_num(rec.get("at"), "num"), _tools_num(rec.get("running"), "int")
        agents, done = _tools_num(rec.get("agents"), "int"), _tools_num(rec.get("doneAt"), "num")
        if at is None or running is None or agents is None or done is None or not now - at < TOOLS_FRESH_S:
            continue
        verb = rec.get("verb")
        if not isinstance(verb, str) or len(verb) > TOOLS_VERB_MAX or not verb.isprintable():
            verb = ""
        fresh.append({"at": at, "verb": verb, "running": running, "doneAt": done, "agents": agents})
    if not fresh:
        return None
    running = [r for r in fresh if r["running"] > 0]
    finished = [r for r in fresh if r["doneAt"] > 0]
    if running:
        pick = max(running, key=lambda r: r["at"])
    elif finished:
        pick = max(finished, key=lambda r: r["doneAt"])
    else:
        pick = {"verb": "", "running": 0, "at": 0, "doneAt": 0}
    return {"agents": sum(r["agents"] for r in fresh), "verb": pick["verb"], "running": pick["running"],
            "at": pick["at"], "doneAt": pick["doneAt"]}


def data_current(state):
    """What a live page needs to repaint without a reload → (payload dict, error_str). The registry exactly as the
    render inlines it (specs loaded, bodies and styles left out), with the drafts folded in — each draft element
    marked `_draft: true`, nothing written anywhere — and the derived logic graph over that same merged registry.
    Cached per version, like the page; the hook's activity is read fresh on every request (it is tiny and has no version)."""
    with state._cache_lock:
        if state._cache_data_version == state.version and state._cache_data is not None:
            data, err = state._cache_data, None
        else:
            data, err = None, None
    if data is None:
        try:
            with open(state.reg_path, encoding="utf-8") as f:
                reg = json.load(f)
            reg = render.load_specs(reg, state.base_dir)
            drafts = pbslice.load_drafts(state.drafts_path)
            merged = pbslice.overlay_drafts(reg, drafts)
            logic = render.load_logic(state.base_dir, merged)   # fails open; the cached derived half is reused
            data = {"registry": render._strip_render(merged),
                    "logic": render._logic_for_shell(logic) if logic else None,
                    "drafts": pbslice.draft_summary(drafts), "version": state.version}
        except FileNotFoundError as e:
            err = "File not found: %s" % e
        except json.JSONDecodeError as e:
            err = "%s is not valid JSON — line %d, column %d: %s" % (
                os.path.basename(state.reg_path), e.lineno, e.colno, e.msg)
        except render.RenderError as e:
            err = "Render error: %s" % e
        except Exception:
            err = traceback.format_exc()
        if data is not None:
            with state._cache_lock:
                state._cache_data_version = state.version
                state._cache_data = data
    if data is None:
        return None, err
    now = time.time()
    activity = read_hook(state)
    if activity is not None:        # the tools ride on a valid activity file only
        tools = read_tools(state, now)
        if tools:
            activity["tools"] = tools
    return dict(data, activity=activity, now=now), None


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


def _snapshot(state):
    return {p: _mtime(p) for p in state.watched}


def refresh(state):
    """The change check — what the watcher does each tick and what a page request does before it
    renders, so a page is never built from files older than what is on disk even while the watcher
    sleeps on its slow poll. One check at a time under check_lock: two threads never both bump the
    version for the same change, and a request that arrives mid-check waits for the re-render and
    then gets it from the cache. Returns the changed paths ([] when nothing changed)."""
    with state.check_lock:
        now = _snapshot(state)
        if state.seen is None:
            state.seen = now
            return []
        changed = [p for p in now if now[p] != state.seen.get(p)]
        if not changed:
            return []
        for p in changed:
            state.seen[p] = now[p]
        rest = [p for p in changed if p not in (state.hook_path, state.tools_path)]
        if len(rest) < len(changed):      # the plugin hook wrote one of its files: the pages hear of it, nothing re-renders
            state.bump_hook()
        if not rest:
            return changed
        # Only registry.json and the drafts are data a page can take in place; a body, the shell, the
        # runtime or a stylesheet is compiled into it, so those still reload.
        soft = (state.reg_path, state.drafts_path)
        kind = "update" if all(p in soft for p in rest) else "reload"
        state.bump(kind)
        _html, err = render_current(state)
        what = ", ".join(os.path.basename(p) for p in rest)
        if err:
            log("✗ %s changed — render error (preview shows it; auto-recovers on save)" % what)
        else:
            log("✓ %s changed — re-rendered, %s browsers" % (what, "updating" if kind == "update" else "reloading"))
        return changed


def _settle(state):
    """After a change is seen, wait for the burst to end: return once no watched file has changed for
    debounce_s, or DEBOUNCE_CAP after the first change, whichever comes first. A single save costs
    one quiet window; ten saves 30 ms apart cost one reload."""
    t0 = quiet_since = time.monotonic()
    prev = _snapshot(state)
    while not state.stop.is_set():
        now = time.monotonic()
        if now - quiet_since >= state.debounce_s or now - t0 >= DEBOUNCE_CAP:
            return
        state.stop.wait(DEBOUNCE_STEP)
        cur = _snapshot(state)
        if cur != prev:
            prev, quiet_since = cur, time.monotonic()


def _stop_idle(state):
    minutes = state.idle_exit_s / 60.0
    log("idle for %s min — stopping (explore.py link or /pb:preview starts it again)" % ("%g" % round(minutes, 2)))
    state.exit_reason = "idle"
    if state.on_idle:
        state.on_idle()        # httpd.shutdown(): serve_forever returns and main()'s finally runs, as for SIGTERM
    state.stop.set()


def watcher(state):
    """Poll watched-file mtimes; on a change coalesce the burst, bump the version once and eagerly
    re-render (to log). Also where the idle exit is decided: it runs on this thread, never on the
    serve_forever one, so shutting the server down from here cannot deadlock."""
    refresh(state)  # primes state.seen when main() has not
    while not state.stop.is_set():
        timeout = state.poll_interval()
        left = state.idle_remaining()
        if left is not None:
            timeout = min(timeout, max(0.05, left))
        if state.wake.wait(timeout):
            state.wake.clear()
        if state.stop.is_set():
            return
        left = state.idle_remaining()
        if left is not None and left <= 0:
            return _stop_idle(state)
        if state.seen is not None and any(_mtime(p) != state.seen.get(p) for p in state.watched):
            if state.debounce_s > 0:
                _settle(state)
            refresh(state)


class Handler(BaseHTTPRequestHandler):
    state = None              # set on the class before the server starts
    hosts = frozenset(LOOPBACK_HOSTS)   # the Host names this server answers to; main() adds --host and --allow-host
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):  # silence per-request noise; the watcher logs what matters
        pass

    def _security_headers(self):
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)

    def _refuse_host(self):
        """The Host guard, first thing in every do_*: True once it has answered 403 because the Host header
        does not name this server. Browsers send the name the address bar holds, so a page on another
        site that resolves its own name to 127.0.0.1 (DNS rebinding) arrives with a name that is not
        ours and reads nothing. A request with no Host is a hand-made one: accepted from this machine,
        refused from any other. Runs before state.touch(): a refused request is not use."""
        hosts = self.headers.get_all("Host") or []
        if not hosts:
            if self.client_address[0] in LOOPBACK_ADDRS:
                return False
            msg = ("pb-preview: refused a request with no Host header. To preview from another device or "
                   "through a tunnel, start the server with --allow-host <name>.")
        elif len(hosts) > 1:      # which one a proxy or a browser would believe is not ours to guess
            msg = "pb-preview: refused a request with more than one Host header."
        else:
            name = host_name(hosts[0])
            if name in self.hosts:
                return False
            # echoed back, so: printable ASCII only (no CR/LF, no escape sequences), and short
            shown = re.sub(r"[^A-Za-z0-9._:\[\]-]", "?", name or hosts[0])[:80]
            msg = ("pb-preview: refused unknown Host %s. To preview from another device or through a tunnel, "
                   "start the server with --allow-host %s." % (shown, shown))
        if self.command == "POST":    # every POST route is a JSON API whose page reads {ok, error}: give it the sentence in that shape
            self._json({"ok": False, "error": msg}, status=403, close=True)
        else:
            self._send(msg.encode("utf-8"), ctype="text/plain; charset=utf-8", status=403, close=True)
        return True

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
        self._security_headers()
        if close:
            # A request body we did not read is still in the socket; on a kept-alive connection
            # its bytes would be parsed as the next request. Say so and hang up.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self._write(body)

    def do_GET(self):
        if self._refuse_host():   # every route, the health probe and the event stream included
            return
        path = self.path.split("?", 1)[0]
        if path != "/__pb_health":   # a health probe (--status, explore.py link) is not use: it must not keep the server alive
            self.state.touch()
        if path == "/__pb_events":
            return self.serve_events()
        if path == "/__pb_health":   # names a local path, so this machine only (--host may bind wider)
            if self.client_address[0] not in LOOPBACK_ADDRS:
                return self._send(b"404 not found", ctype="text/plain", status=404)
            st = self.state
            return self._json({"ok": True, "app": "pb-preview", "registry": st.reg_path,
                               "pid": os.getpid(), "version": render.plugin_version(),
                               "clients": st.sse_clients, "idleSeconds": int(st.idle_seconds()),
                               "startedAt": st.started_at})
        is_page = (path in ("/", "/index.html", "/design-system", "/design-system/", "/design-system.html", "/__pb_data")
                   or path == "/explore" or path.startswith("/explore/") or path.startswith("/research/"))
        if is_page:
            refresh(self.state)   # the watcher may be on its slow poll: look at the disk now, never render stale
        if path.startswith("/research/") or path.startswith("/__pb_research/"):
            return self.serve_research(path)   # /pb:research — loopback peers only, no live-reload client in what it sends
        if path == "/__pb_data":
            return self.serve_data()
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

    def serve_data(self):
        """GET /__pb_data — the registry (and logic graph, drafts folded in, activity) a page repaints from when
        the SSE stream says `update`. Same door as the page it belongs to: the Host guard already ran, and the
        answer carries nothing the page does not already hold inlined. A registry that will not parse is a 500
        with the sentence — the client then reloads, and the reload shows the error page, as it always did."""
        data, err = data_current(self.state)
        if data is None:
            return self._json({"ok": False, "error": err or "no data"}, status=500)
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send(body, ctype="application/json; charset=utf-8")

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
            self._security_headers()
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
        if self._refuse_host():   # …and before the body is read: the refusal closes the connection
            return
        self.state.touch()
        path = self.path.split("?", 1)[0]
        if path == "/api/meta":
            return self.post_meta()
        parts = [p for p in path.split("/") if p]
        if parts[:1] == ["__pb_research"]:
            return self.post_research(parts, self.path.partition("?")[2])
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
        if host_name(host) not in LOOPBACK_HOSTS:     # --allow-host never widens this: a write is for this machine
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

    # ── /pb:research — the session routes (module docstring; tools/research_session.py does the work) ──
    def _research_gate(self):
        """The door of every GET under /research/ and /__pb_research/, after the Host guard: True once it has
        answered 403 because the peer is not this machine or the Host names something other than a loopback
        host. A study's sessions and recordings are a person's data, so --host and --allow-host never widen
        this — a tunnel's proxy is a loopback peer but arrives with its own name. (The POSTs take the same two
        doors, and the Origin one, in _local_same_origin.)"""
        if self.client_address[0] in LOOPBACK_ADDRS and host_name(self.headers.get("Host")) in LOOPBACK_HOSTS:
            return False
        self._send(b"403 forbidden: a research page opens only on this machine, at 127.0.0.1 or localhost",
                   ctype="text/plain; charset=utf-8", status=403, close=True)
        return True

    def _research_missing(self):
        self._send(b"404 not found", ctype="text/plain; charset=utf-8", status=404)

    def serve_research(self, path):
        """GET /research/<id>/{session,observer,report} · /research/<id>/replay/<eid> · /__pb_research/<id>/evidence/<eid>.
        Every id is checked against its anchored pattern before anything is built from it; a path is never
        percent-decoded, so an escape is simply not an id."""
        if self._research_gate():
            return
        try:
            rs, R = research_mods()
        except Exception:
            log("the research tools could not be loaded:\n" + traceback.format_exc())
            return self._send(research_note_page("Research tools unavailable",
                                                 "research_session.py could not be loaded — see the preview server's output.").encode("utf-8"),
                              status=500)
        parts = [p for p in path.split("/") if p]
        if len(parts) < 3 or not R.STUDY_ID.match(parts[1]):
            return self._research_missing()
        sid, rest = parts[1], parts[2:]
        if parts[0] == "__pb_research":
            if len(rest) == 2 and rest[0] == "evidence":
                return self.research_evidence(rs, R, sid, rest[1])
            return self._research_missing()
        if len(rest) == 1 and rest[0] in ("session", "observer"):
            return self.research_page(rs, R, sid, rest[0])
        if len(rest) == 2 and rest[0] == "replay" and (rs.EVIDENCE_ID.match(rest[1]) or rs.PILOT_EID.match(rest[1])):
            return self.research_page(rs, R, sid, "replay", eid=rest[1])
        if len(rest) == 1 and rest[0] == "report":
            return self.research_report(R, sid)
        self._research_missing()

    def research_page(self, rs, R, sid, page, eid=None):
        """The participant page, the observer or a replay — research_session.build_page, sent as it is: no
        live-reload client and no window.PB_PREVIEW (a participant's page must never reload or live-fill)."""
        kw = {}
        if page != "replay":
            try:
                kw = research_query(rs, self.path.partition("?")[2])
            except ValueError as e:
                return self._send(research_note_page("Research · this link does not work", str(e)).encode("utf-8"), status=400)
        st = self.state
        try:
            html = rs.build_page(st.reg_path, sid, page, eid=eid, shell_path=st.shell_path, runtime_path=st.runtime_path, **kw)
        except R.ResearchError as e:    # not found → 404; a study not ready for this page (a draft, scope instrument…) → 409
            return self._send(research_note_page("Research · cannot open this page", str(e)).encode("utf-8"),
                              status=404 if (e.code == R.EXIT_USAGE or page == "replay") else 409)
        except Exception:
            log("research page %s/%s failed:\n%s" % (sid, page, traceback.format_exc()))
            return self._send(research_note_page("Research · the page could not be built",
                                                 "See the preview server's output.").encode("utf-8"), status=500)
        self._send(html.encode("utf-8"))

    def research_report(self, R, sid):
        """GET /research/<id>/report — memory/research/<id>/report/report.html, as the tool wrote it."""
        status, fd, size = open_research_file(R.base_of(self.state.reg_path), R.study_rel(sid) + "/report", "report.html")
        if status != "ok":
            return self._send(research_note_page("No report yet", "%s has no report to show. Write it with:" % sid,
                                                 "research.py report %s" % sid).encode("utf-8"), status=404)
        try:
            body = b"".join(iter(lambda: os.read(fd, RESEARCH_CHUNK), b"")) if size <= RESEARCH_REPORT_MAX else None
        finally:
            os.close(fd)
        if body is None:
            return self._send(research_note_page("The report is too large to show",
                                                 "%s's report.html is over %d MB." % (sid, RESEARCH_REPORT_MAX // (1024 * 1024))).encode("utf-8"),
                              status=413)
        self._send(body, ctype="text/html; charset=utf-8")

    def research_evidence(self, rs, R, sid, eid):
        """GET /__pb_research/<id>/evidence/<eid> — the bytes of one session or recording file (an evidence
        id like e3, or pilot-<sessionId> / pilot-<sessionId>-screen for a pilot), checked against the sha256
        the registry holds before a byte is sent, and streamed from one descriptor so a gigabyte recording is
        never read into memory. A single `Range` is answered 206 (416 when it starts past the end)."""
        st = self.state
        try:
            study = R.find_study(R.load_registry(st.reg_path), sid)
        except R.ResearchError:
            return self._research_missing()
        sha = None
        if rs.EVIDENCE_ID.match(eid):
            row = next((e for e in R.as_list(study.get("evidence")) if isinstance(e, dict) and e.get("id") == eid), None)
            if row is None or row.get("dropped") or row.get("kind") not in ("session", "recording"):
                return self._research_missing()
            prefix = R.evidence_dir_rel(sid) + "/"
            rel, sha = R.sstr(row.get("file")), R.sstr(row.get("sha256"))
            name = rel[len(prefix):] if rel.startswith(prefix) else ""
            if not _EVIDENCE_NAME.fullmatch(name) or not _HEX64.fullmatch(sha):
                return self._json({"ok": False, "error": "%s is not recorded as a plain file inside the evidence folder" % eid}, status=409)
            rel_dir = R.evidence_dir_rel(sid)
            ctype = "application/json; charset=utf-8" if row["kind"] == "session" else "video/webm"
        else:
            m = rs.PILOT_EID.match(eid)
            if not m:
                return self._research_missing()
            wanted, pilots = m.group(1), [p for p in R.as_list(study.get("pilots")) if isinstance(p, dict)]
            screen = wanted[:-len("-screen")] if wanted.endswith("-screen") else None
            if any(p.get("sessionId") == wanted for p in pilots):
                name, ctype = wanted + ".json", "application/json; charset=utf-8"
            elif screen and rs.SESSION_ID.match(screen) and any(
                    p.get("sessionId") == screen and "%s/pilot/%s-screen.webm" % (R.study_rel(sid), screen) in R.as_list(p.get("media"))
                    for p in pilots):
                name, ctype = screen + "-screen.webm", "video/webm"
            else:
                return self._research_missing()
            rel_dir = R.study_rel(sid) + "/pilot"
        status, fd, size = open_research_file(R.base_of(st.reg_path), rel_dir, name, sha)
        if status == "missing":
            return self._research_missing()
        if status != "ok":
            why = ("no longer matches its recorded sha256 — it was changed after import" if status == "mismatch"
                   else "is not a plain file inside its folder")
            return self._json({"ok": False, "error": "%s %s" % (eid, why)}, status=409)
        self.research_stream(fd, size, ctype)

    def _research_head(self, status, ctype, length, extra=()):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        for k, v in extra:
            self.send_header(k, v)
        self._security_headers()
        self.end_headers()

    def research_stream(self, fd, size, ctype):
        """Send the descriptor's bytes (all of them, or the one range asked for) in 1 MiB reads, then close it.
        A reader that stops reading is dropped after RESEARCH_SEND_TIMEOUT; a file that shrinks under us ends
        the connection, because the Content-Length it promised can no longer be kept."""
        try:
            ranges = self.headers.get_all("Range") or []
            span = parse_range(ranges[0], size) if len(ranges) == 1 else None
            if span == "unsatisfiable":
                return self._research_head(416, ctype, 0, [("Content-Range", "bytes */%d" % size)])
            first, last = span if span else (0, size - 1)
            length = last - first + 1
            self._research_head(206 if span else 200, ctype, length,
                                [("Content-Range", "bytes %d-%d/%d" % (first, last, size))] if span else [])
            try:
                self.connection.settimeout(RESEARCH_SEND_TIMEOUT)
                os.lseek(fd, first, os.SEEK_SET)
                left = length
                while left > 0:
                    b = os.read(fd, min(RESEARCH_CHUNK, left))
                    if not b or not self._write(b):
                        self.close_connection = True
                        break
                    left -= len(b)
            finally:
                try:
                    self.connection.settimeout(None)
                except OSError:
                    pass
        finally:
            os.close(fd)

    def _research_length(self, limit):
        """The Content-Length of a research upload, as a number: a plain number of bytes, once, over 0 and
        within `limit`. A body with no length (a chunked one included) is a 411 — the limit cannot be held
        to a size nobody declared. ResearchRequestError otherwise, with the sentence the page shows."""
        lengths = self.headers.get_all("Content-Length") or []
        if self.headers.get("Transfer-Encoding") is not None:
            raise ResearchRequestError("Transfer-Encoding and Content-Length together are not accepted" if lengths
                                       else "a chunked body is not accepted: send a Content-Length", 400 if lengths else 411)
        if len(lengths) > 1:
            raise ResearchRequestError("more than one Content-Length header", 400)
        raw = (lengths[0] if lengths else "").strip()
        if not raw:
            raise ResearchRequestError("Content-Length is required", 411)
        if not re.fullmatch(r"[0-9]{1,12}", raw):
            raise ResearchRequestError("Content-Length must be a plain number of bytes", 400)
        n = int(raw)
        if n <= 0:
            raise ResearchRequestError("payload missing", 400)
        if n > limit:
            raise ResearchRequestError("payload too large (limit %d MB)" % (limit // (1024 * 1024)), 400)
        return n

    def _research_read(self, n, sink):
        """Read exactly `n` body bytes, handing each piece to sink(bytes). Each 1 MiB of it has
        RESEARCH_CHUNK_TIMEOUT seconds in all to arrive, so neither a stalled client nor one trickling a byte
        at a time holds this thread; a client that stops short is a ResearchRequestError (400)."""
        got, window, deadline = 0, 0, time.monotonic() + RESEARCH_CHUNK_TIMEOUT
        try:
            while got < n:
                left = deadline - time.monotonic()
                b = b""
                if left > 0:
                    try:
                        self.connection.settimeout(left)
                        b = self.rfile.read1(min(65536, n - got))
                    except OSError:                   # socket.timeout is one
                        b = b""
                if not b:
                    raise ResearchRequestError("payload incomplete: Content-Length said %d bytes, %d arrived" % (n, got), 400)
                sink(b)
                got += len(b)
                window += len(b)
                if window >= RESEARCH_CHUNK:
                    window, deadline = 0, time.monotonic() + RESEARCH_CHUNK_TIMEOUT
        finally:
            try:
                self.connection.settimeout(None)
            except OSError:
                pass

    def _research_fail(self, e, R):
        """The JSON answer for whatever went wrong in a research POST — a message and a status, never a
        traceback. The connection is closed when the body was not read (its bytes would be parsed as the next request)."""
        close = not self._body_read
        if isinstance(e, ResearchRequestError):
            return self._json({"ok": False, "error": str(e)}, status=e.status, close=close)
        if R is not None and isinstance(e, (R.ResearchError, pbslice.RegistryLocked)):
            status, msg = research_failure(R, e)
            return self._json({"ok": False, "error": msg}, status=status, close=close)
        if isinstance(e, OSError):
            return self._json({"ok": False, "error": "could not store the upload (%s)" % (e.strerror or type(e).__name__)},
                              status=500, close=close)
        log("a research upload failed:\n" + traceback.format_exc())
        self._json({"ok": False, "error": "could not store the upload"}, status=500, close=close)

    def post_research(self, parts, query):
        """POST /__pb_research/<id>/session · /__pb_research/<id>/media?session=<sessionId>&kind=screen."""
        if len(parts) == 3 and parts[2] == "session":
            return self.post_research_session(parts[1])
        if len(parts) == 3 and parts[2] == "media":
            return self.post_research_media(parts[1], query)
        self._send(b"404 not found", ctype="text/plain", status=404, close=True)

    def post_research_session(self, sid):
        """The participant page's save: one pb-session JSON → research_session.store_session. The same three
        doors as /api/meta, then a body of at most SESSION_MAX_BYTES read in pieces. It is NOT parsed here —
        store_session parses it with its own depth and size guards — so what is checked here is only who
        is asking and how much they send."""
        self._body_read = False
        R = None
        try:
            why = self._local_same_origin()
            if why:
                return self._json({"ok": False, "error": why}, status=403, close=True)
            rs, R = research_mods()
            if not R.STUDY_ID.match(sid):
                raise ResearchRequestError("no such study", 404)
            n = self._research_length(rs.SESSION_MAX_BYTES)
            pieces = []
            self._research_read(n, pieces.append)
            self._body_read = True
            res = rs.store_session(self.state.reg_path, sid, b"".join(pieces), source="server")
        except Exception as e:
            return self._research_fail(e, R)
        self._json({"ok": True, "evidence": res["evidence"], "sessionId": res["sessionId"], "pilot": res["pilot"],
                    "warnings": res["warnings"]}, status=201)

    def _research_media_target(self, rs, R, sid, query):
        """The session id a recording upload is for, from `?session=<sessionId>&kind=screen`, after a cheap look
        at the registry: the study exists and that session is stored (an evidence row or a pilot). Refusing
        here — before a byte of a gigabyte is read and before any folder is made for a study that is not
        there — keeps a mistaken upload cheap; store_media still decides consent, size and format."""
        if len(query) > RESEARCH_QUERY_MAX:
            raise ResearchRequestError("this link is too long", 400)
        try:
            q = urllib.parse.parse_qs(query, keep_blank_values=True, max_num_fields=8)
        except ValueError:
            raise ResearchRequestError("the query string cannot be read", 400)
        session_id = (q.get("session") or [""])[0]
        if len(q.get("session") or []) != 1 or not rs.SESSION_ID.match(session_id):
            raise ResearchRequestError("session must be a session id like s-lq3k9-ab12", 400)
        if q.get("kind") != ["screen"]:
            raise ResearchRequestError("kind must be screen", 400)
        study = R.find_study(R.load_registry(self.state.reg_path), sid)
        if study.get("method") not in rs.SESSION_METHODS:
            raise R.ResearchError("%s is a %s study; it has no session recordings" % (sid, study.get("method")))
        stored = any(isinstance(e, dict) and e.get("kind") == "session" and R.as_dict(e.get("session")).get("id") == session_id
                     for e in R.as_list(study.get("evidence"))) \
            or any(isinstance(p, dict) and p.get("sessionId") == session_id for p in R.as_list(study.get("pilots")))
        if not stored:
            raise R.ResearchError("session %s is not stored in %s — store the session file first" % (session_id, sid))
        return session_id

    def post_research_media(self, sid, query):
        """The participant page's screen recording: the raw WebM body, written in 1 MiB pieces to a file made
        exclusively (O_EXCL, no symlink) in memory/research/<id>/.incoming/ — never held in memory — and then
        handed to store_media(move=True), which checks consent, hashes it and renames it into the evidence
        folder. The temp file is removed on every path that does not end in that rename."""
        self._body_read = False
        R, tmp = None, None
        try:
            why = self._local_same_origin()
            if why:
                return self._json({"ok": False, "error": why}, status=403, close=True)
            rs, R = research_mods()
            if not R.STUDY_ID.match(sid):
                raise ResearchRequestError("no such study", 404)
            session_id = self._research_media_target(rs, R, sid, query)
            n = self._research_length(rs.MEDIA_MAX_BYTES)
            incoming_rel = R.study_rel(sid) + "/.incoming"
            R.ensure_dir(R.base_of(self.state.reg_path), incoming_rel)      # made one segment at a time, refusing a symlink
            incoming = os.path.join(os.path.realpath(R.base_of(self.state.reg_path)), *incoming_rel.split("/"))
            tmp = os.path.realpath(os.path.join(incoming, "u-%s.webm" % os.urandom(8).hex()))
            if not tmp.startswith(incoming + os.sep):
                raise ResearchRequestError("the upload folder is not where it should be", 500)
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            magic, head = rs.WEBM_MAGIC, bytearray()
            with os.fdopen(fd, "wb") as out:
                def sink(b):
                    if len(head) < len(magic):      # refuse what is not a WebM on its first bytes, not after a gigabyte
                        head.extend(b[:len(magic) - len(head)])
                        if bytes(head) != magic[:len(head)]:
                            raise ResearchRequestError("the upload is not a WebM recording (no EBML header)", 400)
                    out.write(b)
                self._research_read(n, sink)
            self._body_read = True
            res = rs.store_media(self.state.reg_path, sid, session_id, tmp, mime="video/webm", move=True)
        except Exception as e:
            return self._research_fail(e, R)
        finally:
            if tmp:
                try:
                    os.unlink(tmp)       # gone already once store_media has renamed it
                except OSError:
                    pass
        self._json({"ok": True, "evidence": res["evidence"], "bytes": res["bytes"], "sha256": res["sha256"]}, status=201)

    def serve_ds(self):
        """The design-system site (component workbench) — the second projection of the registry."""
        html, err = render_ds_current(self.state)
        body = (error_page(err, self.state.reg_path) if err is not None
                else inject_reload(inject_preview_api(html))).encode("utf-8")
        self._send(body)

    def _client_gone(self):
        """True when the browser has closed its end of this stream (a tab closed, a laptop slept):
        the socket is readable and a peek says end-of-file. A write would only find out a ping later,
        and the idle exit counts open streams, so a vanished tab must not be believed for 15 s."""
        try:
            ready, _, _ = select.select([self.connection], [], [], 0)
            return bool(ready) and self.connection.recv(1, socket.MSG_PEEK) == b""
        except (OSError, ValueError):
            return True

    def serve_events(self):
        """One long-lived SSE stream per browser tab; emits `update` (registry/drafts only) or `reload` when the
        version bumps, and `activity` when only the hook's file changed. Counted in
        state.sse_clients for exactly as long as it is open — the decrement is in a `finally`, so a
        client that vanishes mid-write cannot leave the count (and with it the server) stuck."""
        st = self.state
        st.client_open()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")  # disable proxy buffering
            self._security_headers()
            self.end_headers()
            if not self._write(b": connected\n\n"):
                return
            last = st.version
            last_hook = st.hook_version
            pinged = time.monotonic()
            while not st.stop.is_set():
                with st.cond:
                    st.cond.wait_for(lambda: st.version != last or st.hook_version != last_hook or st.stop.is_set(),
                                     timeout=SSE_SLICE)
                if st.stop.is_set():
                    break
                if st.version != last:
                    msg = st.message_since(last)
                    last = st.version
                    last_hook = st.hook_version
                    ok = self._write(("data: %s\n\n" % msg).encode("ascii"))
                elif st.hook_version != last_hook:
                    last_hook = st.hook_version
                    ok = self._write(b"data: activity\n\n")
                elif self._client_gone():
                    break
                elif time.monotonic() - pinged >= SSE_PING:
                    pinged = time.monotonic()
                    ok = self._write(b": ping\n\n")  # heartbeat / dead-client detection
                else:
                    continue
                if not ok:
                    break
        except OSError:      # the headers could not be sent: the client was already gone
            pass
        finally:
            st.client_close()
            self.close_connection = True

    def _static_private(self, rel):
        """True for a path under the project that is not an asset and must never be served: anything with a
        dot-named part (.git, .env, .preview, .claude, .pb-backups), the memory/ folder (the spec, the
        decisions log, backups), and the registry itself with the lock and temp files beside it. Decided
        on `rel`, the path AFTER resolve() — so `..`, a symlink and a percent-escaped dot all end up
        judged by where they land — and casefolded, because the macOS filesystem is case-insensitive
        and `/MEMORY/x.md` is the same file as `/memory/x.md`."""
        parts = [p.casefold() for p in rel.parts]
        if any(p.startswith(".") for p in parts):
            return True
        if parts and parts[0] == "memory":
            return True
        reg = Path(self.state.reg_path)
        names = {"registry.json", reg.name.casefold(), reg.resolve().name.casefold()}   # registry.json, registry.json.lock, …
        return len(parts) == 1 and any(parts[0] == n or parts[0].startswith(n + ".") for n in names)

    def serve_static(self, path):
        """Fall back to files next to the registry (e.g. local assets a render references) — assets only."""
        root = Path(self.state.reg_path).resolve().parent
        try:
            # relative_to() raises ValueError on traversal; resolve() expands symlinks first
            rel = (root / path.lstrip("/")).resolve().relative_to(root)
        except ValueError:
            return self._send(b"403 forbidden", ctype="text/plain", status=403)
        if self._static_private(rel):    # whether or not it exists: a 404 would say which names are real
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
    try:
        os.rmdir(os.path.dirname(path))   # only when empty: a log or shots/ beside it keeps the folder
    except OSError:
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


def _loopback_url(url):
    """True for an http URL on this machine — the only kind a server record may send --status / --stop to."""
    try:
        u = urllib.parse.urlsplit(url)
        return u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
    except ValueError:
        return False


def server_status(reg_path):
    """What this registry's preview server says about itself → (state, info).

    state is "running" (info = its /__pb_health answer plus `url`), "none" (no record, or nothing answers
    at the recorded URL — a stale record), "other" (something answers there that is NOT this registry's
    server: another project's, or not a preview at all; info = {"url", "registry"}) or "mismatch" (it IS
    this registry's server but its pid is not the recorded one; info = {"url", "pid", "recorded"}).
    Only "running" is a server --stop may signal."""
    rec = explore.server_record(os.path.dirname(reg_path))
    if not rec or not _loopback_url(rec["url"]):
        return "none", {}
    base = rec["url"].rstrip("/")
    code, body = explore._get(base + "/__pb_health", timeout=3)
    if code is None:
        return "none", {}
    try:
        health = json.loads(body) if code == 200 else None
    except ValueError:
        health = None
    if not isinstance(health, dict) or health.get("app") != "pb-preview":
        return "other", {"url": base + "/", "registry": None}
    if not explore._ours(base, reg_path):
        return "other", {"url": base + "/", "registry": health.get("registry")}
    pid = health.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1 or rec.get("pid") != pid:
        return "mismatch", {"url": base + "/", "pid": pid, "recorded": rec.get("pid")}
    info = dict(health)
    info["url"] = base + "/"
    return "running", info


def _uptime_seconds(started_at):
    try:
        return max(0, int((datetime.datetime.now() - datetime.datetime.fromisoformat(started_at)).total_seconds()))
    except (TypeError, ValueError):
        return None


def _human_seconds(n):
    if n is None:
        return "unknown"
    h, rem = divmod(int(n), 3600)
    m, sec = divmod(rem, 60)
    return "%dh %02dm" % (h, m) if h else ("%dm %02ds" % (m, sec) if m else "%ds" % sec)


def cmd_status(reg_path, as_json):
    """`serve.py --status` — exit 0 when this registry's preview server is running, 1 when not."""
    st, info = server_status(reg_path)
    if st != "running":
        if as_json:
            print(json.dumps({"running": False, "registry": reg_path, "state": st}))
        elif st in ("other", "mismatch"):
            print("pb-serve · not running — %s" % _refusal(st, info))
        else:
            print("pb-serve · not running")
        return 1
    up = _uptime_seconds(info.get("startedAt"))
    if as_json:
        print(json.dumps({"running": True, "url": info["url"], "pid": info["pid"], "registry": info.get("registry"),
                          "startedAt": info.get("startedAt"), "uptimeSeconds": up,
                          "clients": info.get("clients"), "idleSeconds": info.get("idleSeconds")}))
    else:
        print("pb-serve · running")
        print("  url       %s" % info["url"])
        print("  pid       %s" % info["pid"])
        print("  uptime    %s" % _human_seconds(up))
        print("  clients   %s" % info.get("clients"))
        print("  idle      %ss" % info.get("idleSeconds"))
    return 0


def _refusal(st, info):
    if st == "other":
        who = info.get("registry")
        return "%s answers as %s, not this registry's server — left alone" % (
            info["url"], "another registry (%s)" % who if who else "something else")
    return "%s is this registry's server but its pid (%s) is not the recorded one (%s) — left alone" % (
        info["url"], info.get("pid"), info.get("recorded"))


def cmd_stop(reg_path, as_json):
    """`serve.py --stop` — SIGTERM the recorded pid, but only once the health check at the recorded URL has
    answered as THIS registry's server AND named that same pid; then wait up to STOP_WAIT seconds for it to
    go. Exit 0: stopped, or it was not running (a record that names another server is "not running" for
    this registry, and that server is never touched). Exit 1: it is this registry's server and it would
    not stop, or its pid could not be confirmed."""
    st, info = server_status(reg_path)

    def done(code, stopped, msg, **extra):
        if as_json:
            out = {"stopped": stopped, "state": st}
            out.update(extra)
            print(json.dumps(out))
        else:
            print("pb-serve · " + msg)
        return code

    if st == "none":
        return done(0, False, "not running")
    if st == "other":
        return done(0, False, "not running — " + _refusal(st, info), refused=True)
    if st == "mismatch":
        return done(1, False, "not stopped — " + _refusal(st, info), refused=True)
    pid, url = info["pid"], info["url"]
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return done(0, True, "stopped (pid %d was already gone)" % pid, pid=pid)
    except OSError as e:
        return done(1, False, "not stopped — could not signal pid %d (%s)" % (pid, e), pid=pid)
    deadline = time.monotonic() + STOP_WAIT
    while time.monotonic() < deadline:
        # gone = nothing answers at the URL as that pid. (A zombie child still has a pid; its socket is closed.)
        code, body = explore._get(url.rstrip("/") + "/__pb_health", timeout=1)
        try:
            alive = code == 200 and json.loads(body).get("pid") == pid
        except (ValueError, AttributeError):
            alive = False
        if not alive:
            return done(0, True, "stopped pid %d (%s)" % (pid, url), pid=pid)
        time.sleep(0.1)
    return done(1, False, "not stopped — pid %d still answers at %s after %gs" % (pid, url, STOP_WAIT), pid=pid)


def cmd_ensure(reg_path, as_json, extra_args):
    """`serve.py --ensure` — this registry's preview URL, whether or not a server was running: print it and
    start nothing when one is, else start one (detached, managed) through explore.py's find-or-start and
    print that. `extra_args` are the serve.py flags the caller gave (--shell, --port, …), handed on
    as they were. Exit 0, or 3 when no server could be started."""
    st, info = server_status(reg_path)
    started = False
    if st in ("running", "mismatch"):    # "mismatch" is still THIS registry's server: a second would be a duplicate
        url, pid = info["url"], info["pid"]
    else:
        try:
            rec = explore._start_server(reg_path, extra_args=extra_args, managed=True)
        except (explore.ExploreError, OSError) as e:
            if as_json:
                print(json.dumps({"error": str(e)}))
            print("pb-serve: " + str(e), file=sys.stderr)
            return 3
        url, pid, started = rec["url"], rec["pid"], True
    if as_json:
        print(json.dumps({"url": url, "pid": pid, "started": started}))
    else:
        print("pb-serve · %s %s (pid %s)" % ("started" if started else "running at", url, pid))
    return 0


# ── managed previews — the ones --ensure and explore.py link start, kept to a few ─────────────────
# Each server uses 2–6 MB, so what costs people is a preview that is gone when they come back, not one
# more running. But a user who works on many projects ends up with dozens; six is room for the day.
# A managed server records itself in a per-user folder; starting a seventh stops the longest-idle one
# nobody is looking at. Everything here FAILS OPEN: a folder that cannot be used, a peer that does not
# answer — the new server starts regardless.

def preview_dir():
    """The folder managed servers record themselves in: $PB_PREVIEW_DIR, else pb-previews-<uid> under the
    temp dir (0700, the same check browser.py's slot folder gets). Created here."""
    d = os.environ.get("PB_PREVIEW_DIR", "").strip() or os.path.join(
        tempfile.gettempdir(), "pb-previews-%d" % os.getuid())
    pbbrowser._ensure_dir(d)
    return d


def preview_max():
    """PB_PREVIEW_MAX, else PREVIEW_MAX. 0 = no cap; anything that is not a whole number >= 0 is ignored."""
    raw = os.environ.get("PB_PREVIEW_MAX", "").strip()
    try:
        n = int(raw) if raw else PREVIEW_MAX
    except ValueError:
        return PREVIEW_MAX
    return n if n >= 0 else PREVIEW_MAX


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:      # EPERM: it exists, it is somebody else's
        return True
    return True


def _peer_health(rec):
    """(health, answered) for a managed record: `health` is its /__pb_health when that names a pb-preview with
    the recorded pid, else None; `answered` is whether anything at all replied. Loopback URLs only."""
    if not _loopback_url(rec["url"]):
        return None, True
    code, body = explore._get(rec["url"].rstrip("/") + "/__pb_health", timeout=HEALTH_TIMEOUT)
    try:
        health = json.loads(body) if code == 200 else None
    except ValueError:
        health = None
    ok = isinstance(health, dict) and health.get("app") == "pb-preview" and health.get("pid") == rec["pid"]
    return (health if ok else None), code is not None


def managed_peers(d, own_pid):
    """The live managed servers other than this one → [{"rec", "health", "path"}]. A record whose server is
    gone, or whose URL now answers as something else, is deleted. A server that is alive but silent (it
    may be starting) is neither counted nor touched."""
    peers = []
    for name in sorted(os.listdir(d)):
        fp = os.path.join(d, name)
        if not name.endswith(".json"):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        pid = rec.get("pid") if isinstance(rec, dict) else None
        if not (isinstance(pid, int) and not isinstance(pid, bool) and pid > 1 and isinstance(rec.get("url"), str)):
            continue
        if pid == own_pid:
            continue
        health, answered = _peer_health(rec)
        if health is not None:
            peers.append({"rec": rec, "health": health, "path": fp})
        elif answered or not _pid_alive(pid):
            try:
                os.remove(fp)
            except OSError:
                pass
    return peers


def enforce_cap(own_pid):
    """Keep managed servers to PB_PREVIEW_MAX counting the one starting now: while over, SIGTERM the
    longest-idle peer with no browser tab open — only one whose health answer has just named a pb-preview
    with its recorded pid, and asked again right before the signal, in case a tab has opened since. One
    log line per server stopped; one when the cap is exceeded and nothing more may be stopped."""
    cap = preview_max()
    if cap <= 0:
        return
    peers = managed_peers(preview_dir(), own_pid)
    over = len(peers) + 1 - cap
    if over <= 0:
        return
    free = sorted((p for p in peers if p["health"].get("clients") == 0 and isinstance(p["health"].get("idleSeconds"), int)),
                  key=lambda p: -p["health"]["idleSeconds"])
    stopped = 0
    for p in free:
        if stopped >= over:
            break
        now, _ = _peer_health(p["rec"])
        if now is None or now.get("clients") != 0:
            continue
        try:
            os.kill(p["rec"]["pid"], signal.SIGTERM)
        except OSError:
            continue
        stopped += 1
        log("  cap       stopped pid %d (%s), idle %s with no tab open — %d previews run, the cap is %d (PB_PREVIEW_MAX)"
            % (p["rec"]["pid"], now.get("registry"), _human_seconds(now.get("idleSeconds")), len(peers) + 1, cap))
    if stopped < over:
        log("  cap       %d previews run and the cap is %d (PB_PREVIEW_MAX); the rest have a tab open, so they stay"
            % (len(peers) + 1, cap))


def register_managed(url, reg_path, started_at):
    """<preview dir>/<pid>.json — how the next managed start finds and counts this one. Removed on exit."""
    fp = os.path.join(preview_dir(), "%d.json" % os.getpid())
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"url": url, "pid": os.getpid(), "registry": reg_path, "startedAt": started_at}, f)
    os.replace(tmp, fp)
    return fp


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
    ap.add_argument("--port", type=int, default=None,
                    help="port (default: one of the project's own, %d–%d from a hash of the registry's path — "
                         "the same every start; walks up if busy)" % (PORT_BASE, PORT_BASE + PORT_SPAN - 1))
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind host (default: 127.0.0.1; anything else exposes the preview beyond this machine — "
                         "the Host guard then answers only the bound address and the --allow-host names)")
    ap.add_argument("--allow-host", action="append", type=parse_allow_host, metavar="NAME", default=None,
                    help="also answer requests whose Host header is NAME (repeatable; a bare name, no port, no "
                         "wildcard) — for previewing from another device or through a tunnel. Any other Host is a "
                         "403 naming this flag. POST (the settings and score saves) stays loopback-only")
    ap.add_argument("--write", action="store_true",
                    help="also write the rendered prototype.html to disk on every change")
    ap.add_argument("--out", default=None,
                    help="output path for --write (default: prototype.html next to the registry)")
    ap.add_argument("--no-open", action="store_true", help="don't open the browser on start")
    try:
        idle_default = float(os.environ.get("PB_PREVIEW_IDLE_MIN", IDLE_EXIT_MIN))
        if idle_default < 0:
            raise ValueError
    except ValueError:
        idle_default = IDLE_EXIT_MIN
    ap.add_argument("--idle-exit", type=float, default=idle_default, metavar="MINUTES",
                    help="stop by itself after this many minutes with no browser tab open and no request "
                         "(default: %g = %s, or $PB_PREVIEW_IDLE_MIN; 0 = never)"
                         % (idle_default, _human_seconds(idle_default * 60)))
    ap.add_argument("--debounce-ms", type=int, default=DEBOUNCE_MS, metavar="MS",
                    help="fold a burst of saves into one reload: wait this long with no further change, "
                         "at most %gs (default: %d; 0 = reload on the first change)" % (DEBOUNCE_CAP, DEBOUNCE_MS))
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true",
                      help="print this registry's running preview server (url, pid, uptime, clients, idle) and exit: "
                           "0 running, 1 not; starts nothing")
    mode.add_argument("--stop", action="store_true",
                      help="stop this registry's preview server (SIGTERM, only after its health check confirms it is "
                           "this registry's and the pid matches) and exit: 0 stopped / not running, 1 could not")
    mode.add_argument("--ensure", action="store_true",
                      help="print this registry's preview URL and pid; if no server is running, start one in the "
                           "background first (kept to $PB_PREVIEW_MAX, default 6, at once — the longest-idle one with "
                           "no tab open makes room). Safe to run again and again: exit 0 running / started, 3 could not start")
    ap.add_argument("--json", action="store_true", help="with --status / --stop / --ensure: print one JSON object")
    ap.add_argument("--managed", action="store_true", help=argparse.SUPPRESS)   # internal: set by explore._start_server
    args = ap.parse_args()
    if args.idle_exit < 0:
        ap.error("--idle-exit must be 0 or more minutes")
    if args.debounce_ms < 0:
        ap.error("--debounce-ms must be 0 or more")

    reg_path = os.path.abspath(args.registry)
    if args.status or args.stop:   # one-shot: ask the running server, never start one
        sys.exit((cmd_status if args.status else cmd_stop)(reg_path, args.json))
    shell_path = os.path.abspath(args.shell)
    if not os.path.isfile(reg_path):
        sys.exit("pb-serve: registry not found: %s" % reg_path)
    if not os.path.isfile(shell_path):
        sys.exit("pb-serve: shell template not found: %s" % shell_path)
    out_path = os.path.abspath(args.out) if args.out else os.path.join(
        os.path.dirname(reg_path), "prototype.html")

    if args.ensure:
        # What the caller asked for goes to the server it starts, as they asked: a project with a forked
        # shell must get that shell, not the plugin's. Only what differs from a default is passed on, and
        # paths absolute (the server starts in the project's folder, not in this one).
        given = []
        for flag, value, default in (("--shell", args.shell, default_shell), ("--ds-shell", args.ds_shell, default_ds_shell),
                                     ("--runtime", args.runtime, default_runtime), ("--out", args.out, None)):
            if value is not None and os.path.abspath(value) != default:
                given += [flag, os.path.abspath(value)]
        if args.port is not None:
            given += ["--port", str(args.port)]
        if args.host != "127.0.0.1":
            given += ["--host", args.host]
        for name in args.allow_host or []:
            given += ["--allow-host", name]
        if args.idle_exit != idle_default:
            given += ["--idle-exit", "%g" % args.idle_exit]
        if args.debounce_ms != DEBOUNCE_MS:
            given += ["--debounce-ms", str(args.debounce_ms)]
        if args.write:
            given.append("--write")
        sys.exit(cmd_ensure(reg_path, args.json, given))

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
                  default_explore_shell if os.path.isfile(default_explore_shell) else None,
                  idle_exit_min=args.idle_exit, debounce_ms=args.debounce_ms)
    Handler.state = state
    Handler.hosts = allowed_hosts(args.host, args.allow_host or [])

    explicit_port = args.port is not None
    httpd = make_server(args.host, args.port if explicit_port else stable_port(reg_path), explicit_port)
    port = httpd.server_address[1]
    # A wildcard bind names no address a browser could be sent to (0.0.0.0 would arrive as a Host the guard refuses)
    url = "http://%s:%d/" % ("127.0.0.1" if args.host in WILDCARD_HOSTS else args.host, port)

    def rel(p):  # short path when cwd is readable; absolute path if the sandbox forbids getcwd
        try:
            return os.path.relpath(p)
        except OSError:
            return p
    trim_server_log(os.path.dirname(reg_path))
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
    log("  watching  registry.json, shells, render.py, render/**/*.{js,css}, runtime/**/*.js, spec/**/*.json, logic/**/*.json — saving any reloads the browser")
    log("  to disk   %s" % ("ON → %s" % rel(out_path) if args.write
                            else "off (in-memory preview; --write to update prototype.html)"))
    log("  idle exit %s" % ("after %g min with no tab open and no request (--idle-exit 0 keeps it running)" % args.idle_exit
                            if args.idle_exit else "off (--idle-exit MINUTES to stop it when forgotten)"))
    if host_warning(args.host, Handler.hosts):
        log(host_warning(args.host, Handler.hosts))
    elif args.allow_host:
        log("  hosts     also answering Host %s (--allow-host); saves (POST) stay loopback-only" % ", ".join(args.allow_host))

    refresh(state)  # prime the mtimes the watcher compares against (before the render: a save during it is not missed)
    _html, err = render_current(state)  # render once up front so the banner reflects reality
    if err:
        log("  status    ✗ current registry has a render error — preview shows it")
    log("Ctrl-C to stop.")

    state.on_idle = httpd.shutdown   # called from the watcher thread, never from serve_forever's
    threading.Thread(target=watcher, args=(state,), daemon=True).start()
    if not args.no_open:
        threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()

    record = os.path.join(state.base_dir, explore.SERVER_FILE)
    managed_record = None
    # A plain kill (SIGTERM) unwinds like Ctrl-C, so the record goes with the server.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        if args.managed:   # started by --ensure or explore.py link: counted against the cap, and makes room for itself
            try:
                enforce_cap(os.getpid())
                managed_record = register_managed(url, reg_path, state.started_at)
            except Exception as e:   # bookkeeping is never the reason a preview does not start
                log("  ⚠ managed-preview bookkeeping skipped (%s) — started anyway" % e)
        write_server_record(record, {"url": url, "host": args.host, "port": port, "pid": os.getpid(),
                                     "registry": reg_path, "startedAt": state.started_at})
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        drop_server_record(record)
        if managed_record:
            try:
                os.remove(managed_record)
            except OSError:
                pass
        state.stop.set()
        state.bump()  # wake SSE streams so they exit promptly
        httpd.shutdown()
        log("stopped.")


if __name__ == "__main__":
    main()
