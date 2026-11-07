#!/usr/bin/env python3
"""
research_report.py — deterministic research documents for /pb:research. Stdlib only, no I/O, no clock.

Everything here is a pure function of the study object (and the registry, only to name screens):
the same study gives the same bytes. A value the data does not hold renders as "—"; this module
never computes a statistic, it prints the ones the tool already stored in `study.analysis`.

Instrument files (files_for) — for the researcher and the participant, written at G-STUDY:
  plan_md · moderator_guide_md · tasks_md · cards_md · consent_md · screener_md · note_taking_csv
The study report (at G-INSIGHT):
  report_md   Markdown; charts appear as their number tables
  report_html one self-contained printable file: inline CSS, inline SVG charts, every chart beside its table

Participants appear by pseudonym only; the report also redacts anything shaped like an email address
or a phone number from the free text it prints. No external fonts, scripts or images in the HTML.
"""
import csv
import html
import io
import math
import re

try:
    import research_methods as _rm
except ImportError:                                   # imported as pb.tools.* by a caller
    from . import research_methods as _rm             # pragma: no cover

SESSION_METHODS = ("usability", "tree-test", "card-sort", "first-click")
DEFAULT_N = {"survey": 30, "interview": 5, "usability": 5, "tree-test": 50, "card-sort": 15, "first-click": 30}
SEVERITY = {0: "Not a problem", 1: "Cosmetic", 2: "Minor", 3: "Major", 4: "Catastrophe"}
DRAFT_BANNER = "Draft — not yet approved at G-INSIGHT"
DASH = "—"
SUS_AVERAGE = 68
THINK_ALOUD = ("As you work, please say out loud what you are looking at, what you are trying to do and what you are thinking. "
               "There are no right or wrong answers: we are testing the prototype, not you. If you ask me how something works, "
               "I may not answer; that is on purpose, and it helps us most to see what you would do on your own.")
THINK_ALOUD_PRACTICE = "Practice: please think aloud while you work out how many windows there are in the place where you live."
DEFAULT_PROBES = ("What are you looking at right now?", "What did you expect to happen?", "Can you say more about that?",
                  "What would you do next?")
NOTE_CODES = (("A", "Assisted: the facilitator helped (also mark the task Assisted)"),
              ("E", "Error: a wrong turn, wrong entry or validation error"),
              ("H", "Hesitation: a pause, hovering, re-reading"),
              ("C", "Confusion: the participant said or showed they did not understand"),
              ("Q", "Quote: a verbatim line worth keeping (write it exactly)"),
              ("P", "Positive: something worked, or was liked"),
              ("W", "Workaround: the participant did it another way"))


# ── small helpers ────────────────────────────────────────────────────────────

def _squash(s):
    return re.sub(r"\s+", " ", s if isinstance(s, str) else ("" if s is None else str(s))).strip()


def as_list(x):
    return x if isinstance(x, list) else []


def as_dict(x):
    return x if isinstance(x, dict) else {}


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d ().-]{6,}\d(?![\w])")
_DATEISH = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _scrub(s):
    s = _EMAIL.sub("[redacted]", s)

    def ph(m):
        t = m.group(0)
        if _DATEISH.match(t) or len(re.sub(r"\D", "", t)) < 8:
            return t
        return "[redacted]"
    return _PHONE.sub(ph, s)


def _t(x):
    """Plain, squashed, PII-redacted text for the report."""
    return _scrub(_squash(x))


def _d(x):
    return _t(x) or DASH


def _n(x, d=1):
    if x is None or isinstance(x, bool):
        return DASH
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        s = "%.*f" % (d, x)
        return s.rstrip("0").rstrip(".") if "." in s else s
    return _d(x)


def _pct(x):
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return DASH
    return "%d%%" % int(x * 100 + 0.5)


def _rate_cell(s):
    """'4/5 · 80% (38–96%)' from an adjusted_wald dict."""
    s = as_dict(s)
    if not s or s.get("rate") is None:
        return "%s/%s · %s" % (_n(s.get("x")), _n(s.get("n")), DASH) if s else DASH
    return "%s/%s · %s (%s–%s)" % (_n(s.get("x")), _n(s.get("n")), _pct(s.get("rate")), _pct(s.get("low")), _pct(s.get("high")))


def _range_cell(s, unit="", d=1):
    s = as_dict(s)
    v = s.get("geoMean", s.get("mean", s.get("median")))
    if v is None:
        return DASH
    lo, hi = s.get("low"), s.get("high")
    out = "%s%s" % (_n(v, d), unit)
    if lo is not None and hi is not None:
        out += " (%s–%s)" % (_n(lo, d), _n(hi, d))
    return out


def _g(d, *path):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return None
        d = d[p]
    return d


def _mode(study):
    m = as_dict(study.get("instrument")).get("mode")
    return m if m in ("moderated", "unmoderated", "both") else "moderated"


def _moderated(study):
    return _mode(study) in ("moderated", "both")


def _title(study):
    return _squash(study.get("title")) or _squash(study.get("id")) or "Research study"


def _screen_name(reg, sid):
    for s in as_list(as_dict(reg).get("screens")):
        if isinstance(s, dict) and s.get("id") == sid:
            return _squash(s.get("name") or s.get("title"))
    return ""


def _screen_label(reg, sid):
    nm = _screen_name(reg, sid)
    return "`%s`%s" % (sid, " (%s)" % nm if nm else "")


def _questions(study):
    out = []
    for sec in as_list(as_dict(study.get("instrument")).get("sections")):
        if isinstance(sec, dict):
            for q in as_list(sec.get("questions")):
                if isinstance(q, dict):
                    out.append((sec, q))
    return out


def _sections(study, purpose):
    return [s for s in as_list(as_dict(study.get("instrument")).get("sections"))
            if isinstance(s, dict) and s.get("purpose") == purpose and any(isinstance(q, dict) for q in as_list(s.get("questions")))]


def _tasks(study):
    """[{q, sec, post:[questions]}] — the task questions in order, each with the questions that follow it."""
    out = []
    for sec in as_list(as_dict(study.get("instrument")).get("sections")):
        if not isinstance(sec, dict) or sec.get("purpose") != "task":
            continue
        qs = [q for q in as_list(sec.get("questions")) if isinstance(q, dict)]
        keyed = [q for q in qs if any(k in q for k in ("task", "tree", "click"))]
        if not keyed:
            out.extend({"q": q, "sec": sec, "post": []} for q in qs)
            continue
        cur = None
        for q in qs:
            if q in keyed:
                cur = {"q": q, "sec": sec, "post": []}
                out.append(cur)
            elif cur is not None:
                cur["post"].append(q)
    return out


def _hyp(study):
    return [h for h in as_list(study.get("hypotheses")) if isinstance(h, dict)]


def _tested_by(study, hid):
    return [q.get("id") for _s, q in _questions(study) if hid in as_list(q.get("tests"))] + \
           ([] if not hid else ["sort"] if hid in as_list(as_dict(as_dict(study.get("instrument")).get("sort")).get("tests")) else [])


def _tree_labels(study):
    return {n.get("id"): _squash(n.get("label")) for n in as_list(as_dict(study.get("instrument")).get("tree")) if isinstance(n, dict)}


def _card_labels(study):
    return {c.get("id"): _squash(c.get("label")) for c in as_list(as_dict(study.get("instrument")).get("cards")) if isinstance(c, dict)}


def _minutes(study):
    plan = as_dict(study.get("plan"))
    m = as_dict(plan.get("schedule")).get("sessionMinutes")
    if not isinstance(m, int) or m < 1:
        m = as_dict(study.get("instrument")).get("durationMin")
    if not isinstance(m, int) or m < 1:
        ent = _rm.catalog_entry(study.get("method")) or {}
        nums = re.findall(r"\d+", ent.get("minutes", ""))
        m = int(nums[-1]) if nums else 30
    return m


def _live_evidence(study):
    return [e for e in as_list(study.get("evidence")) if isinstance(e, dict) and not e.get("dropped")]


def _session_rows(study):
    return [e for e in _live_evidence(study) if e.get("kind") == "session"]


def _target_n(study):
    t = as_dict(study.get("audience")).get("targetN")
    if isinstance(t, int):
        return t
    t = as_dict(as_dict(study.get("plan")).get("participants")).get("n")
    if isinstance(t, int):
        return t
    return DEFAULT_N.get(study.get("method"))


def _n_done(study):
    n = as_dict(study.get("analysis")).get("n")
    if isinstance(n, int):
        return n
    # A survey's people are its qualified respondents, counted by `tally` — one CSV file holds many of them.
    tn = as_dict(study.get("tally")).get("n")
    if study.get("method") == "survey" and isinstance(tn, int) and not isinstance(tn, bool):
        return tn
    rows = _session_rows(study) if study.get("method") in SESSION_METHODS else _live_evidence(study)
    if study.get("method") in SESSION_METHODS:
        return len(rows)
    return len({e.get("participant") or e.get("id") for e in rows})


def _dates(study):
    rows = _session_rows(study) or _live_evidence(study)
    ds = sorted(d for d in (_squash(e.get("date")) for e in rows) if d)
    if not ds:
        return DASH
    return ds[0] if ds[0] == ds[-1] else "%s to %s" % (ds[0], ds[-1])


def _md_cell(x):
    s = x.get("x", "") if isinstance(x, dict) else x
    return _mx(s).replace("|", "\\|") or DASH


def _mx(s):
    """Markdown-safe: raw HTML in a stored string is made inert."""
    return _squash(s).replace("<", "&lt;")


