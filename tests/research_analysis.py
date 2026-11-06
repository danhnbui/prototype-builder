#!/usr/bin/env python3
"""
research_analysis.py (test) — pins pb/tools/research_analysis.py, the tool that turns recorded session
evidence into every number a UX study reports.

All sessions below are SYNTHETIC TEST DATA built in this file (pseudonyms P01.., invented screens, no real
person or product). Every expected number is computed here independently of research_analysis: either plain
arithmetic written out in a comment, or the matching research_stats function applied to hand-listed inputs.

Usage:  python3 tests/research_analysis.py
Exit:   0 = pass · 1 = a failure
"""
import copy
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
sys.path.insert(0, TOOLS)

# ── the import must not pull in research.py (it will import this module) ─────
_probe = subprocess.run([sys.executable, "-c",
                         "import sys; sys.path.insert(0, %r); import research_analysis; print('research' in sys.modules)" % TOOLS],
                        capture_output=True, text=True)
NO_RESEARCH_AT_LOAD = _probe.stdout.strip() == "False"

import research_analysis as A  # noqa: E402
import research_stats as S  # noqa: E402

FAILS = []
CHECKS = [0]


def check(name, ok, detail=""):
    CHECKS[0] += 1
    if not ok:
        FAILS.append(name)
        print("FAIL  %s %s" % (name, detail))


def eq(name, got, want):
    check(name, got == want, "got %r, want %r" % (got, want))


def near(name, got, want, tol=1e-4):
    ok = got is not None and want is not None and abs(got - want) <= tol
    check(name, ok, "got %r, want %r" % (got, want))


def r4(x):
    return S.r4(x)


check("importing research_analysis leaves `research` out of sys.modules", NO_RESEARCH_AT_LOAD, _probe.stdout + _probe.stderr)


# ── session builder (synthetic) ──────────────────────────────────────────────

def session(method, pid, sid, tasks=(), answers=None, result=None, events=(), pilot=False, config=None):
    return {"format": "pb-session", "version": 1, "study": "rs-test", "method": method, "sessionId": sid,
            "participant": pid, "mode": "moderated", "pilot": pilot,
            "startedAt": "2026-01-01T10:00:00Z", "endedAt": "2026-01-01T10:10:00Z", "durationMs": 600000,
            "env": {"viewport": [1280, 832], "device": "laptop", "sink": "server", "shell": "test"},
            "consent": {"session": True, "recording": False, "at": "2026-01-01T10:00:00Z", "textSha256": "0" * 64},
            "config": config or {"tasks": []}, "tasks": list(tasks), "answers": answers or {},
            "result": result or {}, "events": list(events), "media": []}


def row(eid, obj, pid=None, dropped=False):
    return {"id": eid, "kind": "session", "file": "memory/research/rs-test/evidence/%s-x.json" % eid,
            "sha256": hashlib.sha256(("body-" + eid).encode()).hexdigest(), "participant": pid or obj["participant"],
            "dropped": dropped}


class Ev(object):
    """Event list builder for one session: keeps t non-decreasing."""
    def __init__(self):
        self.t, self.out = 0, []

    def add(self, typ, task=None, screen=None, **kw):
        self.t += 100
        e = {"t": self.t, "type": typ, "task": task, "screen": screen}
        e.update(kw)
        self.out.append(e)


def usability_events(tid, screens, clicks, dead, rage, errors):
    ev = Ev()
    ev.add("task-start", tid, screens[0])
    cur = screens[0]
    for s in screens[1:]:
        ev.add("nav", tid, cur, **{"from": cur, "to": s, "back": False})
        cur = s
    for i in range(clicks):
        ev.add("click", tid, cur, x=0.5, y=0.5, target="t", cmp=None, interactive=i >= dead, dead=i < dead)
    for _ in range(rage):
        ev.add("rage", tid, cur, x=0.5, y=0.5, count=3)
    for _ in range(errors):
        ev.add("field-error", tid, cur, field="f", msg="m")
    return ev.out


def utask(tid, outcome, start, end, assisted=False, answers=None, source="criteria"):
    return {"id": tid, "startT": start, "endT": end, "outcome": outcome, "outcomeSource": source, "criteriaT": None,
            "selfReport": None, "assisted": assisted, "answers": answers or {}}


# ── 1 · usability: 5 sessions, 2 tasks ───────────────────────────────────────

