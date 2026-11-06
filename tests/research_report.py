#!/usr/bin/env python3
"""
research_report.py — pb/tools/research_report.py and research_methods.py, pure and deterministic.

  1. METHOD_CATALOG: six runnable methods, listed-only ones with runner False, every row complete
  2. default_checklist: shape, ids unique, mode-dependent items
  3. files_for per method (and the moderated gate for tree-test / card-sort / first-click)
  4. tasks.md holds the scenario text and nothing of the success criteria or hypotheses
  5. consent.md mentions recording only when instrument.recording asks
  6. moderator-guide.md follows ref-research (think-aloud, warm-up, neutral probes, no defending, assist rule)
  7. report_md carries every section heading; the issue ranking follows the tool's priority; the draft banner
  8. report_html parses, one <svg> and one <table> per chart, escapes planted <script>, no external references
  9. the other methods render (tree-test, card-sort, first-click) and a missing value is a dash
 10. determinism: two calls, same bytes; no input is mutated; PII-shaped text is redacted

The data below is synthetic test data, shaped like the analysis a real run stores (spec §6, §7). The numbers
are placeholders for rendering: nothing here is computed or asserted as a statistic.

Usage: python3 tests/research_report.py · Exit 0/1.
"""
import copy
import html.parser
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))

import research_methods as rm  # noqa: E402
import research_report as rr  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, msg):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(msg)
        print("FAIL  " + msg)


REG = {"screens": [{"id": "cart", "name": "Cart"}, {"id": "pay", "name": "Payment"}, {"id": "done", "name": "Order placed"}]}
PLANTED = "<script>alert(1)</script>"


