#!/usr/bin/env python3
"""
sandbox_demo_model.py — the Sandbox demo model (v2.5): named entry points, a permission matrix, people
within a role, data seeds, a subject that survives a tap, and a real back. Contract:
prototype-builder.md -> "Demo model — roles, permissions, people, entry points, data (v2.5)".

Drives fixtures/demo-model (synthetic, uses every feature) in a real Chromium through serve.py, and
fixtures/golden (declares none of it) to prove nothing changed for a project that does not opt in.

  1  the default entry opens welcome as the requester, person Requester A, seed empty
  2  ?entry=review opens requests as the reviewer on seed two-open; ?role= applies on top; unknown values warn
  3  Reset (the button and R) returns to the active entry with its role, person and seed; picking one clears
     the history and the subject
  4  pbCan is right per the matrix: admin bypass, an unnamed capability, an unknown level, no roles
  5  on the FIRST render after setProtoRole a body's pbCan output and data-can are already right
  6  data-can hides and disables, and gives back what it took, in a Compare frame too
  7  data-ctx shows the tapped subject; data-back goes back with the right one (or to its own screen with no
     history); data-nav-reset stops going back into `done`; a history a module edited does not throw
  8  changing role keeps or changes the person per the contract; the Person row lists only that role's people
  9  events fire before the re-render, and a seed change calls pbScenarioSwitch
 10  pbSandboxRow from a module that runs at load draws a row, keeps it through a re-render, and calls set()
 11  the Run section applies test.entry and test.persona
 12  UX Design -> Logic shows the Permissions table
 13  /design-system renders with zero console errors and the safe defaults
 14  fixtures/golden (no demo model): start and Reset as ever, no new Sandbox rows, no console errors

Dev/CI-only dependency (never shipped): pip install playwright && playwright install chromium

Usage:  python3 tests/sandbox_demo_model.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright/browser not available (a clean skip)
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from e2e_smoke import GOLDEN, Server, _offline, real_console_error  # noqa: E402

DEMO_DIR = os.path.join(ROOT, "fixtures", "demo-model")
DEMO = os.path.join(DEMO_DIR, "registry.json")

_failures = []


def check(cond, msg):
    print("  %s %s" % ("✓" if cond else "✗", msg))
    if not cond:
        _failures.append(msg)


def case(n, title):
    print("\ncase %s · %s" % (n, title))


class Tab:
    """One page on a served project, with what the console and the page said."""

    def __init__(self, browser, url):
        self.page = browser.new_page()
        _offline(self.page)
        self.errors, self.warnings = [], []
        self.page.on("console", self._console)
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_selector(".meta-tab", timeout=10000)
        self.page.wait_for_selector("#proto-frame", timeout=10000)

    def _console(self, m):
        if real_console_error(m):
            self.errors.append(m.text)
        elif m.type == "warning":
            self.warnings.append(m.text)

    def ev(self, js):
        return self.page.evaluate(js)

    def click(self, testid):
        self.page.click('#proto-frame [data-testid="%s"]' % testid)

    def screen(self):
        return self.ev("state.protoScreenId")

    def who(self):
        return self.ev("({role: pbRole(), person: (pbPersona() || {}).id || null, seed: pbSeed(), "
                       "entry: (pbEntry() || {}).id || null, screen: state.protoScreenId, ctx: pbCtx(), "
                       "history: state.protoHistory.slice()})")

    def text(self, testid):
        return self.ev("(document.querySelector('#proto-frame [data-testid=\"%s\"]') || {}).textContent || null" % testid)

    def close(self):
        self.page.close()


def variant(tmp, name, edit):
    """A copy of fixtures/demo-model in tmp/name, its registry edited by edit(reg). Returns the registry path."""
    dst = os.path.join(tmp, name)
    shutil.copytree(DEMO_DIR, dst)
    path = os.path.join(dst, "registry.json")
    reg = json.load(open(path, encoding="utf-8"))
    edit(reg)
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
    return path


ROWS_MODULE = """\
// A project module that runs at load, before the shell has any state: it asks for a Sandbox row.
var __rowLog = [];
var __tone = 'plain';
pbSandboxRow({
  id: 'tone', label: 'Tone',
  options: function () { return [{ value: 'plain', label: 'Plain' }, { value: 'warm', label: 'Warm' }]; },
  get: function () { return __tone; },
  set: function (v) { __tone = v; __rowLog.push(v); }
});
"""


def make_extended(tmp):
    """The fixture with two devices (so Compare is possible) and a runtime module that adds a Sandbox row."""
    def edit(reg):
        reg["meta"]["devices"] = ["laptop", "mobile"]
        reg["runtime"] = [{"id": "rows", "src": "runtime/rows.js", "why": "adds a Sandbox row at load"}]
    path = variant(tmp, "extended", edit)
    os.makedirs(os.path.join(os.path.dirname(path), "runtime"))
    open(os.path.join(os.path.dirname(path), "runtime", "rows.js"), "w", encoding="utf-8").write(ROWS_MODULE)
    return path


def make_noroles(tmp):
    """The fixture with meta.roles removed: pbCan has nothing to compare against."""
    def edit(reg):
        reg["meta"].pop("roles", None)
        reg["meta"].pop("defaultRole", None)
    return variant(tmp, "noroles", edit)


def run():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping sandbox_demo_model (dev/CI-only dependency).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)

    tmp = tempfile.mkdtemp(prefix="pb-demo-model-")
    try:
        ext_reg = make_extended(tmp)
        nor_reg = make_noroles(tmp)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                print("Could not launch Chromium (%s). Run: playwright install chromium" % e)
                sys.exit(2)

            # four projects served at once, so the cases run (and print) in the contract's order
            with Server(DEMO) as demo, Server(ext_reg) as ext, Server(nor_reg) as nor, Server(GOLDEN) as gold:
                case1(browser, demo.url)
                case2(browser, demo.url)
                case3(browser, demo.url)
                case4(browser, demo.url, nor.url)
                case5(browser, demo.url)
                case6(browser, ext.url)
                case7(browser, demo.url)
                case8(browser, demo.url)
                case9(browser, demo.url)
                case10(browser, ext.url)
                case11(browser, demo.url)
                case12(browser, demo.url)
                case13(browser, demo.url, ext.url)
                case14(browser, gold.url)
            browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if _failures:
        print("✗ %d demo-model assertion(s) failed." % len(_failures))
        sys.exit(1)
    print("✓ All demo-model assertions passed.")


# ── fixtures/demo-model ────────────────────────────────────────────────────────────────────────

def case1(browser, base):
    case(1, "the default entry")
    t = Tab(browser, base)
    w = t.who()
    check(w["entry"] == "first-run" and w["screen"] == "welcome", "opens the default entry, first-run, on welcome (%s)" % w)
    check(w["role"] == "requester", "as the requester")
    check(w["person"] == "requester-a" and t.ev("pbPersona().name") == "Requester A", "as person Requester A")
    check(w["seed"] == "empty", "on seed empty")
    check("Signed in as Requester A" in (t.text("who") or ""), "and the first frame already says who is signed in")
    check(t.ev("pbPersona().scope.region") == "north", "the person's scope is plain data on pbPersona()")
    check(t.ev("state.activeRole === pbRole()"), "state.activeRole stays the truth for role")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case2(browser, base):
    case(2, "?entry= wins, ?role= and ?persona= apply on top, unknown values warn")
    t = Tab(browser, base + "?entry=review")
    w = t.who()
    check(w["entry"] == "review" and w["screen"] == "requests", "?entry=review opens requests (%s)" % w)
    check(w["role"] == "reviewer" and w["person"] == "reviewer-a" and w["seed"] == "two-open",
          "as the reviewer, Reviewer A, on two-open")
    check(t.ev("!!document.querySelector('#proto-frame [data-testid=\"row-R-1\"]') && "
               "!!document.querySelector('#proto-frame [data-testid=\"row-R-2\"]')"), "and the seed is on the first frame: R-1 and R-2")
    t.close()

    t = Tab(browser, base + "?entry=review&role=requester")
    w = t.who()
    check(w["entry"] == "review" and w["screen"] == "requests" and w["role"] == "requester",
          "?entry=review&role=requester: the entry's screen, the role asked for (%s)" % w)
    check(w["person"] == "requester-a", "and the person follows the role, not the entry's reviewer")
    t.close()

    t = Tab(browser, base + "?entry=review&persona=requester-b")
    w = t.who()
    check(w["person"] == "requester-b" and w["role"] == "requester",
          "?persona= alone: that person, and the role follows them (a reading of the contract) (%s)" % w)
    t.close()

    t = Tab(browser, base + "?entry=nope&role=nope&persona=nope")
    w = t.who()
    check(w["entry"] == "first-run" and w["role"] == "requester" and w["person"] == "requester-a",
          "unknown values are ignored: the default entry applies (%s)" % w)
    check(len(t.warnings) >= 3 and not t.errors,
          "…each with a console warning, never an error (warnings=%d, errors=%s)" % (len(t.warnings), t.errors))
    t.close()

def case3(browser, base):
    case(3, "Reset returns to the active entry; picking an entry clears history and subject")
    t = Tab(browser, base + "?entry=review")
    t.click("row-R-1")
    check(t.screen() == "detail" and t.who()["ctx"] == "R-1", "on detail, subject R-1")
    t.ev("setProtoRole('admin'); pbSetSeed('empty')")
    w = t.who()
    check(w["role"] == "admin" and w["seed"] == "empty" and w["person"] is None, "wandered off: admin, no one, seed empty")
    t.page.keyboard.press("r")
    w = t.who()
    check(w["screen"] == "requests" and w["role"] == "reviewer" and w["person"] == "reviewer-a" and w["seed"] == "two-open",
          "R returns to the active entry with its role, person and seed (%s)" % w)
    check(w["history"] == [] and w["ctx"] is None and w["entry"] == "review", "…with no history and no subject")
    t.click("row-R-2")
    t.ev("setProtoRole('requester')")
    t.page.keyboard.press("s")
    t.page.wait_for_selector("#pb-insp")
    t.page.click('#pb-insp [data-sbx-f="reset"]')
    w = t.who()
    check(w["screen"] == "requests" and w["role"] == "reviewer" and w["person"] == "reviewer-a" and w["seed"] == "two-open"
          and w["history"] == [] and w["ctx"] is None, "the Reset session button does the same (%s)" % w)
    t.click("row-R-1")
    check(t.who()["history"] == ["requests"], "history is a plain array of screen ids")
    t.page.select_option("#sbx-entry", "first-run")
    w = t.who()
    check(w["entry"] == "first-run" and w["screen"] == "welcome" and w["role"] == "requester" and w["person"] == "requester-a"
          and w["seed"] == "empty", "picking an entry in the Sandbox applies screen, role, person and seed (%s)" % w)
    check(w["history"] == [] and w["ctx"] is None, "…and clears the history and the subject")
    t.page.keyboard.press("r")
    check(t.who()["entry"] == "first-run" and t.screen() == "welcome", "Reset now returns to the entry just picked")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case4(browser, base, noroles_base):
    case(4, "pbCan follows the matrix")
    t = Tab(browser, base)
    rows = {
        "requester": [("request", None, True), ("request", "request", True), ("request", "approve", False),
                      ("report", None, False), ("report", "none", True), ("missing", None, False),
                      ("missing", "none", True), ("request", "bogus", False)],
        "reviewer": [("request", "approve", True), ("request", "apply", False), ("report", None, True),
                     ("report", "request", False), ("request", "bogus", False), ("missing", None, False)],
        "admin": [("request", "apply", True), ("report", None, True), ("missing", None, True), ("report", "apply", True)],
    }
    for role, tests in rows.items():
        t.ev("setProtoRole(%s)" % json.dumps(role))
        got = [t.ev("pbCan(%s)" % ", ".join(json.dumps(x) for x in (c, lv) if x is not None)) for c, lv, _ in tests]
        want = [w for _, _, w in tests]
        check(got == want, "%s: %s" % (role, ", ".join("%s%s=%s" % (c, ":" + lv if lv else "", g) for (c, lv, _), g in zip(tests, got))))
    t.close()
    t = Tab(browser, noroles_base)
    check(t.ev("pbCan('request', 'apply') === true && pbCan('anything') === true"),
          "with no meta.roles there is nothing to compare against, so pbCan is true")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()


def case5(browser, base):
    case(5,"the FIRST render after setProtoRole is already right")
    t = Tab(browser, base + "?entry=review")
    t.click("row-R-1")
    check(t.text("can-approve") == "can approve" and not t.ev("document.querySelector('[data-testid=approve]').disabled"),
          "as the reviewer: the body says can approve and Approve is enabled")
    out = t.ev("""(() => {
      const orig = window.renderPrototype; let n = 0;
      window.renderPrototype = function () { n++; return orig.apply(this, arguments); };
      setProtoRole('requester');
      window.renderPrototype = orig;
      const b = document.querySelector('[data-testid=approve]');
      return { n: n, body: document.querySelector('[data-testid=can-approve]').textContent,
               disabled: b.disabled, aria: b.getAttribute('aria-disabled'), title: b.getAttribute('title') };
    })()""")
    check(out["n"] == 1, "exactly one render ran (%s)" % out["n"])
    check(out["body"] == "cannot approve", "…and in it pbCan('request', 'approve') was already false (%r)" % out["body"])
    check(out["disabled"] and out["aria"] == "true" and "approve" in (out["title"] or ""),
          "…and data-can was already applied: disabled, aria-disabled, a title naming what is missing (%r)" % out["title"])
    t.ev("setProtoRole('reviewer')")
    check(t.text("can-approve") == "can approve" and not t.ev("document.querySelector('[data-testid=approve]').disabled"),
          "back to the reviewer: enabled again on the first render")
    t.close()

def case7(browser, base):
    case(7, "data-ctx, data-back, data-nav-reset")
    t = Tab(browser, base + "?entry=review")
    t.click("row-R-2")
    check(t.screen() == "detail" and t.text("subject") == "R-2" and t.ev("pbCtx()") == "R-2", "tapping R-2 opens detail showing R-2")
    t.click("back")
    w = t.who()
    check(w["screen"] == "requests" and w["ctx"] is None and w["history"] == [], "data-back goes back (%s)" % w)
    t.click("row-R-1")
    check(t.text("subject") == "R-1", "tapping R-1 afterwards shows R-1, not the earlier R-2")
    t.click("approve")
    check(t.screen() == "done" and t.ev("pbCtx()") is None, "a data-nav without data-ctx clears the subject")
    check(t.who()["history"] == ["requests", "detail"], "history so far: requests, detail")
    t.ev("pbBack()")
    check(t.screen() == "detail" and t.text("subject") == "R-1" and t.ev("pbCtx()") == "R-1",
          "pbBack() returns to detail with the subject of THAT screen, R-1")
    t.click("approve")
    t.ev("""(() => { const b = document.createElement('button'); b.id = 'x-back'; b.setAttribute('data-back', 'welcome');
                     document.querySelector('#proto-frame [data-testid=done]').appendChild(b); })()""")
    t.page.click("#x-back")
    check(t.screen() == "detail" and t.text("subject") == "R-1", "a data-back control goes back with the right subject too")
    t.click("approve")
    t.click("to-requests")
    w = t.who()
    check(w["screen"] == "requests" and w["history"] == [] and w["ctx"] is None,
          "leaving a data-nav-reset screen empties the history (%s)" % w)
    t.click("back")
    check(t.screen() == "welcome", "so Back from requests falls through to its own data-back='welcome', not into done")
    t.close()

    t = Tab(browser, base + "?entry=review")
    t.click("back")
    check(t.screen() == "welcome" and t.who()["history"] == [], "data-back='welcome' with no history goes to welcome")
    t.ev("pbBack()")
    check(t.screen() == "welcome", "pbBack() with no history is a no-op")
    # a real module edits the history itself and calls back in with fromBack
    t.click("open-requests")
    t.click("row-R-1")
    t.ev("state.protoHistory.pop(); setProtoScreen('requests', true)")
    w = t.who()
    check(w["screen"] == "requests" and w["ctx"] is None, "a module that pops the history and calls setProtoScreen(id, true) works (%s)" % w)
    t.click("row-R-1")
    t.ev("state.protoHistory = ['welcome', 'requests', 'welcome']; state.protoCtxStack = ['only-one']")
    t.ev("setProtoScreen('requests')")
    t.ev("protoBack(); protoBack(); protoBack(); protoBack(); protoBack()")
    check(t.ev("Array.isArray(state.protoHistory) && state.protoHistory.every(x => typeof x === 'string') "
               "&& state.protoCtxStack.length <= state.protoHistory.length + 1"),
          "a ctx stack that drifted from the history is truncated, never thrown on")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case8(browser, base):
    case(8, "role, person and the Person row")
    t = Tab(browser, base)
    t.ev("pbSetPersona('requester-b')")
    check(t.who()["person"] == "requester-b", "pick Requester B")
    t.ev("setProtoRole('requester')")
    check(t.who()["person"] == "requester-b", "a role change to the same role keeps the person")
    t.ev("setProtoRole('reviewer')")
    check(t.who()["person"] == "reviewer-a", "a role the person does not belong to: that role's first person")
    t.ev("setProtoRole('requester')")
    check(t.who()["person"] == "requester-a", "…and back: that role's first person again")
    t.ev("setProtoRole('admin')")
    check(t.who()["person"] is None and t.ev("pbPersona()") is None, "a role with no people: none")
    t.ev("setProtoRole('requester')")
    t.page.keyboard.press("s")
    t.page.wait_for_selector("#pb-insp")
    opts = t.ev("[...document.querySelectorAll('#sbx-person option')].map(o => o.value)")
    check(opts == ["requester-a", "requester-b"], "the Person row lists only the requester's people (%s)" % opts)
    t.page.select_option("#sbx-person", "requester-b")
    check(t.who()["person"] == "requester-b" and t.ev("document.getElementById('sbx-person').value") == "requester-b",
          "picking a person in the Sandbox applies it, and the row follows")
    t.page.select_option("#sbx-role", "reviewer")
    opts = t.ev("[...document.querySelectorAll('#sbx-person option')].map(o => o.value)")
    check(opts == ["reviewer-a"], "after choosing the reviewer the row lists only Reviewer A (%s)" % opts)
    t.page.select_option("#sbx-role", "admin")
    check(t.ev("!document.getElementById('sbx-person')"), "an admin has no people, so the row is not drawn")
    t.page.select_option("#sbx-role", "requester")
    labels = t.ev("[...document.querySelectorAll('#pb-insp .sbx-row-lbl')].map(e => e.textContent.trim())")
    want = ["Start from", "Device", "Chrome", "Role", "Person", "Data", "This role can"]
    got = [x for x in labels if x in want]
    check(got == want, "Conditions rows, in the contract's order: %s" % got)
    can = t.ev("[...document.querySelectorAll('#pb-insp .sbx-can li')].map(e => e.textContent.replace(/\\s+/g, ' ').trim())")
    check(can == ["request request"], "'This role can' lists the requester's capabilities above the lowest level (%s)" % can)
    t.page.select_option("#sbx-role", "admin")
    can = t.ev("[...document.querySelectorAll('#pb-insp .sbx-can li')].map(e => e.textContent.replace(/\\s+/g, ' ').trim())")
    check(len(can) == 1 and "admin" in can[0], "…and says the admin bypasses the matrix (%s)" % can)
    t.page.select_option("#sbx-seed", "two-open")
    check(t.who()["seed"] == "two-open", "the Data row sets the seed")
    t.close()

def case9(browser, base):
    case(9, "events fire before the re-render")
    t = Tab(browser, base)
    t.ev("""(() => {
      window.__ev = []; window.__sw = [];
      window.pbScenarioSwitch = function (s) { window.__sw.push(s); };
      ['rolechange', 'personachange', 'seedchange', 'entrychange', 'reset'].forEach(n =>
        window.addEventListener('pb:' + n, e => window.__ev.push({ n: n, d: e.detail, role: pbRole(), seed: pbSeed(),
          person: (pbPersona() || {}).id || null, entry: (pbEntry() || {}).id || null,
          shown: (document.querySelector('#proto-frame [data-testid]') || {}).getAttribute('data-testid'),
          who: (document.querySelector('#proto-frame [data-testid=who]') || {}).textContent || null })));
    })()""")
    t.ev("setProtoRole('reviewer')")
    evs = t.ev("window.__ev")
    byn = {e["n"]: e for e in evs}
    check(set(byn) == {"rolechange", "personachange"}, "a role change fires pb:rolechange and pb:personachange (%s)" % sorted(byn))
    e = byn.get("rolechange", {})
    check(e.get("d") == {"role": "reviewer"} and e.get("role") == "reviewer" and e.get("shown") == "welcome"
          and "Requester A" in (e.get("who") or ""),
          "pb:rolechange {role}: pbRole() is already 'reviewer' while the frame still shows the old welcome (%s)" % e)
    e = byn.get("personachange", {})
    check(e.get("person") == "reviewer-a" and (e.get("d") or {}).get("persona", {}).get("id") == "reviewer-a",
          "pb:personachange {persona}: the new person, before the repaint")
    check("Reviewer A" in (t.text("who") or ""), "…and after the event the frame repainted with them")
    t.ev("window.__ev.length = 0; pbSetSeed('two-open')")
    evs = t.ev("window.__ev")
    check([e["n"] for e in evs] == ["seedchange"] and evs[0]["seed"] == "two-open" and evs[0]["d"] == {"seed": "two-open"},
          "a seed change fires pb:seedchange {seed} with pbSeed() already new (%s)" % evs)
    check(t.ev("window.__sw") == ["two-open"], "…and calls window.pbScenarioSwitch(seed) when the project defines it")
    t.ev("window.__ev.length = 0; pbApplyEntry('review')")
    names = [e["n"] for e in t.ev("window.__ev")]
    e = [e for e in t.ev("window.__ev") if e["n"] == "entrychange"]
    check("entrychange" in names and e and e[0]["entry"] == "review" and (e[0]["d"]["entry"] or {}).get("id") == "review"
          and e[0]["shown"] == "welcome", "an entry change fires pb:entrychange {entry} before the repaint (%s)" % names)
    t.ev("window.__ev.length = 0; setProtoScreen('detail'); pbResetSandbox()")
    evs = t.ev("window.__ev")
    r = [e for e in evs if e["n"] == "reset"]
    check(r and r[0]["shown"] == "detail" and (r[0]["d"]["entry"] or {}).get("id") == "review" and r[0]["entry"] == "review",
          "Reset fires pb:reset {entry} while the frame still shows the screen it left (%s)" % [e["n"] for e in evs])
    check(t.screen() == "requests", "…and then lands on the entry's screen")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case11(browser, base):
    case(11, "the Run section applies test.entry and test.persona")
    t = Tab(browser, base)
    t.page.keyboard.press("s")
    t.page.wait_for_selector("#pb-insp")
    n = t.ev("pbTestScenarios().length")
    check(n == 2, "the Run section lists the fixture's two scenarios (%s)" % n)
    t.ev("pbRunScenarios([0])")
    w = t.who()
    st = t.ev("Object.values(state.sbxRun).map(r => ({status: r.status, kinds: r.lines.map(l => l.kind + ':' + l.status)}))")
    check(st and st[0]["kinds"][0] == "entry:pass" and st[0]["status"] == "pass", "scenario 1: 'Start from review' ticks pass and the run passes (%s)" % st)
    check(w["entry"] == "review" and w["role"] == "reviewer" and w["screen"] == "done",
          "…it started from the review entry, as the reviewer, and finished on done (%s)" % w)
    t.ev("pbRunScenarios([1])")
    w = t.who()
    st = t.ev("Object.values(state.sbxRun).map(r => r.lines.map(l => l.kind + ':' + l.status))")
    kinds = st[-1] if st else []
    check(kinds[:3] == ["entry:pass", "persona:pass", "start:pass"], "scenario 2: entry, persona and start tick pass, in that order (%s)" % kinds)
    check(w["entry"] == "first-run" and w["person"] == "requester-b" and w["screen"] == "detail" and w["role"] == "requester",
          "…the page is now the first-run entry, as Requester B, on detail (%s)" % w)
    check(t.ev("document.querySelector('[data-testid=approve]').disabled"), "…where Approve is disabled for them")
    check(t.ev("pbRunPlan({entry: 'review', persona: 'reviewer-a', start: 'detail'}).map(l => l.kind).join()") == "entry,persona,start",
          "the plan puts entry and persona before start")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case12(browser, base):
    case(12, "UX Design -> Logic shows the Permissions table")
    t = Tab(browser, base)
    t.ev("setMetaView('flow'); pbSetUxView('logic');")
    t.page.wait_for_selector(".pb-perm", timeout=5000)
    tbl = t.ev("""(() => { const q = s => document.querySelector(s);
      const rows = [...document.querySelectorAll('.pb-perm-t tbody tr')].map(r => [...r.children].map(c => c.textContent.trim()));
      return { head: [...document.querySelectorAll('.pb-perm-t thead th')].map(c => c.textContent.trim()), rows: rows,
               adminTag: !!q('.pb-perm-t tr.is-admin .pb-perm-tag'), colspan: (q('.pb-perm-t tr.is-admin td') || {}).colSpan,
               note: (q('.pb-perm') || {}).textContent, inProduct: !!q('.pb-perm').closest('.pb-product') }; })()""")
    check(tbl["head"] == ["Role", "request", "report"], "roles down, capabilities across (%s)" % tbl["head"])
    rows = {r[0].replace("admin", "").strip(): r[1:] for r in tbl["rows"]}
    check(rows.get("Requester") == ["request", "none"] and rows.get("Reviewer") == ["approve", "view"],
          "the level is in each cell (%s)" % tbl["rows"])
    check(tbl["adminTag"] and tbl["colspan"] == 2 and "bypasses" in rows.get("Admin", [""])[0],
          "an isAdmin role is marked as bypassing the matrix")
    check("not access control" in (tbl["note"] or ""), "…with a one-line note: demo behaviour, not access control")
    check(not tbl["inProduct"], "it is tool chrome: never inside .pb-product")
    check(t.ev("!!document.querySelector('.pb-perm').closest('.meta-section')"), "it sits in the Logic segment")
    check(t.ev("(() => { const l = document.querySelector('.lg-views'), p = document.querySelector('.pb-perm'); "
               "return !!(l.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING); })()"),
          "…after the Rules/Impact switch, ahead of the rules")
    check(t.ev("document.querySelector('.lg-view.active').textContent.indexOf('Rules') !== -1"),
          "a project with a matrix lands on Rules even with no rules written yet")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()

def case13(browser, base, ext_base):
    case(13, "the design-system site")
    t = Tab(browser, base)
    t.page.goto(base + "design-system", wait_until="domcontentloaded")
    t.page.wait_for_selector(".ds-shell .ds-nav", state="attached", timeout=10000)
    t.page.wait_for_timeout(400)
    check(t.ev("!!document.querySelector('.ds-shell')"), "the design-system shell is up")
    check(not t.errors, "/design-system renders with zero console errors (%s)" % t.errors)
    d = t.ev("({role: pbRole(), person: pbPersona(), seed: pbSeed(), entry: pbEntry(), ctx: pbCtx(), can: pbCan('x', 'apply'), "
             "back: pbBack(), def: [pbRole, pbCan, pbSandboxRow].every(f => f.__pbDefault === true)})")
    check(d == {"role": None, "person": None, "seed": None, "entry": None, "ctx": None, "can": True, "back": None, "def": True},
          "the safe defaults answer 'nothing declared' there (%s)" % d)
    t.close()
    # a module that calls pbSandboxRow while it loads must not break the site that has no Sandbox
    t = Tab(browser, ext_base)
    t.page.goto(ext_base + "design-system", wait_until="domcontentloaded")
    t.page.wait_for_selector(".ds-shell .ds-nav", state="attached", timeout=10000)
    t.page.wait_for_timeout(300)
    check(not t.errors, "a load-time pbSandboxRow in a project module is harmless on /design-system (%s)" % t.errors)
    t.close()


# ── a project with two devices and a module that runs at load ───────────────────────────────────

def case6(browser, base):
    case(6, "data-can hides and disables, restores, and reaches a Compare frame")
    t = Tab(browser, base + "?entry=review")
    t.ev("""window.__inject = function () {
      document.querySelectorAll('.proto-screen').forEach(function (f, i) {
        if (f.querySelector('.x-hide')) return;
        f.insertAdjacentHTML('beforeend',
          '<button class="x-hide" data-can="report">Hide me</button>' +
          '<button class="x-dis" data-can="request:approve" data-can-mode="disable" title="mine">Disable me</button>' +
          '<button class="x-own" data-can="request:approve" data-can-mode="disable" disabled>Already disabled</button>');
      });
    }""")
    t.ev("setProtoCompare('mobile')")
    t.page.wait_for_selector("#proto-frame-b", timeout=5000)
    t.page.wait_for_timeout(300)
    check(t.ev("document.querySelectorAll('.proto-screen').length") == 2, "Compare is on: two frames")
    t.ev("window.__inject()")
    st = t.ev("""(() => {
      const f = id => { const r = document.getElementById(id);
        return { hid: r.querySelector('.x-hide').style.display, dis: r.querySelector('.x-dis').disabled,
          aria: r.querySelector('.x-dis').getAttribute('aria-disabled'), title: r.querySelector('.x-dis').getAttribute('title'),
          own: r.querySelector('.x-own').disabled }; };
      state.activeRole = 'reviewer'; pbApplyRoleGating();
      const rev = { a: f('proto-frame'), b: f('proto-frame-b') };
      state.activeRole = 'requester'; pbApplyRoleGating();
      const req = { a: f('proto-frame'), b: f('proto-frame-b') };
      return { rev: rev, req: req }; })()""")
    for fr in ("a", "b"):
        r, q = st["rev"][fr], st["req"][fr]
        check(r["hid"] == "" and not r["dis"] and r["title"] == "mine" and r["own"],
              "frame %s as the reviewer: shown, enabled, the author's title kept, their own disabled kept" % fr.upper())
        check(q["hid"] == "none", "frame %s as the requester: data-can hides what the role cannot do" % fr.upper())
        check(q["dis"] and q["aria"] == "true" and q["title"] == "Needs approve on request",
              "frame %s: data-can-mode=disable sets disabled, aria-disabled and a title naming what is missing (%r)" % (fr.upper(), q["title"]))
    back = t.ev("""(() => {
      state.activeRole = 'reviewer'; pbApplyRoleGating();
      const r = document.getElementById('proto-frame'), x = r.querySelector('.x-dis'), o = r.querySelector('.x-own');
      return { hid: r.querySelector('.x-hide').style.display, dis: x.disabled, aria: x.getAttribute('aria-disabled'),
               title: x.getAttribute('title'), own: o.disabled, ownTitle: o.getAttribute('title'), mark: x.getAttribute('data-pb-can') }; })()""")
    check(back == {"hid": "", "dis": False, "aria": None, "title": "mine", "own": True, "ownTitle": None, "mark": None},
          "allowed again: everything given back, nothing of the author's lost (%s)" % back)
    # a real render, in Compare: both frames gated on the same render
    t.ev("setProtoScreen('detail')")
    t.page.wait_for_timeout(250)
    t.ev("setProtoRole('requester')")
    t.page.wait_for_timeout(250)
    both = t.ev("[...document.querySelectorAll('.proto-screen')].map(f => f.querySelector('[data-testid=approve]').disabled)")
    check(both == [True, True], "after a real render in Compare, Approve is disabled in both frames (%s)" % both)
    t.ev("setProtoRole('reviewer')")
    t.page.wait_for_timeout(250)
    both = t.ev("[...document.querySelectorAll('.proto-screen')].map(f => f.querySelector('[data-testid=approve]').disabled)")
    check(both == [False, False], "…and enabled in both for the reviewer (%s)" % both)
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()


def case10(browser, base):
    case(10, "pbSandboxRow from a module that runs at load")
    t = Tab(browser, base)
    check(t.ev("window.pbSandboxRows.length") >= 1, "the module's call, made before the shell had state, was queued")
    t.page.keyboard.press("s")
    t.page.wait_for_selector("#pb-insp")
    opts = t.ev("[...document.querySelectorAll('#sbx-x-0 option')].map(o => o.value + ':' + o.textContent.trim())")
    check(opts == ["plain:Plain", "warm:Warm"], "a select row is drawn with the options the module gave (%s)" % opts)
    check(t.ev("document.querySelector('label[for=sbx-x-0]').textContent.trim()") == "Tone", "labelled Tone")
    check(t.ev("document.getElementById('sbx-x-0').value") == "plain", "its current value comes from get()")
    labels = t.ev("[...document.querySelectorAll('#pb-insp .sbx-row-lbl')].map(e => e.textContent.trim())")
    i, j = labels.index("Tone"), labels.index("Data")
    check(j < i < labels.index("This role can"), "it sits after Data and before 'This role can' (%s)" % labels)
    t.page.select_option("#sbx-x-0", "warm")
    check(t.ev("__rowLog") == ["warm"] and t.ev("__tone") == "warm", "choosing a value calls the module's set()")
    t.ev("pbSandboxRerender()")
    check(t.ev("document.getElementById('sbx-x-0').value") == "warm", "the row survives a Sandbox re-render, with its value")
    t.ev("renderPrototype(); pbSandboxRerender()")
    t.ev("setProtoRole('reviewer')")
    check(t.ev("!!document.getElementById('sbx-x-0')"), "…and a role change")
    t.ev("pbSandboxRow({ id: 'late', label: 'Late', options: ['a', 'b'], get: () => 'b', set: () => {} })")
    check(t.ev("document.getElementById('sbx-x-1').value") == "b", "a row added after load appears at once")
    t.ev("pbSandboxRow({ id: 'tone', label: 'Tone 2', options: ['x'], get: () => 'x', set: () => {} })")
    check(t.ev("document.querySelectorAll('#pb-insp [id^=sbx-x-]').length") == 2
          and t.ev("document.querySelector('label[for=sbx-x-0]').textContent.trim()") == "Tone 2",
          "calling it again with the same id replaces the row rather than adding one")
    check(not t.errors, "no console errors (%s)" % t.errors)
    t.close()


# ── fixtures/golden: nothing declared, nothing changes ─────────────────────────────────────────

def case14(browser, base):
    case(14,"fixtures/golden declares no demo model: start and Reset are as ever")
    t = Tab(browser, base)
    w = t.ev("({screen: state.protoScreenId, role: state.activeRole, hist: state.protoHistory.length, "
             "p: pbPersona(), s: pbSeed(), e: pbEntry(), c: pbCtx(), can: pbCan('anything', 'apply'), "
             "defs: ['pbRole','pbCan','pbSeed'].every(k => !window[k].__pbDefault)})")
    check(w["screen"] == "login" and w["role"] == "member" and w["hist"] == 0,
          "starts on screens[0] as meta.defaultRole (%s)" % w)
    check(w["p"] is None and w["s"] is None and w["e"] is None and w["c"] is None and w["can"] is True,
          "pbPersona, pbSeed, pbEntry and pbCtx are null and pbCan is true")
    check(w["defs"], "the shell installed the real functions over the defaults")
    t.page.keyboard.press("s")
    t.page.wait_for_selector("#pb-insp")
    drawn = t.ev("[...document.querySelectorAll('#pb-insp [data-sbx-f]')].map(e => e.getAttribute('data-sbx-f'))")
    extra = [x for x in drawn if x in ("entry", "person", "seed") or x.startswith("x-")]
    check(not extra and not t.ev("!!document.querySelector('#pb-insp .sbx-row--can, #pb-insp .sbx-can')"),
          "the Sandbox draws no new row (%s)" % drawn)
    check(t.ev("[...document.querySelectorAll('#pb-insp .sbx-row-lbl')].map(e => e.textContent.trim()).filter(l => "
               "['Start from','Person','Data','This role can'].includes(l)).length") == 0, "…not Start from, Person, Data or This role can")
    t.page.keyboard.press("Escape")
    t.ev("setProtoRole('admin'); setProtoScreen('dashboard')")
    check(t.who()["history"] == ["login"], "history is the plain array it always was")
    t.page.keyboard.press("r")
    w = t.who()
    check(w["screen"] == "login" and w["role"] == "member" and w["history"] == [],
          "R resets to screens[0] and the default role (%s)" % w)
    t.ev("setProtoRole('guest'); setProtoScreen('dashboard')")
    t.page.keyboard.press("s")
    t.page.click('#pb-insp [data-sbx-f="reset"]')
    w = t.who()
    check(w["screen"] == "login" and w["role"] == "member" and w["history"] == [], "…and so does the Reset session button")
    t.ev("setMetaView('flow'); pbSetUxView('logic');")
    t.page.wait_for_timeout(300)
    check(t.ev("document.querySelectorAll('.pb-perm').length") == 0, "no Permissions table when none is declared")
    t.ev("setMetaView('prototype')")
    check(not t.errors and not t.warnings, "no console errors or warnings (%s %s)" % (t.errors, t.warnings))
    t.close()

    t = Tab(browser, base + "?role=admin&entry=zzz")
    w = t.who()
    check(w["role"] == "admin" and w["screen"] == "login", "?role= works with no demo model: the role asked for (%s)" % w)
    check(any("entry" in x for x in t.warnings) and not t.errors, "…and an unknown ?entry= warns, never errors")
    t.close()


if __name__ == "__main__":
    run()