USAB_STUDY = {
    "id": "rs-test", "method": "usability", "status": "applied",
    "instrument": {"lang": "en", "sections": [
        {"title": "Task 1", "purpose": "task", "questions": [
            {"id": "t1", "text": "Pay for the order.", "task": {
                "screen": "route", "success": "Reaches the handover screen",
                "criteria": [{"screen": "handover"}], "optimalPath": ["route", "pay", "handover"]}},
            {"id": "t1-seq", "template": "seq"}]},
        {"title": "Task 2", "purpose": "task", "questions": [
            {"id": "t2", "text": "Find help.", "task": {"screen": "route", "success": "Opens help"}},
            {"id": "t2-seq", "template": "seq"}]},
        {"title": "Closing", "purpose": "closing", "questions": [
            {"id": "sus", "template": "sus"},
            {"id": "w1", "text": "How often do you pay online?", "type": "single", "options": ["Daily", "Weekly"]}]}]},
    "evidence": [], "observations": [], "issues": [],
}

T1 = [  # pid, outcome, assisted, start, end, screens, clicks, dead, rage, errors, seq
    ("P01", "success", False, 1000, 41000, ["route", "pay", "handover"], 5, 0, 0, 0, 6),
    ("P02", "success", False, 1000, 61000, ["route", "pay", "route", "handover"], 7, 2, 1, 1, 5),
    ("P03", "success", True, 1000, 51000, ["route", "pay", "handover"], 4, 1, 0, 0, 4),
    ("P04", "abandoned", False, 1000, 31000, ["route", "help", "route", "help", "route", "help", "pay"], 9, 3, 2, 2, 2),
    ("P05", "success", False, 1000, 81000, ["route", "pay", "handover"], 6, 0, 0, 0, 5),
]
# SUS item answers (items 1..10): odd item contributes v-1, even item 5-v; total * 2.5.
SUS_ANS = {
    "P01": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1],      # 5*(4) + 5*(4) = 40 -> 100
    "P02": [4, 2, 4, 2, 4, 2, 4, 2, 4, 2],      # 5*3 + 5*3 = 30 -> 75
    "P03": [3, 2, 3, 2, 3, 2, 3, 2, 3, 2],      # 5*2 + 5*3 = 25 -> 62.5
    "P04": [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],      # 5*2 + 5*2 = 20 -> 50
    "P05": [5, 1, 5],                              # only 3 of 10 answered -> not counted
}
SUS_SCORES = [100.0, 75.0, 62.5, 50.0]
W1 = {"P01": "Weekly", "P02": "Weekly", "P03": "Daily", "P04": "Weekly", "P05": "Daily"}


def build_usability():
    sessions = []
    for i, (pid, outc, asst, a, b, scr, clk, dead, rage, errs, seq) in enumerate(T1, 1):
        evs = usability_events("t1", scr, clk, dead, rage, errs)
        tasks = [utask("t1", outc, a, b, asst, {"t1-seq": seq})]
        if pid != "P05":
            tasks.append(utask("t2", "success", b, b + 10000, False, {"t2-seq": 7}))
            evs += usability_events("t2", ["route", "help"], 2, 0, 0, 0)
        else:
            tasks.append(utask("t2", "skipped", b, b + 100, False, {}, source="self"))
        ans = {"w1": W1[pid]}
        for k, v in enumerate(SUS_ANS[pid], 1):
            ans["sus-%d" % k] = v
        obj = session("usability", pid, "s-test-%04d" % i, tasks, ans, events=evs)
        sessions.append((row("e%d" % i, obj), obj))
    return sessions


U = build_usability()
USTUDY_BEFORE = json.dumps(USAB_STUDY, sort_keys=True)
a = A.analyze(USAB_STUDY, U)
t1 = a["usability"]["tasks"]["t1"]
t2 = a["usability"]["tasks"]["t2"]

eq("n sessions", a["n"], 5)
eq("method", a["method"], "usability")
eq("inputs", a["inputs"], ["e1", "e2", "e3", "e4", "e5"])
# inputsHash = sha256 of "e1:<sha>\n...\ne5:<sha>" built here by hand
want_hash = hashlib.sha256("\n".join("%s:%s" % (r["id"], r["sha256"]) for r, _o in U).encode()).hexdigest()
eq("inputsHash", a["inputsHash"], want_hash)
eq("study not mutated", json.dumps(USAB_STUDY, sort_keys=True), USTUDY_BEFORE)

