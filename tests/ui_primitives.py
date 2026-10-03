#!/usr/bin/env python3
"""
ui_primitives.py — the shared UI primitives of both shells, measured in a browser (round 3 · wave A).

Seven things used to exist as several copies, or as none. Each is now one implementation in
pb/template/runtime.js (+ chrome.css), composed by every page of the prototype and the design-system site:

  1. pbDisclosure   one expand/collapse. Multi-open by default, a 20px chevron, aria-expanded /
                    aria-controls, Enter / Space / arrows, "Expand all", open state that survives a re-render
  2. pbFilterBar    search · chips · quick toggles · Clear · "N of M" · slot. Clear sits right after the last
                    chip and exists only while something is filtered. The prototype's own Logic / IA / Test
                    Cases bars are now this component, behaviour unchanged
  3. toasts         the tool's toast (pbUiToast, bottom-right, tones) and the product's (pbToast, bottom-centre,
                    the PROJECT's tokens) never overlap
  4. canvas tokens  diagram colours as light-dark() pairs, pbCanvasPalette(), the `pb:themechange` event
  5. pbRichText     escape first; then blocks, marks, numbers — safe, and unbalanced marks stay literal
  6. type + space   --pb-t-xl / --pb-t-2xl / --pb-s7 / --pb-lh*, and the .pb-head title block
  7. reviewer items pbUse's function replacer; the read-only Project settings lists all three fields, quoted

Both pages are rendered from a copy of the golden fixture, carrying rules and jobs of this test's own,
into a temp dir. The
primitives are exercised on a stage the test builds, on BOTH sites; the toast and the adapters are
the prototype's.

Usage:  .venv/bin/python tests/ui_primitives.py
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright not installed (pip install playwright && playwright install chromium)")
    sys.exit(2)

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def _load(stem, path):
    spec = importlib.util.spec_from_file_location(stem, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[stem] = m
    spec.loader.exec_module(m)
    return m


render = _load("render", os.path.join(TOOLS, "render.py"))
# The golden fixture has no rules and no jobs; the Logic and IA bars need both, so the test adds its own
# (a superseded rule among them, which the bar must hide and not count), and the tokens §3's toast reads.
RULES = [
    {"id": "session-timeout", "title": "A session ends after thirty idle minutes", "kind": "constraint",
     "summary": "Idle sessions expire after thirty minutes without input."},
    {"id": "password-length", "title": "Passwords are at least twelve characters", "kind": "constraint",
     "summary": "Registration refuses a shorter password with an inline message."},
    {"id": "login-landing", "title": "Signing in lands on the dashboard", "kind": "decision",
     "summary": "After signing in, everyone arrives on the dashboard.",
     "decision": {"question": "Dashboard or the last page?", "options": ["Dashboard", "Last page"], "chose": "Dashboard",
                  "why": "Predictable for every role."}},
    {"id": "order-lifecycle", "title": "An order moves from draft to placed to shipped", "kind": "state-machine",
     "summary": "Orders follow one lifecycle.",
     "states": [{"key": "draft", "label": "Draft"}, {"key": "placed", "label": "Placed"}, {"key": "shipped", "label": "Shipped"}],
     "transitions": [["draft", "placed"], ["placed", "shipped"]]},
    {"id": "member-access", "title": "Only admins invite members", "kind": "matrix", "summary": "Permissions by role.",
     "blocks": [{"type": "matrix", "rows": ["Invite"], "cols": ["admin", "member"], "cells": {"Invite": {"admin": True, "member": False}}}]},
    {"id": "guest-readonly", "title": "Guests see a read-only dashboard", "kind": "decision",
     "summary": "Guests browse without editing.", "decision": {"chose": "read-only", "why": "ASSUMPTION: nobody objected."}},
    {"id": "nav-four-tabs", "title": "Navigation uses four tabs", "kind": "decision", "status": "superseded",
     "supersededOn": "2026-09-28", "summary": "Superseded by three tabs."},
]


def build_project(tmp):
    """A copy of the golden project carrying this test's rules and jobs."""
    proj = os.path.join(tmp, "proj")
    shutil.copytree(GOLDEN, proj)
    path = os.path.join(proj, "registry.json")
    reg = json.load(open(path, encoding="utf-8"))
    screens = [s["id"] for s in reg["screens"]]
    roles = [r["id"] for r in reg["meta"].get("roles", [])] or ["member"]
    base = {"when": "something happens", "want": "to do the thing", "so": "the outcome follows"}
    ia = reg.setdefault("ia", {})
    ia["rules"] = RULES
    ia["jobs"] = [dict(base, id="jA", priority="P0", roles=[roles[0]], screens=screens[:1]),
                  dict(base, id="jB", priority="P1", roles=roles[-1:], screens=[], want="to find the second job")]
    ia["populated"] = True
    # the tokens the product toast reads, with values the shell's fallbacks do not have, so §3 can tell
    # the project's ink, card and radius from the tool's
    reg["tokens"].update({"color-ink": {"$value": "#1d2939", "$type": "color"},
                          "color-card": {"$value": "#ffffff", "$type": "color"},
                          "radius-md": {"$value": "14px", "$type": "dimension"}})
    json.dump(reg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return path
RUNTIME = open(os.path.join(TPL, "runtime.js"), encoding="utf-8").read()
CHROME = open(os.path.join(TPL, "chrome.css"), encoding="utf-8").read()


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(s):
    m = re.match(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)", s or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# A full-viewport stage the test builds its fixtures in, above everything the page draws.
STAGE = """(html) => {
  let h = document.getElementById('pbt'); if (h) h.remove();
  h = document.createElement('div'); h.id = 'pbt';
  h.style.cssText = 'position:fixed;inset:0;z-index:5000;overflow:auto;padding:16px;background:var(--pb-page);color:var(--pb-ink);font:14px var(--pb-font)';
  h.innerHTML = html; document.body.appendChild(h);
}"""
FREEZE = "*,*::before,*::after{transition:none!important;animation:none!important}"


# ─────────────────────────────────────────── 1 · disclosure ───────────────────────────────────────────
def disclosure(pg, label):
    print(f"1 · pbDisclosure ({label})")
    pg.evaluate("window.__stage = " + STAGE)
    pg.evaluate("""() => {
      window.__ev = [];
      document.addEventListener('pb:disclosure', e => window.__ev.push([e.detail.id, e.detail.open, !!e.detail.body]));
      window.__discHTML = () => pbDiscGroupBarHTML('t')
        + ['a', 'b', 'c'].map(k => pbDiscHTML({ id: 't-' + k, summary: 'Row ' + k, body: '<p id="body-' + k + '">Body ' + k + '</p>', group: 't' })).join('')
        + pbDiscHTML({ id: 't-sec', summary: 'Section', body: '<p id="body-sec">sec</p>', level: 'section', open: true });
      window.__stage(window.__discHTML());
    }""")
    pg.wait_for_timeout(60)
    exp = lambda k: pg.get_attribute(f'#pbt [data-pb-disc="t-{k}"] > .pb-disc-t', "aria-expanded")  # noqa: E731
    check(all(exp(k) == "false" for k in "abc") and not pg.is_visible("#body-a"), "rows start closed (aria-expanded=false, body hidden)")
    check(exp("sec") == "true" and pg.is_visible("#body-sec"), "…and `open: true` starts a section open")
    pg.click('#pbt [data-pb-disc="t-a"] > .pb-disc-t')
    pg.click('#pbt [data-pb-disc="t-b"] > .pb-disc-t')
    check(exp("a") == "true" and exp("b") == "true" and pg.is_visible("#body-a") and pg.is_visible("#body-b"),
          "two rows are open at once — nothing closes a sibling")
    check(exp("c") == "false", "…and the third is untouched")
    ch = pg.evaluate("(() => { const r = document.querySelector('#pbt .pb-disc-ch').getBoundingClientRect(); return [r.width, r.height]; })()")
    check(ch[0] >= 19.9 and ch[1] >= 19.9, f"the chevron is 20px or more ({ch[0]:.0f}×{ch[1]:.0f})")
    hit = pg.evaluate("document.querySelector('#pbt .pb-disc-t').getBoundingClientRect().height")
    check(hit >= 31.9, f"…in a trigger at least {hit:.0f}px tall (≥ the 32px hit target)")
    ids = pg.evaluate("""() => [...document.querySelectorAll('#pbt .pb-disc')].every(r => {
      const t = r.querySelector(':scope > .pb-disc-t'), b = r.querySelector(':scope > .pb-disc-b');
      return t.getAttribute('aria-controls') === b.id && document.getElementById(b.id) === b && t.tagName === 'BUTTON'; })""")
    check(ids, "every trigger is a <button> whose aria-controls names its body")
    rot = pg.evaluate("""() => { const m = new DOMMatrix(getComputedStyle(document.querySelector('#pbt [data-pb-disc="t-a"] .pb-disc-ch')).transform);
      const c = new DOMMatrix(getComputedStyle(document.querySelector('#pbt [data-pb-disc="t-c"] .pb-disc-ch')).transform);
      return [Math.round(Math.atan2(m.b, m.a) * 180 / Math.PI), Math.round(Math.atan2(c.b, c.a) * 180 / Math.PI)]; }""")
    check(rot == [90, 0], f"the chevron turns a quarter when open ({rot[0]}° open, {rot[1]}° closed)")
    pg.emulate_media(reduced_motion="reduce")
    dur = pg.evaluate("getComputedStyle(document.querySelector('#pbt .pb-disc-ch')).transitionDuration")
    pg.emulate_media(reduced_motion="no-preference")
    check(dur in ("0s", "0ms"), f"…and under reduced motion it does not animate ({dur})")
    # keyboard: the trigger is a button, so Enter and Space are its own; arrows walk the list
    pg.focus('#pbt [data-pb-disc="t-a"] > .pb-disc-t')
    pg.keyboard.press("Enter")
    check(exp("a") == "false", "Enter on a trigger toggles it")
    pg.keyboard.press("Space")
    check(exp("a") == "true", "Space toggles it back")
    focused = lambda: pg.evaluate("document.activeElement.parentElement.getAttribute('data-pb-disc')")  # noqa: E731
    pg.keyboard.press("ArrowDown")
    d1 = focused()
    pg.keyboard.press("ArrowDown")
    d2 = focused()
    pg.keyboard.press("ArrowUp")
    d3 = focused()
    pg.keyboard.press("End")
    d4 = focused()
    pg.keyboard.press("Home")
    d5 = focused()
    check([d1, d2, d3, d4, d5] == ["t-b", "t-c", "t-b", "t-c", "t-a"],
          f"↓ ↑ End Home move between the group's triggers ({[d1, d2, d3, d4, d5]})")
    check(exp("a") == "true" and exp("b") == "true", "…and moving focus opens nothing")
    ev = pg.evaluate("window.__ev")
    check(["t-a", True, True] in ev and ["t-a", False, True] in ev, f"`pb:disclosure` fires with {{id, open, body}} ({len(ev)} events)")
    # Expand all / Collapse all
    bar = lambda: pg.inner_text("#pbt [data-pb-disc-all]").strip()  # noqa: E731
    check(bar() == "Expand all", f"the group bar offers Expand all while any is closed ({bar()!r})")
    pg.click("#pbt [data-pb-disc-all]")
    check(all(exp(k) == "true" for k in "abc") and bar() == "Collapse all" and exp("sec") == "true",
          "Expand all opens the group — and only the group — and the label flips")
    pg.click("#pbt [data-pb-disc-all]")
    check(all(exp(k) == "false" for k in "abc") and bar() == "Expand all", "Collapse all closes it and flips back")
    pg.click('#pbt [data-pb-disc="t-a"] > .pb-disc-t')
    pg.click('#pbt [data-pb-disc="t-b"] > .pb-disc-t')
    pg.click('#pbt [data-pb-disc="t-c"] > .pb-disc-t')
    check(bar() == "Collapse all", "…and the label follows the rows, not the clicks on the bar")
    # a filtered-out row is not part of "all"
    pg.evaluate("document.querySelector('#pbt [data-pb-disc=\"t-c\"]').hidden = true")
    pg.click("#pbt [data-pb-disc-all]")
    check(exp("a") == "false" and exp("b") == "false" and pg.evaluate("pbDiscIsOpen('t-c')") is True,
          "Collapse all leaves a row a filter hid exactly as it was")
    # open state survives a re-render
    pg.evaluate("document.querySelector('#pbt [data-pb-disc=\"t-c\"]').hidden = false")
    pg.click('#pbt [data-pb-disc="t-a"] > .pb-disc-t')
    pg.click('#pbt [data-pb-disc="t-sec"] > .pb-disc-t')
    pg.evaluate("window.__stage(window.__discHTML())")
    pg.wait_for_timeout(60)
    check(exp("a") == "true" and exp("sec") == "false" and pg.is_visible("#body-a") and not pg.is_visible("#body-sec"),
          "a re-render restores what the viewer chose — including a default-open section they closed")
    # …and the data-preserve verb carries it too, with the remembered state wiped
    pg.evaluate("""() => { pbPreserve(() => { PB_DISC_STATE.clear(); window.__stage(window.__discHTML()); }); }""")
    pg.wait_for_timeout(60)
    check(exp("a") == "true" and exp("c") == "true", "pbPreserve() restores a disclosure on its own (data-preserve=\"disc\")")
    # an awkward id
    pg.evaluate("""() => window.__stage(['x"y', '__proto__', "o'k", 'a b'].map((id, i) => pbDiscHTML({ id, summary: 'S' + i, body: '<p>B' + i + '</p>' })).join(''))""")
    pg.wait_for_timeout(40)
    pg.click("#pbt .pb-disc >> nth=0 >> .pb-disc-t")
    pg.click("#pbt .pb-disc >> nth=1 >> .pb-disc-t")
    st = pg.evaluate("""() => [pbDiscIsOpen('x"y'), pbDiscIsOpen('__proto__'), pbDiscIsOpen("o'k"),
      [...document.querySelectorAll('#pbt .pb-disc')].map(r => r.classList.contains('is-open'))]""")
    check(st[0] is True and st[1] is True and st[2] is False and st[3] == [True, True, False, False],
          "ids with quotes, a space or the name of an Object.prototype key are all just keys")
    pg.evaluate("PB_DISC_STATE.clear()")


# ─────────────────────────────────────────── 2 · filter bar ───────────────────────────────────────────
FB_SETUP = """() => {
  window.__fev = [];
  document.addEventListener('pb:filter', e => { if (e.detail.id === 'tf') window.__fev.push(e.detail); });
  window.__esc = 0;
  document.addEventListener('keydown', e => { if (e.key === 'Escape') window.__esc++; });
  const rows = [['Alpha rule', 'open', 'core', 1], ['Beta rule', 'settled', 'core ui', 0], ['Gamma note', 'open', 'ui', 0],
                ['Delta rule', 'superseded', 'core', 1], ['Epsilon note', 'settled', 'ui', 0], ['Zeta rule', 'open', 'core ui', 0],
                ['Eta rule', 'settled', 'core', 0], ['Theta note', 'open', 'ui', 1]];
  window.__fbCfg = { id: 'tf', placeholder: 'Search things', label: 'Filter things', countLabel: 'things',
    chips: [{ id: 'status', label: 'Status', options: [{ value: 'open', label: 'Open', count: 4 }, { value: 'settled', label: 'Settled', count: 3 }, { value: 'superseded', label: 'Superseded', count: 1 }] },
            { id: 'kind', label: 'Kind', options: [{ value: 'core', label: 'Core', count: 5 }, { value: 'ui', label: 'UI', count: 5 }] }],
    quick: [{ id: 'unhandled', label: 'Not handled', count: 3 }],
    slot: '<button type="button" id="slot-btn" class="pb-btn pb-btn--ghost pb-btn--sm">Expand all</button>' };
  window.__fbHTML = () => pbFilterBar(window.__fbCfg) + '<div id="tf-list">'
    + rows.map(r => '<div class="it" data-status="' + r[1] + '" data-kind="' + r[2] + '" data-un="' + r[3] + '">' + r[0] + '</div>').join('') + '</div>' + pbFilterNoneHTML('tf');
  window.__fbItems = () => [...document.querySelectorAll('#tf-list .it')].map(el => ({ el, text: el.textContent,
    facets: { status: el.dataset.status, kind: el.dataset.kind.split(' ') }, quick: { unhandled: el.dataset.un === '1' } }));
  window.__stage(window.__fbHTML());
  return pbFilterApply('tf', window.__fbItems);
}"""


def filter_bar(pg, label):
    print(f"2 · pbFilterBar ({label})")
    pg.evaluate("window.__stage = " + STAGE)
    n = pg.evaluate(FB_SETUP)
    shown = lambda: pg.evaluate("[...document.querySelectorAll('#tf-list .it')].filter(e => !e.hidden).map(e => e.textContent.split(' ')[0])")  # noqa: E731
    count = lambda: pg.inner_text("#pbt .pb-fbar-cnt").strip()  # noqa: E731
    clear = '#pbt [data-pb-fclear="tf"]'
    check(n == 8 and count() == "8 of 8 things", f"it filters nothing at first and says so ({count()!r})")
    order = pg.evaluate("""() => {
      const q = s => document.querySelector('#pbt ' + s);
      const seq = [q('.pb-fbar-q'), q('[data-pb-chip="status"]'), q('[data-pb-chip="kind"]'), q('[data-pb-quick="unhandled"]'),
                   q('[data-pb-fclear]'), q('.pb-fbar-grow'), q('.pb-fbar-cnt'), q('#slot-btn')];
      return seq.map((e, i) => i === 0 ? true : !!(seq[i - 1].compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)); }""")
    check(all(order), f"DOM order: search → chips → quick toggle → Clear → spacer → count → slot ({order})")
    check(pg.get_attribute(clear, "hidden") is not None and not pg.is_visible(clear), "Clear is hidden while nothing is filtered")
    pg.fill("#pbt input[data-pb-fq]", "alpha")
    check(shown() == ["Alpha"] and count() == "1 of 8 things", f"typing filters ({shown()}, {count()!r})")
    check(pg.is_visible(clear), "…and Clear appears")
    adj = pg.evaluate("""() => { const c = document.querySelector('#pbt [data-pb-fclear]'); const p = c.previousElementSibling;
      return p && p.matches('[data-pb-quick]'); }""")
    check(adj, "…immediately after the last chip (there is nothing between the toggle and Clear)")
    last = pg.evaluate("window.__fev[window.__fev.length - 1]")
    check(last["visible"] == 1 and last["total"] == 8 and last["id"] == "tf" and last["state"]["q"] == "alpha",
          f"`pb:filter` carries {{id, visible, total, state}} ({last})")
    pg.click(clear)
    check(len(shown()) == 8 and count() == "8 of 8 things" and not pg.is_visible(clear)
          and pg.input_value("#pbt input[data-pb-fq]") == "", "Clear resets the search and hides itself")
    # chips: OR inside a chip, AND across chips
    pg.click('#pbt [data-pb-chip="status"]')
    check(pg.is_visible("#pbt .pb-pop:not([hidden])") and pg.get_attribute('#pbt [data-pb-chip="status"]', "aria-expanded") == "true",
          "a chip opens a popover of checkboxes with counts")
    pg.check('#pbt input[data-pb-opt="status"][value="open"]')
    check(len(shown()) == 4 and "Status · 1" in pg.inner_text('#pbt [data-pb-chip="status"]'), f"one value filters ({shown()}) and the chip counts it")
    pg.check('#pbt input[data-pb-opt="status"][value="superseded"]')
    check(len(shown()) == 5, f"two values in one chip are OR ({len(shown())} of 8)")
    pg.click('#pbt [data-pb-chip="kind"]')
    check(pg.evaluate("document.querySelectorAll('#pbt .pb-pop:not([hidden])').length") == 1, "only one popover is open at a time")
    pg.check('#pbt input[data-pb-opt="kind"][value="ui"]')
    check(shown() == ["Gamma", "Zeta", "Theta"], f"chips are AND-ed ({shown()})")
    # quick toggle
    pg.click('#pbt [data-pb-quick="unhandled"]')
    check(pg.get_attribute('#pbt [data-pb-quick="unhandled"]', "aria-pressed") == "true" and shown() == ["Theta"],
          f"a quick toggle is aria-pressed and AND-ed ({shown()})")
    pg.click('#pbt [data-pb-quick="unhandled"]')
    check(pg.get_attribute('#pbt [data-pb-quick="unhandled"]', "aria-pressed") == "false" and len(shown()) == 3, "…and presses back out")
    # Esc spends itself on the popover; outside press closes
    pg.click('#pbt [data-pb-chip="kind"]')
    esc0 = pg.evaluate("window.__esc")
    pg.keyboard.press("Escape")
    check(pg.evaluate("document.querySelectorAll('#pbt .pb-pop:not([hidden])').length") == 0
          and pg.evaluate("document.activeElement.getAttribute('data-pb-chip')") == "kind",
          "Esc closes the popover and returns focus to its chip")
    check(pg.evaluate("window.__esc") == esc0, "…and never reaches a page-level Esc handler")
    pg.click('#pbt [data-pb-chip="status"]')
    pg.mouse.click(5, 5)
    check(pg.evaluate("document.querySelectorAll('#pbt .pb-pop:not([hidden])').length") == 0, "a press outside closes it")
    pg.click('#pbt [data-pb-chip="status"]')
    pg.keyboard.press("ArrowDown")
    check(pg.evaluate("document.activeElement.matches('input[data-pb-opt]')"), "↓ walks the checkboxes")
    check(pg.evaluate("pbFilterPopIsOpen()") is True, "pbFilterPopIsOpen() says a popover is open")
    pg.evaluate("window.__stage('<p>the bar was re-rendered away</p>')")
    check(pg.evaluate("pbFilterPopIsOpen()") is False, "…and stops saying so once its bar is gone from the page")
    pg.evaluate("window.__stage(window.__fbHTML()); pbFilterApply('tf', window.__fbItems)")
    # nothing matches
    pg.fill("#pbt input[data-pb-fq]", "zzzzz")
    none = pg.inner_text("#pbt [data-pb-fnone]")
    check(count().startswith("0 of 8") and "No things match" in none and "zzzzz" in none, f"an empty result says what failed ({none!r})")
    pg.click("#pbt [data-pb-fnone] [data-pb-fclear]")
    check(len(shown()) == 8 and pg.evaluate("document.querySelector('#pbt [data-pb-fnone]').hidden"), "…and its own Clear filters undoes it")
    # state per bar id survives a re-render
    pg.fill("#pbt input[data-pb-fq]", "rule")
    pg.click('#pbt [data-pb-chip="status"]')
    pg.check('#pbt input[data-pb-opt="status"][value="settled"]')
    pg.click('#pbt [data-pb-quick="unhandled"]')
    pg.keyboard.press("Escape")
    before = shown()
    pg.evaluate("window.__stage(window.__fbHTML())")
    fresh = pg.evaluate("""() => ({ q: document.querySelector('#pbt input[data-pb-fq]').value, chip: document.querySelector('#pbt [data-pb-chip="status"] .cl').textContent,
      pressed: document.querySelector('#pbt [data-pb-quick]').getAttribute('aria-pressed'), clear: !document.querySelector('#pbt [data-pb-fclear]').hidden,
      checked: document.querySelector('#pbt input[data-pb-opt="status"][value="settled"]').checked })""")
    check(fresh == {"q": "rule", "chip": "Status · 1", "pressed": "true", "clear": True, "checked": True},
          f"a re-rendered bar comes back as it was left ({fresh})")
    pg.evaluate("pbFilterApply('tf', window.__fbItems)")
    check(shown() == before and count().endswith("of 8 things"), f"…and one pbFilterApply() puts the rows back ({shown()})")
    snap = pg.evaluate("pbFilterState('tf')")
    check(snap == {"q": "rule", "sel": {"status": ["settled"]}, "quick": {"unhandled": True}}, f"pbFilterState() reads it back ({snap})")
    pg.evaluate("pbFilterClear('tf')")
    check(len(shown()) == 8 and pg.evaluate("pbFilterState('tf')") == {"q": "", "sel": {}, "quick": {}}
          and pg.input_value("#pbt input[data-pb-fq]") == "", "pbFilterClear() resets state and the controls from code")
    # a disabled bar
    pg.evaluate("window.__stage(pbFilterBar({ id: 'off', placeholder: 'Search', label: 'Filter', off: 'Nothing to filter yet',"
                " chips: [{ id: 'a', label: 'A', options: [] }], quick: [{ id: 'q', label: 'Q' }] }))")
    off = pg.evaluate("""() => { const b = document.querySelector('#pbt .pb-fbar'); return { off: b.classList.contains('is-off'),
      dis: document.querySelector('#pbt input[data-pb-fq]').disabled, why: b.querySelector('.pb-fbar-why').textContent,
      cnt: b.querySelector('.pb-fbar-cnt').textContent, applied: pbFilterApply('off', []) }; }""")
    check(off == {"off": True, "dis": True, "why": "Nothing to filter yet", "cnt": "0 of 0", "applied": 0},
          f"`off` draws a disabled bar with its reason ({off})")


# ─────────────────────────────────────── 2b · the prototype's own bars ───────────────────────────────────────
def prototype_bars(pg):
    print("2b · the prototype's Logic / IA / Test Cases bars are this component (behaviour unchanged)")
    pg.evaluate("document.getElementById('pbt') && document.getElementById('pbt').remove()")
    pg.evaluate("setMetaView('flow'); pbSetUxView('logic');")
    pg.wait_for_timeout(300)
    bar = '.pb-fbar[data-fbar="logic"]'
    # a superseded rule (data-fb-archived) is hidden until "Show superseded": N of M counts the live rules
    rows = lambda: pg.evaluate("document.querySelectorAll('.pb-scan-tr[data-fb-list=\"logic\"]:not([data-fb-archived])').length")  # noqa: E731
    total = rows()
    visible = lambda: pg.evaluate("Array.from(document.querySelectorAll('.pb-scan-tr[data-fb-list=\"logic\"]')).filter(r => !r.hidden).length")  # noqa: E731
    check(total == len(RULES) - 1, f"the Logic tab lists the live rules, the superseded one held back ({total})")
    order = pg.evaluate("""() => {
      const q = s => document.querySelector('.pb-fbar[data-fbar="logic"] ' + s);
      const seq = [q('.pb-fbar-q'), q('[data-pb-chip="status"]'), q('[data-pb-chip="kind"]'), q('[data-pb-fclear]'), q('.pb-fbar-cnt'), q('[data-fb-all]')];
      return seq.map((e, i) => !e ? 'missing:' + i : i === 0 ? true : !!(seq[i - 1].compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)); }""")
    check(all(o is True for o in order), f"search → Status → Kind → Clear → count → Expand all ({order})")
    check(not pg.is_visible(bar + " [data-pb-fclear]"), "Clear is hidden until something is filtered")
    check(pg.inner_text(bar + " .pb-fbar-cnt").strip().startswith(f"{total} of {total}"), "the count says N of N")
    first = pg.evaluate("document.querySelector('.pb-scan-tr[data-fb-list=\"logic\"]').getAttribute('data-fb-hay').split(/\\s+/).filter(w => w.length > 5)[0]")
    pg.fill(bar + " input[data-pb-fq]", first)
    v = visible()
    check(0 < v < total and pg.is_visible(bar + " [data-pb-fclear]") and pg.inner_text(bar + " .pb-fbar-cnt").strip().startswith(f"{v} of {total}"),
          f"typing {first!r} filters the rules ({v} of {total}) and shows Clear")
    pg.click(bar + " [data-pb-fclear]")
    check(visible() == total, "Clear brings every rule back")
    # rows are multi-open, and a row the filter hides keeps its open state (it is not "closed by being hidden")
    key = pg.evaluate("document.querySelector('.pb-scan-tr[data-fb-list=\"logic\"]').getAttribute('data-key')")
    pg.click(f'.pb-scan-tr[data-fb-list="logic"][data-key="{key}"] > .pb-disc-t')
    opened = pg.evaluate(f"document.querySelector('.pb-scan-tr[data-fb-list=\"logic\"][data-key=\"{key}\"]').classList.contains('is-open')")
    pg.fill(bar + " input[data-pb-fq]", "zzzzzzzz")
    hidden_open = pg.evaluate(f"(r => r.hidden && r.classList.contains('is-open'))(document.querySelector('.pb-scan-tr[data-fb-list=\"logic\"][data-key=\"{key}\"]'))")
    check(opened and hidden_open, "an open row that the filter hides stays open (multi-open: nothing closes a row but the viewer)")
    check("No rules match" in pg.inner_text('[data-pb-fnone="logic"]'), "…and the empty message names the noun")
    pg.click(bar + " [data-pb-fclear]")
    back = pg.evaluate(f"(r => !r.hidden && r.classList.contains('is-open'))(document.querySelector('.pb-scan-tr[data-fb-list=\"logic\"][data-key=\"{key}\"]'))")
    check(back, "…and is still open when the filter is cleared")
    # a chip works through the shell's data-fb-<facet> attributes
    pg.click(bar + ' [data-pb-chip="status"]')
    pg.locator(bar + ' input[data-pb-opt="status"]').first.check()
    v = visible()
    check(0 < v <= total and pg.inner_text(bar + ' [data-pb-chip="status"]').strip().endswith("1"), f"a Status chip filters by data-fb-status ({v} of {total})")
    pg.keyboard.press("Escape")
    # state survives the tab being rebuilt
    pg.evaluate("pbSetUxView('ia'); pbSetUxView('logic')")
    pg.wait_for_timeout(250)
    check(pg.inner_text(bar + ' [data-pb-chip="status"]').strip().endswith("1") and visible() == v,
          "…and survives leaving the tab and coming back")
    pg.evaluate("pbFilterClear('logic')")
    pg.evaluate("pbSetUxView('ia')")
    pg.wait_for_timeout(250)
    ia = '.pb-fbar[data-fbar="ia"]'
    check(pg.is_visible(ia) and not pg.is_visible(ia + " [data-pb-fclear]"), "the IA bar is the same component, Clear hidden")


# ─────────────────────────────────────────── 3 · toasts ───────────────────────────────────────────
def toasts(pg):
    print("3 · the tool toast and the product toast")
    pg.evaluate("document.getElementById('pbt') && document.getElementById('pbt').remove()")
    pg.add_style_tag(content=FREEZE)
    for w, h in ((1280, 800), (1024, 700), (900, 700), (390, 800)):
        pg.set_viewport_size({"width": w, "height": h})
        pg.evaluate("document.querySelectorAll('.proto-toast').forEach(e => e.remove())")
        pg.evaluate("pbToast('Product says hello'); pbUiToast('Tool says hi', { note: 'with a note' });")
        pg.wait_for_selector(".proto-toast.in")
        pg.wait_for_selector("#pb-ui-toast.is-on")
        pg.wait_for_timeout(60)
        b = pg.evaluate("""() => { const r = e => { const x = document.querySelector(e).getBoundingClientRect(); return [x.left, x.top, x.right, x.bottom]; };
          return { p: r('.proto-toast'), t: r('#pb-ui-toast'), w: innerWidth }; }""")
        p, t = b["p"], b["t"]
        apart = p[2] <= t[0] or t[2] <= p[0] or p[3] <= t[1] or t[3] <= p[1]
        check(apart, f"{w}px: the two toasts do not overlap (product {[round(x) for x in p]}, tool {[round(x) for x in t]})")
        if w >= 1100:
            check(abs((p[0] + p[2]) / 2 - w / 2) < 3, f"{w}px: the product toast is bottom-centre")
            check(t[2] > w - 40 and t[0] > w / 2, f"{w}px: the tool toast is bottom-right")
    pg.set_viewport_size({"width": 1280, "height": 800})
    pg.evaluate("document.querySelectorAll('.proto-toast').forEach(e => e.remove())")
    pg.evaluate("pbToast('Product says hello')")
    pg.wait_for_selector(".proto-toast.in")
    cs = pg.evaluate("""() => { const t = document.querySelector('.proto-toast'), c = getComputedStyle(t);
      return { bg: c.backgroundColor, fg: c.color, scoped: !!t.closest('.pb-product'), radius: c.borderTopLeftRadius }; }""")
    check(cs["bg"] == "rgb(29, 41, 57)" and cs["fg"] == "rgb(255, 255, 255)" and cs["scoped"],
          f"the product toast speaks in the PROJECT's tokens (ink on card), inside .pb-product ({cs['bg']} on {cs['fg']})")
    check(cs["radius"] == "14px", f"…including its radius ({cs['radius']})")
    tone = pg.evaluate("""() => { const out = {}; const probe = document.createElement('i'); document.documentElement.appendChild(probe);
      const res = n => { probe.style.color = 'var(--pb-' + n + ')'; return getComputedStyle(probe).color; };
      for (const k of ['pass', 'fail']) { pbUiToast('Run ' + k, { tone: k }); const e = document.getElementById('pb-ui-toast');
        out[k] = { cls: e.classList.contains('pb-toast--' + k), color: getComputedStyle(e).color, want: res(k), text: e.textContent }; }
      pbUiToast('Plain'); const e = document.getElementById('pb-ui-toast'); out.plain = { cls: [...e.classList].join(' '), small: e.querySelector('small') };
      pbUiToast('Old signature', 'a note'); out.note = e.querySelector('small') && e.querySelector('small').textContent;
      probe.remove(); return out; }""")
    check(tone["pass"]["cls"] and tone["pass"]["color"] == tone["pass"]["want"], "tone 'pass' is the tool's pass colour")
    check(tone["fail"]["cls"] and tone["fail"]["color"] == tone["fail"]["want"], "tone 'fail' is the tool's fail colour")
    check("pb-toast--" not in tone["plain"]["cls"] and tone["plain"]["small"] is None, "a plain toast carries neither tone nor note (the tone is reset)")
    check(tone["note"] == "a note", "the old `pbUiToast(msg, 'note')` signature still works")
    esc = pg.evaluate("pbUiToast('<b>x</b>', { note: '<i>y</i>' }); document.getElementById('pb-ui-toast').innerHTML")
    check("<b>" not in esc and "&lt;b&gt;" in esc and "&lt;i&gt;" in esc, "message and note are escaped")


# ─────────────────────────────────────────── 4 · canvas tokens ───────────────────────────────────────────
def canvas(pg, label):
    print(f"4 · canvas tokens, pbCanvasPalette, pb:themechange ({label})")
    pal = {}
    for t in ("light", "dark"):
        pg.evaluate("t => window.pbSetTheme(t)", t)
        pal[t] = pg.evaluate("pbCanvasPalette()")

    def flat(p):
        out = {"canvas.bg": p["canvas"]["bg"], "canvas.grid": p["canvas"]["grid"]}
        for k, v in p["node"].items():
            if k in ("start", "process", "decision", "screen", "external"):
                for f in ("fill", "stroke", "text"):
                    out[f"node.{k}.{f}"] = v[f]
        for k, v in p["edge"].items():
            out[f"edge.{k}"] = v
        for k, v in p["erd"].items():
            out[f"erd.{k}"] = v
        return out
    L, D = flat(pal["light"]), flat(pal["dark"])
    same = sorted(k for k in L if L[k] == D[k])
    check(len(L) == 28 and not same and all(v.startswith("rgb") for v in list(L.values()) + list(D.values())),
          f"all {len(L)} canvas values resolve, to a colour, and differ between light and dark (same: {same})")
    check(pal["light"]["dark"] is False and pal["dark"]["dark"] is True, "the palette says which theme it resolved")
    nodes = pal["light"]["node"]
    check(sorted(nodes) == ["decision", "external", "process", "screen", "start"],
          f"the palette's node keys are exactly the legend's five names, and carry no alias for the pre-round-3 keys startEnd / input / action / sub ({sorted(nodes)})")
    legacy = pg.evaluate("typeof FLOW_NODE_PALETTE === 'undefined' ? null : { n: FLOW_NODE_PALETTE, e: PB_FLOW_EDGE_COLORS }")
    if legacy:
        want = {"start": "startEnd", "process": "input", "decision": "decision", "screen": "action", "external": "sub"}
        bad = [f"{k}.{f}" for k, old in want.items() for f in ("fill", "stroke", "text")
               if rgb(pal["light"]["node"][k][f]) != hex_rgb(legacy["n"][old][f if f != "text" else "text"])]
        bad += [k for k in ("yes", "no") if rgb(pal["light"]["edge"][k]) != hex_rgb(legacy["e"][k])]
        bad += [] if rgb(pal["light"]["edge"]["def"]) == hex_rgb(legacy["e"]["def"]) else ["def"]
        check(not bad, f"in light, every shape and edge is exactly the palette the diagram has always used ({bad})")
    else:
        print("  - (the shell no longer carries FLOW_NODE_PALETTE: the light-identity check is retired with it)")
    d = pal["dark"]
    worst = min(contrast(rgb(v["text"]), rgb(v["fill"])) for k, v in d["node"].items() if k in ("start", "process", "decision", "screen", "external"))
    check(worst >= 4.5, f"dark: every node's text clears 4.5:1 on its fill (worst {worst:.2f})")
    edge = min(contrast(rgb(v["stroke"]), rgb(d["canvas"]["bg"])) for k, v in d["node"].items() if k in ("start", "process", "decision", "screen", "external"))
    lines = min(contrast(rgb(v), rgb(d["canvas"]["bg"])) for v in d["edge"].values())
    check(edge >= 3 and lines >= 3, f"dark: node strokes ({edge:.1f}) and edges ({lines:.1f}) clear 3:1 on the paper")
    e = d["erd"]
    check(contrast(rgb(e["text"]), rgb(e["fill"])) >= 4.5 and contrast(rgb(e["headText"]), rgb(e["head"])) >= 4.5
          and contrast(rgb(e["text"]), rgb(e["rowAlt"])) >= 4.5, "dark: ERD text clears 4.5:1 on its body, its alternate row and its header")
    lt = pal["light"]
    lworst = min(contrast(rgb(v["text"]), rgb(v["fill"])) for k, v in lt["node"].items() if k in ("start", "process", "decision", "screen", "external"))
    check(lworst >= 4.5 and min(contrast(rgb(v), rgb(lt["canvas"]["bg"])) for v in lt["edge"].values()) >= 3.0,
          f"light: every node's text clears AA (4.5:1) on its fill ({lworst:.2f}; the screen blue and the yes-edge green were darkened to get there), edges ≥ 3:1 on the paper")
    # the event
    pg.evaluate("""() => { window.__tc = []; window.addEventListener('pb:themechange', e => window.__tc.push(e.detail)); }""")
    last = lambda: pg.evaluate("window.__tc[window.__tc.length - 1]")  # noqa: E731
    pg.evaluate("pbSetTheme('dark')")
    check(last() == {"theme": "dark", "dark": True}, f"pbSetTheme('dark') fires pb:themechange ({last()})")
    pg.evaluate("pbSetTheme('light')")
    check(last() == {"theme": "light", "dark": False}, f"…and 'light' ({last()})")
    n0 = pg.evaluate("window.__tc.length")
    pg.evaluate("pbUiSetTheme('dark')")
    check(pg.evaluate("window.__tc.length") == n0 + 1, "the menu's route (pbUiSetTheme) fires it exactly once")
    painted = pg.evaluate("""() => new Promise(res => { window.addEventListener('pb:themechange', () => res(pbCanvasPalette().canvas.bg), { once: true }); pbSetTheme('light'); })""")
    check(painted == pal["light"]["canvas"]["bg"], "a listener reading the palette inside the event already sees the new theme")
    pg.evaluate("pbSetTheme('system')")
    pg.emulate_media(color_scheme="light")
    pg.wait_for_timeout(80)
    n1 = pg.evaluate("window.__tc.length")
    pg.emulate_media(color_scheme="dark")
    pg.wait_for_timeout(120)
    check(pg.evaluate("window.__tc.length") == n1 + 1 and last() == {"theme": "system", "dark": True},
          f"with theme System, an OS scheme change fires it too ({last()})")
    check(pg.evaluate("pbCanvasPalette().dark") is True and pg.evaluate("pbCanvasPalette().canvas.bg") == pal["dark"]["canvas"]["bg"],
          "…and the palette follows the OS")
    pg.evaluate("pbSetTheme('light')")
    n2 = pg.evaluate("window.__tc.length")
    pg.emulate_media(color_scheme="light")
    pg.wait_for_timeout(80)
    pg.emulate_media(color_scheme="dark")
    pg.wait_for_timeout(80)
    check(pg.evaluate("window.__tc.length") == n2, "…but a pinned theme ignores the OS (no event)")
    pg.evaluate("pbSetTheme('system')")
    pg.emulate_media(color_scheme="light")


# ─────────────────────────────────────────── 5 · rich text ───────────────────────────────────────────
RT = """([s, o]) => { const d = document.createElement('div'); d.innerHTML = pbRichText(s, o || {});
  const n = sel => d.querySelectorAll(sel).length;
  return { html: d.innerHTML, text: d.textContent, bad: d.querySelectorAll('img,script,iframe,svg,a,style,object').length,
    onattr: [...d.querySelectorAll('*')].some(e => [...e.attributes].some(a => /^on/i.test(a.name))),
    strong: n('strong'), em: n('em'), mark: n('mark.pb-hl'), pos: n('.pb-pos'), neg: n('.pb-neg'), code: n('code'), num: n('b.pb-num'),
    ul: n('ul'), ol: n('ol'), li: n('li'), p: n('p'), br: n('br'), root: !!d.querySelector(':scope > .pb-rt'),
    nums: [...d.querySelectorAll('.pb-num')].map(e => e.textContent), codeText: [...d.querySelectorAll('code')].map(e => e.textContent) }; }"""


def rich_text(pg, label):
    print(f"5 · pbRichText ({label})")
    rt = lambda s, o=None: pg.evaluate(RT, [s, o])  # noqa: E731
    r = rt("<img src=x onerror=alert(1)> and <script>alert(2)</script> and <b onclick=1>x</b>")
    check(r["bad"] == 0 and not r["onattr"] and "<img src=x onerror=alert(1)>" in r["text"] and "<script>alert(2)</script>" in r["text"],
          "markup in the input is escaped: `<img onerror>` and `<script>` stay text")
    r = rt("**b** *e* _u_ ==h== {+p+} {-n-} `c`")
    check((r["strong"], r["em"], r["mark"], r["pos"], r["neg"], r["code"]) == (1, 2, 1, 1, 1, 1),
          f"each mark becomes its element/class (strong, 2×em, mark.pb-hl, .pb-pos, .pb-neg, code) ({r['html']})")
    r = rt("`**x** ==y== 98% {+z+}` after")
    check(r["codeText"] == ["**x** ==y== 98% {+z+}"] and r["strong"] == r["mark"] == r["num"] == r["pos"] == 0,
          "a code span is opaque: nothing inside it is parsed")
    r = rt("==a **b** c== and **x ==y== z**")
    check(r["mark"] == 2 and r["strong"] == 2 and "</strong></mark>" not in r["html"], "marks nest cleanly")
    r = rt("· one\n- two\n• three\n* four")
    check(r["ul"] == 1 and r["li"] == 4 and r["p"] == 0, "·  -  •  and `* ` each start a bullet — four lines, one <ul>")
    r = rt("1. one\n2) two\n3. three")
    check(r["ol"] == 1 and r["li"] == 3 and r["ul"] == 0, "`1.` and `1)` start an ordered list")
    r = rt("Intro:\n· a\n· b\n\nSecond paragraph\nsame paragraph")
    check(r["p"] == 2 and r["ul"] == 1 and r["br"] == 1 and r["root"], "blank lines split paragraphs; a bullet run after a lead-in is its own list; the wrapper is .pb-rt")
    r = rt("Up 98.7% to 11,042 users for 500.000 ₫, $12.50 — 24px, 3s, 250ms")
    check(r["nums"] == ["98.7%", "11,042", "500.000 ₫", "$12.50", "24px", "3s", "250ms"], f"numbers with units, percent and currency are .pb-num ({r['nums']})")
    r = rt("Version v2.1 on 2026-10-03, step 3, room 101, 10.2026")
    check(r["num"] == 0, "…and a bare number, a version or a date is not")
    r = rt("98% 24px", {"numbers": False})
    check(r["num"] == 0 and "98%" in r["text"], "opts.numbers:false opts out")
    for src in ("**unclosed", "==unclosed", "{+unclosed", "{-unclosed", "`unclosed", "snake_case_word and more_snake_here", "2 * 3 * 4 = 24", "_ not em _"):
        r = rt(src)
        check(r["text"] == src and not (r["strong"] or r["em"] or r["mark"] or r["pos"] or r["neg"] or r["code"]), f"unbalanced/odd marks stay literal: {src!r}")
    r = rt("việt_nam_x và *nhấn mạnh*")
    check(r["em"] == 1 and "việt_nam_x" in r["text"], "…and a Vietnamese word is a word (no em inside it)")
    check(rt("")["html"] == "" and pg.evaluate("pbRichText(null)") == "" and pg.evaluate("pbRichText(undefined, {})") == "", "empty / null / undefined → empty string")
    r = rt("a **b**\nc 98%", {"inline": True})
    check(r["root"] is False and r["strong"] == 1 and r["br"] == 1 and r["num"] == 1, "opts.inline: marks without blocks or wrapper")
    r = rt("x", {"cls": 'extra "q"'})
    check('class="pb-rt extra &quot;q&quot;"' in pg.evaluate("pbRichText('x', {cls: 'extra \"q\"'})"), "opts.cls is escaped")
    # styles, both themes
    for theme in ("light", "dark"):
        pg.evaluate("t => window.pbSetTheme(t)", theme)
        cs = pg.evaluate("""() => { const d = document.createElement('div'); d.className = 'pb-product-not';
          d.innerHTML = pbRichText('{+p+} {-n-} ==h== **98%** `c`\\n\\nsecond'); document.body.appendChild(d);
          const probe = document.createElement('i'); document.documentElement.appendChild(probe);
          const res = n => { probe.style.color = 'var(--pb-' + n + ')'; return getComputedStyle(probe).color; };
          const g = s => getComputedStyle(d.querySelector(s)); const out = {
            pos: [g('.pb-pos').color, res('pass')], neg: [g('.pb-neg').color, res('fail')], hl: [g('.pb-hl').backgroundColor, res('warn-bg')],
            num: [parseInt(g('.pb-num').fontWeight), g('.pb-num').fontVariantNumeric], ws: g('.pb-rt').whiteSpace,
            gap: parseFloat(g('p + p').marginTop), codeFont: g('.pb-rt code').fontFamily };
          d.remove(); probe.remove(); return out; }""")
        check(cs["pos"][0] == cs["pos"][1] and cs["neg"][0] == cs["neg"][1] and cs["hl"][0] == cs["hl"][1],
              f"{theme}: .pb-pos / .pb-neg / .pb-hl are --pb-pass / --pb-fail / --pb-warn-bg")
        check(cs["num"][0] >= 600 and "tabular" in cs["num"][1] and cs["ws"] == "normal" and cs["gap"] > 0 and "mono" in cs["codeFont"].lower(),
              f"{theme}: .pb-num is bold + tabular, .pb-rt is white-space:normal with a paragraph gap ({cs['gap']}px)")
    pg.evaluate("pbSetTheme('system')")


# ───────────────────────────────── 6 · type + space scale, page head ─────────────────────────────────
HEAD = """() => { window.__stage(pbHeadHTML({ title: 'Project <Summary>', meta: '<span class="pb-tag">Badge</span><span class="pb-tag">Two</span>',
    sub: 'project-summary', actions: '<button class="pb-btn">One</button><button class="pb-btn pb-btn--solid">Two</button>' })
    + pbHeadHTML({ title: 'Flush', flush: true, tag: 'h2' })); }"""


def head(pg, label):
    print(f"6 · type + space scale and .pb-head ({label})")
    tok = pg.evaluate("""() => { const c = getComputedStyle(document.documentElement); return ['--pb-t-xl', '--pb-t-2xl', '--pb-s7', '--pb-lh-tight', '--pb-lh'].map(n => c.getPropertyValue(n).trim()); }""")
    check(tok == ["1.5rem", "1.875rem", "3.5rem", "1.2", "1.5"], f"--pb-t-xl · --pb-t-2xl · --pb-s7 · --pb-lh-tight · --pb-lh ({tok})")
    pg.evaluate("window.__stage = " + STAGE)
    pg.set_viewport_size({"width": 1280, "height": 800})
    pg.evaluate(HEAD)
    m = pg.evaluate("""() => { const h = document.querySelector('#pbt .pb-head'), t = h.querySelector('.pb-head-t'), mt = h.querySelector('.pb-head-meta'),
      s = h.querySelector('.pb-head-sub'), a = h.querySelector('.pb-head-act'), main = h.querySelector('.pb-head-main');
      const cs = e => getComputedStyle(e), r = e => e.getBoundingClientRect();
      return { tag: t.tagName, title: t.textContent, fs: cs(t).fontSize, fw: cs(t).fontWeight, lh: cs(t).lineHeight,
        gapTM: r(mt).top - r(t).bottom, gapMS: r(s).top - r(mt).bottom, pad: cs(h).paddingLeft, mb: cs(h).marginBottom,
        sub: [cs(s).fontFamily, cs(s).fontSize, cs(s).color], hr: r(h).right - parseFloat(cs(h).paddingRight), ar: r(a).right,
        aTop: r(a).top, mainBottom: r(main).bottom, aW: r(a).width, hW: r(h).width,
        flush: cs(document.querySelectorAll('#pbt .pb-head')[1]).paddingLeft, flushTag: document.querySelector('#pbt .pb-head--flush .pb-head-t').tagName,
        subInk: (() => { const p = document.createElement('i'); document.documentElement.appendChild(p); p.style.color = 'var(--pb-ink-3)'; const c = getComputedStyle(p).color; p.remove(); return c; })() }; }""")
    check(m["tag"] == "H1" and m["title"] == "Project <Summary>", "the title is an h1 and is escaped text")
    check(m["fs"] == "30px" and int(m["fw"]) >= 600 and m["lh"] == "36px", f"2xl, bold, tight (1.2): {m['fs']} / {m['fw']} / {m['lh']}")
    check(abs(m["gapTM"] - 8) < 1.5 and abs(m["gapMS"] - 8) < 1.5, f"--pb-s2 between title, meta and id ({m['gapTM']:.0f}px, {m['gapMS']:.0f}px)")
    check(m["mb"] == "24px", f"--pb-s5 below the head ({m['mb']})")
    check(m["pad"] == "24px", f"the side gutter is --pb-gutter on a wide page ({m['pad']})")
    check("mono" in m["sub"][0].lower() or "menlo" in m["sub"][0].lower(), f"the id is mono ({m['sub'][0][:40]})")
    check(m["sub"][1] == "12px" and m["sub"][2] == m["subInk"], "…at t-sm in ink-3")
    check(abs(m["ar"] - m["hr"]) < 2, f"actions sit at the right edge on a wide page ({m['ar']:.0f} vs {m['hr']:.0f})")
    check(m["flush"] == "0px" and m["flushTag"] == "H2", "`flush` drops the gutter; `tag` picks the heading level")
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.evaluate(HEAD)
    n = pg.evaluate("""() => { const h = document.querySelector('#pbt .pb-head'), a = h.querySelector('.pb-head-act'), main = h.querySelector('.pb-head-main'), cs = getComputedStyle(h);
      const w = h.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      return { pad: cs.paddingLeft, aW: a.getBoundingClientRect().width, w, below: a.getBoundingClientRect().top >= main.getBoundingClientRect().bottom - 1 }; }""")
    check(n["pad"] == "16px", f"the gutter is 16px below 600px ({n['pad']})")
    check(n["below"] and abs(n["aW"] - n["w"]) < 2, f"actions drop below the title and take the full width ({n['aW']:.0f} of {n['w']:.0f}px)")
    pg.set_viewport_size({"width": 1280, "height": 800})


# ───────────────────────────────── 7 · reviewer items in runtime.js ─────────────────────────────────
def reviewer_items(pg, label):
    print(f"7 · round-2 reviewer items ({label})")
    r = pg.evaluate("""() => { window.renderCmpUiTest = () => '  <div class="x">hi</div>';
      const reg = PB_REGISTRY.components; const ids = ["a$&b", "q$1$'z", "plain"];
      ids.forEach(id => reg.push({ id, renderFn: 'renderCmpUiTest' })); PB_ORG_BY_ID_CACHE = null;
      const out = ids.map(id => pbUse(id)); ids.forEach(() => reg.pop()); PB_ORG_BY_ID_CACHE = null; return out; }""")
    check(r[0] == '  <div data-cmp="a$&amp;b" class="x">hi</div>', f"pbUse stamps an id containing `$&` verbatim ({r[0]!r})")
    check(r[1] == '  <div data-cmp="q$1$&#39;z" class="x">hi</div>', f"…and `$1` / `$'` ({r[1]!r})")
    check(r[2] == '  <div data-cmp="plain" class="x">hi</div>', "…and an ordinary id as before")
    pg.evaluate("document.querySelectorAll('dialog').forEach(d => d.remove())")
    pg.evaluate("""() => pbUiOpenSettings({ meta: { name: 'The "Final" app', designSystem: { name: 'DS "X" \\\\ y', designLink: 'https://www.figma.com/design/abc' } }, viewOnly: true })""")
    pg.wait_for_selector("#pb-settings[open]")
    cmds = pg.evaluate("[...document.querySelectorAll('#pb-settings .pb-cmd code')].map(c => c.textContent)")
    copies = pg.evaluate("[...document.querySelectorAll('#pb-settings .pb-cmd [data-pb-copy]')].map(c => c.getAttribute('data-pb-copy'))")
    check(len(cmds) == 3 and cmds[0].startswith('Set this project\'s name to "') and cmds[1].startswith('Set this project\'s design system name to "')
          and cmds[2].startswith('Set this project\'s Figma file link to "'), f"the read-only dialog lists all three fields, each as a plain sentence to paste into Claude Code ({cmds})")
    check(not any("/pb:" in c or "meta." in c for c in cmds), f"…and none hands out a made-up /pb:build syntax or a registry path ({cmds})")
    check(cmds[0] == 'Set this project\'s name to "The \\"Final\\" app"' and cmds[1] == 'Set this project\'s design system name to "DS \\"X\\" \\\\ y"',
          f"a double quote (and a backslash) in a value is escaped, so the quoted value cannot end early ({cmds[0]} · {cmds[1]})")
    check(cmds[2].endswith('link to "https://www.figma.com/design/abc"'), "…the Figma link is quoted as is")
    check(copies == cmds, "each prompt has its own copy button, carrying exactly that prompt")
    labels = pg.evaluate("[...document.querySelectorAll('#pb-settings .pb-cmd [data-pb-copy]')].map(c => c.getAttribute('aria-label'))")
    check(len(set(labels)) == 3, f"…and its own accessible name ({labels})")
    pg.evaluate("document.getElementById('pb-settings').close()")
    pg.evaluate("pbUiOpenSettings({ meta: {}, viewOnly: true })")
    pg.wait_for_selector("#pb-settings[open]")
    empty = pg.evaluate("[...document.querySelectorAll('#pb-settings .pb-cmd code')].map(c => c.textContent)")
    check(all("<" in c for c in empty), f"a project with no name / design system shows placeholders, not 'undefined' ({empty})")
    pg.evaluate("document.getElementById('pb-settings').close()")


# ───────────────────────────────── static + bare-vm checks ─────────────────────────────────
def static_checks():
    print("0 · the files")
    for tok, val in (("--pb-t-xl", "1.5rem"), ("--pb-t-2xl", "1.875rem"), ("--pb-s7", "3.5rem"), ("--pb-lh-tight", "1.2"), ("--pb-lh", "1.5")):
        check(re.search(re.escape(tok) + r":\s*" + re.escape(val) + r"\s*;", CHROME) is not None, f"chrome.css defines {tok}: {val}")
    for sel in (".pb-disc-t", ".pb-disc-ch", ".pb-disc-b", ".pb-fbar", ".pb-chip", ".pb-pop", ".pb-rt", ".pb-hl", ".pb-pos", ".pb-neg", ".pb-num",
                ".pb-head", ".pb-head-t", ".pb-head-meta", ".pb-head-sub", ".pb-head-act", ".pb-toast--pass", ".pb-toast--fail"):
        check(re.search(re.escape(sel) + r"[\s,{:.\[]", CHROME) is not None, f"chrome.css styles {sel}")
    css = re.sub(r"/\*.*?\*/", "", CHROME, flags=re.S)
    check(re.search(r"\.pb-disc-ch\s*\{[^}]*width:\s*var\(--pb-ico\)", css) is not None, "the chevron is sized by --pb-ico (20px)")
    check(re.search(r"\.pb-toast\s*\{[^}]*right:\s*var\(--pb-gutter\)", css) is not None and "left: 50%" not in re.search(r"\.pb-toast\s*\{[^}]*\}", css).group(0),
          "the tool toast is anchored bottom-right")
    proto = open(os.path.join(TPL, "prototype.html"), encoding="utf-8").read()
    check("function pbFbarChip" not in proto and "function pbFbarCheck" not in proto and ".pb-pop-opt {" not in proto,
          "the prototype no longer carries its own filter-bar implementation or CSS")
    check("function pbDiscHTML" not in proto and "function pbFilterBar" not in proto and "function pbRichText" not in proto,
          "…and the primitives live once, in runtime.js")
    node = shutil.which("node")
    if not node:
        print("  - (node not on PATH: the bare-vm load is skipped)")
        return
    prog = (
        "const vm=require('vm'),fs=require('fs');const ctx=vm.createContext({console});"
        "vm.runInContext(\"var window=this,self=this;function pbEscape(s){return String(s==null?'':s).replace(/[&<>\\\"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','\\\"':'&quot;',\\\"'\\\":'&#39;'}[c];});}"
        "var PB_REGISTRY={components:[],tokens:{}};\",ctx);"
        "vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);"
        "const r=vm.runInContext(\"JSON.stringify([typeof pbDiscHTML,typeof pbFilterBar,typeof pbRichText,typeof pbCanvasPalette,"
        "pbDiscHTML({id:'x',summary:'s',body:'b'}).indexOf('aria-expanded=\\\"false\\\"')>0,pbFilterBar({id:'f',chips:[{id:'c',label:'C',options:[]}]}).indexOf('data-fbar')>0,"
        "pbRichText('<i>**b**</i>'),pbHeadHTML({title:'t'}).indexOf('pb-head-t')>0])\",ctx);console.log(r);"
    )
    p = subprocess.run([node, "-e", prog, os.path.join(TPL, "runtime.js")], capture_output=True, text=True, timeout=30)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out = None
    check(p.returncode == 0 and out is not None and out[:4] == ["function"] * 4 and out[4] is True and out[5] is True and out[7] is True
          and out[6] == '<div class="pb-rt"><p>&lt;i&gt;<strong>b</strong>&lt;/i&gt;</p></div>',
          f"runtime.js still loads in a bare node vm (no document), and the primitives build their HTML there ({(p.stderr or '')[:120]})")


def main():
    static_checks()
    tmp = tempfile.mkdtemp()
    try:
        p_out, d_out = os.path.join(tmp, "p.html"), os.path.join(tmp, "ds.html")
        reg = build_project(tmp)
        render.render_file(reg, os.path.join(TPL, "prototype.html"), p_out)
        render.render_ds_file(reg, os.path.join(TPL, "design-system.html"), os.path.join(TPL, "runtime.js"), d_out)
        with sync_playwright() as pw:
            try:
                br = pw.chromium.launch()
            except Exception as e:  # noqa: BLE001
                print(f"SKIP: could not launch Chromium ({e})")
                sys.exit(2)
            ctx = br.new_context(viewport={"width": 1280, "height": 800})
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:"))
                      else r.fulfill(status=200, body="", content_type="text/plain"))
            for label, path in (("prototype", p_out), ("design system", d_out)):
                pg = ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                pg.goto("file://" + path, wait_until="domcontentloaded")
                pg.wait_for_selector(".pb-product", state="attached", timeout=10000)
                pg.add_style_tag(content=FREEZE)
                pg.wait_for_timeout(300)
                print(f"\n── {label} ──")
                disclosure(pg, label)
                filter_bar(pg, label)
                if label == "prototype":
                    prototype_bars(pg)
                    toasts(pg)
                canvas(pg, label)
                rich_text(pg, label)
                head(pg, label)
                reviewer_items(pg, label)
                check(errs == [], f"{label}: no page errors ({errs[:2]})")
                pg.close()
            br.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if _fail:
        print(f"✗ {len(_fail)} ui-primitives failure(s):")
        for f in _fail:
            print(f"    - {f}")
        sys.exit(1)
    print("✓ ui-primitives clean.")


if __name__ == "__main__":
    main()
