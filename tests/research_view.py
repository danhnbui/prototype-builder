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
                           {"id": "q5", "text": "How easy is the fee to read?", "tests": ["h2"], "type": "scale", "template": "ces",
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
    "tally": {"n": 30, "excluded": 4, "excludedWhy": {"q1": 4}, "byQuestion": {
        "q2": {"type": "single", "n": 30, "counts": {"COD": 18, "Wallet": 12}, "mean": None},
        "q9": {"type": "scale", "n": 12, "score": {"metric": "ces", "value": 5.4, "pct": 77, "n": 12}}}},
    "biasReview": {"at": "2026-11-02T09:00:00Z", "instrumentHash": "abc123",
                   "rows": [{"id": "b1", "answer": "yes", "evidence": "fine"},
                            {"id": "b3", "answer": "no", "evidence": "Leading wording in q2 " + IMG},
                            {"id": "b4", "answer": "blocked", "evidence": "no access"}],
                   "summary": {"yes": 5, "no": 1, "blocked": 1}},
    "findings": [
        {"id": "f1", "text": "Most couriers open COD first", "hypotheses": ["h1"], "targets": [{"kind": "job", "id": "pay-cod"}, {"kind": "rule", "id": "cod-first"}],
         "evidence": [{"evidence": "e2", "quote": "I always check COD first " + XSS, "participant": "P02"},
                      {"tally": "q2", "option": "COD", "count": 18, "of": 30}]},
        {"id": "f2", "text": "The fee is hard to read", "hypotheses": ["h2"], "targets": [],
         "evidence": [{"tally": "q5", "stat": "mean", "value": 3.8, "of": 30},
                                                                {"tally": "q9", "stat": "ces", "value": 5.4, "of": 12}]},
    ],
    "refill": {"quantitative": "18 of 30 open COD first.", "researchSummary": "", "executiveSummary": ""},
    "refilled": {"at": "2026-11-10T10:00:00Z", "fields": {"quantitative": "18 of 30 open COD first. [rs-cod-payment]"}},
    "gates": [{"gate": "G-STUDY", "at": "2026-11-02T10:00:00Z", "note": "", "acceptReview": "Wording kept on purpose"}],
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


STUDY_C = {
    "id": "rs-ask-only", "title": "Questions for the pay screen", "question": "Is the fee clear?",
    "method": "survey", "status": "approved", "scope": "instrument", "setup": "Use the staging link " + IMG,
    "createdAt": "2026-11-04T10:00:00Z", "audience": {"roles": ["member"], "segment": "", "targetN": 30},
    "targets": [], "hypotheses": [{"id": "h1", "statement": "Fee is clear", "supportedIf": "a", "refutedIf": "b", "targets": [], "verdict": None, "why": ""}],
    "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": 3, "closing": "",
                   "sections": [{"title": "Fee", "purpose": "main", "questions": [{"id": "q1", "text": "How easy was it?", "tests": ["h1"], "type": "scale"}]}]},
    "evidence": [], "tally": None, "findings": [], "refill": {}, "refilled": None,
    "gates": [{"gate": "G-STUDY", "at": "2026-11-04T10:00:00Z", "note": "", "skipReview": ""}],
}


