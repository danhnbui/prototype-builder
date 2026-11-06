#!/usr/bin/env python3
"""
research_serve.py — the /pb:research session routes on the /pb:preview server (pb/tools/serve.py). Stdlib only.

Everything here is TEST DATA: the study is set directly in a temp copy of fixtures/research/ and every
session, recording and report below is written by this test. Nothing was recorded from a person.

The server is booted in this process on port 0 (the way tests/explore_tool.py does), so the page scripts can
be pointed at stubs through research_session.TEMPLATE_DIR — the least invasive way, no flag in serve.py.
The real shell (pb/template/prototype.html) and the real runtime render the pages.

What it proves:

  1. helpers       parse_range (a-b · a- · -n · past the end · reversed · several · other unit), research_query,
                   research_failure (a busy lock that research.locked re-raised as a ResearchError is a 503)
  2. who may ask   loopback peer AND loopback Host on every route; a foreign Host is the Host guard's 403; a
                   peer that is not this machine and a name given with --allow-host are 403 here, on the pages,
                   the evidence and both POSTs; the POSTs also want this page's own Origin
  3. pages         session · observer · replay · report: 200, no `new EventSource`, no `window.PB_PREVIEW=`,
                   nothing of the study's hypotheses; a draft is a 409 (a pilot may run on one); a bad link,
                   an unknown study and an id that is not an id are 400 / 404
  4. POST session  201 with the evidence id (0444 file, sha256 row, status fielding, participant done); a pilot
                   goes to pilot/; duplicate 409; an invalid file, bad JSON, a draft 400; a length that is
                   missing 411, chunked 411, not a number / twice / zero / over the cap / short 400; the cap
                   and the stall timeout; a busy registry 503; a lock file that is a symlink 500
  5. POST media    streamed (a few KB and 3 MiB) into .incoming/, stored, linked both ways, 0444, sha256 right;
                   no recording consent, a second recording, a non-WebM, a session not stored, a bad query,
                   a truncated body, a stalled body, a busy registry: each refused with the temp file removed
  6. evidence GET  full and Range (206 + Content-Range, 416, ignored forms, across the 1 MiB read boundary),
                   sha256 checked first (a changed file 409, a symlink 409, a missing one 404), a dropped row,
                   a hostile path in a row, a kind that is not served, pilot files
  7. report        404 page that names `research.py report <id>`, then 200 with the file, never through a symlink
  8. hygiene       nothing under memory/ is reachable as a static file; no traceback anywhere

Usage:  python3 tests/research_serve.py        Exit: 0 PASS · 1 a failure
"""
import contextlib
import copy
import email.message
import hashlib
import http.client
import io
import json
import os
import shutil
import socket
import stat
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
FIX = os.path.join(ROOT, "fixtures", "research")
sys.path.insert(0, TOOLS)

import research as R           # noqa: E402
import research_session as RS  # noqa: E402
import serve                   # noqa: E402

SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
RUNTIME = os.path.join(ROOT, "pb", "template", "runtime.js")
TMP = tempfile.mkdtemp(prefix="pb-rs-serve-")
SID = "rs-ux-pay"
fails = []
LOG = []                      # what the server logged: no traceback may be in it


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title)


# ── test data ────────────────────────────────────────────────────────────────

HYP = "Couriers will miss the hidden cash total on the pay screen"
TITLE = "Pay screen total study (secret title)"
CONSENT = "I agree to take part. My screen and voice may be recorded if I tick the box."
START, END = "2026-03-02T10:00:00Z", "2026-03-02T10:00:12Z"


def study(status="approved"):
    return {
        "id": SID, "title": TITLE, "question": "Can couriers find the cash total (secret question)?", "method": "usability",
        "status": status, "scope": "collect", "setup": "", "createdAt": "2026-03-01T09:00:00Z",
        "audience": {"roles": ["courier"], "targetN": 5}, "targets": [{"kind": "screen", "id": "pay"}],
        "hypotheses": [{"id": "h1", "statement": HYP, "targets": [{"kind": "screen", "id": "pay"}],
                        "supportedIf": "Fewer than 3 of 5 find the total in 60 seconds.",
                        "refutedIf": "At least 4 of 5 find it.", "verdict": None, "why": ""}],
        "instrument": {
            "lang": "en", "intro": "Thanks for helping.", "consent": CONSENT, "closing": "Thank you.", "durationMin": 30,
            "mode": "both", "recording": {"screen": True, "voice": True}, "device": "mobile", "thinkAloud": True,
            "sections": [
                {"title": "Warm up", "purpose": "warmup", "questions": [
                    {"id": "w1", "text": "How often do you deliver?", "type": "single", "options": ["Daily", "Weekly"], "tests": []}]},
                {"title": "Task", "purpose": "task", "questions": [
                    {"id": "t1", "text": "You have arrived at the first stop. Collect the cash.", "tests": ["h1"],
                     "task": {"screen": "route", "success": "The cash is collected and the handover shows.",
                              "criteria": [{"screen": "handover"}]}},
                    {"id": "seq1", "template": "seq", "tests": ["h1"]}]}]},
        "evidence": [], "findings": [], "gates": []}


def ev(t, typ, task, screen, **f):
    d = {"t": t, "type": typ, "task": task, "screen": screen}
    d.update(f)
    return d


def session_obj(session_id, part="P01", pilot=False, recording=False):
    events = [
        ev(0, "session-start", None, "route"),
        ev(100, "consent", None, "route", recording=recording),
        ev(1000, "task-start", "t1", "route"),
        ev(1500, "click", "t1", "route", x=0.5, y=0.5, target="route > button", cmp="Button", interactive=True, dead=False),
        ev(3000, "nav", "t1", "pay", **{"from": "route", "to": "pay", "back": False}),
        ev(5000, "criteria", "t1", "pay", met=True),
        ev(6000, "nav", "t1", "handover", **{"from": "pay", "to": "handover", "back": False}),
        ev(7000, "task-end", "t1", "handover", outcome="success", source="criteria"),
        ev(12000, "session-end", None, "handover"),
    ]
    return {
        "format": "pb-session", "version": 1, "study": SID, "method": "usability", "sessionId": session_id, "participant": part,
        "mode": "moderated", "pilot": pilot, "startedAt": START, "endedAt": END, "durationMs": 12000,
        "env": {"viewport": [429, 926], "device": "mobile", "sink": "server", "shell": "test"},
        "consent": {"session": True, "recording": recording, "at": START, "textSha256": hashlib.sha256(CONSENT.encode("utf-8")).hexdigest()},
        "config": {"tasks": [{"id": "t1", "text": "Collect the cash.", "task": {"screen": "route"}}]},
        "tasks": [{"id": "t1", "startT": 1000, "endT": 7000, "outcome": "success", "outcomeSource": "criteria", "criteriaT": 5000,
                   "selfReport": "done", "assisted": False, "answers": {"seq1": 6}}],
        "answers": {"w1": "Weekly"}, "result": {}, "events": events, "media": []}


