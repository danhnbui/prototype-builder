#!/usr/bin/env python3
"""
research_session_unit.py — pb/tools/research_session.py, unit level. Stdlib only.

Everything here is TEST DATA: the session files below are written by this test (nothing was recorded from
a person), and the throwaway project is a temp copy of fixtures/research/ with a study set directly in its
registry (research.py's CLI does not yet know the session methods, and the store only needs the study's
method, status, scope and instrument).

What it proves:

  1. validate_session   a good file passes; each defect is refused with its code (format, version, session
                        id, participant, consent, time order, a typed value on an `input` event, an unknown
                        task, an email in a note); keep_pii turns the email into a warning; JSON nested
                        past 64 or over the size limit is refused before it is parsed
  2. the readers        summarize / task_metrics on a two-task usability session; tree_results (including a
                        backtrack), sort_result, click_results — expectations are counted from the data below
  3. participant_config an allow-list: no hypotheses, thresholds, title, question, audience, targets, probes,
                        success text, optimal path or right answer; screener sections left out
  4. kit_registry       what goes and what stays
  5. store_session      0444, sha256 row, status fielding, participants upsert; duplicate session refused;
                        draft refused but a pilot on a draft goes to pilot/ and study.pilots[]; scope
                        instrument, withdrawn participant and invalid files refused
  6. store_media        refused without recording consent; accepted with it (move from .incoming/, rows link
                        both ways, 0444); a move from outside .incoming/, a non-WebM file and a second
                        recording refused; a pilot's recording
  7. build_page         session, kit, observer, replay with stub scripts: config right after <head>, scripts
                        before </body>, no live-reload client, no window.PB_PREVIEW, no `research` in the
                        inlined registry, none of the study's hypotheses in any page
  8. no import cycle    importing research_session does not import research

Usage:  python3 tests/research_session_unit.py
Exit:   0 = PASS · 1 = a failure
"""
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
FIX = os.path.join(ROOT, "fixtures", "research")
sys.path.insert(0, TOOLS)

import research as R          # noqa: E402
import research_session as RS  # noqa: E402

fails = []
TMP = tempfile.mkdtemp(prefix="pb-rs-unit-")
_n = [0]


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def refused(fn, *a, **k):
    """The ResearchError message raised by fn, or None when it did not raise."""
    try:
        fn(*a, **k)
    except R.ResearchError as e:
        return str(e)
    return None


# ── test data ────────────────────────────────────────────────────────────────

HYP = "Couriers will miss the hidden cash total on the pay screen"
TITLE = "Pay screen total study (secret title)"
QUESTION = "Can couriers find the cash total before they reach the door (secret question)?"
CONSENT = "I agree to take part. My screen and voice may be recorded if I tick the box."
START = "2026-03-02T10:00:00Z"
END = "2026-03-02T10:00:12Z"


def usability_study(status="approved", scope="collect"):
    return {
        "id": "rs-ux-pay", "title": TITLE, "question": QUESTION, "method": "usability", "status": status,
        "scope": scope, "setup": "", "createdAt": "2026-03-01T09:00:00Z",
        "audience": {"roles": ["courier"], "targetN": 5}, "targets": [{"kind": "screen", "id": "pay"}],
        "hypotheses": [{"id": "h1", "statement": HYP, "targets": [{"kind": "screen", "id": "pay"}],
                        "supportedIf": "Fewer than 3 of 5 find the total in 60 seconds.",
                        "refutedIf": "At least 4 of 5 find it.", "verdict": None, "why": ""}],
        "instrument": {
            "lang": "en", "intro": "Thanks for helping.", "consent": CONSENT, "closing": "Thank you.", "durationMin": 30,
            "mode": "both", "recording": {"screen": True, "voice": True}, "device": "mobile", "thinkAloud": True,
            "sections": [
                {"title": "Screener", "purpose": "screener", "questions": [
                    {"id": "sc1", "text": "Do you deliver parcels?", "type": "single", "options": ["Yes", "No"], "qualifies": ["Yes"]}]},
                {"title": "Warm up", "purpose": "warmup", "questions": [
                    {"id": "w1", "text": "How often do you deliver?", "type": "single", "options": ["Daily", "Weekly"],
                     "tests": [], "probes": ["Which part is hardest?"]}]},
                {"title": "Tasks", "purpose": "task", "questions": [
                    {"id": "t1", "text": "You have arrived at the first stop. Collect the cash.", "tests": ["h1"],
                     "probes": ["Where are you looking for the total?"],
                     "task": {"screen": "route", "role": "courier", "success": "The cash is collected and the handover shows.",
                              "criteria": [{"screen": "handover"}], "optimalPath": ["route", "pay", "handover"], "timeLimitSec": 300}},
                    {"id": "seq1", "template": "seq", "tests": ["h1"]},
                    {"id": "t2", "text": "Hand the parcels back at the depot.", "tests": [],
                     "task": {"screen": "handover", "role": "dispatcher", "success": "The parcels leave the queue."}},
                    {"id": "seq2", "template": "seq"}]},
                {"title": "Wrap up", "purpose": "closing", "questions": [{"id": "sus", "template": "sus"}]}]},
        "evidence": [], "findings": [], "gates": []}


TREE = [{"id": "n-orders", "label": "Orders", "parent": None}, {"id": "n-refunds", "label": "Refunds", "parent": "n-orders"},
        {"id": "n-account", "label": "Account", "parent": None}, {"id": "n-help", "label": "Help", "parent": None}]
CARDS = [{"id": "c-a", "label": "Refund an order", "job": "job-secret"}, {"id": "c-b", "label": "Track a parcel"},
         {"id": "c-c", "label": "Change my address"}, {"id": "c-d", "label": "Contact support"}]


def other_study(sid, method, inst_extra):
    s = usability_study()
    s["id"] = sid
    s["method"] = method
    inst = s["instrument"]
    inst["sections"] = [{"title": "Tasks", "purpose": "task", "questions": inst_extra.pop("questions", [])}]
    inst.update(inst_extra)
    return s


def tree_study():
    return other_study("rs-ux-tree", "tree-test", {
        "tree": TREE, "questions": [{"id": "tt1", "text": "Where would you go to get your money back?", "tests": ["h1"],
                                     "tree": {"correct": ["n-refunds"]}}]})


def sort_study():
    return other_study("rs-ux-sort", "card-sort", {
        "cards": CARDS, "sort": {"kind": "hybrid", "categories": [{"id": "k-money", "label": "Money"}], "tests": ["h1"]}})


def click_study():
    return other_study("rs-ux-click", "first-click", {
        "questions": [{"id": "fc1", "text": "Where would you tap to pay?", "tests": ["h1"],
                       "click": {"screen": "pay", "target": "[data-action=\"submit\"]", "rect": {"x": 0.1, "y": 0.8, "w": 0.3, "h": 0.1}}}]})