SCRIPT_TITLE = "Total hidden <script>window.__xss=3</script> under Pay"
STUDY_D = {
    "id": "rs-ux-usability", "title": "Can couriers find the total?", "question": "Do couriers find the total on the pay screen?",
    "method": "usability", "status": "analysed", "createdAt": "2026-11-05T10:00:00Z",
    "audience": {"roles": ["member"], "segment": "rural", "targetN": 5},
    "targets": [], "hypotheses": [], "findings": [], "refill": {}, "refilled": None, "gates": [], "tally": None,
    "plan": {"background": "Couriers called support about totals.", "objectives": ["Measure task success on pay", "Find where couriers stall"],
             "researchQuestions": ["Do couriers find the total?", "Where do they look first?"], "decision": "Whether to move the total above the fold",
             "methodRationale": "We need behaviour, not opinion",
             "participants": {"criteria": ["Delivers weekly"], "exclude": ["Works at the company"], "n": 5, "segments": ["rural", "urban"]},
             "recruitment": {"channel": "Courier forum", "incentive": "voucher", "note": ""},
             "schedule": {"start": "2026-11-10", "end": "2026-11-14", "sessionMinutes": 45},
             "team": {"moderator": "Lead", "notetaker": "Assistant", "observers": ["Designer"]},
             "risks": [{"risk": "Few rural courier signups", "mitigation": "Open a second channel"}], "timeline": [], "budget": ""},
    "participants": [
        {"id": "P01", "segment": "rural", "role": "member", "status": "done", "sessionAt": "2026-11-10", "incentive": "paid", "pilot": False},
        {"id": "P02", "segment": "urban", "role": "member", "status": "done", "sessionAt": "2026-11-11", "incentive": "due", "pilot": False},
        {"id": "P03", "segment": "rural", "role": "member", "status": "withdrawn", "sessionAt": "2026-11-12", "incentive": "none", "pilot": False},
        {"id": "P04", "segment": "rural", "role": "member", "status": "scheduled", "sessionAt": "", "incentive": "none", "pilot": True},
    ],
    "pilots": [{"sessionId": "s-pilot1", "participant": "P04", "at": "2026-11-09T09:00:00Z", "file": "memory/research/rs-ux-usability/pilot/s-pilot1.json", "media": [],
                "withheld": {"at": "2026-11-14T08:00:00Z", "reason": "hand-off without recordings"}}],
    "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": 45, "closing": "", "sections": [
        {"title": "Tasks", "purpose": "task", "questions": [
            {"id": "t1", "text": "Pay for the parcel", "tests": [], "task": {"screen": "SCREEN", "success": "paid"}},
            {"id": "t2", "text": "Find the delivery fee", "tests": [], "task": {"screen": "SCREEN", "success": "fee seen"}}]}]},
    "evidence": [
        {"id": "e1", "file": "memory/research/rs-ux-usability/evidence/e1-s-aaa1.json", "kind": "session", "sha256": "1111111111111111", "date": "2026-11-10",
         "participant": "P01", "consent": "yes", "dropped": None,
         "session": {"id": "s-aaa1", "method": "usability", "mode": "moderated", "durationMs": 125000, "tasks": 2, "outcomes": {"success": 1, "fail": 1}, "recording": True, "media": []}},
        {"id": "e2", "file": "memory/research/rs-ux-usability/evidence/e2-s-bbb2.json", "kind": "session", "sha256": "2222222222222222", "date": "2026-11-11",
         "participant": "P02", "consent": "yes", "dropped": None,
         "session": {"id": "s-bbb2", "method": "usability", "mode": "moderated", "durationMs": 61000, "tasks": 2, "outcomes": {"success": 1, "abandoned": 1}, "recording": False, "media": []}},
        {"id": "e3", "file": "memory/research/rs-ux-usability/evidence/e3-s-ccc3.json", "kind": "session", "sha256": "3333333333333333", "date": "2026-11-12",
         "participant": "P03", "consent": "yes", "dropped": {"at": "2026-11-13T10:00:00Z", "reason": "Withdrew"},
         "session": {"id": "s-ccc3", "method": "usability", "mode": "moderated", "durationMs": 30000, "tasks": 2, "outcomes": {"success": 2}, "recording": False, "media": []}},
        {"id": "e4", "file": "memory/research/rs-ux-usability/evidence/e4-s-ddd4.webm", "kind": "recording", "sha256": "4444444444444444", "date": "2026-11-10",
         "participant": "P01", "consent": "yes", "dropped": None, "session": "s-ddd4",
         "withheld": {"at": "2026-11-14T08:00:00Z", "reason": "hand-off without recordings"}},
    ],
    "analysis": {"method": "usability", "n": 2, "inputs": ["e1", "e2"], "usability": {
        "tasks": {"t1": {"n": 2, "success": {"x": 1, "n": 2, "rate": 0.5, "low": 0.09, "high": 0.91}, "time": {"n": 1, "geoMean": 41.2, "low": 30.1, "high": 56.4},
                         "seq": {"n": 2, "mean": 5.5}, "lostness": {"n": 2, "mean": 0.21}, "deadClicks": {"mean": 1, "total": 7}, "errors": {"mean": 1, "total": 3}},
                  "t2": {"n": 2, "success": {"x": 2, "n": 2, "rate": 1.0, "low": 0.34, "high": 1.0}, "deadClicks": {"mean": 0, "total": 0}, "errors": {"mean": 0, "total": 0}}},
        "sus": {"n": 2, "mean": 72.5, "sd": 9.1, "low": 61.2, "high": 83.8, "grade": "C+"},
        "overall": {"success": {"x": 3, "n": 4, "rate": 0.75, "low": 0.3, "high": 0.95}}},
        "issues": {"u1": {"participants": 2, "frequency": 1.0, "priority": 3.0}, "u2": {"participants": 1, "frequency": 0.5, "priority": 4.5}}},
    "observations": [{"id": "o1", "evidence": "e1", "participant": "P01", "task": "t1", "event": 41, "note": "Looked under Pay, not Handover", "tags": ["total-hidden"]},
                     {"id": "o2", "evidence": "e2", "participant": "P02", "task": "t1", "t": 61000, "note": "Gave up after the second screen", "tags": ["total-hidden"]}],
    "themes": [{"id": "th1", "title": "The total hides", "tags": ["total-hidden"], "insight": "People expect the total where they pay."}],
    "issues": [{"id": "u1", "title": SCRIPT_TITLE, "task": "t1", "screen": "SCREEN", "severity": 3, "observations": ["o1", "o2"],
                "recommendation": "Show the total beside the Pay button", "targets": []},
               {"id": "u2", "title": "Fee label is unclear", "task": "t2", "screen": "SCREEN", "severity": 2, "observations": ["o2"], "recommendation": "Rename it", "targets": []}],
}
STUDY_E = {
    "id": "rs-ux-sort", "title": "How do couriers group the actions?", "question": "How do couriers group actions?",
    "method": "card-sort", "status": "analysed", "createdAt": "2026-11-05T10:00:00Z",
    "audience": {"roles": [], "segment": "", "targetN": 15}, "targets": [], "hypotheses": [], "findings": [], "refill": {}, "refilled": None, "gates": [], "tally": None,
    "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": 15, "closing": "", "sections": [],
                   "cards": [{"id": "c-a", "label": "Refund an order"}, {"id": "c-b", "label": "Cancel a parcel"}, {"id": "c-c", "label": "Print a label"}, {"id": "c-d", "label": "Reprint receipt"}],
                   "sort": {"kind": "open", "categories": []}},
    "evidence": [],
    "analysis": {"method": "card-sort", "n": 12, "cardSort": {"n": 12, "kind": "open", "cards": ["c-a", "c-b", "c-c", "c-d"],
        "similarity": {"c-a|c-b": 0.75, "c-a|c-c": 0.1, "c-a|c-d": 0.2, "c-b|c-c": 0.15, "c-b|c-d": 0.05, "c-c|c-d": 0.9},
        "clusters": [["c-a", "c-b"], ["c-c", "c-d"]], "threshold": 0.5, "categories": {}}},
}
STUDY_F = {
    "id": "rs-ux-click", "title": "Where do couriers click first?", "question": "First click on pay", "method": "first-click", "status": "analysed",
    "createdAt": "2026-11-05T10:00:00Z", "audience": {"roles": [], "segment": "", "targetN": 3}, "targets": [], "hypotheses": [], "findings": [], "refill": {}, "refilled": None, "gates": [], "tally": None,
    "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": 5, "closing": "", "sections": [{"title": "Clicks", "purpose": "task", "questions": [{"id": "fc1", "text": "Where would you pay?", "tests": []}]}]},
    "evidence": [],
    "analysis": {"method": "first-click", "n": 3, "firstClick": {"tasks": {"fc1": {"n": 3, "success": {"x": 2, "n": 3, "rate": 0.667, "low": 0.2, "high": 0.94},
        "time": {"median": 3.1, "geoMean": 3.4}, "clicks": [[0.42, 0.86, True], [0.45, 0.8, True], [0.1, 0.1, False]]}}}},
}
STUDY_G = {
    "id": "rs-ux-tree", "title": "Where would couriers look for refunds?", "question": "Findability of refunds", "method": "tree-test", "status": "analysed",
    "createdAt": "2026-11-05T10:00:00Z", "audience": {"roles": [], "segment": "", "targetN": 50}, "targets": [], "hypotheses": [], "findings": [], "refill": {}, "refilled": None, "gates": [], "tally": None,
    "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": 5, "closing": "", "sections": [{"title": "Find", "purpose": "task", "questions": [{"id": "tt1", "text": "Where would you refund?", "tests": []}]}],
                   "tree": [{"id": "n-orders", "label": "Orders", "parent": None}, {"id": "n-refunds", "label": "Refunds", "parent": "n-orders"}]},
    "evidence": [],
    "analysis": {"method": "tree-test", "n": 50, "treeTest": {"tasks": {"tt1": {"n": 50, "success": {"x": 31, "n": 50, "rate": 0.62, "low": 0.48, "high": 0.74},
        "direct": {"x": 20, "n": 50, "rate": 0.4, "low": 0.28, "high": 0.54}, "firstClick": {"x": 35, "n": 50, "rate": 0.7, "low": 0.56, "high": 0.81},
        "destinations": [{"node": "n-refunds", "count": 31}]}}}},
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
        reg["research"] = {"populated": True, "studies": [copy.deepcopy(STUDY_A), b, copy.deepcopy(STUDY_C)]}
    elif research == "ux":
        reg["research"] = {"populated": True, "studies": []}
        for src in (STUDY_D, STUDY_E, STUDY_F, STUDY_G):
            st = copy.deepcopy(src)
            for sec in st["instrument"].get("sections", []):
                for q in sec.get("questions", []):
                    if q.get("task"):
                        q["task"]["screen"] = screens[0]
            for u in st.get("issues", []):
                u["screen"] = screens[0]
            reg["research"]["studies"].append(st)
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
    check(n == 3, f"one row per study ({n})")
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


