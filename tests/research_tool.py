#!/usr/bin/env python3
"""
research_tool.py — /pb:research's engine (pb/tools/research.py), end to end on a temp copy of
fixtures/research/ (a synthetic parcel-desk registry, a Google-Forms-style CSV, two transcripts).

What it proves:

  1. A full SURVEY path: init -> plan -> check -> approve -> import -> tally -> synthesize ->
     verify -> refill, and a full INTERVIEW path through the same verbs (tally is refused there).
  2. The refusals that keep the evidence honest: import while draft, --consent no / missing,
     a PII column, the same file twice, a plan after evidence, refill without --approved or with a
     failing verify, a quote that is not verbatim, a quote citing a file pb cannot read, a tally
     citation with the wrong count, a file changed after import (sha256), a dropped participant
     still cited, approve with check errors, a study that names nobody, an unresolved target.
  3. --drop-columns removes the column from the STORED file; stored evidence is chmod 444; the
     instrument export is byte-identical run to run; refill is idempotent, replaces its own text in
     place, appends and warns when the text was edited, and never touches other text (it backs up).
  4. A Google-Forms CSV (BOM, Timestamp, header = question text, multi answers joined with ", ")
     imports and tallies right; screener exclusions are counted; Vietnamese text matches after NFC.
  5. check / verify / gaps / seed / list / show change nothing on disk.

Usage:  python3 tests/research_tool.py
Exit:   0 = pass · 1 = a failure
"""
import copy
import csv
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "pb", "tools", "research.py")
FIX = os.path.join(ROOT, "fixtures", "research")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
_spec = importlib.util.spec_from_file_location("research", TOOL)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

fails = []
TMP = tempfile.mkdtemp(prefix="pb-research-")
_n = [0]


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def section(title):
    print("\n" + title)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def jload(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def tree_hash(root):
    h = hashlib.sha256()
    for cur, dirs, files in os.walk(root):
        dirs.sort()
        h.update(("D " + os.path.relpath(cur, root) + "\n").encode())
        for f in sorted(files):
            p = os.path.join(cur, f)
            h.update(("F " + os.path.relpath(p, root) + "\n").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


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

    def backups(self, sid):
        d = self.path("memory", "backups")
        return sorted(x for x in os.listdir(d) if x.startswith("research-%s-" % sid)) if os.path.isdir(d) else []


CSV = os.path.join(FIX, "forms-responses.csv")
SKIP = ("--skip-review", "fixture: the bias review has its own section")


def survey_fielding(sid="rs-cod"):
    """A survey study at `fielding`: init, plan, approve, import the Forms CSV (Email dropped)."""
    p = Proj()
    p.run("init", sid, "--method", "survey", "--scope", "collect", "--question", "Do couriers need the cash amount first?",
          "--role", "courier", "--segment", "rural, under 1 year on the job", "--target", "job:pay-cod")
    p.run("plan", sid, "--file", os.path.join(FIX, "survey-plan.json"))
    p.run("approve", sid, *SKIP)
    rc, out, err = p.run("import", sid, CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
    assert rc == 0, (rc, out, err)
    return p


def interview_fielding(sid="rs-handover", p2_consent="unknown"):
    p = Proj()
    p.run("init", sid, "--method", "interview", "--scope", "collect", "--question", "How do dispatchers confirm a handover?",
          "--role", "dispatcher", "--target", "job:confirm-handover", "--target", "screen:handover")
    p.run("plan", sid, "--file", os.path.join(FIX, "interview-plan.json"))
    p.run("approve", sid, *SKIP)
    rc, out, err = p.run("import", sid, os.path.join(FIX, "transcript-p01.txt"), "--kind", "transcript",
                         "--consent", "yes", "--participant", "P01", "--role", "dispatcher")
    assert rc == 0, (rc, out, err)
    rc, out, err = p.run("import", sid, os.path.join(FIX, "transcript-p02.txt"), "--kind", "transcript",
                         "--consent", p2_consent, "--participant", "P02", "--role", "dispatcher")
    assert rc == 0, (rc, out, err)
    return p


def codes(items):
    return sorted({i["code"] for i in items})


# ═════════════════════════════════════════════════════════════════════════════
section("1. the survey path, verb by verb")
p = Proj()
rc, out, err = p.run("init", "rs-cod", "--method", "survey", "--scope", "collect", "--question", "Do couriers need the cash amount first?",
                     "--role", "courier", "--segment", "rural, under 1 year on the job", "--target", "job:pay-cod")
st = p.study("rs-cod")
check(rc == 0 and st["status"] == "draft" and st["audience"]["targetN"] == 30, "init: a draft survey, targetN defaults to 30")
check(p.data()["research"]["populated"] is True, "init: research.populated is set")

rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes")
check(rc == 1 and not os.path.exists(p.path("memory", "research", "rs-cod", "evidence")),
      "REFUSED import while the study is still a draft (no G-STUDY): nothing stored")

rc, out, err = p.run("approve", "rs-cod")
check(rc == 1 and "C-INTRO" in codes(out.get("errors", [])), "REFUSED approve of an empty draft (check errors: no intro)")

rc, out, err = p.run("plan", "rs-cod", "--file", os.path.join(FIX, "survey-plan.json"))
check(rc == 0 and len(p.study("rs-cod")["hypotheses"]) == 3 and p.study("rs-cod")["audience"]["targetN"] == 10,
      "plan: hypotheses + instrument merged, audience merged (targetN 10)")
check(all(h["verdict"] is None for h in p.study("rs-cod")["hypotheses"]), "plan: every hypothesis starts with verdict null")

before = p.raw()
rc, out, err = p.run("check", "rs-cod")
check(rc == 0 and out["errors"] == [] and p.raw() == before, "check: clean, writes nothing")

rc, out, err = p.run("approve", "rs-cod", "--note", "reviewed with the lead", *SKIP)
st = p.study("rs-cod")
check(rc == 0 and st["status"] == "approved" and st["gates"][0]["gate"] == "G-STUDY"
      and st["gates"][0]["note"] == "reviewed with the lead", "approve: status approved, G-STUDY appended with its note")
survey_md = p.path("memory", "research", "rs-cod", "instrument", "survey.md")
tmpl = p.path("memory", "research", "rs-cod", "instrument", "responses-template.csv")
check(os.path.isfile(survey_md) and os.path.isfile(tmpl), "approve: survey.md and responses-template.csv written")
check(open(survey_md, encoding="utf-8").read().find("Approved at G-STUDY") > 0
      and "DRAFT" not in open(survey_md, encoding="utf-8").read(), "survey.md carries the approved header")
check(open(tmpl, encoding="utf-8").read() == "q1,q2,q3,q4,q5,q6,q7\n", "responses-template.csv: the question ids as the header")

# export determinism
a1 = (open(survey_md, "rb").read(), open(tmpl, "rb").read())
rc1 = p.run("export", "rs-cod")[0]
a2 = (open(survey_md, "rb").read(), open(tmpl, "rb").read())
rc2 = p.run("export", "rs-cod")[0]
a3 = (open(survey_md, "rb").read(), open(tmpl, "rb").read())
check(rc1 == rc2 == 0 and a1 == a2 == a3, "export: byte-identical across two runs, and to what approve wrote")
check(b"2026-11" not in a3[0] and b"T10:" not in a3[0], "export: no timestamp in survey.md")

# imports
rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes")
check(rc == 1 and "Email Address" in out.get("error", "") and not os.path.exists(p.path("memory", "research", "rs-cod", "evidence")),
      "REFUSED import of a CSV with a PII column (Email Address) and no --drop-columns")
rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "no", "--drop-columns", "Email Address")
check(rc == 1 and not p.study("rs-cod")["evidence"], "REFUSED import with --consent no: nothing stored")
rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--drop-columns", "Email Address")
check(rc == 2 and not p.study("rs-cod")["evidence"], "REFUSED import with --consent missing (exit 2)")
rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Emial Address")
check(rc == 1 and not p.study("rs-cod")["evidence"], "REFUSED a --drop-columns name that is no column (a typo would leave the PII in)")

rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
ev = p.study("rs-cod")["evidence"]
stored = p.path(*ev[0]["file"].split("/")) if ev else ""
check(rc == 0 and len(ev) == 1 and ev[0]["id"] == "e1" and ev[0]["kind"] == "responses" and ev[0]["consent"] == "yes",
      "import: e1 stored (kind responses, consent yes)")
check(p.study("rs-cod")["status"] == "fielding", "import: status -> fielding")
check(ev[0]["responses"] == 14 and ev[0]["droppedColumns"] == ["Email Address"] and ev[0]["dropped"] is None,
      "import: 14 response rows counted, droppedColumns recorded")
check(os.path.isfile(stored) and stat.S_IMODE(os.stat(stored).st_mode) == 0o444, "stored evidence is chmod 444")
body = open(stored, encoding="utf-8").read()
check("Email Address" not in body and "@example.com" not in body, "--drop-columns removed the column from the STORED file")
check(sha(open(stored, "rb").read()) == ev[0]["sha256"], "evidence sha256 is the sha256 of the stored file")
check(ev[0]["file"] == "memory/research/rs-cod/evidence/e1-forms-responses.csv", "evidence path is memory/research/<id>/evidence/e1-<name>")
check([m["question"] for m in out["matched"]] == ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]
      and all(m["by"] == "text" for m in out["matched"]) and [i["column"] for i in out["ignored"]] == ["Timestamp"],
      "import: reports the 7 columns matched to questions by text, and Timestamp ignored")
check(open(CSV, "rb").read().startswith(b"\xef\xbb\xbf"), "(the fixture CSV really starts with a UTF-8 BOM)")

rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
check(rc == 1 and len(p.study("rs-cod")["evidence"]) == 1, "REFUSED the same file twice (same sha256)")
rc, out, err = p.run("plan", "rs-cod", "--file", os.path.join(FIX, "survey-plan.json"))
check(rc == 1 and "evidence" in out.get("error", ""), "REFUSED plan once evidence exists")

# tally
rc, out, err = p.run("tally", "rs-cod")
t = p.study("rs-cod").get("tally", {})
bq = t.get("byQuestion", {})
check(rc == 0 and t["n"] == 12 and t["excluded"] == 2 and t["excludedWhy"] == {"q1": 1, "q2": 1},
      "tally: 14 rows -> n 12, excluded 2 (one per failing screener)")
check(bq["q3"]["counts"] == {"Yes": 8, "No": 4} and bq["q3"]["n"] == 12, "tally: single choice counts (Yes 8, No 4)")
check(abs(bq["q4"]["mean"] - 47 / 12.0) < 0.001 and bq["q4"]["counts"]["4"] == 6, "tally: scale mean 3.9167 and per-value counts")
check(bq["q5"]["counts"] == {"Cash": 8, "Bank transfer": 3, "E-wallet": 5, "Cash, counted at the door": 2},
      "tally: multi-select split on ', ' with the option that holds a comma matched whole")
check(bq["q6"]["n"] == 11 and bq["q6"]["counts"] == {}, "tally: text is counted (11), not summarised")
check(abs(bq["q7"]["mean"] - 29.25) < 0.001, "tally: number mean 29.25")
check(any("under the target" in w for w in out["warnings"]) is False, "tally: n 12 is over targetN 10, no directional warning")
raw = p.raw()
rc, out, err = p.run("tally", "rs-cod", "--by", "q3")
check(rc == 0 and out["groups"]["Yes"]["n"] == 8 and out["groups"]["No"]["n"] == 4 and p.raw() == raw,
      "tally --by q3: a breakdown (Yes 8, No 4) and registry untouched")

# synthesize / verify
p.write("syn.json", jload("survey-synthesis.json"))
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("syn.json"))
st = p.study("rs-cod")
check(rc == 0 and out["ok"] and st["status"] == "analysed" and [h["verdict"] for h in st["hypotheses"]] == ["supported"] * 3,
      "synthesize: verdicts merged, verify clean, status analysed")
