#!/usr/bin/env python3
"""
logic_blocks.py — a rule's structure renders as components, not paragraphs (v2.1.0).

The Logic tab had three structured layouts (state machine, matrix, constraint) and every other
rule — 43 of 43 on one real project — rendered as escaped paragraphs. The prose hid the same
shapes everywhere: condition → outcome tables, scope lists, placement, formulas, thresholds. This
pins the fix from both ends:

  * logic_check.py: L-BLOCK flags a block the renderer cannot draw; L-PROSE is information only
  * the shell, driven in Chromium: every block type draws its component (swatches, anatomy and
    examples included), the card says what is wrong as to-do rows naming a command, history is a
    tab whose green entry is the decision, a lifecycle draws as nodes + bands + return rows,
    invariants on a `decision` rule render, `enforcedIn` is accepted, the unchecked warning is
    said once, `status: superseded` folds the card, an unknown block degrades to text, a swatch
    value that is not a colour never reaches a style, and nothing throws

Usage:  python3 tests/logic_blocks.py
Exit:   0 = pass (the browser half is skipped, and says so, without Playwright) · 1 = a failure
"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import logic_check  # noqa: E402
import render       # noqa: E402

SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")
FAIL = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAIL.append(msg)


RULES = [
    {"id": "cycle-status", "title": "Cycle status", "kind": "decision",
     "summary": "A cycle's status is derived from today against its window.",
     "blocks": [
         {"type": "cases", "rows": [
             {"when": "today < start", "then": "Sắp bắt đầu", "tone": "info"},
             {"when": "today ≤ end − 48 h", "then": "Đang diễn ra", "tone": "ok"},
             {"when": "today ≤ end", "then": "Sắp hết hạn", "tone": "warn"}],
          "else": {"then": "Quá hạn", "tone": "bad"}},
         {"type": "params", "items": [{"name": "warning", "value": 48, "unit": "hours"}]},
     ],
     "decision": {"question": "Status from dates or set by hand?", "options": ["dates", "by hand"],
                  "chose": "dates", "why": "One source of truth.", "affects": ["Prototype", "UX Design"],
                  "stillOpen": ["Does a paused cycle count as overdue?"]},
     "supersedes": "manual-status", "citeNote": "Owner, 2026-09-01", "origin": "Ops review, week 34"},
    {"id": "undo-scope", "title": "What Undo reaches", "kind": "decision", "summary": "Undo acts on the stroke only.",
     "blocks": [
         {"type": "scope", "acts": ["the stroke being drawn"], "untouched": ["a finished task", "a Reset"]},
         {"type": "matrix", "rowLabel": "control", "rows": ["Undo", "Finish"], "cols": ["0", "1", "2+"],
          "cells": {"Undo": {"0": False, "1": True, "2+": True}, "Finish": {"0": False, "1": False, "2+": True}}},
         {"type": "steps", "items": [{"label": "Place a point"}, "Close the shape"]},
         {"type": "mystery", "text": "an unknown block keeps its text"},
     ]},
    {"id": "home-holds", "title": "What each tab holds", "kind": "decision", "summary": "Money on Home only.",
     "blocks": [
         {"type": "placement", "surfaces": [{"surface": "Home", "holds": ["Total"]},
                                            {"surface": "Profile", "holds": ["Name"], "never": ["money"]}]},
         {"type": "formula", "expr": "b = (b + you + employer) × (1 + m)",
          "terms": [{"name": "m", "means": "monthly return"}], "example": {"inputs": {"m": "0.7%"}, "result": "2,513,534"}},
         {"type": "effects", "writes": ["programs"], "ripple": [{"screen": "Home", "shows": "next deduction"}]},
         {"type": "validation", "items": [{"must": "starts inside the polygon", "code": "EDGE_ON_BOUNDARY",
                                           "message": "Chỉ được vẽ bên trong.", "enforcedIn": "zone-ring.js"}]},
         {"type": "note", "text": "SECOND PASS. Prose still renders with **emphasis**."},
     ]},
    {"id": "snap", "title": "Snapping", "kind": "decision", "summary": "Points snap to vertices.",
     "invariants": [{"must": "snap within 20 px"}, {"must": "never snap across wards"}],
     "decision": {"chose": "snap", "why": "precision"}},
    {"id": "assumed", "title": "Assumed default", "kind": "decision", "summary": "A default applies.",
     "decision": {"chose": "default", "why": "ASSUMPTION: nobody objected."}},
    {"id": "plain-choice", "title": "Plain choice", "kind": "decision",
     "decision": {"question": "A or B?", "options": ["A", "B"], "chose": "A", "why": "Simpler."}},
    {"id": "nav-four", "title": "Four tabs", "kind": "decision", "status": "superseded", "supersededOn": "2026-09-28",
     "summary": "Superseded by three tabs."},
    {"id": "colour-means", "title": "Polygon colour shows coverage", "kind": "constraint", "summary": "Colour is coverage.",
     "blocks": [
         {"type": "swatches", "items": [
             {"label": "Đã gán", "meaning": "assigned", "token": "coverage-assigned", "value": "#198038"},
             {"label": "Đã huỷ", "meaning": "cancelled", "token": "status-cancel", "value": "#B91C1C", "soft": "#FEE2E2"},
             {"label": "x", "meaning": "an unsafe value never reaches a style", "value": "red;background:url(x)"}]},
         {"type": "anatomy", "sample": "1050 · Riverside Hub", "parts": [
             {"text": "1050", "name": "ops_code", "rule": "Reads first."}, {"text": " · ", "name": "separator", "rule": "Middle dot."},
             {"text": "Riverside Hub", "name": "name", "rule": "Supporting.", "note": "Masked server-side.", "tone": "warn"}]},
         {"type": "examples", "items": [{"input": "3862.66", "output": "3.862,66 ha"}]},
     ]},
    {"id": "money-forms", "title": "Money takes three forms", "kind": "state-machine", "summary": "Cash, virtual, certificate.",
     "states": [{"key": "cash", "label": "Cash", "condition": "outside"}, {"key": "virtual", "label": "Virtual"},
                {"key": "cert", "label": "Certificate"}],
     "transitions": [["cash", "virtual"], ["virtual", "cert"], ["cert", "cash"], ["cert", "gone"]],
     "overlays": [{"key": "in", "label": "In programme", "over": ["virtual", "cert"]}],
     "blocks": [{"type": "matrix", "rows": ["Edit"], "cols": ["a", "b"], "cells": {"Edit": {"a": True}}}]},
]


def build(project):
    reg = {"meta": {"schemaVersion": 12, "name": "Blocks fixture"},
           "screens": [{"id": "home", "name": "Home", "renderSrc": "render/screens/home.js", "renderFn": "renderScreenHome"}],
           "components": [], "ia": {"populated": True, "rules": RULES}}
    os.makedirs(os.path.join(project, "render", "screens"))
    with open(os.path.join(project, "registry.json"), "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False)
    with open(os.path.join(project, "render", "screens", "home.js"), "w", encoding="utf-8") as f:
        f.write("return '<main>home</main>';\n")
    return reg


def main():
    print("logic_check.py — L-BLOCK / L-PROSE")
    bad = {"ia": {"rules": [
        {"id": "a", "blocks": [{"type": "cases"}]},
        {"id": "b", "blocks": [{"type": "nope", "text": "x"}]},
        {"id": "c", "blocks": [{"type": "matrix", "rows": ["r"]}]},
        {"id": "d", "summary": "x" * 400},
        {"id": "e", "blocks": RULES[0]["blocks"]},
    ]}}
    f = logic_check.check_blocks(bad)
    where = {x.where.split()[0] for x in f}
    check(all(x.severity == "ERROR" and x.code == "L-BLOCK" for x in f), "L-BLOCK findings are errors")
    check(where == {"rule='a'", "rule='b'", "rule='c'"}, f"L-BLOCK fires on a field-less, an unknown and a col-less block, not a valid one ({sorted(where)})")
    p = logic_check.check_prose(bad)
    check(len(p) == 1 and p[0].severity == "INFO", "L-PROSE notes the long unstructured rule, as information only")
    check(logic_check.check_blocks({"ia": {"rules": RULES}}) == [] or
          [x.where for x in logic_check.check_blocks({"ia": {"rules": RULES}})] == ["rule='undo-scope' blocks[3]"],
          "the fixture's only L-BLOCK is its deliberate unknown block")
    import re
    shell = open(SHELL, encoding="utf-8").read()
    body = shell[shell.index("const LGC_BLOCKS = {"):shell.index("function lgcBlock(")]
    drawn = set(re.findall(r"^      (\w+)\((?:b|m)\) \{", body, re.M))
    check(drawn == set(logic_check.BLOCK_REQUIRES),
          f"logic_check knows exactly the block types the shell draws ({sorted(drawn ^ set(logic_check.BLOCK_REQUIRES))})")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ○ Playwright not installed — the browser half is skipped (pip install playwright)")
        sync_playwright = None

    if sync_playwright:
        print("the Logic tab, in Chromium")
        tmp = tempfile.mkdtemp()
        try:
            project = os.path.join(tmp, "blocks")
            build(project)
            out = os.path.join(project, "prototype.html")
            render.render_file(os.path.join(project, "registry.json"), SHELL, out)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                # offline: the web font and the mermaid CDN are not under test, and a slow network must not fail it
                page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:", "blob:")) else r.abort())
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto("file://" + out)
                page.evaluate("setMetaView('flow'); pbSetUxView('logic');")
                page.wait_for_timeout(300)
                q = lambda sel: page.locator(sel).count()  # noqa: E731
                txt = lambda sel: page.locator(sel).first.inner_text() if q(sel) else ""  # noqa: E731
                check(errors == [], f"no page errors ({errors[:2]})")
                tc = lambda sel: page.locator(sel).first.text_content() if q(sel) else ""  # noqa: E731  (hidden tabs too)
                for t in ("cases", "scope", "placement", "matrix", "validation", "formula", "steps", "params", "effects", "note",
                          "swatches", "anatomy", "examples"):
                    check(q(f".lg-block--{t}") >= 1, f"a {t} block draws its component")
                # Rules are one-line pbDisclosure rows that open in place into the card (any number open
                # at once), so each card is opened before what it shows is read or clicked.
                def open_rule(rid):
                    row = page.locator(f'.pb-scan-tr[data-fb-list="logic"][data-key="{rid}"]')
                    if "is-open" not in (row.get_attribute("class") or ""):
                        row.locator("> .pb-disc-t").click()
                        page.wait_for_timeout(80)
                    check(page.locator(f"#rule-{rid}").is_visible(), f"(the {rid} row opens in place into its card)")
                check(q('.pb-scan-tr[data-fb-list="logic"]') == q(".lgc") and not page.locator("#rule-cycle-status").is_visible(),
                      "every rule is one row, closed until it is opened")
                open_rule("cycle-status")
                card = "#rule-cycle-status"
                check(q(f"{card} .lgc-cases tbody tr") == 4, "cases: three rows plus Otherwise")
                check("Quá hạn" in tc(f"{card} .lgc-cases .lgc-b-bad"), "cases: a tone becomes a coloured chip")
                row_st = lambda rid: txt(f'.pb-scan-tr[data-fb-list="logic"][data-key="{rid}"] .st')  # noqa: E731
                check(row_st("cycle-status") == "1 to resolve" and q(f"{card} .lgc-todo li") == 1,
                      "the row counts what needs resolving, and the card lists exactly that many")
                check(q(f"{card} .lgc-hd") == 0 and q(f"{card} .lgc-bs") == 0 and q(f"{card} .lgc-ti") == 0,
                      "inside a row the card has no repeated title or badges: it opens straight to content")
                check("still open" in txt(f"{card} .lgc-todo") and "/pb:clarify" in txt(f"{card} .lgc-todo"),
                      "an open question is a to-do row naming the command that answers it")
                check(not page.locator(f"{card} .lgc-p-history").is_visible(), "history sits in a tab, closed by default")
                check(page.locator(f"{card} .lgc-p-values").is_visible(), "values are the first tab when a rule has them")
                check("Does a paused cycle" in tc(f"{card} .lgc-p-history .lgc-open"), "History leads with the open question")
                check("Decided" in tc(f"{card} .lgc-ev-ok .lgc-evt") and "dates" in tc(f"{card} .lgc-on"),
                      "the decision is the timeline's green entry, the chosen option marked")
                check(q(f"{card} .lgc-p-history .lgc-chip") == 2, "an affects array becomes one chip per entry")
                check("manual-status" in tc(f"{card} .lgc-p-history"), "what the rule replaced is in its history")
                hist = tc(f"{card} .lgc-p-history")
                check(hist.count("Origin") == 1 and "Ops review, week 34" in hist and "Owner, 2026-09-01" in hist,
                      f"History says Origin once — the section title — and still shows the authored origin and the source ({hist.count('Origin')}x)")
                page.locator(f"{card} .lgc-l-history").click()
                check(page.locator(f"{card} .lgc-p-history").is_visible(), "the History tab opens on click")
                open_rule("undo-scope")
                check(page.locator("#rule-cycle-status").is_visible() and page.locator("#rule-undo-scope").is_visible()
                      and q('.pb-scan-tr[data-fb-list="logic"].is-open') == 2, "opening a row closes nothing: rows are multi-open")
                check("an unknown block keeps its text" in txt("#rule-undo-scope .lg-block--mystery"), "an unknown block degrades to its text")
                check(q("#rule-undo-scope .lgc-sc-out li") == 2, "scope: what is left untouched is listed")
                open_rule("home-holds")
                check("zone-ring.js" in tc("#rule-home-holds .lg-block--validation"), "enforcedIn is accepted as the enforcement point")
                check("EDGE_ON_BOUNDARY" in tc("#rule-home-holds .lg-block--validation"), "a validation code renders")
                check(q("#rule-home-holds .lg-block--note strong") >= 1, "a note gets the prose formatter (emphasis)")
                check(row_st("home-holds") == "Settled" and q("#rule-home-holds .lgc-todo") == 0, "a rule with nothing to resolve says settled")
                open_rule("snap")
                check(q("#rule-snap .lgc-ivl .lgc-iv") == 2 and q("#rule-snap .lgc-ivno") == 2, "invariants on a decision-kind rule render, each marked")
                check(q("#rule-snap .lgc-todo li") == 1 and "2 of 2 invariants" in txt("#rule-snap .lgc-todo"),
                      "the unchecked warning is said once per rule, not per row")
                # A superseded rule is history, not work: its row is hidden until "Show superseded" is on,
                # the Status chip lists only the live states, and the count is of what is shown.
                nav = '.pb-scan-tr[data-fb-list="logic"][data-key="nav-four"]'
                sup_chip = '.pb-fbar[data-fbar="logic"] [data-pb-quick="archived"]'
                n_rules = q('.pb-scan-tr[data-fb-list="logic"]')
                check(page.locator(nav).get_attribute("hidden") is not None and q(sup_chip) == 1
                      and "Show superseded" in txt(sup_chip)
                      and f"{n_rules - 1} of {n_rules - 1}" in txt('.pb-fbar[data-fbar="logic"] .pb-fbar-cnt'),
                      "a superseded rule is hidden by default behind a Show superseded chip, and N of M counts the live rules")
                check(page.locator('.pb-fbar[data-fbar="logic"] input[data-pb-opt="status"][value="Superseded"]').count() == 0,
                      "…and the Status chip offers only the live states")
                page.locator(sup_chip).click()
                page.wait_for_timeout(80)
                check(page.locator(nav).get_attribute("hidden") is None
                      and f"{n_rules} of {n_rules}" in txt('.pb-fbar[data-fbar="logic"] .pb-fbar-cnt'),
                      "Show superseded brings it back into the list")
                open_rule("nav-four")
                sup = page.locator("#rule-nav-four")
                check("lg-card--sup" in (sup.get_attribute("class") or "") and sup.evaluate("e => e.tagName") == "ARTICLE"
                      and "is-dim" in (page.locator(nav).get_attribute("class") or "") and row_st("nav-four") == "Superseded",
                      "a top-level status: superseded dims its row and says Superseded")
                check(sup.is_visible() and "superseded" in txt("#rule-nav-four .lgc-supnote") and "Superseded by three tabs" in txt("#rule-nav-four .lgc-lead"),
                      "…and a superseded card shows its body, with the supersession, when its row is open (no fold to open first)")
                check(q("#rule-cycle-status .lgc-bar .lgc-l") == 2, "a rule with Values and History keeps two tabs")
                check(q("#rule-snap .lgc-lone-history") == 1 and q("#rule-snap .lgc-bar") == 0 and q("#rule-snap details.lgc-acc") == 0
                      and page.locator("#rule-snap .lgc-lone-history .lgc-p-history").is_visible(),
                      "a lone History is drawn open, under its own heading — not a closed accordion, not a one-tab bar")
                gap = page.evaluate("""() => { const l = document.querySelector('#rule-snap .lgc-lone-history'), prev = l.previousElementSibling;
                  return l.getBoundingClientRect().top - prev.getBoundingClientRect().bottom; }""")
                check(gap >= 12, f"History is set off from the body above it by a gap ({gap}px), not touching it")
                check(q("#rule-undo-scope .lgc-lone") == 0 and q("#rule-undo-scope .lgc-tabs") == 0, "a rule with no history has no History section")
                # one status rule: an unconfirmed ASSUMPTION counts as to-resolve on the row, as on the card
                open_rule("assumed")
                check(row_st("assumed") == "1 to resolve" and q("#rule-assumed .lgc-todo li") == 1 and "assumption" in txt("#rule-assumed .lgc-todo"),
                      "an unconfirmed ASSUMPTION is counted by the row, as the card counts it")
                page.locator('.pb-fbar[data-fbar="logic"] [data-fb-all]').click()
                page.wait_for_timeout(100)
                agree = page.evaluate("""() => (window.PB_LOGIC.rules || []).map(r => { const f = pbRuleFacts(r);
                  const card = document.querySelector('#rule-' + CSS.escape(r.id) + ' .lgc-todo');
                  const row = document.querySelector('.pb-scan-tr[data-fb-list="logic"][data-key="' + CSS.escape(r.id) + '"] .st').textContent.trim();
                  const n = card ? card.children.length : 0;
                  return [r.id, f.status === 'Superseded' || (f.todo === n && row === (n ? n + ' to resolve' : 'Settled'))]; }).filter(x => !x[1]).map(x => x[0])""")
                check(agree == [], f"no row disagrees with its card about what is left to resolve ({agree})")
                # a rule that is only a decision shows the decision itself, not a closed History
                check(q("#rule-plain-choice .lgc-decided .lgc-on") == 1 and page.locator("#rule-plain-choice .lgc-decided .lgc-on").is_visible()
                      and q("#rule-plain-choice .lgc-lone, #rule-plain-choice .lgc-tabs, #rule-plain-choice details") == 0
                      and q("#rule-plain-choice .lgc-lead") == 0,
                      "a decision-only rule shows its decision directly (question, options, the choice marked)")
                check(q("#rule-assumed .lgc-decided") == 1, "…also when it has a one-line summary and nothing else")
                # the ID column goes when every id is only a slug; the id stays in the detail, copyable
                check(q(".pb-scan--logic.pb-scan--noid") == 1 and "ID" not in txt(".pb-scan--logic .pb-scan-h").split() and q('.pb-scan-tr[data-fb-list="logic"] .id') == 0,
                      "every id here is a slug, so the list has no ID column")
                check(txt("#rule-cycle-status .lgc-rid") .startswith("Rule id") and "cycle-status" in txt("#rule-cycle-status .lgc-rid"),
                      "…and the id is in the opened rule")
                page.locator("#rule-cycle-status .lgc-rid button").click()
                page.wait_for_timeout(100)
                check("Copied cycle-status" in txt("#pb-ui-toast"), "…with a copy button that says what it copied")
                verdicts = page.evaluate("[pbScanIdsAreSlugs(['ward-picker-scope','screen-model','snap']), pbScanIdsAreSlugs(['R-1','R-2']), pbScanIdsAreSlugs(['rule-3','rule-4']), pbScanIdsAreSlugs(['cycle-status','R-1']), pbScanIdsAreSlugs([])]")
                check(verdicts == [True, False, False, False, False], f"slugs hide the column; codes (R-1, rule-3), a mix and an empty list keep it ({verdicts})")
                page.evaluate("""() => { window.__rules = window.PB_LOGIC.rules; window.PB_LOGIC.rules = __rules.map((r, i) => Object.assign({}, r, { id: 'R-' + (i + 1) }));
                  state.logicView = 'rules'; renderMetaFlow(); }""")
                page.wait_for_timeout(100)
                check(q(".pb-scan--noid") == 0 and "ID" in txt(".pb-scan--logic .pb-scan-h") and q('.pb-scan-tr[data-fb-list="logic"] .id') == q('.pb-scan-tr[data-fb-list="logic"]'),
                      "a project whose ids are codes keeps its ID column")
                page.evaluate("window.PB_LOGIC.rules = window.__rules; renderMetaFlow();")
                page.wait_for_timeout(100)
                open_rule("money-forms")
                mf = "#rule-money-forms"
                check(q(f"{mf} .lgc-fn") == 3 and q(f"{mf} .lgc-fa:not(.lgc-fa-off)") == 2, "lifecycle: a node per state, an arrow per forward move")
                check(q(f"{mf} .lgc-fb") == 1 and "In programme" in txt(f"{mf} .lgc-fb"), "lifecycle: an overlay is a band under its states")
                check("returns to" in txt(f"{mf} .lgc-fo"), "lifecycle: a backward move is its own row")
                check(q(f"{mf} .lgc-todo-bad") == 2 and q(f"{mf} .lgc-gap") == 1, "a missing state and a matrix gap are red to-dos")
                open_rule("colour-means")
                cm = "#rule-colour-means"
                check(q(f"{cm} .lgc-pill") == 1 and "185, 28, 28" in page.locator(f"{cm} .lgc-pill").evaluate("e => getComputedStyle(e).color"),
                      "swatches: a state with a soft colour draws as the real pill")
                check(not page.locator(cm).evaluate("e => [...e.querySelectorAll('[style]')].some(x => /url\\(/.test(x.getAttribute('style')))"), "swatches: a colour that is not a colour never reaches a style")
                check(q(f"{cm} details.lgc-ref:not([open])") == 1, "swatches: tokens are a folded reference")
                check(q(f"{cm} .lgc-ap") == 3 and q(f"{cm} .lgc-tan tbody tr") == 3, "anatomy: the sample in parts, one row per part")
                check("3.862,66 ha" in tc(f"{cm} .lgc-tex"), "examples: the output renders as itself")
                # Impact: picking something far down a long list must not send the list back to the top.
                page.evaluate("""() => {
                  const base = window.PB_LOGIC.rules || [];
                  window.PB_LOGIC = { stats: { handlers: 0, exported: 0, saves: 0, slices: 0, deadReads: 0 }, handlers: [], slices: {},
                    rules: base.concat(base.map(r => Object.assign({}, r, { id: r.id + '-b' })), base.map(r => Object.assign({}, r, { id: r.id + '-c' }))),
                    items: Array.from({ length: 60 }, (_, i) => ({ kind: 'screen', id: 'screen-' + i, file: 'render/screens/screen-' + i + '.js', lines: 10,
                      composes: [], composedBy: [], ownLogic: [], wires: [], readBy: [] })) };
                  state.logicView = 'ripple'; state.logicFocus = null; renderMetaFlow();
                }""")
                page.wait_for_timeout(150)
                page.locator(".lg-search").fill("screen")
                page.evaluate("document.querySelector('.lg-list-wrap').scrollTop = 600")
                before = page.evaluate("document.querySelector('.lg-list-wrap').scrollTop")
                page.locator('.logic-row[data-lg-type="item"][data-lg-id="screen-40"]').click()
                page.wait_for_timeout(150)
                after = page.evaluate("document.querySelector('.lg-list-wrap').scrollTop")
                check(before > 300 and abs(after - before) <= 1, f"Impact: picking an item keeps the list where it was ({before} → {after})")
                check("screen-40" in txt(".lg-detail") and page.locator('.logic-row.active[data-lg-type="item"][data-lg-id="screen-40"]').count() == 1,
                      "Impact: the picked item is the one shown")
                check(page.locator(".lg-search").input_value() == "screen", "Impact: the filter text survives a pick")
                # Tabs remember their own place: leave Impact for Rules (and another UX tab), come back.
                page.evaluate("document.querySelector('.lg-list-wrap').scrollTop = 500")
                page.evaluate("pbSetLogicView('rules')")
                check(page.evaluate("document.querySelector('.lg-list-wrap')") is None, "switching to Rules leaves the Impact list")
                page.evaluate("pbSetLogicView('ripple')")
                page.wait_for_timeout(100)
                back = page.evaluate("document.querySelector('.lg-list-wrap').scrollTop")
                check(abs(back - 500) <= 1, f"Rules ↔ Impact: Impact is where you left it ({back})")
                page.evaluate("pbSetUxView('content')")
                page.evaluate("pbSetUxView('logic')")
                page.wait_for_timeout(100)
                back = page.evaluate("document.querySelector('.lg-list-wrap').scrollTop")
                check(abs(back - 500) <= 1, f"UX Design tabs: Logic is where you left it after visiting Content ({back})")
                page.evaluate("pbSetLogicView('rules')")
                # every card open, as a reader expanding the whole list would have it
                bar = page.locator('.pb-fbar[data-fbar="logic"] [data-fb-all]')
                page.wait_for_timeout(50)
                check(bar.inner_text() == "Collapse all" or q('.pb-scan-tr[data-fb-list="logic"]:not(.is-open)') > 0,
                      "the group bar names what a click will do, from the rows (rows closed → Expand all)")
                if bar.inner_text() == "Expand all":
                    bar.click()
                page.wait_for_timeout(100)
                check(q('.pb-scan-tr[data-fb-list="logic"]:not(.is-open)') == 0 and page.locator("#rule-cycle-status").is_visible()
                      and bar.inner_text() == "Collapse all", "Expand all opens every rule row, and becomes Collapse all")
                room = page.evaluate("(e => e.scrollHeight - e.clientHeight)(document.querySelector('.ux-scroll-wrap > .summary-scroll'))")
                check(room > 400, f"(the Rules pane is long enough to scroll: {room}px)")
                page.evaluate("document.querySelector('.ux-scroll-wrap > .summary-scroll').scrollTop = 300")
                page.evaluate("pbSetLogicView('ripple')"); page.evaluate("pbSetLogicView('rules')")
                rules_back = page.evaluate("document.querySelector('.ux-scroll-wrap > .summary-scroll').scrollTop")
                check(rules_back > 0, f"Rules keeps its own place too ({rules_back})")
                page.evaluate("setMetaView('summary')"); page.evaluate("setMetaView('flow')")
                page.wait_for_timeout(100)
                check(page.evaluate("!!document.querySelector('.ux-scroll-wrap')"), "returning to UX Design from another top-level tab works")
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(200)
                check(page.locator("#rule-cycle-status").is_visible(), "(the cards are open at phone width)")
                wide = page.evaluate("Math.max(...[...document.querySelectorAll('.lgc')].map(e => e.scrollWidth - e.clientWidth))")
                check(wide <= 1, f"cards fit a phone width without horizontal overflow ({wide}px)")
                browser.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ rule blocks: checked by logic_check, drawn as components by the shell")


if __name__ == "__main__":
    main()