def usability_study(**over):
    st = {
        "id": "rs-checkout-usability", "title": "Checkout usability test", "question": "Can a shopper pay for an order unaided?",
        "method": "usability", "status": "analysed", "scope": "collect",
        "audience": {"roles": ["shopper"], "targetN": 5},
        "plan": {"background": "Shoppers reach the cart but some do not finish.", "objectives": ["Find where people stop at payment"],
                 "researchQuestions": ["Do shoppers find the order total before paying?", "Can they pay with a gift card?"],
                 "decision": "Whether to move the total above the payment form.",
                 "methodRationale": "We need to see behaviour on a clickable flow, so a task-based test.",
                 "participants": {"criteria": ["Bought online in the last month"], "exclude": ["Works in e-commerce"], "n": 5, "segments": ["new", "returning"]},
                 "recruitment": {"channel": "Customer panel", "incentive": "Gift voucher", "note": "Mix of ages"},
                 "schedule": {"start": "2026-11-02", "end": "2026-11-06", "sessionMinutes": 40},
                 "team": {"moderator": "Researcher A", "notetaker": "Researcher B", "observers": ["Designer"]},
                 "materials": ["Prototype link"], "risks": [{"risk": "Participants no-show", "mitigation": "Recruit two spares"}],
                 "timeline": [{"milestone": "Pilot", "date": "2026-11-01"}], "budget": "Vouchers for 6"},
        "hypotheses": [
            {"id": "h1", "statement": "Shoppers find the total before paying", "supportedIf": "at least 4 of 5 find it", "refutedIf": "2 or fewer find it",
             "verdict": "refuted", "why": "Only 2 of 5 found it."},
            {"id": "h2", "statement": "A gift card can be applied unaided", "supportedIf": "success of 80% or more", "refutedIf": "success below 50%",
             "verdict": "mixed", "why": "Split."}],
        "instrument": {
            "lang": "en", "mode": "moderated", "recording": {"screen": True, "voice": True}, "device": "laptop", "thinkAloud": True,
            "intro": "Thanks for joining. We are testing a prototype of an ordering flow, not you.",
            "consent": "You will do a few tasks on a prototype while we watch and take notes. You may stop at any time.",
            "closing": "That is everything. Thank you for your time.", "durationMin": 40,
            "sections": [
                {"title": "Screener", "purpose": "screener", "questions": [
                    {"id": "sc1", "text": "How often do you order online?", "type": "single", "options": ["Weekly", "Monthly", "Never"], "qualifies": ["Weekly", "Monthly"]}]},
                {"title": "Warm-up", "purpose": "warmup", "questions": [
                    {"id": "w1", "text": "Tell me about the last time you ordered something online.", "type": "text"}]},
                {"title": "Pay for an order", "purpose": "task", "questions": [
                    {"id": "t1", "text": "You have two books in your cart. Pay for them with your own card.", "tests": ["h1"],
                     "task": {"screen": "cart", "success": "The order-placed screen is shown", "criteria": [{"screen": "done"}, {"absent": ".field__error"}],
                              "optimalPath": ["cart", "pay", "done"], "timeLimitSec": 300}},
                    {"id": "t1-seq", "text": "Overall, how easy or difficult was this task?", "type": "scale", "template": "seq",
                     "scale": {"min": 1, "max": 7, "minLabel": "Very difficult", "maxLabel": "Very easy"}},
                    {"id": "t2", "text": "You have a gift card. Use it to pay for the order.", "tests": ["h2"],
                     "task": {"screen": "pay", "success": "The gift card amount is deducted", "criteria": [{"text": "Gift card applied"}]},
                     "probes": ["What do you expect to happen if you press that?"]},
                    {"id": "t2-seq", "text": "Overall, how easy or difficult was this task?", "type": "scale",
                     "scale": {"min": 1, "max": 7, "minLabel": "Very difficult", "maxLabel": "Very easy"}}]},
                {"title": "Closing", "purpose": "closing", "questions": [{"id": "c1", "text": "What would you change first?", "type": "text"}]}]},
        "participants": [
            {"id": "P01", "segment": "new", "role": "shopper", "status": "done", "sessionAt": "2026-11-02", "pilot": False},
            {"id": "P02", "segment": "returning", "role": "shopper", "status": "done", "sessionAt": "2026-11-03", "pilot": False,
             "note": "contact jane.doe@example.com or +44 20 7946 0958"},
            {"id": "P09", "segment": "new", "role": "shopper", "status": "done", "pilot": True}],
        "pilots": [{"sessionId": "s-pilot-aaaa", "participant": "P09", "at": "2026-11-01T09:00:00Z", "file": "x", "media": []}],
        "evidence": [
            {"id": "e1", "kind": "session", "date": "2026-11-02", "participant": "P01", "consent": "yes", "sha256": "ab" * 32,
             "session": {"id": "s-a", "method": "usability", "recording": True}},
            {"id": "e2", "kind": "session", "date": "2026-11-03", "participant": "P02", "consent": "yes", "sha256": "cd" * 32,
             "session": {"id": "s-b", "method": "usability", "recording": False}},
            {"id": "e3", "kind": "session", "date": "2026-11-04", "participant": "P03", "consent": "unknown", "sha256": "ef" * 32,
             "session": {"id": "s-c", "method": "usability", "recording": True}},
            {"id": "e4", "kind": "notes", "date": "2026-11-04", "participant": "P03", "consent": "yes", "sha256": "01" * 32}],
        "analysis": {
            "method": "usability", "n": 3,
            "usability": {
                "tasks": {
                    "t1": {"n": 3, "success": {"x": 2, "n": 3, "rate": 0.6667, "low": 0.2, "high": 0.9},
                           "assisted": 1, "abandoned": 0, "timeouts": 0,
                           "time": {"n": 2, "geoMean": 41.2, "low": 30.1, "high": 56.4, "median": 40.0},
                           "timeAll": {"n": 3, "geoMean": 45.0, "low": 30.0, "high": 70.0, "median": 44.0},
                           "clicks": {"mean": 9.2}, "deadClicks": {"mean": 1.4, "total": 4}, "rageClicks": 1, "errors": {"mean": 0.6, "total": 2},
                           "lostness": {"n": 3, "mean": 0.21, "lostShare": 0.3333}, "seq": {"n": 3, "mean": 5.1, "low": 3.2, "high": 7.0},
                           "paths": [{"path": ["cart", "pay", "done"], "count": 2}, {"path": ["cart", "pay", "cart", "pay"], "count": 1}]},
                    "t2": {"n": 3, "success": {"x": 1, "n": 3, "rate": 0.3333, "low": 0.1, "high": 0.7},
                           "assisted": 0, "abandoned": 1, "timeouts": 1,
                           "time": {"n": 1, "geoMean": 80.0, "low": None, "high": None, "median": 80.0},
                           "timeAll": {"n": 3, "geoMean": 90.0, "low": 60.0, "high": 140.0, "median": 85.0},
                           "clicks": {"mean": 12.0}, "deadClicks": {"mean": 2.0, "total": 6}, "rageClicks": 0, "errors": {"mean": 1.0, "total": 3},
                           "seq": {"n": 3, "mean": 3.4, "low": 1.9, "high": 4.9}}},
                "sus": {"n": 3, "mean": 61.5, "sd": 8.0, "low": 50.0, "high": 73.0, "grade": "C-"},
                "overall": {"success": {"x": 3, "n": 6, "rate": 0.5, "low": 0.2, "high": 0.8}}},
            "issues": {"u1": {"participants": 2, "frequency": 0.6667, "priority": 2.0}, "u2": {"participants": 3, "frequency": 1.0, "priority": 3.0},
                       "u3": {"participants": 1, "frequency": 0.3333, "priority": 0.3333}, "u4": {"participants": 1, "frequency": 0.3333, "priority": 0.6667}},
            "affinity": {"tags": {"total-hidden": {"observations": 3, "participants": 2, "tasks": ["t1"]}}}},
        "observations": [
            {"id": "o1", "evidence": "e1", "participant": "P01", "task": "t1", "t": 61200, "note": "Looked for the total under Pay " + PLANTED, "tags": ["total-hidden"]},
            {"id": "o2", "evidence": "e2", "participant": "P02", "task": "t2", "event": 4, "note": "Tried the gift card box twice", "tags": ["total-hidden"]}],
        "themes": [{"id": "th1", "title": "The total is out of sight", "tags": ["total-hidden"], "insight": "Shoppers scroll past the total."}],
        "issues": [
            {"id": "u1", "title": "Total hidden below the form", "task": "t1", "screen": "pay", "severity": 3, "observations": ["o1"], "recommendation": "Move the total above the form."},
            {"id": "u2", "title": "Gift card field not found", "task": "t2", "screen": "pay", "severity": 4, "observations": ["o2"], "recommendation": "Label the field plainly."},
            {"id": "u3", "title": "Back arrow ambiguous", "task": "t1", "screen": "cart", "severity": 1, "observations": [], "recommendation": "Use text."},
            {"id": "u4", "title": "Voucher wording", "task": "t2", "screen": "pay", "severity": 2, "observations": [], "recommendation": "Reword."}],
        "findings": [
            {"id": "f1", "text": "Most shoppers did not see the total " + PLANTED + " before paying.", "hypotheses": ["h1"],
             "evidence": [{"evidence": "e1", "quote": "where is the total " + PLANTED, "participant": "P01"},
                          {"analysis": "usability.tasks.t1.success.rate", "value": 0.6667},
                          {"observation": "o1"}, {"issue": "u1"}]}],
        "report": {"summary": "Two of three completed the first task; the gift card task failed for most.",
                   "recommendations": [{"text": "Show the total first.", "issues": ["u1"], "route": "build"}],
                   "nextSteps": ["Re-test after the change"], "limitations": ["Only the laptop layout was tested."]},
        "logistics": {"checklist": [{"id": "plan-approved", "text": "Plan approved", "done": True, "at": None}]},
    }
    st.update(over)
    return st