def raw_of(obj):
    return json.dumps(obj, sort_keys=True).encode("utf-8")


def webm(n, salt=b"abcdefghij"):
    """A stand-in recording: the WebM magic, then n bytes that are not all alike (so a wrong range is visible)."""
    return RS.WEBM_MAGIC + (salt * (n // len(salt) + 1))[:n]


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ── a throwaway project and a server booted on it ────────────────────────────

PROJ = os.path.join(TMP, "project")
shutil.copytree(FIX, PROJ)
REG = os.path.join(PROJ, "registry.json")
STUBS = os.path.join(TMP, "stubs")
os.makedirs(STUBS)
for _name, _marker in (("research-session.js", "/*STUB-SESSION*/ window.__stubSession=1;"),
                       ("research-methods.js", "/*STUB-METHODS*/ window.__stubMethods=1;"),
                       ("research-replay.js", "/*STUB-REPLAY*/ window.__stubReplay=1;")):
    with open(os.path.join(STUBS, _name), "w", encoding="utf-8") as _f:
        _f.write(_marker + "\n")
RS.TEMPLATE_DIR = STUBS


def reg_data():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def reg_save(d):
    with open(REG, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")


def the_study():
    return next(s for s in reg_data()["research"]["studies"] if s["id"] == SID)


def set_study(**kw):
    d = reg_data()
    for s in d["research"]["studies"]:
        if s["id"] == SID:
            s.update(kw)
    reg_save(d)


def reg_put_study(s):
    d = reg_data()
    d["research"] = {"populated": True, "studies": [s]}
    reg_save(d)


reg_put_study(study())


def path_in(*p):
    return os.path.join(PROJ, "memory", "research", SID, *p)


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


st = serve.State(REG, SHELL, None, False, None, RUNTIME, None)
serve.Handler.state = st
serve.log = LOG.append                                   # the server's own log lines, kept for the traceback check
httpd = serve.make_server("127.0.0.1", 0, True)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
PORT = httpd.server_address[1]
HOST = "127.0.0.1:%d" % PORT


# ── requests ─────────────────────────────────────────────────────────────────

def req(method, path, headers=None, body=None, host=HOST, origin=True):
    """One request with the headers under the test's control → (status, {lower-case header: value}, body bytes).
    origin=True sends this page's own Origin (a same-origin fetch); False sends none; a string sends that one."""
    h = {"Host": host}
    if origin is True and method == "POST":
        h["Origin"] = "http://" + HOST
    elif isinstance(origin, str):
        h["Origin"] = origin
    h.update(headers or {})
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20)
    try:
        conn.request(method, path, body=body, headers={k: v for k, v in h.items() if v is not None})
        r = conn.getresponse()
        data = r.read()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, data
    finally:
        conn.close()


def get(path, **k):
    return req("GET", path, **k)


def jbody(data):
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"raw": data[:200]}


def post_json(path, body, **k):
    st_, h, data = req("POST", path, body=body, headers={"Content-Type": "application/json"}, **k)
    return st_, jbody(data)


def post_session(obj_or_raw, **k):
    raw = obj_or_raw if isinstance(obj_or_raw, bytes) else raw_of(obj_or_raw)
    return post_json("/__pb_research/%s/session" % SID, raw, **k)


def post_media(session_id, body, query=None, **k):
    q = query if query is not None else "session=%s&kind=screen" % session_id
    st_, h, data = req("POST", "/__pb_research/%s/media?%s" % (SID, q), body=body,
                       headers={"Content-Type": "video/webm"}, **k)
    return st_, jbody(data)


def raw_exchange(method, path, header_lines, body=b"", half_close=False, wait=None):
    """A request written by hand on a socket, for what http.client will not send (no Content-Length, a chunked
    body, two lengths, fewer bytes than promised). → (status, headers, parsed JSON or {"raw": …}, closed?)."""
    sock = socket.create_connection(("127.0.0.1", PORT), timeout=20)
    lines = ["%s %s HTTP/1.1" % (method, path), "Host: " + HOST, "Origin: http://" + HOST] + list(header_lines)
    try:
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
        if half_close:
            sock.shutdown(socket.SHUT_WR)
        if wait:
            time.sleep(wait)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1]) if head else 0
        hdrs = {}
        for ln in head.split(b"\r\n")[1:]:
            k, _, v = ln.partition(b":")
            hdrs[k.decode("latin-1").lower()] = v.decode("latin-1").strip()
        clen = int(hdrs.get("content-length", "0"))
        while len(rest) < clen:
            chunk = sock.recv(65536)
            if not chunk:
                break
            rest += chunk
        closed = hdrs.get("connection", "").lower() == "close"
        return status, hdrs, jbody(rest), closed
    finally:
        sock.close()


def incoming_files():
    d = path_in(".incoming")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


SECURITY = {"x-content-type-options": "nosniff", "referrer-policy": "no-referrer",
            "x-frame-options": "SAMEORIGIN", "cross-origin-resource-policy": "same-origin"}


def has_security(h):
    return all(h.get(k) == v for k, v in SECURITY.items())


def clean_page(html, label):
    """A participant's page: no live-reload client, no preview API handle, nothing of the study."""
    check("new EventSource" not in html and "pb-serve live-reload" not in html, "%s: no live-reload client (no `new EventSource`)" % label)
    check("window.PB_PREVIEW=" not in html, "%s: no window.PB_PREVIEW= (the shell only reads it, to see whether it was served by the preview)" % label)
    check(HYP not in html and TITLE not in html and "secret question" not in html, "%s: none of the study's hypotheses, title or question" % label)


# ═════════════════════════════════════════════════════════════════════════════
section("1. helpers")
pr = serve.parse_range
check(pr("bytes=0-9", 100) == (0, 9) and pr("bytes=10-", 100) == (10, 99) and pr("bytes=-7", 100) == (93, 99),
      "parse_range: a-b, a- and -n")
check(pr("bytes=90-5000", 100) == (90, 99) and pr("bytes=-500", 100) == (0, 99), "parse_range: an end past the file is clamped, a tail longer than the file is the file")
check(pr("bytes=100-", 100) == "unsatisfiable" and pr("bytes=100-200", 100) == "unsatisfiable" and pr("bytes=-0", 100) == "unsatisfiable"
      and pr("bytes=0-", 0) == "unsatisfiable" and pr("bytes=-5", 0) == "unsatisfiable", "parse_range: a start past the end, -0 and any range of an empty file are unsatisfiable")
check(pr("bytes=5-2", 100) is None and pr("bytes=0-1,3-4", 100) is None and pr("items=0-1", 100) is None
      and pr("bytes=abc", 100) is None and pr("", 100) is None and pr(None, 100) is None and pr("bytes=" + "9" * 40 + "-", 100) is None
      and pr("bytes=0-" + "1" * 80, 100) is None, "parse_range: reversed, several, another unit, junk, empty and over-long are ignored (the whole file is sent)")
