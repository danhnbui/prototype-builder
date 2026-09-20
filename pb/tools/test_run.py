#!/usr/bin/env python3
"""
pb-test — the Playwright-backed test runner (v1.5).

Drives the SAME rendered shell the preview serves (booted through serve.py, exactly
like tests/e2e_smoke.py) and verifies prototype behaviour four ways:

  --functional (DEFAULT)  Run every flow.stories[].scenarios[] that carries a `.test`
                          block: navigate from test.start, execute each step, assert
                          each expect item, then write a `lastResult` verdict back into
                          the registry (read by the UX-tab test glyph).
  --roles                 For each meta.roles entry, drive setProtoRole() and walk the
                          screens: screens/elements gated to OTHER roles must be absent
                          for a non-admin role and present for an admin one. Leaks = ERROR.
                          THEN runs the authored scenarios once per role — visibility
                          sampling cannot tell you whether a role's flow actually works,
                          and a role-gated write control carries no data-roles attribute
                          at all (the render body omits it).
  --server                Assert server health (GET / == 200, /__pb_events is an SSE
                          stream), render every screen with zero console errors + a live
                          render fn, and statically verify every data-nav / data-go /
                          data-redirect target resolves to a real screen (reachability).
  --explore               Enumerate screens + interactive data-* targets, run the static
                          reachability check, and PRINT a human report of dead-ends and
                          untested transitions. Report-only — never writes.

Playwright is a dev/CI-only dependency (NS4 — never shipped to users, never pip-installed
by the plugin). It is imported lazily; if absent the runner prints the install hint and
exits 3 (cannot run) instead of crashing. --explore needs no browser.

`--attach [URL]` is TRANSPORT, not a mode: it reuses an already-running /pb:preview server
instead of booting a headless one, and composes with every mode. (`--server` remains a MODE —
server health + per-screen render + reachability.) A scenario's `roles` and `seed` are both
honoured: it runs once per declared role, with the role set EXPLICITLY every time rather than
inherited, and `lastResult` records which role produced the verdict.

Findings mirror lint_registry.py exactly — each prints as `<SEVERITY> [<CODE>] <where>: <msg>`;
exit 0 = clean, 1 = warnings only, 2 = any error, 3 = COULD NOT RUN (no browser, no reachable
preview) — so CI can tell "the sandbox is not installed here" from "this prototype is broken";
a clean run prints `✓ <label>: <ok>`.

Usage:
  python3 test_run.py <registry.json> [--functional] [--roles] [--server] [--explore]
                      [--attach [URL]] [--story <id|title>] [--json <out>]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SERVE = os.path.join(HERE, "serve.py")

ERROR, WARN = "ERROR", "WARN"

# data-* attributes that declare a navigation target (must resolve to a screen id).
NAV_ATTRS = ("data-nav", "data-go", "data-redirect")
_NAV_RE = {attr: re.compile(attr + r'\s*=\s*"([^"]*)"') for attr in NAV_ATTRS}
_ACTION_RE = re.compile(r'data-action\s*=\s*"([^"]*)"')


# ─────────────────────────────────────────────────────────────────────────────
# Finding + reporting — copied verbatim in spirit from pb/tools/lint_registry.py so the
# CLI contract (severity line, exit code, clean banner) is identical.
# ─────────────────────────────────────────────────────────────────────────────
class Finding:
    __slots__ = ("severity", "code", "where", "msg")

    def __init__(self, severity, code, where, msg):
        self.severity = severity
        self.code = code
        self.where = where
        self.msg = msg

    def line(self):
        return f"{self.severity} [{self.code}] {self.where}: {self.msg}"


def _findings_json(findings):
    return [{"severity": f.severity, "code": f.code, "where": f.where, "msg": f.msg}
            for f in findings]


def _report(findings, label, ok_msg):
    """Print findings, then exit 0 (clean) / 1 (warnings) / 2 (any error)."""
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    for f in findings:
        print(f.line())
    if not findings:
        print(f"✓ {label}: {ok_msg}")
        sys.exit(0)
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(2 if errors else 1)


def _load_json(path):
    """Load a JSON file, failing closed with a one-line R-IO/R-JSON message (no traceback)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _write_registry(path, reg):
    """Persist the registry back to disk (indent=2, key order preserved by the dict)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)


def _now_z():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────────────────────
# Server — boot serve.py on a registry, parse the chosen URL from its stdout.
# (Same pattern as tests/e2e_smoke.py's Server.)
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_attach(value, reg_path):
    """Resolve --attach into a live preview URL, or exit 3. Never boots a server.

    `--attach http://…` is taken as given. Bare `--attach` looks for the project's canonical
    `.claude/launch.json` preview entry, then probes the usual local ports. Reachability is
    checked here so "the preview is not running" surfaces as cannot-run (3), not as a wall of
    failing scenarios (2).
    """
    import urllib.error
    import urllib.request

    def reachable(u):
        try:
            with urllib.request.urlopen(u, timeout=2) as r:
                return 200 <= r.status < 400
        except (urllib.error.URLError, OSError, ValueError):
            return False

    if value:
        url = value if value.endswith("/") else value + "/"
        if not reachable(url):
            _cannot_run(f"--attach {value} is not reachable — start /pb:preview first")
        return url

    cands = []
    lj = os.path.join(os.path.dirname(reg_path), ".claude", "launch.json")
    if os.path.isfile(lj):
        try:
            for entry in (json.load(open(lj, encoding="utf-8")) or {}).get("configurations", []):
                for v in (entry or {}).values():
                    if isinstance(v, str):
                        for m in re.finditer(r"https?://[\w.\-]+:\d+/?", v):
                            cands.append(m.group(0))
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    cands += [f"http://127.0.0.1:{p}/" for p in (5173, 8000, 8080, 8100, 8200)]
    for u in dict.fromkeys(cands):
        u = u if u.endswith("/") else u + "/"
        if reachable(u):
            print(f"attached to the running preview at {u}")
            return u
    _cannot_run("--attach found no running preview — start /pb:preview, or pass --attach <url>")


class _Attached:
    """A Server-shaped handle over an already-running preview. Starts and stops nothing."""

    def __init__(self, url):
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _transport(reg_path, attach):
    """The context manager a mode should use: an attached preview, or a fresh headless one."""
    return _Attached(attach) if attach else Server(reg_path)


class Server:
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
            # Boot failed — clean up the orphaned serve.py and report per the 0/1/2 contract
            # instead of raising an uncaught traceback.
            try:
                if self.proc:
                    self.proc.terminate()
            except Exception:
                pass
            print("ERROR [T-SERVE] serve.py: preview server did not report a URL within 15s")
            sys.exit(2)
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ─────────────────────────────────────────────────────────────────────────────
# Playwright bootstrap — lazy import; degrade gracefully when absent.
# ─────────────────────────────────────────────────────────────────────────────
# Exit codes. 0/1/2 keep their meanings exactly (0 clean, 1 warnings, 2 an error or a failing
# scenario). 3 is new (D-27): "could not run at all". Before it, a missing browser and a genuinely
# failing assertion both exited 2, so a CI step could not tell "the sandbox is not installed here"
# from "this prototype is broken" — and the two want opposite responses.
EXIT_CANNOT_RUN = 3


def _cannot_run(msg):
    """Exit 3 — the runner could not start. Never used for a test that ran and failed."""
    print(f"⚠ cannot run: {msg}")
    sys.exit(EXIT_CANNOT_RUN)


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        _cannot_run("Playwright not installed — pip install playwright && playwright install chromium")
    return sync_playwright


def _launch(p):
    try:
        return p.chromium.launch()
    except Exception as e:  # browser binary missing / launch failure
        print(f"Could not launch Chromium ({e}). Run: playwright install chromium")
        sys.exit(2)


def _open_page(p, url):
    """Launch Chromium, open `url`, wait for the Prototype tab, wire an error buffer.

    Returns (browser, page, console_errors) — console_errors is a live list mutated by
    the console/pageerror handlers; clear it in place (del buf[:]) to scope a check."""
    browser = _launch(p)
    page = browser.new_page()
    console_errors = []
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append(str(e)))
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector("#proto-frame", timeout=10000)
    return browser, page, console_errors


# ─────────────────────────────────────────────────────────────────────────────
# Static helpers — render-body scans (reachability), scenario iteration.
# ─────────────────────────────────────────────────────────────────────────────
def _body_text(item, base_dir):
    """Return an item's render body: renderSrc file (v1.4) or legacy inline `render`."""
    src = item.get("renderSrc")
    if src:
        path = os.path.normpath(os.path.join(base_dir, src))
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return item.get("render", "") or ""
    return item.get("render", "") or ""