# success: P01, P02, P05 succeed unassisted (3); P03 is an assisted success; P04 abandoned -> 3 of 5
w = S.adjusted_wald(3, 5)
eq("t1 success x/n", (t1["success"]["x"], t1["success"]["n"]), (3, 5))
eq("t1 success rate", t1["success"]["rate"], r4(w["rate"]))
eq("t1 success low", t1["success"]["low"], r4(w["low"]))
eq("t1 success high", t1["success"]["high"], r4(w["high"]))
eq("t1 n", t1["n"], 5)
eq("t1 assisted", t1["assisted"], 1)
eq("t1 abandoned", t1["abandoned"], 1)
eq("t1 timeouts", t1["timeouts"], 0)
eq("t1 unknownOutcome", t1["unknownOutcome"], 0)
# time on task: successful, unassisted attempts only -> 40, 60, 80 s (P01, P02, P05)
g = S.geo_mean_ci([40.0, 60.0, 80.0])
eq("t1 time n", t1["time"]["n"], 3)
eq("t1 time geoMean", t1["time"]["geoMean"], r4(g["geoMean"]))
near("t1 time geoMean arithmetic (40*60*80)^(1/3)", t1["time"]["geoMean"], (40 * 60 * 80) ** (1.0 / 3))
eq("t1 time low", t1["time"]["low"], r4(g["low"]))
eq("t1 time high", t1["time"]["high"], r4(g["high"]))
eq("t1 time median", t1["time"]["median"], 60.0)
# timeAll: every non-skipped attempt -> 40, 60, 50, 30, 80
ga = S.geo_mean_ci([40.0, 60.0, 50.0, 30.0, 80.0])
eq("t1 timeAll n", t1["timeAll"]["n"], 5)
eq("t1 timeAll geoMean", t1["timeAll"]["geoMean"], r4(ga["geoMean"]))
eq("t1 timeAll median", t1["timeAll"]["median"], 50.0)
# click counts: 5+7+4+9+6 = 31 over 5 attempts; dead 0+2+1+3+0 = 6; rage 0+1+0+2+0 = 3; errors 0+1+0+2+0 = 3
eq("t1 clicks mean", t1["clicks"]["mean"], r4(31 / 5.0))
eq("t1 dead total", t1["deadClicks"]["total"], 6)
eq("t1 dead mean", t1["deadClicks"]["mean"], r4(6 / 5.0))
eq("t1 rage", t1["rageClicks"], 3)
eq("t1 errors total", t1["errors"]["total"], 3)
eq("t1 errors mean", t1["errors"]["mean"], r4(3 / 5.0))


def lost(s, n, r):
    return math.sqrt((n / float(s) - 1) ** 2 + (r / float(n) - 1) ** 2)


# lostness with R = 3 required screens. S = visits, N = distinct:
#   P01 3/3 -> 0 · P02 route,pay,route,handover S=4 N=3 -> sqrt((3/4-1)^2 + 0) = 0.25
#   P03 3/3 -> 0 · P04 S=7 N=3 (route,help,pay) -> sqrt((3/7-1)^2 + 0) = 4/7 · P05 -> 0
LV = [0.0, lost(4, 3, 3), 0.0, lost(7, 3, 3), 0.0]
near("hand lostness P02 = 0.25", LV[1], 0.25, 1e-12)
eq("t1 lostness n", t1["lostness"]["n"], 5)
eq("t1 lostness mean", t1["lostness"]["mean"], r4(sum(LV) / 5.0))
eq("t1 lostShare (only P04 > 0.4)", t1["lostness"]["lostShare"], 0.2)
# SEQ answers 6, 5, 4, 2, 5 -> mean 22/5 = 4.4
m = S.mean_ci([6.0, 5.0, 4.0, 2.0, 5.0])
eq("t1 seq", t1["seq"], {"n": 5, "mean": 4.4, "low": r4(m["low"]), "high": r4(m["high"])})
# paths: route>pay>handover x3 (P01, P03, P05) first, then the two singles ordered by path
eq("t1 top path", t1["paths"][0], {"path": ["route", "pay", "handover"], "count": 3})
eq("t1 paths count", len(t1["paths"]), 3)
# task 2: no optimalPath -> no lostness; P05 skipped -> n = 4, all succeed
check("t2 has no lostness", "lostness" not in t2)
eq("t2 n and success", (t2["n"], t2["success"]["x"]), (4, 4))
eq("t2 seq mean", t2["seq"]["mean"], 7.0)
# overall: 3 + 4 successes over 5 + 4 attempts
ow = S.adjusted_wald(7, 9)
eq("overall success", a["usability"]["overall"]["success"], {"x": 7, "n": 9, "rate": r4(ow["rate"]), "low": r4(ow["low"]), "high": r4(ow["high"])})
# SUS: four sessions answered all ten
sm = S.mean_ci(SUS_SCORES)
sus = a["usability"]["sus"]
eq("sus n", sus["n"], 4)
eq("sus mean = (100+75+62.5+50)/4", sus["mean"], 71.875)
eq("sus sd", sus["sd"], r4(statistics.stdev(SUS_SCORES)))
eq("sus ci (clamped to the 0..100 scale)", (sus["low"], sus["high"]),
   (r4(max(0, sm["low"])), r4(min(100, sm["high"]))))
