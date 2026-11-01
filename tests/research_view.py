#!/usr/bin/env python3
"""
research_view.py — Project Summary → Research, and the cross-links to it, measured in a browser.

The `research` slice (studies, their hypotheses, findings, instrument and evidence list) is drawn
by the shell as a third Project Summary sub-tab. This test builds its own synthetic registry (no
dependency on pb/tools/research.py) and checks, in Chromium:

  1. the tab         a third sub-tab, Research; a project with only research still shows the tab
  2. the rows        a study is a disclosure row, closed until opened; several open at once; the row
                     carries a verdict tally, the opened study its hypotheses with verdict badges
  3. the findings    quotes (participant + evidence id) and counted / mean stats
  4. the evidence    a table of what is kept on disk; a withdrawn file struck out with its reason
  5. the instrument  closed by default, read-only, opens to the questions
  6. escaping        a quote holding <script> is text; nothing from the registry becomes markup
  7. the links       `[rs-…]` in Insights jumps to the study (an unknown id stays text; Insights keeps
                     its three h3s); a job row and a rule's drawer list the Evidence that names them
  8. ⌘K              a study and a finding are found
  9. empty           no studies: the shared empty state with the `/pb:research` CTA; no `research` key
                     renders as before
 10. no JS errors

Usage:  .venv/bin/python tests/research_view.py
        RESEARCH_SHOTS=<dir> .venv/bin/python tests/research_view.py   (also writes light/dark screenshots)
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import copy
import importlib.util
import json
import os
import shutil
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
FREEZE = "*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}"

XSS = "<script>window.__xss=1</script>"
IMG = "<img src=x onerror=\"window.__xss=2\">"
GONE = "Participant asked to withdraw"
VI_TITLE = "Người giao hàng có cần màn hình đầu tiên không?"

STUDY_A = {
    "id": "rs-cod-payment",
    "title": "Do couriers need COD on the first screen?",
    "question": "Do rural couriers look for cash-on-delivery before anything else?",
    "method": "survey", "status": "analysed", "createdAt": "2026-11-01T10:00:00Z",
    "audience": {"roles": ["member"], "segment": "rural, under 1 year on the job", "targetN": 30},
    "targets": [{"kind": "job", "id": "pay-cod"}, {"kind": "rule", "id": "cod-first"}, {"kind": "feature", "id": "wallet"}],
    "hypotheses": [
        {"id": "h1", "statement": "Couriers open COD first", "supportedIf": "most pick COD", "refutedIf": "most pick another",
         "targets": [{"kind": "job", "id": "pay-cod"}], "verdict": "supported", "why": "18 of 30 chose it"},
        {"id": "h2", "statement": "Couriers read the fee " + IMG, "supportedIf": "mean above 3", "refutedIf": "mean below 3",
         "targets": [], "verdict": "refuted", "why": ""},
        {"id": "h3", "statement": "Couriers notice the badge", "supportedIf": "x", "refutedIf": "y", "targets": [], "verdict": None, "why": ""},
    ],
    "instrument": {"lang": "en", "intro": "A short survey about paying.", "consent": "Answers are anonymous.", "durationMin": 5, "closing": "Thanks.",
                   "sections": [
                       {"title": "Who you are", "purpose": "screener", "questions": [
                           {"id": "q1", "text": "Do you deliver parcels?", "tests": [], "type": "single", "options": ["Yes", "No"], "qualifies": ["Yes"]}]},
                       {"title": "Paying", "purpose": "main", "questions": [
                           {"id": "q2", "text": "Which do you open first?", "tests": ["h1"], "type": "single", "options": ["COD", "Wallet"]},
                           {"id": "q5", "text": "How easy is the fee to read?", "tests": ["h2"], "type": "scale",
                            "scale": {"min": 1, "max": 5, "minLabel": "hard", "maxLabel": "easy"}}]}]},
    "evidence": [
        {"id": "e1", "file": "memory/research/rs-cod-payment/evidence/e1-responses.csv", "kind": "responses", "sha256": "a1b2c3d4e5f60718",
         "importedAt": "2026-11-05T08:00:00Z", "date": "2026-11-05", "participant": "", "role": "member", "consent": "yes", "responses": 34, "droppedColumns": ["Email"], "dropped": None},
        {"id": "e2", "file": "memory/research/rs-cod-payment/evidence/e2-p02.txt", "kind": "transcript", "sha256": "ffeeddccbbaa9988",
         "importedAt": "2026-11-05T09:00:00Z", "date": "2026-11-05", "participant": "P02", "role": "member", "consent": "yes", "responses": None, "dropped": None},
        {"id": "e3", "file": "memory/research/rs-cod-payment/evidence/e3-p03.txt", "kind": "notes", "sha256": "0011223344556677",
         "importedAt": "2026-11-05T10:00:00Z", "date": "2026-11-05", "participant": "P03", "role": "member", "consent": "unknown", "responses": None,
         "dropped": {"at": "2026-11-09T10:00:00Z", "reason": GONE}},
    ],
    "tally": {"n": 30, "excluded": 4, "excludedWhy": {"q1": 4}, "byQuestion": {"q2": {"type": "single", "n": 30, "counts": {"COD": 18, "Wallet": 12}, "mean": None}}},
    "findings": [
        {"id": "f1", "text": "Most couriers open COD first", "hypotheses": ["h1"], "targets": [{"kind": "job", "id": "pay-cod"}, {"kind": "rule", "id": "cod-first"}],
         "evidence": [{"evidence": "e2", "quote": "I always check COD first " + XSS, "participant": "P02"},
                      {"tally": "q2", "option": "COD", "count": 18, "of": 30}]},
        {"id": "f2", "text": "The fee is hard to read", "hypotheses": ["h2"], "targets": [],
         "evidence": [{"tally": "q5", "stat": "mean", "value": 3.8, "of": 30}]},
    ],
    "refill": {"quantitative": "18 of 30 open COD first.", "researchSummary": "", "executiveSummary": ""},
    "refilled": {"at": "2026-11-10T10:00:00Z", "fields": {"quantitative": "18 of 30 open COD first. [rs-cod-payment]"}},
    "gates": [{"gate": "G-STUDY", "at": "2026-11-02T10:00:00Z", "note": ""}],
}
STUDY_B = {
    "id": "rs-first-screen-vi", "title": VI_TITLE, "question": "Bạn thấy màn hình đầu tiên có đủ rõ không?",
    "method": "interview", "status": "draft", "createdAt": "2026-11-03T10:00:00Z",
    "audience": {"roles": ["guest"], "segment": "", "targetN": 5},
    "targets": [{"kind": "screen", "id": "SCREEN"}],
    "hypotheses": [{"id": "h1", "statement": "Họ tìm nút đăng nhập trước", "supportedIf": "nói đến nút", "refutedIf": "không nhắc",
                    "targets": [], "verdict": "mixed", "why": "Hai trên ba người"}],
    "instrument": {"lang": "vi", "intro": "Cuộc trò chuyện ngắn.", "consent": "Chúng tôi không ghi âm.", "durationMin": 20, "closing": "Cảm ơn.",
                   "sections": [{"title": "Khởi động", "purpose": "warmup", "questions": [
                       {"id": "q1", "text": "Bạn làm nghề gì?", "tests": [], "probes": ["Bao lâu rồi?"]}]},
                       {"title": "Việc cần làm", "purpose": "task", "questions": [
                           {"id": "q2", "text": "Hãy đăng nhập.", "tests": ["h1"], "probes": ["Bạn nghĩ gì?"],
                            "task": {"screen": "SCREEN", "role": "guest", "entry": "", "success": "vào được trang chủ"}}]}]},
    "evidence": [], "tally": None,
    "findings": [{"id": "f1", "text": "Hai người tìm nút trước", "hypotheses": ["h1"], "targets": [],
                  "evidence": [{"evidence": "e1", "quote": "Tôi tìm nút đăng nhập ngay", "participant": "P01"}]}],
    "refill": {}, "refilled": None, "gates": [],
}


def build_project(tmp, name, research="full", overview=True):
    """A copy of the golden project with this test's jobs, one rule, Insights prose and research."""
    proj = os.path.join(tmp, name)
    shutil.copytree(GOLDEN, proj)
    path = os.path.join(proj, "registry.json")
    reg = json.load(open(path, encoding="utf-8"))
    screens = [s["id"] for s in reg["screens"]]
    base = {"when": "something happens", "want": "to do the thing", "so": "the outcome follows"}
    reg["ia"] = {"populated": True,
                 "jobs": [dict(base, id="pay-cod", title="Pay cash on delivery", priority="P0", roles=["member"], screens=[screens[0]]),
                          dict(base, id="other-job", priority="P1", roles=["guest"], screens=[])],
                 "rules": [{"id": "cod-first", "title": "COD is shown first", "kind": "decision", "summary": "COD is the first payment choice."}]}
    if overview:
        reg["meta"]["overview"] = {"objectives": "A lead sentence.", "principles": [{"num": 1, "title": "First", "body": "Body."}]}
        reg["meta"]["userInsights"] = {
            "quantitative": "Couriers prefer COD [rs-cod-payment]. An unknown cite [rs-nope] stays text.",
            "researchSummary": "Paragraph one.\n\nParagraph two.", "executiveSummary": "The executive summary."}
    else:
        reg["meta"].pop("overview", None)
        reg["meta"].pop("userInsights", None)
    if research == "full":
        b = copy.deepcopy(STUDY_B)
        b["targets"][0]["id"] = screens[0]
        b["instrument"]["sections"][1]["questions"][0]["task"]["screen"] = screens[0]
        reg["research"] = {"populated": True, "studies": [copy.deepcopy(STUDY_A), b]}
    elif research == "empty":
        reg["research"] = {"populated": False, "studies": []}
    else:
        reg.pop("research", None)
    json.dump(reg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    out = os.path.join(proj, "p.html")
    render.render_file(path, os.path.join(TPL, "prototype.html"), out)
    return out, screens


def open_page(pw, out, w=1440, h=900):
    br = pw.chromium.launch()
    c = br.new_context(viewport={"width": w, "height": h})
    c.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:"))
            else r.fulfill(status=200, body="", content_type="text/plain"))
    pg = c.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # a console error that is only the offline network (the Mermaid CDN) is not the shell's
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "https://" not in m.text
          and "Failed to load resource" not in m.text else None)
    pg.goto("file://" + out, wait_until="domcontentloaded")
    pg.wait_for_selector(".pb-product", state="attached", timeout=10000)
    pg.add_style_tag(content=FREEZE)
    pg.wait_for_timeout(300)
    return br, pg, errs


