#!/usr/bin/env python3
"""
serve_idle.py — the /pb:preview server looks after its own footprint (resource hygiene, WP-B).

A preview server used to run until somebody killed it, poll the disk every 0.3 s forever, reload a
browser once per file write of a burst, and could only be ended with `kill`. Now:

  1. idle exit     a server started with a tiny --idle-exit stops by itself and takes its
                   .preview/server.json record with it; a connected tab (an open /__pb_events
                   stream) keeps it alive, and it stops once the stream closes; --idle-exit 0 never stops
  2. coalescing    10 saves 30 ms apart → exactly one `reload` event; one save → one, within 1 s;
                   --debounce-ms 0 still reloads
  3. never stale   after 2 s with nobody connected, a save followed at once by GET / returns the new page
  4. poll rate     0.3 s while a tab is connected or a request is recent, 2 s otherwise (unit)
  5. health        /__pb_health gains clients, idleSeconds, startedAt beside its existing keys; a health
                   probe is not activity
  6. --status/--stop  the round trip (and the registry argument omitted = ./registry.json); --stop
                   never signals a record whose health check names another registry, nor a pid that is
                   not the one that answered, and --status / --stop never start a server
  7. slot cache    a rendered option of an exploration that is no longer open is dropped when the version bumps
  9. default       the idle exit defaults to 480 minutes (8 h) — 30 lost people their preview mid-afternoon —
                   and --idle-exit / $PB_PREVIEW_IDLE_MIN still set it
 10. --ensure      the one idempotent start: twice gives one pid and one URL (the second starts nothing), JSON
                   {url, pid, started}, the server outlives the command that started it, --shell / --idle-exit /
                   --allow-host are handed on, a server that cannot start is exit 3 with the message; with no
                   --port the project gets its own stable port
 11. the cap       at most $PB_PREVIEW_MAX managed servers (--ensure, explore.py link); starting one more stops
                   the longest-idle server with no tab open — never one with an open event stream — and says so;
                   when every other has a tab, nothing is stopped and the new one starts anyway
 12. who counts    a plain serve.py, a direct explore._start_server and so the private servers shot.py and
                   test_run.py boot never register and never evict; `explore.py link` does register

Stdlib only, no browser, never a fixed port but the one test of the project's own port (the other servers
bind port 0; every managed-server folder is a temp one via PB_PREVIEW_DIR, so this test never reads or
stops a real preview). Builds from a temp copy of fixtures/golden and cleans up every process it starts,
the detached ones with `serve.py --stop`.  Usage:  python3 tests/serve_idle.py
Exit: 0 pass · 1 fail
"""
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
_procs = []      # every process this test starts, killed in the end
_dirs = []       # every temp folder, removed in the end
_ensured = []    # registries of detached servers (--ensure / link): stopped with `serve.py --stop` in the end
T0 = time.time()


def check(cond, msg):
    print("  %s %s" % ("✓" if cond else "✗", msg))
    if not cond:
        _fail.append(msg)


def project():
    """A fresh temp copy of the golden project → registry.json path."""
    d = tempfile.mkdtemp(prefix="pb-serve-idle-")
    _dirs.append(d)
    dst = os.path.join(d, "proj")
    shutil.copytree(GOLDEN_DIR, dst, ignore=shutil.ignore_patterns(".preview"))
    return os.path.join(dst, "registry.json")


def set_name(reg_path, name):
    """Change the project name the way a tool does: a temp file renamed over registry.json."""
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
    reg.setdefault("meta", {})["name"] = name
    tmp = reg_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f)
    os.replace(tmp, reg_path)