eq("sus grade (71.875 >= 71.1 -> C+)", sus["grade"], "C+")
# answers (pre/post, non-task): w1 single -> Weekly 3, Daily 2
w1 = a["answers"]["w1"]
eq("answers w1 counts", (w1["n"], w1["counts"]["Weekly"], w1["counts"]["Daily"]), (5, 3, 2))
check("answers hold the sus group", "sus" in a["answers"] and a["answers"]["sus"]["score"]["n"] == 4)
check("answers hold no task answers", "t1-seq" not in a["answers"])
check("only the usability block", all(k not in a for k in ("treeTest", "cardSort", "firstClick")))

# determinism: two calls, dumped with sorted keys, byte-identical
j1 = json.dumps(A.analyze(USAB_STUDY, U), sort_keys=True)
j2 = json.dumps(A.analyze(copy.deepcopy(USAB_STUDY), copy.deepcopy(U)), sort_keys=True)
eq("analyze is byte-identical", j1, j2)
eq("float values are r4-stable", json.loads(j1)["usability"]["sus"]["mean"], 71.875)

# ── 2 · exclusions: dropped, pilot ───────────────────────────────────────────

pilot_obj = session("usability", "P09", "s-test-0009", [utask("t1", "success", 0, 10000)], pilot=True)
drop_obj = session("usability", "P08", "s-test-0008", [utask("t1", "success", 0, 10000)])
extra_study = copy.deepcopy(USAB_STUDY)
extra_study["evidence"] = [dict(row("e6", drop_obj), dropped=True)]     # dropped, not passed in
mixed = U + [(row("e7", pilot_obj), pilot_obj), (row("e8", drop_obj, dropped=True), drop_obj)]
ax = A.analyze(extra_study, mixed)
eq("excluded reasons", ax["excluded"], {"e6": "dropped", "e7": "pilot", "e8": "dropped"})
eq("excluded rows do not count", (ax["n"], ax["inputs"]), (5, ["e1", "e2", "e3", "e4", "e5"]))
eq("excluded rows do not change the numbers", ax["usability"], a["usability"])
eq("same inputsHash with exclusions", ax["inputsHash"], a["inputsHash"])
bad = A.analyze(USAB_STUDY, [({"id": "e9"}, None)])
check("a non-session is excluded as invalid", bad["excluded"].get("e9", "").startswith("invalid"), bad["excluded"])
eq("no sessions -> n 0, no crash", A.analyze(USAB_STUDY, [])["n"], 0)

# ── 3 · issues and affinity ──────────────────────────────────────────────────

