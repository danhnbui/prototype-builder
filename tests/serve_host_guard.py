#!/usr/bin/env python3
"""
serve_host_guard.py — the preview server answers only requests that are meant for it, and serves only assets.

A server on 127.0.0.1 is reachable by any web page in the same browser: a page on another site whose
name resolves to 127.0.0.1 (DNS rebinding) arrives with ITS name in the Host header and the browser lets
it read the answer. Until now only POST /api/meta looked at Host — GET handed back `/.git/config`,
`/registry.json` and `/memory/decisions.md` to any Host, with no security headers. Now:

  1. host guard     every route (the pages, /__pb_health, /__pb_events, static files) and both POSTs answer a
                    Host that does not name the server with a 403 that names `--allow-host`; 127.0.0.1,
                    localhost and [::1] are accepted with or without a port; a request with no Host is
                    accepted from this machine only; two Host headers are refused; what is echoed back is
                    printable ASCII and short; a refused request is not "use" (idle clock untouched)
  2. --allow-host   a name given with the flag is accepted (any case), nothing else is, and POST stays
                    loopback-only — the flag never lets a foreign name write; a name with a port, a
                    wildcard or a scheme is a usage error
  3. static files   assets only: a dot-named part (.git, .env), memory/, the registry and the lock beside
                    it are 403 — judged on the RESOLVED path (`..`, a symlink, any letter case), whether or
                    not the file exists; /public/a.txt still works; so do page rounds under /explore/<id>/…
  4. headers        every response carries nosniff, no-referrer, X-Frame-Options SAMEORIGIN and
                    Cross-Origin-Resource-Policy same-origin
  5. units          host_name, parse_allow_host, allowed_hosts, host_warning (the startup line for a --host
                    beyond this machine), stable_port

Stdlib only, no browser, never a fixed port (the servers bind port 0). Builds from a temp copy of
fixtures/golden and cleans up every process it starts.  Usage:  python3 tests/serve_host_guard.py
Exit: 0 pass · 1 fail
"""
import email.message
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SERVE = os.path.join(ROOT, "pb", "tools", "serve.py")
GOLDEN_DIR = os.path.join(ROOT, "fixtures", "golden")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import serve  # noqa: E402
import explore  # noqa: E402

_fail = []
_procs = []
_dirs = []

HEADERS = {"x-content-type-options": "nosniff", "referrer-policy": "no-referrer",
           "x-frame-options": "SAMEORIGIN", "cross-origin-resource-policy": "same-origin"}


def check(cond, msg):
    print("  %s %s" % ("✓" if cond else "✗", msg))
    if not cond:
        _fail.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def project():
    """A temp copy of the golden project with the files a leak would hand out."""
    d = tempfile.mkdtemp(prefix="pb-host-guard-")
    _dirs.append(d)
    proj = os.path.join(d, "proj")
    shutil.copytree(GOLDEN_DIR, proj, ignore=shutil.ignore_patterns(".preview"))
    write(os.path.join(proj, ".git", "config"), "[remote \"origin\"]\n\turl = https://example.invalid/secret.git\n")
    write(os.path.join(proj, ".env"), "TOKEN=hunter2\n")
    write(os.path.join(proj, "memory", "x.md"), "# a private note\n")
    write(os.path.join(proj, "public", "a.txt"), "asset-bytes\n")
    write(os.path.join(proj, "public", ".secret"), "hidden\n")
    write(os.path.join(proj, "registry.json.lock"), "")
    return os.path.join(proj, "registry.json")


