#!/usr/bin/env python3
"""
explore_tool.py — /pb:explore's executable half: one manifest, one compare page on the preview
server, a scoring gate that blocks, and a promote that refuses a stale or mixed pick.

The failure this pins: an exploration that ended as three loose preview.html files on a second
port, with no compare page and no scores, and a pick that overwrote a body another session had
edited in the meantime. Each assertion below is one of those, made impossible:

  * init seeds a manifest + candidate copies, multi-body overlays allowed
  * check fails an option that changes nothing, and passes once it renders
  * /explore/<target> and /explore/<target>/<slot> are served by serve.py — same port
  * the shell gets window.PB_EXPLORE, so Sandbox → Explore lists the options
  * POST scores validates and writes the manifest; gate passes only when every cell is scored — and is
    held to the same doors as POST /api/meta: a foreign or missing Origin, another port or scheme, a
    non-loopback Host → 403 with nothing written; a bad Content-Length, a body over the limit, JSON nested
    until the parser gives up, a stalled body, a non-object → 400 with a message
  * promote refuses a mixed pick and a concurrent edit, then promotes + archives
  * two options closer than 4 of 7 axes FAIL check (a missing axis counts as equal); a merge
    slot is exempt; goal mode only warns
  * two options with the same rendered structure FAIL check --shots — same layout in different
    colours (the signature + similarity are also tested on plain HTML strings, so the rule holds
    without Playwright)
  * check warns on a missing direction brief / execution plan; promote and reject move the
    brief and plans/ into memory/explore/_closed/ beside the manifest
  * a page round (--pages) — options that are pages, not registry bodies (the tool's own chrome):
    check fails a missing, escaping or duplicated page; serve.py serves the round's files on the
    same port (a bare slot redirects to its page, ../shared resolves, traversal is refused); promote
    records the pick and copies nothing
  * `link` — the URL the user is handed: it finds this project's server through .preview/server.json
    + GET /__pb_health, refuses a server of another registry, starts one when none answers, and the
    started server drops its record on SIGTERM

IA mode (--ia) is tests/explore_ia.py.

Usage:  python3 tests/explore_tool.py
Exit:   0 = pass · 1 = a failure
"""
import http.client
import json
import os
import shutil
import signal
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import explore  # noqa: E402
import serve    # noqa: E402

SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
COMPARE = os.path.join(ROOT, "pb", "template", "explore-compare.html")
RUNTIME = os.path.join(ROOT, "pb", "template", "runtime.js")
FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build(project):
    reg = {
        "meta": {"schemaVersion": 12, "name": "Explore fixture", "devices": ["laptop", "mobile"]},
        "screens": [{"id": "home", "name": "Home", "renderSrc": "render/screens/home.js",
                     "renderFn": "renderScreenHome"}],
        "components": [{"id": "card", "level": "atom", "renderSrc": "render/components/card.js",
                        "renderFn": "renderCmpCard"}],
    }
    write(os.path.join(project, "registry.json"), json.dumps(reg, indent=2))
    write(os.path.join(project, "render/components/card.js"),
          "return '<div class=\"card\">' + pbEscape(props.title || 'Card') + '</div>';\n")
    write(os.path.join(project, "render/screens/home.js"),
          "return '<main>' + pbUse('card', { title: 'Live' }) + '</main>';\n")


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read().decode("utf-8")


def post(url, obj):
    """A save from the compare page itself: a browser sends this page's own Origin on a same-origin POST."""
    host = url.split("//", 1)[1].split("/", 1)[0]
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Origin": "http://" + host})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def post_as(base, path, body=None, headers=None, raw=None):
    """A POST with the headers under the test's control (a foreign Origin, no Origin, another Host).
    → (status, parsed JSON or {"raw": …})."""
    host = base.split("//", 1)[1]
    conn = http.client.HTTPConnection(host, timeout=10)
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
    h = {"Content-Type": "application/json", "Origin": "http://" + host, "Host": host}
    h.update(headers or {})
    conn.request("POST", path, body=data, headers={k: v for k, v in h.items() if v is not None})
    r = conn.getresponse()
    out = r.read().decode("utf-8")
    conn.close()
    try:
        return r.status, json.loads(out)
    except ValueError:
        return r.status, {"raw": out[:200]}