check(pr(" bytes=3-4 ", 100) == (3, 4), "parse_range: surrounding blanks are fine")

q = serve.research_query(RS, "p=P01&pilot=1&mode=moderated")
check(q == {"participant": "P01", "pilot": True}, "research_query: p, pilot and mode read")
check(serve.research_query(RS, "") == {"participant": None, "pilot": False} and serve.research_query(RS, "x=1&p=P02")["participant"] == "P02",
      "research_query: nothing given is fine; unknown keys are ignored")
for bad in ("p=P1", "p=Maria", "p=P01&p=P02", "pilot=2", "pilot=", "mode=x", "mode=moderated&mode=unmoderated", "p=" + "P" * 300):
    try:
        serve.research_query(RS, bad)
        check(False, "research_query refuses %r" % bad[:30])
    except ValueError:
        check(True, "research_query refuses %r" % bad[:30])


def locked_as_research_error(exc):
    """What research.locked raises when slice.registry_lock refuses: a ResearchError with the lock error as context."""
    try:
        try:
            raise exc
        except serve.pbslice.RegistryLocked as e:
            raise R.ResearchError(str(e))
    except R.ResearchError as e2:
        return e2


for label, exc, want in (
        ("a busy registry (as research.locked re-raises it)", locked_as_research_error(serve.pbslice.RegistryLocked("busy")), 503),
        ("a lock file that is not a regular file (as re-raised)", locked_as_research_error(serve.pbslice.LockFileUnsafe("odd")), 500),
        ("a bare RegistryLocked", serve.pbslice.RegistryLocked("busy"), 503),
        ("a bare LockFileUnsafe", serve.pbslice.LockFileUnsafe("odd"), 500),
        ("a duplicate", R.ResearchError("dup", 1, {"duplicate": True}), 409),
        ("a study that is not there (exit 2)", R.ResearchError("no study", R.EXIT_USAGE), 404),
        ("any other refusal", R.ResearchError("nope"), 400)):
    got = serve.research_failure(R, exc)
    check(got[0] == want and isinstance(got[1], str) and got[1], "research_failure: %s → %d" % (label, want))

# ═════════════════════════════════════════════════════════════════════════════
section("2. who may ask")


class FakeHandler(serve.Handler):
    """A Handler with no socket: just enough of a request for the gates (the same trick tests/serve_host_guard.py uses)."""

    def __init__(self, peer, host, origin=None, command="GET", path="/"):
        self.client_address = (peer, 50000)
        self.headers = email.message.Message()
        if host is not None:
            self.headers["Host"] = host
        if origin is not None:
            self.headers["Origin"] = origin
        self.command, self.path = command, path
        self.sent = []
        self._body_read = False

    def _send(self, body, ctype="text/html", status=200, close=False):
        self.sent.append((status, body, close))


for peer, host, want in (("127.0.0.1", "127.0.0.1:8000", False), ("::1", "[::1]:8000", False), ("::ffff:127.0.0.1", "localhost", False),
                         ("10.0.0.5", "127.0.0.1:8000", True), ("203.0.113.9", "localhost", True),
                         ("127.0.0.1", "my-mac.local:8000", True), ("127.0.0.1", "evil.example", True), ("127.0.0.1", None, True)):
    f = FakeHandler(peer, host)
    got = f._research_gate()
    check(got is want and (bool(f.sent) is want) and (not f.sent or (f.sent[0][0] == 403 and f.sent[0][2] is True)),
          "GET gate: peer %s, Host %s → %s" % (peer, host, "403, closed" if want else "let through"))
for path in ("/research/%s/session" % SID, "/research/%s/observer" % SID, "/research/%s/report" % SID,
             "/research/%s/replay/e1" % SID, "/__pb_research/%s/evidence/e1" % SID):
    f = FakeHandler("10.0.0.5", "127.0.0.1:8000")
    f.serve_research(path)
    check(len(f.sent) == 1 and f.sent[0][0] == 403, "a peer on the LAN gets a 403 from %s (perfect Host or not)" % path.split(SID)[1])
for tail in ("session", "media?session=s-aaaa1&kind=screen"):
    f = FakeHandler("10.0.0.5", "127.0.0.1:8000", origin="http://127.0.0.1:8000", command="POST", path="/__pb_research/%s/%s" % (SID, tail))
    f.post_research(["__pb_research", SID, tail.split("?")[0]], tail.partition("?")[2])
    body = json.loads(f.sent[0][1]) if f.sent else {}
    check(len(f.sent) == 1 and f.sent[0][0] == 403 and f.sent[0][2] is True and body.get("ok") is False,
          "POST %s from a peer on the LAN → 403 JSON, connection closed, body unread" % tail.split("?")[0])

# the live server: a foreign Host is the Host guard's; a name given with --allow-host reaches the guard and stops at the research door
good_get = ["/research/%s/session" % SID, "/research/%s/observer" % SID, "/research/%s/report" % SID,
            "/research/%s/replay/e1" % SID, "/__pb_research/%s/evidence/e1" % SID]
for p in good_get:
    s_, h_, b_ = get(p, host="evil.example")
    check(s_ == 403 and b"evil.example" in b_ and h_.get("connection", "").lower() == "close", "a foreign Host is refused on %s" % p.split(SID)[1])
s_, h_, b_ = req("POST", "/__pb_research/%s/session" % SID, body=b"{}", host="evil.example", origin="http://evil.example")
check(s_ == 403 and jbody(b_).get("ok") is False, "a foreign Host is refused on POST session")
serve.Handler.hosts = frozenset(serve.LOOPBACK_HOSTS) | {"my-mac.local"}
try:
    for p in good_get:
        s_, h_, b_ = get(p, host="my-mac.local")
        check(s_ == 403 and b"127.0.0.1 or localhost" in b_, "a name from --allow-host passes the Host guard and is stopped by the research door: %s" % p.split(SID)[1])
    s_, j_ = post_session(session_obj("s-zzzz1"), host="my-mac.local", origin="http://my-mac.local")
    check(s_ == 403 and j_.get("ok") is False, "…and POST session from such a name is a 403")
finally:
    serve.Handler.hosts = frozenset(serve.LOOPBACK_HOSTS)
s_, h_, b_ = get("/research/%s/session" % SID, host="localhost:%d" % PORT)
check(s_ == 200, "Host localhost:<port> is let through")

# ═════════════════════════════════════════════════════════════════════════════
section("3. pages")
s_, h_, b_ = get("/research/%s/session" % SID)
html = b_.decode("utf-8", "replace")
check(s_ == 200 and h_.get("content-type", "").startswith("text/html"), "GET session → 200 text/html")
check("window.PB_RS_SESSION=" in html and "/*STUB-SESSION*/" in html and "/*STUB-METHODS*/" in html, "…carrying PB_RS_SESSION and both page scripts")
check('"sink":"server"' in html and ("/__pb_research/%s/session" % SID) in html and ("/__pb_research/%s/media" % SID) in html,
      "…with the server sink and the two POST endpoints")