GO_RS = "setMetaView('summary'); setSummarySubTab('research')"
ROW = lambda sid: f'.pb-scan-tr[data-fb-list="rs"][data-key="{sid}"]'  # noqa: E731


def study_rows(pg):
    print("1 · the tab and the rows")
    pg.evaluate("setMetaView('summary')")
    pg.wait_for_timeout(150)
    tabs = pg.evaluate("[...document.querySelectorAll('.meta-subtab')].map(b => b.textContent.trim())")
    check(tabs == ["Overview", "User Insights", "Research"], f"Project Summary has a third sub-tab, Research ({tabs})")
    pg.evaluate("setSummarySubTab('research')")
    pg.wait_for_timeout(200)
    n = pg.locator(".pb-scan--rs .pb-scan-tr").count()
    check(n == 2, f"one row per study ({n})")
    check(pg.locator("h2.meta-h2").first.inner_text().strip() == "2.3 Research", "the section is numbered 2.3 Research")
    check(pg.locator(f"{ROW('rs-cod-payment')} > .pb-disc-b").is_hidden() and pg.locator(f"{ROW('rs-first-screen-vi')} > .pb-disc-b").is_hidden(),
          "every study is closed until opened")
    row_txt = pg.locator(f"{ROW('rs-cod-payment')} > .pb-disc-t").inner_text()
    who = pg.locator(f"{ROW('rs-cod-payment')} > .pb-disc-t .ti").get_attribute("title")
    check("Survey" in row_txt and "n 30 of 30" in row_txt and "Analysed" in row_txt and "Member" in who,
          f"the row says method, n, status, and (on hover) who ({row_txt.split(chr(10))[:6]}; {who!r})")
    vd = pg.evaluate(f"[...document.querySelectorAll('{ROW('rs-cod-payment')} .vd .lgc-b')].map(b => b.textContent.trim())")
    check(vd == ["1 supported", "1 refuted", "1 open"], f"…and a verdict tally ({vd})")
    check("Interview" in pg.locator(f"{ROW('rs-first-screen-vi')} > .pb-disc-t").inner_text(), "the interview row says Interview")
    check(VI_TITLE in pg.locator(f"{ROW('rs-first-screen-vi')} > .pb-disc-t").inner_text(), "Vietnamese text renders in the row")

    pg.locator(f"{ROW('rs-cod-payment')} > .pb-disc-t").click()
    pg.locator(f"{ROW('rs-first-screen-vi')} > .pb-disc-t").click()
    pg.wait_for_timeout(120)
    check(pg.locator(f"{ROW('rs-cod-payment')} > .pb-disc-b").is_visible() and pg.locator(f"{ROW('rs-first-screen-vi')} > .pb-disc-b").is_visible(),
          "a study row opens, and several are open at once")
    q = pg.locator(f"{ROW('rs-cod-payment')} .rs-q").inner_text()
    check("cash-on-delivery" in q, "an opened study shows its question")
    hy = pg.evaluate(f"[...document.querySelectorAll('{ROW('rs-cod-payment')} .rs-list')][0].querySelectorAll(':scope > li').length")
    badges = pg.evaluate(f"[...document.querySelectorAll('{ROW('rs-cod-payment')} .rs-list')][0].querySelectorAll('.lgc-b')")
    del badges
    bt = pg.evaluate(f"[...[...document.querySelectorAll('{ROW('rs-cod-payment')} .rs-list')][0].querySelectorAll(':scope > li .rs-hd .lgc-b')].map(b => b.textContent.trim())")
    check(hy == 3 and bt == ["Supported", "Refuted", "No verdict"], f"hypotheses carry a verdict badge each ({bt})")
    tone = pg.evaluate(f"[...document.querySelectorAll('{ROW('rs-cod-payment')} .rs-hd .lgc-b')].map(b => b.className.split(' ').pop())")
    check(tone == ["lgc-b-ok", "lgc-b-bad", "lgc-b-n"], f"…supported ok, refuted bad, none neutral ({tone})")
    kv = pg.locator(f"{ROW('rs-cod-payment')} .rs-kv").first.inner_text()
    check("Supported if" in kv and "most pick COD" in kv and "Refuted if" in kv, "…with supportedIf / refutedIf")
    check("Mixed" in pg.locator(f"{ROW('rs-first-screen-vi')} .rs-hd .lgc-b").first.inner_text(), "a mixed verdict says Mixed")


