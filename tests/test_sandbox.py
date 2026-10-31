#!/usr/bin/env python3
"""
test_sandbox.py — the sandbox / scenario-runner integration test (refit S7).

Exercises the roles + scenario-`test{}` contract end to end against the golden fixture,
booting through pb/tools/serve.py (the same Server pattern as e2e_smoke.py) and shelling
out to pb/tools/test_run.py the way /pb:test does. It asserts:

  1. test_run.py --functional on the golden PASSES every runnable scenario and writes each
     scenario's lastResult { status, detail, ranAt }.
  2. flipping one expect turns that scenario RED — --functional reports fail (non-zero) and
     records lastResult.status == "fail".
  3. a scenario WITHOUT a test{} block still renders the manual "☐" glyph (and a runnable but
     un-run scenario renders "○"), on the UX Design tab.
  4. test_run.py --roles flags a deliberately-leaked role-gated element (the admin control is
     forced visible for a member) — non-zero.
  5. test_run.py --server flags a deliberately-broken data-nav target (a dangling screen id) —
     non-zero.
  6. lint_registry.py --strict stays exit 0 on the golden with all the additive keys present
     (meta.roles, screens[].roles, data-roles, scenario test{}).
  7. the shell's role seams work: the switcher + Reset render, and a data-roles element is
     hidden for a non-permitted role and shown for an admin (isAdmin bypass).

Dev/CI-only dependency (NS4 — never shipped, never pip-installed by the plugin):
  pip install playwright && playwright install chromium

Usage:  python3 tests/test_sandbox.py
Exit:   0 = all passed · 1 = a failure · 2 = Playwright / a Wave-2 tool not available
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
SERVE = os.path.join(TOOLS, "serve.py")
TEST_RUN = os.path.join(TOOLS, "test_run.py")
CHECK = os.path.join(TOOLS, "lint_registry.py")
GOLDEN = os.path.join(ROOT, "fixtures", "golden", "registry.json")

_failures = []


def check(cond, msg):
    mark = "✓" if cond else "✗"
    print(f"  {mark} {msg}")
    if not cond:
        _failures.append(msg)


class Server:
    """Boot serve.py on a registry; parse the chosen URL from its stdout (as e2e_smoke.py)."""

    def __init__(self, registry):
        self.registry = registry
        self.proc = None
        self.url = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, SERVE, self.registry, "--no-open", "--host", "127.0.0.1"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        deadline = time.time() + 15
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                break
            m = re.search(r"(http://127\.0\.0\.1:\d+/)", line)
            if m:
                self.url = m.group(1)
                break
        if not self.url:
            raise RuntimeError("serve.py did not report a preview URL")
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def copy_golden(dst_dir):
    """Copy the golden project (registry.json + render/ bodies) into dst_dir so a run can write
    lastResult / a mutation can sabotage a body WITHOUT touching the committed golden. Returns the
    copied registry path."""
    src_dir = os.path.dirname(GOLDEN)
    render_src = os.path.join(src_dir, "render")
    if os.path.isdir(render_src):
        shutil.copytree(render_src, os.path.join(dst_dir, "render"))
    reg = json.load(open(GOLDEN, encoding="utf-8"))
    path = os.path.join(dst_dir, "registry.json")
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
    return path


def run_tool(tool_path, *args):
    """Run a pb tool as a subprocess, capturing output. Returns the CompletedProcess."""
    return subprocess.run([sys.executable, tool_path, *args],
                          capture_output=True, text=True)


def iter_test_scenarios(reg):
    for st in (reg.get("flow") or {}).get("stories", []) or []:
        for sc in st.get("scenarios", []) or []:
            if isinstance(sc, dict) and sc.get("test"):
                yield sc


def load(path):
    return json.load(open(path, encoding="utf-8"))


def dump(reg, path):
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)


def _offline(page):
    """Block every request that is not the local preview server.

    The shell pulls Mermaid from a CDN with a blocking <script> in <head>, so DOMContentLoaded
    waits on the network. Run four browser tests in one sweep and several Chromium instances
    hit that CDN at once; one eventually loses and page.goto times out at 30s — a red suite
    caused by the weather, not by pb. Nothing in these tests asserts on a rendered diagram
    (test_sandbox already filters mermaid console noise), so the honest fix is to stop
    depending on the network at all.
    """
    CT = {"script": "application/javascript", "stylesheet": "text/css",
          "font": "font/woff2", "image": "image/png"}

    def _handle(route):
        url = route.request.url
        if "127.0.0.1" in url or "localhost" in url:
            return route.continue_()
        # FULFIL empty, never abort. An aborted request logs "net::ERR_FAILED" to the console,
        # and these tests assert zero console errors — swapping a rare network flake for a
        # guaranteed failure is not a fix. An empty 200 loads cleanly and defines nothing.
        return route.fulfill(status=200, body="",
                             content_type=CT.get(route.request.resource_type, "text/plain"))

    page.route("**/*", _handle)


class _FakePage:
    """Just enough of a Playwright page for test_run._run_scenario: `evaluate` answers the shell's seams,
    and once `navigating` is set it raises what Chromium raises when the page moves on mid-call."""
    def __init__(self, navigating=False):
        self.navigating, self.calls = navigating, 0

    def evaluate(self, expr, arg=None):
        self.calls += 1
        if self.navigating:
            raise Exception("Page.evaluate: Execution context was destroyed, most likely because of a navigation")
        if isinstance(expr, str) and "typeof setProtoRole" in expr:
            return "function"
        if isinstance(arg, dict) and "do" in arg:
            return {"ok": True}
        if isinstance(expr, str) and "protoScreenId" in expr:
            return "login"
        return None

    def wait_for_load_state(self, *a, **k):
        pass

    def wait_for_timeout(self, ms):
        pass


def navigation_race():
    """test_run survives a page that navigates under it: the scenario is `blocked` with the reason, never a
    traceback, and the run goes on to the next scenario."""
    sys.path.insert(0, TOOLS)
    import importlib
    tr = importlib.import_module("test_run")
    print("test_run._eval / _run_scenario against a page that navigates (unit):")
    flaky = _FakePage()
    n = {"left": 2}
    real = flaky.evaluate

    def flap(expr, arg=None):
        if n["left"] > 0:
            n["left"] -= 1
            raise Exception("Page.evaluate: Execution context was destroyed, most likely because of a navigation")
        return real(expr, arg)
    flaky.evaluate = flap
    check(tr._eval(flaky, "() => typeof setProtoRole") == "function", "two navigation races are waited out and retried")
    gone = _FakePage(navigating=True)
    try:
        tr._eval(gone, "() => 1", retries=2)
        check(False, "an exhausted retry raises _Blocked")
    except tr._Blocked as e:
        check(gone.calls == 3 and "navigat" in str(e), f"retries are bounded (3 calls) and the reason is kept ({e})")
    other = _FakePage()
    other.evaluate = lambda *a, **k: (_ for _ in ()).throw(ValueError("not a race"))
    try:
        tr._eval(other, "() => 1")
        check(False, "another error propagates")
    except ValueError:
        check(True, "any other error propagates unchanged")
    cerr = []
    test = {"start": "login", "steps": [{"do": "submit", "target": "x"}], "expect": [{"screen": "login"}]}
    st1, detail = tr._run_scenario(_FakePage(navigating=True), cerr, test, role_id=None)
    st2, _ = tr._run_scenario(_FakePage(), cerr, test, role_id=None)
    check(st1 == "blocked" and "navigat" in detail, f"a scenario on a navigating page is blocked with the reason ({st1}: {detail})")
    check(st2 == "pass", f"…and the next scenario still runs and passes ({st2})")


def navigation_run(sync_playwright):
    """The real thing: a seed that reloads the page. The scenario is `blocked` (lastResult.status), the
    others still pass, and there is no traceback."""
    print("test_run.py --functional (a scenario that navigates mid-run is blocked, the run continues):")
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        os.makedirs(os.path.join(tmp, "runtime"))
        with open(os.path.join(tmp, "runtime", "nav.js"), "w", encoding="utf-8") as f:
            f.write("window.pbScenarioSwitch = function () { location.reload(); return new Promise(function () {}); };\n")
        reg = load(reg_path)
        reg["runtime"] = (reg.get("runtime") or []) + [{"id": "nav-race", "src": "runtime/nav.js", "why": "test: a seed that reloads"}]
        story = reg["flow"]["stories"][0]
        story["scenarios"].insert(0, {"text": "Seeding reloads the page.", "category": "function",
                                      "test": {"start": "login", "seed": "reload", "steps": [],
                                               "expect": [{"screen": "login"}]}})
        dump(reg, reg_path)
        r = run_tool(TEST_RUN, reg_path, "--functional")
        out = r.stdout + r.stderr
        check("Traceback" not in out, f"no traceback on a navigating scenario\n{out[-600:]}")
        scen = list(iter_test_scenarios(load(reg_path)))
        statuses = [(sc.get("lastResult") or {}).get("status") for sc in scen]
        check(statuses[0] == "blocked", f"the navigating scenario is recorded blocked ({statuses})")
        check(len(statuses) >= 2 and all(s == "pass" for s in statuses[1:]),
              f"the scenarios after it still ran and passed ({statuses})")
        check(r.returncode == 1, f"a blocked scenario is a warning, exit 1 (rc={r.returncode})")


def run():
    navigation_race()
    # ── dependency gates (skip cleanly, exit 2) ──────────────────────────────
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed — skipping sandbox e2e (dev/CI-only dependency).")
        print("  pip install playwright && playwright install chromium")
        sys.exit(2)
    if not os.path.isfile(TEST_RUN):
        print(f"test_run.py not found at {TEST_RUN} — skipping (Wave-2 tool not built yet).")
        sys.exit(2)

    # ── 1 · functional pass + lastResult on the golden ───────────────────────
    print("test_run.py --functional (golden — all pass):")
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        r = run_tool(TEST_RUN, reg_path, "--functional")
        check(r.returncode == 0,
              f"--functional exits 0 on the golden (rc={r.returncode})\n{r.stdout}{r.stderr}")
        reg = load(reg_path)
        scen = list(iter_test_scenarios(reg))
        check(len(scen) >= 2, f"golden carries >= 2 runnable scenarios (got {len(scen)})")
        statuses = [(sc.get("lastResult") or {}).get("status") for sc in scen]
        check(all(s == "pass" for s in statuses),
              f"every runnable scenario recorded lastResult.status == pass ({statuses})")
        check(all((sc.get("lastResult") or {}).get("ranAt") and
                   (sc.get("lastResult") or {}).get("detail") for sc in scen),
              "each lastResult carries a detail + ranAt")

    navigation_run(sync_playwright)

    # ── 1b · the verdicts are saved under the registry lock, after the run, on a fresh read ──
    # What is asserted is WHERE the write happens, not whether the scenarios pass (section 1 does that),
    # so a browser that times out loading the page (the shell pulls Mermaid from a CDN) is retried
    # rather than blamed on the lock.
    print("test_run.py --functional (lastResult is written under the registry lock, never during the run):")
    sys.path.insert(0, TOOLS)
    import importlib
    pbslice = importlib.import_module("slice")              # `import slice` would shadow the builtin
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        proc = subprocess.Popen([sys.executable, TEST_RUN, reg_path, "--functional"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        free = 0
        while proc.poll() is None and free < 3:             # the run is under way: can anyone else take the lock?
            try:
                with pbslice.registry_lock(reg_path, "a test probing the lock", timeout=0.1):
                    free += 1
            except pbslice.RegistryLocked:
                pass
            time.sleep(0.2)
        out, _ = proc.communicate(timeout=120)
        check(free >= 3, f"the registry lock is FREE while the browser runs ({free} probes took it mid-run)")
    waiting, out, reg, statuses = False, "", None, []
    for attempt in range(3):
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = copy_golden(tmp)
            with pbslice.registry_lock(reg_path, "a test holding the lock"):
                proc = subprocess.Popen([sys.executable, TEST_RUN, reg_path, "--functional"],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                        env=dict(os.environ, PB_LOCK_TIMEOUT="60"))
                time.sleep(9)                                # long enough for the run to finish and reach the write
                waiting = proc.poll() is None
                mid = load(reg_path)
                mid["meta"]["editedWhileLocked"] = "yes"      # an edit saved while the run was held up
                pbslice._write(reg_path, mid)
            out, _ = proc.communicate(timeout=120)
            reg = load(reg_path)
            statuses = [(sc.get("lastResult") or {}).get("status") for sc in iter_test_scenarios(reg)]
        if "Traceback" not in out:
            break                                            # the run reached the write (a browser timeout is a Traceback: try again)
    check(waiting, "with the lock held, the finished run WAITS to save its verdicts (it does not write around the lock)")
    check(statuses and all(s in ("pass", "fail") for s in statuses),
          f"…then saves a verdict for every scenario once it can ({statuses}, rc={proc.returncode})\n{out}")
    check(reg["meta"].get("editedWhileLocked") == "yes",
          "…on a fresh read: the edit saved while it waited is NOT overwritten by the registry it loaded at the start")

    # ── 2 · flip one expect → RED ────────────────────────────────────────────
    print("test_run.py --functional (a flipped expect turns RED):")
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        reg = load(reg_path)
        flipped_text = None
        for sc in iter_test_scenarios(reg):
            for item in sc["test"]["expect"]:
                if item.get("screen") == "dashboard":
                    item["screen"] = "login"   # a valid submit lands on dashboard, NOT login
                    flipped_text = sc.get("text")
        check(flipped_text is not None, "found the valid-submit scenario to flip")
        dump(reg, reg_path)
        r = run_tool(TEST_RUN, reg_path, "--functional")
        check(r.returncode != 0,
              f"a flipped expect makes --functional fail (rc={r.returncode})")
        reg = load(reg_path)
        red = next((sc for sc in iter_test_scenarios(reg) if sc.get("text") == flipped_text), None)
        status = (red or {}).get("lastResult", {}).get("status") if red else None
        check(status == "fail",
              f"the flipped scenario records lastResult.status == fail (got {status!r})")

    # ── 4 · --roles flags a leaked gated element ─────────────────────────────
    # The golden's dashboard carries a data-roles="admin" control (hidden for member). Here we
    # sabotage the body so it is FORCE-visible (!important beats a display/visibility/opacity hide),
    # i.e. it leaks to the member role — the exact case --roles must flag.
    print("test_run.py --roles (a leaked gated element is flagged):")
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        # A STYLESHEET !important rule (important-author) beats the inline, normal-priority
        # display:none that pbApplyRoleGating sets on the element — the realistic "some CSS
        # overrode the gating" leak. (An inline !important would NOT leak: a JS .style.display=
        # assignment replaces the element's own inline declaration outright.)
        leaked = (
            "function renderScreenDashboard(props) {\n"
            "return '<div style=\"min-height:100%;padding:var(--space-8);background:var(--bg-soft)\">'\n"
            "  + '<style>#proto-frame .leaked-admin{display:block !important;visibility:visible !important;opacity:1 !important}</style>'\n"
            "  + '<h1 style=\"font-family:var(--font-heading);font-size:var(--text-2xl);font-weight:700;margin:0 0 var(--space-2)\">Welcome back</h1>'\n"
            "  + '<p style=\"font-family:var(--font-body);font-size:var(--text-sm);color:var(--text-muted)\">You are signed in.</p>'\n"
            "  + '<button data-roles=\"admin\" class=\"leaked-admin\" style=\"height:var(--size-control);padding:0 var(--space-5);border:0;border-radius:var(--radius-small);background:var(--brand);color:var(--on-brand);font-family:var(--font-body);font-size:var(--text-sm);cursor:pointer\">LEAKED ADMIN CONTROL</button>'\n"
            "  + '</div>';\n"
            "}\n"
        )
        with open(os.path.join(tmp, "render", "screens", "dashboard.js"), "w", encoding="utf-8") as f:
            f.write(leaked)
        r = run_tool(TEST_RUN, reg_path, "--roles")
        check(r.returncode != 0,
              f"--roles flags the leaked admin control (rc={r.returncode})\n{r.stdout}{r.stderr}")

    # ── 5 · --server flags a broken data-nav target ──────────────────────────
    # Break login's "Create an account" nav to a non-existent screen, and add a scenario that
    # navigates through it, so a dangling data-nav is surfaced (a nav-integrity finding, or a
    # failing navigating scenario) — either way non-zero.
    print("test_run.py --server (a broken data-nav target is flagged):")
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = copy_golden(tmp)
        login_path = os.path.join(tmp, "render", "screens", "login.js")
        src = open(login_path, encoding="utf-8").read().replace(
            'data-nav="account"', 'data-nav="ghost-screen"')
        with open(login_path, "w", encoding="utf-8") as f:
            f.write(src)
        reg = load(reg_path)
        reg["flow"]["stories"][0]["scenarios"].append({
            "text": "Broken nav goes nowhere.",
            "category": "function",
            "test": {
                "start": "login",
                "steps": [{"do": "click", "target": '[data-nav="ghost-screen"]'}],
                "expect": [{"screen": "ghost-screen"}],
            },
        })
        dump(reg, reg_path)
        r = run_tool(TEST_RUN, reg_path, "--server")
        check(r.returncode != 0,
              f"--server flags the dangling data-nav (rc={r.returncode})\n{r.stdout}{r.stderr}")

    # ── 6 · lint_registry.py --strict stays clean with the additive keys ─────────────
    print("lint_registry.py --strict (golden stays clean with the additive keys):")
    r = run_tool(CHECK, "--strict", GOLDEN)
    check(r.returncode == 0,
          f"lint_registry.py --strict exits 0 on the golden (rc={r.returncode})\n{r.stdout}{r.stderr}")

    # ── 3 + 7 · shell behaviours (glyphs · role switcher/reset · gating) ─────
    print("shell (golden — glyphs, role switcher/reset, element gating):")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
            sys.exit(2)
        with Server(GOLDEN) as srv:
            page = browser.new_page()
            _offline(page)
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab", timeout=10000)

            # 7a — the meta nav renders the Sandbox button; opening it reveals the roles dropdown +
            # Reset session (meta.roles present). The controls live in the popover, not the header.
            page.click('.meta-tab >> nth=0')  # Prototype
            page.wait_for_timeout(120)
            check(page.locator(".meta-sandbox").count() >= 1,
                  "the Sandbox button renders in the meta nav")
            page.click(".meta-sandbox")
            page.wait_for_timeout(150)
            check(page.locator('.proto-sandbox-menu select[aria-label="Preview as role"]').count() == 1,
                  "opening the menu shows the roles dropdown")
            check(page.locator('.proto-sandbox-menu select[aria-label="Preview as role"] option').count() >= 2,
                  "the roles dropdown lists the project roles")
            check(page.locator(".proto-sandbox-menu .proto-menu-item").count() >= 1,
                  "the menu has a Reset session action")
            page.evaluate("typeof closeCopyPopover==='function' && closeCopyPopover()")
            page.wait_for_timeout(100)

            # 7b — element gating: the admin control is hidden for member, shown for admin.
            page.evaluate("setProtoScreen('dashboard')")
            page.wait_for_timeout(120)
            member_vis = page.locator('#proto-frame [data-roles="admin"]:visible').count()
            check(member_vis == 0,
                  f"data-roles=admin element hidden for the member role (visible={member_vis})")
            page.evaluate("setProtoRole('admin')")
            page.wait_for_timeout(150)
            admin_vis = page.locator('#proto-frame [data-roles="admin"]:visible').count()
            check(admin_vis >= 1,
                  f"data-roles=admin element visible for the admin role (isAdmin bypass) ({admin_vis})")
            page.evaluate("setProtoRole('member')")  # restore before leaving the tab

            # 3 — UX Design → Test Cases: a no-test scenario shows ☐; an un-run test scenario ○.
            # Test Cases became a UX-Design SUB-tab (UX_SUBTABS, shell ~4136): a .meta-subtab
            # button carrying data-ux-view="tests" (it calls pbSetUxView(this.dataset.uxView) — the id is data
            # now, not a quoted JS string in the onclick, M1), not the old [data-tab="tests"]. This step went
            # on clicking a selector the shell had stopped emitting and timed out every time —
            # unseen, because the file skipped on every machine that had no Playwright.
            page.click('.meta-tab >> nth=2')  # UX Design
            page.wait_for_timeout(150)
            page.click('.ux-subtabs .meta-subtab[data-ux-view="tests"]')
            page.wait_for_timeout(200)
            txt = page.locator("#app").inner_text()
            check("☐" in txt, "a scenario WITHOUT a test{} block renders the manual ☐ glyph")
            check("○" in txt, "a runnable-but-un-run scenario renders the untested ○ glyph")

            # 6-ish — no console errors through the interactions (filter mermaid CDN noise, which
            # is network-dependent and not part of this contract).
            real = [e for e in errors if "mermaid" not in e.lower()]
            check(not real, f"zero (non-mermaid) console errors on the golden ({real})")
            page.close()
        browser.close()

    print()
    if _failures:
        print(f"✗ {len(_failures)} sandbox assertion(s) failed.")
        sys.exit(1)
    print("✓ All sandbox assertions passed.")


if __name__ == "__main__":
    run()
