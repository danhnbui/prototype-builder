#!/usr/bin/env python3
"""
health_resources.py — the ranked health report's `resources` block (lint_registry.py --report).

The report ranks and never gates, so these are the properties that keep it honest while it learns to
watch what grows over time — the registry's heaviest key, backups, explore rounds, server.log:

  1. on the golden copy (no memory/, no explore/, no .preview/) it prints every resources row, ranks
     nothing from them, never crashes, and exits 0; the report's existing sections are all still there
  2. each new threshold, once crossed, ranks a line that NAMES THE FIX:
       backups_count / backups_mb → clean.py --apply --keep-backups 10
       explore_open_days          → explore.py reject <id>
       explore_closed_mb          → clean.py --apply --keep-closed 5
       server_log_kb              → clean.py --apply
       registry_key_share         → names the key
     — and a project under every threshold ranks none of them
  3. memory/doctor.json overrides each threshold (and an unusable value falls back to the default)
  4. a candidate folder with no open round is ranked; an open round's own is not
  5. a running preview server that has sat idle past preview_idle_min is ranked with serve.py --stop;
     a record that nothing answers, or that names another project, is "not running"
  6. --report exits 0 whatever it finds, and the lint-only exit codes are unchanged

Pure stdlib, no browser (the "server" is a loopback stub on port 0). Usage: python3 tests/health_resources.py · Exit 0/1.
"""
import datetime
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "pb", "tools", "lint_registry.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def project(base, name):
    p = os.path.join(base, name)
    shutil.copytree(GOLDEN, p, ignore=shutil.ignore_patterns(".preview"))
    return p