def findings_and_evidence(pg):
    print("2 · quotes, stats, instrument, evidence")
    body = ROW("rs-cod-payment")
    quotes = pg.evaluate(f"[...document.querySelectorAll('{body} .rs-quote')].map(q => q.innerText.replace(/\\s+/g,' ').trim())")
    check(len(quotes) == 1 and "P02 · e2" in quotes[0] and "I always check COD first" in quotes[0], f"a quote shows its words, participant and evidence id ({quotes})")
    stats = pg.evaluate(f"[...document.querySelectorAll('{body} .rs-stat')].map(q => q.innerText.replace(/\\s+/g,' ').trim())")
    check(any(s.startswith("18 of 30 answered “COD”") for s in stats) and any(s.startswith("mean 3.8 of 30") for s in stats), f"counted and mean stats read plainly ({stats})")
    check(pg.locator(f"{body} .rs-stat .lg-dim[title='Which do you open first?']").count() == 1, "…and a question id carries its question as a tooltip")

    check(pg.locator(f"{body} .rs-inst").count() == 1 and pg.evaluate(f"document.querySelector('{body} .rs-inst').classList.contains('is-open')") is False
          and pg.locator(f"{body} .rs-inst > .pb-disc-b").is_hidden(), "the instrument is closed by default")
    pg.locator(f"{body} .rs-inst > .pb-disc-t").click()
    pg.wait_for_timeout(100)
    it = pg.locator(f"{body} .rs-inst > .pb-disc-b").inner_text()
    check("Which do you open first?" in it and "COD / Wallet" in it and "tests h1" in it, "…and opens to a read-only question list")
    check(pg.locator(f"{body} .rs-inst input, {body} .rs-inst textarea, {body} .rs-inst select").count() == 0, "…with no form control in it")

    rows = pg.evaluate(f"[...document.querySelectorAll('{body} .rs-tbl tbody tr')].map(r => ({{cls: r.className, text: r.innerText.replace(/\\s+/g,' ').trim(), "
                       f"deco: getComputedStyle(r.querySelector('td')).textDecorationLine}}))")
    check(len(rows) == 4, f"the evidence table has three files and one reason row ({len(rows)})")
    heads = pg.evaluate(f"[...document.querySelectorAll('{body} .rs-tbl thead th')].map(t => t.textContent.trim())")
    check(heads == ["ID", "Kind", "Date", "Participant", "n", "Consent", "File", "Hash"], f"…columns {heads}")
    check("memory/research/rs-cod-payment/evidence/e1-responses.csv" in rows[0]["text"] and "a1b2c3d4" in rows[0]["text"] and "a1b2c3d4e5" not in rows[0]["text"],
          "…the path in full and the hash short")
    check(rows[2]["cls"] == "is-dropped" and "line-through" in rows[2]["deco"], f"a withdrawn file is struck out ({rows[2]['deco']})")
    check(GONE in rows[3]["text"] and "2026-11-09" in rows[3]["text"] and "line-through" not in rows[3]["deco"], "…with the reason beside it, not struck")
    check("line-through" not in rows[0]["deco"], "a kept file is not struck")
    check(pg.locator(f"{body} a[href*='memory/'], {body} [src*='memory/']").count() == 0, "an evidence path is text, never a link or a fetch")

    tg = pg.evaluate(f"[...document.querySelectorAll('{body} .rs-kv')][0] ? 1 : 0")
    del tg
    about = pg.locator(f"{body} dl.pb-kv").first.inner_text()
    check("Answers" in about and "30 of 30" in about and "4 excluded" in about and "In Insights" in about, f"the facts list answers, excluded and when it reached Insights")
    check(pg.locator(f"{body} dl.pb-kv a.lg-link").count() == 2, "targets that exist (a job, a rule) are jumps; a feature is plain text")