check(has_security(h_) and h_.get("cache-control") == "no-store", "…with the security headers and no-store")
clean_page(html, "session")
s_, h_, b_ = get("/research/%s/session?p=P01&pilot=0&mode=moderated" % SID)
check(s_ == 200 and '"participant":"P01"' in b_.decode("utf-8", "replace"), "?p=P01&pilot=0&mode=moderated → 200 with the participant set")
s_, h_, b_ = get("/research/%s/session?p=P07&pilot=1" % SID)
check(s_ == 200 and '"pilot":true' in b_.decode("utf-8", "replace"), "?pilot=1 → 200 with pilot true")
for q_, why in (("p=P1", "a participant that is not a pseudonym"), ("p=Maria", "a name"), ("pilot=2", "pilot=2"), ("mode=loud", "an unknown mode"),
                ("p=P01&p=P02", "p twice"), ("p=" + "P" * 400, "an over-long query")):
    s_, h_, b_ = get("/research/%s/session?%s" % (SID, q_))
    check(s_ == 400 and b"EventSource" not in b_, "?%s → 400 (%s), a page without a reload client" % (q_[:24], why))
s_, h_, b_ = get("/research/%s/observer" % SID)
html = b_.decode("utf-8", "replace")
check(s_ == 200 and "Observer" in html and "/*STUB-SESSION*/" in html and '"page":"observer"' in html, "GET observer → 200 with the observer config")
clean_page(html, "observer")
s_, h_, b_ = get("/research/%s/observer?p=P01&pilot=1" % SID)
check(s_ == 200, "observer takes the same link flags")

for path_, want, why in (
        ("/research/rs-nope/session", 404, "a well-formed study that does not exist"),
        ("/research/RS-UX-PAY/session", 404, "an id that is not a study id"),
        ("/research/x/session", 404, "a short id"),
        ("/research/%s" % SID, 404, "no page named"),
        ("/research/%s/nonsense" % SID, 404, "an unknown page"),
        ("/research/%s/session/extra" % SID, 404, "an extra segment"),
        ("/research/%s%%2Fsession" % SID, 404, "an encoded slash"),
        ("/research/..%2f..%2fregistry.json/session", 404, "a traversal"),
        ("/research/%s/replay" % SID, 404, "replay with no id"),
        ("/research/%s/replay/e1x" % SID, 404, "replay of something that is not an evidence id"),
        ("/research/%s/replay/..%%2fe1" % SID, 404, "replay with an encoded traversal"),
        ("/research/%s/replay/pilot-x" % SID, 404, "replay of a pilot id that is too short"),
        ("/research/%s/replay/e99" % SID, 404, "replay of evidence that is not there"),
        ("/__pb_research/%s" % SID, 404, "evidence with no route"),
        ("/__pb_research/%s/evidence" % SID, 404, "evidence with no id"),
        ("/__pb_research/%s/evidence/e1/extra" % SID, 404, "evidence with an extra segment"),
        ("/__pb_research/%s/other/e1" % SID, 404, "an unknown evidence route")):
    s_, h_, b_ = get(path_)
    check(s_ == want and b"EventSource" not in b_, "%s → %d (%s)" % (path_[:56], want, why))

set_study(status="draft")
s_, h_, b_ = get("/research/%s/session" % SID)
check(s_ == 409 and b"draft" in b_ and b"EventSource" not in b_, "a draft study's session page is a 409 that says why, with no reload client")
s_, h_, b_ = get("/research/%s/session?p=P09&pilot=1" % SID)
check(s_ == 200, "…but a pilot may run on a draft")
s_, j_ = post_session(session_obj("s-draft1"))
check(s_ == 400 and "draft" in j_.get("error", ""), "POST session on a draft → 400 naming the draft (%s)" % j_.get("error", "")[:60])
set_study(status="approved")
set_study(scope="instrument")
s_, h_, b_ = get("/research/%s/session" % SID)
check(s_ == 409, "scope `instrument` → the session page is a 409")
set_study(scope="collect")

# ═════════════════════════════════════════════════════════════════════════════
section("4. POST session")
URL_S = "/__pb_research/%s/session" % SID
good = session_obj("s-aaaa1", "P01")
GOOD_RAW = raw_of(good)
check(post_session(good, origin=False)[0] == 403, "no Origin → 403")
s_, j_ = post_session(good, origin="http://evil.example")
check(s_ == 403 and j_.get("ok") is False, "another site's Origin → 403 JSON")
check(post_session(good, origin="http://localhost:%d" % PORT)[0] == 403, "…and so is another name for this host (an Origin is exact)")
check(the_study()["evidence"] == [] and not os.path.isdir(path_in("evidence")), "(none of those stored anything)")

s_, j_ = post_session(good)
check(s_ == 201 and j_.get("ok") is True and j_.get("evidence") == "e1" and j_.get("sessionId") == "s-aaaa1" and j_.get("pilot") is False
      and isinstance(j_.get("warnings"), list), "a good session → 201 {ok, evidence: e1, sessionId, pilot: false, warnings} (%s)" % j_)
f1 = path_in("evidence", "e1-s-aaaa1.json")
check(os.path.isfile(f1) and mode_of(f1) == 0o444 and open(f1, "rb").read() == GOOD_RAW, "…the file is on disk, mode 0444, byte for byte what was sent")
row = next((e for e in the_study()["evidence"] if e["id"] == "e1"), {})
check(row.get("kind") == "session" and row.get("sha256") == sha(GOOD_RAW) and row.get("consent") == "yes" and row.get("participant") == "P01"
      and row.get("session", {}).get("id") == "s-aaaa1", "…and a session row with the file's sha256")
the = the_study()
check(the.get("status") == "fielding" and any(p.get("id") == "P01" and p.get("status") == "done" for p in the.get("participants", [])),
      "…the study is fielding and P01 is done")
s_, j_ = post_session(good)
check(s_ == 409 and "already stored" in j_.get("error", ""), "the same session again → 409 (%s)" % j_.get("error", "")[:50])
dup = session_obj("s-aaaa1", "P02")
s_, j_ = post_session(dup)
check(s_ == 409, "the same sessionId in a different file → 409")
bad = session_obj("s-bad01", "P03")
bad["consent"]["session"] = False
s_, j_ = post_session(bad)
check(s_ == 400 and "S-CONSENT" in j_.get("error", ""), "a session without consent → 400 naming S-CONSENT (%s)" % j_.get("error", "")[:60])
for label, raw in (("bytes that are not JSON", b"not json at all"), ("a JSON array", b"[1,2,3]"), ("not UTF-8", b"\xff\xfe\x00{"),
                   ("nesting past the depth guard", b"[" * 200 + b"]" * 200)):
    s_, j_ = post_session(raw)
    check(s_ == 400 and j_.get("ok") is False and "Traceback" not in json.dumps(j_), "%s → 400 with a message" % label)