syn = copy.deepcopy(USAB_STUDY)
syn["evidence"] = [row("e%d" % i, U[i - 1][1]) for i in range(1, 6)]
syn["observations"] = [
    {"id": "o1", "evidence": "e1", "participant": "P01", "task": "t1", "t": 5000, "note": "n", "tags": ["total-hidden", "cash-unclear"]},
    {"id": "o2", "evidence": "e2", "task": "t1", "t": 6000, "note": "n", "tags": ["total-hidden"]},   # participant from the row: P02
    {"id": "o3", "evidence": "e1", "participant": "P01", "task": "t2", "t": 7000, "note": "n", "tags": ["total-hidden"]},
]
syn["issues"] = [
    {"id": "u1", "title": "x", "task": "t1", "severity": 3, "observations": ["o1", "o2", "o3"]},
    {"id": "u2", "title": "y", "task": "t1", "severity": 2, "observations": ["o1", "o-missing"]},
]
im = A.issue_metrics(syn, {"n": 5})
# u1: P01 + P02 = 2 participants -> frequency 2/5 = 0.4, priority 3 * 0.4 = 1.2
eq("issue u1", im["u1"], {"participants": 2, "frequency": 0.4, "priority": 1.2})
# u2: only o1 is known -> P01 -> 1/5 = 0.2, priority 2 * 0.2 = 0.4
eq("issue u2", im["u2"], {"participants": 1, "frequency": 0.2, "priority": 0.4})
af = A.affinity(syn)["tags"]
eq("affinity total-hidden", af["total-hidden"], {"observations": 3, "participants": 2, "tasks": ["t1", "t2"]})
eq("affinity cash-unclear", af["cash-unclear"], {"observations": 1, "participants": 1, "tasks": ["t1"]})
asyn = A.analyze(syn, U)
eq("analyze embeds issues", asyn["issues"], im)
eq("analyze embeds affinity", asyn["affinity"], A.affinity(syn))
eq("no observations -> empty issues", a["issues"], {})
eq("no observations -> empty affinity", a["affinity"], {"tags": {}})
eq("zero n gives no frequency", A.issue_metrics(syn, {"n": 0})["u1"]["frequency"], None)

# ── 4 · resolve / verify_ref / allowed_numbers ───────────────────────────────

eq("resolve rate", A.resolve(a, "usability.tasks.t1.success.rate"), 0.6)
eq("resolve list index", A.resolve(a, "usability.tasks.t1.paths.0.count"), 3)
try:
    A.resolve(a, "usability.tasks.t1.nope")
    check("resolve missing raises KeyError", False)
except KeyError:
    check("resolve missing raises KeyError", True)
eq("verify_ref match", A.verify_ref({"analysis": "usability.tasks.t1.success.rate", "value": 0.6}, a), None)
eq("verify_ref match within r4", A.verify_ref({"analysis": "usability.tasks.t1.success.rate", "value": 0.60001}, a), None)
eq("verify_ref int exact match", A.verify_ref({"analysis": "usability.tasks.t1.success.x", "value": 3}, a), None)
mm = A.verify_ref({"analysis": "usability.tasks.t1.success.rate", "value": 0.7}, a)
check("verify_ref mismatch is a message", isinstance(mm, str) and "0.6" in mm and "0.7" in mm, mm)
check("verify_ref int mismatch", isinstance(A.verify_ref({"analysis": "usability.tasks.t1.success.x", "value": 4}, a), str))
ms = A.verify_ref({"analysis": "usability.tasks.t9.success.rate", "value": 0.5}, a)
check("verify_ref missing path is a message", isinstance(ms, str) and "t9" in ms, ms)
check("verify_ref non-number value", isinstance(A.verify_ref({"analysis": "n", "value": "5"}, a), str))
nums = A.allowed_numbers(a)
check("allowed has the rate", 0.6 in nums)
check("allowed has rate as percent, 0 decimals", 60 in nums and 60.0 in nums)
low_pct = a["usability"]["tasks"]["t1"]["success"]["low"] * 100
check("allowed has a CI bound as percent, 1 decimal", round(low_pct, 1) in nums)
check("allowed has the whole percent of a CI bound", round(low_pct, 0) in nums)
check("allowed has ints", 5 in nums and 3 in nums)
check("allowed has the SUS mean", 71.875 in nums and 71.9 in nums)
check("allowed excludes a number never computed", 12345 not in nums)

# ── 5 · tree test ────────────────────────────────────────────────────────────

TREE = [{"id": "n-orders", "label": "Orders", "parent": None}, {"id": "n-refunds", "label": "Refunds", "parent": "n-orders"},
        {"id": "n-returns", "label": "Returns", "parent": "n-orders"}, {"id": "n-account", "label": "Account", "parent": None},
        {"id": "n-profile", "label": "Profile", "parent": "n-account"}]
TREE_STUDY = {"id": "rs-test", "method": "tree-test", "instrument": {"tree": TREE, "sections": [
    {"title": "Tasks", "purpose": "task", "questions": [
        {"id": "tt1", "text": "Where would you go to get money back?", "tree": {"correct": ["n-refunds"]}}]}]}}