def escaping(pg):
    print("3 · escaping")
    body = ROW("rs-cod-payment")
    check(pg.evaluate("window.__xss") is None, "nothing from the registry ran")
    check(pg.locator(f"{body} script, {body} img").count() == 0, "no <script> or <img> was made from registry text")
    qt = pg.locator(f"{body} .rs-quote").first.inner_text()
    check("<script>window.__xss=1</script>" in qt, "a quote holding <script> displays it as text")
    check("<img" in pg.locator(f"{body} .rs-list").first.inner_text(), "a hypothesis holding <img> displays it as text")


def insights_links(pg):
    print("4 · Insights citations, job row, rule drawer")
    pg.evaluate("setSummarySubTab('insights')")
    pg.wait_for_timeout(200)
    h3 = pg.locator(".sum-sec h3.sum-h3").count()
    check(h3 == 3, f"Insights keeps exactly its three h3s ({h3})")
    links = pg.evaluate("[...document.querySelectorAll('.sum-sec a[data-rs]')].map(a => a.dataset.rs)")
    check(links == ["rs-cod-payment"], f"[rs-…] naming a study is a jump ({links})")
    check("[rs-nope]" in pg.locator("#summary-scroll").inner_text(), "…an id that names no study stays as text")
    pg.locator(".sum-sec a[data-rs]").first.click()
    pg.wait_for_timeout(250)
    st = pg.evaluate("({sub: state.summarySubTab, view: state.metaView, open: !!document.querySelector('.pb-scan-tr[data-key=\"rs-cod-payment\"].is-open')})")
    check(st["sub"] == "research" and st["view"] == "summary" and st["open"], f"…and lands on the study, opened ({st})")

    pg.evaluate("setMetaView('flow'); pbSetUxView('ia')")
    pg.wait_for_selector(".pb-scan--jobs")
    pg.locator('.pb-scan-tr[data-fb-list="ia"][data-key="pay-cod"] > .pb-disc-t').click()
    pg.wait_for_timeout(120)
    ev = pg.locator('.pb-scan-tr[data-fb-list="ia"][data-key="pay-cod"] .pb-kv')
    dts = pg.evaluate("[...document.querySelectorAll('.pb-scan-tr[data-key=\"pay-cod\"] .pb-kv dt')].map(d => d.textContent.trim())")
    check("Evidence" in dts, f"a job row has an Evidence line ({dts})")
    li = pg.locator('.pb-scan-tr[data-key="pay-cod"] .rs-evl li')
    check(li.count() == 1 and "Most couriers open COD first" in li.first.inner_text() and "Supported" in li.first.inner_text() and "rs-cod-payment" in li.first.inner_text(),
          f"…the finding, its verdict and its study ({li.first.inner_text() if li.count() else ''!r})")
    check(pg.locator('.pb-scan-tr[data-key="other-job"]').count() == 1 and
          "Evidence" not in pg.evaluate("[...document.querySelectorAll('.pb-scan-tr[data-key=\"other-job\"] .pb-kv dt')].map(d => d.textContent).join(',')"),
          "…and a job nothing names has none")
    del ev
    li.locator("a").click()
    pg.wait_for_timeout(250)
    check(pg.evaluate("state.summarySubTab") == "research" and pg.evaluate("state.metaView") == "summary", "…which jumps to the study")
    check(pg.evaluate("(() => { const e = document.querySelector('.pb-scan-tr[data-key=\"rs-cod-payment\"] [data-rs-finding=\"f1\"]'); return !!e && e.classList.contains('pb-flash'); })()"),
          "…and outlines the finding")

    pg.evaluate("setMetaView('flow'); pbSetUxView('logic')")
    pg.wait_for_selector(".pb-scan--logic")
    pg.evaluate("pbLogicDetails('cod-first')")
    pg.wait_for_timeout(300)
    sec = pg.locator("#lgc-drawer .lgc-dsec--evidence")
    check(sec.count() == 1 and sec.locator(".lgc-dsh").inner_text().strip().lower() == "evidence", "a rule's Details drawer has an Evidence section")
    check("Most couriers open COD first" in sec.inner_text() and "Supported" in sec.inner_text(), "…the finding and its verdict")
    sec.locator("a").click()
    pg.wait_for_timeout(250)
    check(pg.evaluate("state.summarySubTab") == "research" and not pg.evaluate("document.getElementById('lgc-drawer').classList.contains('is-open')"),
          "…a link closes the drawer and lands on the study")