class Server:
    """serve.py on a registry, port 0, its output collected by a thread so the pipe never fills."""

    def __init__(self, reg, *args):
        self.reg = reg
        self.lines = []
        self.url = None
        self.proc = subprocess.Popen([sys.executable, SERVE, reg, "--no-open", "--port", "0"] + list(args),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        _procs.append(self.proc)
        threading.Thread(target=self._pump, daemon=True).start()
        deadline = time.time() + 15
        while time.time() < deadline and not self.url and self.proc.poll() is None:
            time.sleep(0.02)
            for ln in list(self.lines):
                m = re.search(r"(http://127\.0\.0\.1:(\d+)/)", ln)
                if m:
                    self.url, self.port = m.group(1), int(m.group(2))
                    break
        if not self.url:
            raise RuntimeError("serve.py did not report a preview URL: %s" % "".join(self.lines)[-400:])

    def _pump(self):
        for ln in self.proc.stdout:
            self.lines.append(ln)

    def log(self):
        time.sleep(0.2)
        return "".join(self.lines)

    def req(self, method, path, host="default", headers=None, body=None, timeout=10):
        """→ (status, {lower-case header: value}, body text). host "default" = this server's own 127.0.0.1:port."""
        hdrs = dict(headers or {})
        hdrs["Host"] = "127.0.0.1:%d" % self.port if host == "default" else host
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(method, path, body=body, headers=hdrs)
            r = conn.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read().decode("utf-8", "replace")
        finally:
            conn.close()

    def get(self, path, host="default", **kw):
        return self.req("GET", path, host, **kw)

    def raw(self, data, timeout=5):
        """Send bytes as they are → (status, lower-case headers, body). For requests http.client will not build."""
        s = socket.create_connection(("127.0.0.1", self.port), timeout=timeout)
        try:
            s.sendall(data)
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
            head, _, rest = buf.partition(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            status = int(lines[0].split()[1]) if lines and len(lines[0].split()) > 1 else 0
            hdrs = {}
            for ln in lines[1:]:
                k, _, v = ln.partition(":")
                hdrs[k.strip().lower()] = v.strip()
            n = int(hdrs.get("content-length", "0") or 0)
            s.settimeout(1)
            try:
                while len(rest) < n:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    rest += chunk
            except (socket.timeout, OSError):
                pass
            return status, hdrs, rest.decode("utf-8", "replace")
        finally:
            s.close()

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main():
    reg = project()
    proj = os.path.dirname(reg)

    print("1 · a foreign Host is refused on every route; a refused request is not use")
    a = Server(reg)
    st, _h, body = a.get("/__pb_health")
    idle0 = json.loads(body)["idleSeconds"]
    check(st == 200, "(the server answers its own Host: 127.0.0.1:port)")
    time.sleep(2.3)
    for host in ("evil.example", "evil.example:%d" % a.port):
        for path in ("/", "/design-system", "/explore", "/__pb_health", "/__pb_events", "/public/a.txt", "/index.html", "/favicon.ico"):
            st, h, body = a.get(path, host=host)
            check(st == 403 and h.get("content-type", "").startswith("text/plain"),
                  "GET %s with Host %s → 403 text/plain (%s)" % (path, host, st))
        st, h, body = a.get("/", host=host)
        check("--allow-host evil.example" in body and "refused unknown Host evil.example" in body,
              "the refusal names the flag and the host: %r" % body[:140])
    for path in ("/api/meta", "/__pb_explore/x/scores", "/nowhere"):
        st, h, body = a.req("POST", path, host="evil.example",
                            headers={"Origin": "http://evil.example", "Content-Type": "application/json"}, body='{"a":1}')
        try:
            said = json.loads(body)
        except ValueError:
            said = {}
        check(st == 403 and said.get("ok") is False and "--allow-host evil.example" in said.get("error", "")
              and h.get("connection", "").lower() == "close",
              "POST %s with a foreign Host → 403, the sentence naming the flag in the {ok, error} the page reads, connection closed (%s)" % (path, st))
    st, _h, body = a.get("/__pb_health")
    idle1 = json.loads(body)["idleSeconds"]
    check(idle1 >= 2 and idle1 >= idle0 + 2,
          "none of those counted as use: idleSeconds kept growing through them (%s → %s)" % (idle0, idle1))

    print("   what is echoed back")
    st, _h, body = a.raw(b"GET / HTTP/1.1\r\nHost: bad name\x01\x1b[31m<script>alert(1)</script>\r\n\r\n")
    check(st == 403 and "\x01" not in body and "\x1b" not in body and "<" not in body and ">" not in body,
          "control characters and markup in the Host are not echoed (%r)" % body[:120])
    st, _h, body = a.get("/", host="a" * 3000)
    check(st == 403 and len(body) < 400, "a very long Host is cut before it is echoed (%d bytes back)" % len(body))
    st, _h, body = a.raw(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nHost: evil.example\r\n\r\n")
    check(st == 403 and "more than one Host" in body, "two Host headers are refused (%s)" % st)
    st, _h, body = a.raw(b"GET / HTTP/1.1\r\nHost: 127.0.0.1:80@evil.example\r\n\r\n")
    check(st == 403, "a Host that is not a plain host[:port] is refused (%s)" % st)

    print("2 · the names that are this server's work, with or without a port")
    for host in ("127.0.0.1:%d" % a.port, "127.0.0.1", "localhost:%d" % a.port, "localhost", "LOCALHOST:%d" % a.port,
                 "[::1]:%d" % a.port, "[::1]"):
        st, _h, body = a.get("/", host=host)
        check(st == 200 and "<html" in body[:2000].lower(), "GET / with Host %s → 200" % host)
    for path in ("/design-system", "/explore", "/__pb_health", "/public/a.txt"):
        st, _h, _b = a.get(path, host="localhost:%d" % a.port)
        check(st == 200, "GET %s with Host localhost:port → 200" % path)
    s = socket.create_connection(("127.0.0.1", a.port), timeout=5)
    s.sendall(("GET /__pb_events HTTP/1.1\r\nHost: localhost:%d\r\nAccept: text/event-stream\r\n\r\n" % a.port).encode())
    head = s.recv(4096).decode("latin-1")
    check(head.startswith("HTTP/1.1 200") and "text/event-stream" in head and "X-Frame-Options: SAMEORIGIN" in head,
          "/__pb_events opens for a good Host (and carries the headers)")
    s.close()
    st, _h, body = a.raw(b"GET /public/a.txt HTTP/1.0\r\n\r\n")
    check(st == 200 and "asset-bytes" in body, "a request with no Host is accepted from this machine (loopback peer)")

    print("3 · static files are assets only")
    for path in ("/.git/config", "/.env", "/memory/x.md", "/MEMORY/x.md", "/Memory/X.MD", "/memory", "/memory/",
                 "/registry.json", "/REGISTRY.JSON", "/Registry.Json", "/registry.json.lock", "/public/.secret",
                 "/./.git/config", "/public/../.git/config", "/public/../memory/x.md", "/public/../registry.json",
                 "/.git/nope", "/memory/nope.md", "/.preview/server.json", "/.claude/launch.json"):
        st, _h, body = a.get(path)
        check(st == 403 and "forbidden" in body, "GET %s → 403, whether or not it exists (%s)" % (path, st))
    for path in ("/%2Egit/config", "/..%2F..%2Fetc%2Fpasswd", "/%2e%2e/%2e%2e/etc/passwd", "/public/%2e%2e/.env",
                 "/..%5C..%5Cetc%5Cpasswd", "/%00", "/public/a.txt%00.png"):
        st, _h, body = a.get(path)
        check(st != 200 and "hunter2" not in body and "secret.git" not in body and "root:" not in body,
              "GET %s → not served (%s)" % (path, st))
    try:
        os.symlink(os.path.join("..", "memory", "x.md"), os.path.join(proj, "public", "to-memory.txt"))
        os.symlink("/etc/hosts", os.path.join(proj, "public", "to-outside.txt"))
        os.symlink("a.txt", os.path.join(proj, "public", "to-asset.txt"))
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    if linked:
        st, _h, body = a.get("/public/to-memory.txt")
        check(st == 403 and "private note" not in body, "a symlink into memory/ is judged by where it lands → 403 (%s)" % st)
        st, _h, body = a.get("/public/to-outside.txt")
        check(st == 403, "a symlink out of the project → 403 (%s)" % st)
        st, _h, body = a.get("/public/to-asset.txt")
        check(st == 200 and "asset-bytes" in body, "a symlink to an asset still works")
    st, _h, body = a.get("/public/a.txt")
    check(st == 200 and body == "asset-bytes\n", "/public/a.txt is served")
    st, _h, body = a.get("/render/screens/login.js")
    check(st == 200 and len(body) > 10, "…and so is a file under render/ (not a protected name)")
    st, _h, _b = a.get("/public/missing.png")
    check(st == 404, "a missing asset is still a 404")

    print("   page rounds are their own route, and do not depend on memory/ being servable")
    explore.cmd_init(reg, "rt", options=2, pages=True, intent="a page round")
    write(os.path.join(proj, "memory", "explore", "rt", "opt-1", "index.html"), "<!doctype html><title>one</title><p>round page one</p>")
    write(os.path.join(proj, "memory", "explore", "rt", "shared", "base.css"), "body{margin:0}")
    st, _h, body = a.get("/explore/rt/opt-1/index.html")
    check(st == 200 and "round page one" in body, "/explore/rt/opt-1/index.html → 200")
    st, _h, body = a.get("/explore/rt/shared/base.css")
    check(st == 200 and "margin:0" in body, "…and its ../shared/ stylesheet")
    st, _h, body = a.get("/explore/rt")
    check(st == 200 and '"mode":"pages"' in body, "/explore/<id> still renders the compare page")
    st, _h, _b = a.get("/memory/explore/rt/opt-1/index.html")
    check(st == 403, "…but the same file is not reachable as a static path (%s)" % st)
    st, _h, _b = a.get("/explore/rt/%2e%2e/%2e%2e/%2e%2e/registry.json")
    check(st == 403, "a page round's path still cannot climb out of its folder (%s)" % st)

    print("4 · security headers on every response")
    probes = [("GET", "/"), ("GET", "/design-system"), ("GET", "/explore"), ("GET", "/explore/rt"), ("GET", "/explore/rt/opt-1/index.html"),
              ("GET", "/__pb_health"), ("GET", "/public/a.txt"), ("GET", "/public/missing.png"), ("GET", "/.git/config"),
              ("GET", "/favicon.ico"), ("POST", "/api/meta"), ("POST", "/nowhere")]
    for method, path in probes:
        st, h, _b = a.req(method, path, headers={"Content-Length": "0"} if method == "POST" else None)
        missing = [k for k, v in HEADERS.items() if h.get(k) != v]
        check(not missing, "%s %s (%s) carries all four%s" % (method, path, st, " — missing/wrong: %s" % missing if missing else ""))
    st, h, _b = a.get("/", host="evil.example")
    check(all(h.get(k) == v for k, v in HEADERS.items()), "…and so does a Host refusal")
    st, h, _b = a.get("/explore/rt/opt-2")
    check(all(h.get(k) == v for k, v in HEADERS.items()), "…and the answer for a bare slot inside /explore (%s)" % st)
    man = explore.load_manifest(proj, "rt")
    man["options"][1]["page"] = "opt-2/inspector.html"
    explore.save_manifest(proj, man)
    st, h, _b = a.get("/explore/rt/opt-2")
    check(st == 302 and all(h.get(k) == v for k, v in HEADERS.items()), "…and the redirect to a slot's page (%s)" % st)

    print("5 · --allow-host: that name works, any case; writes stay with this machine")
    reg2 = project()
    b = Server(reg2, "--allow-host", "foo.local", "--allow-host", "Tunnel.Example")
    for host in ("foo.local", "foo.local:%d" % b.port, "FOO.LOCAL", "tunnel.example:8443"):
        st, _h, body = b.get("/", host=host)
        check(st == 200 and "<html" in body[:2000].lower(), "GET / with Host %s → 200" % host)
    for host in ("bar.local", "foo.local.evil.example", "evil.foo.local"):
        st, _h, _b = b.get("/", host=host)
        check(st == 403, "Host %s is still refused (%s)" % (host, st))
    st, _h, body = b.get("/.git/config", host="foo.local")
    check(st == 403, "an allowed name does not unlock project internals (%s)" % st)
    before = open(reg2, encoding="utf-8").read()
    payload = json.dumps({"name": "Renamed", "designSystem": {"name": "DS", "designLink": ""}})
    st, _h, body = b.req("POST", "/api/meta", host="foo.local:%d" % b.port,
                         headers={"Origin": "http://foo.local:%d" % b.port, "Content-Type": "application/json"}, body=payload)
    check(st == 403 and "loopback" in body, "POST /api/meta with the allowed Host and its own Origin is still refused: %s" % body[:80])
    st, _h, body = b.req("POST", "/__pb_explore/x/scores", host="foo.local:%d" % b.port,
                         headers={"Origin": "http://foo.local:%d" % b.port, "Content-Type": "application/json"}, body="{}")
    check(st == 403 and "loopback" in body, "…so is the score save (%s)" % st)
    check(open(reg2, encoding="utf-8").read() == before, "…and registry.json is untouched")
    st, _h, body = b.req("POST", "/api/meta", headers={"Origin": "http://127.0.0.1:%d" % b.port, "Content-Type": "application/json"},
                         body=payload)
    check(st == 200 and json.loads(body).get("ok") is True, "the same save from the loopback Host still works (%s)" % st)
    log = b.log()
    check(re.search(r"hosts +also answering Host foo\.local, tunnel\.example", log) is not None, "the banner lists the --allow-host names")
    b.stop()

    for bad in ("foo.local:8080", "*.local", "http://foo.local", "foo.local/x", "", "foo bar", "-x.local"):
        r = subprocess.run([sys.executable, SERVE, reg2, "--allow-host", bad], capture_output=True, text=True, timeout=30)
        check(r.returncode == 2 and "allow-host" in r.stderr, "--allow-host %r is a usage error (exit %d)" % (bad, r.returncode))

    print("6 · units")
    check(serve.host_name("Example.COM:8080") == "example.com" and serve.host_name("[::1]:9") == "[::1]"
          and serve.host_name("localhost") == "localhost" and serve.host_name("localhost:") == "localhost",
          "host_name: lower-cased, port dropped, IPv6 literal kept bracketed")
    check(all(serve.host_name(x) is None for x in ("", None, "a b", "a:b:c", "x@y", "x/y", "evil.example:80@127.0.0.1", "[::1", ":80", "a:123456")),
          "host_name: anything that is not host[:port] is None")
    check(serve.parse_allow_host(" Foo.Local ") == "foo.local" and serve.parse_allow_host("fd00::1") == "[fd00::1]"
          and serve.parse_allow_host("[fd00::1]") == "[fd00::1]" and serve.parse_allow_host("192.168.1.5") == "192.168.1.5",
          "parse_allow_host: names, an IPv4 address and an IPv6 literal")
    check(serve.allowed_hosts("127.0.0.1") == frozenset(serve.LOOPBACK_HOSTS), "allowed_hosts: a loopback bind adds nothing")
    check(serve.allowed_hosts("0.0.0.0") == frozenset(serve.LOOPBACK_HOSTS) and serve.allowed_hosts("") == frozenset(serve.LOOPBACK_HOSTS),
          "allowed_hosts: a wildcard bind names no Host of its own")
    check(serve.allowed_hosts("192.168.1.5", ["foo.local"]) == frozenset(serve.LOOPBACK_HOSTS) | {"192.168.1.5", "foo.local"},
          "allowed_hosts: the concrete bound address plus each --allow-host")
    w = serve.host_warning("0.0.0.0", serve.allowed_hosts("0.0.0.0", ["foo.local"]))
    check(w and "reaches beyond this machine" in w and "--allow-host" in w and "foo.local" in w and "0.0.0.0" in w,
          "host_warning: a --host beyond this machine gets a startup line naming the flag (%s)" % (w or "")[:90])
    check(serve.host_warning("127.0.0.1", serve.allowed_hosts("127.0.0.1")) is None
          and serve.host_warning("localhost", serve.allowed_hosts("localhost")) is None, "host_warning: none for a loopback bind")

    class Fake:
        hosts = frozenset(serve.LOOPBACK_HOSTS)
        command = "GET"

        def __init__(self, peer, *host_values):
            self.client_address = (peer, 50000)
            self.headers = email.message.Message()
            for v in host_values:
                self.headers["Host"] = v
            self.sent = []

        def _send(self, body, ctype="", status=200, close=False):
            self.sent.append((status, body.decode(), close))

    for peer, hosts, refused in (("127.0.0.1", (), False), ("::1", (), False), ("10.0.0.5", (), True), ("203.0.113.9", ("localhost",), False),
                                 ("10.0.0.5", ("evil.example",), True), ("127.0.0.1", ("127.0.0.1", "localhost"), True)):
        f = Fake(peer, *hosts)
        got = serve.Handler._refuse_host(f)
        check(got is refused and (bool(f.sent) is refused) and (not f.sent or (f.sent[0][0] == 403 and f.sent[0][2] is True)),
              "_refuse_host: peer %s, Host %s → %s" % (peer, list(hosts) or "(none)", "403, closed" if refused else "let through"))

    p1 = serve.stable_port(reg)
    check(serve.PORT_BASE <= p1 < serve.PORT_BASE + serve.PORT_SPAN and p1 == serve.stable_port(reg) == serve.stable_port(os.path.relpath(reg)),
          "stable_port: in %d–%d, the same on every call, from the real path (%d)" % (serve.PORT_BASE, serve.PORT_BASE + serve.PORT_SPAN - 1, p1))
    ports = {serve.stable_port("/projects/p%d/registry.json" % i) for i in range(200)}
    check(len(ports) > 100, "stable_port: 200 projects spread over %d ports" % len(ports))
    if linked:
        alias = os.path.join(os.path.dirname(proj), "alias")
        os.symlink(proj, alias)
        check(serve.stable_port(os.path.join(alias, "registry.json")) == p1, "stable_port: a symlinked project folder gets the same port")

    a.stop()
    print()
    if _fail:
        print("✗ %d failure(s)." % len(_fail))
        for m in _fail:
            print("   - " + m)
        return 1
    print("✓ preview server: foreign Hosts refused everywhere, project internals never served, headers on every response.")
    return 0


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    finally:
        for p in _procs:
            if p.poll() is None:
                p.terminate()
        for p in _procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        for d in _dirs:
            shutil.rmtree(d, ignore_errors=True)
    sys.exit(rc)