def _lines_to_text(lines):
    return "\n".join(lines).rstrip("\n") + "\n"


def _list(lines, items, empty=DASH):
    items = [i for i in items if _squash(i)]
    if not items:
        lines.append(empty)
    for i in items:
        lines.append("- %s" % _squash(i))


def _status_line(study):
    return "DRAFT — not approved" if study.get("status") == "draft" else "Approved at G-STUDY"


def _criteria_text(c):
    c = as_dict(c)
    if "screen" in c:
        return "the screen is `%s`" % _squash(c["screen"])
    if "text" in c:
        return "the text \"%s\" is on screen" % _squash(c["text"])
    if "present" in c:
        return "an element matching `%s` is present" % _squash(c["present"])
    if "absent" in c:
        return "no element matches `%s`" % _squash(c["absent"])
    return _squash(str(c))


def _scale_text(q):
    sc = q.get("scale")
    if isinstance(sc, dict):
        return "%s to %s: %s ... %s" % (sc.get("min"), sc.get("max"), _squash(sc.get("minLabel")), _squash(sc.get("maxLabel")))
    return ""


def _question_lines(q, indent="   "):
    out = []
    for o in as_list(q.get("options")):
        out.append("%s- [ ] %s" % (indent, _squash(o)))
    st = _scale_text(q)
    if st:
        out.append("%s- Scale %s" % (indent, st))
    return out


def _proto_link(task):
    task = as_dict(task)
    ent, role = task.get("entry"), task.get("role")
    if ent:
        return "/?entry=%s%s" % (ent, "&role=" + role if role else "")
    return "/?role=%s" % role if role else "/"


# ── plan.md ──────────────────────────────────────────────────────────────────

def plan_md(study, reg):
    plan = as_dict(study.get("plan"))
    inst = as_dict(study.get("instrument"))
    method = study.get("method")
    cat = _rm.catalog_entry(method) or {}
    L = ["# Research plan: %s" % _title(study), "", _status_line(study), "",
         "- Study: `%s` (%s)" % (study.get("id"), method),
         "- Question: %s" % (_squash(study.get("question")) or DASH)]
    if method in SESSION_METHODS:
        L.append("- Mode: %s" % _mode(study))
    L += ["", "## Background", "", _squash(plan.get("background")) or DASH, "", "## Objectives", ""]
    _list(L, as_list(plan.get("objectives")))
    L += ["", "## Research questions", ""]
    rqs = as_list(plan.get("researchQuestions")) or ([study.get("question")] if _squash(study.get("question")) else [])
    _list(L, rqs)
    L += ["", "## The decision this informs", "", _squash(plan.get("decision")) or DASH, "", "## Hypotheses", ""]
    hs = _hyp(study)
    if not hs:
        L.append(DASH)
    for h in hs:
        L.append("- **%s** %s" % (h.get("id"), _squash(h.get("statement"))))
        L.append("  - supported if: %s" % (_squash(h.get("supportedIf")) or DASH))
        L.append("  - refuted if: %s" % (_squash(h.get("refutedIf")) or DASH))
        L.append("  - tested by: %s" % (", ".join(str(x) for x in _tested_by(study, h.get("id"))) or "nothing yet"))
    L += ["", "## Method and why", "", "- Method: %s" % method]
    if cat:
        L.append("- What it answers: %s" % cat.get("answers"))
        L.append("- Behavioural or attitudinal: %s; data: %s" % (cat.get("kind"), cat.get("data")))
        L.append("- Not for: %s" % cat.get("notFor"))
    L.append("- Why this method here: %s" % (_squash(plan.get("methodRationale")) or DASH))
    if method in SESSION_METHODS:
        L.append("- Mode: %s" % _mode(study))
        L.append("- Device: %s" % (_squash(inst.get("device")) or "the project default"))
        rec = as_dict(inst.get("recording"))
        asked = [k for k in ("screen", "voice") if rec.get(k)]
        L.append("- Screen or voice recording: %s" % ("may be asked for (%s); the participant chooses" % " and ".join(asked) if asked else "not asked for"))
    L.append("- Session length: about %s minutes" % _minutes(study))

    L += ["", "## Participants", ""]
    pp = as_dict(plan.get("participants"))
    L.append("Who is in:")
    L.append("")
    _list(L, as_list(pp.get("criteria")))
    L += ["", "Who is out:", ""]
    _list(L, as_list(pp.get("exclude")))
    aud = as_dict(study.get("audience"))
    roles = ", ".join(str(r) for r in as_list(aud.get("roles")))
    L += ["", "- Audience: %s" % (roles or DASH) + (" (%s)" % _squash(aud.get("segment")) if _squash(aud.get("segment")) else ""),
          "- Target n: %s (rule of thumb for %s: about %s)" % (_n(pp.get("n") if isinstance(pp.get("n"), int) else aud.get("targetN")),
                                                              method, DEFAULT_N.get(method, DASH)),
          "- Segments: %s" % (", ".join(_squash(s) for s in as_list(pp.get("segments")) if _squash(s)) or DASH)]
    parts = [p for p in as_list(study.get("participants")) if isinstance(p, dict) and not p.get("pilot")]
    if parts:
        by = {}
        for p in parts:
            by[p.get("status") or "invited"] = by.get(p.get("status") or "invited", 0) + 1
        L.append("- Tracker today: %s" % ", ".join("%s %d" % (k, by[k]) for k in sorted(by)))

    rc = as_dict(plan.get("recruitment"))
    L += ["", "## Recruitment", "", "- Channel: %s" % (_squash(rc.get("channel")) or DASH),
          "- Incentive: %s" % (_squash(rc.get("incentive")) or DASH),
          "- Notes: %s" % (_squash(rc.get("note")) or DASH),
          "- Budget: %s" % (_squash(plan.get("budget")) or DASH)]

    sc = as_dict(plan.get("schedule"))
    L += ["", "## Schedule and timeline", "", "- Fielding: %s to %s" % (_squash(sc.get("start")) or DASH, _squash(sc.get("end")) or DASH)]
    tl = [t for t in as_list(plan.get("timeline")) if isinstance(t, dict)]
    if tl:
        L += ["", "| Milestone | Date |", "|---|---|"]
        for t in tl:
            L.append("| %s | %s |" % (_md_cell(t.get("milestone")), _md_cell(t.get("date"))))

    tm = as_dict(plan.get("team"))
    L += ["", "## Team and roles", "", "- Moderator: %s" % (_squash(tm.get("moderator")) or DASH),
          "- Note-taker: %s" % (_squash(tm.get("notetaker")) or DASH),
          "- Observers: %s" % (", ".join(_squash(o) for o in as_list(tm.get("observers")) if _squash(o)) or DASH)]

    L += ["", "## Materials", ""]
    mats = [m for m in as_list(plan.get("materials"))]
    try:
        gen = sorted(files_for(study, reg))
    except Exception:                                            # a plan view must not fail on a half-written study
        gen = []
    _list(L, mats + ["%s (generated)" % g for g in gen])

    L += ["", "## Risks and mitigations", ""]
    rk = [r for r in as_list(plan.get("risks")) if isinstance(r, dict)]
    if rk:
        L += ["| Risk | Mitigation |", "|---|---|"]
        for r in rk:
            L.append("| %s | %s |" % (_md_cell(r.get("risk")), _md_cell(r.get("mitigation"))))
    else:
        L.append(DASH)

    rec = as_dict(inst.get("recording"))
    L += ["", "## Ethics and consent", "",
          "- Consent is shown and answered before anything is saved (`consent.md`); no consent, no data.",
          "- Participants are known only by a code (`P01`, `P02`). No names, emails or phone numbers are stored.",
          "- Taking part is voluntary; a participant can stop or withdraw at any time and their data is dropped.",
          "- Only the data the hypotheses need is collected."]
    if method in SESSION_METHODS:
        L.append("- Screen or voice recording is optional and asked for separately%s." % ("" if any(rec.get(k) for k in ("screen", "voice")) else " (this study does not ask)"))
    L += ["", "## Analysis plan", "", "What the tool will compute for this method (nothing is typed by hand):", ""]
    _list(L, as_list(cat.get("outputs")) or ["counts and verbatim quotes only"])
    L += ["", "Verdicts are read against the thresholds written above, before the data comes in. Fewer participants than the target is reported as directional.",
          "", "## Deliverables", "", "- `report.md` and `report.html`: summary, results, findings, ranked issues, recommendations, limitations",
          "- Evidence stays on disk, read-only and hashed; the report cites it by id"]
    chk = [c for c in as_list(as_dict(study.get("logistics")).get("checklist")) if isinstance(c, dict)]
    if chk:
        L += ["", "## Logistics checklist", ""]
        for c in chk:
            L.append("- [%s] %s" % ("x" if c.get("done") else " ", _squash(c.get("text"))))
    return _lines_to_text(L)


# ── tasks.md / cards.md ──────────────────────────────────────────────────────

def tasks_md(study, reg):
    """Participant-facing task cards: the scenario text only."""
    ts = _tasks(study)
    L = ["# Tasks", "", "Read one task at a time. Do it the way you normally would, and tell the facilitator when you are done.", ""]
    if not ts:
        L.append(DASH)
    for i, t in enumerate(ts, 1):
        L += ["## Task %d of %d" % (i, len(ts)), "", _squash(t["q"].get("text")) or DASH, ""]
    return _lines_to_text(L)