def command_k(pg):
    print("5 · ⌘K")
    items = pg.evaluate("pbSearchItems().filter(i => i.g === 'Research').map(i => [i.t, i.s])")
    titles = [t for t, _ in items]
    check("Do couriers need COD on the first screen?" in titles and "Most couriers open COD first" in titles and VI_TITLE in titles,
          f"a Research group holds each study and each finding ({len(items)} items)")
    check(pg.evaluate("pbSearchItems().some(i => i.g === 'Go to' && i.t === 'Project Summary → Research')"), "…and a Go to → Project Summary → Research")
    pg.evaluate("setMetaView('prototype')")
    pg.evaluate("pbOpenSearch()")
    pg.wait_for_selector(".pb-cmdk input")
    pg.fill(".pb-cmdk input", "hard to read")
    pg.wait_for_timeout(150)
    txt = pg.locator(".pb-cmdk-list").inner_text()
    check("research" in txt.lower() and "the fee is hard to read" in txt.lower(),"typing a finding's words lists it under Research")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(300)
    check(pg.evaluate("state.summarySubTab") == "research" and pg.evaluate("state.metaView") == "summary", "…and Enter lands on its study")


def responsive(pg):
    print("6 · phone width")
    pg.set_viewport_size({"width": 430, "height": 932})
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(250)
    w = pg.evaluate("(() => { const s = document.querySelector('#summary-scroll'); return [s.scrollWidth, s.clientWidth, document.documentElement.scrollWidth, innerWidth]; })()")
    check(w[0] <= w[1] + 1 and w[2] <= w[3] + 1, f"no sideways scroll with both studies open at 430px ({w})")
    pg.set_viewport_size({"width": 1440, "height": 900})