def tree_study():
    return {"id": "rs-nav-tree", "title": "Navigation tree test", "question": "Is Refunds found under Orders?", "method": "tree-test", "status": "applied",
            "audience": {"targetN": 50},
            "instrument": {"mode": "unmoderated", "intro": "Intro", "consent": "Consent text.",
                           "tree": [{"id": "n-orders", "label": "Orders", "parent": None}, {"id": "n-refunds", "label": "Refunds", "parent": "n-orders"}],
                           "sections": [{"title": "Tasks", "purpose": "task", "questions": [
                               {"id": "tt1", "text": "Where would you go to get your money back?", "tests": ["h1"], "tree": {"correct": ["n-refunds"]}}]}]},
            "hypotheses": [{"id": "h1", "statement": "Refunds are found under Orders", "supportedIf": "70% or more", "refutedIf": "below 40%", "verdict": "supported", "why": "ok"}],
            "evidence": [], "participants": [],
            "analysis": {"n": 40, "treeTest": {"tasks": {"tt1": {"n": 40, "success": {"x": 30, "n": 40, "rate": 0.75, "low": 0.6, "high": 0.86},
                                                              "direct": {"x": 20, "n": 40, "rate": 0.5, "low": 0.35, "high": 0.65},
                                                              "firstClick": {"x": 33, "n": 40, "rate": 0.825, "low": 0.68, "high": 0.92},
                                                              "time": {"median": 21.0}, "destinations": [{"node": "n-refunds", "count": 30}, {"node": "n-orders", "count": 6}]}}}}}


def sort_study(kind="open"):
    return {"id": "rs-card-sort", "title": "Help topics card sort", "question": "How do people group help topics?", "method": "card-sort", "status": "analysed",
            "instrument": {"mode": "both", "consent": "Consent.", "sort": {"kind": kind, "categories": [{"id": "k1", "label": "Money"}, {"id": "k2", "label": "Delivery"}]},
                           "cards": [{"id": "c-a", "label": "Refund an order"}, {"id": "c-b", "label": "Track a parcel"}, {"id": "c-c", "label": "Change payment card"}, {"id": "c-d", "label": "Change delivery address"}],
                           "sections": []},
            "hypotheses": [], "evidence": [], "analysis": {"n": 10, "cardSort": {
                "n": 10, "kind": kind, "cards": ["c-a", "c-b", "c-c", "c-d"],
                "similarity": {"c-a|c-b": 0.1, "c-a|c-c": 0.8, "c-a|c-d": 0.2, "c-b|c-c": 0.1, "c-b|c-d": 0.9, "c-c|c-d": 0.2},
                "merges": [], "clusters": [["c-a", "c-c"], ["c-b", "c-d"]], "threshold": 0.5,
                "categories": {"Money": {"count": 8, "cards": {"c-a": 0.8, "c-c": 0.7}}}}}}


