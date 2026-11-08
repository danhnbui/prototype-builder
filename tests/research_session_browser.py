#!/usr/bin/env python3
"""
research_session_browser.py — the /pb:research UX capability, end to end, in a real browser against the real
/pb:preview server. Playwright + stdlib. Everything below is TEST DATA: pseudonyms P01.., invented screens, no
real person or product; the "participants" are this script driving Chromium.

One temp project (a copy of fixtures/research/ plus three small render bodies, so the prototype has real screens
to click) with four studies, one per session method. One managed preview server (`research.py link`).

  A  moderated usability with screen+voice recording: setup -> consent (incl. "record my screen and voice") ->
     warm-up -> task 1 (success by criteria) -> task 2 (give up) -> SEQ -> SUS -> saved. An observer tab opened
     BEFORE the start receives the events, and a note typed there lands as a `note` event in the stored session.
     `research.py show` then has one session row and one recording row linked both ways, files 0444, status
     fielding, the tracker row done.
  B  replay of that session: no console errors, duration > 0, a seek past the 2nd nav shows its screen, the
     video reaches a finite duration, the recording is served with a Range.
  C  participant kit: `research.py kit` -> file:// -> P02 completes (no recording) -> the .pbsession.json is
     downloaded -> `import --kind session` -> `analyze`: two sessions, every task n == 2, every number equal to
     the formula applied to the stored sessions.
  D  tree-test, card-sort, first-click: one served session each -> saved -> analyze; the first click did not
     navigate; the tree-test outcome is "answered".
  F  report: synthesize a minimal valid file -> verify clean -> report -> GET /research/<id>/report is 200 and
     says "Draft — not yet approved at G-INSIGHT".
  E  the Research view: GET / of the served prototype -> Project Summary -> Research -> the usability study row
     opens to Sessions (Replay links, which are followed) and Results (and Issues, Report).
  (F runs before E so the view has results, issues and a report to show.)

Every page collects console errors; any one fails the test. The only thing filtered is a missing favicon.
Every page of a participant is also checked for outside requests (there must be none; the kit must not call out).
The one request the test answers itself is the Mermaid CDN script of the tool's own shell on `/` (no network is
needed or wanted here).

Usage:  python3 tests/research_session_browser.py
Exit:   0 = pass · 1 = a failure · 2 = Playwright/Chromium not available (skip)
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback
import urllib.request

# `link` may start a preview server (a managed one); with no cap it never stops somebody else's preview to make room.
os.environ["PB_PREVIEW_MAX"] = "0"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TOOL = os.path.join(TOOLS, "research.py")
FIX = os.path.join(ROOT, "fixtures", "research")
UX = os.path.join(FIX, "ux")
sys.path.insert(0, TOOLS)

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    print("SKIP: playwright not installed (pip install playwright && playwright install chromium)")
    sys.exit(2)

import browser as pbbrowser  # noqa: E402  (pb/tools/browser.py — the one door to a headless browser)
import research_stats as S   # noqa: E402

WHO = "research-session-browser"
REAL_CAPTURE = ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                "--auto-accept-this-tab-capture", "--auto-select-desktop-capture-source=Entire screen"]

# Used only when this Chromium cannot give a real screen capture (said out loud, as NOT VERIFIED).
CANVAS_STUB = """
(() => {
  const mk = () => {
    const c = document.createElement('canvas'); c.width = 320; c.height = 200;
    const g = c.getContext('2d'); let n = 0;
    setInterval(() => { g.fillStyle = 'hsl(' + (n++ * 9 % 360) + ',60%,50%)'; g.fillRect(0, 0, 320, 200); }, 60);
    return c.captureStream(15);
  };
  const md = navigator.mediaDevices;
  md.getDisplayMedia = async () => mk();
  md.getUserMedia = async () => {
    const ac = new AudioContext(); const o = ac.createOscillator(); const d = ac.createMediaStreamDestination(); o.connect(d); o.start(); return d.stream;
  };
})();
"""

U, T, C, F = "rs-pay-test", "rs-tree-test", "rs-card-sort", "rs-first-click"
NOTE_TEXT = "Participant hesitated before tapping Confirm"
EXTERNAL = re.compile(r"^https?://(?!(?:127\.0\.0\.1|localhost)(?::|/|$))")

fails = []
NOT_VERIFIED = []
CHECKS = [0]
TMP = tempfile.mkdtemp(prefix="pb-rs-browser-")


def check(cond, msg):
    CHECKS[0] += 1
    print(("  ✓ " if cond else "  ✗ ") + msg, flush=True)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title, flush=True)


def not_verified(msg):
    NOT_VERIFIED.append(msg)
    print("  – NOT VERIFIED: " + msg, flush=True)


# ── the project ─────────────────────────────────────────────────────────────────────────────────

SCREENS = {
    "route": """function renderScreenRoute(props) {
  return '<div style="padding:16px;font-family:system-ui,sans-serif">'
    + '<h1 style="font-size:20px;margin:0 0 8px">Route</h1>'
    + '<p id="plain-text" style="margin:0 0 12px">Three parcels are waiting on your route today.</p>'
    + pbUse('parcel-card', { title: 'Parcel 1042', amount: '45' })
    + '<button type="button" data-nav="pay" id="to-pay" style="margin-top:12px;padding:10px 14px">Collect payment</button>'
    + '</div>';
}
""",
    "pay": """function renderScreenPay(props) {
  return '<form onsubmit="return false" style="padding:16px;font-family:system-ui,sans-serif">'
    + '<h1 style="font-size:20px;margin:0 0 8px">Pay</h1>'
    + '<div class="field" style="display:grid;gap:4px;margin-bottom:12px"><label class="field__label" for="amt">Amount received</label>'
    + '<input id="amt" class="field__input" data-required type="text" style="padding:8px"></div>'
    + '<button type="button" id="confirm" data-action="submit" data-go="handover" data-toast="Payment saved" style="padding:10px 14px">Confirm</button> '
    + '<button type="button" data-back="route" style="padding:10px 14px">Back</button>'
    + '</form>';
}
""",
    "handover": """function renderScreenHandover(props) {
  return '<div style="padding:16px;font-family:system-ui,sans-serif">'
    + '<h1 style="font-size:20px;margin:0 0 8px">Handover</h1>'
    + '<p data-done style="margin:0 0 12px">Handed over to the dispatcher.</p>'
    + '<button type="button" data-nav="route" style="padding:10px 14px">Back to route</button></div>';
}
""",
}
CARD = """function renderCmpParcelCard(props) {
  return '<div class="parcel-card" style="border:1px solid #bbb;border-radius:8px;padding:12px"><b>' + (props.title || '') + '</b> <span>' + (props.amount || '') + '</span></div>';
}
"""
PAYBTN = """function renderCmpPayButton(props) { return '<button type="button">' + (props.label || 'Pay') + '</button>'; }
"""


class Proj:
    """A temp copy of fixtures/research/ with render bodies, and a way to run the tool against it."""

    def __init__(self):
        self.dir = os.path.join(TMP, "proj")
        shutil.copytree(FIX, self.dir)
        self.reg = os.path.join(self.dir, "registry.json")
        reg = self.data()
        os.makedirs(os.path.join(self.dir, "render", "screens"))
        os.makedirs(os.path.join(self.dir, "render", "components"))
        for s in reg["screens"]:
            self.write_text("render/screens/%s.js" % s["id"], SCREENS[s["id"]])
            s["renderSrc"] = "render/screens/%s.js" % s["id"]
            s["renderFn"] = "renderScreen" + s["id"].capitalize()
            if s["id"] == "handover":
                # The fixture gates `handover` to dispatchers, but the study's task runs as a courier and its
                # success criterion is that very screen: the shell (correctly) refuses the navigation. The plan
                # and the registry have to agree, so the screen is opened to couriers here.
                s["roles"] = ["courier", "dispatcher"]
        for c in reg["components"]:
            if c["id"] == "parcel-card":
                self.write_text("render/components/parcel-card.js", CARD)
                c["renderSrc"], c["renderFn"] = "render/components/parcel-card.js", "renderCmpParcelCard"
            else:
                self.write_text("render/components/pay-button.js", PAYBTN)
                c["renderSrc"], c["renderFn"] = "render/components/pay-button.js", "renderCmpPayButton"
        self.save(reg)

    def write_text(self, rel, text):
        with open(os.path.join(self.dir, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def run(self, *a):
        cmd = [sys.executable, TOOL, "--registry", self.reg, "--json"] + list(a)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=self.dir)
        try:
            out = json.loads(p.stdout)
        except ValueError:
            out = {}
        return p.returncode, out, p.stderr

    def ok(self, *a):
        rc, out, err = self.run(*a)
        if rc != 0:
            raise AssertionError("research.py %s -> exit %s: %s %s" % (" ".join(a), rc, json.dumps(out)[:400], err[-400:]))
        return out

    def data(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def save(self, d):
        with open(self.reg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def study(self, sid):
        return next(s for s in self.data()["research"]["studies"] if s["id"] == sid)

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def session_of(self, row):
        with open(self.path(row["file"]), encoding="utf-8") as f:
            return json.load(f)

    def session_rows(self, sid):
        return [e for e in self.study(sid).get("evidence", []) if e.get("kind") == "session" and not e.get("dropped")]


def ux(name):
    return os.path.join(UX, name)


def approve(p, sid, method, plan_file, brief=None, mode="unmoderated"):
    """init -> brief -> plan -> review-plan -> review -> approve, the way a researcher does it."""
    if method == "usability":
        p.ok("init", sid, "--method", method, "--scope", "collect", "--question", "Can couriers pay for a parcel?",
             "--role", "courier", "--target", "screen:pay", "--mode", mode)
    else:
        p.ok("init", sid, "--method", method, "--scope", "collect", "--question", "TEST DATA question?",
             "--segment", "existing app users", "--mode", mode)
    if brief:
        p.ok("brief", sid, "--file", ux(brief))
    p.ok("plan", sid, "--file", ux(plan_file))
    out = p.ok("review-plan", sid)
    rows = os.path.join(p.dir, "rows-%s.txt" % sid)
    with open(rows, "w", encoding="utf-8") as f:
        f.write("\n".join("%s · yes · the words of the question hold" % i for i in out["items"]) + "\n")
    p.ok("review", sid, "--file", rows)
    p.ok("approve", sid, "--note", "test data")


# ── the browser side ────────────────────────────────────────────────────────────────────────────

class Watch:
    """Console errors and outside requests of every page opened through it."""

    def __init__(self):
        self.errors = []
        self.favicon = 0
        self.external = []

    def attach(self, page, tag):
        def on_console(m):
            if m.type != "error":
                return
            loc = m.location if isinstance(m.location, dict) else {}
            if str(loc.get("url", "")).endswith("/favicon.ico"):
                self.favicon += 1
                return
            self.errors.append((tag, m.text))
        page.on("console", on_console)
        page.on("pageerror", lambda e: self.errors.append((tag, "pageerror: %s" % e)))

    def context(self, b, tag, **kw):
        ctx = b.new_context(**kw)
        ctx.set_default_timeout(20000)

        def handler(route):
            self.external.append((tag, route.request.url))
            route.fulfill(status=200, body="", content_type="text/javascript")
        ctx.route(EXTERNAL, handler)
        return ctx


def click_btn(page, name):
    page.get_by_role("button", name=name, exact=True).click()


def pick_option(page, text):
    page.locator(".pb-rs-opt", has_text=text).click()


def pick_point(fieldset, n):
    """The n-th point of a scale (1-based, scales here start at 1)."""
    fieldset.locator("label.pb-rs-pt").nth(n - 1).click()


def pick_scale(page, n):
    pick_point(page.locator("fieldset.pb-rs-q").first, n)


def sus_card(page, value_for):
    """Answer every SUS item on the card: value_for(i) for the i-th item (0-based)."""
    fs = page.locator("fieldset.pb-rs-q")
    expect(fs.first).to_be_visible()
    n = fs.count()
    for i in range(n):
        pick_point(fs.nth(i), value_for(i))
    return n


def go_setup(page, prefilled=None, code=None):
    inp = page.locator("#pb-rs-pcode")
    expect(inp).to_be_visible()
    if prefilled is not None:
        assert inp.input_value() == prefilled, inp.input_value()
    else:
        inp.press_sequentially(code, delay=20)
    click_btn(page, "Continue")


def go_consent(page, record=False):
    expect(page.get_by_role("heading", name="Taking part")).to_be_visible()
    page.locator("#pb-rs-agree").check()
    if record:
        page.locator("#pb-rs-rec").check()
    click_btn(page, "Continue")


def task_one(page, done=True):
    """The pay task: a dead click, a component click, an empty submit (a field error), a typed amount, the
    submit that reaches the handover screen. Then 'I'm done'."""
    click_btn(page, "Start task")
    expect(page.locator("#pb-rs-done")).to_be_visible()
    page.wait_for_timeout(200)
    page.locator("#plain-text").click()                       # a dead click (plain text)
    page.wait_for_timeout(300)
    page.locator(".parcel-card").click()                      # a component (named by pbInspectComponent)
    page.wait_for_timeout(300)
    page.locator("#to-pay").click()
    expect(page.locator("#amt")).to_be_visible()
    page.wait_for_timeout(300)
    page.locator("#confirm").click()                          # empty -> a field error
    page.wait_for_timeout(300)
    page.locator("#amt").press_sequentially("45", delay=30)   # typed; the value is never recorded
    page.wait_for_timeout(300)
    page.locator("#confirm").click()                          # ok -> toast + handover
    expect(page.locator("[data-done]")).to_be_visible()
    page.wait_for_timeout(500)                                # past the 150 ms criteria debounce
    if done:
        page.locator("#pb-rs-done").click()