# (opened nodes in order, chosen, skipped, ms)
TT = [
    (["n-orders"], "n-refunds", False, 20000),                  # direct success, first click on path
    (["n-account", "n-orders"], "n-refunds", False, 30000),     # went into Account first: backtracked, off-path first click
    (["n-orders", "n-returns"], "n-returns", False, 10000),     # wrong answer; Returns is a child of Orders so no backtrack
    ([], None, True, 5000),                                     # skipped: not counted
    (["n-orders"], "n-refunds", False, 40000),
]
tsess = []
for i, (opened, chosen, skipped, ms) in enumerate(TT, 1):
    ev = Ev()
    for node in opened:
        ev.add("tt-open", "tt1", None, node=node)
    if chosen:
        ev.add("tt-choose", "tt1", None, node=chosen)
    path = []
    node = chosen
    while node:
        path.insert(0, node)
        node = {n["id"]: n["parent"] for n in TREE}.get(node)
    obj = session("tree-test", "P%02d" % i, "s-tree-%04d" % i,
                  [utask("tt1", "skipped" if skipped else "answered", 0, ms, source="self")],
                  result={"tree-test": {"tt1": {"chosen": chosen, "path": path}}}, events=ev.out,
                  config={"tasks": [], "tree": TREE})
    tsess.append((row("e%d" % i, obj), obj))
at = A.analyze(TREE_STUDY, tsess)
tt = at["treeTest"]["tasks"]["tt1"]
# 5 attempts: the skipped one stays in n but is not a success; the runner records "answered" for a choice, so
# success is judged only from chosen vs tree.correct. success: attempts 1, 2, 5 = 3; direct (no backtrack): 1, 5 = 2;
# first click on the path root->n-refunds ({n-orders, n-refunds}): 1, 3, 5 = 3 (attempt 2 opened n-account first)
eq("tree n includes the skipped attempt", tt["n"], 5)
eq("tree success", tt["success"], {k: (r4(v) if isinstance(v, float) else v) for k, v in S.adjusted_wald(3, 5).items()})
eq("tree direct x", (tt["direct"]["x"], tt["direct"]["n"]), (2, 5))
eq("tree direct rate", tt["direct"]["rate"], r4(S.adjusted_wald(2, 5)["rate"]))
eq("tree firstClick x", (tt["firstClick"]["x"], tt["firstClick"]["n"]), (3, 5))
# destinations: n-refunds x3, n-returns x1
eq("tree destinations", tt["destinations"], [{"node": "n-refunds", "count": 3}, {"node": "n-returns", "count": 1}])
# times of the 4 non-skipped attempts: 20, 30, 10, 40 s -> median (20+30)/2 = 25
eq("tree time median", tt["time"]["median"], 25.0)
eq("tree time n", tt["time"]["n"], 4)
# a skipped task with no result entry at all still counts as an attempt that failed
nores = session("tree-test", "P06", "s-tree-0006", [utask("tt1", "skipped", 0, 1000, source="self")], config={"tasks": [], "tree": TREE})
tt6 = A.analyze(TREE_STUDY, tsess + [(row("e6", nores), nores)])["treeTest"]["tasks"]["tt1"]
eq("tree skipped without result is in n, not a success", (tt6["n"], tt6["success"]["x"]), (6, 3))
check("tree has only its block", "usability" not in at and "treeTest" in at)

# ── 6 · card sort, open and closed ───────────────────────────────────────────

CARDS = [{"id": "c%d" % i, "label": "Card %d" % i, "job": None} for i in (1, 2, 3, 4)]
OPEN_STUDY = {"id": "rs-test", "method": "card-sort", "instrument": {"cards": CARDS, "sort": {"kind": "open", "categories": []}, "sections": []}}


def sort_obj(i, groups):
    return session("card-sort", "P%02d" % i, "s-sort-%04d" % i, result={"card-sort": {"groups": groups, "unsorted": []}},
                   config={"tasks": [], "cards": CARDS})


csess = []
for i, groups in enumerate([
    [{"name": "Money", "category": None, "cards": ["c1", "c2"]}, {"name": "Help", "category": None, "cards": ["c3", "c4"]}],
    [{"name": "  money ", "category": None, "cards": ["c1", "c2", "c3"]}, {"name": "HELP", "category": None, "cards": ["c4"]}],
    [{"name": "Stuff", "category": None, "cards": ["c1", "c3"]}, {"name": "Other", "category": None, "cards": ["c2", "c4"]}],
], 1):
    o = sort_obj(i, groups)
    csess.append((row("e%d" % i, o), o))
