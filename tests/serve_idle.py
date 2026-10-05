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

Stdlib only, no browser, never a fixed port (the servers bind port 0). Builds from a temp copy of
fixtures/golden and cleans up every process it starts.  Usage:  python3 tests/serve_idle.py
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

_fail = []
_procs = []      # every process this test starts, killed in the end
_dirs = []       # every temp folder, removed in the end
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

    def __init__(self, reg_path, *args, cwd=None):
        self.reg = reg_path
        self.lines = []
        self.url = None
        self.proc = subprocess.Popen([sys.executable, SERVE, reg_path, "--no-open", "--port", "0"] + list(args),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=cwd)
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


def cli(reg_arg, *args, cwd=None):
    """serve.py's one-shot modes → (exit code, stdout)."""
    cmd = [sys.executable, SERVE] + ([reg_arg] if reg_arg else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


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