def ev(t, typ, task, screen, **f):
    d = {"t": t, "type": typ, "task": task, "screen": screen}
    d.update(f)
    return d


def usability_session(sid="s-aaaa1", part="P01", pilot=False, recording=False):
    events = [
        ev(0, "session-start", None, "route"),
        ev(100, "consent", None, "route", recording=recording),
        ev(1000, "task-start", "t1", "route"),
        ev(1500, "click", "t1", "route", x=0.5, y=0.5, target="route > button", cmp="Button", interactive=True, dead=False),
        ev(2000, "click", "t1", "route", x=0.1, y=0.1, target="route > div", cmp=None, interactive=False, dead=True),
        ev(2100, "rage", "t1", "route", x=0.1, y=0.1, count=3),
        ev(3000, "nav", "t1", "pay", **{"from": "route", "to": "pay", "back": False}),
        ev(3500, "field-error", "t1", "pay", field="Amount", msg="Required"),
        ev(4000, "input", "t1", "pay", field="Amount", len=4),
        ev(5000, "criteria", "t1", "pay", met=True),
        ev(6000, "nav", "t1", "handover", **{"from": "pay", "to": "handover", "back": False}),
        ev(6100, "nav", "t1", "handover", **{"from": "handover", "to": "handover", "back": False}),
        ev(7000, "task-end", "t1", "handover", outcome="success", source="criteria"),
        ev(8000, "task-start", "t2", "handover"),
        ev(8500, "click", "t2", "handover", x=0.4, y=0.6, target="handover > button", cmp="Button", interactive=True, dead=False),
        ev(9000, "note", "t2", "handover", text="Hesitated before the confirm button", by="facilitator"),
        ev(9500, "assist", "t2", "handover"),
        ev(11000, "task-end", "t2", "handover", outcome="fail", source="self"),
        ev(12000, "session-end", None, "handover"),
    ]
    return {
        "format": "pb-session", "version": 1, "study": "rs-ux-pay", "method": "usability", "sessionId": sid, "participant": part,
        "mode": "moderated", "pilot": pilot, "startedAt": START, "endedAt": END, "durationMs": 12000,
        "env": {"viewport": [429, 926], "device": "mobile", "sink": "server", "shell": "test"},
        "consent": {"session": True, "recording": recording, "at": START, "textSha256": sha(CONSENT.encode("utf-8"))},
        "config": {"tasks": [{"id": "t1", "text": "Collect the cash.", "task": {"screen": "route"}},
                             {"id": "t2", "text": "Hand the parcels back.", "task": {"screen": "handover"}}]},
        "tasks": [
            {"id": "t1", "startT": 1000, "endT": 7000, "outcome": "success", "outcomeSource": "criteria", "criteriaT": 5000,
             "selfReport": "done", "assisted": False, "answers": {"seq1": 6}},
            {"id": "t2", "startT": 8000, "endT": 11000, "outcome": "fail", "outcomeSource": "self", "criteriaT": None,
             "selfReport": "gave-up", "assisted": True, "answers": {}}],
        "answers": {"w1": "Weekly", "sus-1": 4},
        "result": {}, "events": events, "media": []}


def raw_of(obj):
    return json.dumps(obj, sort_keys=True).encode("utf-8")


def webm(n=2048, salt=b"a"):
    return RS.WEBM_MAGIC + (salt * n)[:n]


class Proj:
    def __init__(self, studies):
        _n[0] += 1
        self.dir = os.path.join(TMP, "p%d" % _n[0])
        shutil.copytree(FIX, self.dir)
        self.reg = os.path.join(self.dir, "registry.json")
        d = self.data()
        d["research"] = {"populated": True, "studies": studies}
        self.save(d)

    def data(self):
        with open(self.reg, encoding="utf-8") as f:
            return json.load(f)

    def save(self, d):
        with open(self.reg, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")

    def study(self, sid="rs-ux-pay"):
        return next(s for s in self.data()["research"]["studies"] if s["id"] == sid)

    def set_study(self, sid, **kw):
        d = self.data()
        for s in d["research"]["studies"]:
            if s["id"] == sid:
                s.update(kw)
        self.save(d)

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def incoming(self, name, data):
        d = self.path("memory", "research", "rs-ux-pay", ".incoming")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, name)
        with open(p, "wb") as f:
            f.write(data)
        return p


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)


# ═════════════════════════════════════════════════════════════════════════════
section("1. validate_session")
ST = usability_study()
good = usability_session()
errs, warns = RS.validate_session(good, ST)
check(errs == [], "a good usability file has no errors (%s)" % errs[:3])
check(RS.validate_session(good)[0] == [], "…and none without a study (tasks checked against its own config)")
check(warns == [], "…and no warnings (%s)" % warns)


def mutated(fn):
    o = copy.deepcopy(good)
    fn(o)
    return o


def has(code, obj, study=ST, **k):
    return any(e.startswith(code + ":") for e in RS.validate_session(obj, study, **k)[0])


check(has("S-FORMAT", mutated(lambda o: o.update(format="pb-survey"))), "wrong format -> S-FORMAT")
check(has("S-FORMAT", mutated(lambda o: o.update(version=2))), "wrong version -> S-FORMAT")
check(has("S-ID", mutated(lambda o: o.update(sessionId="S-UPPER"))), "bad sessionId -> S-ID")
check(has("S-ID", mutated(lambda o: o.update(sessionId="s-../../x"))), "a path in sessionId -> S-ID")
check(has("S-PARTICIPANT", mutated(lambda o: o.update(participant="Maria"))), "a name as participant -> S-PARTICIPANT")
check(has("S-PARTICIPANT", mutated(lambda o: o.update(participant="P1"))), "P1 (one digit) -> S-PARTICIPANT")
check(has("S-CONSENT", mutated(lambda o: o["consent"].update(session=False))), "consent.session false -> S-CONSENT")
check(has("S-CONSENT", mutated(lambda o: o.pop("consent"))), "no consent block -> S-CONSENT")
check(has("S-CONSENT", mutated(lambda o: o.update(media=[{"kind": "screen", "mime": "video/webm", "startT": 0, "durationMs": 5, "file": "x"}]))),
      "a listed recording without recording consent -> S-CONSENT")


def back_in_time(o):
    o["events"][5]["t"] = 10


check(has("S-EVENT-ORDER", mutated(back_in_time)), "non-monotonic t -> S-EVENT-ORDER")


def typed_value(o):
    for e in o["events"]:
        if e["type"] == "input":
            e["value"] = "hunter2"