def _extract_targets(body):
    """List of (attr, value) navigation targets declared in a render body."""
    out = []
    for attr, rx in _NAV_RE.items():
        for val in rx.findall(body or ""):
            out.append((attr, val))
    return out


def _extract_actions(body):
    return list(dict.fromkeys(_ACTION_RE.findall(body or "")))


def _screen_ids(reg):
    return {s.get("id") for s in (reg.get("screens") or []) if isinstance(s, dict)}


def reachability_findings(reg, base_dir):
    """ERROR for every data-nav / data-go / data-redirect target that names no screen."""
    findings = []
    sids = _screen_ids(reg)
    for kind in ("screens", "components"):
        for item in reg.get(kind, []) or []:
            if not isinstance(item, dict):
                continue
            cid = item.get("id", "")
            body = _body_text(item, base_dir)
            for attr, val in _extract_targets(body):
                if val and val not in sids:
                    findings.append(Finding(
                        ERROR, "T-REACH", f"{kind[:-1]} {cid!r} {attr}={val!r}",
                        f"navigation target {val!r} resolves to no screen id"))
    return findings


def _iter_test_scenarios(reg, story_filter=None):
    """Yield (story, scenario_dict, test_dict) for object scenarios with a `.test` block."""
    flow = reg.get("flow") or {}
    for story in (flow.get("stories") or []):
        if not isinstance(story, dict):
            continue
        if story_filter:
            title = str(story.get("title") or "")
            sid = str(story.get("id") or "")
            if story_filter not in (title, sid) and story_filter.lower() not in title.lower():
                continue
        for sc in (story.get("scenarios") or []):
            if isinstance(sc, dict) and isinstance(sc.get("test"), dict):
                yield (story, sc, sc["test"])