def cards_md(study, reg):
    inst = as_dict(study.get("instrument"))
    sort = as_dict(inst.get("sort"))
    kind = sort.get("kind") or "open"
    L = ["# Card sort", "", "- Kind: %s" % kind, "- Study: `%s`" % study.get("id"), "", "## Cards", ""]
    cards = [c for c in as_list(inst.get("cards")) if isinstance(c, dict)]
    if not cards:
        L.append(DASH)
    for c in cards:
        L.append("- %s" % _squash(c.get("label")))
    L += ["", "## Categories", ""]
    if kind == "open":
        L.append("None: participants make and name their own groups.")
    else:
        cats = [c for c in as_list(sort.get("categories")) if isinstance(c, dict)]
        _list(L, [c.get("label") for c in cats])
        if kind == "hybrid":
            L.append("Participants may also make groups of their own.")
    return _lines_to_text(L)


# ── consent.md ───────────────────────────────────────────────────────────────

def consent_md(study, reg):
    inst = as_dict(study.get("instrument"))
    method = study.get("method")
    rec = as_dict(inst.get("recording"))
    rec_screen, rec_voice = bool(rec.get("screen")), bool(rec.get("voice"))
    minutes = _minutes(study)
    L = ["# Consent", "", _squash(study.get("title")) and "Study: %s" % _title(study) or "Study: `%s`" % study.get("id"), "",
         _squash(inst.get("consent")) or "Please read this before you start.", "",
         "## What we ask of you", "", "About %s minutes of your time." % minutes, ""]
    L += ["## What is saved", ""]
    if method in SESSION_METHODS:
        L += ["- A log of what you do on the page: which pages you open, where you click, how long each task takes, and any messages the page shows.",
              "- For text fields, only how many characters you typed. What you type is never saved.",
              "- Your answers to the questions we ask."]
    else:
        L += ["- Your answers, written down as notes under your code."]
    L += ["- A participant code (such as P01) in place of your name. We do not store your name, email address or phone number with your answers."]
    if rec_screen or rec_voice:
        what = " and ".join(x for x, on in (("your screen", rec_screen), ("your voice", rec_voice)) if on)
        L += ["", "## Optional: recording", "",
              "We would also like to record %s while you take part. This is optional." % what,
              "Taking part without recording is fine; you will be asked separately, and you can say no.",
              "The recording is kept as a file on the researcher's own computer, is used only to review what happened, and is not published."]
        if rec_screen:
            L.append("Your browser will ask which screen to share; choose this tab only.")
    L += ["", "## Who sees it and where it is kept", "",
          "- The research team sees it. Findings are reported by code and never by name.",
          "- It is stored on the researcher's own computer. Nothing is uploaded to a website or shared service by this tool.",
          "", "## Your choices", "",
          "- Taking part is voluntary. You can stop at any time, and you do not have to give a reason.",
          "- You can withdraw afterwards by telling the researcher your code. Your data is then removed from the results.",
          "", "## Your answer", "", "Participant code: P__", "",
          "- [ ] I have read this and I agree to take part."]
    if rec_screen or rec_voice:
        L.append("- [ ] I agree to the optional recording described above (leave this empty to take part without it).")
    L += ["", "Date: ______________"]
    return _lines_to_text(L)


# ── screener.md ──────────────────────────────────────────────────────────────

def screener_md(study, reg):
    secs = _sections(study, "screener")
    if not secs:
        return None
    plan = as_dict(study.get("plan"))
    pp = as_dict(plan.get("participants"))
    L = ["# Screener", "", "- Study: `%s`" % study.get("id"),
         "- Use it to decide who is invited. Do not tell the person which answers qualify.", "", "## Who we want", ""]
    _list(L, as_list(pp.get("criteria")))
    L += ["", "## Who we do not want", ""]
    _list(L, as_list(pp.get("exclude")))
    if as_list(pp.get("segments")):
        L += ["", "## Segments to fill", ""]
        _list(L, as_list(pp.get("segments")))
    n = 0
    for sec in secs:
        L += ["", "## %s" % (_squash(sec.get("title")) or "Questions"), ""]
        for q in as_list(sec.get("questions")):
            if not isinstance(q, dict):
                continue
            n += 1
            L.append("%d. **%s** %s (%s)" % (n, q.get("id"), _squash(q.get("text")), q.get("type", "?")))
            keep = {_squash(v).casefold() for v in as_list(q.get("qualifies"))}
            for o in as_list(q.get("options")):
                L.append("   - [ ] %s%s" % (_squash(o), " (qualifies)" if _squash(o).casefold() in keep else ""))
            st = _scale_text(q)
            if st:
                L.append("   - Scale %s" % st)
    L += ["", "Participant code once accepted: P__"]
    return _lines_to_text(L)


# ── note-taking.csv ──────────────────────────────────────────────────────────

NOTE_COLUMNS = ["participant", "session", "task", "time", "observation", "quote", "tag", "severity"]


def note_taking_csv(study):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(NOTE_COLUMNS)
    ts = _tasks(study)
    if not ts:
        w.writerow([""] * len(NOTE_COLUMNS))
    for t in ts:
        w.writerow(["", "", t["q"].get("id") or "", "", "", "", "", ""])
    return out.getvalue()


# ── moderator-guide.md ───────────────────────────────────────────────────────