bad = mutated(typed_value)
check(has("S-INPUT-VALUE", bad), "an input event carrying `value` -> S-INPUT-VALUE")
check(not any("hunter2" in e for e in RS.validate_session(bad, ST)[0]), "…and the error does not repeat the value")
check(has("S-TASK-ID", mutated(lambda o: o["tasks"][0].update(id="zz9"))), "an unknown task id in tasks[] -> S-TASK-ID")
check(has("S-TASK-ID", mutated(lambda o: o["events"][3].update(task="zz9"))), "an unknown task id on an event -> S-TASK-ID")
check(has("S-EVENT-TYPE", mutated(lambda o: o["events"][3].update(type="keylog"))), "an unknown event type -> S-EVENT-TYPE")
check(has("S-STUDY", mutated(lambda o: o.update(study="rs-other"))), "a file for another study -> S-STUDY")
check(has("S-METHOD", mutated(lambda o: o.update(method="tree-test"))), "a file of another method -> S-METHOD")
check(has("S-TIME", mutated(lambda o: o.update(endedAt="2026-03-02T09:00:00Z"))), "ends before it starts -> S-TIME")
check(has("S-RESULT", mutated(lambda o: o["result"].update({"card-sort": {}}))), "a result key of another method -> S-RESULT")
check(has("S-TASKS", mutated(lambda o: o["tasks"][0].update(outcome="won"))), "an unknown outcome -> S-TASKS")


def email_note(o):
    o["events"][15]["text"] = "He said: reach me at alex.rivers@corp-mail.net after the test"


mail = mutated(email_note)
errs_mail = RS.validate_session(mail, ST)[0]
check(any(e.startswith("S-PII:") for e in errs_mail), "an email inside a note -> S-PII")
check(not any("alex.rivers@corp-mail.net" in e and "kept" in e for e in errs_mail), "…refused, not kept")
e2, w2 = RS.validate_session(mail, ST, keep_pii=True)
check(e2 == [] and any(w.startswith("S-PII:") for w in w2), "keep_pii=True -> the same finding is a warning, no error")
check(has("S-PII", mutated(lambda o: o["answers"].update(w1="call me on 0912 345 678"))), "a phone number in an answer -> S-PII")
check(RS.validate_session("nope")[0][0].startswith("S-JSON"), "not an object -> S-JSON")

many = mutated(lambda o: o.update(events=[ev(i, "keylog", None, None) for i in range(200)]))
check(len(RS.validate_session(many, ST)[0]) <= RS.MAX_FINDINGS + 1, "findings are capped (%d)" % len(RS.validate_session(many, ST)[0]))

# parsing: depth and size before json.loads
check("nested" in (refused(RS.parse_session_bytes, b"[" * 65 + b"]" * 65) or ""), "JSON nested past 64 is refused before it is parsed")
deep_in_string = json.dumps({"format": "x", "n": "[" * 500}).encode()
check(refused(RS.parse_session_bytes, deep_in_string) is None, "brackets inside a string do not count as depth")
check(refused(RS.parse_session_bytes, b"x" * (RS.SESSION_MAX_BYTES + 1)) is not None, "over SESSION_MAX_BYTES is refused")
check(refused(RS.parse_session_bytes, b'{"a": NaN}') is not None, "NaN is refused")
check(refused(RS.parse_session_bytes, b"[1,2]") is not None, "a JSON array is refused")
check(refused(RS.parse_session_bytes, b"\xff\xfe") is not None, "non-UTF-8 is refused")

# ═════════════════════════════════════════════════════════════════════════════
section("2. summarize / task_metrics / tree_results / sort_result / click_results")
sm = RS.summarize(good)
check(sm["id"] == "s-aaaa1" and sm["method"] == "usability" and sm["mode"] == "moderated" and sm["participant"] == "P01",
      "summarize: identity")
check(sm["tasks"] == 2 and sm["outcomes"] == {"success": 1, "fail": 1}, "summarize: 2 tasks, outcomes %s" % sm["outcomes"])
check(sm["durationMs"] == 12000 and sm["events"] == len(good["events"]) and sm["recording"] is False and sm["pilot"] is False,
      "summarize: duration, event count, recording, pilot")
check(RS.summarize(usability_session(recording=True))["recording"] is True, "summarize: recording follows consent.recording")

tm = RS.task_metrics(good)
t1, t2 = tm["t1"], tm["t2"]
check(t1["outcome"] == "success" and t1["source"] == "criteria" and t1["assisted"] is False, "t1: outcome, source, not assisted")
check(t1["ms"] == 7000 - 1000 and t1["criteriaMs"] == 5000 - 1000, "t1: ms %s, criteriaMs %s" % (t1["ms"], t1["criteriaMs"]))
check(t1["screens"] == ["route", "pay", "handover"], "t1: visit sequence collapses a repeat (%s)" % t1["screens"])
check((t1["clicks"], t1["dead"], t1["rage"], t1["errors"]) == (2, 1, 1, 1), "t1: clicks 2, dead 1, rage 1, errors 1")
check(t1["answers"] == {"seq1": 6}, "t1: post-task answers")
check(t2["outcome"] == "fail" and t2["source"] == "self" and t2["assisted"] is True and t2["ms"] == 3000 and t2["criteriaMs"] is None,
      "t2: fail, self, assisted, 3000 ms, no criteria time")
check(t2["screens"] == ["handover"] and (t2["clicks"], t2["dead"], t2["rage"], t2["errors"]) == (1, 0, 0, 0), "t2: one screen, one click")


def tree_session(sid, steps, chosen, path):
    t = 1000
    events = [ev(0, "session-start", None, None), ev(t, "task-start", "tt1", None)]
    for kind, node in steps:
        t += 500
        events.append(ev(t, kind, "tt1", None, node=node))
    events.append(ev(t + 500, "task-end", "tt1", None, outcome="success", source="self"))
    events.append(ev(t + 1000, "session-end", None, None))
    o = usability_session(sid=sid)
    o.update(study="rs-ux-tree", method="tree-test", events=events, durationMs=t + 1000,
             config={"tasks": [{"id": "tt1", "text": "Where?", "tree": {}}], "tree": copy.deepcopy(TREE)},
             tasks=[{"id": "tt1", "startT": 1000, "endT": t + 500, "outcome": "success", "outcomeSource": "self", "criteriaT": None,
                     "selfReport": "done", "assisted": False, "answers": {}}],
             answers={}, result={"tree-test": {"tt1": {"chosen": chosen, "path": path}}})
    return o


wander = tree_session("s-tree1", [("tt-open", "n-account"), ("tt-open", "n-orders"), ("tt-open", "n-refunds"), ("tt-choose", "n-refunds")],
                      "n-refunds", ["n-orders", "n-refunds"])
direct = tree_session("s-tree2", [("tt-open", "n-orders"), ("tt-open", "n-refunds"), ("tt-choose", "n-refunds")],
                      "n-refunds", ["n-orders", "n-refunds"])