ac = A.analyze(OPEN_STUDY, csess)
cs = ac["cardSort"]
# all three placed every card, so each pair is out of 3 participants:
#  c1|c2 together for A, B -> 2/3 · c1|c3 for B, C -> 2/3 · c1|c4 none -> 0 · c2|c3 B -> 1/3 · c2|c4 C -> 1/3 · c3|c4 A -> 1/3
want_sim = {"c1|c2": 2 / 3.0, "c1|c3": 2 / 3.0, "c1|c4": 0.0, "c2|c3": 1 / 3.0, "c2|c4": 1 / 3.0, "c3|c4": 1 / 3.0}
eq("cs similarity keys", sorted(cs["similarity"]), sorted(want_sim))
for k, v in want_sim.items():
    eq("cs similarity %s" % k, cs["similarity"][k], r4(v))
eq("cs n and kind", (cs["n"], cs["kind"]), (3, "open"))
eq("cs cards", cs["cards"], ["c1", "c2", "c3", "c4"])
# average linkage: c1+c2 first (tie 2/3 with c1|c3 goes to the lowest pair), then {c1,c2}+c3 at (2/3 + 1/3)/2 = 0.5
# (>= the 0.5 threshold), then c4 at (0 + 1/3 + 1/3)/3 = 2/9 (< threshold)
eq("cs first merge", (cs["merges"][0]["a"], cs["merges"][0]["b"], cs["merges"][0]["sim"]), (["c1"], ["c2"], r4(2 / 3.0)))
eq("cs merge count", len(cs["merges"]), 3)
eq("cs second merge sim", cs["merges"][1]["sim"], 0.5)
eq("cs last merge sim", cs["merges"][2]["sim"], r4(2 / 9.0))
eq("cs threshold", cs["threshold"], 0.5)
eq("cs clusters", cs["clusters"], [["c1", "c2", "c3"], ["c4"]])
# open categories by normalised name: money (A, B) and help (A, B) used twice; stuff and other once
eq("cs category keys", sorted(cs["categories"]), ["help", "money", "other", "stuff"])
eq("cs money count", cs["categories"]["money"]["count"], 2)
# of the 2 who made "money": c1, c2 in both, c3 in B only -> 1.0, 1.0, 0.5
eq("cs money cards", cs["categories"]["money"]["cards"], {"c1": 1.0, "c2": 1.0, "c3": 0.5})
eq("cs help cards", cs["categories"]["help"]["cards"], {"c3": 0.5, "c4": 1.0})
eq("cs stuff cards", cs["categories"]["stuff"]["cards"], {"c1": 1.0, "c3": 1.0})

CLOSED_STUDY = {"id": "rs-test", "method": "card-sort", "instrument": {"cards": CARDS, "sections": [], "sort": {
    "kind": "closed", "categories": [{"id": "k-money", "label": "Money"}, {"id": "k-help", "label": "Help"}]}}}
clsess = []
for i, groups in enumerate([
    [{"name": "anything", "category": "k-money", "cards": ["c1", "c2"]}, {"name": "x", "category": "k-help", "cards": ["c3", "c4"]}],
    [{"name": "y", "category": "k-money", "cards": ["c1", "c3"]}, {"name": "z", "category": "k-help", "cards": ["c2", "c4"]}],
], 1):
    o = sort_obj(i, groups)
    clsess.append((row("e%d" % i, o), o))
acl = A.analyze(CLOSED_STUDY, clsess)["cardSort"]
eq("closed keys are category ids", sorted(acl["categories"]), ["k-help", "k-money"])
eq("closed count", acl["categories"]["k-money"]["count"], 2)
# k-money: c1 in both sorts (1.0), c2 in one (0.5), c3 in one (0.5)
eq("closed cards", acl["categories"]["k-money"]["cards"], {"c1": 1.0, "c2": 0.5, "c3": 0.5})
eq("closed label", acl["categories"]["k-money"]["label"], "Money")
eq("closed kind", acl["kind"], "closed")
# c1|c2 together for the first participant only -> 1/2
eq("closed similarity c1|c2", acl["similarity"]["c1|c2"], 0.5)

# ── 7 · first click ──────────────────────────────────────────────────────────

FC_STUDY = {"id": "rs-test", "method": "first-click", "instrument": {"sections": [{"title": "Clicks", "purpose": "task", "questions": [
    {"id": "fc1", "text": "Where first?", "click": {"screen": "pay", "target": "[data-action=\"submit\"]",
                                                    "rect": {"x": 0.1, "y": 0.8, "w": 0.3, "h": 0.1}}},
    {"id": "fc2", "text": "And here?", "click": {"screen": "pay", "rect": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.2}}}]}]}}