check(len(st["findings"]) == 3 and st["refill"]["executiveSummary"].startswith("Show the cash"), "synthesize: findings + refill stored")
rc, out, err = p.run("verify", "rs-cod")
check(rc == 0 and out["errors"] == [] and out["warnings"] == [], "verify: clean, no warnings (quote verbatim, counts recomputed)")

# read-only commands
snap = tree_hash(p.dir)
res = []
for args in (["check", "rs-cod"], ["verify", "rs-cod"], ["gaps"], ["gaps", "--role", "courier"], ["seed", "job:pay-cod", "rule:cod-limit"],
             ["list"], ["show", "rs-cod"], ["tally", "rs-cod", "--by", "q3"]):
    res.append(p.run(*args)[0])
check(res == [0] * len(res) and tree_hash(p.dir) == snap,
      "check / verify / gaps / seed / list / show leave the whole project tree byte-identical")

# refill
raw = p.raw()
rc, out, err = p.run("refill", "rs-cod")
check(rc == 2 and p.raw() == raw, "REFUSED refill without --approved (exit 2), nothing written")
rc, out, err = p.run("refill", "rs-cod", "--approved", "--note", "lead signed off")
ui = p.data()["meta"]["userInsights"]
st = p.study("rs-cod")
check(rc == 0 and st["status"] == "applied" and st["gates"][-1]["gate"] == "G-INSIGHT", "refill: status applied, G-INSIGHT appended")
check(ui["quantitative"].startswith("Existing note: 41 deliveries were logged in the pilot week.\n\n8 of 12")
      and ui["quantitative"].endswith("[rs-cod]"), "refill: appended AFTER the existing text, after a blank line, cited [rs-cod]")
check(ui["executiveSummary"].startswith("Existing note: the pilot ran for one week.\n\nShow the cash amount on the first screen. [rs-cod]"),
      "refill: the existing executive summary is intact")
check(ui["researchSummary"] == "Couriers new to the job want the amount before they arrive, and most customers still pay in cash. [rs-cod]",
      "refill: an empty (null) field takes the text with no leading blank line")
bk = p.backups("rs-cod")
check(len(bk) == 1 and os.path.isfile(p.path("memory", "backups", bk[0], "registry.json"))
      and json.load(open(p.path("memory", "backups", bk[0], "registry.json")))["meta"]["userInsights"]["researchSummary"] is None,
      "refill: backed up the registry as it was, under memory/backups/research-<id>-<stamp>/")
raw = p.raw()
rc, out, err = p.run("refill", "rs-cod", "--approved")
check(rc == 0 and out.get("noop") is True and p.raw() == raw and len(p.backups("rs-cod")) == 1,
      "refill is idempotent: the second run is a no-op (registry bytes identical, no new backup)")