tr1, tr2 = RS.tree_results(wander)["tt1"], RS.tree_results(direct)["tt1"]
check(tr1["chosen"] == "n-refunds" and tr1["path"] == ["n-orders", "n-refunds"], "tree: chosen and path")
check(tr1["firstNode"] == "n-account" and tr1["backtracked"] is True, "tree: first node n-account, went back up -> backtracked")
check(tr2["firstNode"] == "n-orders" and tr2["backtracked"] is False, "tree: a direct route is not backtracked")
check(tr1["ms"] == wander["tasks"][0]["endT"] - 1000, "tree: ms is the task duration (%s)" % tr1["ms"])
check(RS.validate_session(wander, tree_study())[0] == [], "…and the tree session validates against its study (%s)" % RS.validate_session(wander, tree_study())[0][:2])
skipped = copy.deepcopy(direct)
skipped["result"]["tree-test"]["tt1"] = {"chosen": None, "path": []}
check(RS.tree_results(skipped)["tt1"]["chosen"] is None, "tree: a skipped task has chosen null")
ghost = copy.deepcopy(direct)
ghost["result"]["tree-test"]["tt1"]["chosen"] = "n-ghost"
check(has("S-RESULT", ghost, study=tree_study()), "tree: a node the tree does not have -> S-RESULT")

sorted_obj = usability_session(sid="s-sort1")
sorted_obj.update(study="rs-ux-sort", method="card-sort", tasks=[], answers={}, config={"cards": [], "sort": {}},
                  result={"card-sort": {"groups": [{"name": "Money", "category": "k-money", "cards": ["c-a"]},
                                                   {"name": "Where is it", "category": None, "cards": ["c-b", "c-c"]}],
                                        "unsorted": ["c-d"]}},
                  events=[ev(0, "session-start", None, None), ev(5000, "session-end", None, None)], durationMs=5000)
sr = RS.sort_result(sorted_obj)
check([g["name"] for g in sr["groups"]] == ["Money", "Where is it"] and sr["groups"][0]["category"] == "k-money"
      and sr["groups"][1]["cards"] == ["c-b", "c-c"] and sr["unsorted"] == ["c-d"], "sort_result: groups, categories, unsorted")
check(RS.validate_session(sorted_obj, sort_study())[0] == [], "…and a card sort validates against its study (%s)" % RS.validate_session(sorted_obj, sort_study())[0][:2])
twice = copy.deepcopy(sorted_obj)
twice["result"]["card-sort"]["groups"][1]["cards"].append("c-a")
check(has("S-RESULT", twice, study=sort_study()), "a card in two groups -> S-RESULT")
check(RS.sort_result({}) == {"groups": [], "unsorted": []}, "sort_result of nothing is empty")

click_obj = usability_session(sid="s-clck1")
click_obj.update(study="rs-ux-click", method="first-click", answers={}, config={"tasks": [{"id": "fc1", "text": "Tap to pay", "click": {}}]},
                 tasks=[{"id": "fc1", "startT": 1000, "endT": 3300, "outcome": "success", "outcomeSource": "criteria", "criteriaT": None,
                         "selfReport": None, "assisted": False, "answers": {}}],
                 result={"first-click": {"fc1": {"x": 0.42, "y": 0.86, "target": "pay > button", "hit": True, "ms": 2300}}},
                 events=[ev(0, "session-start", None, None), ev(1000, "task-start", "fc1", "pay"),
                         ev(3300, "fc-click", "fc1", "pay", x=0.42, y=0.86, hit=True, target="pay > button"),
                         ev(3400, "session-end", None, None)], durationMs=3400)
cr = RS.click_results(click_obj)["fc1"]
check((cr["x"], cr["y"], cr["hit"], cr["ms"], cr["target"]) == (0.42, 0.86, True, 2300, "pay > button"), "click_results: point, hit, ms, target")
click_obj["result"]["first-click"]["fc1"].pop("ms")
check(RS.click_results(click_obj)["fc1"]["ms"] == 2300, "click_results: ms falls back to the task duration")
check(RS.validate_session(click_obj, click_study())[0] == [], "…and a first-click session validates (%s)" % RS.validate_session(click_obj, click_study())[0][:2])
click_obj["result"]["first-click"]["fc1"]["x"] = 1.7
check(has("S-RESULT", click_obj, study=click_study()), "a click outside 0..1 -> S-RESULT")

# ═════════════════════════════════════════════════════════════════════════════
section("3. participant_config")
reg0 = R.load_registry(os.path.join(FIX, "registry.json"))
cfg = RS.participant_config(reg0, ST, sink="server", participant="P07", pilot=True, mode="moderated")
text = json.dumps(cfg, ensure_ascii=False)
for key in ("hypotheses", "audience", "targets", "findings", "title", "question", "thresholds", "supportedIf", "refutedIf", "verdict"):
    check(key not in cfg, "top level has no %r" % key)
for needle, what in ((HYP, "the hypothesis statement"), (TITLE, "the study title"), (QUESTION, "the study question"),
                     ("Fewer than 3 of 5", "a threshold"), ("h1", "a hypothesis id"), ("Which part is hardest", "a probe"),
                     ("The cash is collected", "the success description"), ("optimalPath", "the optimal path"),
                     ("Do you deliver parcels", "the screener"), ("qualifies", "screener qualifiers")):
    check(needle not in text, "config text has no %s" % what)
check(cfg["page"] == "session" and cfg["study"] == "rs-ux-pay" and cfg["method"] == "usability" and cfg["mode"] == "moderated"
      and cfg["sink"] == "server" and cfg["participant"] == "P07" and cfg["pilot"] is True and cfg["channel"] == "pb-rs-rs-ux-pay",
      "config: identity, mode, sink, participant, pilot, channel")
check(cfg["post"] == {"session": "/__pb_research/rs-ux-pay/session", "media": "/__pb_research/rs-ux-pay/media"}, "config: server posts")
inst = cfg["instrument"]
check(inst["device"] == "mobile" and inst["thinkAloud"] is True and inst["recording"] == {"screen": True, "voice": True}
      and inst["consent"] == CONSENT and inst["lang"] == "en", "config: device, think-aloud, recording, consent text")
qs = [q for s in inst["sections"] for q in s["questions"]]
ids = [q["id"] for q in qs]
check("sus-1" in ids and "sus-10" in ids and "sus" not in ids and "seq1" in ids, "config: templates are expanded (sus-1..sus-10, seq1)")
check([s["purpose"] for s in inst["sections"]] == ["warmup", "task", "closing"], "config: the screener section is left out")
t1q = next(q for q in qs if q["id"] == "t1")
check(t1q["task"]["screen"] == "route" and t1q["task"]["criteria"] == [{"screen": "handover"}] and "success" not in t1q["task"]
      and "optimalPath" not in t1q["task"] and "tests" not in t1q and "probes" not in t1q, "config: a task keeps screen+criteria, loses success/optimalPath/tests/probes")