def uninteresting_seq(page, value):
    expect(page.get_by_role("heading", name="About this task")).to_be_visible()
    pick_scale(page, value)
    click_btn(page, "Continue")


def read_sess(p, sid, n=-1):
    rows = p.session_rows(sid)
    return rows[n], p.session_of(rows[n])


def sus_score(answers):
    """The SUS formula, applied to the stored answers (items sus-1..sus-10): 2.5 * (sum odd (v-1) + sum even (5-v))."""
    tot = 0
    for i in range(1, 11):
        v = answers["sus-%d" % i]
        tot += (v - 1) if i % 2 == 1 else (5 - v)
    return tot * 2.5


# ═════════════════════════════════════════════════════════════════════════════
# A — moderated usability with recording, observer

def scenario_a(p, b, base, W, S_):
    section("A · moderated usability with screen+voice recording, observer tab")
    p.ok("participant", U, "P01", "--status", "scheduled", "--segment", "rural courier", "--role", "courier")
    ctx = W.context(b, "A", viewport={"width": 1280, "height": 900}, accept_downloads=True)
    obs = ctx.new_page()
    W.attach(obs, "A observer")
    obs.set_viewport_size({"width": 1000, "height": 800})
    obs.goto("%s/research/%s/observer?p=P01" % (base, U))
    expect(obs.locator("#pb-rs-ob-note")).to_be_visible()

    # The capture mode was decided once, before any scenario (decide_capture); A only applies it.
    if S_["capture_mode"] == "stub":
        ctx.add_init_script(CANVAS_STUB)
        S_["real_capture"] = False
    else:
        S_["real_capture"] = True
        check(True, "this Chromium gives a real getDisplayMedia + getUserMedia (fake devices, auto-accepted)")

    page = ctx.new_page()
    W.attach(page, "A session")
    page.goto("%s/research/%s/session?p=P01" % (base, U))
    expect(page.locator("#pb-rs-pcode")).to_be_visible()
    check(page.locator("#pb-rs-rec").count() == 0, "the record checkbox is not on the setup card")
    go_setup(page, prefilled="P01")
    expect(page.get_by_role("heading", name="Taking part")).to_be_visible()
    check(page.locator("#pb-rs-rec").count() == 1, "the consent card offers 'record my screen and voice'")
    go_consent(page, record=True)

    expect(page.get_by_role("heading", name="About you")).to_be_visible(timeout=20000)
    check(page.get_by_text("Recording did not start").count() == 0, "no 'Recording did not start' card")
    pick_option(page, "1 to 3 years")
    click_btn(page, "Continue")

    expect(page.get_by_role("heading", name="Task 1 of 2")).to_be_visible()
    task_one(page)
    uninteresting_seq(page, 6)

    expect(page.get_by_role("heading", name="Task 2 of 2")).to_be_visible()
    click_btn(page, "Start task")
    expect(page.locator("#pb-rs-giveup")).to_be_visible()
    obs.locator("#pb-rs-ob-note").fill(NOTE_TEXT)
    obs.get_by_role("button", name="Add note").click()
    page.wait_for_timeout(400)
    page.locator("#pb-rs-giveup").click()
    uninteresting_seq(page, 3)

    expect(page.locator("fieldset.pb-rs-q").first).to_be_visible()
    n_sus = sus_card(page, lambda i: 4)
    check(n_sus == 10, "the closing card holds the ten SUS items (%d)" % n_sus)
    click_btn(page, "Continue")

    expect(page.get_by_text(re.compile(r"Saved as e\d+"))).to_be_visible(timeout=20000)
    expect(page.get_by_text("The recording was uploaded")).to_be_visible(timeout=30000)
    sink = page.locator(".pb-rs-sink").inner_text().replace("\n", " | ")
    print("    final card: " + sink)
    check(page.locator(".pb-rs-sink a.pb-rs-link").count() == 1, "the final card links to the replay")

    # the observer saw it live
    feed = obs.locator("#pb-rs-ob-feed li")
    n_feed = feed.count()
    print("    observer: %d feed rows · connection: %s" % (n_feed, obs.locator("#pb-rs-ob-conn").inner_text().strip()))
    check(n_feed >= 8, "the observer tab (opened before the start) received the events live (%d rows)" % n_feed)

    # what the tool stored
    study = p.study(U)
    sess_rows = [e for e in study["evidence"] if e["kind"] == "session"]
    rec_rows = [e for e in study["evidence"] if e["kind"] == "recording"]
    check(len(sess_rows) == 1 and len(rec_rows) == 1, "one session row and one recording row (%d, %d)" % (len(sess_rows), len(rec_rows)))
    srow, rrow = sess_rows[0], rec_rows[0]
    sess = p.session_of(srow)
    check(study["status"] == "fielding", "the study is now fielding (%s)" % study["status"])
    check(srow["session"]["id"] == sess["sessionId"] and srow["session"]["media"] == [rrow["id"]] and srow["session"]["recording"] is True,
          "the session row points at the recording row (media %s)" % srow["session"]["media"])
    check(rrow.get("session") == sess["sessionId"] and rrow.get("mime") == "video/webm", "the recording row points back at the session (%s)" % rrow.get("session"))
    for label, row in (("session", srow), ("recording", rrow)):
        path = p.path(row["file"])
        mode = stat.S_IMODE(os.stat(path).st_mode)
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        check(mode == 0o444, "%s file is 0444 (%s)" % (label, oct(mode)))
        check(digest == row["sha256"], "%s file hash equals the row's sha256" % label)
    check(os.path.getsize(p.path(rrow["file"])) > 1000, "the recording is not empty (%d bytes)" % os.path.getsize(p.path(rrow["file"])))
    with open(p.path(rrow["file"]), "rb") as f:
        check(f.read(4) == b"\x1a\x45\xdf\xa3", "the recording is WebM (EBML magic)")
    inc = p.path("memory", "research", U, ".incoming")
    check(not os.path.isdir(inc) or os.listdir(inc) == [], "no temp upload is left in .incoming")
    prow = next((x for x in study.get("participants", []) if x["id"] == "P01"), None)
    check(prow is not None and prow["status"] == "done" and prow.get("sessionAt"), "the tracker has P01 done with a session date")

    consent_text = study["instrument"]["consent"]
    check(sess["format"] == "pb-session" and sess["participant"] == "P01" and sess["mode"] == "moderated" and sess["pilot"] is False
          and sess["env"]["sink"] == "server" and sess["env"]["device"] == "mobile", "the session is P01, moderated, not a pilot, sink server, device mobile")
    check(sess["consent"]["session"] is True and sess["consent"]["recording"] is True
          and sess["consent"]["textSha256"] == hashlib.sha256(consent_text.encode("utf-8")).hexdigest(),
          "consent: session + recording, and the hash of the consent text shown")
    tasks = {t["id"]: t for t in sess["tasks"]}
    check(set(tasks) == {"t1", "t2"}, "two tasks recorded (%s)" % sorted(tasks))
    check(tasks["t1"]["outcome"] == "success" and tasks["t1"]["outcomeSource"] == "criteria" and tasks["t1"]["criteriaT"] is not None
          and tasks["t1"]["assisted"] is False, "t1: success by criteria")
    check(tasks["t2"]["outcome"] == "abandoned" and tasks["t2"]["selfReport"] == "gave-up", "t2: abandoned (gave up)")
    check(tasks["t1"]["answers"].get("t1-seq") == 6 and tasks["t2"]["answers"].get("t2-seq") == 3, "SEQ answers 6 and 3 are on their tasks")
    check(all("sus-%d" % i in sess["answers"] for i in range(1, 11)) and sess["answers"].get("w1") == "1 to 3 years",
          "warm-up and the ten SUS answers are in session.answers")
    ev = sess["events"]
    types = {e["type"] for e in ev}
    want = {"session-start", "consent", "task-start", "task-end", "nav", "click", "criteria", "field-error", "submit", "toast", "input",
            "answer", "note", "media-start", "media-stop", "session-end"}
    check(want <= types, "event types present (missing: %s)" % sorted(want - types))
    check(any(e["type"] == "click" and e.get("dead") for e in ev), "a dead click was recorded")
    check(any(e["type"] == "click" and e.get("cmp") for e in ev), "a click on a component carries its name")
    inputs = [e for e in ev if e["type"] == "input"]
    check(inputs and all("value" not in e for e in inputs) and any(e.get("len") == 2 for e in inputs), "typed input records the length, never the value")
    notes = [e for e in ev if e["type"] == "note"]
    check(len(notes) == 1 and notes[0]["text"] == NOTE_TEXT and notes[0].get("by") == "facilitator" and notes[0].get("task") == "t2",
          "the observer's note is a facilitator `note` event on t2 (%s)" % json.dumps(notes))
    check([e["t"] for e in ev] == sorted(e["t"] for e in ev), "event times never go backwards")
    S_.update(a_row=srow, a_rec=rrow, a_sess=sess, a_sid=sess["sessionId"])
    check(not [x for x in W.external if x[0] == "A"], "no outside request from the participant or observer pages (%s)" % [x for x in W.external if x[0] == "A"][:2])
    ctx.close()