# ─────────────────────────────────────────────────────────────────────────────
# In-page JS — step execution, gating audit, per-screen info, error/expect probes.
# ─────────────────────────────────────────────────────────────────────────────
_STEP_JS = r"""(step) => {
  const frame = document.getElementById('proto-frame');
  if (!frame) return { ok:false, detail:'no #proto-frame' };
  function byData(root, val) {
    const all = Array.from(root.querySelectorAll('*'));
    for (const el of all) {
      for (const a of Array.from(el.attributes)) {
        if (a.name.indexOf('data-') === 0 && a.value === val) return el;
      }
    }
    return null;
  }
  function resolveEl(target) {
    if (!target) return null;
    try { const el = frame.querySelector(target); if (el) return el; } catch (e) {}
    return byData(frame, target);
  }
  function resolveInput(target) {
    if (!target) return frame.querySelector('.field__input');
    const labels = Array.from(frame.querySelectorAll('.field__label, label'));
    for (const lb of labels) {
      const t = (lb.textContent || '').trim();
      if (t === target || (target && t.indexOf(target) !== -1)) {
        const field = lb.closest('.field') || lb.parentElement;
        const inp = field && field.querySelector('.field__input, input, textarea, select');
        if (inp) return inp;
      }
    }
    try { const el = frame.querySelector(target); if (el) return el; } catch (e) {}
    return byData(frame, target);
  }
  const d = step.do;
  if (d === 'fill') {
    const inp = resolveInput(step.target);
    if (!inp) return { ok:false, detail:'fill: no input for ' + JSON.stringify(step.target) };
    inp.value = step.value == null ? '' : String(step.value);
    inp.dispatchEvent(new Event('input', { bubbles:true }));
    inp.dispatchEvent(new Event('change', { bubbles:true }));
    return { ok:true };
  }
  if (d === 'back') {
    if (typeof protoBack === 'function') { protoBack(); return { ok:true }; }
    return { ok:false, detail:'back: no protoBack()' };
  }
  let target = step.target;
  if (!target && d === 'submit') target = '[data-action="submit"]';
  if (!target && d === 'toggle-password') target = '[data-action="toggle-password"]';
  let el = resolveEl(target);
  if (!el && d === 'nav' && step.target && typeof setProtoScreen === 'function') {
    setProtoScreen(step.target);
    return { ok:true };
  }
  if (!el) return { ok:false, detail: d + ': no element for ' + JSON.stringify(step.target) };
  el.click();
  return { ok:true };
}"""

_GATE_JS = r"""(arg) => {
  const rid = arg.rid, admin = arg.admin;
  const frame = document.getElementById('proto-frame');
  if (!frame) return { total:0, leaks:0, hiddenForAdmin:0 };
  function boxVisible(n){
    const s = getComputedStyle(n);
    if (s.display === 'none' || s.visibility === 'hidden' || s.visibility === 'collapse') return false;
    if (parseFloat(s.opacity || '1') === 0) return false;
    const r = n.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  // Effectively visible = the element OR any descendant renders a non-hidden box. Checking
  // descendants closes the display:contents (no own box, visible children) and
  // visibility:hidden-parent + visible-child blind spots a plain offsetParent/display check misses.
  // (A properly gated element gets display:none, which removes its whole subtree from layout, so
  // descendants report zero-size boxes and it is correctly NOT counted as visible.)
  function effVisible(el){
    if (boxVisible(el)) return true;
    const kids = el.querySelectorAll('*');
    for (let i = 0; i < kids.length; i++) if (boxVisible(kids[i])) return true;
    // A display:contents host whose only content is a TEXT node has no element box to measure —
    // measure the rendered text via a Range, then confirm no ancestor (up to #proto-frame) hides it.
    try {
      const es = getComputedStyle(el);
      if (es.display !== 'none' && es.visibility !== 'hidden' && parseFloat(es.opacity || '1') !== 0) {
        const rng = document.createRange(); rng.selectNodeContents(el);
        const rr = rng.getBoundingClientRect();
        if (rr.width > 0 && rr.height > 0) {
          let a = el.parentElement, ok = true;
          while (a && a.id !== 'proto-frame' && a !== document.body) {
            const as = getComputedStyle(a);
            if (as.display === 'none' || as.visibility === 'hidden' || parseFloat(as.opacity || '1') === 0) { ok = false; break; }
            a = a.parentElement;
          }
          if (ok) return true;
        }
      }
    } catch (e) {}
    return false;
  }
  const els = Array.from(frame.querySelectorAll('[data-roles]'));
  let leaks = 0, hiddenForAdmin = 0;
  els.forEach(function (el) {
    const set = (el.getAttribute('data-roles') || '').split(/\s+/).filter(Boolean);
    const allowed = set.length === 0 || set.indexOf(rid) !== -1;
    const visible = effVisible(el);
    if (admin) { if (!visible) hiddenForAdmin++; }
    else if (!allowed && visible) leaks++;
  });
  return { total: els.length, leaks: leaks, hiddenForAdmin: hiddenForAdmin };
}"""