kitcfg = RS.participant_config(reg0, ST, sink="download")
check(kitcfg["post"] is None and kitcfg["mode"] == "unmoderated" and kitcfg["participant"] is None and kitcfg["pilot"] is False,
      "config: download sink -> post null, unmoderated by default")
treecfg = RS.participant_config(reg0, tree_study(), sink="download")
check(treecfg["tree"] == [{"id": n["id"], "label": n["label"], "parent": n["parent"]} for n in TREE] and "n-refunds\"]" not in json.dumps(treecfg["instrument"]),
      "config: tree-test carries the tree and no right answer")
check("correct" not in json.dumps(treecfg), "config: no `correct` anywhere")
sortcfg = RS.participant_config(reg0, sort_study(), sink="download")
check([c["id"] for c in sortcfg["cards"]] == ["c-a", "c-b", "c-c", "c-d"] and "job-secret" not in json.dumps(sortcfg)
      and sortcfg["sort"] == {"kind": "hybrid", "categories": [{"id": "k-money", "label": "Money"}]} and "tests" not in json.dumps(sortcfg["sort"]),
      "config: card-sort carries cards (no job link) and categories (no tests)")
check(refused(RS.participant_config, reg0, ST, sink="lan") is not None, "config: an unknown sink is refused")
check(refused(RS.participant_config, reg0, ST, sink="server", participant="../etc") is not None, "config: a bad participant is refused")
survey = copy.deepcopy(ST)
survey["method"] = "survey"
check(refused(RS.participant_config, reg0, survey, sink="server") is not None, "config: a survey has no session config")

# ═════════════════════════════════════════════════════════════════════════════
section("4. kit_registry")
reg_full = copy.deepcopy(reg0)
reg_full["research"] = {"populated": True, "studies": [ST]}
reg_full["meta"]["tradeoffs"] = [{"id": "tr1"}]
reg_full["meta"]["others"] = {"x": 1}
reg_full["meta"]["designSystem"] = {"name": "Demo DS", "designLink": "https://www.figma.com/design/abc/Demo"}
reg_full["content"] = {"populated": True, "terms": [{"id": "t"}]}
reg_full["components"][0]["uiLogic"] = ["internal prose"]
reg_full["components"][0]["specSrc"] = "spec/components/x.json"
kr = RS.kit_registry(reg_full)
for k in ("research", "ia", "flow", "erd", "content"):
    check(k not in kr, "kit_registry drops %r" % k)
for k in ("userInsights", "tradeoffs", "others", "overview"):
    check(k not in kr["meta"], "kit_registry drops meta.%s" % k)
check("designLink" not in kr["meta"]["designSystem"] and kr["meta"]["designSystem"]["name"] == "Demo DS", "kit_registry drops the Figma link, keeps the DS name")
check("uiLogic" not in kr["components"][0] and "specSrc" not in kr["components"][0], "kit_registry drops component prose and sidecar pointers")
check(kr["config"]["viewOnly"] is True, "kit_registry sets config.viewOnly")
check(kr["meta"]["demo"] == reg0["meta"]["demo"] and kr["meta"]["roles"] == reg0["meta"]["roles"] and kr["meta"]["name"] == reg0["meta"]["name"]
      and kr["screens"] == reg0["screens"] and kr["tokens"] == reg0["tokens"], "kit_registry keeps meta.demo/roles/name, screens, tokens")
check("research" in reg_full and "uiLogic" in reg_full["components"][0], "kit_registry works on a copy")

# ═════════════════════════════════════════════════════════════════════════════
section("5. store_session")
p = Proj([usability_study()])
raw = raw_of(good)
res = RS.store_session(p.reg, "rs-ux-pay", raw)
check(res["evidence"] == "e1" and res["pilot"] is False and res["sessionId"] == "s-aaaa1" and res["warnings"] == [], "returns e1, not a pilot, no warnings (%s)" % res)
fpath = p.path(*res["file"].split("/"))
check(res["file"] == "memory/research/rs-ux-pay/evidence/e1-s-aaaa1.json" and os.path.isfile(fpath), "file lands in evidence/ as e1-<sessionId>.json")
check(mode_of(fpath) == 0o444, "the file is 0444 (%s)" % oct(mode_of(fpath)))
check(open(fpath, "rb").read() == raw, "the stored bytes are the bytes received")
st = p.study()
row = st["evidence"][0]
check(row["kind"] == "session" and row["sha256"] == sha(raw) and row["consent"] == "yes" and row["participant"] == "P01"
      and row["date"] == "2026-03-02" and row["dropped"] is None, "row: kind, sha256, consent yes, participant, date")
check(row["session"]["id"] == "s-aaaa1" and row["session"]["method"] == "usability" and row["session"]["tasks"] == 2
      and row["session"]["outcomes"] == {"success": 1, "fail": 1} and row["session"]["recording"] is False and row["session"]["media"] == []
      and row["session"]["durationMs"] == 12000 and row["session"]["mode"] == "moderated", "row.session summary")
check(R.evidence_file(p.dir, "rs-ux-pay", row)[0] == "ok", "research.evidence_file accepts the stored row")
check(RS.load_session(p.dir, row)["sessionId"] == "s-aaaa1", "load_session returns the parsed file")
check(st["status"] == "fielding", "status -> fielding")
check(st["participants"] == [{"id": "P01", "segment": "", "role": "", "status": "done", "sessionAt": "2026-03-02", "incentive": "due",
                              "pilot": False, "note": ""}], "participants[] upserted (%s)" % st.get("participants"))
# a participant already on the tracker is updated, not duplicated
d = p.data()
d["research"]["studies"][0]["participants"][0].update(status="scheduled", sessionAt=None, segment="new", role="courier")
p.save(d)
RS.store_session(p.reg, "rs-ux-pay", raw_of(usability_session(sid="s-aaaa2", part="P01")))
people = p.study()["participants"]
check(len(people) == 1 and people[0]["status"] == "done" and people[0]["sessionAt"] == "2026-03-02" and people[0]["segment"] == "new",
      "an existing participant is updated in place")
check(p.study()["evidence"][1]["role"] == "courier" and p.study()["evidence"][1]["segment"] == "new", "the row takes the participant's role and segment")
# the tamper check
os.chmod(fpath, 0o644)
with open(fpath, "ab") as f:
    f.write(b" ")
check(refused(RS.load_session, p.dir, row) is not None, "load_session refuses a file changed after import (sha256)")
os.chmod(fpath, 0o444)

# duplicates
msg = refused(RS.store_session, p.reg, "rs-ux-pay", raw_of(usability_session(sid="s-aaaa1")))
check(msg is not None and "already stored" in msg, "a duplicate sessionId is refused (%s)" % msg)
n_before = len(p.study()["evidence"])
changed = usability_session(sid="s-aaaa1")
changed["events"][15]["text"] = "different bytes, same session id"
check(refused(RS.store_session, p.reg, "rs-ux-pay", raw_of(changed)) is not None and len(p.study()["evidence"]) == n_before,
      "…even with different content; nothing was added")