def post_raw(base, path, head_lines, body=b""):
    """A POST written by hand on a socket, for what http.client will not send (a Content-Length that is
    not a number, fewer bytes than promised). → (status, parsed JSON or {"raw": …})."""
    host = base.split("//", 1)[1]
    h, port = host.rsplit(":", 1)
    sock = socket.create_connection((h, int(port)), timeout=15)
    lines = ["POST %s HTTP/1.1" % path, "Host: " + host, "Origin: http://" + host,
             "Content-Type: application/json"] + list(head_lines)
    try:
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        status = int(head.split(b" ", 2)[1]) if head else 0
        clen = 0
        for ln in head.split(b"\r\n")[1:]:
            if ln.lower().startswith(b"content-length:"):
                clen = int(ln.split(b":", 1)[1])
        while len(rest) < clen:
            chunk = sock.recv(65536)
            if not chunk:
                break
            rest += chunk
    finally:
        sock.close()
    try:
        return status, json.loads(rest.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return status, {"raw": rest[:200]}


def shots_convergence(reg_path, project):
    """Two candidates that render the same structure in different colours fail check --shots;
    a real structural difference passes. Skips (not fails) without Playwright + Chromium."""
    man = explore.cmd_init(reg_path, "card", options=2, intent="same page twice?")
    same = "return '<div class=\"card\" style=\"color:var(--%s)\"><span class=\"t\">' + pbEscape(props.title || 'Card') + '</span></div>';\n"
    for o, tone in zip(man["options"], ("fg", "accent")):
        write(os.path.join(project, o["overlay"]["render/components/card.js"]), same % tone)
    man = explore.load_manifest(project, "card")
    for i, o in enumerate(man["options"]):
        o["label"], o["bet"] = "Tone %d" % i, "someone"
        o["axes"] = {k: "%s-%d" % (k, i) for k in explore.AXES[:4]}
    explore.save_manifest(project, man)
    try:
        try:
            problems, _w, _s = explore.cmd_check(reg_path, "card", SHELL, shots=True)
        except explore.ExploreError as e:
            if e.code == explore.EXIT_CANNOT_RUN:
                print("  – skipped: %s" % str(e)[:80])
                return
            raise
        check(any("structurally the same page" in p for p in problems),
              "same layout in different colours FAILS check --shots (%s)" % problems)
        write(os.path.join(project, man["options"][1]["overlay"]["render/components/card.js"]),
              "return '<ul class=\"rows\"><li class=\"row\"><b class=\"k\">' + pbEscape(props.title || 'Card') + "
              "'</b></li><li class=\"row row--meta\"><i class=\"v\">2</i></li></ul>';\n")
        problems, _w, shots = explore.cmd_check(reg_path, "card", SHELL, shots=True)
        check(problems == [] and len(shots) == 4, "a structurally different option passes, 2 shots each (%s)" % problems)
    finally:
        explore.cmd_reject(reg_path, "card")


def in_process_server(reg_path):
    st = serve.State(reg_path, SHELL, None, False, None, RUNTIME, COMPARE)
    serve.Handler.state = st
    httpd = serve.make_server("127.0.0.1", 0, True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d" % httpd.server_address[1]


def get_status(url):
    """GET without following a redirect → (status, headers, body)."""
    host, path = url.split("//", 1)[1].split("/", 1)
    conn = http.client.HTTPConnection(host, timeout=10)
    conn.request("GET", "/" + path)
    r = conn.getresponse()
    body = r.read().decode("utf-8", "replace")
    conn.close()
    return r.status, dict(r.getheaders()), body


def page_round(reg_path, project):
    man = explore.cmd_init(reg_path, "tool-chrome", options=2, pages=True, intent="a calmer tool")
    check(man["mode"] == "pages" and man["host"] is None and "baseline" in man and man["baseline"] == {},
          "--pages opens a round with no host and no bodies (the id need not resolve)")
    check([o["page"] for o in man["options"]] == ["opt-1/index.html", "opt-2/index.html"],
          "each slot's page defaults to <slot>/index.html")
    root = os.path.join(project, "memory", "explore", "tool-chrome")
    check(all(os.path.isdir(os.path.join(root, o["slot"])) for o in man["options"]), "each slot gets its folder")
    try:
        explore.cmd_init(reg_path, "x-round", pages=True, files=["home"])
        check(False, "--pages with --files is refused")
    except explore.ExploreError:
        check(True, "--pages with --files is refused")

    problems, _w, _s = explore.cmd_check(reg_path, "tool-chrome", SHELL)
    check(sum("page missing" in p for p in problems) == 2, "a page that is not written yet fails check (%s)" % problems)
    page = "<!doctype html><html><head><link rel=\"stylesheet\" href=\"../shared/base.css\"></head><body>%s</body></html>"
    write(os.path.join(root, "shared", "base.css"), "body{margin:0}\n")
    write(os.path.join(root, "opt-1", "index.html"), page % "<main class=\"rail\"><nav>a</nav></main>")
    write(os.path.join(root, "opt-2", "index.html"), page % "<main class=\"rail\"><nav>a</nav></main>")
    man = explore.load_manifest(project, "tool-chrome")
    for i, o in enumerate(man["options"]):
        o["label"], o["bet"] = "Take %d" % i, "the maintainer"
        o["axes"] = {k: "%s-%d" % (k, i) for k in explore.AXES[:4]}
    explore.save_manifest(project, man)
    problems, _w, _s = explore.cmd_check(reg_path, "tool-chrome", SHELL)
    check(any("same page, byte for byte" in p for p in problems), "two options that are the same file fail check")
    write(os.path.join(root, "opt-2", "inspector.html"), page % "<section class=\"panel\"><table><tr><td>b</td></tr></table></section>")
    man["options"][1]["page"] = "opt-2/inspector.html#/c/card"
    explore.save_manifest(project, man)
    problems, _w, _s = explore.cmd_check(reg_path, "tool-chrome", SHELL)
    check(problems == [], "a page round passes once every page exists and differs (%s)" % problems)
    man["options"][0]["page"] = "../../../registry.json"
    explore.save_manifest(project, man)
    problems, _w, _s = explore.cmd_check(reg_path, "tool-chrome", SHELL)
    check(any("leaves memory/explore/tool-chrome/" in p for p in problems), "a page outside the round's folder fails check")
    man["options"][0]["page"] = "opt-1/index.html"
    explore.save_manifest(project, man)

    httpd, base = in_process_server(reg_path)
    try:
        code, html = get(base + "/explore/tool-chrome")
        check(code == 200 and '"mode":"pages"' in html, "/explore/<id> serves the compare page for a page round")
        code, html = get(base + "/explore/tool-chrome/opt-1/index.html")
        check(code == 200 and 'class="rail"' in html, "an option page is served from its slot folder, on the same port")
        code, css = get(base + "/explore/tool-chrome/shared/base.css")
        check(code == 200 and "margin:0" in css, "../shared/… from an option page resolves")
        code, hdrs, _b = get_status(base + "/explore/tool-chrome/opt-2")
        check(code == 302 and hdrs.get("Location") == "/explore/tool-chrome/opt-2/inspector.html#/c/card",
              "a bare slot redirects to its page (what Sandbox → Explore opens) (%s %s)" % (code, hdrs.get("Location")))
        code, _h, _b = get_status(base + "/explore/tool-chrome/%2e%2e/%2e%2e/%2e%2e/registry.json")
        check(code == 403, "a path that climbs out of the round's folder is refused (%s)" % code)
        code, _h, _b = get_status(base + "/explore/tool-chrome/opt-1/nope.html")
        check(code == 404, "a missing file is a 404")
        code, body = get(base + "/__pb_health")
        check(code == 200 and json.loads(body)["registry"] == reg_path, "/__pb_health names the registry it serves")
        full = {"%s:%s" % (c["id"], s): 4 for c in explore.DEFAULT_RUBRIC for s in ("opt-1", "opt-2")}
        code, res = post(base + "/__pb_explore/tool-chrome/scores", {"scores": full})
        check(code == 200 and res["missing"] == [], "a page round is rated on the same page, through the same save")
    finally:
        httpd.shutdown()
        httpd.server_close()

    res = explore.cmd_promote(reg_path, "tool-chrome", "opt-2")
    check(res["mode"] == "pages" and res["files"] == [] and res["backup"] is None,
          "promote of a page round copies nothing and backs nothing up")
    check(os.path.isfile(os.path.join(project, res["page"])) and res["page"].endswith("opt-2/inspector.html"),
          "…and points at the picked page, archived with its round (%s)" % res["page"])
    check(explore.sessions(project) == [] and not os.path.exists(root), "the round is closed and its folder archived")


def link_round(reg_path, project):
    explore.cmd_init(reg_path, "card", options=2, intent="a link")
    man = explore.load_manifest(project, "card")
    for i, o in enumerate(man["options"], 1):
        write(os.path.join(project, o["overlay"]["render/components/card.js"]),
              "return '<div class=\"card card--%d\">' + pbEscape(props.title || 'Card') + '</div>';\n" % i)
    record = os.path.join(project, explore.SERVER_FILE)
    started_pid = None
    try:
        httpd, base = in_process_server(reg_path)
        try:
            serve.write_server_record(record, {"url": base + "/", "pid": os.getpid(), "registry": reg_path})
            res = explore.cmd_link(reg_path, "card")
            check(res["problems"] == [] and not res["started"] and res["url"] == base + "/explore/card",
                  "link finds the running server through its record and prints /explore/<id> (%s)" % res)
            check(len(res["options"]) == 2, "…and checked both option frames")
            check(explore._ours(base, reg_path) and not explore._ours(base, os.path.join(project, "other.json")),
                  "a server of another registry is not ours")
        finally:
            httpd.shutdown()
            httpd.server_close()
        # the record now points at a dead port → link starts a server of its own, on the port this
        # project's launch.json entry claims (not the default 8000 another project may hold)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            claimed = s.getsockname()[1]
        write(os.path.join(project, ".claude", "launch.json"), json.dumps({"version": "0.0.1", "configurations": [
            {"name": "pb-preview · other", "runtimeArgs": ["serve.py", "/elsewhere/registry.json"], "port": 1},
            {"name": "pb-preview · x-explore", "runtimeArgs": ["serve.py", reg_path, "--no-open"], "port": claimed}]}))
        res = explore.cmd_link(reg_path, "card")
        started_pid = res["pid"]
        check(res["started"] and res["problems"] == [] and res["pid"] != os.getpid(),
              "with no live server, link starts one in the background (%s)" % res)
        check(res["url"] == "http://127.0.0.1:%d/explore/card" % claimed,
              "…on the port this project's launch.json entry claims (%s)" % res["url"])
        code, html = get(res["url"])
        check(code == 200 and '"target":"card"' in html, "the URL it printed opens the compare page")
        res2 = explore.cmd_link(reg_path, "card")
        check(not res2["started"] and res2["url"] == res["url"], "a second link reuses that server — one per project")
        check(explore.main(["--registry", reg_path, "link", "nope"]) == explore.EXIT_USAGE,
              "link to a round that is not open is a usage error")
        os.kill(started_pid, signal.SIGTERM)
        for _ in range(50):
            if not os.path.exists(record):
                break
            time.sleep(0.1)
        check(not os.path.exists(record), "the started server removes its record on SIGTERM")
        started_pid = None
    finally:
        if started_pid:
            try:
                os.kill(started_pid, signal.SIGKILL)
            except OSError:
                pass
        explore.cmd_reject(reg_path, "card")


def main():
    tmp = tempfile.mkdtemp()
    project = os.path.join(tmp, "[x] explore")
    reg_path = os.path.join(project, "registry.json")
    try:
        build(project)

        print("init")
        man = explore.cmd_init(reg_path, "card", options=2, files=["home"], intent="a calmer card")
        check(man["host"] == "home", "a component target is hosted on the screen that composes it")
        check(set(man["baseline"]) == {"render/components/card.js", "render/screens/home.js"},
              "--files adds a second body to the overlay (multi-body option)")
        cand = os.path.join(project, man["options"][0]["overlay"]["render/components/card.js"])
        check(os.path.isfile(cand), "each slot's candidates are seeded as copies of the live bodies")
        try:
            explore.cmd_init(reg_path, "card")
            check(False, "a second init on an open exploration is refused")
        except explore.ExploreError:
            check(True, "a second init on an open exploration is refused")

        print("check")
        problems, warns, _s = explore.cmd_check(reg_path, "card", SHELL)
        check(any("identical to the live body" in p for p in problems), "an untouched option fails check")
        check(any("no label" in p for p in problems), "an unlabelled option fails check")
        check(any("no direction brief" in w for w in warns), "a missing direction brief is warned about")
        check(sum("no execution plan" in w for w in warns) == 2, "a missing execution plan is warned about, per slot")
        for i, o in enumerate(man["options"], 1):
            write(os.path.join(project, o["overlay"]["render/components/card.js"]),
                  "return '<div class=\"card card--%d\">' + pbEscape(props.title || 'Card') + '</div>';\n" % i)
        man = explore.load_manifest(project, "card")
        for i, o in enumerate(man["options"], 1):
            o["label"], o["bet"], o["axes"] = "Take %d" % i, "someone in a hurry", {"layout": "l%d" % i}
        explore.save_manifest(project, man)
        problems, _w, _s = explore.cmd_check(reg_path, "card", SHELL)
        check(any("differ on only 1 of 7 axes" in p for p in problems),
              "two options 1 axis apart FAIL check — a problem, not a warning (%s)" % problems)
        man = explore.load_manifest(project, "card")
        man["options"][0]["axes"] = {"mental-model": "status", "layout": "Table ", "navigation": "tabs",
                                     "motion": "none", "hierarchy": "status first"}
        man["options"][1]["axes"] = {"mental-model": "time", "layout": "table", "navigation": "rail",
                                     "hierarchy": "next action"}   # motion missing → counts as equal
        explore.save_manifest(project, man)
        problems, _w, _s = explore.cmd_check(reg_path, "card", SHELL)
        check(any("differ on only 3 of 7 axes" in p for p in problems),
              "values compare trimmed + lowercase and a missing axis counts as equal (3 < 4 fails)")
        man["options"][1]["axes"]["contrast"] = "soft"
        man["options"][0]["axes"]["contrast"] = "high"
        explore.save_manifest(project, man)
        brief = explore.brief_path(project, "card")
        write(brief, "# Direction · card\n## Bets\n- opt-1 …\n- opt-2 …\n")
        for o in man["options"]:
            write(explore.plan_path(project, "card", o["slot"]), "# Plan · %s\n" % o["slot"])
        problems, warns, _s = explore.cmd_check(reg_path, "card", SHELL)
        check(problems == [], "check passes once every option is labelled, changed, ≥ 4 axes apart and renders (%s)" % problems)
        check(not any("brief" in w or "execution plan" in w for w in warns), "no brief / plan warning once they exist")

        print("distance + convergence, unit")
        pairs = explore.close_pairs([{"slot": "opt-1", "axes": {"layout": "a"}},
                                     {"slot": "opt-merge", "merge": True, "axes": {"layout": "a"}}])
        check(pairs == [], "a merge slot is not held to the distance gate against its parents")
        a = explore.structure_signature('<main class="pg"><ul class="list"><li class="row" style="color:var(--a)">Hà Nội</li>'
                                        '<li class="row">B</li></ul></main>')
        b = explore.structure_signature('<main class="pg"><ul class="list"><li class="row" style="color:var(--b)">Sài Gòn</li>'
                                        '<li class="row">C</li></ul></main>')
        c = explore.structure_signature('<main class="pg"><table class="grid"><tr><td class="cell">A</td><td>1</td></tr>'
                                        '</table><nav class="tabs"><a class="tab">x</a></nav></main>')
        check(a == b and explore.structure_similarity(a, b) == 1.0,
              "colour, copy and inline style do not change the structure signature")
        check(explore.structure_similarity(a, c) < explore.DEFAULT_CONVERGE, "a different layout is structurally apart")
        check(explore.converged_pairs({"opt-1": a, "opt-2": b, "opt-3": c}) == [("opt-1", "opt-2", 1.0)],
              "converged_pairs names exactly the pair that is the same page twice")
        r = explore.structure_similarity(a, c)
        check(len(explore.converged_pairs({"opt-1": a, "opt-3": c}, threshold=r)) == 1,
              "the threshold (--converge) decides what counts as the same page")
        check(explore.main(["--registry", reg_path, "check", "card", "--converge", "0"]) == explore.EXIT_USAGE,
              "--converge outside (0, 1] is a usage error")
        fenced = explore.structure_signature('<main class="host"><header class="bar"></header><!--pbx:start-->'
                                             '<div class="card"></div><!--pbx:end--><footer></footer></main>')
        check(fenced == ["div", ".card"], "the pbx markers isolate the candidate's own subtree from the host chrome")

        print("serve.py — the same port")
        st = serve.State(reg_path, SHELL, None, False, None, RUNTIME, COMPARE)
        serve.Handler.state = st
        httpd = serve.make_server("127.0.0.1", 0, True)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % httpd.server_address[1]
        try:
            code, html = get(base + "/explore/card")
            check(code == 200 and '"target":"card"' in html, "/explore/card serves the compare page with the manifest inlined")
            check("__PB_EXPLORE_SESSION__" not in html, "the session placeholder is filled")
            code, html = get(base + "/explore/card/opt-2?screen=home")
            check(code == 200 and "card--2" in html, "/explore/card/opt-2 renders that option's body, in memory")
            check("window.PB_EXPLORE=" in html and '"current":{"target":"card","slot":"opt-2"}' in html,
                  "an option page tells the shell which option it is")
            code, html = get(base + "/")
            check("window.PB_EXPLORE=" in html and '"slot":"opt-1"' in html,
                  "the live prototype gets the open explorations for Sandbox → Explore")
            check("card--1" not in html, "the live prototype still renders the live body")
            code, _ = get(base + "/explore")
            check(code == 200, "/explore lists the open explorations")

            code, res = post(base + "/__pb_explore/card/scores", {"scores": {"hierarchy:opt-9": 4}})
            check(code == 400 and not res["ok"], "a score for a slot that does not exist is rejected")
            code, res = post(base + "/__pb_explore/card/scores", {"scores": {"hierarchy:opt-1": 7}})
            check(code == 400, "a score outside 1–5 is rejected")
            print("POST scores — the same three doors and the same body parsing as /api/meta (L5)")
            scores_path = "/__pb_explore/card/scores"
            good_scores = {"scores": {"hierarchy:opt-1": 4}}
            man_before = explore.load_manifest(project, "card")
            for label, hdrs in [("a foreign Origin", {"Origin": "http://evil.example"}),
                                ("no Origin", {"Origin": None}),
                                ("this host on another port", {"Origin": "http://127.0.0.1:1"}),
                                ("an https Origin for this host", {"Origin": "https://" + base.split("//", 1)[1]}),
                                ("a non-loopback Host (DNS rebinding)", {"Host": "evil.example", "Origin": "http://evil.example"})]:
                code, res = post_as(base, scores_path, good_scores, headers=hdrs)
                check(code == 403 and res.get("ok") is False and isinstance(res.get("error"), str),
                      "%s → 403 with a message (%s %s)" % (label, code, str(res)[:80]))
            check(explore.load_manifest(project, "card") == man_before,
                  "…and none of those refusals wrote a score (a perfectly valid payload, refused on who sent it)")
            for label, heads, body, want in [
                ("a non-numeric Content-Length", ["Content-Length: abc"], b"{}", "Content-Length"),
                ("a signed Content-Length", ["Content-Length: +2"], b"{}", "Content-Length"),
                ("no Content-Length at all", [], b"{}", "missing"),
                ("Content-Length: 0", ["Content-Length: 0"], b"", "missing"),
                ("a body over the limit", ["Content-Length: %d" % (serve.SCORES_MAX_BYTES + 1)], b"x" * 10, "too large")]:
                code, res = post_raw(base, scores_path, heads, body)
                check(code == 400 and res.get("ok") is False and want in res.get("error", ""),
                      "%s → 400 with a message (%s %s)" % (label, code, str(res)[:80]))
            deep = b"[" * 60000
            code, res = post_raw(base, scores_path, ["Content-Length: %d" % len(deep)], deep)
            check(code == 400 and "nested" in res.get("error", ""), "JSON nested 60,000 deep → 400, not a traceback (%s %s)" % (code, str(res)[:60]))
            bad = b'{"scores":"\xff\xfe"}'
            code, res = post_raw(base, scores_path, ["Content-Length: %d" % len(bad)], bad)
            check(code == 400 and "JSON" in res.get("error", ""), "a body that is not UTF-8 → 400 (%s)" % code)
            code, res = post_as(base, scores_path, [1, 2])
            check(code == 400 and "JSON object" in res.get("error", ""), "a JSON array is not a payload → 400 (%s %s)" % (code, str(res)[:60]))
            t0 = time.time()
            code, res = post_raw(base, scores_path, ["Content-Length: 99"], b"{}")
            check(code == 400 and "incomplete" in res.get("error", "") and time.time() - t0 < 8,
                  "a body shorter than its Content-Length gives up after a few seconds instead of holding the thread (%.1fs)" % (time.time() - t0))
            check(explore.load_manifest(project, "card") == man_before, "…none of those malformed bodies touched the manifest")
            code, res = post_as(base, scores_path, {"scores": {"hierarchy:opt-9": 4}})
            check(code == 400 and not res["ok"], "the server still answers after all of that — and still validates the sheet")
            partial = {"hierarchy:opt-1": 4, "hierarchy:opt-2": 3}
            code, res = post(base + "/__pb_explore/card/scores", {"scores": partial})
            check(code == 200 and res["ok"] and len(res["missing"]) == 18, "a valid partial save lands; 18 cells remain")
            check(explore.main(["--registry", reg_path, "gate", "card"]) == explore.EXIT_FAIL,
                  "the gate fails while cells are unscored")
            full = {"%s:%s" % (c["id"], s): (4 if s == "opt-2" else 3)
                    for c in explore.DEFAULT_RUBRIC for s in ("opt-1", "opt-2")}
            code, res = post(base + "/__pb_explore/card/scores",
                             {"scores": full, "notes": {"hierarchy": "opt-2 leads"},
                              "verdict": {"pick": "opt-2", "why": "higher on every row", "taught": {"opt-1": "too quiet"}}})
            check(code == 200 and res["missing"] == [], "a complete sheet saves with nothing missing")
        finally:
            httpd.shutdown()
            httpd.server_close()
        check(explore.main(["--registry", reg_path, "gate", "card"]) == explore.EXIT_OK, "the gate passes once every cell is scored")

        print("promote")
        try:
            explore.cmd_promote(reg_path, "card", "opt-1+opt-2")
            check(False, "a mixed pick is refused")
        except explore.ExploreError as e:
            check("mixed pick" in str(e), "a mixed pick is refused and pointed at a merge slot")
        live = os.path.join(project, "render/components/card.js")
        with open(live, "a", encoding="utf-8") as f:
            f.write("// someone else's edit\n")
        try:
            explore.cmd_promote(reg_path, "card", "opt-2")
            check(False, "a promote over a concurrent edit is refused")
        except explore.ExploreError as e:
            check("changed since this exploration started" in str(e), "a promote over a concurrent edit is refused")
        res = explore.cmd_promote(reg_path, "card", "opt-2", force=True)
        with open(live, encoding="utf-8") as f:
            check("card--2" in f.read(), "--force promotes the pick over the live body")
        check(res["drift"] == ["render/components/card.js"], "the overwritten concurrent edit is reported")
        check(os.path.isfile(os.path.join(project, res["backup"], "render/components/card.js")), "the live body was backed up first")
        check(not os.path.exists(os.path.join(project, "render", "_candidates")), "the scratch tree is gone")
        check(not os.path.exists(explore.manifest_path(project, "card")) and os.path.isfile(os.path.join(project, res["archived"])),
              "the manifest is archived, not left open")
        check(explore.sessions(project) == [], "nothing is left in Sandbox → Explore")
        closed = os.path.join(project, res["archived"])[:-len(".json")]
        check(not os.path.exists(brief) and os.path.isfile(closed + ".brief.md"),
              "promote moves the direction brief beside the archived manifest")
        check(not os.path.exists(os.path.join(project, "memory/explore/card/plans"))
              and os.path.isfile(os.path.join(closed, "plans", "opt-1.md")),
              "promote moves plans/ beside the archived manifest")

        print("reject + goal mode")
        explore.cmd_init(reg_path, "new-nav", options=2, goal=True, intent="a calmer navigation")
        problems, _w, _s = explore.cmd_check(reg_path, "new-nav", SHELL)
        check(any("no approach text" in p for p in problems), "a goal option needs its approach written")
        check(not any("axes" in p for p in problems), "goal mode never FAILS on axis distance")
        check(any("differ on only 0 of 7 axes" in w for w in _w), "goal mode warns on axis distance instead")
        write(explore.brief_path(project, "new-nav"), "# Direction\n")
        write(explore.plan_path(project, "new-nav", "opt-1"), "# Plan\n")
        lessons = explore.cmd_reject(reg_path, "new-nav")
        check("archived" in lessons and explore.sessions(project) == [], "reject archives and prints the lessons")
        closed = os.path.join(project, lessons["archived"])[:-len(".json")]
        check(os.path.isfile(closed + ".brief.md") and os.path.isfile(os.path.join(closed, "plans", "opt-1.md"))
              and not os.path.exists(os.path.join(project, "memory/explore/new-nav")),
              "reject moves the brief and plans/ too, and leaves no working folder behind")

        print("page round (--pages)")
        page_round(reg_path, project)

        print("link — the URL the user compares and rates at")
        link_round(reg_path, project)

        print("check --shots — structural convergence (Playwright)")
        shots_convergence(reg_path, project)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ /pb:explore: one manifest, one compare page on the preview server, a real gate, a safe promote")


if __name__ == "__main__":
    main()