_SCREEN_INFO_JS = r"""(arg) => {
  const fn = arg.fn;
  const frame = document.getElementById('proto-frame');
  return {
    cur: (typeof state !== 'undefined' && state) ? state.protoScreenId : null,
    hasFn: !!fn && typeof window[fn] === 'function',
    hasFrame: !!frame,
    empty: !frame || (frame.textContent || '').trim().length === 0
  };
}"""

_COUNT_ERR_JS = r"""() => {
  const f = document.getElementById('proto-frame');
  if (!f) return 0;
  return Array.from(f.querySelectorAll('.field__error')).filter(function (e) {
    const cs = getComputedStyle(e);
    return e.offsetParent !== null && cs.display !== 'none' && cs.visibility !== 'hidden';
  }).length;
}"""

_TOAST_OBS_JS = r"""() => {
  window.__pbToasts = window.__pbToasts || [];
  if (!window.__pbToastObs) {
    window.__pbToastObs = new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        m.addedNodes.forEach(function (n) {
          if (n.nodeType === 1 && n.classList && n.classList.contains('proto-toast')) {
            window.__pbToasts.push(n.textContent || '');
          }
        });
      });
    });
    window.__pbToastObs.observe(document.body, { childList:true, subtree:true });
  }
}"""


def _check_expect(page, exp, console_errors):
    """Return (ok, detail) for a single expect item (one of the contract's shapes)."""
    if not isinstance(exp, dict):
        return (False, f"malformed expect: {exp!r}")
    if "screen" in exp:
        cur = page.evaluate("() => (typeof state!=='undefined' && state) ? state.protoScreenId : null")
        return (cur == exp["screen"], f"protoScreenId={cur!r}, expected {exp['screen']!r}")
    if "text" in exp:
        txt = page.evaluate("() => { const f=document.getElementById('proto-frame'); return f ? f.textContent : ''; }")
        return (exp["text"] in (txt or ""), f"text {exp['text']!r} not found in #proto-frame")
    if "errors" in exp:
        n = page.evaluate(_COUNT_ERR_JS)
        spec = exp["errors"] or {}
        if "count" in spec:
            return (n == spec["count"], f"visible error count {n} != {spec['count']}")
        if "min" in spec:
            return (n >= spec["min"], f"visible error count {n} < min {spec['min']}")
        return (False, "errors expect needs 'min' or 'count'")
    if "toast" in exp:
        toasts = page.evaluate("() => window.__pbToasts || []") or []
        want = exp["toast"]
        hit = any(want in (t or "") for t in toasts)
        return (hit, f"toast {want!r} not observed (saw {toasts})")
    if "no-console-error" in exp:
        if exp.get("no-console-error"):
            return (len(console_errors) == 0, f"console error(s): {console_errors[:5]}")
        return (True, "")
    # present / absent — PRESENCE, not visibility (D-27).
    #
    # A role-gated write control is omitted from the HTML string entirely by the render body when
    # the resolved bucket lacks the capability, so `querySelector` is the honest question. A
    # control that is merely CSS-hidden PASSES `present` and should: hiding is the `:has()` reveal
    # mechanism, a different concern with its own checks. Conflating the two is what makes a
    # visibility-based role audit noisy enough to be ignored.
    for key in ("present", "absent"):
        if key in exp:
            sel = exp[key]
            try:
                n = page.evaluate(
                    "(s) => { const f=document.getElementById('proto-frame');"
                    " if (!f) return -1; try { return f.querySelectorAll(s).length; }"
                    " catch (e) { return -2; } }", sel)
            except Exception as e:                                    # noqa: BLE001
                return (False, f"{key} {sel!r}: page evaluate failed: {e}")
            if n == -1:
                return (False, f"{key} {sel!r}: no #proto-frame on the page")
            if n == -2:
                return (False, f"{key} {sel!r}: not a valid CSS selector")
            if key == "present":
                return (n > 0, f"{sel!r} not present in #proto-frame (matched 0)")
            return (n == 0, f"{sel!r} present in #proto-frame (matched {n}) but expected absent")
    return (False, f"unknown expect key(s): {list(exp.keys())}")


def _apply_role(page, role_id):
    """Drive the shell's setProtoRole seam. Returns (ok, detail).

    Set EXPLICITLY before every scenario, never inherited. The shell's pbResetSandbox() clears
    the screen, history, inputs and toasts but NOT state.activeRole, so a scenario that follows a
    role switch would otherwise silently run as the previous role — the order-dependence this
    whole change exists to remove. Setting it every time is correct both before and after the
    shell learns to reset it.
    """
    if role_id is None:
        return (True, "")
    if page.evaluate("() => typeof setProtoRole") != "function":
        return (False, "setProtoRole seam not found — cannot run per-role")
    page.evaluate("(id) => setProtoRole(id)", role_id)
    page.wait_for_timeout(60)
    return (True, "")