# ═════════════════════════════════════════════════════════════════════════════
# B — replay

def scenario_b(p, b, base, W, S_):
    section("B · replay of the recorded session")
    srow, rrow, sess = S_["a_row"], S_["a_rec"], S_["a_sess"]
    ctx = W.context(b, "B", viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    W.attach(page, "B replay")
    page.goto("%s/research/%s/replay/%s" % (base, U, srow["id"]))
    page.wait_for_function("window.pbRsReplay && document.querySelector('.proto-screen')", timeout=20000)
    page.wait_for_timeout(300)
    dur = page.evaluate("window.pbRsReplay.duration()")
    last_t = max(e["t"] for e in sess["events"])
    check(dur > 0 and dur >= last_t, "pbRsReplay.duration() = %s ms, covers the last event (%s)" % (dur, last_t))
    check(page.evaluate("getComputedStyle(document.getElementById('meta-nav')).display") == "none", "the tool bar is hidden on the replay page")
    navs = sorted([e for e in sess["events"] if e["type"] == "nav"], key=lambda e: e["t"])
    check(len(navs) >= 2, "the stored session has at least two navs (%d)" % len(navs))
    n0, n1 = navs[0], navs[1]
    page.evaluate("t => window.pbRsReplay.seek(t)", n0["t"] + 100)
    page.wait_for_timeout(150)
    s0 = page.evaluate("state.protoScreenId")
    check(s0 == n0["to"], "seek just past the 1st nav (t=%s) shows %s (got %s)" % (n0["t"], n0["to"], s0))
    page.evaluate("t => window.pbRsReplay.seek(t)", n1["t"] + 500)
    page.wait_for_timeout(150)
    s1 = page.evaluate("state.protoScreenId")
    check(s1 == n1["to"], "seek past the 2nd nav (t=%s) shows %s (got %s)" % (n1["t"], n1["to"], s1))
    check(page.evaluate("t => window.pbRsReplay.screenAt(t)", n1["t"] + 500) == n1["to"], "screenAt() agrees")
    check(page.locator(".proto-screen h1").first.inner_text().strip().lower() == n1["to"], "the screen drawn is the %s screen" % n1["to"])

    page.wait_for_function("window.pbRsReplay.videoState() !== 'loading'", timeout=30000)
    vs = page.evaluate("window.pbRsReplay.videoState()")
    vd = page.evaluate("(() => { const v = window.pbRsReplay.video(); return v ? [v.duration, v.readyState] : null; })()")
    if vs == "ready" and vd and vd[0] == vd[0] and vd[0] not in (float("inf"),) and vd[0] > 0:
        check(True, "the video reaches a finite duration (%.2f s, state %s)" % (vd[0], vs))
    else:
        check(False, "the video reaches a finite duration (state %s, duration/readyState %s)" % (vs, vd))
    start = page.evaluate("window.pbRsReplay.videoStart()")
    if vs == "ready" and vd and vd[0] and vd[0] == vd[0] and vd[0] != float("inf"):
        T = int(min(dur, start + vd[0] * 1000) * 0.5)
        page.evaluate("t => window.pbRsReplay.seek(t)", T)
        page.wait_for_timeout(600)
        ct = page.evaluate("window.pbRsReplay.video().currentTime")
        exp = max(0.0, min((T - start) / 1000.0, vd[0]))
        check(abs(ct - exp) <= 0.5, "seek T=%d moves the video to %.2f s (expected %.2f)" % (T, ct, exp))

    # the recording itself is served with a Range
    url = "%s/__pb_research/%s/evidence/%s" % (base, U, rrow["id"])
    req = urllib.request.Request(url, headers={"Range": "bytes=0-3"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        check(r.status == 206 and body == b"\x1a\x45\xdf\xa3", "the recording is served as a 206 range (EBML magic)")
    with urllib.request.urlopen("%s/__pb_research/%s/evidence/%s" % (base, U, srow["id"]), timeout=30) as r:
        served = r.read()
    check(hashlib.sha256(served).hexdigest() == srow["sha256"], "the session file is served byte for byte")
    check(not [x for x in W.external if x[0] == "B"], "no outside request from the replay page")
    ctx.close()


# ═════════════════════════════════════════════════════════════════════════════
# C — the participant kit

def scenario_c(p, b, W, S_):
    section("C · participant kit (file://), download, import, analyze")
    out = p.ok("kit", U)
    kit = out["path"]
    check(os.path.isfile(kit) and out["bytes"] > 10000, "kit: a self-contained file (%s bytes)" % out["bytes"])
    html = open(kit, encoding="utf-8").read()
    study = p.study(U)
    secret = [study["title"]] + [h[k] for h in study["hypotheses"] for k in ("statement", "supportedIf", "refutedIf")]
    leaked = [s for s in secret if s and s in html]
    check(not leaked, "the kit holds no hypothesis, threshold or study title (found: %s)" % leaked)
    check(not re.search(r'<script[^>]+src="https?://', html), "the kit loads no outside script")

    ctx = W.context(b, "C", viewport={"width": 1100, "height": 850}, accept_downloads=True)
    page = ctx.new_page()
    W.attach(page, "C kit")
    page.goto("file://" + kit)
    go_setup(page, code="P02")
    go_consent(page, record=False)
    check(page.locator("#pb-rs-rec").count() == 0, "(recording was not ticked)")
    expect(page.get_by_role("heading", name="About you")).to_be_visible()
    pick_option(page, "Over 3 years")
    click_btn(page, "Continue")
    expect(page.get_by_role("heading", name="Task 1 of 2")).to_be_visible()
    task_one(page)
    uninteresting_seq(page, 5)
    expect(page.get_by_role("heading", name="Task 2 of 2")).to_be_visible()
    click_btn(page, "Start task")
    expect(page.locator("#pb-rs-done")).to_be_visible()
    page.wait_for_timeout(300)
    page.locator("#to-pay").click()
    page.wait_for_timeout(300)
    page.locator("#pb-rs-done").click()
    uninteresting_seq(page, 2)
    # SUS: odd items 5, even items 1 -> the best score
    sus_card(page, lambda i: 5 if i % 2 == 0 else 1)
    click_btn(page, "Continue")

    btn = page.get_by_role("button", name=re.compile("Download the session file"))
    expect(btn).to_be_visible(timeout=20000)
    check(page.get_by_role("button", name=re.compile("Download the recording")).count() == 0, "no recording to download (none was consented)")
    with page.expect_download() as dl:
        btn.click()
    d = dl.value
    dl_path = os.path.join(TMP, d.suggested_filename)
    d.save_as(dl_path)
    check(d.suggested_filename.endswith(".pbsession.json") and "P02" in d.suggested_filename, "downloaded %s" % d.suggested_filename)
    obj = json.load(open(dl_path, encoding="utf-8"))
    check(obj["participant"] == "P02" and obj["mode"] == "unmoderated" and obj["env"]["sink"] == "download"
          and obj["consent"]["recording"] is False and obj["media"] == [], "the file: P02, unmoderated, sink download, no recording")
    check(len(p.session_rows(U)) == 1, "nothing was posted by the kit (still one session on disk)")

    p.ok("import", U, dl_path, "--kind", "session", "--consent", "yes")
    check(len(p.session_rows(U)) == 2, "import: two sessions now")
    p.ok("analyze", U)
    an = p.study(U)["analysis"]
    sessions = [p.session_of(r) for r in p.session_rows(U)]
    check(an["n"] == 2 and an["method"] == "usability", "analysis.n == 2 (%s)" % an["n"])
    tasks = an["usability"]["tasks"]
    check(set(tasks) == {"t1", "t2"} and all(tasks[t]["n"] == 2 for t in tasks), "analysis.usability.tasks: both tasks have n == 2 (%s)" % {t: tasks[t]["n"] for t in tasks})
    for tid in ("t1", "t2"):
        rows = [t for s in sessions for t in s["tasks"] if t["id"] == tid]
        x = sum(1 for t in rows if t["outcome"] == "success" and not t["assisted"])
        # the formula returns full floats; every float the tool stores goes through r4 (the contract's rule)
        want = {k: (S.r4(v) if isinstance(v, float) else v) for k, v in S.adjusted_wald(x, len(rows)).items()}
        check(tasks[tid]["success"] == want, "%s success equals adjusted_wald(%d, %d) = %s" % (tid, x, len(rows), tasks[tid]["success"]))
        seqs = [t["answers"][tid + "-seq"] for t in rows]
        check(abs(tasks[tid]["seq"]["mean"] - sum(seqs) / float(len(seqs))) < 1e-3, "%s SEQ mean equals the mean of %s" % (tid, seqs))
    scores = [sus_score(s["answers"]) for s in sessions]
    check(abs(an["usability"]["sus"]["mean"] - sum(scores) / len(scores)) < 1e-3 and an["usability"]["sus"]["n"] == 2,
          "SUS mean equals the formula on the stored answers %s (%s)" % (scores, an["usability"]["sus"]["mean"]))
    check(an["usability"]["tasks"]["t1"]["deadClicks"]["total"] >= 1, "dead clicks are counted (%s)" % an["usability"]["tasks"]["t1"]["deadClicks"])
    check(not [x for x in W.external if x[0] == "C"], "the kit made no outside request (%s)" % [x for x in W.external if x[0] == "C"][:2])
    ctx.close()


# ═════════════════════════════════════════════════════════════════════════════
# D — tree-test, card-sort, first-click

def center(loc):
    bb = loc.bounding_box()
    return bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2


def drag_card(page, card_id, key):
    c = page.locator('.pb-rs-cs-card[data-card="%s"]' % card_id)
    c.scroll_into_view_if_needed()
    sx, sy = center(c)
    pane = page.locator('.pb-rs-cs-pane[data-drop="%s"]' % key).bounding_box()
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 10, sy + 10, steps=3)
    page.mouse.move(pane["x"] + pane["width"] / 2, pane["y"] + min(pane["height"] - 4, 20), steps=8)
    page.mouse.up()


def put_card(page, card_id, key):
    page.wait_for_timeout(60)
    page.locator('.pb-rs-cs-card[data-card="%s"]' % card_id).click()
    page.locator('.pb-rs-cs-pane[data-drop="%s"] button:has-text("Put here")' % key).click()


def select_card(page, card_id, key):
    page.wait_for_timeout(60)
    page.locator('.pb-rs-cs-card[data-card="%s"]' % card_id).click()
    page.select_option(".pb-rs-cs-sel", key)


def scenario_d(p, b, base, W, S_):
    section("D · tree-test, card-sort, first-click (one served session each)")
    ctx = W.context(b, "D", viewport={"width": 1100, "height": 850})
    # ── tree test
    page = ctx.new_page()
    W.attach(page, "D tree")
    page.goto("%s/research/%s/session?p=P01" % (base, T))
    go_setup(page, prefilled="P01")
    go_consent(page)
    for q_text, node_open, pick in (("You were charged twice", "Orders", "Refunds"), ("You moved house", "Account", "Addresses")):
        expect(page.get_by_role("heading", name=re.compile(q_text))).to_be_visible()
        page.locator(".pb-rs-tt-node", has_text=node_open).first.click()
        page.get_by_role("button", name="I’d find it here: " + pick).click()
    expect(page.get_by_text(re.compile(r"Saved as e\d+"))).to_be_visible(timeout=20000)
    row, sess = read_sess(p, T)
    check([t["outcome"] for t in sess["tasks"]] == ["answered", "answered"], "tree-test: both outcomes are 'answered' (%s)" % [t["outcome"] for t in sess["tasks"]])
    res = sess["result"]["tree-test"]
    check(res["tt1"]["chosen"] == "n-refunds" and res["tt1"]["path"] == ["n-orders", "n-refunds"] and res["tt2"]["chosen"] == "n-address",
          "tree-test: the chosen nodes and the path are stored (%s)" % json.dumps(res))
    check({"tt-open", "tt-choose"} <= {e["type"] for e in sess["events"]}, "tree-test: tt-open and tt-choose events")
    p.ok("analyze", T)
    an = p.study(T)["analysis"]["treeTest"]["tasks"]
    check(an["tt1"]["success"]["x"] == 1 and an["tt1"]["success"]["n"] == 1 and an["tt2"]["success"]["x"] == 1, "tree-test analyze: both tasks scored right against the answer key")
    check(an["tt1"]["destinations"][0]["node"] == "n-refunds", "tree-test analyze: destination n-refunds")
    page.close()

    # ── card sort (hybrid: two fixed categories + one group of the participant's own)
    page = ctx.new_page()
    W.attach(page, "D cards")
    page.goto("%s/research/%s/session?p=P01" % (base, C))
    go_setup(page, prefilled="P01")
    go_consent(page)
    page.wait_for_selector(".pb-rs-cs-board")
    page.locator("button", has_text="New group").click()
    inp = page.locator(".pb-rs-cs-gname").last
    inp.fill("Help")
    page.keyboard.press("Enter")
    keys = page.evaluate("Array.from(document.querySelectorAll('.pb-rs-cs-pane[data-drop]')).map(e => e.dataset.drop).filter(k => k)")
    money, parcels = "c-k-money", "c-k-parcels"
    check(money in keys and parcels in keys and len(keys) == 3, "card-sort: the two fixed categories and the new group are on the board (%s)" % keys)
    custom = [k for k in keys if k not in (money, parcels)][0]
    drag_card(page, "c-refund", money)                   # a real drag
    put_card(page, "c-pay", money)                       # select, then 'Put here'
    select_card(page, "c-receipt", money)                # select, then the move menu
    put_card(page, "c-track", parcels)
    put_card(page, "c-address", parcels)
    put_card(page, "c-support", custom)
    left = page.evaluate("pbRsSession.session.result['card-sort'].unsorted")
    check(left == [], "card-sort: every card has a group (unsorted: %s)" % left)
    page.locator(".pb-rs-cs-foot button", has_text="Done").click()
    expect(page.get_by_text(re.compile(r"Saved as e\d+"))).to_be_visible(timeout=20000)
    row, sess = read_sess(p, C)
    groups = {g["name"]: g for g in sess["result"]["card-sort"]["groups"]}
    check(set(groups["Money"]["cards"]) == {"c-refund", "c-pay", "c-receipt"} and groups["Money"]["category"] == "k-money", "card-sort: Money holds refund, pay, receipt (%s)" % groups["Money"])
    check(set(groups["Parcels"]["cards"]) == {"c-track", "c-address"} and groups["Help"]["cards"] == ["c-support"] and groups["Help"]["category"] is None,
          "card-sort: Parcels holds track+address; the participant's own group 'Help' has no category")
    check({"cs-group", "cs-move"} <= {e["type"] for e in sess["events"]}, "card-sort: cs-group and cs-move events")
    p.ok("analyze", C)
    cs = p.study(C)["analysis"]["cardSort"]
    check(cs["n"] == 1 and cs["similarity"]["c-pay|c-receipt"] == 1.0 and cs["similarity"]["c-refund|c-track"] == 0.0,
          "card-sort analyze: pay+receipt together (1.0), refund and track apart (0.0)")
    cats = cs["categories"]
    check("k-money" in cats and cats["k-money"]["label"] == "Money" and cats["k-money"]["count"] == 1
          and cats["k-money"]["cards"] == {"c-refund": 1.0, "c-pay": 1.0, "c-receipt": 1.0},
          "card-sort analyze: the fixed category k-money (label Money) has the three cards, agreement 1.0 (%s)" % cats.get("k-money"))
    own = [v for v in cats.values() if v["label"] == "Help"]
    check(len(own) == 1 and own[0]["cards"] == {"c-support": 1.0}, "card-sort analyze: the participant's own group 'Help' is counted by its name (%s)" % own)
    page.close()

    # ── first click
    page = ctx.new_page()
    W.attach(page, "D click")
    page.goto("%s/research/%s/session?p=P01" % (base, F))
    go_setup(page, prefilled="P01")
    go_consent(page)
    expect(page.get_by_role("heading", name=re.compile("Where do you tap"))).to_be_visible()
    page.get_by_role("button", name="Show me").click()
    expect(page.locator("#confirm")).to_be_visible()
    check(page.evaluate("state.protoScreenId") == "pay", "first-click: the task starts on the pay screen")
    page.wait_for_timeout(400)
    page.locator("#confirm").click()
    page.wait_for_timeout(300)
    check(page.evaluate("state.protoScreenId") == "pay", "first-click: the click did not navigate (still on pay)")
    expect(page.get_by_text(re.compile(r"Saved as e\d+"))).to_be_visible(timeout=20000)
    row, sess = read_sess(p, F)
    fc = sess["result"]["first-click"]["fc1"]
    ev = sess["events"]
    check(fc["hit"] is True and 0 <= fc["x"] <= 1 and 0 <= fc["y"] <= 1, "first-click: a hit, x/y as fractions (%s, %s)" % (fc["x"], fc["y"]))
    check(not any(e["type"] in ("submit", "toast") for e in ev) and not any(e["type"] == "nav" and e.get("to") == "handover" for e in ev),
          "first-click: no submit, no toast, no nav to the handover screen in the stored events")
    check(sum(1 for e in ev if e["type"] == "fc-click") == 1, "first-click: exactly one fc-click event")
    p.ok("analyze", F)
    fa = p.study(F)["analysis"]["firstClick"]["tasks"]["fc1"]
    check(fa["n"] == 1 and fa["success"]["x"] == 1, "first-click analyze: 1 of 1 hit")
    page.close()
    check(not [x for x in W.external if x[0] == "D"], "no outside request from the method pages")
    ctx.close()


# ═════════════════════════════════════════════════════════════════════════════
# F — synthesize, verify, report

def scenario_f(p, base, S_):
    section("F · synthesize -> verify -> report")
    study = p.study(U)
    an = study["analysis"]
    t1, t2 = an["usability"]["tasks"]["t1"], an["usability"]["tasks"]["t2"]
    rows = p.session_rows(U)
    row = next(r for r in rows if r["session"]["id"] == S_["a_sid"])
    sess = p.session_of(row)
    err_i = next(i for i, e in enumerate(sess["events"]) if e["type"] == "field-error")
    syn = {
        "verdicts": {"h1": {"verdict": "mixed", "why": "One courier finished the pay task unaided and one did too, but the sessions are few."},
                     "h2": {"verdict": "mixed", "why": "The total was looked for before it was found."}},
        "observations": [{"id": "o1", "evidence": row["id"], "participant": "P01", "task": "t1", "event": err_i,
                          "note": "Pressed Confirm with the amount empty and got a required-field error", "tags": ["validation"]}],
        "themes": [{"id": "th1", "title": "Errors appear late", "tags": ["validation"], "insight": "The error shows only after the first press."}],
        "issues": [{"id": "u1", "title": "A required-field error with no hint", "task": "t1", "screen": "pay", "severity": 2,
                    "observations": ["o1"], "recommendation": "Say what is required before the first press.",
                    "targets": [{"kind": "screen", "id": "pay"}]}],
        "findings": [{"id": "f1", "text": "The pay task was completed by the couriers who tried it.", "hypotheses": ["h1"],
                      "evidence": [{"analysis": "usability.tasks.t1.success.rate", "value": t1["success"]["rate"]},
                                   {"issue": "u1"}]},
                     {"id": "f2", "text": "Finding the total was harder than paying.", "hypotheses": ["h2"],
                      "evidence": [{"analysis": "usability.tasks.t2.success.rate", "value": t2["success"]["rate"]},
                                   {"observation": "o1"}]}],
        "report": {"summary": "The pay task works; the first error comes late.",
                   "recommendations": [{"text": "Hint the required field.", "issues": ["u1"], "route": "build"}],
                   "nextSteps": ["Retest after the change."], "limitations": ["Only a few couriers took part."]}}
    f = os.path.join(p.dir, "synthesis.json")
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(syn, fh, ensure_ascii=False, indent=2)
    p.ok("synthesize", U, "--file", f)
    rc, v, err = p.run("verify", U)
    check(rc == 0 and not v.get("errors"), "verify: clean (exit %s, errors %s)" % (rc, v.get("errors")))
    st = p.study(U)
    check(st["issues"][0].get("severity") == 2 and p.study(U)["analysis"]["issues"]["u1"]["participants"] == 1,
          "the tool computed the issue's participants (%s)" % p.study(U)["analysis"]["issues"])
    out = p.ok("report", U)
    check(out.get("url") and out["url"].endswith("/research/%s/report" % U), "report: the tool prints the preview URL (%s)" % out.get("url"))
    with urllib.request.urlopen("%s/research/%s/report" % (base, U), timeout=30) as r:
        body = r.read().decode("utf-8")
        check(r.status == 200 and "Draft — not yet approved at G-INSIGHT" in body, "GET /research/%s/report -> 200 with the Draft banner" % U)
    visible = re.sub(r"<[^>]+>", " ", re.sub(r"<(style|script)\b.*?</\1>", " ", body, flags=re.S | re.I))
    check("P01" in visible and "P02" in visible, "the report names the participants by pseudonym (P01, P02)")
    check(not re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", visible), "…and shows no email address")


# ═════════════════════════════════════════════════════════════════════════════
# E — the Research view

def scenario_e(p, b, base, W, S_):
    section("E · the Research view on the served prototype")
    ctx = W.context(b, "E", viewport={"width": 1440, "height": 900}, accept_downloads=True)
    # The tool's own shell loads Mermaid from a CDN (with an integrity hash). This test needs no network, so the
    # one <script> tag is dropped from the served document — what the participant pages already do on purpose.
    def no_cdn(route):
        resp = route.fetch()
        body = re.sub(r'<script\b[^>]*mermaid[^>]*>\s*</script>', "", resp.text(), flags=re.I)
        route.fulfill(response=resp, body=body)
    ctx.route(base + "/", no_cdn)
    page = ctx.new_page()
    W.attach(page, "E view")
    page.goto(base + "/", wait_until="domcontentloaded")
    page.wait_for_selector(".pb-product", state="attached", timeout=30000)
    page.wait_for_timeout(500)
    check(page.evaluate("!!window.PB_PREVIEW"), "the served page is a live preview (window.PB_PREVIEW)")
    page.evaluate("setMetaView('summary'); setSummarySubTab('research')")
    page.wait_for_timeout(300)
    row = page.locator('.pb-scan-tr[data-fb-list="rs"][data-key="%s"]' % U)
    expect(row).to_be_visible()
    rows_n = page.locator(".pb-scan--rs .pb-scan-tr").count()
    check(rows_n == 4, "one row per study (%d)" % rows_n)
    check(row.locator("> .pb-disc-b").is_hidden(), "the usability study is closed until opened")
    row.locator("> .pb-disc-t").click()
    page.wait_for_timeout(200)
    check(row.locator("> .pb-disc-b").is_visible(), "the usability study opens")
    heads = [h.strip() for h in row.locator("h4.rs-h").all_inner_texts()]
    print("    sections in the opened study: %s" % heads)
    check("Sessions" in heads and "Results" in heads, "the opened study shows Sessions and Results")
    links = row.locator("tr[data-rs-session] a.lg-link")
    hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
    texts = [links.nth(i).inner_text().strip() for i in range(links.count())]
    rows = p.session_rows(U)
    want = ["/research/%s/replay/%s" % (U, r["id"]) for r in rows]
    check(texts == ["Replay"] * len(rows) and hrefs == want, "each session row has a Replay link to /research/<id>/replay/<eid> (%s)" % hrefs)
    top = row.locator("p.rs-links").first.inner_text()
    check("Start a moderated session" in top and "Open observer" in top, "the Sessions block offers 'Start a moderated session' and 'Open observer'")
    res = row.locator("tr[data-rs-task]")
    check(res.count() == 2, "Results has a row per task (%d)" % res.count())
    check("2 of 2" in res.first.inner_text() or "of 2" in res.first.inner_text(), "…with the success counts of the stored analysis (%s)" % res.first.inner_text().replace("\n", " ")[:80])
    check(row.locator("[data-rs-issue], .rs-issues, h4.rs-h:has-text('Issues')").count() >= 1, "Issues are listed")
    rep = row.locator("a.lg-link:has-text('Open report')")
    check(rep.count() == 1 and rep.get_attribute("href") == "/research/%s/report" % U, "the Report block links to /research/<id>/report")

    # follow the first Replay link in a new tab: it is a real page, not just a href
    with ctx.expect_page() as newp:
        links.first.click()
    rp = newp.value
    W.attach(rp, "E replay")
    rp.wait_for_function("window.pbRsReplay && document.querySelector('.proto-screen')", timeout=20000)
    check(rp.url.endswith(want[0]) and rp.evaluate("window.pbRsReplay.duration()") > 0, "the Replay link opens the replay (%s)" % rp.url)
    rp.close()
    page.wait_for_timeout(200)
    outside = [x for x in W.external if x[0] == "E"]
    check(not outside, "the served prototype and its replay tab made no outside request (%s)" % outside[:2])
    ctx.close()


# ═════════════════════════════════════════════════════════════════════════════

PROBE_JS = """async () => {
  try {
    const s = await navigator.mediaDevices.getDisplayMedia({video: true, audio: false, preferCurrentTab: true});
    s.getTracks().forEach(t => t.stop());
    const m = await navigator.mediaDevices.getUserMedia({audio: true});
    m.getTracks().forEach(t => t.stop());
    return 'ok';
  } catch (e) { return e.name + ': ' + e.message; }
}"""


def probe_capture(br, base):
    """Ask a browser for a real screen + voice capture on the preview's own http://127.0.0.1 page
    (a data: URL is not a secure context, so it would fail for the wrong reason)."""
    ctx = br.new_context()
    try:
        pg = ctx.new_page()
        pg.goto(base + "/", wait_until="domcontentloaded")
        return pg.evaluate(PROBE_JS)
    finally:
        with contextlib.suppress(Exception):
            ctx.close()


def decide_capture(pw, base, S_):
    """Pick the browser once: the default (headless shell), then Chromium's new headless, then the
    canvas stub. Returns the open browser; S_['capture_mode'] is 'headless-shell' | 'chromium' | 'stub'.
    With PB_REQUIRE_REAL_CAPTURE=1 (CI) landing on the stub is a failed check, not a NOT VERIFIED note."""
    section("capture · which Chromium gives a real screen capture")
    errors = []
    for mode, launch in (("headless-shell", {}), ("chromium", {"channel": "chromium"})):
        try:
            br = pbbrowser.open_browser(pw, who=WHO, args=REAL_CAPTURE, **launch)
        except Exception as e:
            errors.append("%s: launch failed: %s" % (mode, str(e).splitlines()[0][:160] if str(e) else type(e).__name__))
            continue
        try:
            res = probe_capture(br, base)
        except Exception as e:
            res = "%s: %s" % (type(e).__name__, str(e).splitlines()[0][:160] if str(e) else "")
        if res == "ok":
            S_["capture_mode"] = mode
            check(True, "capture mode: %s (real getDisplayMedia + getUserMedia)" % mode)
            return br
        errors.append("%s: %s" % (mode, res))
        with contextlib.suppress(Exception):
            br.close()
    S_["capture_mode"] = "stub"
    detail = "; ".join(errors)
    if os.environ.get("PB_REQUIRE_REAL_CAPTURE") == "1":
        check(False, "capture mode: stub, but PB_REQUIRE_REAL_CAPTURE=1 demands a real screen capture (%s)" % detail)
    else:
        not_verified("capture mode: stub; real getDisplayMedia/getUserMedia is not available in this Chromium (%s); "
                     "the recording path ran on a synthetic canvas+oscillator MediaStream instead of a real screen capture" % detail)
    return pbbrowser.open_browser(pw, who=WHO, args=REAL_CAPTURE)


def main():
    W = Watch()
    p = Proj()
    reg_stop = [sys.executable, os.path.join(TOOLS, "serve.py"), "--stop", p.reg]
    br = None
    S_ = {}
    try:
        section("setup · four approved studies, one managed preview server")
        approve(p, U, "usability", "usability-plan.json", brief="usability-brief.json", mode="moderated")
        approve(p, T, "tree-test", "tree-test-plan.json")
        approve(p, C, "card-sort", "card-sort-plan.json", brief="brief-min.json")
        approve(p, F, "first-click", "first-click-plan.json", brief="brief-min.json")
        link = p.ok("link", U, "--observer", "--participant", "P01")
        base = link["url"].split("/research/")[0]
        check(base.startswith("http://127.0.0.1:") and link["observer"].endswith("/research/%s/observer?p=P01" % U),
              "link: the preview server answers (%s)" % base)

        with sync_playwright() as pw:
            br = decide_capture(pw, base, S_)
            for name, fn in (("A", lambda: scenario_a(p, br, base, W, S_)),
                             ("B", lambda: scenario_b(p, br, base, W, S_)),
                             ("C", lambda: scenario_c(p, br, W, S_)),
                             ("D", lambda: scenario_d(p, br, base, W, S_)),
                             ("F", lambda: scenario_f(p, base, S_)),
                             ("E", lambda: scenario_e(p, br, base, W, S_))):
                try:
                    fn()
                except Exception as e:  # a scenario that cannot finish is a failure, and the rest still run
                    traceback.print_exc()
                    check(False, "scenario %s did not finish: %s: %s" % (name, type(e).__name__, str(e).splitlines()[0][:300] if str(e) else ""))
        section("console")
        check(not W.errors, "no console error or page error on any page%s" % ("" if not W.errors else ": " + json.dumps(W.errors[:6])))
        print("    (filtered: %d missing-favicon 404s)" % W.favicon)
    finally:
        if br is not None:
            with contextlib.suppress(Exception):
                br.close()
        subprocess.run(reg_stop, capture_output=True, text=True, cwd=p.dir)
        shutil.rmtree(TMP, ignore_errors=True)

    if fails:
        print("\nFAIL: research_session_browser — %d of %d checks failed" % (len(fails), CHECKS[0]))
        for f_ in fails:
            print("  ✗ " + f_)
        sys.exit(1)
    print("\nPASS: research_session_browser (%d checks)%s" % (CHECKS[0], (" — NOT VERIFIED: " + "; ".join(NOT_VERIFIED)) if NOT_VERIFIED else ""))


if __name__ == "__main__":
    main()