def click_study():
    return {"id": "rs-first-click", "title": "Pay button first click", "question": "Do people click Pay first?", "method": "first-click", "status": "analysed",
            "instrument": {"mode": "moderated", "consent": "Consent.", "sections": [{"title": "Tasks", "purpose": "task", "questions": [
                {"id": "fc1", "text": "Where would you click to pay?", "click": {"screen": "pay", "target": "[data-action=\"submit\"]", "rect": {"x": 0.1, "y": 0.8, "w": 0.3, "h": 0.1}}}]}]},
            "hypotheses": [], "evidence": [], "analysis": {"n": 4, "firstClick": {"tasks": {"fc1": {
                "n": 4, "success": {"x": 3, "n": 4, "rate": 0.75, "low": 0.3, "high": 0.95}, "time": {"median": 3.1, "geoMean": 3.4},
                "clicks": [[0.42, 0.86, True], [0.2, 0.84, True], [0.9, 0.1, False], [0.25, 0.82, True]]}}}}}


class Doc(html.parser.HTMLParser):
    VOID = {"meta", "link", "br", "hr", "img", "input", "col", "area", "base", "wbr", "source", "track", "embed", "param"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.tags = [], [], {}
        self.scripts, self.attrs = 0, []
        self.in_fig, self.figs = None, []

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        self.attrs += [(tag, k, v) for k, v in attrs]
        if tag == "script":
            self.scripts += 1
        if tag == "figure":
            self.in_fig = {"svg": 0, "table": 0}
            self.figs.append(self.in_fig)
        if self.in_fig is not None and tag in ("svg", "table"):
            self.in_fig[tag] += 1
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "figure":
            self.in_fig = None
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected </%s> with %s open" % (tag, self.stack[-3:]))
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()


def parse(text):
    d = Doc()
    d.feed(text)
    d.close()
    if d.stack:
        d.errors.append("unclosed: %s" % d.stack)
    return d


def main():
    # 1 · catalog -------------------------------------------------------------------------------------------
    run = [c["method"] for c in rm.METHOD_CATALOG if c["runner"]]
    check(run == ["survey", "interview", "usability", "tree-test", "card-sort", "first-click"], "runnable methods: %r" % run)
    listed = [c["method"] for c in rm.METHOD_CATALOG if not c["runner"]]
    for m in ("diary study", "contextual inquiry", "concept test", "five-second test"):
        check(m in listed, "listed-only method missing: " + m)
    for c in rm.METHOD_CATALOG:
        for k in ("method", "answers", "kind", "data", "n", "minutes", "runner", "outputs", "notFor"):
            check(k in c, "%s lacks %s" % (c.get("method"), k))
        check(c["kind"] in ("behavioural", "attitudinal") and c["data"] in ("qual", "quant", "both"), "%s kind/data values" % c["method"])
        check(bool(c["notFor"].strip()) and bool(c["answers"].strip()), "%s has honest text" % c["method"])
        check(bool(c["outputs"]) == bool(c["runner"]), "%s outputs only when runnable" % c["method"])
    check(len({c["method"] for c in rm.METHOD_CATALOG}) == len(rm.METHOD_CATALOG), "catalog methods unique")
    check(rm.catalog_entry("usability")["method"] == "usability" and rm.catalog_entry("nope") is None, "catalog_entry")

    # 2 · checklist -----------------------------------------------------------------------------------------
    for m in ("survey", "interview", "usability", "tree-test", "card-sort", "first-click"):
        for mode in ("moderated", "unmoderated", "both"):
            cl = rm.default_checklist(m, mode)
            ids = [c["id"] for c in cl]
            check(len(ids) == len(set(ids)) and ids, "%s/%s ids unique" % (m, mode))
            check(all(set(c) == {"id", "text", "done", "at"} and c["done"] is False and c["at"] is None for c in cl), "%s/%s item shape" % (m, mode))
            check(cl == rm.default_checklist(m, mode), "%s/%s deterministic" % (m, mode))
    check("kit-opened-clean" in [c["id"] for c in rm.default_checklist("usability", "unmoderated")], "unmoderated has the kit item")
    check("kit-opened-clean" not in [c["id"] for c in rm.default_checklist("usability", "moderated")], "moderated has no kit item")
    check("note-taker-assigned" in [c["id"] for c in rm.default_checklist("usability", "moderated")], "moderated has note-taker")
    check("note-taker-assigned" not in [c["id"] for c in rm.default_checklist("tree-test", "unmoderated")], "unmoderated has no note-taker")
    for need in ("plan-approved", "consent-ready", "pilot-run", "recording-tested", "incentives-budgeted", "invites-sent"):
        check(need in [c["id"] for c in rm.default_checklist("usability", "both")], "checklist has " + need)

    # 3 · files_for -----------------------------------------------------------------------------------------
    u = usability_study()
    before = copy.deepcopy(u)
    check(sorted(rr.files_for(u, REG)) == ["consent.md", "moderator-guide.md", "note-taking.csv", "plan.md", "screener.md", "tasks.md"], "usability files: %s" % sorted(rr.files_for(u, REG)))
    u2 = usability_study()
    u2["instrument"]["sections"] = [s for s in u2["instrument"]["sections"] if s["purpose"] != "screener"]
    check("screener.md" not in rr.files_for(u2, REG) and rr.screener_md(u2, REG) is None, "no screener section, no screener.md")
    check(rr.files_for({"id": "rs-x", "method": "survey", "instrument": {}}, REG) == {}, "survey: no new files")
    check(sorted(rr.files_for({"id": "rs-i", "method": "interview", "instrument": {}}, REG)) == ["consent.md", "plan.md"], "interview files")
    tt = tree_study()
    check(sorted(rr.files_for(tt, REG)) == ["consent.md", "plan.md", "tasks.md"], "tree-test unmoderated: %s" % sorted(rr.files_for(tt, REG)))
    tt["instrument"]["mode"] = "moderated"
    check(sorted(rr.files_for(tt, REG)) == ["consent.md", "moderator-guide.md", "plan.md", "tasks.md"], "tree-test moderated adds the guide")
    tt["instrument"]["mode"] = "both"
    check("moderator-guide.md" in rr.files_for(tt, REG), "mode both counts as moderated")
    cs = sort_study()
    check(sorted(rr.files_for(cs, REG)) == ["cards.md", "consent.md", "moderator-guide.md", "plan.md"], "card-sort (mode both): %s" % sorted(rr.files_for(cs, REG)))
    cs["instrument"]["mode"] = "unmoderated"
    check(sorted(rr.files_for(cs, REG)) == ["cards.md", "consent.md", "plan.md"], "card-sort unmoderated")
    fc = click_study()
    check(sorted(rr.files_for(fc, REG)) == ["consent.md", "moderator-guide.md", "plan.md", "tasks.md"], "first-click moderated: %s" % sorted(rr.files_for(fc, REG)))
    check(all(isinstance(v, str) and v.strip() for v in rr.files_for(u, REG).values()), "every file has text")

    # 4 · tasks.md ------------------------------------------------------------------------------------------
    tmd = rr.tasks_md(u, REG)
    check("Pay for them with your own card" in tmd and "Use it to pay for the order" in tmd, "tasks.md has the scenarios")
    for leak in ("The order-placed screen is shown", "The gift card amount is deducted", "Gift card applied", "field__error", "supportedIf", "supported if",
                 "refuted", "Shoppers find the total", "h1", "h2", "hypothes", "success", "optimal", "cart > pay", "Total hidden", "300"):
        check(leak.lower() not in tmd.lower(), "tasks.md leaks %r" % leak)
    check("Task 1 of 2" in tmd and "Task 2 of 2" in tmd, "tasks.md numbering")
    check("seq" not in tmd.lower() and "easy or difficult" not in tmd, "post-task questions are not in the task cards")
    tt_t = rr.tasks_md(tree_study(), REG)
    check("Where would you go to get your money back?" in tt_t and "n-refunds" not in tt_t and "Refunds" not in tt_t, "tree-test tasks.md has no correct answer")

    # 5 · consent.md ----------------------------------------------------------------------------------------
    c_on = rr.consent_md(u, REG)
    check("screen" in c_on.lower() and "voice" in c_on.lower() and "optional" in c_on.lower(), "consent mentions recording when asked")
    check("agree to the optional recording" in c_on and "Participant code: P__" in c_on and "withdraw" in c_on.lower(), "consent has the optional box, code, withdrawal")
    check("never saved" in c_on, "consent says typed values are not saved")
    u_off = usability_study()
    u_off["instrument"]["recording"] = {"screen": False, "voice": False}
    c_off = rr.consent_md(u_off, REG).lower()
    for word in ("record", "screen", "voice", "microphone", "webm", "video"):
        check(word not in c_off, "consent without recording mentions %r" % word)
    u_none = usability_study()
    del u_none["instrument"]["recording"]
    check("record" not in rr.consent_md(u_none, REG).lower(), "consent with no recording key mentions no recording")
    u_scr = usability_study()
    u_scr["instrument"]["recording"] = {"screen": True, "voice": False}
    c_scr = rr.consent_md(u_scr, REG).lower()
    check("your screen" in c_scr and "your voice" not in c_scr, "screen-only recording does not mention voice")
    check("record" not in rr.consent_md({"id": "rs-i", "method": "interview", "instrument": {"consent": "Hello."}}, REG).lower(), "interview consent without recording key")

    # 6 · moderator guide -----------------------------------------------------------------------------------
    g = rr.moderator_guide_md(u, REG)
    for need in ("Thanks for joining", "You will do a few tasks", "Think-aloud instruction", "Practice", "Warm-up questions", "Read exactly:",
                 "You have two books in your cart", "Start screen: `cart` (Cart)", "Success: The order-placed screen is shown", "tool checks: the screen is `done`",
                 "Shortest path: cart > pay > done", "Time limit: 300 seconds", "Neutral probes", "What do you expect to happen if you press that?",
                 "What did you expect to happen?", "After the task, ask:", "Overall, how easy or difficult was this task?", "Never defend the design",
                 "more than 2 minutes", "Assisted", "Debrief", "Note-taking codes", "Is there anything I did not ask that I should have?",
                 "That is everything", "Tests: h1", "What would you change first?", "Tell me about the last time"):
        check(need in g, "moderator guide lacks %r" % need)
    order = [g.index("## " + k) for k in ("1. Welcome and introduction", "2. Consent (read aloud", "3. Think-aloud instruction", "4. Warm-up questions", "5. Task 1 of 2",
                                           "6. Task 2 of 2", "7. Closing questions", "8. Debrief", "Note-taking codes")]
    check(order == sorted(order), "guide order: intro, consent, think-aloud, warm-up, tasks, closing, debrief, codes")
    check("| 0:00 |" in g and "Total" in g, "guide has a timing table")
    check("agree" in g.lower() and "recording" in g.lower(), "guide records the recording choice when asked")
    ug = copy.deepcopy(u)
    ug["instrument"]["thinkAloud"] = False
    check("## 3. Think-aloud" not in rr.moderator_guide_md(ug, REG), "thinkAloud false drops the think-aloud section")
    ug2 = copy.deepcopy(u)
    ug2["instrument"]["stuckMin"] = 4
    check("more than 4 minutes" in rr.moderator_guide_md(ug2, REG), "stuckMin respected")
    um = copy.deepcopy(u)
    um["instrument"]["mode"] = "unmoderated"
    check("unmoderated" in rr.moderator_guide_md(um, REG).lower(), "unmoderated usability guide says so")
    tg = rr.moderator_guide_md(tree_study(), REG)
    check("Correct answer: Refunds" in tg and "Think-aloud instruction" not in tg, "tree-test guide: correct answer, no think-aloud")
    check("Correct first click" in rr.moderator_guide_md(click_study(), REG), "first-click guide")

    sc = rr.screener_md(u, REG)
    check("How often do you order online?" in sc and "Monthly (qualifies)" in sc and "Never\n" in sc and "Bought online in the last month" in sc, "screener content")

    csvt = rr.note_taking_csv(u)
    check(csvt.splitlines()[0] == "participant,session,task,time,observation,quote,tag,severity", "note-taking header")
    check(csvt.splitlines()[1].split(",")[2] == "t1" and csvt.splitlines()[2].split(",")[2] == "t2" and len(csvt.splitlines()) == 3, "note-taking rows per task")

    p = rr.plan_md(u, REG)
    for need in ("## Background", "## Objectives", "## Research questions", "## The decision this informs", "## Hypotheses", "supported if: at least 4 of 5 find it",
                 "refuted if: 2 or fewer find it", "tested by: t1", "## Method and why", "We need to see behaviour", "## Participants", "Bought online in the last month",
                 "Works in e-commerce", "## Recruitment", "Customer panel", "## Schedule and timeline", "2026-11-02 to 2026-11-06", "| Pilot | 2026-11-01 |",
                 "## Team and roles", "Researcher A", "## Materials", "moderator-guide.md (generated)", "## Risks and mitigations", "Participants no-show",
                 "## Ethics and consent", "## Analysis plan", "task success with adjusted-Wald interval", "## Deliverables", "## Logistics checklist", "- [x] Plan approved",
                 "Tracker today", "about 40 minutes"):
        check(need in p, "plan.md lacks %r" % need)
    check("jane.doe" not in p and "7946" not in p, "plan.md carries no participant note")
    bare = rr.plan_md({"id": "rs-bare", "method": "usability", "instrument": {}}, {})
    check("## Risks and mitigations" in bare and "—" in bare, "a bare study still renders every plan section with dashes")

    cm = rr.cards_md(cs, REG)
    check("Refund an order" in cm and "Money" not in cm and "make and name their own" in cm, "open card sort: cards, no categories")
    cs2 = sort_study("closed")
    check("Money" in rr.cards_md(cs2, REG) and "Delivery" in rr.cards_md(cs2, REG), "closed card sort lists categories")
    check("also make groups of their own" in rr.cards_md(sort_study("hybrid"), REG), "hybrid note")

    # 7 · report_md -----------------------------------------------------------------------------------------
    md = rr.report_md(u, REG)
    for h in ("# Checkout usability test", "## 1. Summary", "## 2. Research questions and what we learned", "## 3. Method and participants", "## 4. Results",
              "## 5. Findings", "## 6. Usability issues", "## 7. Themes", "## 8. Recommendations and next steps", "## 9. Limitations", "## Appendix"):
        check(h in md, "report_md lacks heading %r" % h)
    idx = [md.index(h) for h in ("## 1. Summary", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8.", "## 9.", "## Appendix")]
    check(idx == sorted(idx), "report_md section order")
    check(rr.DRAFT_BANNER in md, "draft banner when status is analysed")
    done = usability_study(status="applied")
    check(rr.DRAFT_BANNER not in rr.report_md(done, REG) and rr.DRAFT_BANNER not in rr.report_html(done, REG), "no banner when applied")
    check(rr.DRAFT_BANNER in rr.report_html(u, REG), "draft banner in html")
    check("2026-11-02 to 2026-11-04" in md, "dates are min/max of session dates")
    check("3 of target 5" in md, "n versus target")
    check("Top issues by priority" in md and md.index("Gift card field not found") < md.index("Total hidden below the form"), "top issues ordered by the tool's priority")
    sec6 = md.split("## 6. Usability issues")[1].split("## 7.")[0]
    check(sec6.index("u2") < sec6.index("u1") < sec6.index("u4") < sec6.index("u3"), "issue table ranked by priority: %s" % [sec6.index(k) for k in ("u2", "u1", "u4", "u3")])
    check("3 of 3" in md and "2 of 3" in md, "frequency 'k of n'")
    check("4 Catastrophe" in md and "3 Major" in md, "severity labels")
    check("| t1 · You have two books in your cart. Pay for them with your own card. |" in md, "task label in tables")
    check("2/3 · 67% (20%–90%)" in md, "success cell: x/n, rate, interval")
    check("61.5" in md and "C-" in md, "SUS in the report")
    check("Verdict" in md and "refuted" in md and "mixed" in md, "verdict table")
    check("“where is the total &lt;script>alert(1)&lt;/script>” — P01 (e1)" in md.replace("<script>", "&lt;script>") or "P01 (e1)" in md, "quote with participant and evidence id")
    check("Number: usability.tasks.t1.success.rate = 0.6667" in md, "cited number")
    check("Observation o1 (P01, e1)" in md and "Issue u1: Total hidden below the form" in md, "observation and issue refs")
    check("1 pilot session(s) were excluded" in md, "limitation: pilots")
    check("Consent is not recorded as given for 2 evidence item(s) (e3, e4)" in md or "Consent is not recorded as given for 1 evidence item(s) (e3)" in md, "limitation: consent unknown")
    check("sessions have no screen or voice recording" in md, "limitation: sessions without recording")
    check("1 assisted completion(s)" in md, "limitation: assisted")
    check("Only the laptop layout was tested." in md, "model's own limitation kept")
    check("3 of the target 5 participants: results are directional" in md, "limitation: below target")
    check("| P01 | new | shopper | done |" in md and "P09" not in md.split("## 4.")[0].split("Participants (by code)")[1], "participants by pseudonym, pilots out of the table")
    check("e1 | session | 2026-11-02 | P01 | " + "ab" * 6 + " |" in md.replace("  ", " "), "evidence index with sha prefix")
    check("jane.doe" not in md and "7946" not in md, "no PII in report_md")
    check("<script>" not in md, "report_md makes raw tags inert")
    check(len(md.splitlines()) > 80, "report_md is substantial")

    # 8 · report_html ---------------------------------------------------------------------------------------
    h = rr.report_html(u, REG)
    d = parse(h)
    check(not d.errors, "html well-formed: %s" % d.errors[:3])
    check(d.scripts == 0 and "<script" not in h.lower(), "no script tag at all (planted ones escaped)")
    check("&lt;script&gt;alert(1)&lt;/script&gt;" in h, "planted script escaped in a finding / participant note")
    check(h.count(PLANTED) == 0, "planted script appears nowhere raw")
    check(h.startswith("<!doctype html>") and '<html lang="en">' in h and "<title>Checkout usability test</title>" in h and "@media print" in h, "document shell, title, print css")
    check("http://" not in h and "https://" not in h and "<link" not in h and "<img" not in h and "src=" not in h and "@import" not in h and "url(" not in h, "no external references")
    check(not [a for a in d.attrs if a[1].startswith("on")], "no inline event handlers")
    check(len(d.figs) == 4, "usability report has 4 charts (success, time, SEQ, SUS): %d" % len(d.figs))
    check(all(f["svg"] == 1 and f["table"] == 1 for f in d.figs), "every chart has one svg and one table: %s" % d.figs)
    check(d.tags.get("svg") == 4, "one svg per chart")
    check("-apple-system" in h and "fonts.googleapis" not in h, "system font stack")
    check('class="banner"' in h and "role=\"note\"" in h, "banner markup")
    check('aria-label="Task success rate by task, 0 to 100 percent"' in h and "<title>SUS score 61.5 out of 100, grade C-</title>" in h, "svg accessible names")
    check('class="chip sev4"' in h and "4 Catastrophe" in h, "severity chip")
    check("68 (commonly cited average)" in h, "SUS gauge average mark")
    for k in ("h2", "h3", "table", "dl"):
        check(d.tags.get(k), "html has <%s>" % k)
    check(h.count("<h2>") == 10, "html has 9 sections plus the appendix: %d" % h.count("<h2>"))
    check("—" in h, "dashes where the data is missing")

    # 9 · other methods -------------------------------------------------------------------------------------
    th = rr.report_html(tree_study(), REG)
    dt = parse(th)
    check(not dt.errors and len(dt.figs) == 1 and dt.figs[0] == {"svg": 1, "table": 1}, "tree-test html: %s %s" % (dt.errors, dt.figs))
    check(rr.DRAFT_BANNER not in th, "tree-test study applied: no banner")
    tmd2 = rr.report_md(tree_study(), REG)
    check("Refunds" in tmd2 and "30/40" in tmd2 and "Where people chose" in tmd2 and "40 of target 50" in tmd2, "tree-test md results with node labels")
    sh = rr.report_html(cs, REG)
    ds = parse(sh)
    check(not ds.errors and len(ds.figs) == 1 and ds.figs[0]["table"] == 1 and ds.figs[0]["svg"] == 0, "card-sort heat table is the chart: %s" % ds.figs)
    check("background:rgb(" in sh and "0.9" in sh and "Track a parcel" in sh, "heat cells shaded with their value printed")
    check("Clusters at similarity 0.5" in rr.report_md(cs, REG) and "Refund an order, Change payment card" in rr.report_md(cs, REG), "clusters in md")
    ch = rr.report_html(click_study(), REG)
    dc = parse(ch)
    check(not dc.errors and len(dc.figs) == 1 and dc.figs[0] == {"svg": 1, "table": 1}, "first-click html: %s" % dc.figs)
    check('viewBox="0 0 320 200"' in ch and 'class="tgt"' in ch and ch.count('class="hit"') == 3 and ch.count('class="miss"') == 1, "first-click dot plot: 16:10, target box, 3 hits, 1 miss")
    empty = {"id": "rs-e", "title": "Empty", "method": "usability", "status": "draft", "instrument": {}, "evidence": [], "hypotheses": []}
    em = rr.report_md(empty, {})
    check("No usability analysis has been computed yet" in em and rr.DRAFT_BANNER in em and "—" in em, "a study with no data still renders, with dashes")
    check(not parse(rr.report_html(empty, {})).errors, "empty study html parses")
    sv = {"id": "rs-s", "title": "Survey", "method": "survey", "status": "analysed", "instrument": {}, "evidence": [{"id": "e1", "kind": "responses", "date": "2026-10-01", "consent": "yes", "sha256": "ab" * 32}], "hypotheses": []}
    check("2026-10-01" in rr.report_md(sv, {}) and not parse(rr.report_html(sv, {})).errors, "survey renders (dates from data)")

    # 10 · determinism, purity, PII -------------------------------------------------------------------------
    check(rr.report_md(u, REG) == rr.report_md(copy.deepcopy(u), REG), "report_md deterministic")
    check(rr.report_html(u, REG) == rr.report_html(copy.deepcopy(u), REG), "report_html deterministic")
    check(rr.files_for(u, REG) == rr.files_for(copy.deepcopy(u), REG), "files_for deterministic")
    check(u == before, "no function mutated the study")
    check(json.dumps(rr.report_html(u, REG)).count("2026-11-06T") == 0 and "Generated" not in rr.report_md(u, REG), "no 'now' stamp")
    pii = usability_study()
    pii["report"]["summary"] = "Contact jane.doe@example.com or +44 20 7946 0958 about it; seen 2026-11-03."
    pm = rr.report_md(pii, REG)
    check("jane.doe" not in pm and "7946" not in pm and "[redacted]" in pm and "2026-11-03" in pm, "email and phone redacted, dates kept")
    check("jane.doe" not in rr.report_html(pii, REG), "email redacted in html")
    pipe = usability_study()
    pipe["themes"][0]["insight"] = "a | b"
    check("a \\| b" in rr.report_md(pipe, REG), "pipe escaped in md tables")

    if FAILS:
        print("\nFAIL: %d of %d checks failed" % (len(FAILS), CHECKS[0]))
        return 1
    print("PASS: research_report (%d checks)" % CHECKS[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