s_, j_ = post_json("/__pb_research/rs-nope/session", GOOD_RAW)
check(s_ == 404 and j_.get("ok") is False, "an unknown study → 404")
s_, j_ = post_json("/__pb_research/rs-BAD/session", GOOD_RAW)
check(s_ == 404, "an id that is not a study id → 404")
s_, j_ = post_json("/__pb_research/%s/other" % SID, GOOD_RAW)
check(s_ == 404, "an unknown POST route → 404")
st_x, _h, _b, closed = raw_exchange("POST", "/__pb_research/%s/other" % SID, ["Content-Length: 2"], b"{}")
check(st_x == 404 and closed, "…and the connection is closed (a body nobody read)")

# the length: missing, chunked, not a number, twice, zero, over the cap, short
st_x, _h, j_, closed = raw_exchange("POST", URL_S, [])
check(st_x == 411 and closed and j_.get("ok") is False, "no Content-Length → 411, closed")
st_x, _h, j_, closed = raw_exchange("POST", URL_S, ["Transfer-Encoding: chunked"], b"5\r\nhello\r\n0\r\n\r\n")
check(st_x == 411 and closed and "chunked" in j_.get("error", ""), "Transfer-Encoding: chunked without a length → 411, closed")
st_x, _h, j_, closed = raw_exchange("POST", URL_S, ["Transfer-Encoding: chunked", "Content-Length: 5"], b"hello")
check(st_x == 400 and closed, "chunked and a length together → 400, closed")
for label, lines in (("not a number", ["Content-Length: 12abc"]), ("negative", ["Content-Length: -5"]), ("with a plus", ["Content-Length: +5"]),
                     ("a hex number", ["Content-Length: 0x10"]), ("13 digits", ["Content-Length: 1234567890123"]),
                     ("given twice", ["Content-Length: 5", "Content-Length: 5"]), ("zero", ["Content-Length: 0"]),
                     ("over the cap", ["Content-Length: %d" % (RS.SESSION_MAX_BYTES + 1)])):
    st_x, _h, j_, closed = raw_exchange("POST", URL_S, lines, b"hello")
    check(st_x == 400 and closed and j_.get("ok") is False, "Content-Length %s → 400, closed (%s)" % (label, j_.get("error", "")[:40]))
st_x, _h, j_, closed = raw_exchange("POST", URL_S, ["Content-Length: %d" % RS.SESSION_MAX_BYTES], b"{}", half_close=True)
check(st_x == 400 and "incomplete" in j_.get("error", ""), "a body shorter than its length, then the client hangs up → 400 incomplete")
serve.RESEARCH_CHUNK_TIMEOUT = 0.4
try:
    t0 = time.time()
    st_x, _h, j_, closed = raw_exchange("POST", URL_S, ["Content-Length: 5000"], b'{"a":')
    check(st_x == 400 and "incomplete" in j_.get("error", "") and time.time() - t0 < 5, "a body that stalls is dropped after the piece timeout (%.1fs), not held open" % (time.time() - t0))
finally:
    serve.RESEARCH_CHUNK_TIMEOUT = 30.0
check(len(the_study()["evidence"]) == 1, "(none of those stored anything: still one evidence row)")

# a pilot goes to pilot/, never evidence — and a pilot may arrive on a draft
set_study(status="draft")
pil = session_obj("s-pilot1", "P90", pilot=True, recording=True)
PIL_RAW = raw_of(pil)
s_, j_ = post_session(pil)
check(s_ == 201 and j_.get("pilot") is True and j_.get("evidence") is None, "a pilot → 201, pilot true, no evidence id (%s)" % j_)
set_study(status="fielding")
check(os.path.isfile(path_in("pilot", "s-pilot1.json")) and len(the_study()["evidence"]) == 1 and the_study()["pilots"][0]["sessionId"] == "s-pilot1",
      "…in pilot/ and study.pilots[], not in the evidence list")

# a busy registry: another writer holds the lock → 503; the registry is untouched and no file is left
lock_path = os.path.realpath(REG) + ".lock"
os.environ["PB_LOCK_TIMEOUT"] = "0.3"
before = open(REG, "rb").read()
try:
    with serve.pbslice.registry_lock(REG, "research_serve test"):
        s_, j_ = post_session(session_obj("s-busy01", "P04"))
    check(s_ == 503 and "another pb process" in j_.get("error", ""), "a held registry lock → 503 naming the holder (%s)" % j_.get("error", "")[:60])
    check(open(REG, "rb").read() == before and not os.path.exists(path_in("evidence", "e2-s-busy01.json")), "…the registry untouched, no file written")
    s_, j_ = post_session(session_obj("s-busy01", "P04"))
    check(s_ == 201 and j_.get("evidence") == "e2", "…and the same upload succeeds once the lock is free (%s)" % j_)
    # a lock file that is a symlink is not "try again": 500, nothing followed
    victim = os.path.join(TMP, "victim.txt")
    with open(victim, "w") as f:
        f.write("keep me")
    if os.path.lexists(lock_path):
        os.unlink(lock_path)
    os.symlink(victim, lock_path)
    s_, j_ = post_session(session_obj("s-lock01", "P05"))
    check(s_ == 500 and "not a regular file" in j_.get("error", "") and open(victim).read() == "keep me",
          "a lock file that is a symlink → 500, and nothing was written through it (%s)" % j_.get("error", "")[:50])
    os.unlink(lock_path)
finally:
    del os.environ["PB_LOCK_TIMEOUT"]

# ═════════════════════════════════════════════════════════════════════════════
section("5. POST media")
check(incoming_files() == [], "(no temp upload is lying about to start with)")
rec_obj = session_obj("s-rec01", "P06", recording=True)
s_, j_ = post_session(rec_obj)
rec_eid = j_.get("evidence")
check(s_ == 201 and rec_eid == "e3", "(a session that consented to recording is stored as %s)" % rec_eid)
body_small = webm(4096)
check(post_media("s-rec01", body_small, origin=False)[0] == 403 and post_media("s-rec01", body_small, origin="http://evil.example")[0] == 403,
      "no Origin and another Origin → 403")
s_, j_ = post_media("s-aaaa1", body_small)
check(s_ == 400 and "no recording consent" in j_.get("error", ""), "a session without recording consent → 400 (%s)" % j_.get("error", "")[:60])
check(incoming_files() == [], "…and the temp file was removed")
s_, j_ = post_media("s-rec01", body_small)
media_eid = j_.get("evidence")
check(s_ == 201 and j_.get("ok") is True and media_eid == "e4" and j_.get("bytes") == len(body_small) and j_.get("sha256") == sha(body_small),
      "a recording → 201 {ok, evidence: e4, bytes, sha256} (%s)" % {k: v for k, v in j_.items() if k != "sha256"})
