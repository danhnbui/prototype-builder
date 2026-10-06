#!/usr/bin/env python3
"""
logic_blocks.py — a rule's structure renders as components, not paragraphs (v2.1.0).

The Logic tab had three structured layouts (state machine, matrix, constraint) and every other
rule — 43 of 43 on one real project — rendered as escaped paragraphs. The prose hid the same
shapes everywhere: condition → outcome tables, scope lists, placement, formulas, thresholds. This
pins the fix from both ends:

  * logic_check.py: L-BLOCK flags a block the renderer cannot draw; L-PROSE is information only
  * the shell, driven in Chromium: every block type draws its component (swatches, anatomy and
    examples included), the card says what is wrong as to-do rows naming a command, history is in
    the drawer, a lifecycle draws as nodes + bands + return rows,
    invariants on a `decision` rule render, `enforcedIn` is accepted, the unchecked warning is
    said once, `status: superseded` folds the card, an unknown block degrades to text, a swatch
    value that is not a colour never reaches a style, and nothing throws

Variant B (feat/logic-visuals): the card is the rule's visuals, stacked in a fixed order, with a
Details button; the rule text, decision, open questions, history, tests and sources are in ONE
right-hand drawer (#lgc-drawer), which closes on Esc, ×, and the scrim, returns focus to its button
and survives a re-render. A rule with no visual says so and names what it looks like.

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
         {"type": "timeline", "marks": [{"key": "a", "label": "Issued"}, {"key": "b", "label": "Due"}],
          "bands": [{"to": "b", "then": "Open", "tone": "ok"}, {"from": "b", "then": "Late", "tone": "bad", "note": "Fee"}]},
         {"type": "order", "keys": [{"by": "status", "dir": "asc", "values": ["Late", "Open"]}, {"by": "updated", "dir": "desc"}],
          "tiebreak": "number", "never": ["alphabetical"]},
         {"type": "ladder", "items": [{"label": "First"}, {"label": "Second"}], "fallback": "Owner"},
         {"type": "matrix", "axis": "role", "rows": ["Admin", "Viewer"], "cols": ["Edit"], "cells": {"Admin": {"Edit": True}}},
     ]},
    {"id": "home-holds", "title": "What each tab holds", "kind": "decision", "summary": "Money on Home only.",
     "blocks": [
         {"type": "placement", "surfaces": [{"surface": "Home", "holds": ["Total"]},
                                            {"surface": "Profile", "holds": ["Name"], "never": ["money"]}]},
         {"type": "formula", "expr": "b = (b + you + employer) × (1 + m)",
          "terms": [{"name": "m", "means": "monthly return"}], "example": {"inputs": {"m": "0.7%"}, "result": "2,513,534"}},
         {"type": "effects", "writes": ["programs"], "ripple": [{"screen": "Home", "shows": "next deduction"}], "toast": ["Joined the programme"]},
         {"type": "edges", "rows": [{"case": "Nothing yet", "shows": "Empty state", "status": "covered"},
                                    {"case": "Offline", "shows": "Cached list", "recovery": "Retry", "status": "open"},
                                    {"case": "Expired", "shows": "Expired badge", "status": "accepted"}]},
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
    {"id": "values-new", "title": "Values family", "kind": "decision", "summary": "Fields, gates, formulas.",
     "invariants": [{"must": "Totals add up", "enforcedBy": "orderTotal", "when": "a line changes"}, {"must": "Never reused"}],
     "blocks": [
         {"type": "validation", "field": {"label": "Quantity", "sample": "120"},
          "items": [{"must": "1 to 99", "code": "QTY_RANGE", "message": "Enter 1 to 99.", "enforcedIn": "orders.js"}]},
         {"type": "gate", "control": "Submit", "requires": ["A line", {"label": "A workspace"}],
          "notGated": [{"what": "Save draft", "why": "Never loses work"}], "message": "Finish the order."},
         {"type": "formula", "expr": "t = a + b", "split": [{"label": "A", "value": 30}, {"label": "B", "value": 10, "tone": "warn"}]},
         {"type": "params", "items": [{"name": "limit", "value": 9, "unit": "items", "source": "sourced", "ref": "Ops"},
                                      {"name": "undo", "value": 10, "unit": "s", "source": "invented"}]},
         {"type": "inputs", "rows": [{"input": "Cmd+K", "does": "Search"}, {"input": "Shift-click", "does": "Range", "never": "Delete"}]},
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
                for t in ("cases", "scope", "placement", "matrix", "validation", "formula", "steps", "params", "effects",
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
                dr = "#lgc-drawer"

                def open_details(rid):
                    page.locator(f"#rule-{rid} .lgc-dbtn").click()
                    page.wait_for_timeout(350)
                    check(page.locator(f"{dr} .lgc-dpanel").is_visible(), f"(Details opens the drawer for {rid})")

                def close_details():
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(350)
                check(q('.pb-scan-tr[data-fb-list="logic"]') == q(".lgc") and not page.locator("#rule-cycle-status").is_visible(),
                      "every rule is one row, closed until it is opened")
                check(q(dr) == 0, "the drawer does not exist until Details is first pressed")
                open_rule("cycle-status")
                card = "#rule-cycle-status"
                check(q(f"{card} .lgc-cases .lgt-cr") == 4 and q(f"{card} .lgc-cases .lgt-cr--else") == 1 and "first match" in tc(f"{card} .lg-block--cases"), "cases: three rows plus Otherwise, as a first-match ladder")
                check("Quá hạn" in tc(f"{card} .lgc-cases .lgc-b-bad"), "cases: a tone becomes a coloured chip")
                row_st = lambda rid: txt(f'.pb-scan-tr[data-fb-list="logic"][data-key="{rid}"] .st')  # noqa: E731
                check(row_st("cycle-status") == "1 to resolve" and q(f"{card} .lgc-todo li") == 1,
                      "the row counts what needs resolving, and the card lists exactly that many")
                check(q(f"{card} .lgc-hd") == 0 and q(f"{card} .lgc-bs") == 0 and q(f"{card} .lgc-ti") == 0,
                      "inside a row the card has no repeated title or badges: it opens straight to content")
                check("still open" in txt(f"{card} .lgc-todo") and "/pb:clarify" in txt(f"{card} .lgc-todo"),
                      "an open question is a to-do row naming the command that answers it")
                check(q(f"{card} .lgc-tabs") == 0 and q(f"{card} .lgc-bar") == 0 and q(f"{card} .lgc-lone") == 0 and q(f"{card} .lgc-p-history") == 0
                      and q(f"{card} .lgc-r") == 0, "the card has no Values/History tabs and no inline history: that is all behind Details")
                check(q(f"{card} > .lgc-lead") == 1 and q(f"{card} > .lgc-vis") == 1 and q(f"{card} > .lgc-dbar .lgc-dbtn") == 1,
                      "a card is a lead, a visual stack and a details bar")
                order = page.evaluate("[...document.querySelectorAll('#rule-cycle-status .lgc-vis > .lg-block')].map(e => e.className.match(/lg-block--(\\w+)/)[1])")
                check(order == ["cases", "params"], f"the stack follows the fixed order: tables before values ({order})")
                chips = tc(f"{card} .lgc-dbar")
                check("Decided" in chips and "chose dates over 1" in chips and "1 open" in chips,
                      f"the bar's quiet chips say what is behind Details ({chips.strip()!r})")
                check(page.locator(f"{card} .lgc-dbtn").get_attribute("data-rule") == "cycle-status"
                      and "cycle-status" not in (page.locator(f"{card} .lgc-dbtn").get_attribute("onclick") or ""),
                      "the Details button carries the id in data-rule, never in its handler")
                open_details("cycle-status")
                panel = page.locator(f"{dr} .lgc-dpanel")
                check(panel.get_attribute("role") == "dialog" and panel.get_attribute("aria-modal") == "true"
                      and "Cycle status" in txt(f"{dr} #lgc-d-title") and panel.get_attribute("aria-labelledby") == "lgc-d-title",
                      "the drawer is a modal dialog labelled by the rule's title")
                check(page.evaluate("document.activeElement === document.querySelector('#lgc-drawer .lgc-dpanel')"), "focus moves to the drawer's panel")
                check(page.evaluate("document.querySelector('#lgc-drawer .lgc-dpanel').getBoundingClientRect().width") <= 482, "the drawer is 480px wide on a desktop")
                secs = page.evaluate("[...document.querySelectorAll('#lgc-drawer .lgc-dsec')].map(e => e.className.match(/lgc-dsec--(\\w+)/)[1])")
                check(secs == ["text", "decision", "open", "history", "tests", "sources"], f"the drawer's sections come in order, each present only when it has content ({secs})")
                check("Does a paused cycle" in tc(f"{dr} .lgc-dsec--open"), "Open questions lists the open question")
                check("Decided" not in tc(f"{dr} .lgc-p-history .lgc-evt") and q(f"{dr} .lgc-p-history .lgc-ev-ok") == 0,
                      "History does not repeat the decision: it has its own section")
                check("dates" in tc(f"{dr} .lgc-dsec--decision .lgc-co--yes") and q(f"{dr} .lgc-dsec--decision .lgc-co") == 2,
                      "the decision marks the chosen option among the weighed ones")
                check(q(f"{dr} .lgc-dsec--decision .lgc-chip") == 2, "an affects array becomes one chip per entry")
                check("manual-status" in tc(f"{dr} .lgc-p-history"), "what the rule replaced is in its history")
                hist = tc(f"{dr} .lgc-p-history")
                check(hist.count("Origin") == 1 and "Ops review, week 34" in hist and "Owner, 2026-09-01" in hist,
                      f"History says Origin once — the section title — and still shows the authored origin and the source ({hist.count('Origin')}x)")
                check(page.locator(f"{dr} .lgc-p-history").is_visible(), "history is reachable once Details is pressed")
                check("No test names this rule" in tc(f"{dr} .lgc-dsec--tests"), "Tests says so when no scenario names the rule")
                check("cycle-status" in tc(f"{dr} .lgc-dsec--sources .lgc-rid"), "Sources carries the rule id")
                # closing: Esc, ×, the scrim — each returns focus to the Details button
                close_details()
                check(not page.locator(f"{dr} .lgc-dpanel").is_visible() and page.locator(dr).get_attribute("aria-hidden") == "true",
                      "Esc closes the drawer")
                check(page.evaluate("document.activeElement === document.querySelector('#rule-cycle-status .lgc-dbtn')"), "…and focus returns to the Details button")
                open_details("cycle-status")
                x = page.locator(f"{dr} .lgc-dhd button")
                check(x.get_attribute("aria-label") and x.get_attribute("title"), "the × button has both an aria-label and a title")
                x.click(); page.wait_for_timeout(350)
                check(not page.locator(f"{dr} .lgc-dpanel").is_visible(), "× closes the drawer")
                open_details("cycle-status")
                page.mouse.click(40, 450); page.wait_for_timeout(350)
                check(not page.locator(f"{dr} .lgc-dpanel").is_visible(), "a click on the scrim closes the drawer")
                # it survives a re-render of the tab, on the same rule
                open_details("cycle-status")
                page.evaluate("pbKeepScroll(renderMetaFlow)"); page.wait_for_timeout(200)
                check(page.locator(f"{dr} .lgc-dpanel").is_visible() and "Cycle status" in txt(f"{dr} #lgc-d-title"),
                      "the drawer survives a re-render, on the same rule")
                close_details()
                open_rule("undo-scope")
                check(page.locator("#rule-cycle-status").is_visible() and page.locator("#rule-undo-scope").is_visible()
                      and q('.pb-scan-tr[data-fb-list="logic"].is-open') == 2, "opening a row closes nothing: rows are multi-open")
                check("an unknown block keeps its text" in txt("#rule-undo-scope .lg-block--mystery"), "an unknown block degrades to its text")
                check(q("#rule-undo-scope .lgc-sc-out li") == 2, "scope: what is left untouched is listed")
                check(q("#rule-undo-scope .lg-block--scope svg.lgc-sv") == 1, "scope: a region diagram sits above the lists")
                check(q("#rule-undo-scope .lg-block--timeline svg .lgt-tick") == 2 and q("#rule-undo-scope .lg-block--timeline .lgt-seg") == 2,
                      "timeline: a ruler svg with one tick per mark and one band per segment")
                check(q("#rule-undo-scope .lg-block--order .lgt-key") == 2 and q("#rule-undo-scope .lg-block--order .lgt-c--bad") == 1,
                      "order: numbered key rows and a never-listed chip")
                check(q("#rule-undo-scope .lg-block--ladder .lgt-rung") == 3 and q("#rule-undo-scope .lg-block--ladder .lgt-rung--end") == 1,
                      "ladder: numbered rungs plus a dashed fallback")
                check(q("#rule-undo-scope .lg-block--matrix .lgt-rd") == 2 and q("#rule-undo-scope .lg-block--matrix .lgt-gapm") == 1,
                      "matrix: role dots on rows, a gap marker for the missing cell")
                open_rule("home-holds")
                check("zone-ring.js" in tc("#rule-home-holds .lg-block--validation"), "enforcedIn is accepted as the enforcement point")
                check("EDGE_ON_BOUNDARY" in tc("#rule-home-holds .lg-block--validation"), "a validation code renders")
                check(q("#rule-home-holds .lg-block--placement td .lgt-g--ink") == 2 and q("#rule-home-holds .lg-block--placement td .lgt-g--bad") == 1,
                      "placement: a figures x surfaces grid with holds and never marks")
                check(q("#rule-home-holds .lg-block--note") == 0, "a note is not in the visual stack")
                open_details("home-holds")
                check(q(f"{dr} .lgc-dsec--text .lg-block--note strong") >= 1, "a note is in the drawer's Rule text, with the prose formatter (emphasis)")
                close_details()
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
                open_details("snap")
                check(q(f"{dr} .lgc-dsec--decision") == 1 and q(f"{dr} .lgc-dsec--history") == 0,
                      "a rule whose only record is its decision has a Decision section and no History section")
                close_details()
                open_details("undo-scope")
                check(q(f"{dr} .lgc-dsec--history") == 0 and q(f"{dr} .lgc-dsec--decision") == 0 and q(f"{dr} .lgc-dsec--text") == 1,
                      "a rule with no history has no History section: sections with nothing in them are left out")
                close_details()
                # drawer sections, driven with synthetic rules so each path is pinned on its own
                def frag(fn, rule):
                    html = page.evaluate("([fn, r]) => eval(fn)(r)", [fn, rule])
                    page.evaluate("h => { let d = document.getElementById('b7-frag'); if (!d) { d = document.createElement('div'); d.id = 'b7-frag'; d.hidden = true; document.body.appendChild(d); } d.innerHTML = h; }", html)
                    return html
                fq = lambda sel: page.locator(f"#b7-frag {sel}").count()  # noqa: E731
                ft = lambda sel: page.locator(f"#b7-frag {sel}").first.text_content() if fq(sel) else ""  # noqa: E731
                frag("lgcDrawerDecision", {"id": "t", "decision": {"question": "Which?", "options": "Alpha | Beta | Gamma", "chose": "Beta",
                                           "why": "Beta is simpler. Gamma costs more to run. ASSUMPTION: load stays low.", "affects": ["Orders"], "decidedOn": "2026-09-01"}})
                check(fq(".lgc-cmp .lgc-co--yes") == 1 and fq(".lgc-co--yes .lgc-ck") == 1 and "Chosen" in ft(".lgc-co--yes")
                      and fq(".lgc-co--no") == 2 and "Not chosen" in ft(".lgc-co--no"),
                      "the decision is a compare: one chosen card with a check, one muted card per rejected option")
                check("Gamma costs more" in ft(".lgc-co--no:nth-child(2) .lgc-cor") and fq(".lgc-co--no .lgc-cor") == 1,
                      "a rejected option shows its reason only when the why gives one")
                check("Assumption" in ft(".lgc-dline") and "Orders" in ft(".lgc-chips"), "an ASSUMPTION in the why is a warn chip, and affects are chips")
                frag("lgcDrawerDecision", {"id": "t", "decision": {"chose": "Y", "options": ["Z"], "why": "Y is cheaper."}})
                check("Question not recorded" in ft(".lgc-dq--none") and fq(".lgc-co--yes") == 1 and fq(".lgc-co--no") == 1 and fq(".lgc-cor") == 0,
                      "an empty question is a dashed slot; a chosen option outside `options` is still the chosen card, and no reason is invented")
                frag("lgcDrawerOpen", {"id": "t", "decision": {"stillOpen": ["Cover refunds? (1) partial (2) full"], "why": "ASSUMPTION: x."}})
                check(fq(".lgc-oq") == 4 and "question" in ft(".lgc-oq:nth-child(2)") and "open" in ft(".lgc-oq:nth-child(2)") and "assumption" in ft(".lgc-oq:last-child"),
                      "open questions are rows with a kind and a status chip, split on (1) (2), plus an assumption row")
                loop = {"id": "a", "supersedes": "b", "supersededBy": "b", "decision": {"chose": "x"}}
                frag("lgcDrawerHistory", {"id": "a", "supersedes": "b", "decision": {"chose": "x", "decidedOn": "2026-09-01"}})
                check(fq(".lgc-p-history .lgc-lin svg") == 1 and fq(".lgc-sv-n--strong") == 1 and fq(".lgc-sv-e--bad") == 0,
                      "a rule that replaces another draws a lineage chain with the current rule strong")
                frag("lgcDrawerHistory", loop)
                check(fq(".lgc-sv-e--bad.lgc-sv-e--dash") == 1 and "Lineage loop" in ft(".lgc-lin"), "a supersedes loop is a red dashed back edge labelled Lineage loop")
                check(fq(".lgc-p-history") == 1, "the History wrapper is kept")
                page.evaluate("""() => { const f = PB_DATA.flow = PB_DATA.flow || {}; f.stories = (f.stories || []).concat([{ title: 'Probe', scenarios: [
                    { id: 'p1', rule: 'probe', title: 'Probe passes', test: 'x', lastResult: { result: 'pass' } },
                    { id: 'p2', rule: 'probe', title: 'Probe fails', test: 'x', lastResult: { result: 'fail', roles: { admin: 'pass', editor: 'fail' } } }] }]); }""")
                frag("lgcDrawerTests", {"id": "probe"})
                check(fq(".lgc-tst") == 2 and fq(".lgc-tg-fail") >= 1 and "1 pass" in ft(".lgc-tsum") and "1 fail" in ft(".lgc-tsum") and fq(".lgc-rr") == 2,
                      "the tests list shows each verdict glyph, a pass/fail/not-run summary and per-role results")
                frag("lgcDrawerTests", {"id": "no-such-rule"})
                check("No test names this rule" in ft(".lgc-dim"), "a rule no test names says so")
                page.evaluate("PB_DATA.flow.stories.pop()")
                page.evaluate("(() => { const f = document.getElementById('b7-frag'); if (f) f.remove(); })()")
                # rows: the first visual's glyph and a tiny preview
                row = lambda rid, sel: txt(f'.pb-scan-tr[data-fb-list="logic"][data-key="{rid}"] {sel}')  # noqa: E731
                check(q('.pb-scan-tr[data-fb-list="logic"][data-key="cycle-status"] .lgc-gl svg') == 1 and row("cycle-status", ".lgc-pv") == "3 cases +1"
                      and row("snap", ".lgc-pv") == "0 of 2 checked" and row("plain-choice", ".lgc-pv") == "prose only"
                      and row("home-holds", ".lgc-pv") == "2 surfaces +4",
                      "each row shows its first visual's glyph and a tiny preview (3 cases +1, 0 of 2 checked, prose only)")
                check(page.evaluate("[...document.querySelectorAll('.pb-scan-tr[data-fb-list=\"logic\"] .lgc-gl svg')].every(s => s.getBoundingClientRect().width >= 16)"),
                      "the glyph is never under 16px")
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
                check(q("#rule-plain-choice .lgc-vis--none .lgc-nov") == 1 and "Prose only" in txt("#rule-plain-choice .lgc-nov")
                      and "/pb:clarify" in txt("#rule-plain-choice .lgc-nov") and "solid" in (page.locator("#rule-plain-choice .lgc-dbtn").get_attribute("class") or "")
                      and q("#rule-plain-choice .lgc-lead") == 0,
                      "a rule with no visual says so, names /pb:clarify, and emphasises its Details button")
                check("Looks like" not in txt("#rule-plain-choice .lgc-nov"), "…and offers no 'Looks like' without a shape scan")
                page.evaluate("""() => { window.PB_LOGIC.shapes = { 'plain-choice': [{ type: 'steps', why: 'first' }, { type: 'cases', why: 'if' }] };
                  renderMetaFlow(); }""")
                page.wait_for_timeout(120)
                check(q("#rule-plain-choice .lgc-nov-c .lgc-chip") == 2 and "Looks like" in txt("#rule-plain-choice .lgc-nov"),
                      "…with 'Looks like: steps, cases' when the shape scan found signals")
                open_details("plain-choice")
                check(q(f"{dr} .lgc-dsec--decision .lgc-co--yes") == 1 and page.locator(f"{dr} .lgc-dsec--decision .lgc-co--yes").is_visible(),
                      "a decision-only rule's decision (question, options, the choice marked) is in the drawer")
                close_details()
                open_details("assumed")
                check(q(f"{dr} .lgc-dsec--decision") == 1 and "assumption" in txt(f"{dr} .lgc-dsec--open").lower(), "…also when it has a one-line summary and nothing else")
                close_details()
                # the Pattern chip: Flow · Tables · Values · Effects · Prose only
                pat = '.pb-fbar[data-fbar="logic"] [data-pb-chip="pattern"]'
                check(q(pat) == 1, "the filter bar has a Pattern chip")
                page.locator(pat).click()
                prose = page.locator('.pb-fbar[data-fbar="logic"] input[data-pb-opt="pattern"][value="Prose only"]')
                opts = page.evaluate("[...document.querySelectorAll('.pb-fbar[data-fbar=\"logic\"] input[data-pb-opt=\"pattern\"]')].map(i => i.value)")
                check(opts == ["Flow", "Tables", "Values", "Effects", "Prose only"], f"Pattern offers the five families in order ({opts})")
                prose.check(); page.wait_for_timeout(100)
                vis_rows = page.evaluate("[...document.querySelectorAll('.pb-scan-tr[data-fb-list=\"logic\"]')].filter(r => !r.hidden).map(r => r.dataset.key).sort()")
                check(vis_rows == ["assumed", "nav-four", "plain-choice"], f"Pattern → Prose only keeps the rules with no visual ({vis_rows})")
                prose.uncheck(); page.locator('.pb-fbar[data-fbar="logic"] input[data-pb-opt="pattern"][value="Flow"]').check(); page.wait_for_timeout(100)
                vis_rows = page.evaluate("[...document.querySelectorAll('.pb-scan-tr[data-fb-list=\"logic\"]')].filter(r => !r.hidden).map(r => r.dataset.key).sort()")
                check(vis_rows == ["money-forms", "undo-scope"], f"Pattern → Flow matches a rule by ANY of its visuals ({vis_rows})")
                page.locator('.pb-fbar[data-fbar="logic"] input[data-pb-opt="pattern"][value="Flow"]').uncheck(); page.keyboard.press("Escape"); page.wait_for_timeout(100)
                # the ID column goes when every id is only a slug; the id stays in the detail, copyable
                check(q(".pb-scan--logic.pb-scan--noid") == 1 and "ID" not in txt(".pb-scan--logic .pb-scan-h").split() and q('.pb-scan-tr[data-fb-list="logic"] .id') == 0,
                      "every id here is a slug, so the list has no ID column")
                open_details("cycle-status")
                check(txt(f"{dr} .lgc-rid").startswith("Rule id") and "cycle-status" in txt(f"{dr} .lgc-rid"),
                      "…and the id is in the drawer's Sources")
                page.locator(f"{dr} .lgc-rid button").click()
                page.wait_for_timeout(100)
                check("Copied cycle-status" in txt("#pb-ui-toast"), "…with a copy button that says what it copied")
                close_details()
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
                check(q(f"{mf} svg.lgc-sv") == 1, "lifecycle: drawn as one SVG statechart")
                check(q(f"{mf} .lgc-sc-node[data-state]") == 3, "lifecycle: one node per state")
                check(q(f"{mf} .lgc-sc-back .lgc-sv-e--dash") == 1, "lifecycle: a move back is a dashed edge")
                check(q(f"{mf} .lgc-sc-band") == 1 and "In programme" in tc(f"{mf} .lgc-sc-band"), "lifecycle: an overlay is a dashed band with its label")
                check(q(f"{mf} .lgc-sc-miss") == 1 and "gone" in tc(f"{mf} .lgc-sc-miss"), "lifecycle: a move to a missing state is drawn to a dashed ? node")
                check(q(f"{mf} .lgc-todo-bad") == 2 and q(f"{mf} .lgc-gap") == 1, "a missing state and a matrix gap are red to-dos")
                page.evaluate("""() => { window.__rules2 = window.PB_LOGIC.rules; window.PB_LOGIC.stateWriters = Object.assign({}, window.PB_LOGIC.stateWriters, { 'fx-life': { open: { assigns: [] }, shut: { derived: true, assigns: [] } } });
                  window.PB_LOGIC.rules = __rules2.concat([
                  { id: 'fx-life', title: 'Life', kind: 'state-machine', summary: 'A lifecycle.', stateField: 'order.status', states: [{ key: 'open', label: 'Open' }, { key: 'shut', label: 'Shut', derived: true }], transitions: [['open', 'shut']] },
                  { id: 'fx-steps', title: 'Steps', kind: 'decision', summary: 'A stepper.', blocks: [{ type: 'steps', items: [{ label: 'One', detail: 'first' }, { label: 'Two', guard: 'ticked', back: 'One' }], outcome: { label: 'Done' } }] },
                  { id: 'fx-states', title: 'States', kind: 'decision', summary: 'Frames.', blocks: [{ type: 'states', component: 'card', items: [{ key: 'a', label: 'A', shows: 'Edit' }, { key: 'b', label: 'B', shows: 'Pay', tone: 'ok' }], interaction: ['hover'] }] },
                  { id: 'fx-nav', title: 'Nav', kind: 'decision', summary: 'Tabs.', blocks: [{ type: 'nav', tabs: [{ key: 'h', label: 'Home' }, { key: 'o', label: 'Orders' }], pushed: ['Detail'], reset: ['Switch'] }] },
                  { id: 'fx-branches', title: 'Branches', kind: 'decision', summary: 'Show when.', blocks: [{ type: 'branches', rows: [{ when: 'empty', shows: 'A prompt' }], else: { shows: 'The list' } }] },
                  { id: 'fx-async', title: 'Async', kind: 'decision', summary: 'Outcomes.', blocks: [{ type: 'async', order: ['pending', 'ok'], outcomes: [{ key: 'pending', label: 'Saving', copy: 'Saving' }, { key: 'ok', label: 'Saved', copy: 'Saved' }, { key: 'partial', label: 'Some failed', copy: 'Some failed' }] }] },
                ]); state.logicView = 'rules'; renderMetaFlow(); }""")
                page.wait_for_timeout(100)
                for rid in ("fx-life", "fx-steps", "fx-states", "fx-nav", "fx-branches", "fx-async"):
                    open_rule(rid)
                check(q("#rule-fx-life .lgc-sc-dead") >= 1 and "Nothing sets order.status = 'open'" in tc("#rule-fx-life .lgc-sc-flag") and q("#rule-fx-life .lgc-sc-node[data-state=shut]") == 1,
                      "lifecycle: a state nothing sets is flagged (amber dashed) with what to set")
                check(q("#rule-fx-steps .lg-block--steps svg .lgc-st-node") == 3 and q("#rule-fx-steps .lgc-st-out") == 1 and q("#rule-fx-steps .lgc-sv-e--dash") == 1
                      and "ticked" in tc("#rule-fx-steps .lg-block--steps"), "steps: a node per step plus the outcome, the guard on the connector, a dashed return arrow")
                check(q("#rule-fx-states .lg-block--states .lgc-fr") == 2 and "hover" in tc("#rule-fx-states .lgc-stx"), "states: a mini frame per business state, interaction states as chips")
                check(q("#rule-fx-nav .lg-block--nav .lgc-nv-tab") == 2 and q("#rule-fx-nav .lgc-nv-back") == 1 and "no back, resets history" in tc("#rule-fx-nav .lg-block--nav"),
                      "nav: a tab bar mini, a pushed mini with a back control, pushed and reset chips")
                check(q("#rule-fx-branches .lg-block--branches .lgc-br") == 2 and q("#rule-fx-branches .lgc-br-else") == 1, "branches: a condition card per row, the else row last")
                check(q("#rule-fx-async .lg-block--async svg .lgc-as-out") == 3 and q("#rule-fx-async .lgc-as-out .lgc-sv-etxt") >= 1, "async: an outcome pill per outcome in the UI lane, partial marked")
                page.evaluate("window.PB_LOGIC.rules = window.__rules2; renderMetaFlow();")
                page.wait_for_timeout(100)
                open_rule("values-new")
                vn = "#rule-values-new"
                check(q(f"{vn} .lgc-fcard") == 2 and q(f"{vn} .lgc-fcard--bad .lgc-ferr") == 1 and "Enter 1 to 99" in txt(f"{vn} .lgc-ferr")
                      and q(f"{vn} .lg-block--validation code.lgc-code") >= 1, "validation: a field valid and refused, message inline, code badge")
                check(q(f"{vn} .lgc-gc--off .lgc-pbtn--off") == 1 and q(f"{vn} .lgc-gc--on .lgc-pbtn:not(.lgc-pbtn--off)") == 1
                      and q(f"{vn} .lgc-gc--off .lgc-gg--off") == 2 and "Finish the order" in txt(f"{vn} .lgc-ghint") and "deliberately not gated" in tc(f"{vn} .lgc-ng").lower(),
                      "gate: disabled over unmet, enabled over met, hint, not-gated list")
                check(q(f"{vn} .lgc-sgb > i") == 2 and q(f"{vn} .lgc-sgl > div") == 2 and q(f"{vn} .lgc-sg-warn") >= 1, "formula: a toned stacked bar with a legend")
                check(q(f"{vn} .lgc-pt") == 2 and q(f"{vn} .lgc-pt--warn") == 1 and "invented" in txt(f"{vn} .lgc-pt--warn")
                      and "Ops" in (page.locator(f"{vn} .lgc-pt").first.get_attribute("title") or ""), "params: tiles, invented is warn, ref in the tooltip")
                check(q(f"{vn} .lgc-tkm tbody tr") == 2 and q(f"{vn} .lgc-tkm .lgc-kbd") >= 3 and q(f"{vn} .lgc-tkm svg.lgc-mouse") == 1
                      and page.locator(f"{vn} svg.lgc-mouse").first.evaluate("e => e.getBoundingClientRect().width") >= 16, "inputs: keycaps and a 16px+ mouse glyph")
                iv = f"{vn} .lg-block--invariants"
                check("1 of 2" in tc(f"{iv} .lgc-ivsum") and q(f"{iv} .lgc-ivok") == 1 and q(f"{iv} .lgc-ivwhen") == 1, "invariants: summary, badge, when chip")
                open_rule("colour-means")
                cm = "#rule-colour-means"
                check(q(f"{cm} .lgc-pill") == 1 and "185, 28, 28" in page.locator(f"{cm} .lgc-pill").evaluate("e => getComputedStyle(e).color"),
                      "swatches: a state with a soft colour draws as the real pill")
                check(not page.locator(cm).evaluate("e => [...e.querySelectorAll('[style]')].some(x => /url\\(/.test(x.getAttribute('style')))"), "swatches: a colour that is not a colour never reaches a style")
                check(q(f"{cm} details.lgc-ref:not([open])") == 1, "swatches: tokens are a folded reference")
                check(q(f"{cm} .lgc-ap") == 3 and q(f"{cm} .lgc-tan tbody tr") == 3, "anatomy: the sample in parts, one row per part")
                check("3.862,66 ha" in tc(f"{cm} .lgc-tex"), "examples: the output renders as itself")
                # effects + edges (B4)
                open_rule("home-holds")
                hh = "#rule-home-holds"
                check(q(f"{hh} .lg-block--effects svg") == 1 and "Joined the programme" in tc(f"{hh} .lg-block--effects .lgx-toast")
                      and "store.programs" in tc(f"{hh} .lg-block--effects svg"), "effects: an SVG ripple, and the toast as a real toast")
                check(q(f"{hh} .lg-block--edges .lgc-fr") == 3 and q(f"{hh} .lg-block--edges .lgc-b-ok") == 1
                      and q(f"{hh} .lg-block--edges .lgc-b-warn") == 1 and q(f"{hh} .lg-block--edges .lgc-b-n") == 1
                      and "1 covered · 1 open · 1 accepted" in tc(f"{hh} .lg-block--edges .lgx-sum"), "edges: a frame per row, a status chip each, a summary bar")
                check("Retry" in tc(f"{hh} .lg-block--edges .lgc-sk-btn"), "edges: the recovery is a button")
                # the drawer's Rule text: dated revisions become a timeline, otherwise prose
                page.evaluate("""() => { const r = window.PB_LOGIC.rules.find(x => x.id === 'home-holds');
                  window.__sum = r.summary; r.summary = 'Money on Home only. REVISED 2026-10-05: Profile may show a total. AMENDED on 2026-09-28 - Settings never shows money.'; }""")
                open_details("home-holds")
                check(q(f"{dr} .lgc-tl-i") == 3 and "2026-10-05" in tc(f"{dr} .lgc-tl") and "Profile may show a total" in tc(f"{dr} .lgc-tl"),
                      "rule text: dated revision markers draw as a timeline (original + one entry each)")
                close_details()
                page.evaluate("window.PB_LOGIC.rules.find(x => x.id === 'home-holds').summary = window.__sum")
                open_details("home-holds")
                check(q(f"{dr} .lgc-tl") == 0 and "Money on Home only" in tc(f"{dr} .lgc-rt"), "rule text: no dated marker, no timeline — prose")
                close_details()
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
                page.evaluate("""() => { window.PB_LOGIC.slices = { orders: { writers: ['saveOrder'], readers: ['showList'] }, notes: { writers: ['saveNote'], readers: ['showList'] } };
                  window.PB_LOGIC.handlers = ['saveOrder', 'saveNote', 'showList'].map(n => ({ name: n, file: 'runtime/' + n + '.js', line: 1, length: 3, isSave: false, exported: false, slices: [], owners: [], writes: [] })); }""")
                page.evaluate("pbLogicGo('slice', 'orders')")
                page.wait_for_timeout(100)
                check(q(".lg-ripple .lgi-graph svg") == 1 and q(".lgi-graph.is-focus") == 1, "Impact: a writers → slices → readers graph, lit for the picked slice")
                lit1 = page.evaluate("[...document.querySelectorAll('.lgi-graph .lgi-g:not(.lgi-g--dim)')].map(g => g.textContent.trim()).filter(Boolean).join('|')")
                page.evaluate("pbLogicGo('slice', 'notes')")
                page.wait_for_timeout(100)
                lit2 = page.evaluate("[...document.querySelectorAll('.lgi-graph .lgi-g:not(.lgi-g--dim)')].map(g => g.textContent.trim()).filter(Boolean).join('|')")
                check("store.orders" in lit1 and "store.notes" not in lit1 and "store.notes" in lit2 and lit1 != lit2, f"Impact: the highlight follows the focus ({lit1} → {lit2})")
                check(page.evaluate("document.querySelectorAll('.lgi-graph .lgi-g').length") < 40, "Impact: the graph stays bounded")
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
                open_details("cycle-status")
                pw_ = page.evaluate("document.querySelector('#lgc-drawer .lgc-dpanel').getBoundingClientRect().width")
                check(abs(pw_ - 390) <= 1, f"the drawer is full width under 600px ({pw_}px)")
                check(page.evaluate("(e => e.scrollWidth - e.clientWidth)(document.querySelector('#lgc-drawer .lgc-dbody'))") <= 1, "…and does not overflow sideways")
                close_details()
                # leaving the tab closes it: the drawer belongs to the Logic page
                open_details("cycle-status")
                page.evaluate("setMetaView('summary')"); page.wait_for_timeout(350)
                check(not page.locator(f"{dr} .lgc-dpanel").is_visible(), "the drawer closes when another top-level tab is chosen")
                browser.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if FAIL:
        print("\n✗ %d failure(s)" % len(FAIL))
        sys.exit(1)
    print("\n✓ rule blocks: checked by logic_check, drawn as components by the shell")


if __name__ == "__main__":
    main()