# fc1 has a target AND a rect: the recorded hit may come from the target. fc2 is rect-only.
#   (x, y, recorded hit)  fc1: in rect+hit · outside rect+hit (target) · outside+miss · in rect but recorded MISS (disagrees)
FC = [
    {"fc1": (0.2, 0.85, True, 2000), "fc2": (0.6, 0.6, True, 4000)},     # fc2: in rect, hit  -> agree
    {"fc1": (0.9, 0.1, True, 3000), "fc2": (0.1, 0.1, True, 5000)},      # fc2: outside rect, recorded hit -> disagree
    {"fc1": (0.9, 0.1, False, 4000), "fc2": (0.6, 0.6, False, 6000)},    # fc2: in rect, recorded miss -> disagree
    {"fc1": (0.2, 0.85, False, 5000), "fc2": (0.1, 0.1, False, 7000)},   # fc1: in rect, recorded miss -> disagree
]
fsess = []
for i, d in enumerate(FC, 1):
    res = {tid: {"x": x, "y": y, "hit": hit, "ms": ms, "target": "btn"} for tid, (x, y, hit, ms) in d.items()}
    o = session("first-click", "P%02d" % i, "s-fc-%04d" % i, result={"first-click": res})
    fsess.append((row("e%d" % i, o), o))
af_ = A.analyze(FC_STUDY, fsess)["firstClick"]["tasks"]
f1, f2 = af_["fc1"], af_["fc2"]
eq("fc1 success x/n", (f1["success"]["x"], f1["success"]["n"]), (2, 4))      # recorded hits: P01, P02
eq("fc1 rate", f1["success"]["rate"], r4(S.adjusted_wald(2, 4)["rate"]))
# fc1 mismatch: with a target, only "rect says hit, recorded miss" is a certain disagreement -> P04 only
eq("fc1 hitMismatch", f1["hitMismatch"], 1)
# fc2 recorded hits: P01, P02 -> 2 of 4 ; rect-only so any difference counts: P02 (outside, hit), P03 (inside, miss)
eq("fc2 success x/n", (f2["success"]["x"], f2["success"]["n"]), (2, 4))
eq("fc2 hitMismatch", f2["hitMismatch"], 2)
eq("fc1 click points", f1["clicks"], [[0.2, 0.85, True], [0.9, 0.1, True], [0.9, 0.1, False], [0.2, 0.85, False]])
# fc1 times 2, 3, 4, 5 s -> median 3.5; geometric mean (2*3*4*5)^(1/4)
eq("fc1 time median", f1["time"]["median"], 3.5)
near("fc1 time geoMean (120^(1/4))", f1["time"]["geoMean"], 120 ** 0.25)
eq("fc2 time n", f2["time"]["n"], 4)

# ── 8 · an "answered" outcome outside a tree test ────────────────────────────

ans_u = copy.deepcopy(U[0][1])
ans_u["tasks"][0]["outcome"] = "answered"        # P01's t1 success becomes "answered": counted, not a success
au = A.analyze(USAB_STUDY, [(U[0][0], ans_u)] + U[1:])["usability"]["tasks"]["t1"]
eq("usability answered: unknownOutcome", au["unknownOutcome"], 1)
eq("usability answered: not a success (P02, P05 remain)", (au["success"]["x"], au["success"]["n"]), (2, 5))
fc_ans = copy.deepcopy(fsess[0][1])
fc_ans["tasks"] = [utask("fc1", "answered", 0, 2000, source="self")]
fa = A.analyze(FC_STUDY, [(fsess[0][0], fc_ans)] + fsess[1:])["firstClick"]["tasks"]["fc1"]
# P01 recorded a hit but its outcome is "answered": counted in n and unknownOutcome, not a success -> only P02 hit
eq("first-click answered", (fa["unknownOutcome"], fa["success"]["x"], fa["success"]["n"]), (1, 1, 4))
eq("first-click unknownOutcome default", f1["unknownOutcome"], 0)

# ── result ───────────────────────────────────────────────────────────────────

if FAILS:
    print("FAIL  %d of %d checks failed: %s" % (len(FAILS), CHECKS[0], ", ".join(FAILS)))
    sys.exit(1)
print("PASS  research_analysis — %d checks" % CHECKS[0])