f_rec = path_in("evidence", "e4-s-rec01-screen.webm")
check(os.path.isfile(f_rec) and mode_of(f_rec) == 0o444 and open(f_rec, "rb").read() == body_small, "…stored 0444, byte for byte")
d = the_study()
srow = next(e for e in d["evidence"] if e["id"] == "e3")
mrow = next(e for e in d["evidence"] if e["id"] == "e4")
check(mrow.get("kind") == "recording" and mrow.get("session") == "s-rec01" and mrow.get("sha256") == sha(body_small) and mrow.get("bytes") == len(body_small)
      and srow["session"]["media"] == ["e4"] and srow["session"]["recording"] is True, "…the two rows link to each other")
check(incoming_files() == [], "…and .incoming/ is empty again")
s_, j_ = post_media("s-rec01", webm(4096, b"zyxwv"))
check(s_ == 409 and "already has a recording" in j_.get("error", ""), "a second recording for the session → 409 (%s)" % j_.get("error", "")[:50])
check(incoming_files() == [], "…temp file removed")
s_, j_ = post_media("s-rec01", b"RIFF....WAVEfmt " + b"x" * 200)
check(s_ == 400 and "WebM" in j_.get("error", ""), "a body that is not WebM → 400, refused on its first bytes (%s)" % j_.get("error", "")[:50])
check(incoming_files() == [], "…temp file removed")
s_, j_ = post_media("s-nope1", body_small)
check(s_ == 400 and "not stored" in j_.get("error", ""), "a session that is not stored → 400 before any body is read (%s)" % j_.get("error", "")[:50])
check(not os.path.isdir(path_in(".incoming")) or incoming_files() == [], "…and no temp file")
for label, query in (("no session", "kind=screen"), ("session twice", "session=s-rec01&session=s-rec01&kind=screen"), ("a session that is a path", "session=..%2f..%2fx&kind=screen"),
                     ("an upper-case session", "session=S-REC01&kind=screen"), ("no kind", "session=s-rec01"), ("kind=audio", "session=s-rec01&kind=audio"),
                     ("an over-long query", "session=s-rec01&kind=screen&x=" + "a" * 400)):
    s_, j_ = post_media("s-rec01", body_small, query=query)
    check(s_ == 400 and j_.get("ok") is False, "media query with %s → 400 (%s)" % (label, j_.get("error", "")[:40]))
s_, j_ = req("POST", "/__pb_research/rs-nope/media?session=s-rec01&kind=screen", body=body_small)[0], None
check(s_ == 404, "media for an unknown study → 404")
URL_M = "/__pb_research/%s/media?session=s-rec01&kind=screen" % SID
st_x, _h, j_, closed = raw_exchange("POST", URL_M, [])
check(st_x == 411 and closed, "media with no Content-Length → 411")
st_x, _h, j_, closed = raw_exchange("POST", URL_M, ["Transfer-Encoding: chunked"], b"3\r\nabc\r\n0\r\n\r\n")
check(st_x == 411 and closed and j_.get("ok") is False, "media sent chunked → 411")
st_x, _h, j_, closed = raw_exchange("POST", URL_M, ["Content-Length: %d" % (RS.MEDIA_MAX_BYTES + 1)])
check(st_x == 400 and closed and "too large" in j_.get("error", ""), "media over the cap → 400 before a byte is read, closed (%s)" % j_.get("error", "")[:40])
st_x, _h, j_, closed = raw_exchange("POST", URL_M, ["Content-Length: abc"], b"x")
check(st_x == 400, "media with a Content-Length that is not a number → 400")
# a body that stops short: the temp file existed, and must be gone
rec2 = session_obj("s-rec02", "P07", recording=True)
s_, j_ = post_session(rec2)
check(s_ == 201, "(a second consenting session is stored for the failure cases)")
URL_M2 = "/__pb_research/%s/media?session=s-rec02&kind=screen" % SID
st_x, _h, j_, closed = raw_exchange("POST", URL_M2, ["Content-Length: 500000"], webm(1000), half_close=True)
check(st_x == 400 and "incomplete" in j_.get("error", ""), "a recording cut off mid-body → 400 incomplete")
check(incoming_files() == [], "…and the half-written temp file was removed")
serve.RESEARCH_CHUNK_TIMEOUT = 0.4
try:
    st_x, _h, j_, closed = raw_exchange("POST", URL_M2, ["Content-Length: 500000"], webm(1000))
    check(st_x == 400 and "incomplete" in j_.get("error", ""), "a recording that stalls mid-body is dropped after the piece timeout → 400")
finally:
    serve.RESEARCH_CHUNK_TIMEOUT = 30.0
check(incoming_files() == [], "…and its temp file was removed")
# a busy registry during the store step: 503 and the temp file removed
os.environ["PB_LOCK_TIMEOUT"] = "0.3"
try:
    with serve.pbslice.registry_lock(REG, "research_serve test"):
        s_, j_ = post_media("s-rec02", webm(2048))
    check(s_ == 503, "a held registry lock during the store step → 503 (%s)" % j_.get("error", "")[:40])
finally:
    del os.environ["PB_LOCK_TIMEOUT"]
check(incoming_files() == [] and not any(e.get("session") == "s-rec02" for e in the_study()["evidence"] if e.get("kind") == "recording"),
      "…the temp file removed and nothing stored")
# a big one: three pieces of 1 MiB and a bit, streamed to disk, hashed right
big = webm(3 * 1024 * 1024 + 123)
s_, j_ = post_media("s-rec02", big)
big_eid = j_.get("evidence")
check(s_ == 201 and j_.get("bytes") == len(big) and j_.get("sha256") == sha(big) and big_eid == "e6", "a 3 MiB recording → 201 with the right size and sha256 (%s)" % (big_eid,))
check(incoming_files() == [] and open(path_in("evidence", "e6-s-rec02-screen.webm"), "rb").read() == big, "…stored whole, .incoming/ empty")
# a pilot's recording lands in pilot/
s_, j_ = post_media("s-pilot1", webm(2048, b"pilotbytes"))
check(s_ == 201 and j_.get("evidence") is None, "a pilot's recording → 201 with no evidence id (%s)" % {k: v for k, v in j_.items() if k != "sha256"})
check(os.path.isfile(path_in("pilot", "s-pilot1-screen.webm")) and the_study()["pilots"][0]["media"] == ["memory/research/%s/pilot/s-pilot1-screen.webm" % SID],
      "…in pilot/, listed on the pilot")
# the upload folder replaced by a symlink: refused before a byte is written through it
rec3 = session_obj("s-rec03", "P08", recording=True)
check(post_session(rec3)[0] == 201, "(a third consenting session is stored for the symlink case)")
inc = path_in(".incoming")
aside = os.path.join(TMP, "incoming-target")
os.makedirs(aside)
os.rmdir(inc)
os.symlink(aside, inc)
s_, j_ = post_media("s-rec03", webm(2048, b"third"))
check(s_ == 400 and "symlink" in j_.get("error", "") and os.listdir(aside) == [], "an .incoming/ that is a symlink → 400, nothing written through it (%s)" % j_.get("error", "")[:50])
os.unlink(inc)
s_, j_ = post_media("s-rec03", webm(2048, b"third"))
check(s_ == 201 and incoming_files() == [], "…and with a real folder again the upload is stored")