# replace in place
syn = jload("survey-synthesis.json")
syn["refill"] = {"executiveSummary": "Show the cash amount first, always."}
p.write("syn2.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("syn2.json"))
check(rc == 0 and p.study("rs-cod")["status"] == "applied", "synthesize again after refill: clean, status stays applied")
rc, out, err = p.run("refill", "rs-cod", "--approved")
ui = p.data()["meta"]["userInsights"]
check(rc == 0 and out["how"]["executiveSummary"] == "replaced" and out["warnings"] == [], "refill with changed text, text still in place: replaced in place, no warning")
check(ui["executiveSummary"] == "Existing note: the pilot ran for one week.\n\nShow the cash amount first, always. [rs-cod]"
      and "on the first screen" not in ui["executiveSummary"], "refill: replaced in place (one citation, old sentence gone, existing text intact)")
check(len(p.backups("rs-cod")) == 2, "refill: a real change makes a second backup")

# edited -> append + warn
d = p.data()
d["meta"]["userInsights"]["executiveSummary"] = d["meta"]["userInsights"]["executiveSummary"].replace("always", "ALWAYS")
p.save(d)
syn["refill"] = {"executiveSummary": "Show the cash amount first, in bold."}
p.write("syn3.json", syn)
p.run("synthesize", "rs-cod", "--file", p.path("syn3.json"))
rc, out, err = p.run("refill", "rs-cod", "--approved")
ui = p.data()["meta"]["userInsights"]
check(rc == 0 and out["how"]["executiveSummary"] == "appended" and any("edited" in w for w in out["warnings"]),
      "refill when someone edited the earlier text: appends and warns")
check("first, ALWAYS. [rs-cod]" in ui["executiveSummary"] and ui["executiveSummary"].endswith("in bold. [rs-cod]")
      and ui["executiveSummary"].startswith("Existing note:"), "refill: the human edit and the older text are left intact")

# ═════════════════════════════════════════════════════════════════════════════
section("2. the interview path")
p = interview_fielding()
st = p.study("rs-handover")
check(st["status"] == "fielding" and st["audience"]["targetN"] == 2, "interview: init/plan/approve/import x2 -> fielding")
guide = p.path("memory", "research", "rs-handover", "instrument", "interview-guide.md")
g = open(guide, encoding="utf-8").read()
check(os.path.isfile(guide) and not os.path.exists(p.path("memory", "research", "rs-handover", "instrument", "survey.md")),
      "interview: interview-guide.md only")
check("/?entry=dispatcher-start&role=dispatcher" in g and "done when: The parcels are confirmed" in g and "probe: What are you looking at" in g,
      "interview guide: the task's prototype link, success and probes")
check([e["participant"] for e in st["evidence"]] == ["P01", "P02"] and st["evidence"][1]["consent"] == "unknown",
      "interview: two transcripts stored with participant + consent")
rc, out, err = p.run("tally", "rs-handover")
check(rc == 1, "REFUSED tally on an interview")
syn = jload("interview-synthesis.json")
syn["findings"][0]["evidence"][1]["quote"] = unicodedata.normalize("NFD", syn["findings"][0]["evidence"][1]["quote"])
check(syn["findings"][0]["evidence"][1]["quote"] != "Tôi luôn mở lại ảnh trước khi bấm xác nhận", "(the Vietnamese quote is NFD, the transcript is NFC)")
p.write("isyn.json", syn)
rc, out, err = p.run("synthesize", "rs-handover", "--file", p.path("isyn.json"))
check(rc == 0 and out["status"] == "analysed", "synthesize (interview): quotes found across a line break and in NFD, status analysed")
rc, out, err = p.run("verify", "rs-handover")
check(rc == 0 and codes(out["warnings"]) == ["W-CONSENT"], "verify: clean; one warning, the participant with consent: unknown")
rc, out, err = p.run("refill", "rs-handover", "--approved")
ui = p.data()["meta"]["userInsights"]
check(rc == 0 and ui["quantitative"].startswith("Existing note") and "[rs-handover]" not in ui["quantitative"],
      "refill (interview): a field the synthesis has no text for is left alone")
check(ui["researchSummary"].endswith("[rs-handover]") and ui["executiveSummary"].startswith("Existing note: the pilot ran"),
      "refill (interview): researchSummary set, executiveSummary appended after the existing one")

# one participant / short quote warnings
p2 = interview_fielding(p2_consent="yes")
one = jload("interview-synthesis.json")
one["findings"][0]["evidence"] = [one["findings"][0]["evidence"][0]]
one["findings"][1]["evidence"][0]["quote"] = "single tap"
p2.write("one.json", one)
rc, out, err = p2.run("synthesize", "rs-handover", "--file", p2.path("one.json"))
check(rc == 0 and "W-ONE-PARTICIPANT" in codes(out["warnings"]) and "W-SHORT-QUOTE" in codes(out["warnings"]),
      "verify warns: a finding resting on one participant, and a quote under 12 characters")

# ═════════════════════════════════════════════════════════════════════════════
section("3. the refusals")
p = Proj()
rc, out, err = p.run("init", "rs-x", "--method", "survey", "--scope", "collect", "--question", "q")
check(rc == 1 and "who it asks" in out["error"] and not p.data()["research"]["studies"],
      "REFUSED init with no role and no segment")
rc, out, err = p.run("init", "rs-x", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier", "--target", "job:not-a-job")
check(rc == 1 and "does not resolve" in out["error"], "REFUSED init with an unresolved target")
rc, out, err = p.run("init", "rs-x", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "astronaut")
check(rc == 1 and "meta.roles" in out["error"], "REFUSED init with a role meta.roles does not declare")
rc, out, err = p.run("init", "rs-x", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier", "--target", "feature:a thing nobody modelled")
check(rc == 0, "init accepts a free-text feature target")
rc, out, err = p.run("init", "rs-x", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
check(rc == 1, "REFUSED init of an id that exists")
rc, out, err = p.run("init", "RS_x", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
check(rc == 2, "REFUSED a malformed study id (exit 2)")
rc, out, err = p.run("init", "rs-i", "--method", "interview", "--scope", "collect", "--question", "q", "--segment", "new dispatchers")
check(rc == 0 and p.study("rs-i")["audience"]["targetN"] == 5, "init: a segment alone is enough; interview targetN defaults to 5")

# approve with check errors
bad = jload("survey-plan.json")
del bad["hypotheses"][0]["refutedIf"]
bad["instrument"]["sections"][1]["questions"][0]["tests"] = []
p.run("init", "rs-bad", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
p.write("bad.json", bad)
p.run("plan", "rs-bad", "--file", p.path("bad.json"))
rc, out, err = p.run("approve", "rs-bad")
check(rc == 1 and "C-HYP-FALSIFIABLE" in codes(out["errors"]) and "C-TESTS" in codes(out["errors"])
      and p.study("rs-bad")["status"] == "draft" and not os.path.exists(p.path("memory", "research", "rs-bad", "instrument")),
      "REFUSED approve with check errors (no refutedIf, a main question testing nothing): still a draft, no files")

# quote not verbatim / opaque / wrong tally count / tamper / drop / failing refill
p = survey_fielding()
syn = jload("survey-synthesis.json")
syn["findings"][0]["evidence"][1]["quote"] = "Customers hand over big notes and I never have change"
p.write("s.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
st = p.study("rs-cod")
check(rc == 1 and "V-QUOTE" in codes(out["errors"]) and st["status"] == "fielding" and len(st["findings"]) == 3,
      "REFUSED a quote that is not verbatim: written so it can be fixed, status NOT analysed")
raw = p.raw()
rc, out, err = p.run("refill", "rs-cod", "--approved")
check(rc == 1 and p.raw() == raw and not os.path.isdir(p.path("memory", "backups")),
      "REFUSED refill with a failing verify: registry untouched, no backup")

open(p.path("call.m4a"), "wb").write(b"\x00\x01fake audio bytes\x02")
rc, out, err = p.run("import", "rs-cod", p.path("call.m4a"), "--kind", "recording", "--consent", "yes", "--participant", "R07")
rec = p.study("rs-cod")["evidence"][-1]
check(rc == 0 and rec["kind"] == "recording" and rec["file"].endswith("e2-call.m4a") and out.get("opaque") is True,
      "import: a recording is stored as an opaque file (hashed, chmod 444, never scanned)")
syn = jload("survey-synthesis.json")
syn["findings"][0]["evidence"][1] = {"evidence": rec["id"], "quote": "Customers hand over big notes and I have no change"}
p.write("s.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
rc, out, err = p.run("verify", "rs-cod")
check(rc == 1 and "V-QUOTE-OPAQUE" in codes(out["errors"]) and "transcript" in " ".join(e["msg"] for e in out["errors"]),
      "REFUSED a quote citing an opaque file (a recording): the message says import a text transcript")

p = survey_fielding()
syn = jload("survey-synthesis.json")
syn["findings"][0]["evidence"][0]["count"] = 7
p.write("s.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
check(rc == 1 and "V-TALLY" in codes(out["errors"]) and p.study("rs-cod")["status"] == "fielding",
      "REFUSED a tally citation with the wrong count (7, tally says 8)")
syn = jload("survey-synthesis.json")
syn["findings"][0]["evidence"][0]["of"] = 14
p.write("s.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
check(rc == 1 and "V-TALLY" in codes(out["errors"]), "REFUSED a tally citation with the wrong 'of' (14, qualified n is 12)")
syn = jload("survey-synthesis.json")
syn["findings"][1]["evidence"][0]["value"] = 3.2
p.write("s.json", syn)
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
check(rc == 1 and "V-TALLY" in codes(out["errors"]), "REFUSED a cited mean that the tally does not round to (3.2 vs 3.9167)")

# tamper
ev = p.study("rs-cod")["evidence"][0]
fp = p.path(*ev["file"].split("/"))
os.chmod(fp, 0o644)
with open(fp, "ab") as f:
    f.write(b"tampered\n")
rc, out, err = p.run("verify", "rs-cod")
check(rc == 1 and any(e["code"] == "V-EVIDENCE" and "sha256" in e["msg"] for e in out["errors"]),
      "REFUSED (verify fails) once a stored file is changed: sha256 mismatch")
rc, out, err = p.run("tally", "rs-cod")
check(rc == 1 and "sha256" in out["error"], "tally refuses a changed file too")

# drop-evidence
p = survey_fielding()
p.write("s.json", jload("survey-synthesis.json"))
rc, out, err = p.run("synthesize", "rs-cod", "--file", p.path("s.json"))
check(rc == 0, "(setup: a clean analysed survey)")
row = p.study("rs-cod")["evidence"][0]
fp = p.path(*row["file"].split("/"))
rc, out, err = p.run("drop-evidence", "rs-cod", "e1")
check(rc == 2, "drop-evidence needs --reason (exit 2)")
rc, out, err = p.run("drop-evidence", "rs-cod", "e1", "--reason", "participant withdrew consent")
row2 = p.study("rs-cod")["evidence"][0]
check(rc == 0 and not os.path.exists(fp) and row2["sha256"] == row["sha256"] and row2["dropped"]["reason"] == "participant withdrew consent"
      and row2["id"] == "e1", "drop-evidence: file deleted, row and hash kept with dropped{at, reason}")
rc, out, err = p.run("verify", "rs-cod")
check(rc == 1 and any("dropped" in e["msg"] for e in out["errors"]), "REFUSED: verify fails the finding that cites dropped evidence")
rc, out, err = p.run("import", "rs-cod", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
check(rc == 1, "the withdrawn participant's file is not re-imported (hash of a dropped row still counts)")
rc, out, err = p.run("refill", "rs-cod", "--approved")
check(rc == 1, "refill refuses after drop-evidence (verify fails)")

# ═════════════════════════════════════════════════════════════════════════════
section("4. files, names, symlinks, PII in text")
check(R.safe_name("../../etc/passwd") == "passwd", "safe_name: directories and .. never survive")
check(".." not in R.safe_name("a..b..csv") and R.safe_name("..") == "file" and R.safe_name("...hidden.txt") == "hidden.txt",
      "safe_name: no '..', no leading dot, never empty")
check(R.safe_name("Phỏng vấn  đợt 1.TXT") == "Phong-van-dot-1.txt", "safe_name: Vietnamese -> ASCII, spaces -> '-', extension lowercased")

p = interview_fielding()
odd = p.path("Ghi chú   ../phỏng vấn.txt".replace("/", "_"))
open(odd, "w", encoding="utf-8").write("Notes for P03 - the dispatcher said the queue reloads and loses the place.\n")
rc, out, err = p.run("import", "rs-handover", odd, "--kind", "notes", "--consent", "yes", "--participant", "P03")
f = p.study("rs-handover")["evidence"][-1]["file"]
check(rc == 0 and f.startswith("memory/research/rs-handover/evidence/e3-") and ".." not in f and f.isascii()
      and os.path.dirname(f) == "memory/research/rs-handover/evidence", "import: a hostile or accented file name is stored as a safe ASCII name inside evidence/")
link = p.path("link.txt")
os.symlink(p.path("transcript-p01.txt"), link)
rc, out, err = p.run("import", "rs-handover", link, "--kind", "notes", "--consent", "yes")
check(rc == 1 and "symlink" in out["error"], "REFUSED a symlink as the source file")
os.makedirs(p.path("memory", "research", "rs-handover", "evidence"), exist_ok=True)
phone = p.path("notes-phone.txt")
open(phone, "w", encoding="utf-8").write("Call back on 0912 345 678 about the queue.\n")
rc, out, err = p.run("import", "rs-handover", phone, "--kind", "notes", "--consent", "yes", "--participant", "P04")
check(rc == 0 and out["warnings"], "import: text evidence is scanned; a phone number prints as a warning, not a refusal")
rc, out, err = p.run("show", "rs-handover")
check(rc == 0 and len(out["study"]["evidence"]) == 4, "show: the whole study as JSON")

# ═════════════════════════════════════════════════════════════════════════════
section("5. Vietnamese, NFC, CRLF and semicolons")
p = Proj()
vi_plan = jload("survey-plan.json")
vi_q3 = "Bạn có cần thấy số tiền thu hộ trước khi đến cửa không?"
vi_plan["instrument"]["sections"][1]["questions"][0]["text"] = unicodedata.normalize("NFC", vi_q3)
vi_plan["instrument"]["sections"][1]["questions"][0]["options"] = ["Có", "Không"]
p.run("init", "rs-vi", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
p.write("vi.json", vi_plan)
p.run("plan", "rs-vi", "--file", p.path("vi.json"))
rc, out, err = p.run("check", "rs-vi")
check(rc == 0, "a Vietnamese question set checks clean (no errors)")
rc, out, err = p.run("approve", "rs-vi", *SKIP)
header = ["Dấu thời gian", "q1", "q2", unicodedata.normalize("NFD", vi_q3)]
rows = [["2026/11/02", "Yes", "Under 1 year", "Có"], ["2026/11/02", "Yes", "1 to 3 years", "Không"],
        ["2026/11/02", "Yes", "Under 1 year", "có"], ["2026/11/02", "No", "Under 1 year", "Có"]]
buf = io.StringIO()
w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
w.writerow(header)
w.writerows(rows)
open(p.path("vi.csv"), "wb").write(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))
rc, out, err = p.run("import", "rs-vi", p.path("vi.csv"), "--kind", "responses", "--consent", "yes")
check(rc == 0 and {m["question"]: m["by"] for m in out["matched"]} == {"q1": "id", "q2": "id", "q3": "text"},
      "import: semicolon + CRLF + BOM; id columns match by id, an NFD Vietnamese header matches the NFC question by text")
rc, out, err = p.run("tally", "rs-vi")
t = p.study("rs-vi")["tally"]
check(rc == 0 and t["n"] == 3 and t["excluded"] == 1 and t["byQuestion"]["q3"]["counts"] == {"Có": 2, "Không": 1},
      "tally: Vietnamese options counted case-insensitively ('có' = 'Có'), the screener excluded one row")
check(R.split_multi("Cash, counted at the door, E-wallet", {"options": ["Cash", "E-wallet", "Cash, counted at the door"]})
      == ["Cash, counted at the door", "E-wallet"] and R.split_multi("a; b", {"options": ["a", "b"]}) == ["a", "b"]
      and R.split_multi("Cash, Other thing", {"options": ["Cash"]}) == ["Cash", "(other)"],
      "split_multi: longest option first, ';' splits, an unknown choice is '(other)'")

# ═════════════════════════════════════════════════════════════════════════════
section("6. check: errors and warnings")
p = Proj()
p.run("init", "rs-w", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
w = jload("survey-plan.json")
qs = w["instrument"]["sections"][1]["questions"]
qs[3]["text"] = "Would you like the amount first and a total?"
qs[4]["text"] = "Bạn có thấy màn hình này tốt không?"
qs[0]["text"] = "Bạn sẽ dùng nút này chứ?"
qs[1]["text"] = "Don't you think counting is hard?"
p.write("w.json", w)
p.run("plan", "rs-w", "--file", p.path("w.json"))
rc, out, err = p.run("check", "rs-w")
check(rc == 0 and out["errors"] == [], "heuristics are warnings, never errors")
check({"W-HYPOTHETICAL", "W-LEADING", "W-DOUBLE"} <= set(codes(out["warnings"])),
      "warnings (EN + VI): hypothetical, leading, double-barrelled -> %s" % codes(out["warnings"]))

p.run("init", "rs-e", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
e = jload("survey-plan.json")
e["instrument"]["intro"] = ""
e["instrument"]["sections"][1]["questions"][0]["tests"] = ["h9"]
e["instrument"]["sections"][1]["questions"][1]["scale"] = {"min": 5, "max": 5}
e["instrument"]["sections"][0]["questions"][0]["qualifies"] = ["Maybe"]
e["instrument"]["sections"][1]["questions"][2]["options"] = ["Cash"]
e["instrument"]["sections"][1]["questions"][3]["id"] = "q3"
e["instrument"]["sections"][1]["questions"][4]["type"] = "essay"
e["hypotheses"][2]["targets"] = [{"kind": "rule", "id": "no-such-rule"}]
p.write("e.json", e)
p.run("plan", "rs-e", "--file", p.path("e.json"))
rc, out, err = p.run("check", "rs-e")
need = {"C-INTRO", "C-TESTS", "C-SCALE", "C-QUALIFIES", "C-OPTIONS", "C-ID", "C-TYPE", "C-TARGET"}
check(rc == 1 and need <= set(codes(out["errors"])), "check errors: %s" % sorted(need & set(codes(out["errors"]))))

p.run("init", "rs-s", "--method", "survey", "--scope", "collect", "--question", "q", "--segment", "rural couriers")
ns = jload("survey-plan.json")
ns["instrument"]["sections"] = ns["instrument"]["sections"][1:]
p.write("ns.json", ns)
p.run("plan", "rs-s", "--file", p.path("ns.json"))
rc, out, err = p.run("check", "rs-s")
check(rc == 1 and "C-SCREENER" in codes(out["errors"]), "check error: the audience names a segment but there is no screener")

p.run("init", "rs-t", "--method", "interview", "--scope", "collect", "--question", "q", "--role", "dispatcher")
it = jload("interview-plan.json")
it["instrument"]["sections"] = it["instrument"]["sections"][1:]
tk = it["instrument"]["sections"][0]["questions"][0]["task"]
tk.update({"screen": "nowhere", "role": "astronaut", "entry": "no-entry"})
del tk["success"]
p.write("it.json", it)
p.run("plan", "rs-t", "--file", p.path("it.json"))
rc, out, err = p.run("check", "rs-t")
msgs = " ".join(x["msg"] for x in out["errors"])
check(rc == 1 and "C-WARMUP" in codes(out["errors"]) and "screen 'nowhere'" in msgs and "role 'astronaut'" in msgs
      and "entry 'no-entry'" in msgs and "success" in msgs, "check errors (interview): no warmup; a task with an unknown screen, role, entry and no success")

# ═════════════════════════════════════════════════════════════════════════════
section("7. plan on an approved study, gaps, seed")
p = Proj()
p.run("init", "rs-cod", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier", "--target", "job:pay-cod")
p.run("plan", "rs-cod", "--file", os.path.join(FIX, "survey-plan.json"))
p.run("approve", "rs-cod", *SKIP)
smd = p.path("memory", "research", "rs-cod", "instrument", "survey.md")
check("Approved at G-STUDY" in open(smd, encoding="utf-8").read(), "(setup: approved)")
rc, out, err = p.run("plan", "rs-cod", "--file", os.path.join(FIX, "survey-plan.json"))
st = p.study("rs-cod")
check(rc == 0 and out["withdrawn"] and st["status"] == "draft" and st["gates"][0].get("withdrawnAt"),
      "plan on an approved study: back to draft, the G-STUDY gate is marked withdrawn (kept for the record)")
check("DRAFT — not approved" in open(smd, encoding="utf-8").read(), "plan on an approved study: the instrument files are re-headed DRAFT")
rc, out, err = p.run("export", "rs-cod")
check(rc == 0 and "DRAFT — not approved" in open(smd, encoding="utf-8").read(), "export of a draft is headed 'DRAFT — not approved'")

p = Proj()
rc, out, err = p.run("gaps")
rows = out["gaps"]
ids = [(r["kind"], r["id"]) for r in rows]
check(rc == 0 and ids[0] == ("rule", "cod-limit"), "gaps: the rule with an open question + ASSUMPTION + an assumed parameter ranks first")
why = {(r["kind"], r["id"]): r["why"] for r in rows}
check("open question" in why[("rule", "cod-limit")] and "ASSUMPTION" in why[("rule", "cod-limit")] and "'limit' is assumed" in why[("rule", "cod-limit")],
      "gaps: names the open question, the ASSUMPTION and the assumed param (sourced params are not gaps)")
check("warn-at" not in why[("rule", "cod-limit")] and ("rule", "handover-state") not in ids, "gaps: a settled rule and a sourced param are not gaps")
check("gap:" in why[("job", "pay-cod")] and ids.index(("job", "pay-cod")) < ids.index(("job", "confirm-handover")) < ids.index(("job", "report-failure")),
      "gaps: jobs with a gap, then uncited jobs, P1 first")
check(("story", "collect-cash") in ids and not any("Refunds" in r["why"] for r in rows), "gaps: an open coverage warning counts (on its story), a resolved one does not")
rc, out, err = p.run("gaps", "--role", "dispatcher")
dids = [(r["kind"], r["id"]) for r in out["gaps"]]
check(("job", "confirm-handover") in dids and ("job", "pay-cod") not in dids and ("rule", "cod-limit") in dids,
      "gaps --role dispatcher: courier-only jobs drop out, role-less rows stay")
d = p.data()
d["research"] = {"populated": True, "studies": [{"id": "rs-old", "method": "interview", "status": "analysed", "audience": {"roles": ["courier"]},
                                                  "targets": [{"kind": "job", "id": "report-failure"}],
                                                  "hypotheses": [{"id": "h1", "statement": "Couriers report failures at once", "verdict": "inconclusive",
                                                                  "targets": [{"kind": "job", "id": "report-failure"}]}],
                                                  "findings": [{"id": "f1", "targets": [{"kind": "job", "id": "confirm-handover"}]}]}]}
p.save(d)
rc, out, err = p.run("gaps")
why = {(r["kind"], r["id"]): r["why"] for r in out["gaps"]}
check("inconclusive" in why[("job", "report-failure")] and "no research finding cites it" not in why.get(("job", "confirm-handover"), ""),
      "gaps: an inconclusive hypothesis is a gap again; a job a finding cites is no longer 'uncited'")

rc, out, err = p.run("seed", "job:pay-cod", "screen:handover")
paths = [l["path"] for l in out["links"]]
s0 = out["seeds"][0]
check(rc == 0 and s0["job"]["when"] == "the customer opens the door" and s0["job"]["so"] == "I do not ask them twice"
      and [s["id"] for s in s0["stories"]] == ["collect-cash"] and [r["id"] for r in s0["rules"]] == ["cod-limit"],
      "seed job: when/want/so, the stories on its screens, the rules shown there")
check("/?role=courier" in paths and "/?entry=cod-demo&role=courier" in paths and "/?entry=dispatcher-start&role=dispatcher" in paths
      and "/?role=dispatcher" in paths, "seed: prototype links /?role=<r> and /?entry=<id>&role=<r> from meta.demo.entries")
rc, out, err = p.run("seed", "story:Collect cash on delivery", "rule:handover-state", "component:pay-button", "feature:anything at all")
check(rc == 0 and len(out["seeds"]) == 4, "seed: a story (by title), a rule, a component and a free-text feature all resolve")
rc, out, err = p.run("seed", "job:nope")
check(rc == 1, "REFUSED seed of an unresolved target")
rc, out, err = p.run("seed", "job")
check(rc == 2, "seed: a malformed target is a usage error (exit 2)")
rc, txt, err = p.text("gaps")
check(rc == 0 and "rule:cod-limit" in txt, "human output (no --json) prints a readable list")

# ═════════════════════════════════════════════════════════════════════════════
section("8. scope and setup")
SETUP_MARK = "SETUP-MARK-36 Typeform, panel of 40 couriers, results in the team drive"
p = Proj()
rc, out, err = p.run("init", "rs-i1", "--method", "survey", "--question", "q", "--role", "courier")
check(rc == 2, "init without --scope is a usage error (exit 2)")
rc, out, err = p.run("init", "rs-i1", "--method", "survey", "--scope", "somewhere", "--question", "q", "--role", "courier")
check(rc == 2, "init with a scope that is neither instrument nor collect is a usage error (exit 2)")
rc, out, err = p.run("init", "rs-i1", "--method", "survey", "--scope", "instrument", "--setup", SETUP_MARK,
                     "--question", "q", "--role", "courier", "--target", "job:pay-cod")
st = p.study("rs-i1")
check(rc == 0 and st["scope"] == "instrument" and st["setup"] == SETUP_MARK, "init --scope instrument --setup: both stored on the study")
rc, out, err = p.run("init", "rs-c1", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
check(rc == 0 and p.study("rs-c1")["scope"] == "collect" and p.study("rs-c1")["setup"] == "", "init --scope collect without --setup: setup is empty")
p.run("plan", "rs-i1", "--file", os.path.join(FIX, "survey-plan.json"))
rc, out, err = p.run("approve", "rs-i1", *SKIP)
check(rc == 0 and p.study("rs-i1")["status"] == "approved", "an instrument study reaches approved")
rc, out, err = p.run("import", "rs-i1", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
check(rc == 1 and "scope" in out.get("error", "") and "scope rs-i1 --scope collect" in out["error"]
      and not p.study("rs-i1")["evidence"] and not os.path.exists(p.path("memory", "research", "rs-i1", "evidence")),
      "REFUSED import into an instrument study; the message names the `scope` command; nothing stored")
exported = b"".join(open(p.path("memory", "research", "rs-i1", "instrument", n), "rb").read()
                    for n in ("survey.md", "responses-template.csv"))
p.run("export", "rs-i1")
exported2 = b"".join(open(p.path("memory", "research", "rs-i1", "instrument", n), "rb").read()
                     for n in ("survey.md", "responses-template.csv"))
check(exported == exported2 and b"SETUP-MARK" not in exported and b"Typeform" not in exported,
      "exported instrument files are deterministic and do not contain the setup")
rc, out, err = p.run("gaps")
check(rc == 0 and "rs-i1" not in json.dumps(out) , "gaps: an approved instrument study is not listed as unfinished work")
d = p.data()
d["research"]["studies"][0]["hypotheses"][0]["verdict"] = "inconclusive"
p.save(d)
rc, out, err = p.run("gaps")
check("inconclusive" not in json.dumps(out["gaps"]), "gaps: an inconclusive verdict in an instrument study is not a gap (no result was due)")
rc, out, err = p.run("list")
row = next(r for r in out["studies"] if r["id"] == "rs-i1")
check(rc == 0 and row["scope"] == "instrument" and next(r for r in out["studies"] if r["id"] == "rs-c1")["scope"] == "collect",
      "list --json carries each study's scope")
rc, txt, err = p.text("list")
check("instrument" in txt and "collect" in txt, "list (text) shows the scope")

gates = p.study("rs-i1")["gates"]
raw_status = p.study("rs-i1")["status"]
rc, out, err = p.run("scope", "rs-i1")
check(rc == 2, "scope with neither --scope nor --setup is a usage error (exit 2)")
rc, out, err = p.run("scope", "rs-i1", "--scope", "collect")
st = p.study("rs-i1")
check(rc == 0 and st["scope"] == "collect" and st["setup"] == SETUP_MARK and st["gates"] == gates and st["status"] == raw_status,
      "scope --scope collect: changed, setup kept, no gate written, status untouched")
rc, out, err = p.run("scope", "rs-i1", "--setup", "now: Google Forms")
check(rc == 0 and p.study("rs-i1")["setup"] == "now: Google Forms" and p.study("rs-i1")["scope"] == "collect",
      "scope --setup alone changes only the setup")
rc, out, err = p.run("import", "rs-i1", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
check(rc == 0 and len(p.study("rs-i1")["evidence"]) == 1, "after `scope --scope collect` the import goes through")
rc, out, err = p.run("scope", "rs-i1", "--scope", "instrument")
rc2, out2, err2 = p.run("scope", "rs-nope", "--scope", "collect")
check(rc == 0 and rc2 == 2, "scope can go back to instrument at any status; an unknown study is exit 2")

# a study from before scope existed behaves as collect
p = Proj()
p.run("init", "rs-old", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
p.run("plan", "rs-old", "--file", os.path.join(FIX, "survey-plan.json"))
p.run("approve", "rs-old", *SKIP)
d = p.data()
for k in ("scope", "setup"):
    del d["research"]["studies"][0][k]
p.save(d)
rc, out, err = p.run("import", "rs-old", CSV, "--kind", "responses", "--consent", "yes", "--drop-columns", "Email Address")
check(rc == 0 and "scope" not in p.study("rs-old"), "a study with no `scope` key behaves as collect: import works, no migration writes the key")
rc, out, err = p.run("list")
check(out["studies"][0]["scope"] == "collect", "list reports a study with no scope key as collect")
rc, out, err = p.run("check", "rs-old")
check(rc == 0, "check passes on a study with no scope key")
d = p.data()
d["research"]["studies"][0]["scope"] = "somewhere"
p.save(d)
rc, out, err = p.run("check", "rs-old")
check(rc == 1 and "C-SCOPE" in codes(out["errors"]), "check error C-SCOPE: a stored scope that is neither instrument nor collect")

# ═════════════════════════════════════════════════════════════════════════════
section("9. standard metric templates")
SUS_WORDING = ["I think that I would like to use this system frequently.",
               "I found the system unnecessarily complex.",
               "I thought the system was easy to use.",
               "I think that I would need the support of a technical person to be able to use this system.",
               "I found the various functions in this system were well integrated.",
               "I thought there was too much inconsistency in this system.",
               "I would imagine that most people would learn to use this system very quickly.",
               "I found the system very cumbersome to use.",
               "I felt very confident using the system.",
               "I needed to learn a lot of things before I could get going with this system."]


def template_plan(extra=None, lang="en"):
    plan = jload("survey-plan.json")
    plan["instrument"]["lang"] = lang
    qs = [{"id": "q9", "template": "ces", "subject": "settling cash at the door", "tests": ["h2"]},
          {"id": "q10", "template": "seq", "tests": ["h2"]},
          {"id": "q11", "template": "csat", "subject": "the cash screen", "tests": ["h2"]},
          {"id": "q12", "template": "nps", "tests": ["h2"]},
          {"id": "q13", "template": "sus", "tests": ["h2"]}]
    plan["instrument"]["sections"].append({"title": "Ratings", "purpose": "main", "questions": qs + (extra or [])})
    return plan


def template_study(plan=None, lang="en"):
    p = Proj()
    p.run("init", "rs-tpl", "--method", "survey", "--scope", "collect", "--question", "q", "--role", "courier")
    p.write("tpl.json", plan or template_plan(lang=lang))
    rc, out, err = p.run("plan", "rs-tpl", "--file", p.path("tpl.json"))
    return p, rc, out, err


p, rc, out, err = template_study()
inst = p.study("rs-tpl")["instrument"]
byid = {q["id"]: q for s in inst["sections"] for q in s["questions"]}
check(rc == 0 and all(i in byid for i in ["q9", "q10", "q11", "q12"] + ["q13-%d" % n for n in range(1, 11)]) and "q13" not in byid,
      "plan expands ces/seq/csat/nps to one question each and sus to q13-1 .. q13-10")
check(byid["q9"]["text"] == "Settling cash at the door was easy to handle." and byid["q9"]["type"] == "scale"
      and byid["q9"]["scale"] == {"min": 1, "max": 7, "minLabel": "Strongly disagree", "maxLabel": "Strongly agree"}
      and byid["q9"]["template"] == "ces" and byid["q9"]["tests"] == ["h2"], "ces: wording from the subject (capitalised), scale 1-7, template kept")
check(byid["q10"]["text"] == "Overall, how difficult or easy was this task to complete?"
      and byid["q10"]["scale"] == {"min": 1, "max": 7, "minLabel": "Very difficult", "maxLabel": "Very easy"}, "seq: standard wording and 1-7 labels")
check(byid["q11"]["text"] == "How satisfied are you with the cash screen?"
      and byid["q11"]["scale"] == {"min": 1, "max": 5, "minLabel": "Very dissatisfied", "maxLabel": "Very satisfied"}, "csat: subject in the wording, 1-5 labels")
check(byid["q12"]["text"] == "How likely are you to recommend this to a friend or colleague?"
      and byid["q12"]["scale"] == {"min": 0, "max": 10, "minLabel": "Not at all likely", "maxLabel": "Extremely likely"},
      "nps: default subject 'this', 0-10 labels")
check([byid["q13-%d" % n]["text"] for n in range(1, 11)] == SUS_WORDING
      and all(byid["q13-%d" % n]["scale"] == {"min": 1, "max": 5, "minLabel": "Strongly disagree", "maxLabel": "Strongly agree"}
              and byid["q13-%d" % n]["template"] == "sus" and byid["q13-%d" % n]["templateItem"] == n for n in range(1, 11)),
      "sus: the ten Brooke items in order, scale 1-5, each keeps template + templateItem")
rc, out, err = p.run("check", "rs-tpl")
check(rc == 0 and "W-TEMPLATE-TEXT" not in codes(out["warnings"]) and "W-DOUBLE" not in codes(out["warnings"])
      and not [w for w in out["warnings"] if w["where"].endswith(("q12", "q13-2", "q9"))],
      "check: standard wording draws no W-TEMPLATE-TEXT, and template questions are exempt from the wording heuristics (nps text holds ' or ')")

# the wording heuristics DO fire on a hand-written question of the same shape (so the exemption is real)
hand = template_plan()
hand["instrument"]["sections"][-1]["questions"].append({"id": "q14", "text": "Would you recommend this to a friend or colleague?",
                                                       "tests": ["h2"], "type": "text"})
p2, rc, out, err = template_study(hand)
rc, out, err = p2.run("check", "rs-tpl")
check({"W-HYPOTHETICAL", "W-DOUBLE"} <= set(codes(out["warnings"])), "(control) a hand-written 'would you … or …' still warns")

# re-planning an already expanded instrument is stable
again = p.study("rs-tpl")["instrument"]
p.write("again.json", {"instrument": again})
rc, out, err = p.run("plan", "rs-tpl", "--file", p.path("again.json"))
check(rc == 0 and p.study("rs-tpl")["instrument"] == again, "plan of an already expanded instrument leaves it unchanged (no q13-1-1)")

# translated wording, unknown template, tests rule, bad entries
vi = template_plan(lang="vi")
vi["instrument"]["sections"][-1]["questions"][0]["text"] = "Việc thu tiền tại cửa rất dễ xử lý."
pv, rc, out, err = template_study(vi)
rc2, out2, err2 = pv.run("check", "rs-tpl")
tw = [w for w in out2["warnings"] if w["code"] == "W-TEMPLATE-TEXT"]
check(rc == 0 and rc2 == 0 and len(tw) == 1 and tw[0]["where"].endswith("q9") and pv.study("rs-tpl")["instrument"]["sections"][-1]["questions"][0]["text"] == "Việc thu tiền tại cửa rất dễ xử lý.",
      "lang vi + a translated `text`: kept, and check warns W-TEMPLATE-TEXT for that question only (not validated)")
en_text = template_plan()
en_text["instrument"]["sections"][-1]["questions"][0]["text"] = "Settling was a breeze."
pe, rc, out, err = template_study(en_text)
check(rc == 1 and "lang" in out.get("error", ""), "REFUSED a `text` override while lang is en (it is for a translation)")
bad = template_plan(extra=[{"id": "q15", "template": "foo", "tests": ["h2"]}])
pb_, rc, out, err = template_study(bad)
rc2, out2, err2 = pb_.run("check", "rs-tpl")
check(rc == 0 and rc2 == 1 and "C-TEMPLATE" in codes(out2["errors"]), "an unknown template is stored as written and `check` reports C-TEMPLATE")
rc3, out3, err3 = pb_.run("approve", "rs-tpl", *SKIP)
check(rc3 == 1 and pb_.study("rs-tpl")["status"] == "draft", "REFUSED approve while a template is unknown")
nt = template_plan()
nt["instrument"]["sections"][-1]["questions"][3]["tests"] = []
pn, rc, out, err = template_study(nt)
rc2, out2, err2 = pn.run("check", "rs-tpl")
check(rc2 == 1 and any(e["code"] == "C-TESTS" and e["where"].endswith("q12") for e in out2["errors"]),
      "a template question in a main section needs `tests` like any other main question")
sc = template_plan()
sc["instrument"]["sections"][-1]["questions"][1]["subject"] = "the task"
ps, rc, out, err = template_study(sc)
check(rc == 1 and "subject" in out.get("error", ""), "REFUSED a subject on seq (its wording is fixed)")
d = p.data()
d["research"]["studies"][0]["instrument"]["sections"][-1]["questions"][0]["scale"]["max"] = 5
p.save(d)
rc, out, err = p.run("check", "rs-tpl")
check(rc == 1 and "C-TEMPLATE" in codes(out["errors"]), "check error: a template question whose scale was changed (the score would be wrong)")

# scores, against values worked by hand
HEAD = ["q1", "q2", "q9", "q10", "q11", "q12"] + ["q13-%d" % n for n in range(1, 11)]
BEST = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
ROWS = [["Yes", "Under 1 year", 7, 7, 5, 10] + [3] * 10,                        # SUS all 3s            -> 50
        ["Yes", "Under 1 year", 6, 5, 4, 9] + BEST,                              # SUS best case         -> 100
        ["Yes", "Under 1 year", 5, 6, 3, 9] + [3] * 9 + [""],                    # item 10 missing       -> not scored
        ["Yes", "1 to 3 years", 4, 3, 3, 8] + [4, 2, 4, 2, 4, 2, 4, 2, 4, 2],    # odd 4 -> 3 x5, even 2 -> 3 x5 = 30 -> 75
        ["Yes", "1 to 3 years", 2, 4, 1, 3] + [""] * 10]                         # no SUS at all         -> not scored
buf = io.StringIO()
w = csv.writer(buf, lineterminator="\n")
w.writerow(HEAD)
w.writerows(ROWS)
p, rc, out, err = template_study()
open(p.path("scores.csv"), "w", encoding="utf-8").write(buf.getvalue())
p.run("approve", "rs-tpl", *SKIP)
rc, out, err = p.run("import", "rs-tpl", p.path("scores.csv"), "--kind", "responses", "--consent", "yes")
check(rc == 0 and len(out["matched"]) == 16, "import: the 16 score columns match the question ids (including q13-1 .. q13-10)")
rc, out, err = p.run("tally", "rs-tpl")
bq = p.study("rs-tpl")["tally"]["byQuestion"]
# CES [7,6,5,4,2]: mean 24/5 = 4.8; 5-7 are 7,6,5 = 3 of 5 = 60 %
check(rc == 0 and bq["q9"]["score"] == {"metric": "ces", "value": 4.8, "pct": 60.0, "n": 5}, "tally: CES [7,6,5,4,2] -> mean 4.8, 60% answering 5-7")
# SEQ [7,5,6,3,4]: 25/5 = 5.0
check(bq["q10"]["score"] == {"metric": "seq", "value": 5.0, "n": 5}, "tally: SEQ [7,5,6,3,4] -> mean 5.0")
# CSAT [5,4,3,3,1]: 4 or 5 are 5,4 = 2 of 5 = 40 %
check(bq["q11"]["score"] == {"metric": "csat", "value": 40.0, "n": 5}, "tally: CSAT [5,4,3,3,1] -> 40% answering 4 or 5")
# NPS [10,9,9,8,3]: promoters 10,9,9 = 60 %, detractors (0-6) 3 = 20 % -> 40
check(bq["q12"]["score"] == {"metric": "nps", "value": 40, "n": 5} and isinstance(bq["q12"]["score"]["value"], int),
      "tally: NPS [10,9,9,8,3] -> 60% promoters - 20% detractors = 40 (an integer)")
# SUS: all 3s = (10 + 10) x 2.5 = 50 ; best case = (20 + 20) x 2.5 = 100 ; [4,2,...] = (15 + 15) x 2.5 = 75 ; two incomplete respondents left out
sus_one = lambda a: R.sus_respondent(a)
check(sus_one([3] * 10) == 50 and sus_one(BEST) == 100 and sus_one([4, 2] * 5) == 75 and sus_one([3] * 9 + [None]) is None
      and sus_one([1, 5] * 5) == 0, "sus_respondent: all 3s = 50, best case = 100, [4,2,..] = 75, worst case = 0, an incomplete set = None")
check(bq["q13"]["score"] == {"metric": "sus", "value": 75.0, "n": 3} and bq["q13"]["n"] == 3 and bq["q13"]["type"] == "sus",
      "tally: SUS over 3 complete respondents (50, 100, 75) -> mean 75, n 3 (under the base id q13)")
check(bq["q13-1"]["n"] == 4 and "score" not in bq["q13-1"] and bq["q13-1"]["type"] == "scale", "tally: each sus item is still an ordinary scale question (n 4, no score)")
check("score" not in bq.get("q1", {}) and "score" not in bq.get("q2", {}), "tally: ordinary questions carry no score")

# verify: a correct citation of every score is clean; a wrong one fails
syn = {"verdicts": {"h1": {"verdict": "inconclusive", "why": "not asked"}, "h2": {"verdict": "inconclusive", "why": "n is 5"},
                    "h3": {"verdict": "inconclusive", "why": "not asked"}},
       "findings": [{"id": "f1", "text": "Settling cash is rated moderately easy.", "hypotheses": ["h2"],
                     "evidence": [{"tally": "q9", "stat": "ces", "value": 4.8, "of": 5},
                                  {"tally": "q9", "stat": "ces", "value": 4.8, "pct": 60, "of": 5},
                                  {"tally": "q10", "stat": "seq", "value": 5.0, "of": 5},
                                  {"tally": "q11", "stat": "csat", "value": 40, "of": 5},
                                  {"tally": "q12", "stat": "nps", "value": 40, "of": 5},
                                  {"tally": "q13", "stat": "sus", "value": 75, "of": 3}]}],
       "refill": {"quantitative": "CES 4.8, NPS 40 and SUS 75 (n 3 complete respondents)."}}
p.write("syn.json", syn)
rc, out, err = p.run("synthesize", "rs-tpl", "--file", p.path("syn.json"))
check(rc == 0 and out["ok"] and p.study("rs-tpl")["status"] == "analysed" and "W-NUMBER" not in codes(out["warnings"]),
      "synthesize: all six score citations verify (value at the cited precision), and the refill numbers (4.8, 40, 75, 3) count as known")
syn_n = json.loads(json.dumps(syn))
syn_n["refill"]["quantitative"] = "SUS 76 from 3 respondents."
p.write("syn_n.json", syn_n)
rc, out, err = p.run("synthesize", "rs-tpl", "--file", p.path("syn_n.json"))
check(rc == 0 and any(w["code"] == "W-NUMBER" and "76" in w["msg"] for w in out["warnings"]), "refill: a number that is no score or count (76) still warns W-NUMBER")


def wrong(ev, why):
    s = json.loads(json.dumps(syn))
    s["findings"][0]["evidence"] = [ev]
    p.write("w.json", s)
    rc, out, err = p.run("synthesize", "rs-tpl", "--file", p.path("w.json"))
    check(rc == 1 and "V-TALLY" in codes(out["errors"]), "REFUSED " + why)


wrong({"tally": "q9", "stat": "ces", "value": 4.9, "of": 5}, "a CES citation off by a tenth (4.9 vs 4.8)")
wrong({"tally": "q9", "stat": "ces", "value": 4.8, "pct": 80, "of": 5}, "a CES percent that is wrong (80 vs 60)")
wrong({"tally": "q11", "stat": "csat", "value": 60, "of": 5}, "a CSAT citation of 60 (the tally says 40)")
wrong({"tally": "q12", "stat": "nps", "value": 41, "of": 5}, "an NPS citation of 41 (the tally says 40)")
wrong({"tally": "q13", "stat": "sus", "value": 75, "of": 5}, "a SUS citation with of=5 (3 respondents were complete)")
wrong({"tally": "q13", "stat": "sus", "value": 70, "of": 3}, "a SUS citation of 70 (the tally says 75)")
wrong({"tally": "q11", "stat": "nps", "value": 40, "of": 5}, "a citation naming the wrong metric for the question (nps on a csat question)")
wrong({"tally": "q3", "stat": "ces", "value": 4.8, "of": 5}, "a score citation of a question that has none")

# a template question in an interview: in the guide, never scored
iv = jload("interview-plan.json")
iv["instrument"]["sections"][2]["questions"].append({"id": "q4", "template": "seq", "tests": ["h1"]})
p = Proj()
p.run("init", "rs-handover", "--method", "interview", "--scope", "collect", "--question", "q", "--role", "dispatcher",
      "--target", "screen:handover", "--target", "job:confirm-handover")
p.write("iv.json", iv)
rc, out, err = p.run("plan", "rs-handover", "--file", p.path("iv.json"))
rc2, out2, err2 = p.run("approve", "rs-handover", *SKIP)
guide = open(p.path("memory", "research", "rs-handover", "instrument", "interview-guide.md"), encoding="utf-8").read()
rc3, out3, err3 = p.run("tally", "rs-handover")
check(rc == 0 and rc2 == 0 and "Overall, how difficult or easy was this task to complete?" in guide and rc3 == 1,
      "interview: a template question is expanded into the guide, and tally (the only scorer) is refused for an interview")

# ═════════════════════════════════════════════════════════════════════════════
section("10. the independent bias review")
MARKS = {"title": "TITLE-MARK-31", "question": "QUESTION-MARK-32", "hyp": "HYP-MARK-33", "thresh": "THRESH-MARK-34",
         "target": "TARGET-MARK-35", "setup": "SETUP-MARK-36", "section": "SECTION-TITLE-MARK-37", "segment": "SEGMENT-MARK-38",
         "intro": "INTRO-MARK-39", "consent": "CONSENT-MARK-40", "closing": "CLOSING-MARK-41", "refuted": "REFUTED-MARK-42"}


def marked_plan():
    plan = jload("survey-plan.json")
    for h in plan["hypotheses"]:
        h["statement"] += " " + MARKS["hyp"]
        h["supportedIf"] += " " + MARKS["thresh"]
        h["refutedIf"] += " " + MARKS["refuted"]
    plan["instrument"]["intro"] += " " + MARKS["intro"]
    plan["instrument"]["consent"] += " " + MARKS["consent"]
    plan["instrument"]["closing"] += " " + MARKS["closing"]
    for s in plan["instrument"]["sections"]:
        s["title"] += " " + MARKS["section"]
    return plan


def review_project():
    p = Proj()
    p.run("init", "rs-rev", "--method", "survey", "--scope", "collect", "--setup", MARKS["setup"], "--title", MARKS["title"],
          "--question", MARKS["question"], "--segment", MARKS["segment"], "--role", "courier", "--target", "feature:" + MARKS["target"])
    p.write("plan.json", marked_plan())
    assert p.run("plan", "rs-rev", "--file", p.path("plan.json"))[0] == 0
    return p


BR = ("memory", "research", "rs-rev", "instrument", "bias-review.md")


def rows_for(items, overrides=None, evidence="\"quoted words\""):
    ov = overrides or {}
    return "\n".join("%s · %s · %s" % (i, ov.get(i, "yes"), evidence) for i in items) + "\n"


p = review_project()
snap = p.raw()
rc, out, err = p.run("review-plan", "rs-rev")
body = open(p.path(*BR), "rb").read()
items = out["items"]
check(rc == 0 and out["file"] == "memory/research/rs-rev/instrument/bias-review.md" and p.raw() == snap,
      "review-plan: writes bias-review.md and leaves the registry untouched")
rc2, out2, err2 = p.run("review-plan", "rs-rev")
check(rc2 == 0 and open(p.path(*BR), "rb").read() == body, "bias-review.md is byte-identical across two runs")
p_other = review_project()
p_other.run("review-plan", "rs-rev")
check(open(p_other.path(*BR), "rb").read() == body, "bias-review.md is byte-identical across two separate projects with the same instrument")
text = body.decode("utf-8")
leaks = [name for name, mark in MARKS.items() if mark in text]
check(not leaks, "bias-review.md holds none of the planted title / study question / hypothesis / threshold / target / setup / "
      "segment / intro / consent / closing / section-title text (leaked: %s)" % leaks)
check("rs-rev" not in text and "supportedIf" not in text and "tests" not in text.lower() and "qualifies" not in text.lower()
      and "target" not in text.lower() and "hypothes" not in text.lower() and "h1" not in text,
      "bias-review.md names no study id, hypothesis, test, target or qualifier")
plan_q = jload("survey-plan.json")["instrument"]["sections"]
check(all(q["text"] in text for s in plan_q for q in s["questions"]) and "options: Yes | No" in text
      and "scale: 1 to 5, 1 = No effort, 5 = A lot of effort" in text and "purpose: screener" in text and "purpose: main" in text
      and text.index("**q1**") < text.index("**q3**") < text.index("**q7**"),
      "bias-review.md has every question's text, options and scale, the section purpose, in order")
check("`<id> · yes|no|blocked · <evidence quoting the words>`" in text and "yes` means the check held" in text,
      "bias-review.md says at the top how to answer (the row format; yes = the check held)")
want = ["q1.neutral", "q1.single", "q1.plain", "q1.options", "q2.neutral", "q2.single", "q2.plain", "q2.options",
        "q3.neutral", "q3.single", "q3.actual", "q3.plain", "q3.unnamed", "q3.options",
        "q4.neutral", "q4.single", "q4.actual", "q4.plain", "q4.unnamed", "q4.scale",
        "q5.neutral", "q5.single", "q5.actual", "q5.plain", "q5.unnamed", "q5.options",
        "q6.neutral", "q6.single", "q6.actual", "q6.plain", "q6.unnamed",
        "q7.neutral", "q7.single", "q7.actual", "q7.plain", "q7.unnamed", "order.general-first"]
check(items == want, "items: screener questions skip actual + unnamed; options only on choice questions; scale only on scales; one order item "
      "(got %d, want %d)" % (len(items), len(want)))
item_lines = [l for l in text.split("## Items")[1].strip().splitlines()]
check(len(item_lines) == len(want) and all(l.split(" · ")[0] == i and l.rstrip().endswith("?") for l, i in zip(item_lines, want)),
      "each item is one line `<id> · <closed question>` and every one ends in a question mark")

# template questions get no items, but stay in the question list
pt, rc, out, err = template_study()
rc, out, err = pt.run("review-plan", "rs-tpl")
ttext = open(pt.path("memory", "research", "rs-tpl", "instrument", "bias-review.md"), encoding="utf-8").read()
check(rc == 0 and not [i for i in out["items"] if i.split(".")[0] in ("q9", "q10", "q11", "q12") or i.startswith("q13")]
      and "How likely are you to recommend this" in ttext and out["items"][-1] == "order.general-first",
      "template questions (ces, seq, csat, nps, sus) get no per-question items, yet appear in the question list")

# an interview is reviewed too (no options / scale items)
pi = Proj()
pi.run("init", "rs-iv", "--method", "interview", "--scope", "collect", "--question", "q", "--role", "dispatcher")
pi.run("plan", "rs-iv", "--file", os.path.join(FIX, "interview-plan.json"))
rc, out, err = pi.run("review-plan", "rs-iv")
check(rc == 0 and "q2.goal" in out["items"] and not [i for i in out["items"] if i.endswith((".options", ".scale"))],
      "review-plan on an interview: closed items, none about options or scales")
check(not [i for i in out["items"] if i.startswith("q2.") and i.endswith((".actual", ".plain", ".unnamed", ".single"))],
      "…and a task is asked about its goal, never whether it is past behaviour or needs no product knowledge")

# review: refusals first
rc, out, err = p.run("review", "rs-rev", "--file", p.path("none.txt"))
check(rc == 2, "review: a rows file that does not exist is exit 2")


def put_rows(name, text_):
    open(p.path(name), "w", encoding="utf-8").write(text_)
    return p.path(name)


good = rows_for(items)
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("unk.txt", good + "q99.neutral · yes · \"x\"\n"))
check(rc == 1 and "q99.neutral" in json.dumps(out) and "biasReview" not in p.study("rs-rev"), "REFUSED review rows with an unknown id; nothing stored")
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("miss.txt", rows_for([i for i in items if i != "q4.scale"])))
check(rc == 1 and "q4.scale" in json.dumps(out) and "biasReview" not in p.study("rs-rev"), "REFUSED review rows with a missing id; nothing stored")
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("mal.txt", good.replace("q3.plain · yes", "q3.plain · maybe", 1)))
check(rc == 1 and "biasReview" not in p.study("rs-rev"), "REFUSED a malformed row (answer is not yes|no|blocked)")
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("noev.txt", good.replace("q3.plain · yes · \"quoted words\"", "q3.plain · yes ·", 1)))
check(rc == 1 and "biasReview" not in p.study("rs-rev"), "REFUSED a row with no evidence")
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("dup.txt", good + "q1.neutral · no · \"again\"\n"))
check(rc == 1 and "biasReview" not in p.study("rs-rev"), "REFUSED an item answered twice")

# approve without a review
rc, out, err = p.run("approve", "rs-rev")
check(rc == 1 and "review" in out.get("error", "") and p.study("rs-rev")["status"] == "draft",
      "REFUSED approve with no bias review (and no --skip-review): still a draft")
rc, out, err = p.run("approve", "rs-rev", "--skip-review", " ")
check(rc == 2 and p.study("rs-rev")["status"] == "draft", "--skip-review without a reason is a usage error (exit 2)")

# a clean review is stored, with the hash of this instrument
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("ok.txt", "# rows\n\n" + good))
br = p.study("rs-rev").get("biasReview", {})
check(rc == 0 and br["summary"] == {"yes": len(items), "no": 0, "blocked": 0} and [r["id"] for r in br["rows"]] == items
      and br["rows"][0] == {"id": "q1.neutral", "answer": "yes", "evidence": "\"quoted words\""}
      and br["instrumentHash"] == R.instrument_hash(p.study("rs-rev")) and br["at"].endswith("Z"),
      "review: stores {at, instrumentHash, rows[{id, answer, evidence}], summary{yes,no,blocked}} (a # line and blanks are skipped)")
rc, out, err = p.run("approve", "rs-rev", "--note", "ok")
g = p.study("rs-rev")["gates"][-1]
check(rc == 0 and p.study("rs-rev")["status"] == "approved" and g["gate"] == "G-STUDY" and "skipReview" not in g and "acceptReview" not in g
      and g["review"]["summary"]["yes"] == len(items), "approve passes with a current all-yes review; the gate records the review summary")

# plan clears the review, and a stale review is refused
p.run("plan", "rs-rev", "--file", p.path("plan.json"))
check("biasReview" not in p.study("rs-rev"), "plan clears the stored review")
rc, out, err = p.run("approve", "rs-rev")
check(rc == 1 and p.study("rs-rev")["status"] == "draft", "REFUSED approve again after the plan (the review is gone)")
p.run("review", "rs-rev", "--file", put_rows("ok.txt", good))
d = p.data()
d["research"]["studies"][0]["instrument"]["sections"][1]["questions"][0]["text"] += " Please answer carefully."
p.save(d)
rc, out, err = p.run("approve", "rs-rev")
check(rc == 1 and "earlier version" in out.get("error", ""), "REFUSED approve when the stored review is for an earlier version of the instrument (hash differs)")
rc, out, err = p.run("approve", "rs-rev", "--skip-review", "no reviewer on this machine")
g = p.study("rs-rev")["gates"][-1]
check(rc == 0 and g["skipReview"] == "no reviewer on this machine" and "review" not in g, "approve --skip-review records the reason in the gate entry")

# a no / blocked row needs --accept-review, and it is recorded
p = review_project()
rc, out, err = p.run("review-plan", "rs-rev")
items = out["items"]
rows = rows_for(items, {"q3.neutral": "no", "q5.options": "blocked"}).replace("q3.neutral · no · \"quoted words\"", "q3.neutral · no · \"need the cash amount\" signals yes")
rc, out, err = p.run("review", "rs-rev", "--file", put_rows("flag.txt", rows))
check(rc == 0 and p.study("rs-rev")["biasReview"]["summary"] == {"yes": len(items) - 2, "no": 1, "blocked": 1}
      and "q3.neutral" in err + json.dumps(out), "review: a no and a blocked row are stored and reported back")
rc, out, err = p.run("approve", "rs-rev")
check(rc == 1 and p.study("rs-rev")["status"] == "draft" and "accept-review" in out.get("error", "")
      and {f["id"] for f in out["flags"]} == {"q3.neutral", "q5.options"}, "REFUSED approve with a `no`/`blocked` row and no --accept-review (the flagged rows are returned)")
p = review_project()
p.run("review-plan", "rs-rev")
p.run("review", "rs-rev", "--file", put_rows("flag.txt", rows))
rc, out, err = p.run("approve", "rs-rev", "--accept-review", " ")
check(rc == 2 and p.study("rs-rev")["status"] == "draft", "--accept-review without words is a usage error (exit 2)")
rc, out, err = p.run("approve", "rs-rev", "--accept-review", "the user keeps q3 because the wording is the product's own term")
g = p.study("rs-rev")["gates"][-1]
check(rc == 0 and p.study("rs-rev")["status"] == "approved" and g["acceptReview"] == "the user keeps q3 because the wording is the product's own term"
      and g["review"]["summary"]["no"] == 1 and {f["id"] for f in out["reviewFlags"]} == {"q3.neutral", "q5.options"},
      "approve --accept-review passes, records the reason in the gate entry, and returns the flagged rows")
rc, out, err = p.run("review", "rs-rev", "--file", p.path("flag.txt"))
check(rc == 1 and "approved" in out.get("error", ""), "REFUSED a review of a study that is no longer a draft")

shutil.rmtree(TMP, ignore_errors=True)
print()
if fails:
    print("FAIL: %d check(s) failed" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("PASS: research_tool")
