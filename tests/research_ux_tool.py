#!/usr/bin/env python3
"""
research_ux_tool.py — /pb:research's UX extension (pb/tools/research.py) end to end, through the CLI, on a temp copy of
fixtures/research/ (a synthetic parcel-desk registry) plus fixtures/research/ux/ (plans for each new method and
synthetic session files — every one of them TEST DATA: pseudonyms P01.., invented screens, no real person or product).

What it proves:

  1. A usability study from the first verb to the last: init -> plan -> check (a deliberate C-TASK error, fixed) ->
     brief -> review-plan -> review -> approve (the instrument files exist) -> participant -> logistics -> kit (no
     hypotheses in it) -> import three sessions, a pilot and a recording -> analyze (equal to research_analysis
     recomputed here) -> synthesize (observations, themes, issues, findings that cite analysis values) -> verify
     clean -> report (a Draft banner) -> refill --approved (the banner goes).
  2. A tree test, a card sort and a first-click study from plan to analyze, each with its own check rules and its
     own bias-review items.
  3. The refusals that keep the evidence honest: analyze on a survey, report with a failing verify, a cited analysis
     value that is wrong, a stale inputsHash after one more import, a hand-edited analysis, a computed number typed
     into an issue, an email in a participant note, a session without consent, a recording without recording
     consent, G-STUDY withdrawn by a plan change (and not by a logistics change).
  4. `link` against a real preview server (marked NOT VERIFIED when the research routes are not served yet).
  5. security_scan skips a screen recording instead of reading it.

Usage:  python3 tests/research_ux_tool.py
Exit:   0 = pass · 1 = a failure
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request

# `link` may start a preview server (a managed one); with no cap it never stops somebody else's preview to make room.
os.environ["PB_PREVIEW_MAX"] = "0"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TOOL = os.path.join(TOOLS, "research.py")
FIX = os.path.join(ROOT, "fixtures", "research")
UX = os.path.join(FIX, "ux")
sys.path.insert(0, TOOLS)
_spec = importlib.util.spec_from_file_location("research", TOOL)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
import research_analysis as RA  # noqa: E402
import research_stats as S  # noqa: E402
import security_scan  # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="pb-research-ux-")
_n = [0]
CHECKS = [0]
NOT_VERIFIED = []


def check(cond, msg):
    CHECKS[0] += 1
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title)


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def ux(name):
    return os.path.join(UX, name)


def jload(name):
    with open(ux(name), encoding="utf-8") as f:
        return json.load(f)


def codes(items):
    return sorted({i["code"] for i in items})


class Proj:
    """A fresh temp copy of the fixture, and a way to run the tool against it."""

    def __init__(self):
        _n[0] += 1
        self.dir = os.path.join(TMP, "p%d" % _n[0])
        shutil.copytree(FIX, self.dir)
        self.reg = os.path.join(self.dir, "registry.json")

    def run(self, *a):
        cmd = [sys.executable, TOOL, "--registry", self.reg, "--json"] + list(a)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=self.dir)
        try:
            out = json.loads(p.stdout)
        except ValueError:
            out = {}
        return p.returncode, out, p.stderr

    def text(self, *a):
        cmd = [sys.executable, TOOL, "--registry", self.reg] + list(a)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=self.dir)
        return p.returncode, p.stdout, p.stderr

    def data(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def save(self, d):
        with open(self.reg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def study(self, sid):
        return next(s for s in self.data()["research"]["studies"] if s["id"] == sid)

    def edit(self, sid, fn):
        d = self.data()
        fn(next(s for s in d["research"]["studies"] if s["id"] == sid))
        self.save(d)

    def raw(self):
        with open(self.reg, "rb") as f:
            return f.read()

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def write(self, name, obj):
        p = self.path(name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return p

    def write_bytes(self, name, data):
        p = self.path(name)
        with open(p, "wb") as f:
            f.write(data)
        return p

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()

    def exists(self, *parts):
        return os.path.exists(self.path(*parts))


SID = "rs-pay-test"
WEBM = b"\x1a\x45\xdf\xa3" + bytes(range(256)) * 4
EMAIL = "person.name@mailbox-demo.net"


def review_rows(p, sid):
    rc, out, err = p.run("review-plan", sid)
    assert rc == 0, (rc, out, err)
    rows = "\n".join("%s · yes · the words of the question hold" % i for i in out["items"])
    path = os.path.join(p.dir, "rows-%s.txt" % sid)
    with open(path, "w", encoding="utf-8") as f:
        f.write(rows + "\n")
    return path, out["items"]


def usability_ready(approved=True):
    p = Proj()
    rc, out, err = p.run("init", SID, "--method", "usability", "--scope", "collect", "--question", "Can couriers pay for a parcel?",
                         "--role", "courier", "--target", "screen:pay", "--mode", "moderated")
    assert rc == 0, (rc, out, err)
    rc, out, err = p.run("brief", SID, "--file", ux("usability-brief.json"))
    assert rc == 0, (rc, out, err)
    rc, out, err = p.run("plan", SID, "--file", ux("usability-plan.json"))
    assert rc == 0, (rc, out, err)
    if approved:
        path, _items = review_rows(p, SID)
        rc, out, err = p.run("review", SID, "--file", path)
        assert rc == 0, (rc, out, err)
        rc, out, err = p.run("approve", SID, "--note", "test data")
        assert rc == 0, (rc, out, err)
    return p


def usability_fielding(recording=True):
    p = usability_ready()
    for pid in ("P01", "P02", "P03"):
        rc, out, err = p.run("participant", SID, pid, "--status", "scheduled", "--segment", "rural courier", "--role", "courier")
        assert rc == 0, (rc, out, err)
    for s in ("s1", "s2", "s3"):
        rc, out, err = p.run("import", SID, ux("usability-%s.json" % s), "--kind", "session", "--consent", "yes")
        assert rc == 0, (s, rc, out, err)
    if recording:
        rec = p.write_bytes("rec.webm", WEBM)
        rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-ux02b2", "--consent", "yes")
        assert rc == 0, (rc, out, err)
    return p


def session_objs(p, sid):
    st = p.study(sid)
    pairs = []
    for e in st["evidence"]:
        if e["kind"] == "session" and not e.get("dropped"):
            with open(os.path.join(p.dir, e["file"]), "rb") as f:
                pairs.append((e, json.loads(f.read().decode("utf-8"))))
    return st, pairs


def recomputed(p, sid):
    st, pairs = session_objs(p, sid)
    return RA.analyze(st, pairs)


def event_index(name, typ):
    return next(i for i, e in enumerate(jload(name)["events"]) if e["type"] == typ)


def synthesis(p, with_second_issue=True):
    """A usability synthesis built from the analysis the tool stored — every cited number is read from it."""
    an = p.study(SID)["analysis"]
    t1, t2 = an["usability"]["tasks"]["t1"], an["usability"]["tasks"]["t2"]
    note_i = event_index("usability-s3.json", "note")
    err_i = event_index("usability-s2.json", "field-error")
    quote = next(e["text"] for e in jload("usability-s3.json")["events"] if e["type"] == "note")
    obs = [
        {"id": "o1", "evidence": "e3", "participant": "P03", "task": "t1", "event": note_i,
         "note": "Looked for the total on the handover screen, not on the pay screen", "tags": ["total-hidden"]},
        {"id": "o2", "evidence": "e2", "participant": "P02", "task": "t1", "event": err_i,
         "note": "Hit a required-field error on pay and went back to the route", "tags": ["total-hidden", "validation"]},
        {"id": "o3", "evidence": "e3", "participant": "P03", "task": "t1", "quote": quote,
         "note": "Said so out loud", "tags": ["total-hidden"]},
        {"id": "o4", "evidence": "e2", "participant": "P02", "task": "t1", "t": 25000,
         "note": "The error appeared 25 seconds in", "tags": ["validation"]}]
    issues = [{"id": "u1", "title": "The total is not where people look", "task": "t1", "screen": "pay", "severity": 3,
               "observations": ["o1", "o2"], "recommendation": "Show the total on the route screen.",
               "targets": [{"kind": "screen", "id": "pay"}]}]
    if with_second_issue:
        issues.append({"id": "u2", "title": "A required-field error with no hint", "task": "t1", "screen": "pay", "severity": 3,
                       "observations": ["o4"], "recommendation": "Say what is required."})
    return {
        "verdicts": {"h1": {"verdict": "mixed", "why": "Two of the three finished t1 unaided."},
                     "h2": {"verdict": "supported", "why": "All three found the total in t2."}},
        "observations": obs,
        "themes": [{"id": "th1", "title": "The total is hard to find", "tags": ["total-hidden"],
                    "insight": "People look for the total on the wrong screen."}],
        "issues": issues,
        "findings": [
            {"id": "f1", "text": "Most couriers completed the payment task.", "hypotheses": ["h1"],
             "evidence": [{"analysis": "usability.tasks.t1.success.x", "value": t1["success"]["x"]},
                          {"analysis": "usability.tasks.t1.success.n", "value": t1["success"]["n"]},
                          {"analysis": "usability.tasks.t1.success.rate", "value": t1["success"]["rate"]},
                          {"issue": "u1"}]},
            {"id": "f2", "text": "Every courier found the total.", "hypotheses": ["h2"],
             "evidence": [{"analysis": "usability.tasks.t2.success.x", "value": t2["success"]["x"]},
                          {"observation": "o1"}, {"evidence": "e3", "quote": quote, "participant": "P03"}]}],
        "refill": {"researchSummary": "Two of 3 couriers completed the payment task unaided; all 3 found the total."},
        "report": {"summary": "The payment task mostly works. The total is hard to find.",
                   "recommendations": [{"text": "Show the total earlier.", "issues": ["u1"], "route": "build"}],
                   "nextSteps": ["Retest after the change."], "limitations": ["Only three couriers took part."]}}


def synthesized():
    p = usability_fielding()
    rc, out, err = p.run("analyze", SID)
    assert rc == 0, (rc, out, err)
    f = p.write("synthesis.json", synthesis(p))
    rc, out, err = p.run("synthesize", SID, "--file", f)
    assert rc == 0, (rc, out, err)
    return p


# ═════════════════════════════════════════════════════════════════════════════
section("1. the catalog and the new methods at init")
p = Proj()
rc, out, err = p.run("methods")
cat = out.get("methods", [])
check(rc == 0 and {c["method"] for c in cat if c["runner"]} == set(R.METHODS) and len(R.METHODS) == 6,
      "methods: the catalog lists the six methods pb runs")
check(any(not c["runner"] for c in cat), "methods: listed-only methods are marked as not run here")
rc, txt, err = p.text("methods")
check(rc == 0 and "tree-test" in txt and "card-sort" in txt and "first-click" in txt, "methods: the table prints")
want_n = {"survey": 30, "interview": 5, "usability": 5, "tree-test": 50, "card-sort": 15, "first-click": 30}
check(R.DEFAULT_N == want_n, "DEFAULT_N follows the contract")
for m in R.METHODS:
    q = Proj()
    rc, out, err = q.run("init", "rs-m-" + m, "--method", m, "--scope", "collect", "--question", "A question?", "--segment", "app users")
    st = q.study("rs-m-" + m)
    cl = [c["id"] for c in st["logistics"]["checklist"]]
    check(rc == 0 and st["audience"]["targetN"] == want_n[m] and "plan-approved" in cl and "consent-ready" in cl,
          "init --method %s: a draft, targetN %d, the logistics checklist is seeded" % (m, want_n[m]))
q = Proj()
q.run("init", "rs-mode", "--method", "usability", "--scope", "collect", "--question", "q?", "--segment", "s", "--mode", "unmoderated")
check("kit-opened-clean" in [c["id"] for c in q.study("rs-mode")["logistics"]["checklist"]], "init --mode unmoderated: the kit items are on the checklist")
no_mode = jload("usability-plan.json")
no_mode["instrument"].pop("mode")
q.run("plan", "rs-mode", "--file", q.write("pm.json", no_mode))
check(q.study("rs-mode")["instrument"]["mode"] == "unmoderated", "plan: a plan without a mode keeps the one chosen at init")
q = Proj()
q.run("init", "rs-mode", "--method", "usability", "--scope", "collect", "--question", "q?", "--segment", "s", "--mode", "moderated")
q.run("plan", "rs-mode", "--file", q.write("pm.json", dict(no_mode, instrument=dict(no_mode["instrument"], mode="unmoderated"))))
check("kit-opened-clean" in [c["id"] for c in q.study("rs-mode")["logistics"]["checklist"]], "plan: an unmoderated plan adds the kit items to a moderated checklist")
q = Proj()
q.run("init", "rs-mode", "--method", "usability", "--scope", "collect", "--question", "q?", "--segment", "s")
check("kit-opened-clean" not in [c["id"] for c in q.study("rs-mode")["logistics"]["checklist"]], "init without --mode: moderated, no kit items")
rc, out, err = q.run("init", "rs-bad", "--method", "diary", "--scope", "collect", "--question", "q?", "--segment", "s")
check(rc == 2, "init --method diary: refused by the parser (exit 2)")

# ═════════════════════════════════════════════════════════════════════════════
section("2. the check rules of the four session methods (in process)")
base = usability_ready(approved=False)
reg = base.data()
U = base.study(SID)


def rules(study, regd=None):
    errs, warns = R.check_study(regd or reg, study)
    return codes(errs), codes(warns)


def mutated(fn, study=None):
    s = copy.deepcopy(study or U)
    fn(s)
    return s


def task_q(s, qid):
    return next(q for sec in s["instrument"]["sections"] for q in sec["questions"] if q["id"] == qid)


e, w = rules(U)
check(e == [] and w == [], "usability: the fixture plan is clean (no error, no warning)")
check("C-PLAN" in rules(mutated(lambda s: s["plan"].pop("objectives")))[0], "C-PLAN: no plan.objectives")
check("C-PLAN" in rules(mutated(lambda s: s["plan"].pop("researchQuestions")))[0], "C-PLAN: no plan.researchQuestions")
check("W-PLAN" in rules(mutated(lambda s: s["plan"].pop("schedule")))[1], "W-PLAN: no schedule is a warning, not an error")
check("C-PLAN" not in rules(mutated(lambda s: s["plan"].pop("schedule")))[0], "W-PLAN: and does not block")
check("C-MODE" in rules(mutated(lambda s: s["instrument"].update(mode="hybrid")))[0], "C-MODE: a mode that is not moderated/unmoderated/both")
check("C-RECORDING" in rules(mutated(lambda s: s["instrument"].update(recording={"screen": "yes"})))[0], "C-RECORDING: a non-boolean")
check("C-DEVICE" in rules(mutated(lambda s: s["instrument"].update(device="tv")))[0], "C-DEVICE: not a pb device")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(screen="nowhere")))[0], "C-TASK: the start screen does not resolve")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(success="")))[0], "C-TASK: no success text")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(criteria=[{"colour": "red"}])))[0], "C-TASK: an unknown criteria key")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(criteria=[{"screen": "nowhere"}])))[0], "C-TASK: a criteria screen that does not resolve")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(optimalPath=["route", "nowhere"])))[0], "C-TASK: an optimalPath screen that does not resolve")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1")["task"].update(timeLimitSec=0)))[0], "C-TASK: a time limit under one second")
check("C-TASK" in rules(mutated(lambda s: task_q(s, "t1").pop("task")))[0], "C-TASK: a task section whose question has no task object")
check("C-TESTS" in rules(mutated(lambda s: task_q(s, "t1").update(tests=[])))[0], "C-TESTS: a task that tests no hypothesis")
check("C-TESTS" not in rules(U)[0], "C-TESTS: a post-task SEQ with no `tests` is not asked for one")
check("W-SEQ" in rules(mutated(lambda s: s["instrument"]["sections"][1]["questions"].pop()))[1], "W-SEQ: a task with no post-task SEQ")
check("C-WARMUP" in rules(mutated(lambda s: s["instrument"]["sections"].pop(0)))[0], "C-WARMUP: a moderated usability test needs a warmup")
unmod = mutated(lambda s: (s["instrument"].update(mode="unmoderated"), s["instrument"]["sections"].pop(0)))
check("C-WARMUP" not in rules(unmod)[0] and "W-WARMUP" in rules(unmod)[1], "W-WARMUP: an unmoderated test without a warmup only warns")


def add_hyp(s):
    s["hypotheses"].append({"id": "h3", "statement": "x", "supportedIf": "a", "refutedIf": "b"})


check("C-HYP-UNTESTED" in rules(mutated(add_hyp))[0], "C-HYP-UNTESTED: a hypothesis no task tests")
check("C-METHOD" in rules(mutated(lambda s: s.update(method="diary-study")))[0], "C-METHOD: an unknown method")
check(rules(mutated(lambda s: s["instrument"]["sections"][1]["questions"].append(
    {"id": "late", "text": "How did that feel?", "type": "text", "tests": []})))[0] == [],
    "a typed question after a task question is its post-task question")

# tree test
q = Proj()
q.run("init", "rs-tree-test", "--method", "tree-test", "--scope", "collect", "--question", "Where?", "--segment", "app users", "--mode", "unmoderated")
rc, out, err = q.run("plan", "rs-tree-test", "--file", ux("tree-test-plan.json"))
T = q.study("rs-tree-test")
check(rc == 0 and T["plan"]["objectives"] and T["plan"]["participants"]["n"] == 50,
      "plan: the optional `plan` key merges the research plan (tree test)")
check(rules(T, q.data()) == ([], []), "tree-test: the fixture plan is clean")
nodes = lambda s: s["instrument"]["tree"]   # noqa: E731
check("C-TREE" in rules(mutated(lambda s: nodes(s)[1].update(parent="ghost"), T), q.data())[0], "C-TREE: a parent that is not a node")
check("C-TREE" in rules(mutated(lambda s: nodes(s)[1].update(id="n-orders"), T), q.data())[0], "C-TREE: a duplicate node id")
check("C-TREE" in rules(mutated(lambda s: nodes(s)[0].update(parent="n-refunds"), T), q.data())[0], "C-TREE: a cycle")
check("C-TREE" in rules(mutated(lambda s: task_q(s, "tt1")["tree"].update(correct=["ghost"]), T), q.data())[0], "C-TREE: a correct node that is not in the tree")
check("C-TREE" in rules(mutated(lambda s: task_q(s, "tt1")["tree"].update(correct=[]), T), q.data())[0], "C-TREE: no correct node")
check("C-TREE" in rules(mutated(lambda s: s["instrument"].pop("tree"), T), q.data())[0], "C-TREE: no tree at all")
check("W-HYPOTHETICAL" not in rules(T, q.data())[1], "tree-test: 'where would you go' is a scenario, not a hypothetical")

# card sort
q = Proj()
q.run("init", "rs-card-sort", "--method", "card-sort", "--scope", "collect", "--question", "How?", "--segment", "app users", "--mode", "unmoderated")
q.run("brief", "rs-card-sort", "--file", ux("brief-min.json"))
rc, out, err = q.run("plan", "rs-card-sort", "--file", ux("card-sort-plan.json"))
C = q.study("rs-card-sort")
e, w = rules(C, q.data())
check(rc == 0 and e == [] and w == ["W-CARDS"], "card-sort: the fixture plan is clean, with W-CARDS for six cards")
check("C-CARDS" in rules(mutated(lambda s: s["instrument"].update(cards=s["instrument"]["cards"][:3]), C), q.data())[0], "C-CARDS: fewer than four cards")


def dup_label(s):
    s["instrument"]["cards"][1]["label"] = s["instrument"]["cards"][0]["label"]


check("C-CARDS" in rules(mutated(dup_label, C), q.data())[0], "C-CARDS: two cards with one label")
many = lambda s: s["instrument"].update(cards=[{"id": "c-%d" % i, "label": "Card number %d" % i} for i in range(70)])   # noqa: E731
check("W-CARDS" in rules(mutated(many, C), q.data())[1] and "C-CARDS" not in rules(mutated(many, C), q.data())[0], "W-CARDS: seventy cards only warns")
check("C-SORT" in rules(mutated(lambda s: s["instrument"]["sort"].update(kind="bogus"), C), q.data())[0], "C-SORT: an unknown kind")
check("C-SORT" in rules(mutated(lambda s: s["instrument"]["sort"].update(categories=s["instrument"]["sort"]["categories"][:1]), C), q.data())[0],
      "C-SORT: a hybrid sort with one category")
check("C-HYP-UNTESTED" in rules(mutated(lambda s: s["instrument"]["sort"].pop("tests"), C), q.data())[0], "C-HYP-UNTESTED: sort.tests is what tests a card sort's hypothesis")
check("C-HYP-UNTESTED" not in rules(C, q.data())[0], "sort.tests counts as testing")

# first click
q = Proj()
q.run("init", "rs-first-click", "--method", "first-click", "--scope", "collect", "--question", "Where?", "--segment", "app users", "--mode", "unmoderated")
q.run("brief", "rs-first-click", "--file", ux("brief-min.json"))
rc, out, err = q.run("plan", "rs-first-click", "--file", ux("first-click-plan.json"))
F = q.study("rs-first-click")
check(rc == 0 and rules(F, q.data()) == ([], []), "first-click: the fixture plan is clean")
check("C-CLICK" in rules(mutated(lambda s: (task_q(s, "fc1")["click"].pop("target"), task_q(s, "fc1")["click"].pop("rect")), F), q.data())[0],
      "C-CLICK: neither a target nor a rect")
check("C-CLICK" in rules(mutated(lambda s: task_q(s, "fc1")["click"].update(rect={"x": 0.9, "y": 0.1, "w": 0.3, "h": 0.1}), F), q.data())[0],
      "C-CLICK: a rect past the edge of the screen")
check("C-CLICK" in rules(mutated(lambda s: task_q(s, "fc1")["click"].update(screen="nowhere"), F), q.data())[0], "C-CLICK: a screen that does not resolve")
check("C-CLICK" in rules(mutated(lambda s: task_q(s, "fc1").pop("click"), F), q.data())[0], "C-CLICK: a task with no click object")

# ═════════════════════════════════════════════════════════════════════════════
section("3. a usability study, verb by verb")
p = Proj()
rc, out, err = p.run("init", SID, "--method", "usability", "--scope", "collect", "--question", "Can couriers pay for a parcel?",
                     "--role", "courier", "--target", "screen:pay", "--mode", "moderated")
st = p.study(SID)
check(rc == 0 and st["status"] == "draft" and st["audience"]["targetN"] == 5 and st["instrument"]["mode"] == "moderated",
      "init: a draft usability study, targetN 5, mode moderated")

# a plan with one deliberate C-TASK error
bad = jload("usability-plan.json")
bad["instrument"]["sections"][1]["questions"][0]["task"]["screen"] = "nowhere"
badp = p.write("plan-bad.json", bad)
rc, out, err = p.run("plan", SID, "--file", badp)
rc2, out2, err2 = p.run("check", SID)
check(rc == 0 and rc2 == 1 and "C-TASK" in codes(out2["errors"]) and "C-PLAN" in codes(out2["errors"]),
      "check: the unresolved task screen is a C-TASK error, and the missing research plan a C-PLAN error")
rc, out, err = p.run("approve", SID, "--skip-review", "test")
check(rc == 1 and not p.exists("memory", "research", SID, "instrument", "plan.md"), "REFUSED approve while check has errors: no instrument file written")

rc, out, err = p.run("plan", SID, "--file", ux("usability-plan.json"))
rc2, out2, err2 = p.run("check", SID)
check(rc == 0 and rc2 == 1 and codes(out2["errors"]) == ["C-PLAN"], "plan: the fixed task clears C-TASK; only C-PLAN is left")

# brief
for label, content, expect in (("an unknown key", {"colour": "red"}, 2), ("a bad date", {"schedule": {"start": "next week"}}, 2),
                               ("an end before the start", {"schedule": {"start": "2026-03-10", "end": "2026-03-02"}}, 2),
                               ("an unknown sub-key", {"team": {"boss": "x"}}, 2), ("a bad number", {"participants": {"n": 0}}, 2)):
    rc, out, err = p.run("brief", SID, "--file", p.write("b.json", content))
    check(rc == expect, "brief REFUSES %s (exit %d)" % (label, rc))
before = p.raw()
rc, out, err = p.run("brief", SID, "--file", p.write("b.json", {"recruitment": {"note": "write to %s" % EMAIL}}))
check(rc == 1 and p.raw() == before, "brief REFUSES an email address in the plan, and writes nothing")
rc, out, err = p.run("brief", SID, "--file", ux("usability-brief.json"))
plan = p.study(SID)["plan"]
check(rc == 0 and plan["objectives"][0].startswith("Find out whether a courier") and plan["schedule"]["sessionMinutes"] == 40
      and plan["participants"]["n"] == 5, "brief: the research plan is merged into study.plan")
rc, out, err = p.run("brief", SID, "--file", p.write("b.json", {"plan": {"schedule": {"sessionMinutes": 50}}}))
plan = p.study(SID)["plan"]
check(rc == 0 and plan["schedule"] == {"start": "2026-03-02", "end": "2026-03-13", "sessionMinutes": 50},
      "brief: an object key merges key by key ({\"plan\": {...}} is read too)")
p.run("brief", SID, "--file", p.write("b.json", {"schedule": {"sessionMinutes": 40}}))
rc, out, err = p.run("check", SID)
check(rc == 0 and out["errors"] == [], "check: clean once the research plan exists")

# the bias review
path, items = review_rows(p, SID)
doc = p.read("memory", "research", SID, "instrument", "bias-review.md")
check(len(items) == 14 and "t1.nolabels" in items and "t1.goal" in items and "t2.single" in items and "w1.options" in items
      and "order.general-first" in items, "review-plan: scenario items for each task, form items for the warm-up question (%d items)" % len(items))
leak = ["Couriers reach the handover", "supportedIf", "What are you looking for?", "optimalPath", "The handover screen is reached after",
        "pay-cod", "h1", "criteria"]
check(not [x for x in leak if x in doc], "review-plan: shows the questions only (no hypothesis, probe, success text, path or criteria)")
rc, out, err = p.run("approve", SID)
check(rc == 1 and "bias review" in out.get("error", ""), "REFUSED approve without a review of this instrument")
rc, out, err = p.run("review", SID, "--file", path)
check(rc == 0 and out["summary"]["yes"] == 14, "review: 14 rows stored")

# approve writes the research documents
rc, out, err = p.run("approve", SID, "--note", "test data")
inst_dir = ("memory", "research", SID, "instrument")
want_files = ["plan.md", "moderator-guide.md", "tasks.md", "consent.md", "note-taking.csv"]
check(rc == 0 and all(p.exists(*(inst_dir + (f,))) for f in want_files), "approve: plan.md, moderator-guide.md, tasks.md, consent.md and note-taking.csv exist")
check("Find out whether a courier" in p.read(*(inst_dir + ("plan.md",))), "approve: plan.md carries the research plan")
cl = {c["id"]: c for c in p.study(SID)["logistics"]["checklist"]}
check(cl["plan-approved"]["done"] is True and cl["plan-approved"]["at"], "approve: ticks the plan-approved checklist item")
sums = {f: hashlib.sha256(open(p.path(*(inst_dir + (f,))), "rb").read()).hexdigest() for f in want_files}
rc, out, err = p.run("export", SID)
check(rc == 0 and sums == {f: hashlib.sha256(open(p.path(*(inst_dir + (f,))), "rb").read()).hexdigest() for f in want_files},
      "export: the generated documents are byte-identical run to run")

# a logistics change keeps G-STUDY; a change of purpose withdraws it
rc, out, err = p.run("brief", SID, "--file", p.write("b.json", {"schedule": {"sessionMinutes": 45}, "budget": "TEST DATA: six vouchers"}))
check(rc == 0 and out["withdrawn"] is False and p.study(SID)["status"] == "approved" and "45" in p.read(*(inst_dir + ("plan.md",))),
      "brief: schedule and budget do not withdraw G-STUDY, and plan.md follows")
rc, out, err = p.run("brief", SID, "--file", p.write("b.json", {"objectives": ["Find out whether a courier can pay unaided", "Find out where the total is looked for", "TEST DATA. A third aim"]}))
st = p.study(SID)
cl = {c["id"]: c for c in st["logistics"]["checklist"]}
check(rc == 0 and out["withdrawn"] is True and st["status"] == "draft" and st["gates"][-1].get("withdrawnAt") and cl["plan-approved"]["done"] is False,
      "brief: changing the objectives withdraws G-STUDY (a draft again, plan-approved unticked)")
rc, out, err = p.run("approve", SID, "--note", "approved again")
check(rc == 0 and p.study(SID)["status"] == "approved", "approve again: the bias review survived a plan-only change")

# participants
p.run("participant", SID, "P01", "--status", "scheduled", "--segment", "rural courier", "--role", "courier", "--at", "2026-03-03T10:00")
p.run("participant", SID, "P02", "--status", "invited", "--segment", "city courier")
rc, out, err = p.run("participant", SID, "P03", "--status", "screened")
people = {x["id"]: x for x in p.study(SID)["participants"]}
check(rc == 0 and sorted(people) == ["P01", "P02", "P03"] and people["P01"]["scheduledAt"] == "2026-03-03T10:00"
      and people["P01"]["status"] == "scheduled" and people["P02"]["incentive"] == "none", "participant: a pseudonymous tracker (add and upsert)")
rc, out, err = p.run("participant", SID, "p1")
check(rc == 2, "participant REFUSES a code that is not P01…")
rc, out, err = p.run("participant", SID, "P04", "--note", "write to %s" % EMAIL)
check(rc == 1 and "P04" not in [x["id"] for x in p.study(SID)["participants"]] and EMAIL not in err and EMAIL not in json.dumps(out),
      "participant REFUSES an email in --note, stores nothing and does not echo it")
rc, out, err = p.run("participant", SID, "P04", "--segment", "call 0912345678")
check(rc == 1 and "P04" not in [x["id"] for x in p.study(SID)["participants"]], "participant REFUSES a phone number in --segment")
rc, out, err = p.run("participant", SID, "P04", "--status", "bogus")
check(rc == 2, "participant REFUSES an unknown status")
rc, out, err = p.run("participant", SID, "P04", "--role", "nobody")
check(rc == 1, "participant REFUSES a role meta.roles does not declare")
rc, out, err = p.run("participant", SID, "P04", "--pilot")
rc2, out2, err2 = p.run("participant", SID, "P04", "--remove")
check(rc == 0 and rc2 == 0 and "P04" not in [x["id"] for x in p.study(SID)["participants"]], "participant --remove drops a row that has no evidence")

# logistics
rc, out, err = p.run("logistics", SID, "--done", "consent-ready", "--done", "screener-ready")
check(rc == 0 and {c["id"] for c in out["checklist"] if c["done"]} == {"plan-approved", "consent-ready", "screener-ready"},
      "logistics --done ticks items (and says which are done)")
rc, out, err = p.run("logistics", SID, "--undo", "screener-ready")
check(rc == 0 and "screener-ready" not in {c["id"] for c in out["checklist"] if c["done"]}, "logistics --undo")
rc, out, err = p.run("logistics", SID, "--done", "no-such-item")
check(rc == 2, "logistics REFUSES an item that is not on the checklist (exit 2)")
rc, out, err = p.run("logistics", SID, "--add", "Print the consent sheet")
check(rc == 0 and any(c["text"] == "Print the consent sheet" and c["done"] is False for c in out["checklist"]), "logistics --add appends an item")
rc, txt, err = p.text("logistics", SID)
check(rc == 0 and "[x] plan-approved" in txt and "scheduled" in txt and "P01" in txt and "invited" in txt and "2026-03-02 to 2026-03-13" in txt,
      "logistics: the checklist, the participant pipeline by status and the schedule print")

# the kit
rc, out, err = p.run("kit", SID)
kit_path = p.path("memory", "research", SID, "kit", SID + "-kit.html")
kit = open(kit_path, encoding="utf-8").read() if os.path.exists(kit_path) else ""
check(rc == 0 and out.get("kit") == "memory/research/%s/kit/%s-kit.html" % (SID, SID) and "PB_RS_SESSION" in kit,
      "kit: one HTML file written to memory/research/<id>/kit/")
secret = ["Couriers reach the handover", "Most couriers complete t1 without help", "Fewer than half of the couriers", '"research"',
          '"hypotheses"', "pay-cod", "The handover screen is reached after", "optimalPath", "Find out where the total",
          "Whether the amount moves"]
check(not [x for x in secret if x in kit], "kit: carries no hypothesis, no threshold, no research slice, no success text, no answer")
check('"sink":"download"' in kit and "Under a year" in kit, "kit: a download sink, and the participant's own questions")
rc, txt, err = p.text("kit", SID)
check(rc == 0 and "SEND" in txt and "BACK" in txt and "IMPORT" in txt, "kit: says what to send and how results come back")
rc, out, err = p.run("kit", SID, "--out", "../escape.html")
check(rc == 2 and not os.path.exists(os.path.join(TMP, "escape.html")), "kit REFUSES an --out outside the project")
rc, out, err = p.run("kit", SID, "--out", "custom-kit.html")
check(rc == 0 and p.exists("custom-kit.html"), "kit --out writes inside the project")
q = Proj()
q.run("init", SID, "--method", "usability", "--scope", "collect", "--question", "q?", "--role", "courier")
q.run("plan", SID, "--file", ux("usability-plan.json"))
rc, out, err = q.run("kit", SID)
check(rc == 1 and not q.exists("memory", "research", SID, "kit"), "kit REFUSES a draft study")
rc, out, err = q.run("kit", SID, "--pilot")
check(rc == 0 and q.exists("memory", "research", SID, "kit", SID + "-kit.html"), "kit --pilot works on a draft (a rehearsal)")

# import
fix = {n: jload("usability-%s.json" % n) for n in ("s1", "s2", "s3")}
rc, out, err = p.run("import", SID, ux("usability-s1.json"), "--kind", "session", "--consent", "unknown")
check(rc == 1 and not p.study(SID)["evidence"], "REFUSED --kind session with --consent unknown: nothing stored")
rc, out, err = p.run("import", SID, ux("usability-s1.json"), "--kind", "session", "--consent", "no")
check(rc == 1 and not p.study(SID)["evidence"], "REFUSED --kind session with --consent no")
wrong = dict(fix["s1"], study="rs-other", sessionId="s-wrong01")
rc, out, err = p.run("import", SID, p.write("wrong.json", wrong), "--kind", "session", "--consent", "yes")
check(rc == 1 and not p.study(SID)["evidence"], "REFUSED a session file made for another study")
noconsent = copy.deepcopy(fix["s1"])
noconsent["consent"]["session"] = False
noconsent["sessionId"] = "s-nocons1"
rc, out, err = p.run("import", SID, p.write("noconsent.json", noconsent), "--kind", "session", "--consent", "yes")
check(rc == 1 and not p.study(SID)["evidence"], "REFUSED a session whose own consent.session is not true")
rc, out, err = p.run("import", SID, ux("usability-s1.json"), "--kind", "session", "--consent", "yes", "--participant", "P02")
check(rc == 1, "REFUSED --participant that disagrees with the file")
for s in ("s1", "s2", "s3"):
    rc, out, err = p.run("import", SID, ux("usability-%s.json" % s), "--kind", "session", "--consent", "yes")
    check(rc == 0 and out["kind"] == "session", "import --kind session: %s stored as %s" % (s, out.get("imported")))
st = p.study(SID)
files = [e["file"] for e in st["evidence"]]
modes = [os.stat(p.path(f)).st_mode & 0o777 for f in files]
check([e["id"] for e in st["evidence"]] == ["e1", "e2", "e3"] and all(m == 0o444 for m in modes) and st["status"] == "fielding",
      "import: e1..e3, read-only (0444), study is fielding")
check({x["id"]: x["status"] for x in st["participants"]} == {"P01": "done", "P02": "done", "P03": "done"}
      and st["evidence"][0]["session"]["id"] == "s-ux01a1" and st["evidence"][0]["consent"] == "yes", "import: the participants are done; the row carries the session summary")
rc, out, err = p.run("import", SID, ux("usability-s1.json"), "--kind", "session", "--consent", "yes")
check(rc == 1 and len(p.study(SID)["evidence"]) == 3, "REFUSED the same session twice")
rc, out, err = p.run("import", SID, ux("usability-pilot.json"), "--kind", "session", "--consent", "yes")
st = p.study(SID)
check(rc == 0 and out["pilot"] is True and len(st["evidence"]) == 3 and len(st["pilots"]) == 1 and p.exists("memory", "research", SID, "pilot", "s-ux00pil.json"),
      "import: a pilot session is stored as a pilot, never as evidence")
rc, out, err = p.run("pilots", SID)
check(rc == 0 and out["pilots"][0]["sessionId"] == "s-ux00pil", "pilots: lists the pilot session")

# recordings
rec = p.write_bytes("rec.webm", WEBM)
rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-ux01a1", "--consent", "yes")
check(rc == 1 and not [e for e in p.study(SID)["evidence"] if e["kind"] == "recording"], "REFUSED a recording for a session without recording consent")
rc, out, err = p.run("import", SID, p.write_bytes("fake.webm", b"not a recording at all"), "--kind", "recording", "--session", "s-ux02b2", "--consent", "yes")
check(rc == 1, "REFUSED a file with no WebM header")
rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-nope000", "--consent", "yes")
check(rc == 1, "REFUSED a recording for a session that is not stored")
rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-ux02b2", "--consent", "unknown")
check(rc == 1, "REFUSED a session-linked recording with --consent unknown")
rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-ux02b2", "--consent", "yes")
st = p.study(SID)
rrow = next((e for e in st["evidence"] if e["kind"] == "recording"), {})
srow = next(e for e in st["evidence"] if e["id"] == "e2")
check(rc == 0 and rrow.get("session") == "s-ux02b2" and rrow["id"] == "e4" and srow["session"]["media"] == ["e4"]
      and os.stat(p.path(rrow["file"])).st_mode & 0o777 == 0o444, "import --kind recording --session: linked, hashed, read-only")
check(rrow.get("sha256") == hashlib.sha256(WEBM).hexdigest() and rrow["bytes"] == len(WEBM), "import: the recording's hash is the file's")
rc, out, err = p.run("import", SID, rec, "--kind", "recording", "--session", "s-ux02b2", "--consent", "yes")
check(rc == 1, "REFUSED the same recording twice")
rc, out, err = p.run("import", SID, p.write_bytes("other.webm", WEBM + b"x"), "--kind", "recording", "--session", "s-ux01a1", "--consent", "yes")
check(rc == 1, "REFUSED a second recording route into a session with no recording consent")
rc, out, err = p.run("verify", SID)
check("V-EVIDENCE" not in codes(out.get("errors", [])), "verify: the recording row's hash checks (streamed)")
q = Proj()
q.run("init", "rs-opaque", "--method", "interview", "--scope", "collect", "--question", "q?", "--role", "courier")
q.run("plan", "rs-opaque", "--file", os.path.join(FIX, "interview-plan.json"))
q.run("approve", "rs-opaque", "--skip-review", "test")
rc, out, err = q.run("import", "rs-opaque", q.write_bytes("call.webm", WEBM), "--kind", "recording", "--consent", "yes", "--participant", "P01")
check(rc == 0 and q.study("rs-opaque")["evidence"][0]["kind"] == "recording" and "session" not in q.study("rs-opaque")["evidence"][0],
      "import --kind recording without --session keeps today's opaque behaviour")
rc, out, err = q.run("import", "rs-opaque", os.path.join(FIX, "transcript-p01.txt"), "--kind", "transcript", "--consent", "yes", "--session", "s-abcd1")
check(rc == 2, "REFUSED --session with a kind that is not a recording")

# analyze
before = p.raw()
rc, txt, err = p.text("analyze", SID)
after_text = p.raw()
rc, out, err = p.run("analyze", SID)
an = p.study(SID)["analysis"]
check(rc == 0 and out["analysis"] == an and an["method"] == "usability" and an["n"] == 3 and an["inputs"] == ["e1", "e2", "e3"],
      "analyze: stored in study.analysis from the three sessions (the recording and the pilot are not inputs)")
check(canon(an) == canon(recomputed(p, SID)), "analyze: byte-equal to research_analysis.analyze recomputed here")
check("t1" in txt and "success" in txt and "SUS" in txt and "2/3" in txt, "analyze: prints the per-task table")
t1s = an["usability"]["tasks"]["t1"]["success"]
want = S.adjusted_wald(2, 3)
check(t1s["x"] == 2 and t1s["n"] == 3 and t1s["rate"] == S.r4(want["rate"]) and t1s["low"] == S.r4(want["low"]) and t1s["high"] == S.r4(want["high"]),
      "analyze: t1 success is 2 of 3 with the adjusted-Wald interval")
check(an["usability"]["tasks"]["t2"]["success"]["x"] == 3 and an["usability"]["tasks"]["t1"]["abandoned"] == 1, "analyze: t2 is 3 of 3; t1 has one abandonment")
p.run("analyze", SID)
check(canon(p.study(SID)["analysis"]) == canon(an), "analyze: running it again gives the same analysis")

# synthesize
syn = synthesis(p)
f = p.write("synthesis.json", syn)
bad_issue = copy.deepcopy(syn)
bad_issue["issues"][0]["frequency"] = 0.5
raw0 = p.raw()
rc, out, err = p.run("synthesize", SID, "--file", p.write("syn-bad.json", bad_issue))
check(rc == 2 and p.raw() == raw0, "synthesize REFUSES a computed number (frequency) typed into an issue, and writes nothing")
bad_obs = copy.deepcopy(syn)
bad_obs["observations"][0]["extra"] = "x"
rc, out, err = p.run("synthesize", SID, "--file", p.write("syn-bad.json", bad_obs))
check(rc == 2 and p.raw() == raw0, "synthesize REFUSES an unknown observation key")
bad_rep = copy.deepcopy(syn)
bad_rep["report"]["recommendations"][0]["route"] = "somewhere"
rc, out, err = p.run("synthesize", SID, "--file", p.write("syn-bad.json", bad_rep))
check(rc == 2, "synthesize REFUSES a route that is not clarify/explore/build/none")
bad_key = {"analysis": {"n": 99}}
rc, out, err = p.run("synthesize", SID, "--file", p.write("syn-bad.json", bad_key))
check(rc == 2, "synthesize REFUSES a typed `analysis`")
rc, out, err = p.run("synthesize", SID, "--file", f)
st = p.study(SID)
check(rc == 0 and out["ok"] and st["status"] == "analysed", "synthesize: observations, themes, issues, findings and report accepted; verify clean; analysed")
check("W-ONE-PARTICIPANT" in codes(out["warnings"]), "verify: W-ONE-PARTICIPANT for the severity 3 issue u2 that rests on one participant")
iss = st["analysis"]["issues"]
check(iss["u1"] == {"participants": 2, "frequency": S.r4(2 / 3.0), "priority": S.r4(3 * 2 / 3.0)} and iss["u2"]["participants"] == 1
      and "participants" not in st["issues"][0] and "frequency" not in st["issues"][0],
      "synthesize: issue frequency and priority are the tool's (in analysis.issues), never in the issue")
check(st["analysis"]["affinity"]["tags"]["total-hidden"] == {"observations": 3, "participants": 2, "tasks": ["t1"]}, "synthesize: the affinity counts are the tool's")
before = p.raw()
rc, out, err = p.run("affinity", SID)
check(rc == 0 and out["tags"]["validation"] == {"observations": 2, "participants": 1, "tasks": ["t1"]} and p.raw() == before, "affinity: read-only; tag x participant counts")
rc, out, err = p.run("verify", SID)
check(rc == 0 and out["errors"] == [], "verify: clean")
rc, out, err = p.run("show", SID)
sm = out["summary"]
check(rc == 0 and sm["sessions"] == 3 and sm["pilots"] == 1 and sm["issues"] == 2 and sm["participants"] == 4 and "success" in (sm["headline"] or ""),
      "show: sessions, pilots, issues, participants and the analysis headline")
rc, txt, err = p.text("list")
check(rc == 0 and "Usability test" in txt and "3 session(s)" in txt and "2 issue(s)" in txt, "list: method label, sessions, pilots, issues")

# report and refill
rc, out, err = p.run("report", SID)
rep_md, rep_html = ("memory/research/%s/report/report.md" % SID, "memory/research/%s/report/report.html" % SID)
check(rc == 0 and out["report"] == [rep_md, rep_html] and p.exists(rep_md) and p.exists(rep_html), "report: report.md and report.html written")
check("Draft — not yet approved at G-INSIGHT" in p.read(rep_md) and "Draft — not yet approved at G-INSIGHT" in p.read(rep_html), "report: the Draft banner shows before G-INSIGHT")
check("P03" in p.read(rep_md) and EMAIL not in p.read(rep_md) and "<script" not in p.read(rep_html), "report: participants by pseudonym; the HTML has no script")
md_before = p.read(rep_md)
rc, out, err = p.run("refill", SID, "--approved", "--note", "approved at G-INSIGHT")
check(rc == 0 and p.study(SID)["status"] == "applied" and out["report"] == [rep_md, rep_html], "refill --approved: applied, and the report is regenerated")
check("Draft — not yet approved" not in p.read(rep_md) and "Draft — not yet approved" not in p.read(rep_html) and p.read(rep_md) != md_before,
      "refill --approved: the Draft banner is gone")
rc, out, err = p.run("verify", SID)
check(rc == 0, "verify: still clean once applied")
q = Proj()
q.run("init", "rs-nr", "--method", "usability", "--scope", "collect", "--question", "q?", "--role", "courier")
rc, out, err = q.run("report", "rs-nr")
check(rc == 1 and not q.exists("memory", "research", "rs-nr", "report"), "REFUSED report for a study that has not been synthesized")

# ═════════════════════════════════════════════════════════════════════════════
section("4. refusals: the analysis cannot drift from the evidence")
p = synthesized()
good = p.raw()


def tamper_finding(study):
    study["findings"][0]["evidence"][0]["value"] = 3        # the real x is 2


p.edit(SID, tamper_finding)
rc, out, err = p.run("verify", SID)
check(rc == 1 and "V-ANALYSIS" in codes(out["errors"]) and any("is 2, not 3" in e["msg"] for e in out["errors"]),
      "verify: V-ANALYSIS for a cited analysis value that is wrong")
md_path = p.path("memory", "research", SID, "report")
rc, out, err = p.run("report", SID)
check(rc == 1 and not os.path.exists(md_path), "REFUSED report while verify fails: no report written")
rc, out, err = p.run("refill", SID, "--approved")
check(rc == 1 and p.study(SID)["status"] == "analysed", "REFUSED refill while verify fails")
p.save(json.loads(good))

p.edit(SID, lambda s: s["analysis"]["usability"]["tasks"]["t1"]["success"].update(x=1))
rc, out, err = p.run("verify", SID)
check(rc == 1 and "V-ANALYSIS" in codes(out["errors"]) and any("differs" in e["msg"] for e in out["errors"]),
      "verify: V-ANALYSIS for a stored analysis edited by hand")
p.save(json.loads(good))

p.edit(SID, lambda s: s["findings"][1]["evidence"].append({"issue": "u9"}))
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-FINDING" and "u9" in e["msg"] for e in out["errors"]), "verify: a finding citing an issue that does not exist")
p.save(json.loads(good))

p.edit(SID, lambda s: s["findings"][1]["evidence"].append({"observation": "o9"}))
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-FINDING" and "o9" in e["msg"] for e in out["errors"]), "verify: a finding citing an observation that does not exist")
p.save(json.loads(good))

obs_cases = (
    ("an event index out of range", lambda s: s["observations"][0].update(event=9999), "out of range"),
    ("a t past the end of the session", lambda s: s["observations"][3].update(t=999999), "after the end"),
    ("a quote that is not in the evidence", lambda s: s["observations"][2].update(quote="Words nobody said in this session"), "word for word"),
    ("no note", lambda s: s["observations"][0].update(note=""), "no note"),
    ("a bad tag", lambda s: s["observations"][0].update(tags=["Bad Tag"]), "tag"),
    ("two ways of pointing at the evidence", lambda s: s["observations"][0].update(t=100), "exactly one"),
    ("evidence that is not stored", lambda s: s["observations"][0].update(evidence="e9"), "not stored"),
    ("a participant that is not the evidence's", lambda s: s["observations"][0].update(participant="P01"), "P03"),
    ("a task the study does not have", lambda s: s["observations"][0].update(task="t9"), "t9"),
)
for label, fn, frag in obs_cases:
    p.edit(SID, lambda s, fn=fn: fn(s))
    rc, out, err = p.run("verify", SID)
    check(rc == 1 and any(e["code"] == "V-OBS" and frag in e["msg"] for e in out["errors"]), "verify: V-OBS for %s" % label)
    p.save(json.loads(good))
issue_cases = (
    ("a severity of 5", lambda s: s["issues"][0].update(severity=5), "severity"),
    ("an unknown observation", lambda s: s["issues"][0].update(observations=["o1", "o9"]), "o9"),
    ("an unknown task", lambda s: s["issues"][0].update(task="t9"), "t9"),
    ("no observations", lambda s: s["issues"][0].update(observations=[]), "no observation"),
    ("a screen that is not one", lambda s: s["issues"][0].update(screen="nowhere"), "nowhere"),
)
for label, fn, frag in issue_cases:
    p.edit(SID, lambda s, fn=fn: fn(s))
    rc, out, err = p.run("verify", SID)
    check(rc == 1 and any(e["code"] == "V-ISSUE" and frag in e["msg"] for e in out["errors"]), "verify: V-ISSUE for %s" % label)
    p.save(json.loads(good))
p.edit(SID, lambda s: s["themes"][0].update(tags=["never-used"]))
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-THEME" and "never-used" in e["msg"] for e in out["errors"]), "verify: V-THEME for a tag no observation carries")
p.save(json.loads(good))
p.edit(SID, lambda s: s["report"]["recommendations"][0].update(issues=["u9"]))
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-REPORT" for e in out["errors"]), "verify: V-REPORT for a recommendation citing an issue that does not exist")
p.save(json.loads(good))
p.edit(SID, lambda s: s["report"].update(summary="Some 7777 couriers loved it."))
rc, out, err = p.run("verify", SID)
check(rc == 0 and any(w["code"] == "W-NUMBER" and "report.summary" in w["where"] for w in out["warnings"]),
      "verify: W-NUMBER for a number in the report narrative that no analysis holds")
p.save(json.loads(good))
rc, out, err = p.run("verify", SID)
check(rc == 0 and "W-NUMBER" not in codes(out["warnings"]), "verify: the numbers the analysis holds are allowed in the narrative")

# stale inputs
extra = copy.deepcopy(jload("usability-s1.json"))
extra.update(sessionId="s-ux04d4", participant="P04")
extra["startedAt"] = "2026-03-06T10:00:00Z"
extra["endedAt"] = "2026-03-06T10:01:05Z"
rc, out, err = p.run("import", SID, p.write("extra.json", extra), "--kind", "session", "--consent", "yes")
check(rc == 0 and p.study(SID)["status"] == "fielding" and any("W-REFIELD" in w for w in out["warnings"]), "import: another session re-opens fielding with a warning")
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-ANALYSIS" and "stale" in e["msg"] for e in out["errors"]), "verify: V-ANALYSIS for a stale inputsHash after an extra import")
rc, out, err = p.run("analyze", SID)
check(rc == 0 and p.study(SID)["analysis"]["n"] == 4 and canon(p.study(SID)["analysis"]) == canon(recomputed(p, SID)), "analyze: n=4 after the extra import")
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] == "V-ANALYSIS" and "is 3, not 2" in e["msg"] for e in out["errors"]),
      "verify: re-analysing is not enough — the finding's cited value (2) no longer holds (3 of 4)")
p.save(json.loads(good))

# a participant with two sessions
dup = copy.deepcopy(jload("usability-s1.json"))
dup.update(sessionId="s-ux05e5")
dup["startedAt"] = "2026-03-07T10:00:00Z"
dup["endedAt"] = "2026-03-07T10:01:05Z"
rc, out, err = p.run("import", SID, p.write("dup.json", dup), "--kind", "session", "--consent", "yes")
rc, out, err = p.run("analyze", SID)
w1 = [w for w in out["warnings"] if w["code"] == "W-DUP-PARTICIPANT"]
check(rc == 0 and len(w1) == 1 and "P01" in w1[0]["msg"], "analyze: W-DUP-PARTICIPANT when one participant has two sessions")
rc, txt, err = p.text("analyze", SID)
check("W-DUP-PARTICIPANT" in txt, "analyze: the warning is printed")
rc, out, err = p.run("verify", SID)
check("W-DUP-PARTICIPANT" in codes(out["warnings"]), "verify: W-DUP-PARTICIPANT as a warning")

# a withdrawn participant
p = synthesized()
good = p.raw()
rc, out, err = p.run("participant", SID, "P03", "--status", "withdrawn")
check(rc == 0 and out["evidence"] == ["e3"] and "drop-evidence" in p.text("participant", SID, "P03", "--status", "withdrawn")[1],
      "participant --status withdrawn: says the evidence is still there and how to drop it")
rc, out, err = p.run("participant", SID, "P03", "--remove")
check(rc == 1 and "P03" in [x["id"] for x in p.study(SID)["participants"]], "participant --remove REFUSED while the participant has evidence")
lateP3 = copy.deepcopy(jload("usability-s3.json"))
lateP3["sessionId"] = "s-ux06f6"
rc, out, err = p.run("import", SID, p.write("late.json", lateP3), "--kind", "session", "--consent", "yes")
check(rc == 1, "import REFUSED a session of a withdrawn participant")
rc, out, err = p.run("drop-evidence", SID, "e3", "--reason", "P03 withdrew")
rc, out, err = p.run("verify", SID)
check(rc == 1 and any(e["code"] in ("V-OBS", "V-ANALYSIS") for e in out["errors"]), "verify: observations on a dropped session, and a stale analysis, are errors")
rc, out, err = p.run("analyze", SID)
check(rc == 0 and p.study(SID)["analysis"]["n"] == 2 and p.study(SID)["analysis"]["excluded"] == {"e3": "dropped"}, "analyze: a dropped session is excluded and listed")

q = usability_fielding()
rc, out, err = q.run("drop-evidence", SID, "e2", "--reason", "P02 withdrew")
st = q.study(SID)
rrow = next(e for e in st["evidence"] if e["id"] == "e4")
check(rc == 0 and out["alsoDropped"] == ["e4"] and rrow["dropped"] and not q.exists(rrow["file"]) and not q.exists(st["evidence"][1]["file"]),
      "drop-evidence: a session's screen recording is dropped with it (the file goes, the row and hash stay)")

# other methods refused
q = Proj()
q.run("init", "rs-cod", "--method", "survey", "--scope", "collect", "--question", "Q?", "--role", "courier")
q.run("plan", "rs-cod", "--file", os.path.join(FIX, "survey-plan.json"))
q.run("approve", "rs-cod", "--skip-review", "test")
rc, out, err = q.run("import", "rs-cod", os.path.join(FIX, "forms-responses.csv"), "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
before = q.raw()
rc, out, err = q.run("analyze", "rs-cod")
check(rc == 1 and "session methods" in out.get("error", "") and q.raw() == before, "REFUSED analyze on a survey, with a clear message")
rc, out, err = q.run("tally", "rs-cod")
check(rc == 0, "a survey is still tallied")
rc, out, err = q.run("kit", "rs-cod")
check(rc == 1, "REFUSED kit for a survey")
rc, out, err = q.run("link", "rs-cod")
check(rc == 1, "REFUSED link for a survey")
rc, out, err = q.run("import", "rs-cod", ux("usability-s1.json"), "--kind", "session", "--consent", "yes")
check(rc == 1, "REFUSED a session file imported into a survey")
rc, out, err = q.run("synthesize", "rs-cod", "--file", q.write("s.json", {"issues": [{"id": "u1", "title": "x", "severity": 1, "observations": []}]}))
check(rc == 2, "REFUSED issues in a survey's synthesis")

# ═════════════════════════════════════════════════════════════════════════════
section("5. a tree test, a card sort and a first-click study, end to end")


def method_ready(sid, method, plan_file, sessions, brief=None, mode="unmoderated"):
    p = Proj()
    rc, out, err = p.run("init", sid, "--method", method, "--scope", "collect", "--question", "TEST DATA question?",
                         "--segment", "existing app users", "--mode", mode)
    assert rc == 0, (rc, out, err)
    if brief:
        rc, out, err = p.run("brief", sid, "--file", ux(brief))
        assert rc == 0, (rc, out, err)
    rc, out, err = p.run("plan", sid, "--file", ux(plan_file))
    assert rc == 0, (rc, out, err)
    return p


# tree test
p = method_ready("rs-tree-test", "tree-test", "tree-test-plan.json", None)
rc, out, err = p.run("check", "rs-tree-test")
check(rc == 0, "tree-test: check clean")
path, items = review_rows(p, "rs-tree-test")
doc = p.read("memory", "research", "rs-tree-test", "instrument", "bias-review.md")
check({"tt1.treewords", "tt2.treewords", "tt1.neutral"} <= set(items) and "order.general-first" in items,
      "tree-test review-plan: a tree-words item per task")
check("- Orders" in doc and "  - Refunds" in doc and "  - Addresses" in doc, "tree-test review-plan: lists the labels of the tree, indented by level")
check("correct" not in doc and "n-refunds" not in doc and "h1" not in doc and "supportedIf" not in doc, "tree-test review-plan: never the correct answer")
rc, out, err = p.run("review", "rs-tree-test", "--file", path)
rc, out, err = p.run("approve", "rs-tree-test")
check(rc == 0 and p.exists("memory", "research", "rs-tree-test", "instrument", "tasks.md") and p.exists("memory", "research", "rs-tree-test", "instrument", "consent.md"),
      "tree-test approve: tasks.md and consent.md written")
check("n-refunds" not in p.read("memory", "research", "rs-tree-test", "instrument", "consent.md"), "tree-test: the participant-facing consent holds no answer key")
for s in ("tree-test-s1", "tree-test-s2"):
    rc, out, err = p.run("import", "rs-tree-test", ux(s + ".json"), "--kind", "session", "--consent", "yes")
    check(rc == 0, "tree-test import %s" % s)
rc, out, err = p.run("analyze", "rs-tree-test")
an = p.study("rs-tree-test")["analysis"]
tt = an["treeTest"]["tasks"]
check(rc == 0 and canon(an) == canon(recomputed(p, "rs-tree-test")), "tree-test analyze: equal to research_analysis recomputed")
check(tt["tt1"]["success"]["x"] == 1 and tt["tt1"]["success"]["n"] == 2 and tt["tt2"]["success"]["x"] == 2
      and {d["node"]: d["count"] for d in tt["tt1"]["destinations"]} == {"n-refunds": 1, "n-help": 1},
      "tree-test analyze: tt1 1 of 2 (one chose Help), tt2 2 of 2")

# card sort
p = method_ready("rs-card-sort", "card-sort", "card-sort-plan.json", None, brief="brief-min.json")
rc, out, err = p.run("check", "rs-card-sort")
check(rc == 0 and codes(out["warnings"]) == ["W-CARDS"], "card-sort: check passes (W-CARDS for six cards)")
path, items = review_rows(p, "rs-card-sort")
doc = p.read("memory", "research", "rs-card-sort", "instrument", "bias-review.md")
check(items == ["cards.leadword", "cards.single", "cards.neutral"], "card-sort review-plan: leading word, one thing per card, no category names (no questions to review)")
check("- Refund an order" in doc and "- Pay on delivery" in doc and "Money" not in doc, "card-sort review-plan: the card labels, and no category")
rc, out, err = p.run("review", "rs-card-sort", "--file", path)
rc, out, err = p.run("approve", "rs-card-sort")
check(rc == 0 and p.exists("memory", "research", "rs-card-sort", "instrument", "cards.md"), "card-sort approve: cards.md written")
for s in ("card-sort-s1", "card-sort-s2"):
    rc, out, err = p.run("import", "rs-card-sort", ux(s + ".json"), "--kind", "session", "--consent", "yes")
    check(rc == 0, "card-sort import %s" % s)
rc, out, err = p.run("analyze", "rs-card-sort")
an = p.study("rs-card-sort")["analysis"]
cs = an["cardSort"]
check(rc == 0 and canon(an) == canon(recomputed(p, "rs-card-sort")), "card-sort analyze: equal to research_analysis recomputed")
check(cs["n"] == 2 and cs["kind"] == "hybrid" and cs["similarity"]["c-track|c-address"] == 1.0 and cs["similarity"]["c-pay|c-receipt"] == 1.0
      and cs["similarity"]["c-refund|c-track"] == 0.0, "card-sort analyze: both put Track and Change-address together (1.0), Refund and Track never (0.0)")
check(["c-track", "c-address"] in cs["clusters"] and ["c-pay", "c-receipt"] in cs["clusters"], "card-sort analyze: clusters at similarity 0.5")
check(cs["categories"]["k-money"]["count"] == 2 and cs["categories"]["k-money"]["cards"]["c-pay"] == 1.0, "card-sort analyze: category agreement for the fixed categories")

# first click
p = method_ready("rs-first-click", "first-click", "first-click-plan.json", None, brief="brief-min.json")
rc, out, err = p.run("check", "rs-first-click")
check(rc == 0 and out["errors"] == [], "first-click: check clean")
path, items = review_rows(p, "rs-first-click")
doc = p.read("memory", "research", "rs-first-click", "instrument", "bias-review.md")
check({"fc1.neutral", "fc1.single", "fc1.goal", "fc1.nolabels"} <= set(items) and "data-action" not in doc and "rect" not in doc,
      "first-click review-plan: scenario items, and no selector or rect")
rc, out, err = p.run("review", "rs-first-click", "--file", path)
rc, out, err = p.run("approve", "rs-first-click")
check(rc == 0, "first-click: approve")
for s in ("first-click-s1", "first-click-s2"):
    rc, out, err = p.run("import", "rs-first-click", ux(s + ".json"), "--kind", "session", "--consent", "yes")
    check(rc == 0, "first-click import %s" % s)
rc, out, err = p.run("analyze", "rs-first-click")
an = p.study("rs-first-click")["analysis"]
fc = an["firstClick"]["tasks"]["fc1"]
check(rc == 0 and canon(an) == canon(recomputed(p, "rs-first-click")), "first-click analyze: equal to research_analysis recomputed")
check(fc["n"] == 2 and fc["success"]["x"] == 1 and fc["clicks"] == [[0.42, 0.86, True], [0.2, 0.15, False]], "first-click analyze: 1 of 2 hit, both click points kept")
rc, out, err = p.run("synthesize", "rs-first-click", "--file", p.write("syn.json", {
    "verdicts": {"h1": {"verdict": "inconclusive", "why": "Two participants."}},
    "findings": [{"id": "f1", "text": "One of two tapped the button.", "hypotheses": ["h1"],
                  "evidence": [{"analysis": "firstClick.tasks.fc1.success.x", "value": fc["success"]["x"]}]}]}))
check(rc == 0 and out["ok"] and "W-DIRECTIONAL" not in codes(out["warnings"]), "first-click synthesize: an analysis citation verifies (n=2 meets the target of 2)")
rc, out, err = p.run("synthesize", "rs-first-click", "--file", p.write("syn.json", {
    "findings": [{"id": "f1", "text": "x", "hypotheses": ["h1"], "evidence": [{"analysis": "firstClick.tasks.fc1.success.x", "value": 2}]}]}))
check(rc == 1 and "V-ANALYSIS" in codes(out["errors"]), "first-click synthesize: a wrong cited value fails verify")
p.edit("rs-first-click", lambda s: s["audience"].update(targetN=30))
rc, out, err = p.run("verify", "rs-first-click")
check("W-DIRECTIONAL" in codes(out["warnings"]) and any("2 of the target 30" in w["msg"] for w in out["warnings"]),
      "verify: W-DIRECTIONAL counts the analysis n (2 of the target 30)")

# ═════════════════════════════════════════════════════════════════════════════
section("6. security_scan skips a screen recording")
d = tempfile.mkdtemp(prefix="pb-scan-", dir=TMP)
ev = os.path.join(d, "memory", "research", "rs-x", "evidence")
os.makedirs(ev)
planted = "AKIA" + "IOSFODNN7" + "EXAMPLE"
with open(os.path.join(ev, "e1-screen.webm"), "wb") as fh:
    fh.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 64 + ("aws_access_key_id = " + planted).encode())
with open(os.path.join(ev, "e2-binary.bin"), "wb") as fh:
    fh.write(b"\xff\xfe\xfd" * 4000 + planted.encode())
with open(os.path.join(ev, "e3-big.txt"), "wb") as fh:
    fh.write(b"x" * (security_scan.MAX_BYTES + 10))
with open(os.path.join(ev, "e4-note.txt"), "w") as fh:
    fh.write("aws_access_key_id = " + planted + "\n")
err = io.StringIO()
with contextlib.redirect_stderr(err):
    found = security_scan.scan({}, d)
wheres = " ".join(f.where for f in found)
check("e4-note.txt" in wheres and "e1-screen.webm" not in wheres and "e2-binary.bin" not in wheres,
      "security_scan: a key in a text note is found; the same key inside a WebM and a binary is not read")
note = err.getvalue()
check("e1-screen.webm: skipped, a WebM recording" in note and "e2-binary.bin: skipped" in note and "e3-big.txt: skipped" in note,
      "security_scan: every skipped file is reported on stderr, not silently dropped")
sess = {"consent": {"textSha256": hashlib.sha256(b"x").hexdigest()}, "participant": "P01"}
with open(os.path.join(ev, "e5-session.json"), "w") as fh:
    json.dump(sess, fh)
err = io.StringIO()
with contextlib.redirect_stderr(err):
    found = security_scan.scan({}, d)
check(not [f for f in found if "e5-session.json" in f.where], "security_scan: a session file's consent.textSha256 is a digest, not a secret")
hits = []
security_scan.scan_text(lambda sev, code, w, msg: hits.append(code), hashlib.sha256(b"x").hexdigest(), "research.apikey")
check(hits == ["R-SEC-KEY"], "security_scan: a 64-hex under a secret-looking key still fires")

# ═════════════════════════════════════════════════════════════════════════════
section("7. link: the session URL on a running preview server")
p = usability_fielding(recording=False)
rc, out, err = Proj().run("link", SID)
check(rc == 2, "link REFUSED for a study that does not exist (exit 2)")
q = Proj()
q.run("init", SID, "--method", "usability", "--scope", "collect", "--question", "q?", "--role", "courier")
rc, out, err = q.run("link", SID)
check(rc == 1 and not q.exists(".preview", "server.json"), "link REFUSED for a draft study (no server is started)")
rc, out, err = p.run("link", SID, "--participant", "bad")
check(rc == 2, "link REFUSED for a participant code that is not P01…")
try:
    rc, out, err = p.run("link", SID, "--observer", "--participant", "P04")
    problems = out.get("problems", [])
    if rc == 0:
        url, obs = out["url"], out["observer"]
        codes_ = []
        for u in (url, obs):
            with urllib.request.urlopen(u, timeout=60) as r:
                codes_.append(r.status)
        check(url.startswith("http://127.0.0.1:") and url.endswith("/research/%s/session?p=P04" % SID) and obs.endswith("/research/%s/observer?p=P04" % SID),
              "link: the session and observer URLs (%s)" % url)
        check(codes_ == [200, 200], "link: both answer HTTP 200 (checked here, independently of the tool)")
        rc2, out2, err2 = p.run("link", SID)
        check(rc2 == 0 and out2["started"] is False and out2["url"].startswith(url.split("/research/")[0]), "link: a second call finds the running server")
        pilot_rc, pilot_out, _e = p.run("link", SID, "--pilot")
        check(pilot_rc == 0 and pilot_out["url"].endswith("session?pilot=1"), "link --pilot adds pilot=1")
        # report URL appears once a report exists and the server runs
        rc3, out3, err3 = p.run("analyze", SID)
        syn = synthesis(p)
        p.run("synthesize", SID, "--file", p.write("syn.json", syn))
        rc4, out4, err4 = p.run("report", SID)
        check(rc4 == 0 and out4["url"] and out4["url"].endswith("/research/%s/report" % SID), "report: prints the /research/<id>/report URL when a preview is running")
        with urllib.request.urlopen(out4["url"], timeout=60) as r:
            body = r.read().decode("utf-8")
            check(r.status == 200 and "Draft — not yet approved" in body, "report: the preview serves the report (HTTP 200)")
    elif any("HTTP 404" in x for x in problems) or any("HTTP None" in x for x in problems):
        NOT_VERIFIED.append("link: the preview server does not serve /research/ yet (%s)" % problems[0])
        print("  – NOT VERIFIED: " + NOT_VERIFIED[-1])
    else:
        NOT_VERIFIED.append("link: %s %s" % (out.get("error"), problems))
        print("  – NOT VERIFIED: " + NOT_VERIFIED[-1])
finally:
    subprocess.run([sys.executable, os.path.join(TOOLS, "serve.py"), "--stop", p.reg], capture_output=True, text=True, cwd=p.dir)

shutil.rmtree(TMP, ignore_errors=True)
if fails:
    print("\nFAIL: research_ux_tool — %d of %d checks failed" % (len(fails), CHECKS[0]))
    for f_ in fails:
        print("  ✗ " + f_)
    sys.exit(1)
print("\nPASS: research_ux_tool (%d checks)%s" % (CHECKS[0], (" — NOT VERIFIED: " + "; ".join(NOT_VERIFIED)) if NOT_VERIFIED else ""))