def report(proj, *extra):
    r = subprocess.run([sys.executable, LINT, "--report", *extra, os.path.join(proj, "registry.json")],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def fix_first(out):
    """The ranked lines under `── fix first`."""
    tail = out.split("── fix first", 1)[1]
    return [ln.strip() for ln in tail.splitlines()[1:] if ln.strip()]


def doctor(proj, **kw):
    write(os.path.join(proj, "memory", "doctor.json"), json.dumps(kw))


ROWS = ("largest key", "largest meta key", "backups", "explore open", "explore closed", "server.log", "preview server")
FIXES = ("clean.py --apply --keep-backups 10", "explore.py reject", "clean.py --apply --keep-closed 5",
         "trims it to its last 256 KB", "serve.py --stop")


def ranked(out, needle):
    return any(needle in ln for ln in fix_first(out))


tmp = tempfile.mkdtemp(prefix="pb-health-")
try:
    # ── 1 ────────────────────────────────────────────────────────────────────────
    print("1 · the golden copy: every row, nothing ranked, exit 0")
    g = project(tmp, "golden")
    rc, out, err = report(g)
    check(rc == 0, "exit 0 (rc=%d)" % rc)
    check("Traceback" not in err and "unavailable" not in out, "no crash, and the block did not report itself unavailable")
    check("── resources" in out, "a resources section is printed")
    for row in ROWS:
        check(any(ln.strip().startswith(row) for ln in out.splitlines()), "row: %s" % row)
    check(not any(any(f in ln for f in FIXES) for ln in fix_first(out)), "nothing from the resources block is ranked")
    for old in ("── findings by code", "── items carrying the most", "── shape", "registry  ", "components/screens",
                "largest body", "largest slice", "── information (never a finding)", "── fix first"):
        check(old in out, "the report's existing line is still there: %s" % old.strip())
    check(not os.path.exists(os.path.join(g, "memory")) and not os.path.exists(os.path.join(g, ".preview")),
          "reading the project created no memory/ or .preview/ folder")

    # ── 2 ────────────────────────────────────────────────────────────────────────
    print("2 · each threshold ranks a line that names the fix")
    # backups_count: 21 entries across the two places
    p = project(tmp, "backups-count")
    for i in range(14):
        write(os.path.join(p, "memory", "backups", "pre-%02d" % i, "registry.json"), "{}")
    for i in range(7):
        write(os.path.join(p, ".pb-backups", "registry.12.T%d.json" % i), "{}")
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "clean.py --apply --keep-backups 10") and "21 backups" in " ".join(fix_first(out)),
          "21 backups > 20 → ranked with `clean.py --apply --keep-backups 10`")
    p = project(tmp, "backups-ok")
    for i in range(20):
        write(os.path.join(p, "memory", "backups", "pre-%02d" % i, "registry.json"), "{}")
    rc, out, _ = report(p)
    check(rc == 0 and not ranked(out, "keep-backups"), "exactly 20 backups is not over the threshold")

    # backups_mb: a few entries, one of them 51 MB (sparse where the filesystem allows, written otherwise)
    p = project(tmp, "backups-mb")
    big = os.path.join(p, "memory", "backups", "pre-big")
    os.makedirs(big)
    with open(os.path.join(big, "blob.bin"), "wb") as f:
        f.truncate(51 * 1024 * 1024)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "keep-backups 10") and "MB" in " ".join(fix_first(out)),
          "51 MB of backups > 50 → ranked with the same fix")

    # explore_open_days: an open round created 6 days ago
    p = project(tmp, "open-old")
    six = (datetime.datetime.now() - datetime.timedelta(days=6)).replace(microsecond=0).isoformat()
    write(os.path.join(p, "memory", "explore", "stale-round.json"),
          json.dumps({"target": "stale-round", "status": "open", "mode": "target", "createdAt": six}))
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "explore.py reject stale-round"), "an open round 6 days old > 3 → ranked with `explore.py reject stale-round`")
    p = project(tmp, "open-fresh")
    write(os.path.join(p, "memory", "explore", "fresh.json"),
          json.dumps({"target": "fresh", "status": "open", "mode": "target",
                      "createdAt": datetime.datetime.now().replace(microsecond=0).isoformat()}))
    rc, out, _ = report(p)
    check(rc == 0 and not ranked(out, "explore.py reject") and "fresh" in out, "a fresh open round is listed, not ranked")
    # no createdAt: falls back to the manifest file's own mtime
    p = project(tmp, "open-mtime")
    mf = os.path.join(p, "memory", "explore", "undated.json")
    write(mf, json.dumps({"target": "undated", "status": "open"}))
    old = datetime.datetime.now().timestamp() - 9 * 86400
    os.utime(mf, (old, old))
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "explore.py reject undated"), "no createdAt → the manifest's mtime gives the age")

    # explore_closed_mb: 52 MB of closed rounds
    p = project(tmp, "closed-mb")
    closed = os.path.join(p, "memory", "explore", "_closed")
    write(os.path.join(closed, "old-20260101T000000.json"), json.dumps({"target": "old", "status": "rejected"}))
    os.makedirs(os.path.join(closed, "old-20260101T000000"))
    with open(os.path.join(closed, "old-20260101T000000", "shot.png"), "wb") as f:
        f.truncate(52 * 1024 * 1024)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "clean.py --apply --keep-closed 5"), "52 MB of closed rounds > 50 → ranked with `--keep-closed 5`")

    # server_log_kb: a 1.2 MB log
    p = project(tmp, "log")
    write(os.path.join(p, ".preview", "server.log"), "l" * (1200 * 1024))
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "trims it to its last 256 KB") and ranked(out, "clean.py --apply"),
          "a 1.2 MB server.log > 1024 KB → ranked with `clean.py --apply`")

    # registry_key_share: one key holding most of a registry over slice_kb
    p = project(tmp, "key")
    reg = json.load(open(os.path.join(p, "registry.json"), encoding="utf-8"))
    reg["notes"] = "n" * (120 * 1024)
    json.dump(reg, open(os.path.join(p, "registry.json"), "w", encoding="utf-8"))
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "registry key 'notes'"), "a key at >35% of the registry and >20 KB → ranked by name")
    check(any("notes" in ln and "%" in ln for ln in out.splitlines() if ln.strip().startswith("largest key")),
          "…and the largest-key row shows its share")
    reg = json.load(open(os.path.join(p, "registry.json"), encoding="utf-8"))
    del reg["notes"]
    reg["meta"]["bulk"] = "m" * (60 * 1024)
    json.dump(reg, open(os.path.join(p, "registry.json"), "w", encoding="utf-8"))
    rc, out, _ = report(p)
    check(rc == 0 and any(ln.strip().startswith("largest meta key") and "meta.bulk" in ln for ln in out.splitlines()),
          "the largest key under meta is named")
    # the golden registry's own largest key is a large SHARE of a small file — that alone is never ranked
    check(not ranked(report(g)[1], "registry key"), "a big share of a registry under slice_kb is not ranked")

    # ── 3 ────────────────────────────────────────────────────────────────────────
    print("3 · memory/doctor.json overrides")
    p = project(tmp, "override")
    for i in range(3):
        write(os.path.join(p, "memory", "backups", "pre-%d" % i, "registry.json"), "{}" * 1000)
    write(os.path.join(p, ".preview", "server.log"), "l" * (10 * 1024))
    write(os.path.join(p, "memory", "explore", "_closed", "c-1.json"), json.dumps({"target": "c", "status": "rejected"}))
    write(os.path.join(p, "memory", "explore", "r.json"),
          json.dumps({"target": "r", "status": "open",
                      "createdAt": (datetime.datetime.now() - datetime.timedelta(days=2)).replace(microsecond=0).isoformat()}))
    rc, out, _ = report(p)
    check(rc == 0 and not any(any(f in ln for f in FIXES) for ln in fix_first(out)), "under the defaults nothing is ranked")
    doctor(p, backups_count=2)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "keep-backups 10"), "doctor.json backups_count=2 ranks 3 backups")
    doctor(p, backups_mb=0.001)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "keep-backups 10"), "doctor.json backups_mb=0.001 ranks them by size")
    doctor(p, server_log_kb=5)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "256 KB"), "doctor.json server_log_kb=5 ranks a 10 KB log")
    doctor(p, explore_open_days=1)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "explore.py reject r"), "doctor.json explore_open_days=1 ranks a 2-day-old round")
    doctor(p, explore_closed_mb=0.0000001)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "keep-closed 5"), "doctor.json explore_closed_mb ranks the closed rounds")
    doctor(p, registry_key_share=0.01, slice_kb=0)
    rc, out, _ = report(p)
    check(rc == 0 and ranked(out, "registry key"), "doctor.json registry_key_share (+ slice_kb) ranks the heaviest key")
    doctor(p, backups_count="lots", server_log_kb=None, explore_open_days=[1])
    rc, out, err = report(p)
    check(rc == 0 and "Traceback" not in err and "unavailable" not in out and not ranked(out, "keep-backups"),
          "a value that is not a number falls back to the default, no crash")
    write(os.path.join(p, "memory", "doctor.json"), "{ not json")
    rc, out, err = report(p)
    check(rc == 0 and "unreadable" in out and "Traceback" not in err, "an unreadable doctor.json is a note, never a crash")

    # ── 4 ────────────────────────────────────────────────────────────────────────
    print("4 · candidate folders")
    p = project(tmp, "cand")
    write(os.path.join(p, "render", "_candidates", "ghost", "opt", "b.js"), "//")
    write(os.path.join(p, "render", "_candidates", "live", "opt", "b.js"), "//")
    write(os.path.join(p, "memory", "explore", "live.json"),
          json.dumps({"target": "live", "status": "open", "createdAt": datetime.datetime.now().replace(microsecond=0).isoformat()}))
    rc, out, _ = report(p)
    line = " ".join(ln for ln in fix_first(out) if "_candidates" in ln)
    check(rc == 0 and "ghost" in line and "live" not in line and "clean.py --apply" in line,
          "the folder with no round is ranked with `clean.py --apply`; the open round's own is not")

    # ── 5 ────────────────────────────────────────────────────────────────────────
    print("5 · the preview server")
    p = project(tmp, "server")
    reg_path = os.path.join(p, "registry.json")
    state = {"registry": os.path.realpath(reg_path), "idle": 4000}

    class Stub(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/__pb_health":
                body = json.dumps({"ok": True, "app": "pb-preview", "registry": state["registry"], "pid": 4242,
                                   "clients": 0, "idleSeconds": state["idle"],
                                   "startedAt": "2026-01-01T00:00:00"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = "http://127.0.0.1:%d/" % httpd.server_address[1]
        write(os.path.join(p, ".preview", "server.json"), json.dumps({"url": url, "pid": 4242}))
        rc, out, _ = report(p)
        row = [ln for ln in out.splitlines() if ln.strip().startswith("preview server")][0]
        check(rc == 0 and "running at " + url in row and "idle 67 min" in row, "a running server shows its URL and idle minutes (%s)" % row.strip())
        check(ranked(out, "serve.py --stop"), "idle 67 min >= 60 → ranked with `serve.py --stop`")
        state["idle"] = 120
        rc, out, _ = report(p)
        check(rc == 0 and "idle 2 min" in out and not ranked(out, "serve.py --stop"), "idle 2 min is shown, not ranked")
        doctor(p, preview_idle_min=1)
        rc, out, _ = report(p)
        check(rc == 0 and ranked(out, "serve.py --stop"), "doctor.json preview_idle_min=1 ranks it")
        os.remove(os.path.join(p, "memory", "doctor.json"))
        state["registry"] = os.path.realpath(os.path.join(tmp, "somewhere-else", "registry.json"))
        rc, out, _ = report(p)
        check(rc == 0 and "not running" in out and not ranked(out, "serve.py --stop"),
              "a server that names another registry is not this project's — not running")
    finally:
        httpd.shutdown()
        httpd.server_close()
    rc, out, _ = report(p)
    check(rc == 0 and "not running" in out, "a record nothing answers any more is not running")

    # ── 6 ────────────────────────────────────────────────────────────────────────
    print("6 · exit codes")
    p = project(tmp, "exit")
    write(os.path.join(p, "memory", "doctor.json"), json.dumps({"backups_count": 0, "backups_mb": 0, "server_log_kb": 0}))
    for i in range(3):
        write(os.path.join(p, "memory", "backups", "b%d" % i, "registry.json"), "{}")
    rc, out, _ = report(p)
    check(rc == 0 and fix_first(out), "--report exits 0 with things ranked")
    r = subprocess.run([sys.executable, LINT, os.path.join(p, "registry.json")], capture_output=True, text=True)
    check(r.returncode == 0 and "── resources" not in r.stdout, "without --report the lint run is unchanged (exit %d, no resources block)" % r.returncode)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
if fails:
    print("✗ %d health_resources failure(s):" % len(fails))
    for m in fails:
        print("  " + m)
    sys.exit(1)
print("✓ health_resources — what grows is shown, ranked, and named with its fix")