def scope_scores_bias(pg):
    print("3b · scope, setup, scores, bias review")
    a, c, b = ROW("rs-cod-payment"), ROW("rs-ask-only"), ROW("rs-first-screen-vi")
    pg.locator(f"{c} > .pb-disc-t").click()
    pg.wait_for_timeout(120)
    kvc = pg.locator(f"{c} dl.pb-kv").first.inner_text()
    kva = pg.locator(f"{a} dl.pb-kv").first.inner_text()
    kvb = pg.locator(f"{b} dl.pb-kv").first.inner_text()
    check("Scope" in kvc and "Questions only" in kvc, "an instrument study says Scope: Questions only")
    check("Setup" in kvc and "Use the staging link" in kvc, "…and shows its Setup")
    check("Questions and results" in kva and "Setup" not in kva, "a collect study says Questions and results, with no Setup row when absent")
    check("Questions and results" in kvb, "an old study with no scope reads as collect")
    check("Answers" not in kvc and "0 of" not in kvc, "an approved instrument study shows no Answers line")
    check("Answers" in kva, "a collect study keeps its Answers line")
    rowc = pg.locator(f"{c} > .pb-disc-t").inner_text()
    check("0 of" not in rowc and "open" not in rowc and "supported" not in rowc.lower() and pg.locator(f"{c} > .pb-disc-t .vd .lgc-b").count() == 0,
          f"…and its row shows no n or verdict tally ({rowc.split(chr(10))[:6]})")
    check(pg.evaluate("window.__xss") is None and pg.locator(f"{c} script, {c} img").count() == 0, "setup text with markup is escaped")
    check("<img" in pg.locator(f"{c} dl.pb-kv").first.inner_text(), "…and shown as text")

    sc = pg.evaluate(f"[...document.querySelectorAll('{a} .rs-score')].map(x => x.innerText.replace(/\\s+/g,' ').trim())")
    check(len(sc) == 1 and "q9" in sc[0] and "Customer Effort Score (CES)" in sc[0] and "5.4" in sc[0] and "n 12" in sc[0], f"a Scores block lists each score with its question id ({sc})")
    order = pg.evaluate(f"(() => {{ const hs = [...document.querySelectorAll('{a} .rs-h')].map(h => h.textContent.trim()); return hs; }})()")
    lines = pg.evaluate(f"(() => {{ const li = document.querySelector('{a} .rs-score'); const cs = getComputedStyle(li); return Math.round(li.getBoundingClientRect().height / parseFloat(cs.lineHeight || 20)); }})()")
    check(lines <= 3, f"…and a score reads as a line, not its parts stacked ({lines} lines tall)")
    check("77% answered 5 to 7" in sc[0], f"…with its percentage saying what it counts ({sc[0]})")
    check(order.index("Scores") < order.index("Findings"), f"Scores sits above Findings ({order})")
    check(pg.locator(f"{b} .rs-scores").count() == 0, "a study with no score has no Scores block")
    stats = pg.evaluate(f"[...document.querySelectorAll('{a} .rs-stat')].map(q => q.innerText.replace(/\\s+/g,' ').trim())")
    check(any(s.startswith("CES 5.4 of 12") for s in stats), f"a score citation reads CES 5.4 of 12 ({stats})")
    pg.locator(f"{a} .rs-inst > .pb-disc-b").first.inner_text()
    ins = pg.locator(f"{a} .rs-inst > .pb-disc-b").inner_text()
    check("Customer Effort Score" in ins, "the instrument marks a template question with its metric name")

    bias = pg.locator(f"{a} .rs-bias")
    check(bias.count() == 1 and pg.evaluate(f"document.querySelector('{a} .rs-bias').classList.contains('is-open')") is False
          and pg.locator(f"{a} .rs-bias > .pb-disc-b").is_hidden(), "the Bias review is closed by default")
    check("5 yes" in pg.locator(f"{a} .rs-bias > .pb-disc-t").inner_text() and "1 no" in pg.locator(f"{a} .rs-bias > .pb-disc-t").inner_text(),
          "…with summary counts")
    pg.locator(f"{a} .rs-bias > .pb-disc-t").click()
    pg.wait_for_timeout(100)
    bt = pg.locator(f"{a} .rs-bias > .pb-disc-b").inner_text()
    check("b3" in bt and "Leading wording" in bt and "b4" in bt and "blocked" in bt and "b1" not in bt, f"…opens to the no and blocked rows only ({bt!r})")
    check("Accepted: Wording kept on purpose" in bt, "…and an accepted reason is shown plainly")
    check("<img" in bt and pg.locator(f"{a} .rs-bias img").count() == 0, "…evidence is escaped")
    ct = pg.locator(f"{c} .rs-bias").inner_text()
    check("Not reviewed" in ct, f"an approved study with no review reads Not reviewed ({ct!r})")
    check(pg.locator(f"{b} .rs-bias").count() == 0, "a draft study with no review shows nothing")


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