# ═════════════════════════════════════════════════════════════════════════════
section("6. evidence GET")
EURL = "/__pb_research/%s/evidence/" % SID
s_, h_, b_ = get(EURL + "e1")
check(s_ == 200 and b_ == GOOD_RAW and h_.get("content-type") == "application/json; charset=utf-8" and h_.get("accept-ranges") == "bytes"
      and h_.get("content-length") == str(len(GOOD_RAW)) and has_security(h_), "a session file: 200, its bytes, application/json, Accept-Ranges, security headers")
N = len(GOOD_RAW)
for rng, status_want, lo, hi in (("bytes=0-9", 206, 0, 9), ("bytes=10-", 206, 10, N - 1), ("bytes=-7", 206, N - 7, N - 1), ("bytes=5-5", 206, 5, 5),
                                 ("bytes=%d-%d" % (N - 3, N + 5000), 206, N - 3, N - 1), ("bytes=-%d" % (N + 99), 206, 0, N - 1)):
    s_, h_, b_ = get(EURL + "e1", headers={"Range": rng})
    check(s_ == status_want and b_ == GOOD_RAW[lo:hi + 1] and h_.get("content-range") == "bytes %d-%d/%d" % (lo, hi, N) and h_.get("content-length") == str(hi - lo + 1),
          "Range %s → 206, bytes %d-%d/%d, the right %d bytes" % (rng, lo, hi, N, hi - lo + 1))
for rng in ("bytes=%d-" % N, "bytes=%d-%d" % (N + 10, N + 20), "bytes=-0"):
    s_, h_, b_ = get(EURL + "e1", headers={"Range": rng})
    check(s_ == 416 and h_.get("content-range") == "bytes */%d" % N and b_ == b"", "Range %s → 416 with Content-Range: bytes */%d" % (rng, N))
for rng in ("bytes=5-2", "bytes=0-1,3-4", "items=0-1", "bytes=zz"):
    s_, h_, b_ = get(EURL + "e1", headers={"Range": rng})
    check(s_ == 200 and b_ == GOOD_RAW and "content-range" not in h_, "Range %s is not a range: the whole file, 200" % rng)
s_, h_, b_ = get(EURL + "e1", headers={"Range": "bytes=0-1"}, host="evil.example")
check(s_ == 403, "…and a foreign Host is still a 403 with a Range")

# the 3 MiB recording: whole, and a range that crosses the 1 MiB read boundary
s_, h_, b_ = get(EURL + big_eid)
check(s_ == 200 and h_.get("content-type") == "video/webm" and len(b_) == len(big) and sha(b_) == sha(big), "the 3 MiB recording: 200, video/webm, streamed whole and identical")
lo, hi = 1024 * 1024 - 10, 1024 * 1024 + 20
s_, h_, b_ = get(EURL + big_eid, headers={"Range": "bytes=%d-%d" % (lo, hi)})
check(s_ == 206 and b_ == big[lo:hi + 1] and h_.get("content-range") == "bytes %d-%d/%d" % (lo, hi, len(big)), "a range across the 1 MiB boundary: exactly those bytes")
s_, h_, b_ = get(EURL + big_eid, headers={"Range": "bytes=%d-" % (len(big) - 1000)})
check(s_ == 206 and b_ == big[-1000:], "an open-ended range near the end")
s_, h_, b_ = get(EURL + media_eid, headers={"Range": "bytes=0-3"})
check(s_ == 206 and b_ == RS.WEBM_MAGIC, "bytes 0-3 of a recording are the WebM magic")
check(len(serve._hashed) >= 2, "(a recording is hashed once, then remembered: %d known)" % len(serve._hashed))

# pilot files
s_, h_, b_ = get(EURL + "pilot-s-pilot1")
check(s_ == 200 and b_ == PIL_RAW and h_.get("content-type") == "application/json; charset=utf-8", "pilot-<sessionId> → the pilot's session file")
s_, h_, b_ = get(EURL + "pilot-s-pilot1-screen", headers={"Range": "bytes=0-3"})
check(s_ == 206 and b_ == RS.WEBM_MAGIC and h_.get("content-type") == "video/webm", "pilot-<sessionId>-screen → the pilot's recording, ranged")
for eid_ in ("pilot-s-nothere", "pilot-s-pilot1-audio", "pilot-s-pilot1-screen-screen", "pilot-", "pilot-../x"):
    check(get(EURL + eid_)[0] == 404, "%s → 404" % eid_)

# what is not served
for eid_, why in (("e99", "evidence that is not there"), ("e1x", "an id with a tail"), ("E1", "upper case"), ("..%2f..%2fregistry.json", "an encoded traversal"),
                  ("e1%2f..%2f..%2fregistry.json", "an encoded traversal after a real id"), ("%65%31", "a percent-escaped id")):
    check(get(EURL + eid_)[0] == 404, "evidence %s → 404 (%s)" % (eid_, why))
d = reg_data()
stu = d["research"]["studies"][0]
stu["evidence"].append({"id": "e50", "file": "memory/research/%s/evidence/e50-notes.txt" % SID, "kind": "notes", "sha256": sha(b"x"), "dropped": None})
stu["evidence"].append({"id": "e51", "file": "memory/research/%s/evidence/../../../../registry.json" % SID, "kind": "session", "sha256": sha(b"x"), "dropped": None})
stu["evidence"].append({"id": "e52", "file": "memory/research/rs-other/evidence/e52-s-xxxx1.json", "kind": "session", "sha256": sha(b"x"), "dropped": None})
stu["evidence"].append({"id": "e53", "file": "memory/research/%s/evidence/e1-s-aaaa1.json" % SID, "kind": "session", "sha256": "not-a-hash", "dropped": None})
stu["evidence"].append({"id": "e54", "file": "memory/research/%s/evidence/e1-s-aaaa1.json" % SID, "kind": "session", "sha256": sha(GOOD_RAW), "dropped": {"at": "x"}})
stu["evidence"].append({"id": "e55", "file": "memory/research/%s/evidence/e55-s-ghost1.json" % SID, "kind": "session", "sha256": sha(b"x"), "dropped": None})
reg_save(d)
check(get(EURL + "e50")[0] == 404, "a row of a kind that is not a session or a recording is not served")
s_, h_, b_ = get(EURL + "e51")
check(s_ == 409, "a row whose file climbs out of the evidence folder → 409, nothing served (%s)" % s_)
check(b"pb-session" not in get(EURL + "e51")[2] and b'"research"' not in get(EURL + "e51")[2], "…and the registry's bytes are not in the answer")
check(get(EURL + "e52")[0] == 409, "a row whose file is in another study's folder → 409")
check(get(EURL + "e53")[0] == 409, "a row with no usable sha256 → 409 (nothing is served that cannot be checked)")
check(get(EURL + "e54")[0] == 404, "a dropped row (a participant withdrew) → 404")
check(get(EURL + "e55")[0] == 404, "a row whose file is gone → 404")
d = reg_data()
d["research"]["studies"][0]["evidence"] = [e for e in d["research"]["studies"][0]["evidence"] if e["id"] not in ("e50", "e51", "e52", "e53", "e54", "e55")]
reg_save(d)