files = sorted(os.listdir(p.path("memory", "research", "rs-ux-pay", "evidence")))
check(files == ["e1-s-aaaa1.json", "e2-s-aaaa2.json"], "no stray file after a refusal (%s)" % files)

# refusals
bad_pii = usability_session(sid="s-pii01", part="P03")
bad_pii["events"][15]["text"] = "mail alex.rivers@corp-mail.net"
e = None
try:
    RS.store_session(p.reg, "rs-ux-pay", raw_of(bad_pii))
except R.ResearchError as ex:
    e = ex
check(e is not None and any(x.startswith("S-PII") for x in e.data.get("errors", [])), "an invalid file is refused with its error codes in data")
ok_kp = RS.store_session(p.reg, "rs-ux-pay", raw_of(bad_pii), keep_pii=True)
check(ok_kp["evidence"] == "e3" and any(w.startswith("S-PII") for w in ok_kp["warnings"]), "keep_pii stores it and returns the warning")
check(refused(RS.store_session, p.reg, "rs-ux-pay", b"not json") is not None, "bad JSON is refused")
check(refused(RS.store_session, p.reg, "rs-nope", raw) is not None, "an unknown study is refused")
check(refused(RS.store_session, p.reg, "../x", raw) is not None, "a bad study id is refused")

p2 = Proj([usability_study(status="draft")])
msg = refused(RS.store_session, p2.reg, "rs-ux-pay", raw_of(usability_session(sid="s-draf1")))
check(msg is not None and "draft" in msg and p2.study()["evidence"] == [], "a draft study refuses a real session")
pil = usability_session(sid="s-pilot1", part="P90", pilot=True)
pres = RS.store_session(p2.reg, "rs-ux-pay", raw_of(pil))
check(pres["pilot"] is True and pres["evidence"] is None and pres["file"] == "memory/research/rs-ux-pay/pilot/s-pilot1.json",
      "…but a pilot on a draft is stored in pilot/ (%s)" % pres)
check(os.path.isfile(p2.path("memory", "research", "rs-ux-pay", "pilot", "s-pilot1.json")) and mode_of(p2.path(*pres["file"].split("/"))) == 0o444,
      "…0444")
s2 = p2.study()
check(s2["evidence"] == [] and s2["status"] == "draft", "…no evidence row, status still draft")
check(len(s2["pilots"]) == 1 and s2["pilots"][0]["sessionId"] == "s-pilot1" and s2["pilots"][0]["participant"] == "P90"
      and s2["pilots"][0]["file"] == pres["file"] and s2["pilots"][0]["media"] == [], "…study.pilots[] has it")
check(any(x["id"] == "P90" and x["pilot"] is True for x in s2["participants"]), "…the pilot participant is marked pilot")
check("already stored" in (refused(RS.store_session, p2.reg, "rs-ux-pay", raw_of(pil)) or ""), "…a pilot sessionId is not stored twice")
p2.set_study("rs-ux-pay", status="approved", scope="instrument")
check("instrument" in (refused(RS.store_session, p2.reg, "rs-ux-pay", raw_of(usability_session(sid="s-inst1"))) or ""),
      "scope instrument refuses a real session")
check(RS.store_session(p2.reg, "rs-ux-pay", raw_of(usability_session(sid="s-pilot2", part="P91", pilot=True)))["pilot"] is True,
      "…and accepts a pilot")
p2.set_study("rs-ux-pay", scope="collect", participants=[{"id": "P05", "status": "withdrawn", "pilot": False}])
check("withdrawn" in (refused(RS.store_session, p2.reg, "rs-ux-pay", raw_of(usability_session(sid="s-wdrw1", part="P05"))) or ""),
      "a withdrawn participant's session is refused")
survey_proj = Proj([dict(usability_study(), method="interview")])
check(refused(RS.store_session, survey_proj.reg, "rs-ux-pay", raw) is not None, "a study of another method is refused")
check(p2.study()["status"] == "approved", "the registry is still valid JSON after the refusals")

# ═════════════════════════════════════════════════════════════════════════════
section("6. store_media")
pm = Proj([usability_study()])
rec = usability_session(sid="s-rec01", part="P02", recording=True)
rec["media"] = [{"kind": "screen", "mime": "video/webm", "startT": 900, "durationMs": 11000, "file": "p02-screen.webm"}]
RS.store_session(pm.reg, "rs-ux-pay", raw_of(rec))
norec = usability_session(sid="s-norec", part="P03", recording=False)
RS.store_session(pm.reg, "rs-ux-pay", raw_of(norec))