def empty_states(tmp, pw):
    print("7 · empty, only-research, no research key")
    out, _ = build_project(tmp, "empty", research="empty")
    br, pg, errs = open_page(pw, out)
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(200)
    cta = pg.locator(".empty-state .empty-state-cta")
    check(cta.count() == 1 and cta.get_attribute("data-cmd") == "/pb:research", "no studies: the shared empty state offers /pb:research")
    check(pg.locator(".pb-scan--rs").count() == 0, "…and no list")
    check(errs == [], f"…no JS errors ({errs[:2]})")
    br.close()

    out, _ = build_project(tmp, "nokey", research="none")
    br, pg, errs = open_page(pw, out)
    pg.evaluate("setMetaView('summary')")
    pg.wait_for_timeout(200)
    check(pg.evaluate("[...document.querySelectorAll('.meta-subtab')].map(b => b.textContent.trim())") == ["Overview", "User Insights", "Research"],
          "a project with no `research` key still opens its Summary")
    pg.evaluate("setSummarySubTab('insights')")
    pg.wait_for_timeout(150)
    check(pg.locator(".sum-sec a[data-rs]").count() == 0 and "[rs-nope]" in pg.locator("#summary-scroll").inner_text()
          and pg.locator(".sum-sec h3.sum-h3").count() == 3, "…Insights is as it was (no citation links, three h3s)")
    pg.evaluate("setSummarySubTab('research')")
    pg.wait_for_timeout(150)
    check(pg.locator(".empty-state-cta").get_attribute("data-cmd") == "/pb:research", "…and Research is the empty state")
    check(pg.evaluate("pbSearchItems().filter(i => i.g === 'Research').length") == 0, "…⌘K has no Research group")
    check(errs == [], f"…no JS errors ({errs[:2]})")
    br.close()

    out, _ = build_project(tmp, "only", research="full", overview=False)
    br, pg, errs = open_page(pw, out)
    pg.evaluate("setMetaView('summary')")
    pg.wait_for_timeout(200)
    check(pg.locator(".meta-subtab").count() == 3 and pg.locator(".empty-state").count() == 0,
          "a project with only research populated still shows the Summary and the tab")
    pg.evaluate("setSummarySubTab('research')")
    pg.wait_for_timeout(200)
    check(pg.locator(".pb-scan--rs .pb-scan-tr").count() == 2, "…with its studies")
    check(errs == [], f"…no JS errors ({errs[:2]})")
    br.close()