def _apply_seed(page, seed):
    """Apply a scenario's `seed` through the shell's scenario seam. Returns (ok, detail).

    A seed names a data scenario the project authored. It is reported when it cannot be applied
    rather than ignored: the real project authors `seed` on every test block, and a silently
    discarded authored field is exactly the defect this change exists to fix.
    """
    if not seed:
        return (True, "")
    fn = page.evaluate(
        "() => (typeof pbScenarioSwitch === 'function') ? 'pbScenarioSwitch'"
        " : (typeof pbApplyScenario === 'function') ? 'pbApplyScenario' : null")
    if not fn:
        return (False, f"seed {seed!r} declared but the shell exposes no scenario seam "
                       f"(pbScenarioSwitch / pbApplyScenario) — seed NOT applied")
    page.evaluate("([f, s]) => window[f](s)", [fn, seed])
    page.wait_for_timeout(120)
    return (True, "")


def _run_scenario(page, console_errors, test, role_id=None):
    """Drive one scenario's test block; return (status, detail)."""
    del console_errors[:]
    # Fresh sandbox + toast buffer before each scenario.
    page.evaluate("() => { if (typeof pbResetSandbox === 'function') pbResetSandbox(); window.__pbToasts = []; }")
    ok, detail = _apply_role(page, role_id)
    if not ok:
        return ("skip", detail)
    ok, detail = _apply_seed(page, test.get("seed"))
    if not ok:
        return ("fail", detail)
    start = test.get("start")
    if start:
        page.evaluate("(id) => { if (typeof setProtoScreen === 'function') setProtoScreen(id); }", start)
        page.wait_for_timeout(60)
    for step in (test.get("steps") or []):
        if not isinstance(step, dict) or not step.get("do"):
            return ("fail", f"malformed step: {step!r}")
        res = page.evaluate(_STEP_JS, step)
        if not res.get("ok"):
            return ("fail", f"step {step!r} failed: {res.get('detail')}")
        page.wait_for_timeout(120)
    page.wait_for_timeout(200)  # settle redirect timers / toast animation
    for exp in (test.get("expect") or []):
        ok, detail = _check_expect(page, exp, console_errors)
        if not ok:
            return ("fail", f"expect {exp!r} failed: {detail}")
    return ("pass", "all expectations met")


# ─────────────────────────────────────────────────────────────────────────────
# Modes
# ─────────────────────────────────────────────────────────────────────────────
def _scenario_screens(test):
    """Every screen a scenario actually exercises: where it starts, where it navigates, and
    every screen it asserts on. That set — not the whole project — is what its verdict depends
    on, so an edit elsewhere must not mark it stale."""
    out = set()
    if isinstance(test.get("start"), str):
        out.add(test["start"])
    for step in (test.get("steps") or []):
        if isinstance(step, dict) and step.get("do") in ("nav", "go") and isinstance(step.get("target"), str):
            out.add(step["target"])
    for exp in (test.get("expect") or []):
        if isinstance(exp, dict) and isinstance(exp.get("screen"), str):
            out.add(exp["screen"])
    return sorted(out)