src = pm.incoming("up1.webm", webm(4096, b"x"))
msg = refused(RS.store_media, pm.reg, "rs-ux-pay", "s-norec", src, move=True)
check(msg is not None and "consent" in msg, "no recording consent -> refused (%s)" % msg)
check(os.path.exists(src) and not any(e["kind"] == "recording" for e in pm.study()["evidence"]), "…the upload is untouched and no row was written")
check("consent" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-norec", src, move=False) or ""), "…a copy is refused the same way")
check("not stored" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-ghost1", src, move=True) or ""), "an unknown session is refused")

outside = os.path.join(TMP, "outside.webm")
with open(outside, "wb") as f:
    f.write(webm(512))
check(".incoming" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", outside, move=True) or ""), "move=True from outside .incoming/ is refused")
link = pm.incoming("target.webm", webm(512, b"l"))
sym = os.path.join(os.path.dirname(link), "sym.webm")
os.symlink(outside, sym)
check(refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", sym, move=True) is not None, "a symlink in .incoming/ pointing outside is refused")
os.unlink(sym)
trick = os.path.join(os.path.dirname(link), "..", "..", "..", "..", "outside.webm")
check(refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", os.path.join(TMP, "outside.webm"), move=True) is not None
      and refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", trick, move=True) is not None, "a ..-path out of .incoming/ is refused")
notwebm = pm.incoming("junk.webm", b"this is not a webm file at all")
check("WebM" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", notwebm, move=True) or ""), "a non-WebM file is refused")
check(refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", link, mime="video/mp4", move=True) is not None, "a non-webm mime is refused")
check(refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", pm.incoming("empty.webm", b""), move=True) is not None, "an empty file is refused")
check(refused(RS.store_media, pm.reg, "rs-ux-pay", "../x", link, move=True) is not None, "a bad session id is refused")

body = webm(8192, b"v")
src = pm.incoming("up2.webm", body)
mres = RS.store_media(pm.reg, "rs-ux-pay", "s-rec01", src, move=True)
st = pm.study()
rrow = next(e for e in st["evidence"] if e["kind"] == "recording")
srow = next(e for e in st["evidence"] if e["kind"] == "session" and e["session"]["id"] == "s-rec01")
check(mres["evidence"] == rrow["id"] and mres["sha256"] == sha(body) and mres["bytes"] == len(body), "returns the eid, sha256 and size (%s)" % mres)
check(mres["file"] == "memory/research/rs-ux-pay/evidence/%s-s-rec01-screen.webm" % rrow["id"], "file name: <eid>-<sessionId>-screen.webm")
mpath = pm.path(*mres["file"].split("/"))
check(open(mpath, "rb").read() == body and mode_of(mpath) == 0o444, "stored intact and 0444")
check(not os.path.exists(src), "the .incoming upload was moved, not copied")
check(rrow["session"] == "s-rec01" and rrow["mime"] == "video/webm" and rrow["bytes"] == len(body) and rrow["sha256"] == sha(body)
      and rrow["consent"] == "yes" and rrow["participant"] == "P02", "recording row: links to the session, mime, bytes, sha256")
check(rrow["id"] in srow["session"]["media"] and srow["session"]["recording"] is True, "session row links to the recording (both ways)")
check(R.evidence_file(pm.dir, "rs-ux-pay", rrow)[0] == "ok", "research.evidence_file accepts the recording row")
check("already has a recording" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec01", pm.incoming("up3.webm", webm(900, b"q")), move=True) or ""),
      "a second recording for the session is refused")
# copy mode (CLI import)
rec2 = usability_session(sid="s-rec02", part="P04", recording=True)
RS.store_session(pm.reg, "rs-ux-pay", raw_of(rec2))
cp = os.path.join(TMP, "p04.webm")
with open(cp, "wb") as f:
    f.write(webm(3000, b"c"))
cres = RS.store_media(pm.reg, "rs-ux-pay", "s-rec02", cp)
check(os.path.exists(cp) and mode_of(pm.path(*cres["file"].split("/"))) == 0o444 and cres["bytes"] == os.path.getsize(cp),
      "move=False copies (the source stays) and stores 0444")
# the same bytes for another session
rec3 = usability_session(sid="s-rec03", part="P05", recording=True)
RS.store_session(pm.reg, "rs-ux-pay", raw_of(rec3))
check("already stored" in (refused(RS.store_media, pm.reg, "rs-ux-pay", "s-rec03", cp) or ""), "the same recording bytes are not stored twice")
# a pilot recording
pm.set_study("rs-ux-pay", status="draft")
RS.store_session(pm.reg, "rs-ux-pay", raw_of(usability_session(sid="s-pilot3", part="P92", pilot=True, recording=True)))
pres = RS.store_media(pm.reg, "rs-ux-pay", "s-pilot3", pm.incoming("pilotrec.webm", webm(700, b"p")), move=True)
ps = pm.study()
check(pres["evidence"] is None and pres["file"] == "memory/research/rs-ux-pay/pilot/s-pilot3-screen.webm"
      and os.path.isfile(pm.path(*pres["file"].split("/"))), "a pilot's recording lands in pilot/")
check(next(x for x in ps["pilots"] if x["sessionId"] == "s-pilot3")["media"] == [pres["file"]] and not any(
    e["id"] == pres["evidence"] for e in ps["evidence"] if pres["evidence"]), "…and is listed on study.pilots[], not in evidence")

# ═════════════════════════════════════════════════════════════════════════════
section("7. build_page (stub scripts)")
stubs = os.path.join(TMP, "stubs")
os.makedirs(stubs)
for name, marker in (("research-session.js", "/*STUB-SESSION*/ window.__stubSession=1;"),
                     ("research-methods.js", "/*STUB-METHODS*/ window.__stubMethods=1;"),
                     ("research-replay.js", "/*STUB-REPLAY*/ window.__stubReplay=1; var s='</script>';")):
    with open(os.path.join(stubs, name), "w", encoding="utf-8") as f:
        f.write(marker + "\n")
RS.TEMPLATE_DIR = stubs

pb = Proj([usability_study(), tree_study(), sort_study(), click_study()])
RS.store_session(pb.reg, "rs-ux-pay", raw_of(usability_session(sid="s-rec01", part="P02", recording=True)))
RS.store_media(pb.reg, "rs-ux-pay", "s-rec01", pb.incoming("v.webm", webm(1500, b"r")), move=True)
pb.set_study("rs-ux-tree", status="approved")


def config_of(html, name="PB_RS_SESSION"):
    marker = "window.%s=" % name
    i = html.index(marker) + len(marker)
    j = html.index(";</script>", i)
    return json.loads(html[i:j])


def common(html, label, js_markers):
    head = html.lower().find("<head")
    head_end = html.find(">", head) + 1
    check(html.startswith("<script>window.PB_RS_", head_end), "%s: the config script sits right after <head>" % label)
    last_body = html.rfind("</body>")
    pos = [html.find(m) for m in js_markers]
    check(all(x > 0 and x < last_body for x in pos), "%s: scripts are inlined before </body>" % label)
    check(pos == sorted(pos), "%s: scripts are in order %s" % (label, [m.strip("/*") for m in js_markers]))
    check("window.PB_PREVIEW=" not in html and "window.PB_PREVIEW =" not in html, "%s: no window.PB_PREVIEW" % label)
    check("new EventSource" not in html and "__pb_events" not in html and "pb-serve live-reload" not in html, "%s: no live-reload client" % label)
    check(HYP not in html and TITLE not in html and QUESTION not in html and "Fewer than 3 of 5" not in html,
          "%s: none of the study's hypotheses, title or question is in the page" % label)


html = RS.build_page(pb.reg, "rs-ux-pay", "session", participant="P01", shell_path=None)
common(html, "session", ["/*STUB-SESSION*/", "/*STUB-METHODS*/"])
c = config_of(html)
check(c["page"] == "session" and c["sink"] == "server" and c["participant"] == "P01" and c["pilot"] is False and c["study"] == "rs-ux-pay"
      and c["post"]["session"] == "/__pb_research/rs-ux-pay/session", "session: config page/sink/participant/post")
check('"research":{' not in html, "session: the inlined registry has no `research` key")
check('"viewOnly":true' in html, "session: the registry is view-only")
check(html.count("<!DOCTYPE html>") == 1 and "PB_REGISTRY" in html, "session: it is the prototype shell")

kit = RS.build_page(pb.reg, "rs-ux-pay", "kit")
common(kit, "kit", ["/*STUB-SESSION*/", "/*STUB-METHODS*/"])
kc = config_of(kit)
check(kc["page"] == "kit" and kc["sink"] == "download" and kc["post"] is None and kc["mode"] == "unmoderated" and kc["participant"] is None,
      "kit: sink download, post null, unmoderated, no participant")
check('"research":{' not in kit and '"viewOnly":true' in kit, "kit: no `research` in the registry; view-only")

for sid_, label in (("rs-ux-tree", "tree"), ("rs-ux-sort", "sort"), ("rs-ux-click", "click")):
    h = RS.build_page(pb.reg, sid_, "kit")
    cc = config_of(h)
    check(cc["method"] in ("tree-test", "card-sort", "first-click") and "correct" not in json.dumps(cc) and "job-secret" not in h,
          "kit for %s: method config without a right answer" % label)

obs = RS.build_page(pb.reg, "rs-ux-pay", "observer")
oc = config_of(obs)
check(oc["page"] == "observer" and "/*STUB-SESSION*/" in obs and "/*STUB-METHODS*/" not in obs and "PB_REGISTRY" not in obs,
      "observer: a small tool page with research-session.js only, no prototype")
check("/*__PB_CHROME__*/" not in obs and "--pb-" in obs, "observer: the tool's chrome.css is injected")
check(oc["moderator"]["probes"]["t1"] == ["Where are you looking for the total?"]
      and oc["moderator"]["tasks"]["t1"]["success"].startswith("The cash is collected"), "observer: the moderator view has probes and success text")
check(HYP not in obs and "window.PB_PREVIEW=" not in obs and "new EventSource" not in obs and obs.find("window.PB_RS_SESSION=") < obs.find("<body"),
      "observer: no hypotheses, no preview hooks; config in <head>")
check("<title>Observer · rs-ux-pay</title>" in obs, "observer: titled")

rp = RS.build_page(pb.reg, "rs-ux-pay", "replay", eid="e1")
common(rp, "replay", ["/*STUB-REPLAY*/"])
rc = config_of(rp, "PB_RS_REPLAY")
rec_eid = next(e["id"] for e in pb.study()["evidence"] if e["kind"] == "recording")
check(rc["study"] == "rs-ux-pay" and rc["eid"] == "e1" and rc["session"]["sessionId"] == "s-rec01" and rc["session"]["events"], "replay: PB_RS_REPLAY carries the session")
check(rc["media"] == [{"eid": rec_eid, "url": "/__pb_research/rs-ux-pay/evidence/%s" % rec_eid, "mime": "video/webm"}], "replay: the recording is linked (%s)" % rc["media"])
check('"research":{' not in rp, "replay: no `research` in the registry")
check("<\\/script>" in rp and "var s='</script>'" not in rp, "replay: a </script in an inlined script is escaped")
check("window.PB_RS_SESSION=" not in rp, "replay: no session config")

pb.set_study("rs-ux-pay", status="draft")
RS.store_session(pb.reg, "rs-ux-pay", raw_of(usability_session(sid="s-pilot9", part="P93", pilot=True)))
rpp = RS.build_page(pb.reg, "rs-ux-pay", "replay", eid="pilot-s-pilot9")
check(config_of(rpp, "PB_RS_REPLAY")["session"]["sessionId"] == "s-pilot9" and config_of(rpp, "PB_RS_REPLAY")["media"] == [], "replay of a pilot: pilot-<sessionId>")
msg = refused(RS.build_page, pb.reg, "rs-ux-pay", "session")
check(msg is not None and "draft" in msg, "session page on a draft study is refused")
dp = RS.build_page(pb.reg, "rs-ux-pay", "session", pilot=True, participant="P94")
check(config_of(dp)["pilot"] is True and config_of(dp)["participant"] == "P94", "…but a pilot (pilot=True) may run on a draft")
check(refused(RS.build_page, pb.reg, "rs-ux-pay", "kit") is not None and RS.build_page(pb.reg, "rs-ux-pay", "observer"), "kit on a draft is refused; the observer opens")
pb.set_study("rs-ux-pay", status="approved", scope="instrument")
check("instrument" in (refused(RS.build_page, pb.reg, "rs-ux-pay", "session") or ""), "scope instrument refuses a session page (a pilot is allowed)")
pb.set_study("rs-ux-pay", scope="collect")

for bad_eid in ("e99", "../etc/passwd", "e1/../e1", "pilot-s-ghost1", "pilot-../x", "E1", "", None):
    check(refused(RS.build_page, pb.reg, "rs-ux-pay", "replay", eid=bad_eid) is not None, "replay refuses eid %r" % (bad_eid,))
check(refused(RS.build_page, pb.reg, "rs-ux-pay", "session", participant="P1") is not None, "build_page refuses a bad participant code")
check(refused(RS.build_page, pb.reg, "rs-ux-pay", "dashboard") is not None, "build_page refuses an unknown page")
check(refused(RS.build_page, pb.reg, "../x", "session") is not None, "build_page refuses a bad study id")
check(refused(RS.build_page, pb.reg, "rs-nope", "session") is not None, "build_page refuses an unknown study")
RS.TEMPLATE_DIR = os.path.join(TMP, "no-such-folder")
check("cannot be read" in (refused(RS.build_page, pb.reg, "rs-ux-pay", "session", participant="P01") or ""), "a missing page script is a refusal, not a traceback")
RS.TEMPLATE_DIR = RS.DEFAULT_TEMPLATE_DIR
# a withdrawn replay
d = pb.data()
for e in d["research"]["studies"][0]["evidence"]:
    if e["id"] == "e1":
        e["dropped"] = {"at": "2026-03-03T00:00:00Z", "reason": "withdrew"}
pb.save(d)
RS.TEMPLATE_DIR = stubs
check("dropped" in (refused(RS.build_page, pb.reg, "rs-ux-pay", "replay", eid="e1") or ""), "replay of a dropped session is refused")
RS.TEMPLATE_DIR = RS.DEFAULT_TEMPLATE_DIR

# ═════════════════════════════════════════════════════════════════════════════
section("8. import cycle")
code = ("import sys; sys.path.insert(0, %r); import research_session; "
        "assert 'research' not in sys.modules, 'research was imported at load time'; "
        "assert 'render' not in sys.modules; print('ok')" % TOOLS)
pr = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
check(pr.returncode == 0 and pr.stdout.strip() == "ok", "importing research_session imports neither research nor render (%s)" % (pr.stderr.strip()[-200:] or pr.stdout.strip()))
src_research = open(os.path.join(TOOLS, "research.py"), encoding="utf-8").read()
top_level = [ln for ln in src_research.splitlines() if ln.startswith(("import research_session", "from research_session"))]
check(top_level == [], "research.py has no top-level import of research_session (it may import it inside a function)")
pr = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import research_session as s; import research; "
                     "assert s._R() is research; print('ok')" % TOOLS], capture_output=True, text=True, cwd=ROOT)
check(pr.returncode == 0, "_R() returns the already-imported research module")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("PASS" if not fails else "FAIL: %d check(s) failed" % len(fails)))
for f_ in fails:
    print("  - " + f_)
sys.exit(0 if not fails else 1)