# the file changed after import, a symlink in its place
orig = open(f1, "rb").read()
os.chmod(f1, 0o644)
with open(f1, "ab") as f:
    f.write(b" ")
s_, h_, b_ = get(EURL + "e1")
check(s_ == 409 and "sha256" in jbody(b_).get("error", "") and GOOD_RAW not in b_, "a session file changed after import → 409, naming the sha256, not served")
s_, h_, b_ = get(EURL + "e1", headers={"Range": "bytes=0-9"})
check(s_ == 409, "…also for a Range request")
with open(f1, "wb") as f:
    f.write(orig)
os.chmod(f1, 0o444)
check(get(EURL + "e1")[0] == 200, "…and served again once it is what was recorded")
os.rename(f1, f1 + ".away")
check(get(EURL + "e1")[0] == 404, "a missing file → 404")
os.symlink(os.path.join(PROJ, "registry.json"), f1)
s_, h_, b_ = get(EURL + "e1")
check(s_ == 409 and b'"research"' not in b_, "a symlink in its place → 409, and its target is not read")
os.unlink(f1)
os.rename(f1 + ".away", f1)
check(get(EURL + "e1")[0] == 200, "(restored)")
os.chmod(f_rec, 0o644)
with open(f_rec, "r+b") as f:
    f.seek(100)
    f.write(b"X")
os.chmod(f_rec, 0o444)
check(get(EURL + media_eid)[0] == 409, "a recording changed after import → 409")
os.chmod(f_rec, 0o644)
with open(f_rec, "wb") as f:
    f.write(body_small)
os.chmod(f_rec, 0o444)

# the evidence folder itself replaced by a symlink to elsewhere: the one realpath guard refuses it
ev_dir = path_in("evidence")
os.rename(ev_dir, ev_dir + ".real")
elsewhere = os.path.join(TMP, "elsewhere")
shutil.copytree(ev_dir + ".real", elsewhere)
os.symlink(elsewhere, ev_dir)
s_, h_, b_ = get(EURL + "e1")
check(s_ == 409, "an evidence folder that is a symlink to somewhere else → 409, not served")
os.unlink(ev_dir)
os.rename(ev_dir + ".real", ev_dir)
check(get(EURL + "e1")[0] == 200, "(restored)")

# ═════════════════════════════════════════════════════════════════════════════
section("7. replay and report")
s_, h_, b_ = get("/research/%s/replay/e1" % SID)
html = b_.decode("utf-8", "replace")
check(s_ == 200 and "window.PB_RS_REPLAY=" in html and "/*STUB-REPLAY*/" in html and '"eid":"e1"' in html and "s-aaaa1" in html, "replay of e1 → 200 with the stored session inlined")
clean_page(html, "replay")
s_, h_, b_ = get("/research/%s/replay/%s" % (SID, rec_eid))
html = b_.decode("utf-8", "replace")
check(s_ == 200 and ("/__pb_research/%s/evidence/%s" % (SID, media_eid)) in html, "replay of a recorded session lists its recording's evidence URL")
s_, h_, b_ = get("/research/%s/replay/pilot-s-pilot1" % SID)
html = b_.decode("utf-8", "replace")
check(s_ == 200 and "pilot-s-pilot1-screen" in html, "replay of a pilot → 200, with the pilot's recording URL")
clean_page(html, "pilot replay")
check(get("/research/%s/replay/e2" % SID)[0] == 200, "(another session replays)")
set_study(evidence=[dict(e, dropped={"at": "x"}) if e["id"] == "e2" else e for e in the_study()["evidence"]])
check(get("/research/%s/replay/e2" % SID)[0] == 404, "replay of a dropped session → 404")

s_, h_, b_ = get("/research/%s/report" % SID)
html = b_.decode("utf-8", "replace")
check(s_ == 404 and ("research.py report %s" % SID) in html and "EventSource" not in html and "<script" not in html,
      "no report yet → a 404 page that names `research.py report %s`, with no script and no reload client" % SID)
rep_dir = path_in("report")
os.makedirs(rep_dir)
REPORT = "<!doctype html><html><head><title>Report</title></head><body><h1>Report marker</h1></body></html>"
with open(os.path.join(rep_dir, "report.html"), "w", encoding="utf-8") as f:
    f.write(REPORT)
s_, h_, b_ = get("/research/%s/report" % SID)
check(s_ == 200 and b_.decode("utf-8") == REPORT and h_.get("content-type", "").startswith("text/html") and has_security(h_), "the report is written → 200, the file as it is, security headers")
os.unlink(os.path.join(rep_dir, "report.html"))
os.symlink(REG, os.path.join(rep_dir, "report.html"))
s_, h_, b_ = get("/research/%s/report" % SID)
check(s_ == 404 and b'"research"' not in b_, "a report.html that is a symlink is not read (404)")
os.unlink(os.path.join(rep_dir, "report.html"))
with open(os.path.join(rep_dir, "report.html"), "w", encoding="utf-8") as f:
    f.write(REPORT)
os.rename(rep_dir, rep_dir + ".real")
os.symlink(rep_dir + ".real", rep_dir)
check(get("/research/%s/report" % SID)[0] == 404, "a report/ folder that is a symlink is not followed (404)")
os.unlink(rep_dir)
os.rename(rep_dir + ".real", rep_dir)
check(get("/research/%s/report" % SID)[0] == 200, "(restored)")
check(get("/research/rs-nope/report")[0] == 404, "the report of a study that does not exist → 404")

# ═════════════════════════════════════════════════════════════════════════════
section("8. hygiene")
for p in ("/memory/research/%s/evidence/e1-s-aaaa1.json" % SID, "/memory/research/%s/.incoming/x" % SID):
    check(get(p)[0] == 403, "%s is still not a static file (403)" % p[:50])
check(get("/")[0] == 200, "the prototype at / still answers")
check(get("/__pb_health")[0] == 200, "/__pb_health still answers")
check(get("/design-system")[0] in (200, 500), "/design-system still routes")
check(not [ln for ln in LOG if "Traceback" in ln], "no traceback in the server's log (%d lines)" % len(LOG))
unexpected = [ln for ln in LOG if "research upload failed" in ln or "research page" in ln]
check(not unexpected, "…and no request fell through to the catch-all (%s)" % [u[:60] for u in unexpected])
check(incoming_files() == [], "…and no temp upload is left in .incoming/")

httpd.shutdown()
shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL — %d check(s):" % len(fails))
    for m in fails:
        print("   - " + m)
    sys.exit(1)
print("PASS — research session routes: loopback only, hardened doors, sha-checked ranged evidence, streamed uploads.")