def _body_hashes(reg_path):
    """{item id: digest} from logic_extract — the same derivation the shell is handed, so the
    two cannot disagree about what "changed" means. Fails OPEN: no extractor, no digests, and
    the verdict is written exactly as it was before this existed."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import logic_extract
        return logic_extract.extract(os.path.dirname(os.path.abspath(reg_path)) or ".").get("itemHash") or {}
    except Exception as exc:                                        # noqa: BLE001
        print("test_run: input digests skipped (%s: %s)" % (type(exc).__name__, exc))
        return {}


def _scenario_inputs(test, body_hash):
    return {sid: body_hash[sid] for sid in _scenario_screens(test) if sid in body_hash}


def run_functional(reg_path, story_filter, json_out, attach=None):
    reg = _load_json(reg_path)
    body_hash = _body_hashes(reg_path)
    tests = list(_iter_test_scenarios(reg, story_filter))
    if not tests:
        note = ("no scenarios match --story %r" % story_filter) if story_filter else "no functional test blocks"
        if json_out:
            _write_json(json_out, {"mode": "functional", "scenarios": [], "summary": note})
        _report([], "test_run.py --functional", f"{note} — {reg_path}")
        return

    sync_playwright = _require_playwright()
    findings, results = [], []
    with sync_playwright() as p:
        with _transport(reg_path, attach) as srv:
            browser, page, cerr = _open_page(p, srv.url)
            page.evaluate(_TOAST_OBS_JS)
            roles = (reg.get("meta") or {}).get("roles") or []
            fallback = _default_role_id(reg, roles)
            for (story, sc, test) in tests:
                title = sc.get("text") or story.get("title") or "(scenario)"
                # D-27: honour test.roles — run the scenario once per declared role. The field is
                # already authored on real projects and was being discarded, so every scenario ran
                # as whatever role happened to be active and reported `pass` for an unknown one.
                want = [r for r in (test.get("roles") or []) if isinstance(r, str)] or [fallback]
                per_role = []
                for rid in want:
                    status, detail = _run_scenario(page, cerr, test, role_id=rid)
                    per_role.append({"role": rid, "status": status, "detail": detail})
                    results.append({"story": story.get("title"), "scenario": title,
                                    "role": rid, "status": status, "detail": detail})
                    if status == "fail":
                        findings.append(Finding(
                            ERROR, "T-FUNC",
                            f"flow.stories[{story.get('title')!r}] scenario {title!r} "
                            f"as role {rid!r}", detail))
                # lastResult records WHICH role produced the verdict; a scenario is only `pass`
                # when every declared role passes.
                worst = ("fail" if any(r["status"] == "fail" for r in per_role)
                         else "skip" if any(r["status"] == "skip" for r in per_role) else "pass")
                sc["lastResult"] = {
                    "status": worst, "ranAt": _now_z(),
                    "detail": "; ".join(f"{r['role']}: {r['status']}" for r in per_role),
                    "roles": per_role,
                    # WHAT THIS VERDICT WAS COMPUTED FROM. Without it a `pass` is undated
                    # evidence: on the reference project three scenarios read "passing" after
                    # 141 of 141 render bodies had changed underneath them. The shell compares
                    # these against the live digests and shows a stale verdict as stale.
                    "inputs": _scenario_inputs(test, body_hash),
                }
            browser.close()

    _write_registry(reg_path, reg)  # persist lastResult verdicts (read by the UX-tab glyph)
    passed = sum(1 for r in results if r["status"] == "pass")
    if json_out:
        _write_json(json_out, {"mode": "functional", "passed": passed, "total": len(results),
                               "scenarios": results, "findings": _findings_json(findings)})
    _report(findings, "test_run.py --functional",
            f"{passed}/{len(results)} scenario(s) passed — {reg_path}")


def _default_role_id(reg, roles):
    m = reg.get("meta") or {}
    dr = m.get("defaultRole")
    if dr and any(r.get("id") == dr for r in roles):
        return dr
    non_admin = next((r for r in roles if not r.get("isAdmin")), None)
    if non_admin:
        return non_admin.get("id")
    return roles[0].get("id") if roles else None


def run_roles(reg_path, json_out, attach=None):
    reg = _load_json(reg_path)
    roles = ((reg.get("meta") or {}).get("roles")) or []
    if not roles:
        if json_out:
            _write_json(json_out, {"mode": "roles", "note": "no meta.roles"})
        _report([], "test_run.py --roles", f"no meta.roles — role gating not applicable — {reg_path}")
        return

    screens = reg.get("screens") or []
    sync_playwright = _require_playwright()
    findings, checked, ran = [], [], []
    with sync_playwright() as p:
        with _transport(reg_path, attach) as srv:
            browser, page, cerr = _open_page(p, srv.url)
            if page.evaluate("() => typeof setProtoRole") != "function":
                findings.append(Finding(
                    WARN, "T-ROLE-SEAM", "shell",
                    "setProtoRole seam not found — cannot verify role gating"))
            else:
                for role in roles:
                    rid = role.get("id")
                    admin = bool(role.get("isAdmin"))
                    page.evaluate("(id) => setProtoRole(id)", rid)
                    page.wait_for_timeout(60)
                    for s in screens:
                        if not isinstance(s, dict):
                            continue
                        sid = s.get("id")
                        sroles = s.get("roles")
                        permitted = admin or not sroles or (rid in sroles)
                        page.evaluate("(id) => { if (typeof setProtoScreen==='function') setProtoScreen(id); }", sid)
                        page.wait_for_timeout(40)
                        cur = page.evaluate("() => (typeof state!=='undefined' && state) ? state.protoScreenId : null")
                        shown = (cur == sid)
                        if permitted and not shown:
                            findings.append(Finding(
                                ERROR, "T-ROLE-SCREEN", f"role {rid!r} screen {sid!r}",
                                f"role should see this screen but navigation fell back to {cur!r}"))
                        if (not permitted) and shown:
                            findings.append(Finding(
                                ERROR, "T-ROLE-SCREEN", f"role {rid!r} screen {sid!r}",
                                "screen gated to other roles is reachable (leak)"))
                        if shown:
                            g = page.evaluate(_GATE_JS, {"rid": rid, "admin": admin})
                            if (not admin) and g["leaks"] > 0:
                                findings.append(Finding(
                                    ERROR, "T-ROLE-EL", f"role {rid!r} screen {sid!r}",
                                    f"{g['leaks']} element(s) gated to other roles are visible (leak)"))
                            if admin and g["hiddenForAdmin"] > 0:
                                findings.append(Finding(
                                    ERROR, "T-ROLE-EL", f"role {rid!r} screen {sid!r}",
                                    f"{g['hiddenForAdmin']} data-roles element(s) hidden despite admin bypass"))
                            checked.append({"role": rid, "screen": sid, "gatedEls": g["total"]})

                # D-27: --roles RUNS the authored scenarios per role. Visibility sampling above
                # answers "is a data-roles element hidden"; it cannot answer "does this role's
                # flow work", and a role-gated write control carries no data-roles attribute at
                # all — the render body omits it. Running the scenarios is the only way to see
                # that. `present`/`absent` expects are what a scenario uses to assert it.
                for (story, sc, test) in _iter_test_scenarios(reg, None):
                    title = sc.get("text") or story.get("title") or "(scenario)"
                    want = [r for r in (test.get("roles") or []) if isinstance(r, str)] \
                        or [r.get("id") for r in roles]
                    for rid in want:
                        status, detail = _run_scenario(page, cerr, test, role_id=rid)
                        ran.append({"scenario": title, "role": rid, "status": status})
                        if status == "fail":
                            findings.append(Finding(
                                ERROR, "T-ROLE-FUNC",
                                f"scenario {title!r} as role {rid!r}", detail))
            browser.close()

    if json_out:
        _write_json(json_out, {"mode": "roles", "roles": len(roles), "checked": checked,
                               "scenarios": ran, "findings": _findings_json(findings)})
    _report(findings, "test_run.py --roles",
            f"role gating verified across {len(roles)} role(s); "
            f"{len(ran)} scenario run(s) — {reg_path}")


def _check_health(url):
    """(ok, detail): GET / == 200 and /__pb_events opens a text/event-stream."""
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            if r.status != 200:
                return (False, f"GET / returned {r.status}")
    except Exception as e:
        return (False, f"GET / failed: {e}")
    ev = url.rstrip("/") + "/__pb_events"
    try:
        resp = urllib.request.urlopen(ev, timeout=8)
        try:
            status = resp.status
            ctype = resp.headers.get_content_type()
        finally:
            resp.close()
        if status != 200:
            return (False, f"/__pb_events returned {status}")
        if ctype != "text/event-stream":
            return (False, f"/__pb_events content-type {ctype!r} is not text/event-stream")
    except Exception as e:
        return (False, f"/__pb_events failed: {e}")
    return (True, "server healthy (GET / 200, /__pb_events SSE)")


def run_server(reg_path, json_out, attach=None):
    reg = _load_json(reg_path)
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    screens = reg.get("screens") or []
    roles = ((reg.get("meta") or {}).get("roles")) or []
    admin = next((r for r in roles if r.get("isAdmin")), None)
    default_role = _default_role_id(reg, roles)

    findings = list(reachability_findings(reg, base_dir))  # static, browserless
    health = {}
    sync_playwright = _require_playwright()
    with sync_playwright() as p:
        with _transport(reg_path, attach) as srv:
            ok, detail = _check_health(srv.url)
            health = {"ok": ok, "detail": detail}
            if not ok:
                findings.append(Finding(ERROR, "T-SERVE", "server", detail))

            browser, page, cerr = _open_page(p, srv.url)
            has_role_seam = page.evaluate("() => typeof setProtoRole") == "function"
            if admin and has_role_seam:
                page.evaluate("(id) => setProtoRole(id)", admin.get("id"))  # admin bypasses gating
            for s in screens:
                if not isinstance(s, dict):
                    continue
                sid = s.get("id")
                fn = s.get("renderFn")
                # Ensure the active role can see this screen so it actually renders.
                if roles and not admin and has_role_seam:
                    sroles = s.get("roles")
                    rid = (sroles[0] if sroles else default_role)
                    page.evaluate("(id) => setProtoRole(id)", rid)
                del cerr[:]
                page.evaluate("(id) => { if (typeof setProtoScreen==='function') setProtoScreen(id); }", sid)
                page.wait_for_timeout(80)
                info = page.evaluate(_SCREEN_INFO_JS, {"fn": fn})
                where = f"screen {sid!r}"
                if not info["hasFn"]:
                    findings.append(Finding(ERROR, "T-RENDERFN", where,
                                            f"render fn {fn!r} is not defined on window"))
                if not info["hasFrame"]:
                    findings.append(Finding(ERROR, "T-FRAME", where,
                                            "no #proto-frame after navigation"))
                elif info["cur"] != sid:
                    findings.append(Finding(ERROR, "T-FRAME", where,
                                            f"screen did not render (active screen is {info['cur']!r})"))
                if cerr:
                    findings.append(Finding(ERROR, "T-CONSOLE", where,
                                            f"console error(s): {cerr[:3]}"))
            browser.close()

    if json_out:
        _write_json(json_out, {"mode": "server", "health": health,
                               "screens": len(screens), "findings": _findings_json(findings)})
    _report(findings, "test_run.py --server",
            f"server + {len(screens)} screen(s) healthy, reachability clean — {reg_path}")


def run_explore(reg_path, json_out, attach=None):
    reg = _load_json(reg_path)
    base_dir = os.path.dirname(os.path.abspath(reg_path))
    screens = [s for s in (reg.get("screens") or []) if isinstance(s, dict)]
    sids = [s.get("id") for s in screens]
    sid_set = set(sids)

    per_screen = {}   # sid -> [(attr, target)]
    actions = {}      # sid -> [data-action, ...]
    edges = []        # (src, attr, target)
    for s in screens:
        sid = s.get("id")
        body = _body_text(s, base_dir)
        tgts = _extract_targets(body)
        per_screen[sid] = tgts
        actions[sid] = _extract_actions(body)
        for attr, val in tgts:
            edges.append((sid, attr, val))

    comp_edges = []   # (component-id, attr, target)
    for c in (reg.get("components") or []):
        if not isinstance(c, dict):
            continue
        for attr, val in _extract_targets(_body_text(c, base_dir)):
            comp_edges.append((c.get("id"), attr, val))

    all_edges = edges + comp_edges
    broken = [(src, attr, val) for (src, attr, val) in all_edges if val and val not in sid_set]
    dead_ends = [sid for sid in sids if not per_screen.get(sid)]
    targeted = {val for (_, _, val) in all_edges if val in sid_set}
    first = sids[0] if sids else None
    unreachable = [sid for sid in sids if sid != first and sid not in targeted]

    tested_dest = set()
    for _story, _sc, test in _iter_test_scenarios(reg):
        for exp in (test.get("expect") or []):
            if isinstance(exp, dict) and "screen" in exp:
                tested_dest.add(exp["screen"])
        for step in (test.get("steps") or []):
            if isinstance(step, dict) and step.get("do") == "nav" and step.get("target"):
                tested_dest.add(step["target"])
    untested = [(src, attr, val) for (src, attr, val) in edges
                if val in sid_set and val not in tested_dest]

    # ── human report ──────────────────────────────────────────────────────────
    print(f"pb-test · explore — {reg_path}")
    print(f"  screens ({len(sids)}): {', '.join(sids) if sids else '(none)'}")
    print("  interactive targets:")
    for sid in sids:
        tgts = per_screen.get(sid) or []
        acts = actions.get(sid) or []
        bits = [f"{a}→{v}" for a, v in tgts] + [f"action:{a}" for a in acts]
        print(f"    {sid}: {', '.join(bits) if bits else '(none — dead-end)'}")
    if broken:
        print("  ⚠ broken links (target is not a screen):")
        for src, attr, val in broken:
            print(f"    {src}: {attr}=\"{val}\" → no such screen")
    else:
        print("  reachability: all navigation targets resolve to a screen ✓")
    print(f"  dead-ends (no outgoing navigation): {', '.join(dead_ends) if dead_ends else '(none)'}")
    print(f"  unreachable (never a navigation target): {', '.join(unreachable) if unreachable else '(none)'}")
    if untested:
        print("  untested transitions (no functional test lands on the target):")
        for src, attr, val in untested:
            print(f"    {src} --{attr}--> {val}")
    else:
        print("  untested transitions: (none — every reachable target has a test, or no tests defined)")

    if json_out:
        _write_json(json_out, {
            "mode": "explore",
            "screens": sids,
            "transitions": [{"from": s, "attr": a, "to": v} for (s, a, v) in edges],
            "componentTransitions": [{"component": s, "attr": a, "to": v} for (s, a, v) in comp_edges],
            "brokenLinks": [{"from": s, "attr": a, "to": v} for (s, a, v) in broken],
            "deadEnds": dead_ends,
            "unreachable": unreachable,
            "untestedTransitions": [{"from": s, "attr": a, "to": v} for (s, a, v) in untested],
        })
    sys.exit(0)  # explore is report-only


# ─────────────────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────────────────
def run(argv=None):
    ap = argparse.ArgumentParser(
        prog="test_run.py",
        description="Playwright-backed prototype test runner (functional / roles / server / explore).")
    ap.add_argument("registry", help="path to registry.json")
    ap.add_argument("--functional", action="store_true", help="run scenario .test blocks (default)")
    ap.add_argument("--roles", action="store_true", help="verify meta.roles screen/element gating")
    ap.add_argument("--server", action="store_true", help="server health + per-screen render + reachability")
    ap.add_argument("--explore", action="store_true", help="print a reachability / dead-end / untested report")
    ap.add_argument("--story", default=None, help="limit --functional to one story (id or title)")
    ap.add_argument("--json", dest="json_out", default=None, help="write a machine-readable result JSON")
    # TRANSPORT, not a mode (D-27). `--server` is and stays a MODE (server health + per-screen
    # render + reachability); repurposing it into a transport flag would be a repurpose-in-place,
    # which AGENTS.md forbids. `--attach` is the transport the docs were really describing: it
    # composes with every mode instead of replacing one, and it never boots a second preview.
    ap.add_argument("--attach", nargs="?", const="", default=None, metavar="URL",
                    help="reuse an already-running /pb:preview server instead of booting a headless "
                         "one; bare --attach discovers it from .claude/launch.json or 127.0.0.1")
    args = ap.parse_args(argv)

    reg_path = os.path.abspath(args.registry)
    # Mode and transport are independent: any mode may be combined with --attach.
    attach = _resolve_attach(args.attach, reg_path) if args.attach is not None else None

    # Mode precedence: explore > server > roles > functional (the default).
    if args.explore:
        run_explore(reg_path, args.json_out, attach=attach)
    elif args.server:
        run_server(reg_path, args.json_out, attach=attach)
    elif args.roles:
        run_roles(reg_path, args.json_out, attach=attach)
    else:
        run_functional(reg_path, args.story, args.json_out, attach=attach)


if __name__ == "__main__":
    run()
