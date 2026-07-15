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
  6. check.py --strict stays exit 0 on the golden with all the additive keys present
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
CHECK = os.path.join(TOOLS, "check.py")
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


def run():
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

    # ── 6 · check.py --strict stays clean with the additive keys ─────────────
    print("check.py --strict (golden stays clean with the additive keys):")
    r = run_tool(CHECK, "--strict", GOLDEN)
    check(r.returncode == 0,
          f"check.py --strict exits 0 on the golden (rc={r.returncode})\n{r.stdout}{r.stderr}")

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
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(srv.url, wait_until="domcontentloaded")
            page.wait_for_selector(".meta-tab", timeout=10000)

            # 7a — the Prototype header renders the ⋯ sandbox menu; opening it reveals the role
            # switcher + Reset (meta.roles present). The controls live in the popover, not the header.
            page.click('.meta-tab >> nth=0')  # Prototype
            page.wait_for_timeout(120)
            check(page.locator(".proto-menu-btn").count() >= 1,
                  "sandbox menu button renders in the Prototype header")
            page.click(".proto-menu-btn")
            page.wait_for_timeout(150)
            check(page.locator(".proto-sandbox-menu .proto-role-item").count() >= 2,
                  "opening the menu lists the roles (list, not a dropdown)")
            check(page.locator(".proto-sandbox-menu .proto-role-item-desc").count() >= 1,
                  "each role row shows a description (abilities / JTBD)")
            check(page.locator(".proto-sandbox-menu .proto-role-radio").count() >= 2,
                  "each role row shows a radio (not a check glyph)")
            check(page.locator('.proto-sandbox-menu .proto-role-item[aria-checked="true"] .proto-role-radio.is-on').count() == 1,
                  "exactly one role's radio is filled (single selection)")
            check(page.locator(".proto-sandbox-menu .proto-menu-item").count() >= 1,
                  "the menu has a Reset sandbox action")
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

            # 3 — UX Design → Test cases: a no-test scenario shows ☐; an un-run test scenario ○.
            page.click('.meta-tab >> nth=2')  # UX Design (flow)
            page.wait_for_timeout(150)
            page.click('[data-tab="tests"]')
            page.wait_for_timeout(150)
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