def _fmt_clock(m):
    return "%d:%02d" % (m // 60, m % 60)


def moderator_guide_md(study, reg):
    inst = as_dict(study.get("instrument"))
    method = study.get("method")
    ts = _tasks(study)
    think = method == "usability" and inst.get("thinkAloud", True) is not False
    total = _minutes(study)
    stuck = inst.get("stuckMin") if isinstance(inst.get("stuckMin"), int) and inst.get("stuckMin") > 0 else 2

    warm = _sections(study, "warmup")
    close = _sections(study, "closing")
    # Fixed slots, then what is left is shared by the tasks (at least 2 minutes each).
    slots = [("Welcome and introduction", 3), ("Consent", 2)]
    if think:
        slots.append(("Think-aloud instruction and practice", 3))
    if warm:
        slots.append(("Warm-up questions", 4))
    fixed = sum(m for _t_, m in slots) + 5 + 3          # closing questions + debrief
    each = max(2, (total - fixed) // len(ts)) if ts else 0
    L = ["# Moderator guide: %s" % _title(study), "", _status_line(study), "",
         "- Study: `%s` (%s, %s)" % (study.get("id"), method, _mode(study)),
         "- Session length: about %d minutes" % total,
         "- Device: %s" % (_squash(inst.get("device")) or "the project default"),
         "- Keep this guide to yourself: it names the success definitions and the hypotheses."]
    if _mode(study) == "unmoderated":
        L.append("- This study is unmoderated. Use this guide for the pilot session and to review the participant kit; participants never see it.")
    L += ["", "## Timing", "", "| Start | Minutes | Part |", "|---|---|---|"]
    clock = 0
    plan_rows = list(slots) + [("Task %d: %s" % (i, t["q"].get("id")), each) for i, t in enumerate(ts, 1)] + [("Closing questions", 5), ("Debrief", 3)]
    for name, m in plan_rows:
        L.append("| %s | %d | %s |" % (_fmt_clock(clock), m, name))
        clock += m
    L.append("| %s | | Total (a guide: the real session finds its own pace) |" % _fmt_clock(clock))

    L += ["", "## Facilitator rules", "",
          "- Read the scenario exactly as written. Do not add words, hints or the names of buttons.",
          "- Never lead. Ask \"What do you expect?\", not \"Do you think it should be a button?\".",
          "- Never defend the design. When they criticise, say \"Thank you, tell me more.\" Do not explain why it is like that.",
          "- Do not help unless the participant has been stuck for more than %d minutes. If you do, mark the task **Assisted** (observer window, or note code A). An assisted success is not counted as a success." % stuck,
          "- Wait about 5 seconds after an answer. People fill silence with the useful part.",
          "- Stay neutral on the outcome: \"mm-hm\", \"thank you\", \"that's helpful\", never \"good\" or \"wrong\".",
          "- If they ask \"Is this right?\", say \"What would you do if I weren't here?\".",
          "- Record what you see, not what you conclude. Write the quote exactly, in their words.",
          "- The participant can stop at any time. If they ask to, stop, say thank you, and do not argue."]

    L += ["", "## 1. Welcome and introduction (read aloud)", "", _squash(inst.get("intro")) or DASH,
          "", "## 2. Consent (read aloud, then record the answer)", "", _squash(inst.get("consent")) or DASH,
          "", "- Participant code: P__", "- Agreed to take part: yes / no (if no, thank them and stop; save nothing)"]
    rec = as_dict(inst.get("recording"))
    if rec.get("screen") or rec.get("voice"):
        L.append("- Agreed to screen / voice recording: yes / no (the participant answers this on the page; it is optional)")
    sec_no = 3
    if think:
        L += ["", "## %d. Think-aloud instruction and practice" % sec_no, "", "Say:", "", "> %s" % THINK_ALOUD, "",
              "Practice, then continue when they have done it once:", "", "> %s" % THINK_ALOUD_PRACTICE]
        sec_no += 1
    if warm:
        L += ["", "## %d. Warm-up questions" % sec_no, "", "Easy and factual. Ask about the last time they did something, not about what they would do.", ""]
        n = 0
        for sec in warm:
            for q in as_list(sec.get("questions")):
                if isinstance(q, dict):
                    n += 1
                    L.append("%d. %s" % (n, _squash(q.get("text"))))
                    L += _question_lines(q)
        sec_no += 1

    labels = _tree_labels(study)
    for i, t in enumerate(ts, 1):
        q = t["q"]
        task = as_dict(q.get("task"))
        L += ["", "## %d. Task %d of %d (%s), about %d minutes" % (sec_no, i, len(ts), q.get("id"), each), "",
              "Read exactly:", "", "> %s" % (_squash(q.get("text")) or DASH), ""]
        if task:
            L.append("- Start screen: %s%s" % (_screen_label(reg, task.get("screen")) if task.get("screen") else DASH,
                                                 ", role `%s`" % task["role"] if task.get("role") else ""))
            L.append("- Open: `%s`" % _proto_link(task))
            L.append("- Success: %s" % (_squash(task.get("success")) or DASH))
            for c in as_list(task.get("criteria")):
                L.append("  - tool checks: %s" % _criteria_text(c))
            if as_list(task.get("optimalPath")):
                L.append("- Shortest path: %s" % " > ".join(str(s) for s in task["optimalPath"]))
            if isinstance(task.get("timeLimitSec"), int):
                L.append("- Time limit: %d seconds (then move on and mark it timed out)" % task["timeLimitSec"])
        tree = as_dict(q.get("tree"))
        if tree:
            L.append("- Correct answer: %s" % (", ".join(labels.get(c) or str(c) for c in as_list(tree.get("correct"))) or DASH))
        click = as_dict(q.get("click"))
        if click:
            L.append("- Start screen: %s" % (_screen_label(reg, click.get("screen")) if click.get("screen") else DASH))
            L.append("- Correct first click: %s" % (("`%s`" % click["target"]) if click.get("target") else "the marked region"))
        L.append("- Tests: %s" % (", ".join(str(x) for x in as_list(q.get("tests"))) or DASH))
        L += ["", "Observe:", "",
              "- Where they look first, where they hesitate, any wrong turn, and what they say.",
              "- Whether they finish on their own, give up, or need help (mark Assisted).",
              "", "Neutral probes (only when needed):", ""]
        for p in as_list(q.get("probes")) or list(DEFAULT_PROBES):
            L.append("- %s" % _squash(p))
        if t["post"]:
            L += ["", "After the task, ask:", ""]
            for k, pq in enumerate(t["post"], 1):
                L.append("%d. %s" % (k, _squash(pq.get("text"))))
                L += _question_lines(pq)
        sec_no += 1

    L += ["", "## %d. Closing questions" % sec_no, ""]
    n = 0
    for sec in close:
        for q in as_list(sec.get("questions")):
            if isinstance(q, dict):
                n += 1
                L.append("%d. %s" % (n, _squash(q.get("text"))))
                L += _question_lines(q)
    L.append("%d. Is there anything I did not ask that I should have?" % (n + 1))
    if _squash(inst.get("closing")):
        L += ["", "Say:", "", "> %s" % _squash(inst.get("closing"))]
    sec_no += 1
    L += ["", "## %d. Debrief" % sec_no, "",
          "- Thank them. Say what happens to what they told us, and that they can withdraw by quoting their code.",
          "- Tell them the study tested the prototype, not them.",
          "- Stop any recording, check the session was saved, and arrange the incentive.",
          "- Write your own first impressions straight away, before the next session.",
          "", "## Note-taking codes", "", "Use these in the `tag` column of `note-taking.csv`. Severity is Nielsen's, 0 to 4.", ""]
    for code, text in NOTE_CODES:
        L.append("- **%s** %s" % (code, text))
    L += ["", "Severity: 0 not a problem · 1 cosmetic · 2 minor · 3 major · 4 catastrophe"]
    return _lines_to_text(L)


# ── files_for ────────────────────────────────────────────────────────────────

def files_for(study, reg):
    """{filename: text} for the instrument/ folder of this study's method."""
    method = study.get("method")
    out = {}
    if method == "survey":
        return out
    out["plan.md"] = plan_md(study, reg)
    if method == "interview":
        out["consent.md"] = consent_md(study, reg)
        return out
    if method == "usability":
        out["moderator-guide.md"] = moderator_guide_md(study, reg)
        out["tasks.md"] = tasks_md(study, reg)
        out["consent.md"] = consent_md(study, reg)
        s = screener_md(study, reg)
        if s:
            out["screener.md"] = s
        out["note-taking.csv"] = note_taking_csv(study)
        return out
    if method in ("tree-test", "first-click"):
        out["tasks.md"] = tasks_md(study, reg)
    elif method == "card-sort":
        out["cards.md"] = cards_md(study, reg)
    else:
        return out
    out["consent.md"] = consent_md(study, reg)
    if _moderated(study):
        out["moderator-guide.md"] = moderator_guide_md(study, reg)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# The report: one block model, two renderers (Markdown, HTML)
# ═════════════════════════════════════════════════════════════════════════════
#
# Blocks: {"t":"h","l":2,"x"} · {"t":"p","x"} · {"t":"ul","items":[..]} · {"t":"ol","items":[..]} ·
#         {"t":"kv","rows":[(k,v)]} · {"t":"banner","x"} ·
#         {"t":"table","head":[..],"rows":[[cell..]]}   cell = str | {"x","cls"?,"bg"?,"fg"?}
#         {"t":"chart","title","svg","head","rows","note"?}  svg may be None (the table is the chart)

def _h(level, x):
    return {"t": "h", "l": level, "x": x}


def _p(x):
    return {"t": "p", "x": x}


def _table(head, rows):
    return {"t": "table", "head": head, "rows": rows}


# ── SVG ──────────────────────────────────────────────────────────────────────

def _f(x):
    return ("%.1f" % x).replace("-0.0", "0.0")


def _e(s):
    return html.escape(_squash(s), quote=True)


def _short(s, n=28):
    s = _squash(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def _nice_max(v):
    if not v or v <= 0:
        return 1.0
    ex = math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if m * 10 ** ex >= v:
            return float(m * 10 ** ex)
    return float(10 ** (ex + 1))


def _svg_bars(rows, vmin, vmax, ticks, kind, aria):
    """Horizontal bars (kind 'bar') or dots (kind 'dot') with optional whiskers.
    rows = [{"label","v","lo","hi","text"}]; v None draws a dash."""
    W, lw, rw, rh, top = 680, 200, 110, 30, 8
    pw = W - lw - rw
    H = top + len(rows) * rh + 30

    def X(v):
        v = min(max(v, vmin), vmax)
        return lw + (v - vmin) / float(vmax - vmin) * pw
    p = ['<svg class="chart-svg" role="img" aria-label="%s" viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx">' % (_e(aria), W, H, W),
         "<title>%s</title>" % _e(aria)]
    bottom = top + len(rows) * rh
    for tv, tl in ticks:
        x = X(tv)
        p.append('<line class="g" x1="%s" y1="%d" x2="%s" y2="%d"/>' % (_f(x), top, _f(x), bottom))
        p.append('<text class="ax" x="%s" y="%d" text-anchor="middle">%s</text>' % (_f(x), bottom + 16, _e(tl)))
    for i, r in enumerate(rows):
        y = top + i * rh
        mid = y + rh / 2.0
        p.append('<text class="lb" x="%d" y="%s" text-anchor="end">%s</text>' % (lw - 8, _f(mid + 4), _e(_short(r.get("label")))))
        if r.get("v") is None:
            p.append('<text class="vl" x="%s" y="%s">%s</text>' % (_f(X(vmin) + 6), _f(mid + 4), DASH))
            continue
        if kind == "bar":
            p.append('<rect class="bar" x="%d" y="%s" width="%s" height="%d"/>' % (lw, _f(y + 6), _f(max(X(r["v"]) - lw, 0)), rh - 12))
        else:
            p.append('<circle class="dot" cx="%s" cy="%s" r="5"/>' % (_f(X(r["v"])), _f(mid)))
        lo, hi = r.get("lo"), r.get("hi")
        if lo is not None and hi is not None:
            xl, xh = X(lo), X(hi)
            p.append('<line class="wh" x1="%s" y1="%s" x2="%s" y2="%s"/>' % (_f(xl), _f(mid), _f(xh), _f(mid)))
            p.append('<line class="wh" x1="%s" y1="%s" x2="%s" y2="%s"/>' % (_f(xl), _f(mid - 5), _f(xl), _f(mid + 5)))
            p.append('<line class="wh" x1="%s" y1="%s" x2="%s" y2="%s"/>' % (_f(xh), _f(mid - 5), _f(xh), _f(mid + 5)))
        p.append('<text class="vl" x="%d" y="%s">%s</text>' % (W - rw + 8, _f(mid + 4), _e(r.get("text") or "")))
    p.append("</svg>")
    return "".join(p)


def _svg_gauge(score, low, high, grade):
    W, H, x0, pw = 680, 132, 30, 620

    def X(v):
        return x0 + min(max(v, 0), 100) / 100.0 * pw
    bands = ((0, 51.7, "b1", "F"), (51.7, SUS_AVERAGE, "b2", "below average"), (SUS_AVERAGE, 80.8, "b3", "above average"), (80.8, 100, "b4", "A range"))
    aria = "SUS score %s out of 100, grade %s" % (_n(score), grade or DASH)
    p = ['<svg class="chart-svg" role="img" aria-label="%s" viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx"><title>%s</title>' % (_e(aria), W, H, W, _e(aria))]
    for a, b, cls, nm in bands:
        p.append('<rect class="%s" x="%s" y="40" width="%s" height="26"/>' % (cls, _f(X(a)), _f(X(b) - X(a))))
        p.append('<text class="ax" x="%s" y="84" text-anchor="middle">%s</text>' % (_f((X(a) + X(b)) / 2.0), _e(nm)))
    for tv in (0, 25, 50, 75, 100):
        p.append('<text class="ax" x="%s" y="102" text-anchor="middle">%d</text>' % (_f(X(tv)), tv))
    p.append('<line class="avg" x1="%s" y1="32" x2="%s" y2="110"/>' % (_f(X(SUS_AVERAGE)), _f(X(SUS_AVERAGE))))
    p.append('<text class="ax" x="%s" y="124" text-anchor="middle">%d (commonly cited average)</text>' % (_f(X(SUS_AVERAGE)), SUS_AVERAGE))
    if low is not None and high is not None:
        p.append('<line class="wh" x1="%s" y1="53" x2="%s" y2="53"/>' % (_f(X(low)), _f(X(high))))
    xs = X(score)
    p.append('<polygon class="mk" points="%s,38 %s,28 %s,28"/>' % (_f(xs), _f(xs - 7), _f(xs + 7)))
    p.append('<text class="vl" x="%s" y="16" text-anchor="middle">%s · %s</text>' % (_f(xs), _e(_n(score)), _e(grade or DASH)))
    p.append("</svg>")
    return "".join(p)


def _svg_clicks(clicks, rect, aria):
    W, H = 320, 200
    p = ['<svg class="chart-svg fc" role="img" aria-label="%s" viewBox="0 0 %d %d" width="100%%" style="max-width:480px"><title>%s</title>' % (_e(aria), W, H, _e(aria)),
         '<rect class="scr" x="0.5" y="0.5" width="%d" height="%d"/>' % (W - 1, H - 1)]
    for k in (1, 2):
        p.append('<line class="g" x1="%s" y1="0" x2="%s" y2="%d"/>' % (_f(W * k / 3.0), _f(W * k / 3.0), H))
        p.append('<line class="g" x1="0" y1="%s" x2="%d" y2="%s"/>' % (_f(H * k / 3.0), W, _f(H * k / 3.0)))
    r = as_dict(rect)
    if all(isinstance(r.get(k), (int, float)) for k in ("x", "y", "w", "h")):
        p.append('<rect class="tgt" x="%s" y="%s" width="%s" height="%s"/>' % (_f(r["x"] * W), _f(r["y"] * H), _f(r["w"] * W), _f(r["h"] * H)))
    for c in clicks:
        if not (isinstance(c, (list, tuple)) and len(c) >= 2 and all(isinstance(v, (int, float)) for v in c[:2])):
            continue
        cx, cy = min(max(c[0], 0), 1) * W, min(max(c[1], 0), 1) * H
        if len(c) > 2 and c[2]:
            p.append('<circle class="hit" cx="%s" cy="%s" r="4"/>' % (_f(cx), _f(cy)))
        else:
            p.append('<path class="miss" d="M%s %sL%s %sM%s %sL%s %s"/>' % (_f(cx - 4), _f(cy - 4), _f(cx + 4), _f(cy + 4), _f(cx - 4), _f(cy + 4), _f(cx + 4), _f(cy - 4)))
    p.append("</svg>")
    return "".join(p)


def _heat(v):
    if not isinstance(v, (int, float)):
        return {"x": DASH}
    v = min(max(v, 0.0), 1.0)
    r, g, b = 255 - int(v * (255 - 31)), 255 - int(v * (255 - 78)), 255 - int(v * (255 - 124))
    return {"x": _n(v, 2), "bg": "rgb(%d,%d,%d)" % (r, g, b), "fg": "#fff" if v >= 0.55 else "#1a1a1a"}


# ── report content ───────────────────────────────────────────────────────────

def _task_order(study, d):
    ids = [t["q"].get("id") for t in _tasks(study) if t["q"].get("id") in d]
    return ids + sorted(k for k in d if k not in ids)


def _task_text(study, tid):
    for t in _tasks(study):
        if t["q"].get("id") == tid:
            return _t(t["q"].get("text"))
    return ""


def _task_label(study, tid):
    tx = _task_text(study, tid)
    return "%s · %s" % (tid, tx) if tx else str(tid)


def _issues_sorted(study):
    an = as_dict(as_dict(study.get("analysis")).get("issues"))
    items = [i for i in as_list(study.get("issues")) if isinstance(i, dict)]

    def k(i):
        pr = as_dict(an.get(i.get("id"))).get("priority")
        sev = i.get("severity") if isinstance(i.get("severity"), int) else -1
        return (-(pr if isinstance(pr, (int, float)) else -1), -sev, str(i.get("id")))
    return sorted(items, key=k)


def _issue_stats(study, iid):
    return as_dict(as_dict(as_dict(study.get("analysis")).get("issues")).get(iid))


def _sev_cell(sev):
    if isinstance(sev, int) and sev in SEVERITY:
        return {"x": "%d %s" % (sev, SEVERITY[sev]), "cls": "sev%d" % sev}
    return DASH


def _freq(study, iid):
    st = _issue_stats(study, iid)
    n = as_dict(study.get("analysis")).get("n")
    if isinstance(st.get("participants"), int) and isinstance(n, int):
        return "%d of %d" % (st["participants"], n)
    return DASH


def _obs_by_id(study):
    return {o.get("id"): o for o in as_list(study.get("observations")) if isinstance(o, dict)}


def _ev_row(study, eid):
    for e in as_list(study.get("evidence")):
        if isinstance(e, dict) and e.get("id") == eid:
            return e
    return {}


def _usability_blocks(study, reg):
    B = []
    ua = as_dict(as_dict(study.get("analysis")).get("usability"))
    tasks = as_dict(ua.get("tasks"))
    if not tasks:
        return [_p("No usability analysis has been computed yet (run the analysis).")]
    order = _task_order(study, tasks)
    ov = as_dict(as_dict(ua.get("overall")).get("success"))
    if ov:
        B.append(_p("Overall task success: %s." % _rate_cell(ov)))
    # success
    rows = [[_task_label(study, t), _n(tasks[t].get("n")), _rate_cell(tasks[t].get("success")),
             _n(tasks[t].get("assisted")), _n(tasks[t].get("abandoned")), _n(tasks[t].get("timeouts"))] for t in order]
    srows = [{"label": _task_label(study, t), "v": _g(tasks[t], "success", "rate"), "lo": _g(tasks[t], "success", "low"),
              "hi": _g(tasks[t], "success", "high"), "text": _pct(_g(tasks[t], "success", "rate"))} for t in order]
    B.append({"t": "chart", "title": "Task success rate, with 95% interval (adjusted Wald)",
              "svg": _svg_bars(srows, 0, 1, [(i / 4.0, "%d%%" % (i * 25)) for i in range(5)], "bar", "Task success rate by task, 0 to 100 percent"),
              "head": ["Task", "n", "Success (x/n, rate, interval)", "Assisted", "Abandoned", "Timed out"], "rows": rows,
              "note": "A success needs the outcome 'success' and no help. Intervals are wide at small n."})
    # time
    trows = [[_task_label(study, t), _n(_g(tasks[t], "time", "n")), _range_cell(tasks[t].get("time"), " s"),
              _n(_g(tasks[t], "time", "median")), _range_cell(tasks[t].get("timeAll"), " s")] for t in order]
    if any(isinstance(_g(tasks[t], "time", "geoMean"), (int, float)) for t in order):
        vals = [(_g(tasks[t], "time", "high") if _g(tasks[t], "time", "high") is not None else _g(tasks[t], "time", "geoMean")) for t in order]
        vmax = _nice_max(max([v for v in vals if isinstance(v, (int, float))] or [1]) * 1.05)
        rws = [{"label": _task_label(study, t), "v": _g(tasks[t], "time", "geoMean"), "lo": _g(tasks[t], "time", "low"),
                "hi": _g(tasks[t], "time", "high"), "text": "%s s" % _n(_g(tasks[t], "time", "geoMean"))} for t in order]
        B.append({"t": "chart", "title": "Time on task (successful attempts), geometric mean with 95% interval, seconds",
                  "svg": _svg_bars(rws, 0, vmax, [(vmax * i / 4.0, _n(vmax * i / 4.0)) for i in range(5)], "bar", "Time on task in seconds by task"),
                  "head": ["Task", "n", "Geometric mean (interval)", "Median s", "All attempts (interval)"], "rows": trows})
    # SEQ
    if any(isinstance(_g(tasks[t], "seq", "mean"), (int, float)) for t in order):
        sq = [{"label": _task_label(study, t), "v": _g(tasks[t], "seq", "mean"), "lo": _g(tasks[t], "seq", "low"),
               "hi": _g(tasks[t], "seq", "high"), "text": _n(_g(tasks[t], "seq", "mean"))} for t in order]
        B.append({"t": "chart", "title": "Single Ease Question per task (1 very difficult to 7 very easy), mean with 95% interval",
                  "svg": _svg_bars(sq, 1, 7, [(i, str(i)) for i in range(1, 8)], "dot", "Single Ease Question mean by task, 1 to 7"),
                  "head": ["Task", "n", "Mean (interval)"],
                  "rows": [[_task_label(study, t), _n(_g(tasks[t], "seq", "n")), _range_cell(tasks[t].get("seq"))] for t in order]})
    # behaviour
    B.append(_h(3, "Behaviour on the page"))
    B.append(_table(["Task", "Clicks (mean)", "Dead clicks (mean / total)", "Rage clicks", "Errors (mean / total)", "Lostness (mean, share lost)"],
                    [[_task_label(study, t), _n(_g(tasks[t], "clicks", "mean")),
                      "%s / %s" % (_n(_g(tasks[t], "deadClicks", "mean")), _n(_g(tasks[t], "deadClicks", "total"))),
                      _n(tasks[t].get("rageClicks")),
                      "%s / %s" % (_n(_g(tasks[t], "errors", "mean")), _n(_g(tasks[t], "errors", "total"))),
                      ("%s, %s" % (_n(_g(tasks[t], "lostness", "mean"), 2), _pct(_g(tasks[t], "lostness", "lostShare")))) if as_dict(tasks[t].get("lostness")) else DASH]
                     for t in order]))
    prow = []
    for t in order:
        for pth in as_list(tasks[t].get("paths")):
            if isinstance(pth, dict):
                prow.append([_task_label(study, t), " > ".join(_t(s) for s in as_list(pth.get("path"))) or DASH, _n(pth.get("count"))])
    if prow:
        B += [_h(3, "Paths taken"), _table(["Task", "Path", "Participants"], prow)]
    # SUS
    sus = ua.get("sus")
    if isinstance(sus, dict) and isinstance(sus.get("mean"), (int, float)):
        B.append({"t": "chart", "title": "System Usability Scale, 0 to 100, with grade (n = %s)" % _n(sus.get("n")),
                  "svg": _svg_gauge(sus["mean"], sus.get("low"), sus.get("high"), sus.get("grade")),
                  "head": ["n", "Mean", "SD", "Interval", "Grade"],
                  "rows": [[_n(sus.get("n")), _n(sus.get("mean")), _n(sus.get("sd")),
                            "%s–%s" % (_n(sus.get("low")), _n(sus.get("high"))) if sus.get("low") is not None else DASH, _d(sus.get("grade"))]],
                  "note": "68 is a commonly cited average from other products; it is context, not a pass mark. The hypotheses' own thresholds decide the verdicts."})
    return B


def _tree_blocks(study, reg):
    tt = as_dict(as_dict(as_dict(study.get("analysis")).get("treeTest")).get("tasks"))
    if not tt:
        return [_p("No tree-test analysis has been computed yet.")]
    labels = _tree_labels(study)
    order = _task_order(study, tt)
    rows, rws = [], []
    for t in order:
        d = tt[t]
        rows.append([_task_label(study, t), _n(d.get("n")), _rate_cell(d.get("success")), _rate_cell(d.get("direct")),
                     _rate_cell(d.get("firstClick")), _n(_g(d, "time", "median"))])
        rws.append({"label": "%s success" % t, "v": _g(d, "success", "rate"), "lo": _g(d, "success", "low"), "hi": _g(d, "success", "high"), "text": _pct(_g(d, "success", "rate"))})
        rws.append({"label": "%s direct" % t, "v": _g(d, "direct", "rate"), "lo": _g(d, "direct", "low"), "hi": _g(d, "direct", "high"), "text": _pct(_g(d, "direct", "rate"))})
    B = [{"t": "chart", "title": "Tree test: success and directness, with 95% interval",
          "svg": _svg_bars(rws, 0, 1, [(i / 4.0, "%d%%" % (i * 25)) for i in range(5)], "bar", "Tree test success and directness by task, 0 to 100 percent"),
          "head": ["Task", "n", "Success", "Direct (no backtracking)", "First click correct", "Median s"], "rows": rows}]
    drows = []
    for t in order:
        for dd in as_list(tt[t].get("destinations")):
            if isinstance(dd, dict):
                drows.append([_task_label(study, t), _t(labels.get(dd.get("node")) or dd.get("node")) or DASH, _n(dd.get("count"))])
    if drows:
        B += [_h(3, "Where people chose"), _table(["Task", "Destination", "Participants"], drows)]
    return B


def _sort_blocks(study, reg):
    cs = as_dict(as_dict(study.get("analysis")).get("cardSort"))
    if not cs:
        return [_p("No card-sort analysis has been computed yet.")]
    labels = _card_labels(study)
    cards = [c for c in as_list(cs.get("cards"))]
    sim = as_dict(cs.get("similarity"))
    B = [_p("Card sort (%s), %s participants. Each cell is the share of participants who put both cards in one group." % (_d(cs.get("kind")), _n(cs.get("n"))))]
    head = [""] + [_short(labels.get(c) or c, 14) for c in cards]
    rows = []
    for a in cards:
        row = [_t(labels.get(a) or a)]
        for b in cards:
            if a == b:
                row.append({"x": DASH})
                continue
            i, j = cards.index(a), cards.index(b)
            k = "%s|%s" % ((a, b) if i < j else (b, a))
            row.append(_heat(sim.get(k)))
        rows.append(row)
    B.append({"t": "chart", "title": "Card similarity (0 never together, 1 always together)", "svg": None, "head": head, "rows": rows,
              "note": "Darker is more often sorted together."})
    cl = [c for c in as_list(cs.get("clusters")) if isinstance(c, list)]
    B.append(_h(3, "Clusters at similarity %s" % _n(cs.get("threshold"), 2) if cs.get("threshold") is not None else "Clusters"))
    if cl:
        B.append({"t": "ul", "items": [", ".join(_t(labels.get(c) or c) for c in grp) for grp in cl]})
    else:
        B.append(_p(DASH))
    cats = as_dict(cs.get("categories"))
    if cats:
        crow = []
        for name in sorted(cats):
            d = as_dict(cats[name])
            top = sorted(as_dict(d.get("cards")).items(), key=lambda kv: (-(kv[1] if isinstance(kv[1], (int, float)) else 0), kv[0]))[:5]
            crow.append([_d(name), _n(d.get("count")), ", ".join("%s (%s)" % (_t(labels.get(c) or c), _pct(v)) for c, v in top) or DASH])
        B += [_h(3, "Categories"), _table(["Category", "Participants", "Cards most often placed here (share)"], crow)]
    return B


def _click_blocks(study, reg):
    fc = as_dict(as_dict(as_dict(study.get("analysis")).get("firstClick")).get("tasks"))
    if not fc:
        return [_p("No first-click analysis has been computed yet.")]
    order = _task_order(study, fc)
    rect = {}
    for t in _tasks(study):
        rect[t["q"].get("id")] = as_dict(as_dict(t["q"].get("click")).get("rect"))
    B = [_table(["Task", "n", "Success (x/n, rate, interval)", "Median s", "Geometric mean s"],
                [[_task_label(study, t), _n(fc[t].get("n")), _rate_cell(fc[t].get("success")), _n(_g(fc[t], "time", "median")), _n(_g(fc[t], "time", "geoMean"))] for t in order])]
    for t in order:
        clicks = [c for c in as_list(fc[t].get("clicks")) if isinstance(c, (list, tuple))]
        B.append({"t": "chart", "title": "First clicks, task %s (circle = hit, cross = miss; dashed box = target)" % t,
                  "svg": _svg_clicks(clicks, rect.get(t), "First click positions for task %s" % t),
                  "head": ["#", "x", "y", "Hit"],
                  "rows": [[str(i), _n(c[0], 3), _n(c[1], 3), "yes" if len(c) > 2 and c[2] else "no"] for i, c in enumerate(clicks, 1) if len(c) >= 2]})
    return B


def _ref_line(study, ref):
    ref = as_dict(ref)
    obs = _obs_by_id(study)
    if "quote" in ref:
        row = _ev_row(study, ref.get("evidence"))
        who = _t(ref.get("participant") or row.get("participant")) or DASH
        return "“%s” — %s (%s)" % (_t(ref.get("quote")), who, _d(ref.get("evidence")))
    if "analysis" in ref:
        return "Number: %s = %s" % (_d(ref.get("analysis")), _n(ref.get("value"), 4))
    if "tally" in ref:
        bits = [_d(ref.get("tally"))]
        for k in ("option", "stat"):
            if ref.get(k) is not None:
                bits.append(_t(ref[k]))
        if ref.get("count") is not None:
            bits.append("%s of %s" % (_n(ref.get("count")), _n(ref.get("of"))))
        elif ref.get("value") is not None:
            bits.append("%s (n = %s)" % (_n(ref.get("value"), 2), _n(ref.get("of"))))
        return "Tally: " + " · ".join(bits)
    if "issue" in ref:
        i = next((x for x in as_list(study.get("issues")) if isinstance(x, dict) and x.get("id") == ref["issue"]), {})
        return "Issue %s: %s" % (_d(ref["issue"]), _d(i.get("title")))
    if "observation" in ref:
        o = as_dict(obs.get(ref["observation"]))
        return "Observation %s (%s, %s): %s" % (_d(ref["observation"]), _d(o.get("participant")), _d(o.get("evidence")), _d(o.get("note") or o.get("quote")))
    return DASH


def _limitations(study):
    out = [_t(x) for x in as_list(as_dict(study.get("report")).get("limitations")) if _t(x)]
    auto = []
    tgt, n = _target_n(study), _n_done(study)
    if isinstance(tgt, int) and n < tgt:
        auto.append("%d of the target %d participants: results are directional, not conclusive." % (n, tgt))
    live = _live_evidence(study)
    unk = [e for e in live if e.get("consent") != "yes"]
    if unk:
        auto.append("Consent is not recorded as given for %d evidence item(s) (%s)." % (len(unk), ", ".join(_t(e.get("id")) for e in unk)))
    srows = _session_rows(study)
    norec = [e for e in srows if not as_dict(e.get("session")).get("recording")]
    if srows and norec:
        auto.append("%d of %d sessions have no screen or voice recording; those findings rest on the event log and notes." % (len(norec), len(srows)))
    ass = sum(v.get("assisted") for v in as_dict(_g(study, "analysis", "usability", "tasks")).values()
              if isinstance(v, dict) and isinstance(v.get("assisted"), int))
    if ass:
        auto.append("%d assisted completion(s) are not counted as successes." % ass)
    if as_list(study.get("pilots")):
        auto.append("%d pilot session(s) were excluded from every number." % len(as_list(study.get("pilots"))))
    dropped = [e for e in as_list(study.get("evidence")) if isinstance(e, dict) and e.get("dropped")]
    if dropped:
        auto.append("%d participant(s) withdrew and are excluded." % len(dropped))
    return out, auto


def _report_blocks(study, reg):
    B = []
    method = study.get("method")
    plan = as_dict(study.get("plan"))
    rep = as_dict(study.get("report"))
    an = as_dict(study.get("analysis"))
    inst = as_dict(study.get("instrument"))
    n, tgt = _n_done(study), _target_n(study)

    B.append(_h(1, _scrub(_title(study))))
    if study.get("status") != "applied":
        B.append({"t": "banner", "x": DRAFT_BANNER})
    B.append({"t": "kv", "rows": [("Study", _d(study.get("id"))), ("Method", _d(method)),
                                  ("Mode", _mode(study) if method in SESSION_METHODS else DASH),
                                  ("Dates", _dates(study)),
                                  ("Participants", "%s of target %s" % (n, _n(tgt))),
                                  ("Status", _d(study.get("status")))]})

    # 1 Summary
    B.append(_h(2, "1. Summary"))
    B.append(_p(_d(rep.get("summary"))))
    iss = _issues_sorted(study)[:3]
    B.append(_h(3, "Top issues by priority"))
    if iss:
        B.append({"t": "ol", "items": ["%s — severity %s, %s participants" % (_d(i.get("title")), _d(i.get("severity")), _freq(study, i.get("id"))) for i in iss]})
    else:
        B.append(_p("No issues recorded."))
    B.append(_h(3, "Hypothesis verdicts"))
    hs = _hyp(study)
    B.append(_table(["Hypothesis", "Verdict"], [[_t("%s %s" % (h.get("id"), h.get("statement"))), _d(h.get("verdict"))] for h in hs]) if hs else _p(DASH))

    # 2 Research questions
    B.append(_h(2, "2. Research questions and what we learned"))
    rqs = as_list(plan.get("researchQuestions")) or ([study.get("question")] if _squash(study.get("question")) else [])
    B.append({"t": "ul", "items": [_t(q) for q in rqs if _t(q)]} if rqs else _p(DASH))
    if _squash(plan.get("decision")):
        B.append(_p("Decision this informs: %s" % _t(plan.get("decision"))))
    if hs:
        B.append(_table(["Id", "Hypothesis", "Supported if", "Refuted if", "Verdict", "Why"],
                        [[_d(h.get("id")), _d(h.get("statement")), _d(h.get("supportedIf")), _d(h.get("refutedIf")), _d(h.get("verdict")), _d(h.get("why"))] for h in hs]))

    # 3 Method and participants
    B.append(_h(2, "3. Method and participants"))
    B.append(_p(_d(plan.get("methodRationale"))))
    srows = _session_rows(study)
    rec_n = sum(1 for e in srows if as_dict(e.get("session")).get("recording"))
    kv = [("Method", _d(method)), ("Mode", _mode(study) if method in SESSION_METHODS else DASH),
          ("Device", _d(inst.get("device"))),
          ("Pilot sessions excluded", str(len(as_list(study.get("pilots")))))]
    if method in SESSION_METHODS:
        kv.append(("Sessions with recording", "%d of %d" % (rec_n, len(srows)) if srows else DASH))
    B.append({"t": "kv", "rows": kv})
    ts = _tasks(study)
    if ts:
        B.append(_h(3, "Tasks"))
        B.append({"t": "ol", "items": ["%s — %s" % (_d(t["q"].get("id")), _d(t["q"].get("text"))) for t in ts]})
    parts = [p for p in as_list(study.get("participants")) if isinstance(p, dict) and not p.get("pilot")]
    prow = [[_d(p.get("id")), _d(p.get("segment")), _d(p.get("role")), _d(p.get("status"))] for p in sorted(parts, key=lambda x: str(x.get("id")))]
    if not prow:
        seen = {}
        for e in _live_evidence(study):
            if e.get("participant") and e["participant"] not in seen:
                seen[e["participant"]] = e
        prow = [[_d(k), _d(v.get("segment")), _d(v.get("role")), DASH] for k, v in sorted(seen.items())]
    B.append(_h(3, "Participants (by code)"))
    B.append(_table(["Participant", "Segment", "Role", "Status"], prow) if prow else _p(DASH))

    # 4 Results
    B.append(_h(2, "4. Results"))
    if method == "usability":
        B += _usability_blocks(study, reg)
    elif method == "tree-test":
        B += _tree_blocks(study, reg)
    elif method == "card-sort":
        B += _sort_blocks(study, reg)
    elif method == "first-click":
        B += _click_blocks(study, reg)
    else:
        B.append(_p("This method's numbers are in the findings below (n = %s)." % n))
    ans = as_dict(an.get("answers"))
    arows = []
    qtext = {q.get("id"): q.get("text") for _s, q in _questions(study)}
    for k in sorted(ans):
        d = as_dict(ans[k])
        if isinstance(d.get("n"), int) or isinstance(d.get("mean"), (int, float)):
            arows.append([_d(qtext.get(k) or k), _n(d.get("n")), _n(d.get("mean"), 2)])
    if arows:
        B += [_h(3, "Answers to the other questions"), _table(["Question", "n", "Mean"], arows)]

    # 5 Findings
    B.append(_h(2, "5. Findings"))
    fs = [f for f in as_list(study.get("findings")) if isinstance(f, dict)]
    if not fs:
        B.append(_p("No findings recorded."))
    for f in fs:
        B.append(_h(3, _d(f.get("id"))))
        B.append(_p(_d(f.get("text"))))
        if as_list(f.get("hypotheses")):
            B.append(_p("Bears on: %s" % ", ".join(_t(x) for x in f["hypotheses"])))
        refs = as_list(f.get("evidence"))
        if refs:
            B.append({"t": "ul", "items": [_ref_line(study, r) for r in refs]})

    # 6 Issues
    B.append(_h(2, "6. Usability issues"))
    issues = _issues_sorted(study)
    if not issues:
        B.append(_p("None recorded."))
    else:
        rows = []
        for r, i in enumerate(issues, 1):
            st = _issue_stats(study, i.get("id"))
            rows.append([str(r), _d(i.get("id")), _d(i.get("title")), _sev_cell(i.get("severity")), _freq(study, i.get("id")),
                         _n(st.get("priority"), 2), _d(i.get("task")), _d(i.get("screen"))])
        B.append(_table(["Rank", "Id", "Issue", "Severity", "Frequency", "Priority", "Task", "Screen"], rows))
        obs = _obs_by_id(study)
        items = []
        for i in issues:
            bits = ["%s: %s" % (_d(i.get("id")), _d(i.get("title")))]
            ev = []
            for oid in as_list(i.get("observations")):
                o = as_dict(obs.get(oid))
                ev.append("%s (%s: %s)" % (_d(oid), _d(o.get("participant")), _d(o.get("note") or o.get("quote"))))
            if ev:
                bits.append("Observations: " + "; ".join(ev))
            bits.append("Recommendation: %s" % _d(i.get("recommendation")))
            items.append(" — ".join(bits))
        B.append({"t": "ul", "items": items})

    # 7 Themes
    B.append(_h(2, "7. Themes"))
    th = [t for t in as_list(study.get("themes")) if isinstance(t, dict)]
    if th:
        B.append(_table(["Theme", "Tags", "Insight"], [[_d(t.get("title")), ", ".join(_t(x) for x in as_list(t.get("tags"))) or DASH, _d(t.get("insight"))] for t in th]))
    else:
        B.append(_p("None recorded."))
    tags = as_dict(as_dict(an.get("affinity")).get("tags"))
    if tags:
        B.append(_h(3, "Tags by observations and participants"))
        B.append(_table(["Tag", "Observations", "Participants", "Tasks"],
                        [[_d(k), _n(as_dict(tags[k]).get("observations")), _n(as_dict(tags[k]).get("participants")),
                          ", ".join(_t(x) for x in as_list(as_dict(tags[k]).get("tasks"))) or DASH] for k in sorted(tags)]))

    # 8 Recommendations
    B.append(_h(2, "8. Recommendations and next steps"))
    recs = [r for r in as_list(rep.get("recommendations")) if isinstance(r, dict)]
    if recs:
        B.append(_table(["Recommendation", "Issues", "Route"], [[_d(r.get("text")), ", ".join(_t(x) for x in as_list(r.get("issues"))) or DASH, _d(r.get("route"))] for r in recs]))
    else:
        B.append(_p("None recorded."))
    ns = [x for x in as_list(rep.get("nextSteps")) if _t(x)]
    B.append(_h(3, "Next steps"))
    B.append({"t": "ul", "items": [_t(x) for x in ns]} if ns else _p(DASH))

    # 9 Limitations
    B.append(_h(2, "9. Limitations"))
    own, auto = _limitations(study)
    allx = own + auto
    B.append({"t": "ul", "items": allx} if allx else _p(DASH))

    # Appendix
    B.append(_h(2, "Appendix"))
    B.append(_h(3, "A. Plan"))
    pp = as_dict(plan.get("participants"))
    sc = as_dict(plan.get("schedule"))
    rc = as_dict(plan.get("recruitment"))
    B.append({"t": "kv", "rows": [("Background", _d(plan.get("background"))),
                                  ("Objectives", "; ".join(_t(x) for x in as_list(plan.get("objectives")) if _t(x)) or DASH),
                                  ("Criteria", "; ".join(_t(x) for x in as_list(pp.get("criteria")) if _t(x)) or DASH),
                                  ("Excluded", "; ".join(_t(x) for x in as_list(pp.get("exclude")) if _t(x)) or DASH),
                                  ("Recruitment", _d(rc.get("channel"))),
                                  ("Schedule", "%s to %s" % (_d(sc.get("start")), _d(sc.get("end"))))]})
    B.append(_h(3, "B. Tasks"))
    if ts:
        rows = []
        for t in ts:
            q = t["q"]
            tk = as_dict(q.get("task"))
            rows.append([_d(q.get("id")), _d(q.get("text")), _d(tk.get("screen") or as_dict(q.get("click")).get("screen")), _d(tk.get("success"))])
        B.append(_table(["Id", "Scenario", "Start screen", "Success definition"], rows))
    else:
        B.append(_p(DASH))
    B.append(_h(3, "C. Instrument summary"))
    srows_i = []
    for sec in as_list(inst.get("sections")):
        if isinstance(sec, dict):
            srows_i.append([_d(sec.get("title")), _d(sec.get("purpose")), str(len([q for q in as_list(sec.get("questions")) if isinstance(q, dict)]))])
    B.append(_table(["Section", "Purpose", "Questions"], srows_i) if srows_i else _p(DASH))
    B.append(_h(3, "D. Evidence index"))
    ev = [e for e in as_list(study.get("evidence")) if isinstance(e, dict)]
    B.append(_table(["Id", "Kind", "Date", "Participant", "SHA-256 (first 12)", "Status"],
                    [[_d(e.get("id")), _d(e.get("kind")), _d(e.get("date")), _d(e.get("participant")),
                      _squash(e.get("sha256"))[:12] and re.sub(r"[^0-9a-f]", "", _squash(e.get("sha256")).lower())[:12] or DASH,
                      "dropped" if e.get("dropped") else "live"] for e in ev]) if ev else _p(DASH))
    return B


# ── Markdown renderer ────────────────────────────────────────────────────────

def _md_table(head, rows):
    out = ["| %s |" % " | ".join(_md_cell(h) if h else " " for h in head), "|%s|" % "|".join("---" for _ in head)]
    for r in rows:
        out.append("| %s |" % " | ".join(_md_cell(c) for c in r))
    return out


def report_md(study, reg):
    L = []
    for b in _report_blocks(study, reg):
        t = b["t"]
        if t == "h":
            L += ["", "%s %s" % ("#" * b["l"], _mx(b["x"])), ""]
        elif t == "p":
            L += [_mx(b["x"]), ""]
        elif t == "banner":
            L += ["> **%s**" % _mx(b["x"]), ""]
        elif t == "ul":
            L += ["- %s" % _mx(i) for i in b["items"]] + [""]
        elif t == "ol":
            L += ["%d. %s" % (n, _mx(i)) for n, i in enumerate(b["items"], 1)] + [""]
        elif t == "kv":
            L += ["- **%s:** %s" % (_mx(k), _mx(v)) for k, v in b["rows"]] + [""]
        elif t == "table":
            L += _md_table(b["head"], b["rows"]) + [""]
        elif t == "chart":
            L += ["**%s**" % _mx(b["title"]), ""] + _md_table(b["head"], b["rows"])
            if b.get("note"):
                L += ["", "_%s_" % _mx(b["note"])]
            L.append("")
    text = "\n".join(L).strip("\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text + "\n"


# ── HTML renderer ────────────────────────────────────────────────────────────

CSS = """
:root{color-scheme:light;--ink:#1a1a1a;--mute:#555;--line:#d6d6d6;--wash:#f5f6f8;--accent:#1f4e7c;--bar:#8fb2d6;--warn:#8a4b00}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
main.doc{max-width:860px;margin:0 auto;padding:32px 24px 64px}
h1{font-size:28px;line-height:1.2;margin:0 0 12px}
h2{font-size:20px;margin:36px 0 10px;padding-top:10px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:22px 0 6px}
p{margin:0 0 10px}
ul,ol{margin:0 0 12px;padding-left:22px}
li{margin:2px 0}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:13px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--wash);font-weight:600}
td.heat{text-align:center;font-variant-numeric:tabular-nums}
dl.kv{display:grid;grid-template-columns:max-content 1fr;gap:3px 16px;margin:0 0 12px}
dl.kv dt{color:var(--mute)}dl.kv dd{margin:0}
.banner{border:1px solid var(--warn);background:#fff6e8;color:var(--warn);padding:8px 12px;margin:0 0 14px;font-weight:600;border-radius:4px}
figure.chart{margin:16px 0;padding:0;break-inside:avoid}
figure.chart figcaption{font-weight:600;margin-bottom:6px}
figure.chart p.note{color:var(--mute);font-size:12px;margin:0 0 6px}
.chart-svg{display:block;height:auto}
.chart-svg text{font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;fill:#1a1a1a}
.chart-svg .ax{fill:#555;font-size:11px}
.chart-svg .g{stroke:#e2e2e2;stroke-width:1}
.chart-svg .bar{fill:var(--bar)}
.chart-svg .dot{fill:var(--accent)}
.chart-svg .wh{stroke:#14304d;stroke-width:1.5}
.chart-svg .b1{fill:#f3d6d2}.chart-svg .b2{fill:#f6ead0}.chart-svg .b3{fill:#dfeccf}.chart-svg .b4{fill:#c9e3c4}
.chart-svg .avg{stroke:#555;stroke-width:1.5;stroke-dasharray:3 2}
.chart-svg .mk{fill:var(--accent)}
.chart-svg .scr{fill:#fafafa;stroke:#999}
.chart-svg .tgt{fill:none;stroke:var(--accent);stroke-width:1.5;stroke-dasharray:4 3}
.chart-svg .hit{fill:#2e7d32;stroke:#fff;stroke-width:1}
.chart-svg .miss{stroke:#b3261e;stroke-width:1.8;fill:none}
.chip{display:inline-block;padding:1px 8px;border-radius:10px;font-weight:600;font-size:12px;border:1px solid var(--line)}
.sev0,.sev1{background:#eef2f6}.sev2{background:#fdf3d0}.sev3{background:#fbdcc2}.sev4{background:#f6c7c3}
blockquote{margin:0 0 10px;padding-left:12px;border-left:3px solid var(--line);color:var(--mute)}
@page{margin:16mm}
@media print{body{font-size:11pt}main.doc{max-width:none;padding:0}h2{break-after:avoid}h3{break-after:avoid}table,figure.chart,tr{break-inside:avoid}.banner{border-width:2px}}
"""


def _h_cell(c, tag="td"):
    if isinstance(c, dict):
        x, cls, bg, fg = c.get("x", ""), c.get("cls"), c.get("bg"), c.get("fg")
        style = ' style="background:%s;color:%s"' % (_e(bg), _e(fg or "#1a1a1a")) if bg else ""
        if cls and str(cls).startswith("sev"):
            return "<%s><span class=\"chip %s\">%s</span></%s>" % (tag, _e(cls), _e(x), tag)
        return "<%s%s%s>%s</%s>" % (tag, ' class="heat"' if bg else "", style, _e(x) or DASH, tag)
    return "<%s>%s</%s>" % (tag, _e(c) or DASH, tag)


def _h_table(head, rows):
    out = ["<table><thead><tr>%s</tr></thead><tbody>" % "".join("<th scope=\"col\">%s</th>" % _e(h) for h in head)]
    for r in rows:
        out.append("<tr>%s</tr>" % "".join(_h_cell(c) for c in r))
    out.append("</tbody></table>")
    return "".join(out)


def report_html(study, reg):
    parts = []
    for b in _report_blocks(study, reg):
        t = b["t"]
        if t == "h":
            parts.append("<h%d>%s</h%d>" % (b["l"], _e(b["x"]), b["l"]))
        elif t == "p":
            parts.append("<p>%s</p>" % _e(b["x"]))
        elif t == "banner":
            parts.append('<div class="banner" role="note">%s</div>' % _e(b["x"]))
        elif t in ("ul", "ol"):
            parts.append("<%s>%s</%s>" % (t, "".join("<li>%s</li>" % _e(i) for i in b["items"]), t))
        elif t == "kv":
            parts.append('<dl class="kv">%s</dl>' % "".join("<dt>%s</dt><dd>%s</dd>" % (_e(k), _e(v)) for k, v in b["rows"]))
        elif t == "table":
            parts.append(_h_table(b["head"], b["rows"]))
        elif t == "chart":
            f = ['<figure class="chart"><figcaption>%s</figcaption>' % _e(b["title"])]
            if b.get("note"):
                f.append('<p class="note">%s</p>' % _e(b["note"]))
            if b.get("svg"):
                f.append(b["svg"])
            f.append(_h_table(b["head"], b["rows"]))
            f.append("</figure>")
            parts.append("".join(f))
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>%s</title>\n<style>%s</style>\n</head>\n'
            '<body>\n<main class="doc">\n%s\n</main>\n</body>\n</html>\n' % (_e(_title(study)), CSS, "\n".join(parts)))