class Proc:
    """serve.py on a registry, with its output collected by a thread so the pipe never fills."""

    def __init__(self, reg_path, *args, cwd=None, env=None):
        self.reg = reg_path
        self.lines = []
        self.url = None
        self.proc = subprocess.Popen([sys.executable, SERVE, reg_path, "--no-open", "--port", "0"] + list(args),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=cwd, env=env)
        _procs.append(self.proc)
        threading.Thread(target=self._pump, daemon=True).start()
        deadline = time.time() + 15
        while time.time() < deadline and not self.url and self.proc.poll() is None:
            time.sleep(0.02)
            for ln in list(self.lines):
                m = re.search(r"(http://127\.0\.0\.1:\d+/)", ln)
                if m:
                    self.url = m.group(1)
                    break
        if not self.url:
            raise RuntimeError("serve.py did not report a preview URL: %s" % "".join(self.lines)[-400:])

    def _pump(self):
        for ln in self.proc.stdout:
            self.lines.append(ln)

    @property
    def record(self):
        return os.path.join(os.path.dirname(self.reg), ".preview", "server.json")

    @property
    def hostport(self):
        return self.url.split("//", 1)[1].rstrip("/")

    def alive(self):
        return self.proc.poll() is None

    def wait_exit(self, seconds):
        try:
            self.proc.wait(timeout=seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def log(self):
        time.sleep(0.2)   # let the pump drain
        return "".join(self.lines)

    def get(self, path="/", timeout=10):
        conn = http.client.HTTPConnection(self.hostport, timeout=timeout)
        try:
            conn.request("GET", path)
            r = conn.getresponse()
            return r.status, r.read().decode("utf-8", "replace")
        finally:
            conn.close()

    def health(self):
        st, body = self.get("/__pb_health")
        return json.loads(body) if st == 200 else None


class Events:
    """An open /__pb_events stream on a raw socket: counts `reload` events and notes when they arrive."""

    def __init__(self, proc):
        host, port = proc.hostport.rsplit(":", 1)
        self.sock = socket.create_connection((host, int(port)), timeout=10)
        self.sock.sendall(("GET /__pb_events HTTP/1.1\r\nHost: %s\r\nAccept: text/event-stream\r\n\r\n" % proc.hostport).encode())
        self.reloads = []     # monotonic timestamps
        self.connected = threading.Event()
        self._buf = b""
        threading.Thread(target=self._read, daemon=True).start()
        self.connected.wait(5)

    def _read(self):
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    return
                self._buf += chunk
                while b"\n\n" in self._buf:
                    block, self._buf = self._buf.split(b"\n\n", 1)
                    if b": connected" in block:
                        self.connected.set()
                    if b"data: reload" in block:
                        self.reloads.append(time.monotonic())
        except OSError:
            return

    def close(self):
        # shutdown() first: on Linux a close() while the reader thread is blocked in recv() leaves the
        # socket open in the kernel, so no FIN reaches the server — a closed browser tab does send one.
        for step in (lambda: self.sock.shutdown(socket.SHUT_RDWR), self.sock.close):
            try:
                step()
            except OSError:
                pass


def cli(reg_arg, *args, cwd=None, env=None, split=False):
    """serve.py's one-shot modes → (exit code, stdout + stderr), or (exit code, stdout, stderr) with split."""
    cmd = [sys.executable, SERVE] + ([reg_arg] if reg_arg else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd, env=env)
    return (r.returncode, r.stdout, r.stderr) if split else (r.returncode, r.stdout + r.stderr)


def ensure(reg, env, *args, cwd=None):
    """`serve.py --ensure --json` → (exit code, parsed JSON or {}, stderr). Remembers the server for the final cleanup."""
    if reg not in _ensured:
        _ensured.append(reg)
    code, out, err = cli(reg, "--ensure", "--json", *args, env=env, split=True, cwd=cwd)
    try:
        return code, json.loads(out), err
    except ValueError:
        return code, {}, err + out


def up(info):
    """True when the server `info` names answers its health as that pid."""
    try:
        conn = http.client.HTTPConnection(info["url"].split("//", 1)[1].rstrip("/"), timeout=2)
        conn.request("GET", "/__pb_health")
        return json.loads(conn.getresponse().read().decode()).get("pid") == info["pid"]
    except (OSError, ValueError, KeyError):
        return False


class Remote:
    """What Events needs of a server this test did not start itself."""
    def __init__(self, info):
        self.hostport = info["url"].split("//", 1)[1].rstrip("/")


def port_of(info):
    return int(info["url"].rstrip("/").rsplit(":", 1)[1])


def wait_until(fn, seconds, step=0.05):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if fn():
            return True
        time.sleep(step)
    return fn()


def main():
    print("1 · idle exit: a tiny --idle-exit stops the server, and the record goes with it")
    reg = project()
    s = Proc(reg, "--idle-exit", "0.02")        # 1.2 s
    check(wait_until(lambda: os.path.isfile(s.record), 1.0) or not s.alive(), "the record is written while it runs")
    check(re.search(r"idle exit +after 0\.02 min", s.log()) is not None, "the banner says when it will stop")
    check(s.wait_exit(15), "it exits by itself, with no signal")
    check(s.proc.returncode == 0, "…with exit code 0 (got %s)" % s.proc.returncode)
    check(not os.path.exists(s.record), ".preview/server.json is gone")
    log = s.log()
    check(re.search(r"idle for 0\.02 min — stopping \(explore\.py link or /pb:preview starts it again\)", log) is not None,
          "it logs why: idle for 0.02 min — stopping (explore.py link or /pb:preview starts it again)")
    check("stopped." in log, "…and went through the normal exit (stopped.)")

    print("2 · a connected tab keeps it alive; it exits once the stream closes")
    reg = project()
    s = Proc(reg, "--idle-exit", "0.03")        # 1.8 s
    ev = Events(s)
    check(ev.connected.is_set(), "an /__pb_events stream is open")
    time.sleep(4.0)                              # more than twice the idle limit
    check(s.alive(), "4 s later, with the stream held open, it is still running")
    h = s.health()
    check(h is not None and h.get("clients") == 1, "/__pb_health counts the open stream (clients == 1)")
    ev.close()
    check(wait_until(lambda: (s.health() or {}).get("clients") == 0 if s.alive() else True, 4), "closing the stream is noticed (clients back to 0)")
    check(s.wait_exit(12), "it then exits by itself")
    check(not os.path.exists(s.record), "…and the record is gone")

    print("3 · --idle-exit 0 never exits; the health keys; a probe is not activity; one project, one server")
    reg = project()
    s = Proc(reg, "--idle-exit", "0")
    time.sleep(3.0)
    check(s.alive(), "3 s with no tab and no request: still running")
    check(re.search(r"idle exit +off", s.log()) is not None, "the banner says idle exit is off")
    h = s.health()
    check(h is not None and all(k in h for k in ("ok", "app", "registry", "pid", "version", "clients", "idleSeconds", "startedAt")),
          "/__pb_health carries clients, idleSeconds and startedAt beside ok, app, registry, pid, version")
    check(h and h["app"] == "pb-preview" and h["pid"] == s.proc.pid and h["clients"] == 0, "…with this server's pid and no clients")
    check(h and isinstance(h["idleSeconds"], int) and h["idleSeconds"] >= 2, "…and idleSeconds grew through the 3 s the health probes did not count (%s)" % (h or {}).get("idleSeconds"))
    check(h and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", h["startedAt"]) is not None, "…startedAt is an ISO time (%s)" % (h or {}).get("startedAt"))
    st, _ = s.get("/")
    h2 = s.health()
    check(st == 200 and h2["idleSeconds"] < h["idleSeconds"], "a page request resets idleSeconds")

    print("4 · coalescing: one save = one reload; a burst = one reload")
    ev = Events(s)
    time.sleep(0.4)
    t = time.monotonic()
    set_name(reg, "Solo one")
    check(wait_until(lambda: len(ev.reloads) >= 1, 1.0), "one save reloads the browser within 1 s")
    lat = (ev.reloads[0] - t) if ev.reloads else None
    print("      (latency %s)" % ("%.2f s" % lat if lat is not None else "none"))
    time.sleep(1.2)
    check(len(ev.reloads) == 1, "…and only once (%d reload events)" % len(ev.reloads))
    before = len(ev.reloads)
    for i in range(10):
        set_name(reg, "Burst %d" % i)
        time.sleep(0.03)
    time.sleep(1.8)
    check(len(ev.reloads) - before == 1, "10 saves 30 ms apart produce exactly one reload (%d)" % (len(ev.reloads) - before))
    st, body = s.get("/")
    check("Burst 9" in body, "…and the page carries the last of them")
    ev.close()

    print("5 · never stale: after 2 s with nobody connected, a save then GET / shows the save")
    check(wait_until(lambda: (s.health() or {}).get("clients") == 0, 3), "no clients are connected")
    time.sleep(2.0)
    set_name(reg, "Fresh after quiet")
    st, body = s.get("/")                        # no wait: the watcher has not got to it yet
    check(st == 200 and "Fresh after quiet" in body, "GET / straight after the write returns the new content")
    set_name(reg, "Fresh design system")
    st, body = s.get("/design-system")
    check(st == 200 and "Fresh design system" in body, "…and so does GET /design-system")

    print("6 · --status / --stop")
    proj_dir = os.path.dirname(reg)
    code, out = cli(None, "--status", cwd=proj_dir)   # registry omitted: ./registry.json
    check(code == 0 and "running" in out and s.url in out and str(s.proc.pid) in out,
          "--status with the registry omitted (cwd = the project) exits 0 and names url and pid")
    check(all(w in out for w in ("uptime", "clients", "idle")), "…and uptime, clients, idle")
    code, out = cli(reg, "--status", "--json")
    info = json.loads(out) if code == 0 else {}
    check(code == 0 and info.get("running") is True and info.get("pid") == s.proc.pid and info.get("url") == s.url
          and isinstance(info.get("clients"), int) and isinstance(info.get("idleSeconds"), int)
          and isinstance(info.get("uptimeSeconds"), int), "--status --json is one JSON object with url, pid, uptimeSeconds, clients, idleSeconds")

    other = project()                                  # a second project whose record points at the first one's server
    os.makedirs(os.path.join(os.path.dirname(other), ".preview"))
    sleeper = subprocess.Popen(["sleep", "60"])        # a pid that must never be signalled
    _procs.append(sleeper)
    with open(os.path.join(os.path.dirname(other), ".preview", "server.json"), "w", encoding="utf-8") as f:
        json.dump({"url": s.url, "host": "127.0.0.1", "port": int(s.hostport.rsplit(":", 1)[1]), "pid": sleeper.pid,
                   "registry": other, "startedAt": "2000-01-01T00:00:00"}, f)
    code, out = cli(other, "--stop")
    check(code == 0 and "left alone" in out and "not running" in out, "--stop refuses a record whose health check names another registry (exit %d: %s)" % (code, out.strip()))
    check(sleeper.poll() is None and s.alive(), "…and signals nothing: the recorded pid and the server both live on")
    code, out = cli(other, "--status")
    check(code == 1 and "not running" in out, "--status on that project says not running (exit %d)" % code)

    rec_path = s.record                                # the right server, but a pid that is not the one that answered
    with open(rec_path, encoding="utf-8") as f:
        good = f.read()
    bad = json.loads(good)
    bad["pid"] = sleeper.pid
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(bad, f)
    code, out = cli(reg, "--stop")
    check(code == 1 and "left alone" in out, "--stop refuses when the recorded pid is not the pid that answered (exit %d)" % code)
    check(sleeper.poll() is None and s.alive(), "…and signals nothing")
    with open(rec_path, "w", encoding="utf-8") as f:
        f.write(good)

    never = project()
    code, out = cli(never, "--status")
    check(code == 1 and "not running" in out and not os.path.exists(os.path.join(os.path.dirname(never), ".preview")),
          "--status on a project with no server exits 1 and starts nothing")
    code, out = cli(never, "--stop")
    check(code == 0 and "not running" in out and not os.path.exists(os.path.join(os.path.dirname(never), ".preview")),
          "--stop on a project with no server exits 0 (already not running) and starts nothing")
    code, out = cli(never, "--status", "--stop")
    check(code == 2, "--status and --stop together are a usage error (exit %d)" % code)

    t = time.monotonic()
    code, out = cli(reg, "--stop")
    check(code == 0 and "stopped" in out and str(s.proc.pid) in out, "--stop stops this registry's server and says so (exit %d: %s)" % (code, out.strip()))
    check(s.wait_exit(5), "…the process is gone (%.1f s)" % (time.monotonic() - t))
    check(not os.path.exists(s.record), "…and its record with it")
    check(s.proc.returncode == 0, "…through the normal exit (code %s)" % s.proc.returncode)
    code, out = cli(reg, "--stop")
    check(code == 0 and "not running" in out, "--stop again: already not running, exit 0")
    code, out = cli(reg, "--status", "--json")
    check(code == 1 and json.loads(out).get("running") is False, "--status --json after: running false, exit 1")
    check(sleeper.poll() is None, "the bystander pid was never signalled")
    sleeper.kill()

    print("7 · --debounce-ms 0 still reloads on the first change")
    reg = project()
    s = Proc(reg, "--idle-exit", "0", "--debounce-ms", "0")
    ev = Events(s)
    time.sleep(0.4)
    t = time.monotonic()
    set_name(reg, "No debounce")
    check(wait_until(lambda: len(ev.reloads) >= 1, 1.0), "one save reloads within 1 s")
    ev.close()
    code, out = cli(reg, "--stop")
    check(code == 0 and s.wait_exit(5), "stopped through --stop")

    print("8 · the poll rate and the slot cache (in process)")
    reg = project()
    st = serve.State(reg, os.path.join(ROOT, "pb", "template", "prototype.html"), None, False)
    check(st.poll_interval() == serve.FAST_POLL, "a fresh server polls every %g s" % serve.FAST_POLL)
    st.last_activity = time.monotonic() - (serve.WARM_SECONDS + 5)
    check(st.poll_interval() == serve.SLOW_POLL, "with no request for %g s it polls every %g s" % (serve.WARM_SECONDS, serve.SLOW_POLL))
    st.client_open()
    st.last_activity = time.monotonic() - (serve.WARM_SECONDS + 5)
    check(st.poll_interval() == serve.FAST_POLL and st.idle_remaining() is None, "a connected client brings back the fast poll and holds off the idle exit")
    st.client_close()
    check(st.sse_clients == 0, "client_close brings the count back")
    expl = os.path.join(os.path.dirname(reg), "memory", "explore")
    os.makedirs(expl)
    with open(os.path.join(expl, "kept.json"), "w", encoding="utf-8") as f:
        json.dump({"target": "kept", "status": "open", "options": []}, f)
    with open(os.path.join(expl, "closed.json"), "w", encoding="utf-8") as f:
        json.dump({"target": "closed", "status": "promoted", "options": []}, f)
    st._slot_cache[("kept", "a")] = (0, "<p>a</p>", None)
    st._slot_cache[("closed", "a")] = (0, "<p>b</p>", None)
    st._slot_cache[("gone", "a")] = (0, "<p>c</p>", None)
    st.bump()
    check(("kept", "a") in st._slot_cache and ("closed", "a") not in st._slot_cache and ("gone", "a") not in st._slot_cache,
          "a version bump drops cached options of explorations that are no longer open, and keeps the open one")

    # two threads that both notice the same change bump the version once, and neither renders stale
    reg = project()
    st = serve.State(reg, os.path.join(ROOT, "pb", "template", "prototype.html"), None, False,
                     os.path.join(ROOT, "pb", "template", "design-system.html"), os.path.join(ROOT, "pb", "template", "runtime.js"))
    serve.refresh(st)                       # primes the mtimes
    serve.render_current(st)
    v0 = st.version
    os.utime(reg, (time.time() + 5, time.time() + 5))
    set_name(reg, "Raced")
    got = []
    ts = [threading.Thread(target=lambda: got.append(serve.refresh(st))) for _ in range(6)]
    for t_ in ts:
        t_.start()
    for t_ in ts:
        t_.join()
    html, err = serve.render_current(st)
    check(st.version == v0 + 1 and sum(1 for g in got if g) == 1,
          "six threads that all see one change bump the version once (%d bumps, %d saw it)" % (st.version - v0, sum(1 for g in got if g)))
    check(err is None and "Raced" in html, "…and what they render is the new file")

    def stop_plain(p):
        p.proc.terminate()
        p.wait_exit(5)

    def log_of(reg_path):
        try:
            with open(os.path.join(os.path.dirname(reg_path), ".preview", "server.log"), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def records(d):
        return sorted(n for n in os.listdir(d) if n.endswith(".json"))

    def tempdir(prefix):
        d = tempfile.mkdtemp(prefix=prefix)
        _dirs.append(d)
        return d

    print("9 · the idle exit defaults to 480 minutes (8 h)")
    env0 = {k: v for k, v in os.environ.items() if k not in ("PB_PREVIEW_IDLE_MIN", "PB_PREVIEW_DIR", "PB_PREVIEW_MAX")}
    check(serve.IDLE_EXIT_MIN == 480, "IDLE_EXIT_MIN is 480 (it was 30)")
    s = Proc(project(), env=env0)
    check(re.search(r"idle exit +after 480 min", s.log()) is not None, "a server started with no --idle-exit says it stops after 480 min")
    stop_plain(s)
    s = Proc(project(), env=dict(env0, PB_PREVIEW_IDLE_MIN="12"))
    check(re.search(r"idle exit +after 12 min", s.log()) is not None, "$PB_PREVIEW_IDLE_MIN still sets it")
    stop_plain(s)
    s = Proc(project(), "--idle-exit", "7", env=dict(env0, PB_PREVIEW_IDLE_MIN="12"))
    check(re.search(r"idle exit +after 7 min", s.log()) is not None, "…and --idle-exit still wins over it")
    stop_plain(s)
    code, out = cli(None, "--help", env=env0)
    check(code == 0 and "default: 480" in out, "--help states the new default")

    print("10 · --ensure: one idempotent start")
    pdir = tempdir("pb-previews-")
    env = dict(env0, PB_PREVIEW_DIR=pdir)
    reg = project()
    code, a1, err = ensure(reg, env)
    check(code == 0 and a1.get("started") is True and sorted(a1) == ["pid", "started", "url"] and isinstance(a1.get("pid"), int),
          "the first --ensure --json starts a server and prints exactly {url, pid, started} (exit %s: %s)" % (code, a1 or err[-200:]))
    own = serve.stable_port(reg)
    check(own <= port_of(a1) < own + 60, "with no --port it takes the project's own port, or the next free one above it (got %d, own %d)" % (port_of(a1), own))
    check(up(a1), "it answers as that pid after the command that started it has exited")
    try:
        check(os.getsid(a1["pid"]) == a1["pid"], "…in a session of its own, so it outlives that command's terminal")
    except (OSError, AttributeError):
        check(True, "(os.getsid unavailable)")
    code, a2, err = ensure(reg, env)
    check(code == 0 and a2 == dict(a1, started=False), "a second --ensure starts nothing: the same pid and URL, started false (%s)" % (a2 or err))
    code, out = cli(reg, "--ensure", env=env)
    check(code == 0 and a1["url"] in out and str(a1["pid"]) in out and "running at" in out, "without --json it says where it runs (%s)" % out.strip())
    ps = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout.splitlines()
    mine = [ln for ln in ps if "serve.py" in ln and reg in ln and "--ensure" not in ln]
    check(len(mine) == 1, "…and one serve.py process serves this registry (%d)" % len(mine))
    rec_file = os.path.join(pdir, "%d.json" % a1["pid"])
    try:
        with open(rec_file, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        rec = {}
    check(rec.get("pid") == a1["pid"] and rec.get("url") == a1["url"] and rec.get("registry") == reg and rec.get("startedAt"),
          "a managed server records itself as <preview dir>/<pid>.json {url, pid, registry, startedAt}")
    check(re.search(r"idle exit +after 480 min", log_of(reg)) is not None, "…and the server it started stops after 480 min by default")
    code, out = cli(reg, "--stop", env=env)
    check(code == 0 and wait_until(lambda: not up(a1), 5), "--stop ends it (exit %d)" % code)
    check(wait_until(lambda: not os.path.exists(rec_file), 3) and not os.path.exists(os.path.join(os.path.dirname(reg), ".preview", "server.json")),
          "…and both its records go with it")

    print("   the flags the caller gave reach the server it starts")
    fork_dir = tempdir("pb-fork-")
    forked = os.path.join(fork_dir, "forked-shell.html")
    with open(os.path.join(ROOT, "pb", "template", "prototype.html"), encoding="utf-8") as f:
        shell_html = f.read()
    with open(forked, "w", encoding="utf-8") as f:
        f.write(shell_html.replace("<title>Prototype Builder</title>", "<title>Prototype Builder FORKED-SHELL-MARK</title>", 1))
    reg_f = project()
    # (the relative --shell is resolved against the caller's cwd — fork_dir — before it is handed on: the server starts in the project)
    code, f1, err = ensure(reg_f, env, "--port", "0", "--shell", "forked-shell.html", "--idle-exit", "7", "--allow-host", "Foo.Local",
                           cwd=fork_dir)
    check(code == 0 and f1.get("started") is True, "--ensure with --port 0 --shell --idle-exit --allow-host starts (exit %s: %s)" % (code, f1 or err[-200:]))
    if f1:
        conn = http.client.HTTPConnection(f1["url"].split("//", 1)[1].rstrip("/"), timeout=10)
        conn.request("GET", "/")
        body = conn.getresponse().read().decode("utf-8", "replace")
        check("FORKED-SHELL-MARK" in body, "--shell survives: the page is the forked shell's")
        check(re.search(r"idle exit +after 7 min", log_of(reg_f)) is not None, "--idle-exit survives (the server's banner says 7 min)")
        conn = http.client.HTTPConnection(f1["url"].split("//", 1)[1].rstrip("/"), timeout=10)
        conn.request("GET", "/", headers={"Host": "foo.local"})
        check(conn.getresponse().status == 200, "--allow-host survives (Host foo.local is answered)")
        cli(reg_f, "--stop", env=env)

    print("   a server that cannot start is exit 3 with the message")
    busy = socket.socket()
    busy.bind(("127.0.0.1", 0))
    busy.listen(1)
    reg_x = project()
    _ensured.append(reg_x)
    code, out, err = cli(reg_x, "--ensure", "--port", str(busy.getsockname()[1]), env=env, split=True)
    check(code == 3 and "exited as it started" in err and "server.log" in err, "--ensure on a port in use → exit 3 and why (%s)" % err.strip()[:120])
    code, out, err = cli(reg_x, "--ensure", "--json", "--port", str(busy.getsockname()[1]), env=env, split=True)
    check(code == 3 and "exited as it started" in json.loads(out).get("error", ""), "…and with --json, {error} on stdout (%s)" % out.strip()[:100])
    busy.close()
    check(wait_until(lambda: records(pdir) == [], 3), "…and nothing was recorded")
    code, out = cli(reg, "--ensure", "--stop", env=env)
    check(code == 2, "--ensure with --stop or --status is a usage error (exit %d)" % code)

    print("   PB_PREVIEW_MAX")
    saved = os.environ.get("PB_PREVIEW_MAX")
    try:
        got = []
        for raw in (None, "", "0", "3", "junk", "-2"):
            if raw is None:
                os.environ.pop("PB_PREVIEW_MAX", None)
            else:
                os.environ["PB_PREVIEW_MAX"] = raw
            got.append(serve.preview_max())
        check(got == [6, 6, 0, 3, 6, 6], "preview_max: default 6, 0 = no cap, a number, junk and negatives ignored (%s)" % got)
    finally:
        if saved is None:
            os.environ.pop("PB_PREVIEW_MAX", None)
        else:
            os.environ["PB_PREVIEW_MAX"] = saved

    print("11 · the cap: the longest-idle server with no tab open makes room; one with a tab is never stopped")
    pdir2 = tempdir("pb-previews-")
    envc = dict(env0, PB_PREVIEW_DIR=pdir2, PB_PREVIEW_MAX="2")
    ra, rb, rc_ = project(), project(), project()
    _c, A, _e = ensure(ra, envc, "--port", "0")
    time.sleep(2.2)
    _c, B, _e = ensure(rb, envc, "--port", "0")
    time.sleep(2.2)
    check(up(A) and up(B) and len(records(pdir2)) == 2, "two managed servers fit under a cap of 2 (records: %d)" % len(records(pdir2)))
    code, C, err = ensure(rc_, envc, "--port", "0")
    check(code == 0 and C.get("started") is True and up(C), "a third --ensure starts (exit %s)" % code)
    check(wait_until(lambda: not up(A), 6), "…and stops the longest-idle one with no tab open (the first)")
    check(up(B) and up(C), "…the other two stay")
    check(wait_until(lambda: records(pdir2) == sorted("%d.json" % i["pid"] for i in (B, C)), 4), "…and the records are B's and C's (%s)" % records(pdir2))
    lg = log_of(rc_)
    check(re.search(r"cap +stopped pid %d " % A["pid"], lg) is not None and "no tab open" in lg and "PB_PREVIEW_MAX" in lg,
          "one log line in the new server's log names what was stopped (%s)" % ([ln for ln in lg.splitlines() if "cap" in ln][:1]))
    for reg_i in (rb, rc_):
        cli(reg_i, "--stop", env=envc)
    check(wait_until(lambda: records(pdir2) == [], 5), "(the other two stopped: no records left)")

    pdir3 = tempdir("pb-previews-")
    envd = dict(env0, PB_PREVIEW_DIR=pdir3, PB_PREVIEW_MAX="2")
    rd, re_, rf, rg = project(), project(), project(), project()
    _c, D, _e = ensure(rd, envd, "--port", "0")
    ev_d = Events(Remote(D))
    check(ev_d.connected.is_set(), "(a tab is open on the first server)")
    time.sleep(2.2)
    _c, E, _e = ensure(re_, envd, "--port", "0")
    time.sleep(2.2)
    _c, F, _e = ensure(rf, envd, "--port", "0")
    check(wait_until(lambda: not up(E), 6), "with a tab open on the OLDEST, the next-oldest is the one stopped")
    check(up(D) and up(F), "…the one with the open event stream stays, and so does the new one")
    ev_f = Events(Remote(F))
    time.sleep(1.2)
    code, G, err = ensure(rg, envd, "--port", "0")
    check(code == 0 and G.get("started") is True and up(G) and up(D) and up(F),
          "every other server has a tab open: nothing is stopped and the new one starts anyway (exit %s)" % code)
    lg = log_of(rg)
    check("have a tab open" in lg and not re.search(r"cap +stopped", lg), "…it says so in one line (%s)" % ([ln for ln in lg.splitlines() if "cap" in ln][:1]))
    ev_d.close()
    ev_f.close()

    print("12 · only --ensure and explore.py link are managed — plain servers and direct starts neither register nor evict")
    pdir4 = tempdir("pb-previews-")
    envp = dict(env0, PB_PREVIEW_DIR=pdir4, PB_PREVIEW_MAX="1")
    rh, ri, rj, rk = project(), project(), project(), project()
    _c, H, _e = ensure(rh, envp, "--port", "0")
    check(up(H) and len(records(pdir4)) == 1, "(one managed server, cap 1)")
    plain = Proc(ri, env=envp)
    time.sleep(1.0)
    check(up(H) and records(pdir4) == ["%d.json" % H["pid"]], "a plain serve.py registers nothing and stops nothing, though that is over the cap")
    stop_plain(plain)
    saved_env = {k: os.environ.get(k) for k in ("PB_PREVIEW_DIR", "PB_PREVIEW_MAX")}
    os.environ.update(PB_PREVIEW_DIR=pdir4, PB_PREVIEW_MAX="1")
    try:
        _ensured.append(rj)
        direct = explore._start_server(rj)
        time.sleep(1.0)
        check(up(H) and "%d.json" % direct["pid"] not in records(pdir4) and len(records(pdir4)) == 1,
              "explore._start_server on its own (what shot.py and the tests use) registers nothing and stops nothing")
        explore.cmd_init(rk, "lk", options=2, goal=True, intent="a round to link to")
        _ensured.append(rk)
        res = explore.cmd_link(rk, "lk")
        check(res["started"] and res["problems"] == [], "explore.py link starts a server (%s)" % res["problems"])
        check("%d.json" % res["pid"] in records(pdir4), "…a managed one: it records itself")
        check(wait_until(lambda: not up(H), 6), "…and, with the cap at 1, it stops the idle managed server to make room")
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print()
    print("wall time %.1f s" % (time.time() - T0))
    if _fail:
        print("✗ %d failure(s)." % len(_fail))
        for m in _fail:
            print("   - " + m)
        return 1
    print("✓ preview server: stops when idle, coalesces bursts, never stale, controllable without kill.")
    return 0


if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    finally:
        for reg_i in _ensured:       # the detached ones: only `--stop` ends them, and only after confirming whose they are
            try:
                subprocess.run([sys.executable, SERVE, reg_i, "--stop"], capture_output=True, timeout=30)
            except (subprocess.SubprocessError, OSError):
                pass
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
