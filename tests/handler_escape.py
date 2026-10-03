#!/usr/bin/env python3
"""
handler_escape.py — a registry value never becomes code through an inline handler (round 3 · F1 · M1).

The shell used to carry a registry value to its click handlers as a quoted JS string inside the
attribute:  onclick="pbLogicGo('item','${pbEscape(id)}')".  pbEscape turns ' into &#39; — which is
right for the HTML parser and useless against the JS one: the HTML parser DECODES the attribute first,
so the handler's source reads  pbLogicGo('item','x');alert(1);//')  and runs. Any id, name or label a
project (or a hand-off recipient, or an imported bundle) controls could execute in the viewer's page.

The fix carries the value as DATA — data-x="${escapeHtmlAttr(v)}" with onclick="f(this.dataset.x)" — so
the handler's source is constant. This file pins it from three sides:

  1. static     the shell has no inline handler that interpolates a value into a quoted JS string
                (the only `${…}` allowed in a handler is a code-side function name or a loop index)
  2. end to end a project whose job, rule, term, entity, variant, screen, component and property ids are
                BOTH payloads — `');window.__pwn=1;//` and `"><img src=x onerror=window.__pwn=1>` — is
                rendered; every control that carries one is activated; `window.__pwn` stays undefined, no
                dialog opens, no page error is thrown, and the handler still receives the EXACT string
                (the round trip is lossless — a fix that merely stopped the attack by mangling the id
                would fail here)
  3. builders   a control whose value cannot reach it through a registry (a nav id is [\\w-]+ only; a
                handler name is a code identifier) is built directly with the payload and activated

`--shell <path>` renders another copy of the shell — the negative control: run against the shell as it
was before the fix, this file must FAIL (it does; that is how it was shown to bite).

Usage:  .venv/bin/python tests/handler_escape.py [--shell path/to/prototype.html]
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
SHELL = os.path.join(TPL, "prototype.html")
if "--shell" in sys.argv:
    SHELL = os.path.abspath(sys.argv[sys.argv.index("--shell") + 1])

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


# ── 1 · static ────────────────────────────────────────────────────────────────────────────────

# An inline handler attribute whose value interpolates `${…}`. The ONLY interpolations allowed are the
# ones below — a code-side function name (`${onclick}(…)`, `${fn}(…)`) or a loop index (`[${i}]`).
_HANDLER = re.compile(r"""\bon[a-z]+\s*=\s*"([^"]*\$\{[^"]*)"|\bon[a-z]+\s*=\s*'([^']*\$\{[^']*)'""", re.S)
_ALLOWED = (re.compile(r"^\$\{(?:onclick|fn)\}\(this\.dataset\.\w+\)"),            # ${fn}(this.dataset.x)
            re.compile(r"^pbRunScenarios\(\[\$\{i\}\]\)$"),                          # a numeric index
            re.compile(r"^pbFlowHighlight\(\$\{i\}, (?:true|false)\)$"),
            re.compile(r"^pbRunScenarios\(\[\$\{i\}\]\)$"))


def static_scan(src):
    bad = []
    for m in _HANDLER.finditer(src):
        body = (m.group(1) or m.group(2)).strip()
        if any(a.match(body) for a in _ALLOWED):
            continue
        line = src.count("\n", 0, m.start()) + 1
        bad.append(f"line {line}: {body[:90]}")
    # a handler built by string concatenation (the anatomy link): onclick="…(\'' + x + '\')"
    for m in re.finditer(r"""on[a-z]+=\\?"[^"]*\\'\s*'\s*\+""", src):
        bad.append(f"line {src.count(chr(10), 0, m.start()) + 1}: string-concatenated handler")
    for m in re.finditer(r"""on[a-z]+="[^"]*\(\\''\s*\+""", src):
        bad.append(f"line {src.count(chr(10), 0, m.start()) + 1}: string-concatenated handler")
    return bad


# ── 2 · the project ───────────────────────────────────────────────────────────────────────────

P1 = "');window.__pwn=1;//"
P2 = '"><img src=x onerror=window.__pwn=1>'
# Every id carries one of the two, and two of each kind exist so both break-outs are exercised.
JOB1, JOB2 = "j1" + P1, "j2" + P2
RULE1, RULE2 = "r1" + P1, "r2" + P2
ENT1, ENT2 = "Ent1" + P1, "Ent2" + P2
VAR1, VAR2 = "var1" + P1, "var2" + P2
SCR1, SCR2 = "s1" + P1, "s2" + P2
CMP1, CMP2 = "c1" + P1, "c2" + P2
PROP1, PROP2 = "p1" + P1, "p2" + P2
OPT1, OPT2 = "o1" + P1, "o2" + P2
ENF = "enf" + P1


def build_project(tmp):
    proj = os.path.join(tmp, "proj")
    os.makedirs(os.path.join(proj, "render", "screens"))
    os.makedirs(os.path.join(proj, "render", "components"))

    def body(path, text):
        with open(os.path.join(proj, path), "w", encoding="utf-8") as f:
            f.write(text)

    screens = []
    for i, sid in enumerate(("home", SCR1, SCR2)):
        fn = "renderScreenPay%d" % i
        screens.append({"id": sid, "name": "Screen %d" % i, "renderFn": fn, "level": "page",
                        "renderSrc": "render/screens/pay%d.js" % i, "elements": []})
        body("render/screens/pay%d.js" % i, "return '<main class=\"pay\">screen %d</main>';\n" % i)
    comps = []
    for i, (cid, pid, oid) in enumerate(((CMP1, PROP1, OPT1), (CMP2, PROP2, OPT2))):
        comps.append({"id": cid, "name": "Comp %d" % i, "renderFn": "renderCmpPay%d" % i, "scope": "local", "level": "atom",
                      "renderSrc": "render/components/pay%d.js" % i,
                      "properties": [{"id": pid, "type": "enum", "default": oid,
                                      "options": [{"label": "One", "value": oid}, {"label": "Two", "value": "two" + P2}]},
                                     {"id": "free" + P1, "type": "string", "default": "x"}],
                      "code": {"lang": "html", "snippet": "<b>x</b>"}})
        body("render/components/pay%d.js" % i, "return '<span class=\"pay\">c%d</span>';\n" % i)

    base = {"when": "something happens", "want": "to do the thing", "so": "the outcome follows"}
    jobs = [dict(base, id=JOB1, title="Job one", priority="P0", roles=["admin"], screens=[]),
            dict(base, id=JOB2, title="Job two", priority="P1", roles=["admin"], screens=[]),
            dict(base, id="jok", title="Job three", priority="P1", roles=["admin"], screens=["home"])]
    rules = [{"id": RULE1, "title": "Rule one", "kind": "decision", "summary": "A rule.",
              "invariants": [{"must": "hold", "enforcedBy": ENF}],
              "decision": {"question": "A or B?", "options": ["A", "B"], "chose": "A", "why": "Simpler."}},
             {"id": RULE2, "title": "Rule two", "kind": "constraint", "summary": "Another rule."}]
    reg = {
        "meta": {"name": "handler-escape", "schemaVersion": 12, "device": "laptop", "devices": ["laptop"],
                 "roles": [{"id": "admin", "name": "Admin", "isAdmin": True}], "defaultRole": "admin",
                 "overview": {"objectives": "x", "principles": []}, "userInsights": {}},
        "tokens": {}, "components": comps, "screens": screens, "staleness": {},
        "flow": {"populated": False}, "runtime": [],
        "ia": {"populated": True, "jobs": jobs, "rules": rules},
        "erd": {"populated": True, "mermaid": "erDiagram\n  A ||--o{ B : has",
                "table": [{"entity": e, "field": "id", "type": "identifier", "example": "x", "notes": "PK"} for e in (ENT1, ENT2)],
                "warnings": [],
                "mock": [{"entity": e, "label": v, "rows": [{"id": "1"}]} for e, v in ((ENT1, VAR1), (ENT2, VAR2), (ENT1, VAR2))]},
        "content": {"terms": [{"id": "t1", "term": "Term one", "definition": "d", "rule": RULE1},
                              {"id": "t2", "term": "Term two", "definition": "d", "rule": RULE2}], "strings": []},
    }
    path = os.path.join(proj, "registry.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False)
    return path


PWN = "window.__pwn"


class Probe:
    """Activates controls and asserts the payload never ran."""

    def __init__(self, pg, errs, dialogs):
        self.pg, self.errs, self.dialogs, self.n = pg, errs, dialogs, 0

    def pwned(self):
        return self.pg.evaluate("typeof %s !== 'undefined'" % PWN)

    def settle(self):
        self.pg.wait_for_timeout(90)

    def idx(self, selector, text):
        """Index of the first control matching `selector` whose visible text starts with `text` — found by what
        it SAYS, not by any attribute this fix introduced, so the same probe runs against the old shell."""
        return self.pg.evaluate("([s, t]) => [...document.querySelectorAll(s)].findIndex(e => e.textContent.trim().startsWith(t))", [selector, text])

    def activate(self, selector, what, expect=None, nth=None, limit=40, allow_none=False):
        """Click every element matching `selector` (re-queried each time — a click re-renders).
        `expect` is a JS expression that must be true after EACH click, given the element's index `i`."""
        cnt = self.pg.evaluate("(s) => document.querySelectorAll(s).length", selector)
        if nth is not None:
            idxs = [nth]
        else:
            idxs = list(range(min(cnt, limit)))
        if not idxs or cnt == 0:
            if not allow_none:
                check(False, f"{what}: found no control matching {selector}")
            return 0
        ok_run, ok_val = True, True
        for i in idxs:
            self.pg.evaluate("([s, i]) => { const e = document.querySelectorAll(s)[i]; if (e) e.click(); }", [selector, i])
            self.settle()
            self.n += 1
            if self.pwned():
                ok_run = False
                self.pg.evaluate("delete %s" % PWN)
            if expect is not None and not self.pg.evaluate(expect):
                ok_val = False
        check(ok_run, f"{what}: {len(idxs)} control(s) activated — nothing ran")
        if expect is not None:
            check(ok_val, f"{what}: …and the handler received the exact id (`{expect[:70]}`)")
        return len(idxs)


def js(s):
    return json.dumps(s)


def end_to_end(pg, errs, dialogs):
    pr = Probe(pg, errs, dialogs)
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.evaluate("setMetaView('flow')")

    # tabs, sub-tabs: constants, but converted too — and they must still switch
    pr.activate(".pb-tabs .meta-tab", "the top tabs")
    pg.evaluate("setMetaView('flow')")
    print("  — UX Design · Information Architecture")
    pg.evaluate("pbSetUxView('ia')")
    pg.wait_for_timeout(150)
    # rows are disclosures; open them so their actions exist
    pg.evaluate("document.querySelectorAll('[data-fb-list=\"ia\"] .pb-disc-t').forEach(b => b.click())")
    pg.wait_for_timeout(120)
    n = pg.evaluate("document.querySelectorAll('[data-fb-list=\"ia\"] .pb-tags button').length")
    check(n >= 4, f"the two jobs with no screen each carry Plan a screen + Fold into… ({n} command buttons)")
    pr.activate("[data-fb-list=\"ia\"] .pb-tags button", "IA job actions (Plan a screen / Fold into…)")
    toast = pg.evaluate("[...document.querySelectorAll('.sync-toast')].map(t => t.textContent).join('|')")
    check(("--ia " + JOB2) in toast or ("--ia " + JOB1) in toast,
          "…and the command reaches the clipboard with the id verbatim (the toast reads it back)")
    pr.activate(".ux-subtabs .meta-subtab", "the UX Design sub-tabs")

    print("  — UX Design · Logic")
    pg.evaluate("pbSetUxView('logic')")
    pg.wait_for_timeout(150)
    pg.evaluate("pbSetLogicView('ripple')")
    pg.wait_for_timeout(150)
    rows = pg.evaluate("document.querySelectorAll('.logic-row').length")
    check(rows >= 3, f"the ripple list has a row per screen ({rows})")
    for cid in (SCR1, SCR2, "home"):
        sel_i = pr.idx(".logic-row", cid)
        if sel_i < 0:
            check(False, f"a Logic row exists for the id {cid[:14]}…")
            continue
        pr.activate(".logic-row", f"Logic row `{cid[:12]}…`", nth=sel_i,
                    expect=f"state.logicFocus.id === {js(cid)} && state.logicFocus.type === 'item'")
        # the detail pane lists links (pbLgLink) to the item's neighbours — activate those too
        pr.activate(".lg-detail a.lg-link", f"links in the detail of `{cid[:12]}…`", limit=20, allow_none=True)
        pg.evaluate("pbSetLogicView('ripple')")
    pg.evaluate("pbSetLogicView('rules')")
    pg.wait_for_timeout(150)
    pg.evaluate("document.querySelectorAll('.pb-scan--logic .pb-disc-t').forEach(b => b.click())")
    pg.wait_for_timeout(120)
    pr.activate(".lg-link", "links on the rule cards (an invariant's `enforcedBy` is a registry string)", limit=20)
    pr.activate(".meta-subtab, .lg-view", "the Logic sub-views", limit=12)

    print("  — UX Design · Content")
    pg.evaluate("pbSetUxView('content'); pbSetContentView('terms')")
    pg.wait_for_timeout(150)
    for rid, title in ((RULE1, "Rule one"), (RULE2, "Rule two")):
        i = pr.idx("a.ct-rule", title)
        if i < 0:
            check(False, f"a glossary link to the rule {rid[:12]}… exists")
            continue
        pr.activate("a.ct-rule", f"glossary link → rule `{rid[:12]}…`", nth=i,
                    expect=f"state.logicView === 'rules' && state.uxView === 'logic'")
        pg.evaluate("pbSetUxView('content'); pbSetContentView('terms')")
        pg.wait_for_timeout(120)

    print("  — Data")
    pg.evaluate("setMetaView('erd')")
    pg.wait_for_timeout(150)
    pr.activate(".meta-subtabs--view .meta-subtab", "the Diagram | Table toggle")
    pg.evaluate("setErdView('table')")
    pg.wait_for_timeout(200)
    # (entity, variant) for every chip, by position — the entity is the table the chip sits in
    chips = pg.evaluate("""[...document.querySelectorAll('.pb-mock-chip')].map(c => [c.closest('.erd-entity').dataset.entity, c.textContent.trim()])""")
    check(len(chips) >= 5, f"each entity with data sets has a Schema chip and one per variant ({len(chips)})")
    for k, (ent, var) in enumerate(chips):
        if var == "Schema":
            want = "'schema'"
        else:
            want = js(var)
        pr.activate(".pb-mock-chip", f"variant chip #{k} `{ent[:10]}… / {var[:10]}…`", nth=k,
                    expect=f"state.erdVariant[{js(ent)}] === {want}")
        pg.evaluate("setErdView('table')")

    print("  — Prototype · the Structure tree")
    pg.evaluate("setMetaView('prototype')")
    pg.wait_for_timeout(200)
    pg.evaluate("toggleProtoStructPanel()")
    pg.wait_for_timeout(200)
    for sid, name in ((SCR1, "Screen 1"), (SCR2, "Screen 2"), ("home", "Screen 0")):
        i = pr.idx(".pb-tree-page", name)
        if i < 0:
            check(False, f"the tree lists the screen {sid[:12]}…")
            continue
        pr.activate(".pb-tree-page", f"tree row `{sid[:12]}…`", nth=i, expect=f"state.protoScreenId === {js(sid)}")
        if not pg.evaluate("!!document.querySelector('.pb-tree-page')"):
            pg.evaluate("toggleProtoStructPanel()")
            pg.wait_for_timeout(150)

    print("  — The component workbench (renderHandoff — no tab opens it any more, but it is shipped code)")
    pg.evaluate("PB_DATA.handoff.view = 'component'; state.handoffDrawerOpenFor = null; state.uidScreenSel = null; renderHandoff()")
    pg.wait_for_timeout(200)
    for cid, pid, name in ((CMP1, PROP1, "Comp 0"), (CMP2, PROP2, "Comp 1")):
        i = pr.idx(".uid-row", name)
        if i < 0:
            check(False, f"the list has a row for {cid[:12]}…")
            continue
        pr.activate(".uid-row", f"component list row `{cid[:12]}…`", nth=i, expect=f"state.handoffDrawerOpenFor === {js(cid)}")
        # its property controls: pick every option, edit the free-text value
        sels = pg.evaluate("document.querySelectorAll('select.ci-select:not(.pb-cm-select), select.prop-select').length")
        for k in range(sels):
            opts = pg.evaluate("(k) => [...document.querySelectorAll('select.ci-select:not(.pb-cm-select), select.prop-select')[k].options].map(o => o.value)", k)
            for val in opts:
                pg.evaluate("([k, v]) => { const s = document.querySelectorAll('select.ci-select:not(.pb-cm-select), select.prop-select')[k]; s.value = v; s.dispatchEvent(new Event('change', {bubbles: true})); }", [k, val])
                pr.settle()
                pr.n += 1
                check(not pr.pwned(), f"select #{k} = `{val[:10]}…`: nothing ran")
                pg.evaluate("delete %s" % PWN)
                got = pg.evaluate("(a) => (handoffProps[a[0]] || {})[a[1]]", [cid, pid])
                check(got == val, f"…and setHandoffProp stored the exact value under the exact ids ({got!r})")
                if pg.evaluate("document.querySelectorAll('select.ci-select:not(.pb-cm-select), select.prop-select').length") <= k:
                    break
        pg.evaluate("renderHandoff()")
        for k in range(pg.evaluate("document.querySelectorAll('input.ci-input').length")):
            pg.evaluate("(k) => { const e = document.querySelectorAll('input.ci-input')[k]; e.value = 'typed'; e.dispatchEvent(new Event('change', {bubbles: true})); }", k)
            pr.settle()
            pr.n += 1
        check(not pr.pwned(), "free-text property inputs: nothing ran")
        pr.activate(".pb-pg-reset, .handoff-copy-code-btn, .handoff-drawer-segment", "reset / copy-code / drawer segments", limit=10)
    pr.activate(".handoff-drawer-segment", "drawer segments", limit=6, allow_none=True)
    # the cards view
    pg.evaluate("setHandoffView('component'); state.handoffDrawerOpenFor = null; renderHandoff()")
    pr.activate(".handoff-card, .prop-select, .handoff-copy-code-btn", "component cards", limit=12)

    check(pg.evaluate("typeof %s === 'undefined'" % PWN), "after all of it, window.__pwn is still undefined")
    check(dialogs == [], f"no alert()/confirm() was raised ({dialogs[:2]})")
    check(errs == [], f"no page error was thrown ({errs[:2]})")
    return pr.n


def builders(pg, errs, dialogs):
    """Controls whose value cannot be reached through a registry — built directly with the payload."""
    print("3 · builders fed a payload directly")
    pg.evaluate("setMetaView('flow'); pbSetUxView('logic')")
    pg.wait_for_timeout(200)
    for p in (P1, P2, "a'b\"c<d>&amp;"):
        pg.evaluate("document.getElementById('hx') && document.getElementById('hx').remove()")
        pg.evaluate("""(p) => { const d = document.createElement('div'); d.id = 'hx'; document.body.appendChild(d);
          d.innerHTML = pbIaGoBtn(p) + pbLgLink('handler', p, 'h') + pbLgLink('slice', p, 's')
            + (typeof pbRenderHandoffCode === 'function' ? pbRenderHandoffCode({ id: p, code: { snippet: 'x' } }) : ''); }""", p)
        got = pg.evaluate("""(p) => { const out = []; const orig = window.pbLogicGo;
          window.pbLogicGo = (t, id) => { out.push([t, id]); };
          document.querySelectorAll('#hx button.ia-node-go, #hx a.lg-link').forEach(e => e.click());
          window.pbLogicGo = orig; return out; }""", p)
        check(not pg.evaluate("typeof window.__pwn !== 'undefined'"), f"builder probe {p[:14]!r}: nothing ran")
        check([g[1] for g in got] == [p, p, p], f"…and pbLogicGo received the exact string each time ({len(got)} calls)")
        pg.evaluate("delete window.__pwn")
    pg.evaluate("document.getElementById('hx') && document.getElementById('hx').remove()")
    # the anatomy table link (string-built): openHandoffDrawer must get the exact id
    has = pg.evaluate("typeof pbRenderAnatomy === 'function'")
    if has:
        check(True, "pbRenderAnatomy present (its link is covered by the static scan)")


def main():
    print("1 · static — no handler interpolates a value into a JS string")
    src = open(SHELL, encoding="utf-8").read()
    bad = static_scan(src)
    check(not bad, "inline handlers carry only constants, code-side names and indices" + ("" if not bad else f" — {len(bad)} do not"))
    for b in bad[:12]:
        print("      " + b)
    check(not re.search(r"""onclick="[^"]*\('\$\{""", src), "…no onclick=\"…('${…\" remains (the grep the brief names)")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright not installed (pip install playwright && playwright install chromium)")
        sys.exit(2)

    render = _load("render", os.path.join(TOOLS, "render.py"))
    tmp = tempfile.mkdtemp()
    try:
        reg_path = build_project(tmp)
        out = os.path.join(tmp, "p.html")
        render.render_file(reg_path, SHELL, out)
        with sync_playwright() as pw:
            try:
                br = pw.chromium.launch()
            except Exception as e:  # noqa: BLE001
                print(f"SKIP: could not launch Chromium ({e})")
                sys.exit(2)
            c = br.new_context(viewport={"width": 1440, "height": 900})
            c.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:"))
                    else r.fulfill(status=200, body="", content_type="text/plain"))
            c.add_init_script("try { navigator.clipboard.writeText = () => Promise.resolve(); } catch (e) {}")   # headless has no clipboard grant
            pg = c.new_page()
            errs, dialogs = [], []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
            pg.goto("file://" + out, wait_until="domcontentloaded")
            pg.wait_for_selector(".pb-product", state="attached", timeout=10000)
            pg.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
            pg.wait_for_timeout(300)
            print("\n2 · end to end — every control that carries a registry id, with a payload id")
            n = end_to_end(pg, errs, dialogs)
            print(f"  ({n} activations)")
            builders(pg, errs, dialogs)
            check(pg.evaluate("typeof window.__pwn === 'undefined'"), "window.__pwn is undefined at the end")
            br.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if _fail:
        print(f"✗ {len(_fail)} handler-escape failure(s):")
        for f in _fail:
            print(f"    - {f}")
        sys.exit(1)
    print("✓ handler-escape: clean")


if __name__ == "__main__":
    main()