UX = lambda sid: f'.pb-scan-tr[data-fb-list="rs"][data-key="{sid}"]'  # noqa: E731


def ux_blocks(pg, shots_dir=None):
    print("8 · UX studies: plan, participants, sessions, results, issues, themes, report (file://)")
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(200)
    kd = pg.locator(f"{UX('rs-ux-usability')} > .pb-disc-t").inner_text()
    check("Usability test" in kd and "n 2 of 5" in kd, f"the row says Usability test and counts distinct participants of kept sessions ({kd.splitlines()[:6]})")
    for sid, lab in (("rs-ux-sort", "Card sort"), ("rs-ux-click", "First-click test"), ("rs-ux-tree", "Tree test")):
        check(lab in pg.locator(f"{UX(sid)} > .pb-disc-t").inner_text(), f"{sid} row says {lab}")
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-ux-usability'), true)")
    pg.wait_for_timeout(150)
    d = UX("rs-ux-usability")
    check(pg.locator(f"{d} .rs-plan").count() == 1 and pg.locator(f"{d} .rs-plan > .pb-disc-b").is_hidden(), "the Plan is a closed disclosure")
    pg.locator(f"{d} .rs-plan > .pb-disc-t").click()
    pg.wait_for_timeout(100)
    pl = pg.locator(f"{d} .rs-plan > .pb-disc-b").inner_text()
    check(all(x in pl for x in ("Measure task success on pay", "Do couriers find the total?", "Whether to move the total above the fold", "Delivers weekly",
                                  "5 planned", "rural", "2026-11-10 to 2026-11-14", "45 min", "Moderator Lead", "Few rural courier signups", "Open a second channel")),
          "…and opens to objectives, questions, decision, participants, schedule, team and risks")

    pt = pg.evaluate(f"[...document.querySelectorAll('{d} tr[data-rs-part]')].map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    pipe = pg.locator(f"{d} .rs-pipe").inner_text()
    check(len(pt) == 4 and "1 scheduled · 2 done · 1 withdrawn" in pipe, f"Participants: a row each and a pipeline line ({pipe!r}, {len(pt)} rows)")
    check("P04" in pt[3] and "Pilot" in pt[3] and "P01" in pt[0] and "rural" in pt[0] and "paid" in pt[0], f"…pseudonym, segment, status, incentive, pilot ({pt[3]!r})")

    sess = pg.evaluate(f"[...document.querySelectorAll('{d} tr[data-rs-session]')].map(r => ({{cls: r.className, text: r.innerText.replace(/\\s+/g,' ').trim()}}))")
    check(len(sess) == 3 and "2:05" in sess[0]["text"] and "✓ 1" in sess[0]["text"] and "✗ 1" in sess[0]["text"] and "Yes" in sess[0]["text"], f"Sessions: duration m:ss, outcome glyphs, recording ({sess[0]['text'] if sess else ''!r})")
    check("↩ 1" in sess[1]["text"] and sess[1]["text"].rstrip().endswith("No"), f"…abandoned shows the return glyph; no recording says No ({sess[1]['text']!r})")
    check(sess[2]["cls"] == "is-dropped", "…a dropped session is struck")
    ev4 = pg.evaluate(f"(() => {{ const r = document.querySelector('{d} tr[data-rs-ev=\"e4\"]'); return r ? {{cls: r.className, text: r.innerText.replace(/\\s+/g,' ').trim(), struck: getComputedStyle(r.cells[0]).textDecorationLine}} : null; }})()")
    check(ev4 and "Left out of the hand-off" in ev4["text"] and ev4["cls"] != "is-dropped" and "line-through" not in ev4["struck"],
          f"Evidence: a withheld recording carries the label and is not struck like a dropped row ({ev4!r})")
    check("Left out of the hand-off" not in pg.locator(f"{d} tr[data-rs-ev='e1']").inner_text(), "…and an ordinary row does not")
    check("Left out of the hand-off" in pg.locator(f"{d} tr[data-rs-pilot='s-pilot1']").inner_text(), "Sessions: a pilot whose recordings were left out says so instead of Yes or No")
    only = pg.evaluate("""(() => { const st = pbRsStudies().find(s => s.id === 'rs-ux-usability');
        const mk = ev => { const w = document.createElement('div'); w.innerHTML = pbRsSessionsHTML(Object.assign({}, st, {evidence: ev})); return [...w.querySelectorAll('tr[data-rs-session]')].map(r => r.cells[5].textContent.replace(/\\s+/g,' ').trim()); };
        const e1 = st.evidence.find(e => e.id === 'e1'), w = {at: '2026-11-14T08:00:00Z'};
        return {only: mk([e1, {id: 'e9', kind: 'recording', session: 's-aaa1', withheld: w}]), put: mk([e1, {id: 'e9', kind: 'recording', session: 's-aaa1'}]), none: mk([e1])}; })()""")
    check(only["only"] == ["Left out of the hand-off"] and only["put"] == ["Yes"] and only["none"] == ["Yes"],
          f"…a session whose only recording is withheld does not claim a video; one put back, or none stored, reads as before ({only!r})")
    check(pg.locator(f"{d} tr[data-rs-pilot='s-pilot1']").count() == 1 and "Pilot" in pg.locator(f"{d} tr[data-rs-pilot='s-pilot1']").inner_text(), "…a pilot is listed and marked Pilot")
    check(pg.locator(f"{d} a[href^='/research/']").count() == 0, "over file:// there are no session, observer, replay or report links")
    check("research.py link rs-ux-usability" in pg.locator(f"{d} .rs-links").first.inner_text(), "…the CLI hint stands in")

    res = pg.locator(f"{d} .rs-tbl--res tbody tr")
    rt = pg.evaluate(f"[...document.querySelectorAll('{d} .rs-tbl--res tbody tr')].map(r => r.innerText.replace(/\\s+/g,' ').trim())")
    check(res.count() == 2 and "Pay for the parcel" in rt[0] and "1 of 2" in rt[0] and "50%" in rt[0] and "41.2 s" in rt[0] and "5.5" in rt[0] and "0.21" in rt[0] and "7" in rt[0],
          f"Results: a task table with the task's text, success x of n, rate, time, SEQ, lostness, clicks ({rt[0] if rt else ''!r})")
    check(pg.locator(f"{d} .rs-tbl--res .rs-ci[role=img]").count() == 2 and pg.locator(f"{d} .rs-tbl--res .rs-ci-whisk").count() == 2, "…each rate has a small bar with a whisker")
    st = pg.locator(f"{d} .rs-stat").all_inner_texts()
    check(any("SUS" in x and "72.5" in x and "C+" in x for x in st), f"…SUS with its grade ({st})")
    check("Directional" in pg.locator(f"{d} .rs-note").inner_text(), "…n 2 of 5 planned is labelled Directional")

    iss = pg.evaluate(f"[...document.querySelectorAll('{d} .rs-issues > li')].map(r => ({{id: r.dataset.rsIssue, text: r.innerText.replace(/\\s+/g,' ').trim()}}))")
    check([i["id"] for i in iss] == ["u2", "u1"], f"Issues are ranked by priority, not severity ({[i['id'] for i in iss]})")
    check("1 of 2 participants" in iss[1]["text"] or "2 of 2 participants" in iss[1]["text"], f"…each says how many participants ({iss[1]['text'][:160]!r})")
    check("3 Major" in iss[1]["text"] and "2 Minor" in iss[0]["text"], "…with a severity chip")
    check("Show the total beside the Pay button" in iss[1]["text"] and "Looked under Pay" in iss[1]["text"] and "P01" in iss[1]["text"] and "e1" in iss[1]["text"] and "event 41" in iss[1]["text"] and "1:01" in iss[1]["text"],
          "…recommendation and observations with participant, evidence id and event or time")
    check(pg.locator(f"{d} .rs-issues a.lg-link").count() >= 2, "…the screen is a jump")
    check(pg.evaluate("window.__xss") is None and pg.locator(f"{d} script, {d} img").count() == 0, "a <script> in an issue title ran nothing")
    check("<script>window.__xss=3</script>" in pg.locator(f"{d} .rs-issues").inner_text(), "…and shows as text")
    th = pg.locator(f"{d} .rs-themes").inner_text()
    check("The total hides" in th and "total-hidden" in th and "People expect the total" in th, "Themes: title, tags, insight")
    check("memory/research/rs-ux-usability/report/report.html" in pg.locator(f"{d} .rs-links").last.inner_text(), "Report: its path is text")

    e = UX("rs-ux-sort")
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-ux-sort'), true)")
    pg.wait_for_timeout(120)
    cells = pg.evaluate(f"[...document.querySelectorAll('{e} .rs-heat tbody tr')].map(r => [...r.querySelectorAll('td')].map(c => c.textContent.trim()))")
    check(len(cells) == 4 and cells[0][1] == "0.75" and cells[1][0] == "0.75" and cells[2][3] == "0.90" and cells[0][0] == "—", f"card sort: a 4 x 4 similarity table with the value printed ({cells})")
    shade = pg.evaluate(f"[...document.querySelectorAll('{e} .rs-heat td.rs-hm')].map(c => getComputedStyle(c).backgroundColor)")
    check(len(set(shade)) > 2, "…the shade follows the value")
    cl = pg.locator(f"{e} .rs-clusters li").all_inner_texts()
    check(len(cl) == 2 and "Refund an order" in cl[0] and "Print a label" in cl[1], f"…and the clusters ({cl})")
    check("Directional" in pg.locator(f"{e} .rs-note").inner_text(), "…12 of 15 is Directional")

    f = UX("rs-ux-click")
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-ux-click'), true)")
    pg.wait_for_timeout(120)
    box = pg.evaluate(f"(() => {{ const r = document.querySelector('{f} .rs-plot').getBoundingClientRect(); return [r.width, r.height, document.querySelectorAll('{f} .rs-dot').length, document.querySelectorAll('{f} .rs-dot.is-hit').length]; }})()")
    check(abs(box[0] / box[1] - 1.6) < 0.05 and box[2] == 3 and box[3] == 2, f"first click: a 16:10 plot with 3 dots, 2 hits ({box})")
    check("Directional" not in pg.locator(f"{f} .rs-note").inner_text(), "…n 3 of 3 is not Directional")
    g = UX("rs-ux-tree")
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-ux-tree'), true)")
    pg.wait_for_timeout(120)
    tt = pg.locator(f"{g} .rs-tbl--res tbody tr").first.inner_text().replace("\n", " ")
    check("31 of 50" in tt and "20 of 50" in tt and "35 of 50" in tt and "Refunds" in tt, f"tree test: success, direct, first click and top destination ({tt!r})")

    if shots_dir:
        os.makedirs(shots_dir, exist_ok=True)
        pg.evaluate("pbDiscSet('rs-plan-rs-ux-usability', true)")
        for w, h in ((1280, 900), (429, 932)):
            pg.set_viewport_size({"width": w, "height": h})
            pg.evaluate(GO_RS)
            pg.wait_for_timeout(250)
            pg.evaluate("document.querySelector('#summary-scroll').scrollTop = 0")
            pg.evaluate(f"document.querySelector('{d}').scrollIntoView()")
            pg.wait_for_timeout(200)
            pg.screenshot(path=os.path.join(shots_dir, f"usability-detail-{w}.png"), full_page=False)
            pg.evaluate("document.querySelector('.rs-tbl--res').scrollIntoView({block: 'start'})")
            pg.wait_for_timeout(150)
            pg.screenshot(path=os.path.join(shots_dir, f"usability-results-{w}.png"), full_page=False)
            pg.evaluate(f"document.querySelector('{e} .rs-heat').scrollIntoView({{block: 'center'}})")
            pg.wait_for_timeout(150)
            pg.screenshot(path=os.path.join(shots_dir, f"cardsort-{w}.png"), full_page=False)
        pg.set_viewport_size({"width": 1440, "height": 900})

    print("9 · UX studies: phone width, ⌘K")
    pg.set_viewport_size({"width": 429, "height": 932})
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(250)
    w = pg.evaluate("(() => { const s = document.querySelector('#summary-scroll'); return [s.scrollWidth, s.clientWidth, document.documentElement.scrollWidth, innerWidth]; })()")
    check(w[0] <= w[1] + 1 and w[2] <= w[3] + 1, f"no sideways scroll in the Research view at 429px with UX studies open ({w})")
    pg.set_viewport_size({"width": 1440, "height": 900})
    items = pg.evaluate("pbSearchItems().filter(i => i.g === 'Research' && String(i.s).indexOf('Issue') === 0).map(i => [i.t, i.s])")
    check(any(s == "Issue · rs-ux-usability" and t == "Fee label is unclear" for t, s in items), f"⌘K indexes each issue as Issue · <study> ({items})")
    pg.evaluate("setMetaView('prototype')")
    pg.evaluate("pbOpenSearch()")
    pg.wait_for_selector(".pb-cmdk input")
    pg.fill(".pb-cmdk input", "fee label")
    pg.wait_for_timeout(150)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(350)
    check(pg.evaluate("state.summarySubTab") == "research" and pg.evaluate("state.metaView") == "summary", "…Enter lands on the study")
    check(pg.evaluate("(() => { const e = document.querySelector('[data-rs-issue=\"u2\"]'); return !!e && e.classList.contains('pb-flash'); })()"), "…and outlines the issue")


def ux_served(pw, out):
    print("10 · UX studies served by the preview (window.PB_PREVIEW)")
    html = open(out, encoding="utf-8").read()
    inj = '<script>window.PB_PREVIEW={"meta":"/api/meta","data":"/__pb_data"};</script>'
    i = html.find("<script")
    served = os.path.join(os.path.dirname(out), "p-served.html")
    open(served, "w", encoding="utf-8").write(html[:i] + inj + html[i:])
    br, pg, errs = open_page(pw, served)
    pg.evaluate(GO_RS)
    pg.wait_for_timeout(200)
    pg.evaluate("pbDiscSet(pbScanId('rs','rs-ux-usability'), true)")
    pg.wait_for_timeout(150)
    d = UX("rs-ux-usability")
    hrefs = pg.evaluate(f"[...document.querySelectorAll('{d} a[href^=\"/research/\"]')].map(a => [a.getAttribute('href'), a.target, a.textContent.trim()])")
    got = {h: (t, x) for h, t, x in hrefs}
    check(got.get("/research/rs-ux-usability/session") == ("_blank", "Start a moderated session"), f"Start a moderated session opens in a new tab ({hrefs})")
    check("/research/rs-ux-usability/observer" in got and got["/research/rs-ux-usability/observer"][1] == "Open observer", "…Open observer")
    check("/research/rs-ux-usability/replay/e1" in got and "/research/rs-ux-usability/replay/e2" in got and "/research/rs-ux-usability/replay/e3" not in got,
          "…a Replay link per kept session, none for the dropped one")
    check("/research/rs-ux-usability/replay/pilot-s-pilot1" in got, "…and for the pilot (pilot-<sessionId>)")
    check("/research/rs-ux-usability/report" in got and got["/research/rs-ux-usability/report"][1] == "Open report", "…Open report")
    check("research.py link" not in pg.locator(f"{d} .rs-links").first.inner_text(), "…and no CLI hint")
    check("memory/research/rs-ux-usability/report/report.html" in pg.locator(f"{d} .rs-links").last.inner_text(), "…the report path is still text")
    check(pg.locator(f"{d} a[target=_blank]").evaluate_all("els => els.every(e => e.rel.includes('noopener'))"), "…every new-tab link is noopener")
    check(errs == [], f"…no JS errors ({errs[:2]})")
    br.close()


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
    check(pg.locator(".pb-scan--rs .pb-scan-tr").count() == 3, "…with its studies")
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
            scope_scores_bias(pg)
            if os.environ.get("RESEARCH_SHOTS"):
                shots(pg, os.environ["RESEARCH_SHOTS"])
            insights_links(pg)
            command_k(pg)
            responsive(pg)
            check(errs == [], f"no JS errors on the main page ({errs[:3]})")
            br.close()
            uxout, _ = build_project(tmp, "ux", research="ux")
            br, pg, errs = open_page(pw, uxout)
            ux_blocks(pg, os.environ.get("RESEARCH_SHOTS"))
            check(errs == [], f"no JS errors on the UX page ({errs[:3]})")
            br.close()
            ux_served(pw, uxout)
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
