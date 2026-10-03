#!/usr/bin/env python3
"""
tradeoff_rules.py — schema 12 (D-33): a trade-off is a rule, so it is stored as one.

  1. 0010 up() converts each meta.tradeoffs[] entry into an ia.rules[] rule carrying a
     decision{} block, reads a [SUPERSEDED …] title prefix into decision.status, and EMPTIES
     meta.tradeoffs rather than removing it (AGENTS.md §3).
  2. down() restores the array byte-for-byte; a rule edited since the migration is kept as a
     rule and reported, never demoted back into a flat row.
  3. 0010 is in the chain, the chain reaches CURRENT_SCHEMA (12 or later — this file owns 0010,
     not the current schema number) and the shipped template carries the new shape.
  4. The rendered shell draws the decision on the rule card — question, what won, what LOST,
     why — for any kind, and dims a superseded one in place.
  5. There is no Trade-offs view and no Others sub-tab left to click.
  6. A project that has NOT migrated still sees its trade-offs, under a banner naming the
     command that converts them. A retirement that hides someone's decisions is a deletion.

Browser assertions need Playwright (dev/CI-only, same as the other browser suites); without it
the pure-Python half still runs and the browser half is skipped.

Usage:  python3 tests/tradeoff_rules.py
Exit:   0 = all passed · 1 = a failure
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
MIG = os.path.join(ROOT, "pb", "migrations", "0010_tradeoff_rules.py")
MANIFEST = os.path.join(ROOT, "pb", "migrations", "manifest.py")
TEMPLATE = os.path.join(ROOT, "pb", "template", "registry.template.json")
SHELL = os.path.join(ROOT, "pb", "template", "prototype.html")

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TRADEOFFS = [
    {"title": "Inline vs. on-submit validation", "question": "When do we validate?",
     "options": "Inline | On submit", "decision": "Inline",
     "why": "Catches errors before the user commits.", "tabsAffected": "Prototype, UX Design"},
    {"title": "[SUPERSEDED 2026-08-10] Weights are per cycle", "question": "Where do weights live?",
     "options": "Per cycle | Per goal", "decision": "Per cycle", "why": "One pool to total."},
]


def reg_with_tradeoffs():
    return {"meta": {"schemaVersion": 11, "tradeoffs": json.loads(json.dumps(TRADEOFFS))},
            "ia": {"populated": False}}


def test_migration():
    m = _load(MIG, "m0010")
    print("1 · up — a trade-off becomes a rule that carries its decision")
    up = m.up(reg_with_tradeoffs())
    rules = (up.get("ia") or {}).get("rules") or []
    check(len(rules) == 2, f"both trade-offs became rules ({len(rules)})")
    r = rules[0]
    check(r.get("kind") == "decision" and r.get("origin") == "tradeoff",
          f"kind 'decision', stamped with its origin ({r.get('kind')}, {r.get('origin')})")
    d = r.get("decision") or {}
    check(d.get("question") == "When do we validate?" and d.get("chose") == "Inline"
          and d.get("why", "").startswith("Catches"),
          "the question, what won and why all survive")
    check(d.get("options") == ["Inline", "On submit"],
          f"and what LOST is a list, not a pipe-string ({d.get('options')})")
    sup = (rules[1].get("decision") or {})
    check(sup.get("status") == "superseded" and sup.get("supersededOn") == "2026-08-10",
          f"a [SUPERSEDED <date>] title becomes decision.status ({sup.get('status')}, {sup.get('supersededOn')})")
    check(rules[1]["title"] == "Weights are per cycle", f"and the title comes out clean ({rules[1]['title']!r})")
    check(up["meta"].get("tradeoffs") == [] and "tradeoffs" in up["meta"],
          "meta.tradeoffs is EMPTIED, not removed — AGENTS.md §3")
    check(up["meta"]["schemaVersion"] == 12, "stamped schema 12")
    check(m.up({"meta": {"schemaVersion": 11}}) == {"meta": {"schemaVersion": 12}},
          "a registry that never had the field does not grow one")

    print("2 · down — the array comes back, and work done since does not")
    orig = reg_with_tradeoffs()
    back = m.down(m.up(json.loads(json.dumps(orig))))
    check(back == orig, "round-trip is byte-for-byte identical")
    edited = m.up(reg_with_tradeoffs())
    edited["ia"]["rules"][0]["kind"] = "constraint"          # worked on since the migration
    edited["ia"]["rules"][0]["invariants"] = [{"must": "every field validates on blur"}]
    d2 = m.down(edited)
    kept = [x for x in (d2.get("ia") or {}).get("rules", []) if x.get("kind") == "constraint"]
    check(len(kept) == 1, "a rule edited since the migration is KEPT as a rule")
    check(len(d2["meta"]["tradeoffs"]) == 1, "and only the untouched one is demoted back")

    print("3 · the chain and the shipped template")
    mf = _load(MANIFEST, "manifest")
    check(mf.CURRENT_SCHEMA >= 12, f"CURRENT_SCHEMA is at least 12, 0010's target (got {mf.CURRENT_SCHEMA})")
    check(max(t for _f, t, _s in mf._REGISTRY) == mf.CURRENT_SCHEMA, "the chain reaches CURRENT_SCHEMA")
    check((11, 12, "0010_tradeoff_rules") in mf._REGISTRY, "0010 is wired into the chain")
    tpl = json.load(open(TEMPLATE, encoding="utf-8"))
    check(tpl["meta"]["schemaVersion"] == mf.CURRENT_SCHEMA,
          f"the template is stamped CURRENT_SCHEMA ({tpl['meta']['schemaVersion']} vs {mf.CURRENT_SCHEMA})")
    check("tradeoffs" not in tpl["meta"] and "others" not in tpl["meta"],
          "a NEW project is not born with either retired field")
    check(tpl.get("ia", {}).get("rules") == [], "and is born with ia.rules[]")

    src = open(SHELL, encoding="utf-8").read()
    check("pbRenderTradeoffs" not in src and "pbRenderOthers" not in src,
          "the two retired renderers are gone from the shell, not stubbed")


RULE = {"id": "validation-timing", "title": "Validation timing", "kind": "decision",
        "summary": "Inline, on blur, per field.",
        "decision": {"question": "When do we validate?", "options": ["Inline", "On submit"],
                     "chose": "Inline", "why": "Catches errors before the user commits.",
                     "affects": "Prototype"}}
SUP_RULE = {"id": "weights", "title": "Weights are per cycle", "kind": "decision",
            "summary": "Per cycle.",
            "decision": {"chose": "Per cycle", "why": "One pool to total.",
                         "status": "superseded", "supersededOn": "2026-08-10"}}


def _fixture(tmp, golden, migrated):
    shutil.copytree(os.path.join(os.path.dirname(golden), "render"), os.path.join(tmp, "render"))
    reg = json.load(open(golden, encoding="utf-8"))
    if migrated:
        reg["meta"]["tradeoffs"] = []
        reg["ia"] = {"rules": [RULE, SUP_RULE]}
    else:
        reg["meta"]["tradeoffs"] = json.loads(json.dumps(TRADEOFFS))
    path = os.path.join(tmp, "registry.json")
    json.dump(reg, open(path, "w", encoding="utf-8"), indent=2)
    return path


def test_shell():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n(browser half skipped — Playwright not installed)")
        return
    from e2e_smoke import GOLDEN, Server, _offline  # noqa: E402

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:
            print(f"\n(browser half skipped — Chromium unavailable: {e})")
            return

        def open_logic(page, url):
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector("#proto-frame", timeout=15000)
            page.evaluate("setMetaView('flow'); state.uxView = 'logic'; renderMetaFlow()")
            page.wait_for_timeout(500)

        print("4 · the rendered rule card carries its decision")
        with tempfile.TemporaryDirectory() as tmp:
            with Server(_fixture(tmp, GOLDEN, True)) as srv:
                page = browser.new_page(viewport={"width": 1500, "height": 1000})
                _offline(page)
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                open_logic(page, srv.url)
                # The decision is the History tab's latest entry (v2.1.0 rule card) — read its text
                # whether or not the tab is the one open.
                body = page.eval_on_selector("#app", "e => e.textContent")
                check("When do we validate?" in body, "the question renders")
                won = page.eval_on_selector_all(".lgc-opts li.lgc-on", "e => e.map(x => x.textContent)")
                lost = page.eval_on_selector_all(".lgc-opts li:not(.lgc-on)", "e => e.map(x => x.textContent)")
                check(any("Inline" in x for x in won) and any("On submit" in x for x in lost),
                      "what won is shown beside what LOST — the part a rule cannot say for itself")
                check("Catches errors before the user commits." in body, "and the why")
                sup = page.locator(".lg-card--sup")
                srow = page.locator(".pb-scan-tr.is-dim")
                check(sup.count() == 1 and "superseded" in sup.locator(".lgc-supnote").text_content()
                      and srow.count() == 1 and "Superseded" in srow.locator(".st").text_content(),
                      "a superseded decision stays in place — a dimmed row saying Superseded, whose card carries a superseded pill — rather than disappearing")

                print("5 · nothing left to click that no longer exists")
                views = page.eval_on_selector_all(".lg-view", "e => e.map(x => x.innerText.split(' ')[0])")
                check(views == ["Rules", "Impact"], f"Logic has two views, not three ({views})")
                check("2" in page.eval_on_selector(".lg-view", "e => e.innerText"),
                      "and the Rules count includes them")
                page.evaluate("setMetaView('summary')")
                page.wait_for_timeout(350)
                subs = page.eval_on_selector_all(".meta-subtab", "e => e.map(x => x.innerText.trim())")
                check(subs == ["Overview", "User Insights"],
                      f"Project Summary is Overview + User Insights, and nothing else ({subs})")
                check(not errs, f"zero console errors ({errs})")
                page.close()

        print("6 · a project that has not migrated keeps seeing its decisions")
        with tempfile.TemporaryDirectory() as tmp:
            with Server(_fixture(tmp, GOLDEN, False)) as srv:
                page = browser.new_page(viewport={"width": 1500, "height": 1000})
                _offline(page)
                errs = []
                page.on("pageerror", lambda e: errs.append(str(e)))
                page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                open_logic(page, srv.url)
                body = page.eval_on_selector("#app", "e => e.innerText")
                check(page.locator(".pb-qa-warn-head").count() == 1,
                      "a banner names the retired field")
                check("/pb:update-version" in body, "and the one command that converts them")
                check("When do we validate?" in body and "over On submit" in body,
                      "the trade-offs still render, through the same decision renderer")
                check(page.locator(".lg-card").count() == 2, "one card each, unchanged")
                check(not errs, f"zero console errors ({errs})")
                page.close()
        browser.close()


def main():
    test_migration()
    test_shell()
    print()
    if fails:
        print(f"✗ {len(fails)} assertion(s) failed.")
        sys.exit(1)
    print("✓ trade-offs are rules — migration, render and the unmigrated path all hold.")


if __name__ == "__main__":
    main()