def shots(pg, outdir):
    os.makedirs(outdir, exist_ok=True)
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(200)
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-cod-payment'), true); pbDiscSet('rs-inst-rs-cod-payment', true)")
    pg.wait_for_timeout(200)
    for theme in ("light", "dark"):
        pg.evaluate("document.querySelector('#summary-scroll').scrollTop = 0")
        pg.evaluate(f"pbSetTheme('{theme}')")
        pg.wait_for_timeout(250)
        pg.screenshot(path=os.path.join(outdir, f"research-study-{theme}.png"), full_page=False)
        pg.evaluate("document.querySelector('.rs-tbl').scrollIntoView({block: 'center'})")
        pg.wait_for_timeout(150)
        pg.screenshot(path=os.path.join(outdir, f"research-study-{theme}-evidence.png"), full_page=False)
        pg.evaluate("document.querySelector('#summary-scroll').scrollTop = 0")
    pg.evaluate("pbSetTheme('light')")


def main():
    tmp = tempfile.mkdtemp()
    try:
        out, _ = build_project(tmp, "main")
        with sync_playwright() as pw:
            try:
                br, pg, errs = open_page(pw, out)
            except Exception as e:  # noqa: BLE001
                print(f"SKIP: could not launch Chromium ({e})")
                sys.exit(2)
            study_rows(pg)
            findings_and_evidence(pg)
            escaping(pg)
            if os.environ.get("RESEARCH_SHOTS"):
                shots(pg, os.environ["RESEARCH_SHOTS"])
            insights_links(pg)
            command_k(pg)
            responsive(pg)
            check(errs == [], f"no JS errors on the main page ({errs[:3]})")
            br.close()
            empty_states(tmp, pw)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if _fail:
        print(f"✗ {len(_fail)} research-view failure(s):")
        for f in _fail:
            print(f"    - {f}")
        sys.exit(1)
    print("✓ research-view clean.")


if __name__ == "__main__":
    main()
