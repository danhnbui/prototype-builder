#!/usr/bin/env python3
"""
research.py — the executable form of /pb:research (v2.6.0). Stdlib only.

Find what a prototype is unsure about, write a survey, an interview guide or a UX test (usability, tree test,
card sort, first click) that tests it, keep what comes back as evidence on disk, and refill the Project
Summary's User Insights from it — with every number computed by this tool and every quote checked word for
word against the raw file. pb hosts nothing online: the instrument is fielded elsewhere (a CSV or a transcript
comes back), or run on the researcher's own machine through the /pb:preview server, or sent as one HTML
participant kit whose session file comes back. The model NEVER simulates respondents and NEVER writes evidence.

Six methods: survey · interview (asked elsewhere) and the four SESSION methods usability · tree-test ·
card-sort · first-click, which run in a browser on the prototype (research_session.py, the page scripts) and
store `pb-session` files as evidence (kind `session`, plus a linked `recording` when the participant agreed).

State is the optional `research` slice of registry.json (absent = empty state, no schema bump):

    research = { populated, studies: [ { id, title, question, method, status, scope, setup, audience,
                 targets, hypotheses, instrument, biasReview?, evidence, tally?, findings, refill?,
                 refilled?, gates,
                 plan?, participants?, logistics?, pilots?,                    (the research plan, the tracker, the checklist)
                 analysis?, observations?, themes?, issues?, report? } ] }    (session methods; analysis is the tool's alone)

and, per study, files under memory/research/<id>/:

    instrument/survey.md · responses-template.csv     (survey)
    instrument/interview-guide.md                     (interview)
    instrument/plan.md · moderator-guide.md · tasks.md · cards.md · consent.md · screener.md · note-taking.csv
                                                      (research_report.files_for: generated at G-STUDY, rewritten by export)
    instrument/bias-review.md                         (review-plan: the questions only, for a reviewer who knows nothing else)
    evidence/e1-<name>.<ext> …                        read-only (chmod 444), hashed, never edited
    evidence/e<N>-<sessionId>.json · …-screen.webm    a stored session and its recording
    pilot/<sessionId>.json                            a rehearsal: never evidence, never analysed
    kit/<id>-kit.html                                 the participant kit (one self-contained file)
    report/report.md · report.html                    the study report (a Draft until G-INSIGHT)

Scope (per study, the user's call): `instrument` = the user wants the questions and the setup and the study
legitimately ends at `approved` (import is refused); `collect` = results will come back. `setup` is free text
(the survey tool, the panel, where results live): it is stored on the study and never written into an exported
file. A study with no `scope` key behaves as `collect` (no migration).

Standard metrics: a plan question may be {"id","template":"ces|seq|csat|nps|sus","subject"?,"tests"?}.
`plan` expands it with fixed wording and scale (sus: the ten Brooke items, ids <id>-1 .. <id>-10, each
carrying `templateItem`) and keeps `template`. `tally` scores a survey (byQuestion.<id>.score, SUS under
the base id) and `verify` recomputes a {"tally","stat":<template>,"value","of"} citation. An interview
reads a template question aloud and does not score it. A translated `text` (lang other than en) is accepted
and draws W-TEMPLATE-TEXT: the translated wording is not validated.

Bias review: `review-plan` writes bias-review.md (each question's text, type, options and scale, its
section purpose and order, and yes/no items; no hypothesis, threshold, target, title or study question),
a fresh reviewer answers it, `review` stores the rows with the instrument hash, and `approve` demands a
review of the current instrument (or --skip-review "<reason>") and --accept-review "<why>" when any row is
`no` or `blocked`. `plan` clears the review.

Subcommands (all take --registry PATH, default ./registry.json, and --json):

  gaps [--role R]                 read-only: the ranked list of what is unsure
  seed <kind:id>...               read-only: the job / story / rule / screen facts a question is written from
  methods                         read-only: the method catalog (what each answers, sample size, minutes, what it is not for)
  init <id> --method survey|interview|usability|tree-test|card-sort|first-click --scope instrument|collect
        [--setup T] --question Q [--title T] [--role R]... [--segment S] [--target kind:id]... [--target-n N]
        [--mode moderated|unmoderated|both]
                                  a draft study; it always names who it asks; seeds the logistics checklist
  scope <id> [--scope S] [--setup T]    change the scope and/or setup at any time; writes no gate
  brief <id> --file F             merge the research plan {background, objectives, researchQuestions, decision, methodRationale,
                                  participants, recruitment, schedule, team, materials, risks, timeline, budget} into study.plan;
                                  unknown keys refused; on an approved study a change to objectives / researchQuestions / decision /
                                  methodRationale / participants withdraws G-STUDY (the logistics keys do not)
  plan <id> --file F              merge {hypotheses, instrument, audience?, plan?}; refused once evidence exists;
                                  expands template questions; clears any bias review
  check <id>                      lint the study (errors block G-STUDY; warnings are heuristics)
  review-plan <id>                write instrument/bias-review.md (deterministic; questions only)
  review <id> --file ROWS         store the reviewer's rows: <item id> · yes|no|blocked · <evidence>
  approve <id> [--note N] [--skip-review R] [--accept-review W]
                                  G-STUDY: check must be clean and a review of this instrument stored
                                  (or --skip-review); a `no`/`blocked` row needs --accept-review;
                                  writes the instrument files and ticks the plan-approved checklist item
  export <id>                     rewrite the instrument files (deterministic; no timestamps)
  participant <id> <P01> [--status S] [--segment T] [--role R] [--at WHEN] [--incentive due|paid|none] [--pilot|--no-pilot]
        [--note T] [--remove]     the pseudonymous tracker; an email or phone in free text is refused
  logistics <id> [--done ID]... [--undo ID]... [--add TEXT]
                                  the checklist, the participant pipeline by status and the schedule
  pilots <id>                     the rehearsal sessions (never evidence)
  kit <id> [--out PATH] [--pilot] the participant kit: one HTML file to send (unmoderated), with what to send and how results come back
  link <id> [--observer] [--participant P] [--pilot] [--open]
                                  the session URL on the /pb:preview server (found or started), checked to answer 200
  import <id> <file> --kind K --consent yes|unknown|no [--participant P] [--role R] [--segment S]
        [--date D] [--drop-columns A,B] [--keep-pii] [--session S]
                                  store evidence (copy, chmod 444, sha256). `--kind session` stores a pb-session file (consent yes);
                                  `--kind recording --session <sessionId>` links a screen recording to a stored session
  drop-evidence <id> <eid> --reason R   a participant withdrew: delete the file, keep the row + hash (a session takes its recording)
  tally <id> [--by qN]            survey: every count and mean, computed here
  analyze <id>                    session methods: success rates with intervals, times, lostness, SEQ, SUS, tree / sort / click
                                  results — computed here from the stored sessions, stored in study.analysis
  affinity <id>                   read-only: tag x participant counts over the observations
  synthesize <id> --file F        merge {verdicts, findings, refill, observations, themes, issues, report}; tally (survey) or
                                  analyze (session methods) first, then verify
  verify <id>                     every quote verbatim, every hash, every cited number recomputed; for the session methods the
                                  analysis is recomputed from the evidence and every `{"analysis": path, "value": n}` checked
  report <id>                     refused unless verify is clean; writes report/report.md and report.html (Draft until G-INSIGHT)
  refill <id> --approved [--note N]     G-INSIGHT: append the refill text to meta.userInsights.*; rewrites an existing report
  list · show <id>                read-only

Every registry write holds slice.registry_lock and goes through slice._write (atomic).

Exit: 0 ok · 1 refused / a check failed · 2 usage or missing input
"""
import argparse
import contextlib
import csv
import datetime
import hashlib
import importlib
import io
import json
import math
import os
import posixpath
import re
import shutil
import stat
import sys
import unicodedata
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if __name__ == "__main__":
    # research_analysis does `import research`: give it THIS module, not a second copy with a ResearchError
    # of its own that main() would not catch.
    sys.modules.setdefault("research", sys.modules[__name__])

import security_scan  # noqa: E402
# The registry's write path (advisory lock + atomic write). importlib because `import slice` would
# shadow the builtin of the same name in this module — explore.py and serve.py do the same.
pbslice = importlib.import_module("slice")

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

STUDY_ID = re.compile(r"^rs-[a-z0-9-]+\Z")
ITEM_ID = re.compile(r"^[a-z][a-z0-9_-]*\Z")
METHODS = ("survey", "interview", "usability", "tree-test", "card-sort", "first-click")
SESSION_METHODS = ("usability", "tree-test", "card-sort", "first-click")    # these produce `session` evidence
METHOD_LABELS = {"survey": "Survey", "interview": "Interview", "usability": "Usability test", "tree-test": "Tree test",
                 "card-sort": "Card sort", "first-click": "First-click test"}
STATUSES = ("draft", "approved", "fielding", "analysed", "applied")
TARGET_KINDS = ("job", "story", "rule", "screen", "component", "feature")
PURPOSES = ("screener", "warmup", "main", "task", "closing")
QTYPES = ("single", "multi", "scale", "number", "text")
EVIDENCE_KINDS = ("responses", "transcript", "notes", "recording", "session", "other")
CONSENTS = ("yes", "unknown")
VERDICTS = ("supported", "refuted", "mixed", "inconclusive")
REFILL_KEYS = ("quantitative", "researchSummary", "executiveSummary")
TEXT_EXTS = (".csv", ".tsv", ".txt", ".md", ".markdown", ".json", ".vtt", ".srt", ".log")
OTHER = "(other)"
DEFAULT_N = {"survey": 30, "interview": 5, "usability": 5, "tree-test": 50, "card-sort": 15, "first-click": 30}
MODES = ("moderated", "unmoderated", "both")
PARTICIPANT_ID = re.compile(r"^P[0-9]{2,3}\Z")
PARTICIPANT_STATUSES = ("invited", "screened", "scheduled", "done", "no-show", "withdrawn", "excluded")
INCENTIVES = ("due", "paid", "none")
TAG = re.compile(r"^[a-z0-9][a-z0-9-]*\Z")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}\Z")
ISO_AT = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?\Z")
ROUTES = ("clarify", "explore", "build", "none")
GAP_BASE = 30
SCOPES = ("instrument", "collect")
TEMPLATES = ("ces", "seq", "csat", "nps", "sus")
# (min, max, minLabel, maxLabel) — fixed: a score is only comparable on the standard scale.
TEMPLATE_SCALES = {"ces": (1, 7, "Strongly disagree", "Strongly agree"),
                   "seq": (1, 7, "Very difficult", "Very easy"),
                   "csat": (1, 5, "Very dissatisfied", "Very satisfied"),
                   "nps": (0, 10, "Not at all likely", "Extremely likely"),
                   "sus": (1, 5, "Strongly disagree", "Strongly agree")}
# The System Usability Scale (Brooke, 1996), item order and wording as published. Odd items are
# positive, even items negative; the score depends on that order.
SUS_ITEMS = ("I think that I would like to use this system frequently.",
             "I found the system unnecessarily complex.",
             "I thought the system was easy to use.",
             "I think that I would need the support of a technical person to be able to use this system.",
             "I found the various functions in this system were well integrated.",
             "I thought there was too much inconsistency in this system.",
             "I would imagine that most people would learn to use this system very quickly.",
             "I found the system very cumbersome to use.",
             "I felt very confident using the system.",
             "I needed to learn a lot of things before I could get going with this system.")
# type + scale are tolerated so an already-expanded question can be planned again; they are replaced by the standard ones.
TEMPLATE_KEYS = {"id", "template", "subject", "text", "tests", "required", "probes", "type", "scale"}
REVIEW_ANSWERS = ("yes", "no", "blocked")


class ResearchError(Exception):
    """A refusal (exit 1) or a missing input (exit 2). `data` rides into --json output."""

    def __init__(self, msg, code=EXIT_FAIL, data=None):
        Exception.__init__(self, msg)
        self.code = code
        self.data = data or {}


# ── small helpers ────────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else ""


def squash(s):
    """NFC and collapsed whitespace — how a quote and its source are compared."""
    return re.sub(r"\s+", " ", nfc(s)).strip()


def key(s):
    return squash(s).casefold()


def sstr(x):
    return x if isinstance(x, str) else ""


def as_list(x):
    return x if isinstance(x, list) else []


def as_dict(x):
    return x if isinstance(x, dict) else {}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def slug(s, n=60):
    s = re.sub(r"[^a-z0-9]+", "-", key(s)).strip("-")
    return s[:n].strip("-")


# The four UX modules are imported on first use, never at load: research_session and research_analysis reach
# back into this module (lazily, too), so a top-level import here would be a cycle.

def _rs():
    return importlib.import_module("research_session")


def _ra():
    return importlib.import_module("research_analysis")


def _rr():
    return importlib.import_module("research_report")


def _rm():
    return importlib.import_module("research_methods")


def _explore():
    return importlib.import_module("explore")


# ── registry access ──────────────────────────────────────────────────────────

def load_registry(reg_path):
    try:
        with open(reg_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ResearchError("registry not found: %s" % reg_path, EXIT_USAGE)
    except ValueError as e:
        raise ResearchError("registry is not valid JSON: %s" % e, EXIT_USAGE)


def base_of(reg_path):
    return os.path.dirname(os.path.abspath(reg_path))


@contextlib.contextmanager
def locked(reg_path, who):
    """The registry, read inside its write lock. The caller writes with pbslice._write while still inside."""
    if not os.path.isfile(reg_path):
        raise ResearchError("registry not found: %s" % reg_path, EXIT_USAGE)
    try:
        with pbslice.registry_lock(reg_path, who):
            yield load_registry(reg_path)
    except pbslice.RegistryLocked as e:
        raise ResearchError(str(e))


def studies_of(reg):
    r = reg.get("research")
    return [s for s in as_list(r.get("studies")) if isinstance(s, dict)] if isinstance(r, dict) else []


def find_study(reg, sid):
    for s in studies_of(reg):
        if s.get("id") == sid:
            return s
    raise ResearchError("no study %r in the registry" % sid, EXIT_USAGE)


def role_ids(reg):
    out = []
    for r in as_list(as_dict(reg.get("meta")).get("roles")):
        i = r.get("id") if isinstance(r, dict) else r
        if isinstance(i, str) and i:
            out.append(i)
    return out


def jobs_of(reg):
    return [j for j in as_list(as_dict(reg.get("ia")).get("jobs")) if isinstance(j, dict)]


def rules_of(reg):
    return [r for r in as_list(as_dict(reg.get("ia")).get("rules")) if isinstance(r, dict)]


def stories_of(reg):
    return [s for s in as_list(as_dict(reg.get("flow")).get("stories")) if isinstance(s, dict)]


def screens_of(reg):
    return [s for s in as_list(reg.get("screens")) if isinstance(s, dict)]


def components_of(reg):
    return [s for s in as_list(reg.get("components")) if isinstance(s, dict)]


def entries_of(reg):
    return [e for e in as_list(as_dict(as_dict(reg.get("meta")).get("demo")).get("entries")) if isinstance(e, dict)]


# ── targets ──────────────────────────────────────────────────────────────────

def parse_target(s):
    k, sep, i = s.partition(":")
    if not sep or k not in TARGET_KINDS or not i.strip():
        raise ResearchError("target %r is not <kind>:<id> with kind one of %s" % (s, "|".join(TARGET_KINDS)),
                            EXIT_USAGE)
    return {"kind": k, "id": i.strip()}


def target_problem(reg, t):
    """None when the target resolves; else the reason. `feature` is free text and always resolves."""
    if not isinstance(t, dict):
        return "a target must be an object {kind, id}"
    k, i = t.get("kind"), t.get("id")
    if k not in TARGET_KINDS or not isinstance(i, str) or not i.strip():
        return "target %r needs a kind (%s) and an id" % (t, "|".join(TARGET_KINDS))
    if k == "feature":
        return None
    pool = {"job": [j.get("id") for j in jobs_of(reg)],
            "story": [x for s in stories_of(reg) for x in (s.get("id"), s.get("title"))],
            "rule": [r.get("id") for r in rules_of(reg)],
            "screen": [s.get("id") for s in screens_of(reg)],
            "component": [c.get("id") for c in components_of(reg)]}[k]
    return None if i in pool else "target %s:%s does not resolve in this registry" % (k, i)


def target_str(t):
    return "%s:%s" % (t.get("kind"), t.get("id")) if isinstance(t, dict) else str(t)


# ── paths and files on disk ──────────────────────────────────────────────────

def study_rel(sid):
    return "memory/research/%s" % sid


def evidence_dir_rel(sid):
    return "%s/evidence" % study_rel(sid)


def under(base, rel):
    """base/rel, refused if it climbs out of base (a `..`, an absolute path, or a symlinked parent)."""
    if os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        raise ResearchError("unsafe path %r" % rel)
    p = os.path.join(base, *rel.split("/"))
    root = os.path.realpath(base)
    real = os.path.realpath(os.path.dirname(p))
    if real != root and not real.startswith(root + os.sep):
        raise ResearchError("path %r leaves the project" % rel)
    return p


def ensure_dir(base, rel):
    """Create base/rel one segment at a time, refusing a symlink anywhere in it."""
    cur = base
    for seg in rel.split("/"):
        cur = os.path.join(cur, seg)
        if os.path.islink(cur):
            raise ResearchError("%s is a symlink — refusing to write through it" % os.path.relpath(cur, base))
        if not os.path.isdir(cur):
            os.mkdir(cur)
    return cur


def read_nofollow(path):
    """The bytes of a regular file, never through a symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        chunks = []
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            chunks.append(b)
        return b"".join(chunks)
    finally:
        os.close(fd)


def write_exclusive(path, data):
    """Create a NEW file, 0444 once written. Never overwrites, never follows a symlink."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(path)
        raise
    os.chmod(path, 0o444)


def safe_name(path):
    """A file name safe to keep: ASCII letters, digits, dot, dash, underscore; never a `..`."""
    b = os.path.basename(sstr(path).replace("\\", "/"))
    b = unicodedata.normalize("NFKD", nfc(b)).replace("đ", "d").replace("Đ", "D")
    b = "".join(c for c in b if not unicodedata.combining(c))
    stem, ext = os.path.splitext(b)
    ext = "." + re.sub(r"[^A-Za-z0-9]", "", ext)[:8].lower() if re.sub(r"[^A-Za-z0-9]", "", ext) else ""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem)
    stem = re.sub(r"\.{2,}", ".", stem).strip("-._")[:60].strip("-._")
    return (stem or "file") + ext


def decode_text(raw, name):
    """The text of a text file (UTF-8, BOM tolerated), or None for a file that is opaque to pb."""
    if raw is None or os.path.splitext(name)[1].lower() not in TEXT_EXTS or b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


# ── CSV ──────────────────────────────────────────────────────────────────────

def _first_record(text, delim):
    try:
        return next(csv.reader(io.StringIO(text, newline=""), delimiter=delim), [])
    except csv.Error:
        return []


def parse_csv(text):
    """(delimiter, header, rows). Comma, semicolon or tab, whichever splits the header most."""
    best, width = ",", 0
    for d in (",", ";", "\t"):
        w = len(_first_record(text, d))
        if w > width:
            best, width = d, w
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=best))
    except csv.Error as e:
        raise ResearchError("cannot read the CSV: %s" % e)
    if not rows or not any(c.strip() for c in rows[0]):
        raise ResearchError("the CSV has no header row")
    return best, rows[0], rows[1:]


PII_PHRASES = ("họ và tên", "họ tên", "số điện thoại", "địa chỉ", "full name", "first name", "last name",
               "phone number", "email address", "e-mail")
PII_TOKENS = ("email", "mail", "name", "phone", "mobile", "telephone", "address", "tên", "sđt", "sdt")


def looks_pii(header):
    k = key(header)
    return any(p in k for p in PII_PHRASES) or any(t in PII_TOKENS for t in re.findall(r"\w+", k))


def all_questions(study):
    out = []
    for sec in as_list(as_dict(study.get("instrument")).get("sections")):
        if isinstance(sec, dict):
            for q in as_list(sec.get("questions")):
                if isinstance(q, dict):
                    out.append((sec, q))
    return out


def map_columns(study, header):
    """Per column: {col, header, question, by} or {col, header, question: None, why}. Id wins over text."""
    by_key = {}
    qs = [q for _s, q in all_questions(study)]
    for q in qs:
        if sstr(q.get("id")):
            by_key.setdefault(key(q["id"]), (q["id"], "id"))
    for q in qs:
        if sstr(q.get("text")) and sstr(q.get("id")):
            by_key.setdefault(key(q["text"]), (q["id"], "text"))
    out, seen = [], set()
    for i, h in enumerate(header):
        hit = by_key.get(key(h)) if key(h) else None
        if hit and hit[0] not in seen:
            seen.add(hit[0])
            out.append({"col": i, "header": h, "question": hit[0], "by": hit[1]})
        else:
            out.append({"col": i, "header": h, "question": None,
                        "why": "empty header" if not key(h) else ("duplicate of a matched question" if hit else "matches no question")})
    return out


def _cell(row, i):
    return row[i] if i < len(row) else ""


# ── evidence on disk ─────────────────────────────────────────────────────────

def next_evidence_number(study):
    n = 0
    for e in as_list(study.get("evidence")):
        m = re.match(r"^e(\d+)\Z", sstr(as_dict(e).get("id")))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def evidence_file(base, sid, row):
    """(status, bytes|None, message). status: ok | missing | mismatch | unsafe."""
    rel = sstr(row.get("file"))
    prefix = evidence_dir_rel(sid) + "/"
    if (not rel.startswith(prefix) or posixpath.normpath(rel) != rel or ".." in rel.split("/")
            or "/" in rel[len(prefix):]):
        return "unsafe", None, "evidence path %r is not inside %s" % (rel, prefix)
    path = os.path.join(base, *rel.split("/"))
    try:
        if os.path.islink(path):
            return "unsafe", None, "%s is a symlink" % rel
        if row.get("kind") == "recording":      # a video can be a gigabyte: hash it in pieces, hand back no bytes
            digest = hash_file(path)
            raw = None
        else:
            raw = read_nofollow(path)
            digest = sha256_bytes(raw)
    except FileNotFoundError:
        return "missing", None, "%s is missing from disk" % rel
    except OSError as e:
        return "unsafe", None, "%s cannot be read (%s)" % (rel, e.strerror or e)
    if digest != sstr(row.get("sha256")):
        return "mismatch", None, "%s no longer matches its recorded sha256 — it was changed after import" % rel
    return "ok", raw, ""


def hash_file(path):
    """sha256 of a regular file, read in 1 MiB pieces and never through a symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        h = hashlib.sha256()
        while True:
            b = os.read(fd, 1 << 20)
            if not b:
                break
            h.update(b)
        return h.hexdigest()
    finally:
        os.close(fd)


def live_evidence(study):
    return [e for e in as_list(study.get("evidence")) if isinstance(e, dict) and not e.get("dropped")]


# ── tally ────────────────────────────────────────────────────────────────────

def _opt_map(q):
    return {key(o): o for o in as_list(q.get("options")) if isinstance(o, str)}


def split_multi(cell, q):
    """The options a multi-select cell holds. `;` splits when present; else the known options are
    matched greedily (longest first), because Google Forms joins with ', ' and an option may hold one."""
    text = squash(cell)
    if not text:
        return []
    omap = _opt_map(q)
    if ";" in text:
        return [omap.get(key(p), OTHER) for p in text.split(";") if p.strip()]
    low = text.casefold()
    names = sorted(omap, key=len, reverse=True)
    out, pos = [], 0
    while pos < len(low):
        while pos < len(low) and low[pos] in ", ":
            pos += 1
        if pos >= len(low):
            break
        for n in names:
            end = pos + len(n)
            if low.startswith(n, pos) and (end == len(low) or low[end] == ","):
                out.append(omap[n])
                pos = end
                break
        else:
            nxt = low.find(",", pos)
            out.append(OTHER)
            pos = len(low) if nxt < 0 else nxt
    return out


def _num(s):
    s = squash(s)
    try:
        return float(s)
    except ValueError:
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None


def scope_of(study):
    """The study's scope. A study with no `scope` key is a `collect` study (no migration)."""
    return study.get("scope") if study.get("scope") in SCOPES else "collect"


# ── standard metric templates ────────────────────────────────────────────────

def is_en(lang):
    k = key(sstr(lang))
    return k in ("", "en") or k.startswith("en-") or k.startswith("en_")


def template_text(name, subject=None, item=None):
    """The standard wording of one template question (item = 1..10 for sus)."""
    subj = squash(subject)
    if name == "ces":
        s = subj or "This task"
        return "%s was easy to handle." % (s[:1].upper() + s[1:])
    if name == "seq":
        return "Overall, how difficult or easy was this task to complete?"
    if name == "csat":
        return "How satisfied are you with %s?" % (subj or "this")
    if name == "nps":
        return "How likely are you to recommend %s to a friend or colleague?" % (subj or "this")
    if name == "sus" and isinstance(item, int) and 1 <= item <= len(SUS_ITEMS):
        return SUS_ITEMS[item - 1]
    return ""


def template_scale(name):
    lo, hi, minl, maxl = TEMPLATE_SCALES[name]
    return {"min": lo, "max": hi, "minLabel": minl, "maxLabel": maxl}


def _template_one(entry, name, qid, text, item=None):
    q = {"id": qid, "text": text, "tests": entry.get("tests", []), "type": "scale", "scale": template_scale(name),
         "required": entry.get("required", True), "template": name}
    if squash(entry.get("subject")):
        q["subject"] = squash(entry.get("subject"))
    if item is not None:
        q["templateItem"] = item
    if "probes" in entry:
        q["probes"] = entry["probes"]
    return q


def expand_template_entry(entry, en):
    """A plan question {id, template, subject?, text?, tests?} -> the normal question(s). An unknown template
    and an already-expanded sus item are returned as they are (`check` reports the first)."""
    name = entry.get("template")
    if name not in TEMPLATES or isinstance(entry.get("templateItem"), int):
        return [entry]
    qid = sstr(entry.get("id"))
    if not ITEM_ID.match(qid):
        raise ResearchError("template question id %r is malformed (lowercase letters, digits, - _)" % entry.get("id"))
    extra = sorted(set(entry) - TEMPLATE_KEYS)
    if extra:
        raise ResearchError("template question %s takes {%s}; unexpected: %s" % (qid, ", ".join(sorted(TEMPLATE_KEYS)), ", ".join(extra)))
    if name in ("seq", "sus") and squash(entry.get("subject")):
        raise ResearchError("template %s (%s) has fixed wording and takes no subject" % (name, qid))
    over = entry.get("text")
    if name == "sus":
        if over is None:
            texts = list(SUS_ITEMS)
        elif en:
            raise ResearchError("%s: `text` overrides a template only when the instrument's lang is not en" % qid)
        else:
            if not (isinstance(over, list) and len(over) == len(SUS_ITEMS) and all(squash(t) for t in over)
                    and all(isinstance(t, str) for t in over)):
                raise ResearchError("%s: a translated sus `text` is a list of the %d items, in order" % (qid, len(SUS_ITEMS)))
            texts = [squash(t) for t in over]
        return [_template_one(entry, name, "%s-%d" % (qid, i), texts[i - 1], i) for i in range(1, len(SUS_ITEMS) + 1)]
    canon = template_text(name, entry.get("subject"))
    if over is None:
        text = canon
    elif not isinstance(over, str) or not squash(over):
        raise ResearchError("%s: `text` must be a non-empty string" % qid)
    elif en and squash(over) != canon:
        raise ResearchError("%s: `text` overrides a template only when the instrument's lang is not en" % qid)
    else:
        text = squash(over)
    return [_template_one(entry, name, qid, text)]


def expand_templates(instrument):
    """A copy of the instrument with every template question expanded."""
    inst = json.loads(json.dumps(instrument))
    en = is_en(inst.get("lang"))
    for sec in as_list(inst.get("sections")):
        if isinstance(sec, dict) and isinstance(sec.get("questions"), list):
            out = []
            for q in sec["questions"]:
                out += expand_template_entry(q, en) if isinstance(q, dict) and "template" in q else [q]
            sec["questions"] = out
    return inst


def score_scale(name, vals):
    """The score of one scale template from the numeric answers. value is None with no answers."""
    n = len(vals)
    if not n:
        return {"metric": name, "value": None, "n": 0}
    if name in ("ces", "seq"):
        s = {"metric": name, "value": round(sum(vals) / n, 4)}
        if name == "ces":
            s["pct"] = round(100.0 * sum(1 for v in vals if v >= 5) / n, 4)
    elif name == "csat":
        s = {"metric": name, "value": round(100.0 * sum(1 for v in vals if v >= 4) / n, 4)}
    else:                                           # nps: % promoters (9-10) minus % detractors (0-6)
        prom, det = sum(1 for v in vals if v >= 9), sum(1 for v in vals if v <= 6)
        s = {"metric": name, "value": int(math.floor(100.0 * (prom - det) / n + 0.5))}
    s["n"] = n
    return s


def sus_respondent(answers):
    """One respondent's SUS (0-100) from the ten answers in item order, or None unless all ten are 1-5."""
    if len(answers) != len(SUS_ITEMS):
        return None
    total = 0
    for i, v in enumerate(answers, 1):
        if v is None or v != int(v) or not 1 <= v <= 5:
            return None
        total += (v - 1) if i % 2 else (5 - v)
    return total * 2.5


def sus_groups(study):
    """{base id: [item question ids in order 1..10]} for every complete set of sus items."""
    groups = {}
    for _s, q in all_questions(study):
        it = q.get("templateItem")
        if q.get("template") == "sus" and isinstance(it, int) and sstr(q.get("id")):
            groups.setdefault(q["id"].rsplit("-", 1)[0], {})[it] = q["id"]
    return {b: [m[i] for i in range(1, len(SUS_ITEMS) + 1)] for b, m in groups.items()
            if sorted(m) == list(range(1, len(SUS_ITEMS) + 1))}


def tally_questions(study, rows, mapped):
    by = {}
    for _sec, q in all_questions(study):
        qid = q.get("id")
        if qid not in mapped:
            continue
        typ = q.get("type") if q.get("type") in QTYPES else "text"
        cells = [r[qid] for r in rows if qid in r and squash(r[qid])]
        counts, mean, n = {}, None, 0
        if typ == "single":
            counts = {o: 0 for o in as_list(q.get("options")) if isinstance(o, str)}
            omap = _opt_map(q)
            for c in cells:
                k = omap.get(key(c), OTHER)
                counts[k] = counts.get(k, 0) + 1
            n = len(cells)
        elif typ == "multi":
            counts = {o: 0 for o in as_list(q.get("options")) if isinstance(o, str)}
            for c in cells:
                for k in set(split_multi(c, q)):
                    counts[k] = counts.get(k, 0) + 1
            n = len(cells)
        elif typ == "scale":
            sc = as_dict(q.get("scale"))
            lo, hi = sc.get("min"), sc.get("max")
            vals = [v for v in (_num(c) for c in cells) if v is not None and
                    (not isinstance(lo, (int, float)) or v >= lo) and (not isinstance(hi, (int, float)) or v <= hi)]
            if isinstance(lo, int) and isinstance(hi, int) and lo < hi:
                counts = {str(k): 0 for k in range(lo, hi + 1)}
            for v in vals:
                k = str(int(v)) if v == int(v) else str(v)
                counts[k] = counts.get(k, 0) + 1
            n = len(vals)
            mean = round(sum(vals) / n, 4) if n else None
        elif typ == "number":
            vals = [v for v in (_num(c) for c in cells) if v is not None]
            n = len(vals)
            mean = round(sum(vals) / n, 4) if n else None
        else:
            n = len(cells)
        by[qid] = {"type": typ, "n": n, "counts": counts, "mean": mean}
        if typ == "scale" and q.get("template") in ("ces", "seq", "csat", "nps"):
            by[qid]["score"] = score_scale(q["template"], vals)
    for base, ids in sorted(sus_groups(study).items()):
        if not any(i in mapped for i in ids):
            continue
        scores = []
        if all(i in mapped for i in ids):
            for r in rows:
                ans = [_num(r.get(i, "")) for i in ids]
                s = sus_respondent([a if a is not None and math.isfinite(a) else None for a in ans])
                if s is not None:
                    scores.append(s)
        score = ({"metric": "sus", "value": round(sum(scores) / len(scores), 4), "n": len(scores)} if scores
                 else {"metric": "sus", "value": None, "n": 0})
        by[base] = {"type": "sus", "n": score["n"], "counts": {}, "mean": None, "score": score}
    return by


def read_response_rows(study, base):
    """All answer rows from every live `responses` evidence file: (rows, mapped question ids, warnings)."""
    ev = [e for e in live_evidence(study) if e.get("kind") == "responses"]
    if not ev:
        raise ResearchError("no responses evidence is stored for %s — import a CSV first" % study.get("id"))
    rows, mapped, warns = [], set(), []
    for e in ev:
        status, raw, msg = evidence_file(base, study["id"], e)
        if status != "ok":
            raise ResearchError("%s: %s — run `verify`" % (e.get("id"), msg))
        text = decode_text(raw, sstr(e.get("file")))
        if text is None:
            raise ResearchError("%s is not a readable CSV" % e.get("id"))
        _d, header, data = parse_csv(text)
        cols = [c for c in map_columns(study, header) if c["question"]]
        mapped.update(c["question"] for c in cols)
        for r in data:
            row = {c["question"]: _cell(r, c["col"]) for c in cols}
            if any(squash(v) for v in row.values()):
                rows.append(row)
    return rows, mapped, warns


def screener_questions(study):
    return [q for sec, q in all_questions(study)
            if sec.get("purpose") == "screener" and as_list(q.get("qualifies"))]


def qualifies(q, cell):
    keep = {key(v) for v in as_list(q.get("qualifies"))}
    if q.get("type") == "multi":
        return any(key(v) in keep for v in split_multi(cell, q))
    return key(cell) in keep


def compute_tally(study, base):
    """(tally, warnings). Raises ResearchError when there is nothing to tally."""
    rows, mapped, warns = read_response_rows(study, base)
    scr = [q for q in screener_questions(study) if q.get("id") in mapped]
    kept, excluded, why = [], 0, {}
    for r in rows:
        bad = next((q for q in scr if q["id"] in r and
                    not (qualifies(q, r[q["id"]]) if squash(r[q["id"]]) else False)), None)
        if bad is None:
            kept.append(r)
        else:
            excluded += 1
            why[bad["id"]] = why.get(bad["id"], 0) + 1
    tally = {"n": len(kept), "excluded": excluded, "excludedWhy": why,
             "byQuestion": tally_questions(study, kept, mapped)}
    target = as_dict(study.get("audience")).get("targetN")
    if isinstance(target, int) and len(kept) < target:
        warns.append("n=%d is under the target of %d — directional, not conclusive" % (len(kept), target))
    return tally, warns, kept, mapped


# ── check (G-STUDY lint) ─────────────────────────────────────────────────────

HYPOTHETICAL = (r"\bwould you\b", r"\bif we (?:built|build)\b", "bạn có muốn", "bạn sẽ")
LEADING = (r"don'?t you think", r"how much do you love", r"bạn có thấy .{0,80}tốt không")
CONJ = re.compile(r"\s(?:and|or|và|hoặc)\s")


def _finding(level, code, where, msg):
    return {"level": level, "code": code, "where": where, "msg": msg}


def _check_template(q, tpl, where, E, W):
    """A template question must be a known template, on its standard scale; its wording is checked
    against the standard and a difference (a translation) is a warning, not an error."""
    qid = q.get("id")
    if tpl not in TEMPLATES:
        E("C-TEMPLATE", where, "%s: unknown template %r (known: %s)" % (qid, tpl, ", ".join(TEMPLATES)))
        return
    item = q.get("templateItem")
    if tpl == "sus" and not (isinstance(item, int) and 1 <= item <= len(SUS_ITEMS)):
        E("C-TEMPLATE", where, "%s: a sus question is one of ten items — let `plan` expand {\"template\": \"sus\"}" % qid)
        return
    sc = as_dict(q.get("scale"))
    want = template_scale(tpl)
    if q.get("type") != "scale" or sc.get("min") != want["min"] or sc.get("max") != want["max"]:
        E("C-TEMPLATE", where, "%s: a %s question is a scale %s to %s — its score is only valid on that scale"
          % (qid, tpl, want["min"], want["max"]))
    if squash(q.get("text")) != template_text(tpl, q.get("subject"), item):
        W("W-TEMPLATE-TEXT", where, "%s: the wording differs from the standard %s wording (a translation?) — the "
          "translated wording is not validated, so its score is not comparable with published norms" % (qid, tpl))


TASK_KEYS = ("task", "tree", "click")            # what makes a session-method question a task
CRITERIA_KEYS = ("screen", "text", "present", "absent")
DEVICES = ("monitor", "laptop", "tablet", "mobile")
SORT_KINDS = ("open", "closed", "hybrid")


def _check_criteria(qid, w, crit, screens, E):
    if not isinstance(crit, list) or not crit:
        E("C-TASK", w, "%s: task.criteria is a non-empty list of {screen|text|present|absent: …}" % qid)
        return
    for i, c in enumerate(crit):
        if not isinstance(c, dict) or not c:
            E("C-TASK", w, "%s: task.criteria[%d] must be an object such as {\"screen\": \"handover\"}" % (qid, i))
            continue
        bad = sorted(set(c) - set(CRITERIA_KEYS))
        if bad:
            E("C-TASK", w, "%s: task.criteria[%d] has unknown key(s) %s (known: %s)" % (qid, i, ", ".join(bad), ", ".join(CRITERIA_KEYS)))
        for k in CRITERIA_KEYS:
            if k in c and not squash(c[k] if isinstance(c[k], str) else ""):
                E("C-TASK", w, "%s: task.criteria[%d].%s must be a non-empty string" % (qid, i, k))
        if isinstance(c.get("screen"), str) and c["screen"] and c["screen"] not in screens:
            E("C-TASK", w, "%s: task.criteria[%d] names screen %r, which is not a screen of this registry" % (qid, i, c["screen"]))


def _check_usability_task(qid, w, tk, screens, E):
    """The usability additions to a task object (the screen / role / entry / success checks are shared with interviews)."""
    if "criteria" in tk:
        _check_criteria(qid, w, tk["criteria"], screens, E)
    if "optimalPath" in tk:
        op = tk["optimalPath"]
        if not (isinstance(op, list) and op and all(isinstance(s, str) and s for s in op)):
            E("C-TASK", w, "%s: task.optimalPath is a non-empty list of screen ids" % qid)
        else:
            for s in op:
                if s not in screens:
                    E("C-TASK", w, "%s: task.optimalPath names screen %r, which is not a screen of this registry" % (qid, s))
    if "timeLimitSec" in tk:
        t = tk["timeLimitSec"]
        if isinstance(t, bool) or not isinstance(t, int) or t < 1:
            E("C-TASK", w, "%s: task.timeLimitSec is a whole number of seconds, 1 or more" % qid)


def _check_tree(inst, E):
    """C-TREE for the tree itself. Returns the set of node ids (empty when the tree is unusable)."""
    tree = inst.get("tree")
    if not (isinstance(tree, list) and tree):
        E("C-TREE", "instrument", "a tree test needs instrument.tree: a non-empty list of {id, label, parent}")
        return set()
    ids = []
    for i, n in enumerate(tree):
        w = "instrument.tree[%d]" % i
        if not isinstance(n, dict):
            E("C-TREE", w, "a tree node must be an object {id, label, parent}")
            continue
        nid = n.get("id")
        if not ITEM_ID.match(sstr(nid)):
            E("C-TREE", w, "node id %r is malformed (lowercase letters, digits, - _)" % nid)
        elif nid in ids:
            E("C-TREE", w, "duplicate node id %r" % nid)
        ids.append(nid)
        if not squash(n.get("label")):
            E("C-TREE", w, "node %s has no label" % nid)
    idset = {i for i in ids if isinstance(i, str)}
    parent = {}
    for i, n in enumerate(tree):
        if not isinstance(n, dict) or not isinstance(n.get("id"), str):
            continue
        p = n.get("parent")
        if p is None:
            continue
        if not isinstance(p, str) or p not in idset:
            E("C-TREE", "instrument.tree[%d]" % i, "node %s has parent %r, which is not a node of the tree" % (n.get("id"), p))
        elif p == n.get("id"):
            E("C-TREE", "instrument.tree[%d]" % i, "node %s is its own parent" % p)
        else:
            parent[n.get("id")] = p
    for start in sorted(parent):
        seen, cur = set(), start
        while cur in parent and cur not in seen:
            seen.add(cur)
            cur = parent[cur]
        if cur in seen:
            E("C-TREE", "instrument.tree", "the tree has a cycle through node %s" % start)
            break
    return idset


def _check_cards(reg, inst, hyp_ids, tested, E, W):
    cards = inst.get("cards")
    if not isinstance(cards, list):
        E("C-CARDS", "instrument", "a card sort needs instrument.cards: a list of {id, label}")
        cards = []
    ids, labels = set(), set()
    jobs = {j.get("id") for j in jobs_of(reg)}
    for i, c in enumerate(cards):
        w = "instrument.cards[%d]" % i
        if not isinstance(c, dict):
            E("C-CARDS", w, "a card must be an object {id, label, job?}")
            continue
        cid = c.get("id")
        if not ITEM_ID.match(sstr(cid)):
            E("C-CARDS", w, "card id %r is malformed (lowercase letters, digits, - _)" % cid)
        elif cid in ids:
            E("C-CARDS", w, "duplicate card id %r" % cid)
        if isinstance(cid, str):
            ids.add(cid)
        lk = key(c.get("label"))
        if not lk:
            E("C-CARDS", w, "card %s has no label" % cid)
        elif lk in labels:
            E("C-CARDS", w, "two cards are labelled %r" % squash(c.get("label")))
        labels.add(lk)
        if isinstance(c.get("job"), str) and c["job"] and jobs and c["job"] not in jobs:
            W("W-CARDS", w, "card %s names job %r, which is not in ia.jobs" % (cid, c["job"]))
    if len(cards) < 4:
        E("C-CARDS", "instrument.cards", "a card sort needs at least 4 cards (has %d)" % len(cards))
    elif not 10 <= len(cards) <= 60:
        W("W-CARDS", "instrument.cards", "%d cards — a sort is steadiest between 10 and 60" % len(cards))
    sort = inst.get("sort")
    if not isinstance(sort, dict):
        E("C-SORT", "instrument", "a card sort needs instrument.sort: {kind: open|closed|hybrid, categories?, tests?}")
        return
    kind = sort.get("kind")
    if kind not in SORT_KINDS:
        E("C-SORT", "instrument.sort", "sort kind %r is not one of %s" % (kind, "|".join(SORT_KINDS)))
    cats = sort.get("categories")
    cats = cats if isinstance(cats, list) else []
    cat_ids = set()
    for i, c in enumerate(cats):
        w = "instrument.sort.categories[%d]" % i
        if not isinstance(c, dict) or not ITEM_ID.match(sstr(c.get("id"))) or not squash(c.get("label")):
            E("C-SORT", w, "a category is {id, label} with a lowercase id and a label")
        elif c["id"] in cat_ids:
            E("C-SORT", w, "duplicate category id %r" % c["id"])
        else:
            cat_ids.add(c["id"])
    if kind in ("closed", "hybrid") and len(cat_ids) < 2:
        E("C-SORT", "instrument.sort", "a %s sort needs at least 2 categories" % kind)
    tests = sort.get("tests", [])
    if not isinstance(tests, list):
        E("C-SORT", "instrument.sort", "sort.tests must be a list of hypothesis ids")
        tests = []
    for h in tests:
        if h not in hyp_ids:
            E("C-TESTS", "instrument.sort", "the sort tests %r, which is not a hypothesis of this study" % h)
        else:
            tested.add(h)


def _check_click(qid, w, ck, screens, E):
    if not isinstance(ck, dict):
        E("C-CLICK", w, "%s: click must be an object {screen, target?, rect?}" % qid)
        return
    if ck.get("screen") not in screens:
        E("C-CLICK", w, "%s: click screen %r is not a screen of this registry" % (qid, ck.get("screen")))
    has_target = bool(squash(ck["target"] if isinstance(ck.get("target"), str) else ""))
    rect = ck.get("rect")
    if not has_target and rect is None:
        E("C-CLICK", w, "%s: click needs a `target` (a selector) and/or a `rect` (fractions of the screen)" % qid)
    if "target" in ck and not has_target:
        E("C-CLICK", w, "%s: click.target must be a non-empty string" % qid)
    if rect is not None:
        ok = isinstance(rect, dict) and all(isinstance(rect.get(k), (int, float)) and not isinstance(rect.get(k), bool)
                                            for k in ("x", "y", "w", "h"))
        if not ok:
            E("C-CLICK", w, "%s: click.rect is {x, y, w, h}, each a fraction of the screen (0 to 1)" % qid)
        elif not (0 <= rect["x"] <= 1 and 0 <= rect["y"] <= 1 and 0 < rect["w"] <= 1 and 0 < rect["h"] <= 1
                  and rect["x"] + rect["w"] <= 1.0000001 and rect["y"] + rect["h"] <= 1.0000001):
            E("C-CLICK", w, "%s: click.rect must lie within the screen (0 to 1 in both directions)" % qid)


def _check_task_object(qid, w, tk, screens, declared_roles, entry_ids, E):
    """The task object shared by interviews and usability tests. Returns it (an empty dict when it was not one)."""
    if not isinstance(tk, dict):
        E("C-TASK", w, "%s: task must be an object" % qid)
        tk = {}
    if not isinstance(tk.get("screen"), str) or tk.get("screen") not in screens:
        E("C-TASK", w, "%s: task screen %r is not a screen of this registry" % (qid, tk.get("screen")))
    if tk.get("role") and declared_roles and tk["role"] not in declared_roles:
        E("C-TASK", w, "%s: task role %r is not declared in meta.roles" % (qid, tk["role"]))
    if tk.get("entry") and tk["entry"] not in entry_ids:
        E("C-TASK", w, "%s: task entry %r is not in meta.demo.entries" % (qid, tk["entry"]))
    if not squash(tk.get("success")):
        E("C-TASK", w, "%s: a task needs `success` — what done looks like" % qid)
    return tk


def _check_typed(q, qid, w, E):
    """A question answered on a form in a session (warm-up, post-task, closing): its type, options and scale."""
    typ = q.get("type")
    if typ is None:
        return
    if typ not in QTYPES:
        E("C-TYPE", w, "%s has type %r, not one of %s" % (qid, typ, "|".join(QTYPES)))
        return
    if typ in ("single", "multi"):
        ol = as_list(q.get("options"))
        if len(ol) < 2 or not all(isinstance(o, str) and squash(o) for o in ol):
            E("C-OPTIONS", w, "%s (%s) needs at least 2 non-empty options" % (qid, typ))
        elif len({key(o) for o in ol}) != len(ol):
            E("C-OPTIONS", w, "%s has duplicate options" % qid)
    if typ == "scale":
        sc = q.get("scale")
        lo, hi = (sc.get("min"), sc.get("max")) if isinstance(sc, dict) else (None, None)
        if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo < hi):
            E("C-SCALE", w, "%s is a scale without numeric min < max" % qid)


def _check_session_instrument(reg, study, inst, purposes, hyp_ids, tested, E, W):
    """The instrument-level rules of the four session methods (mode, recording, device, tree, cards, sort)."""
    method = study.get("method")
    mode = inst.get("mode", "moderated")
    if mode not in MODES:
        E("C-MODE", "instrument", "instrument.mode %r is not one of %s" % (mode, "|".join(MODES)))
        mode = "moderated"
    if "thinkAloud" in inst and not isinstance(inst["thinkAloud"], bool):
        E("C-MODE", "instrument", "instrument.thinkAloud must be true or false")
    if "recording" in inst:
        rec = inst["recording"]
        if not isinstance(rec, dict) or sorted(set(rec) - {"screen", "voice"}) or \
                not all(isinstance(v, bool) for v in rec.values()):
            E("C-RECORDING", "instrument", "instrument.recording is {screen: true|false, voice: true|false}")
        elif rec.get("voice") and not rec.get("screen"):
            W("W-RECORDING", "instrument", "voice without screen: the runner records the screen and, with it, the voice")
    if "device" in inst:
        dev = inst["device"]
        declared = [d for d in as_list(as_dict(reg.get("meta")).get("devices")) if isinstance(d, str)]
        if dev not in DEVICES:
            E("C-DEVICE", "instrument", "instrument.device %r is not one of %s" % (dev, "|".join(DEVICES)))
        elif declared and dev not in declared:
            W("W-DEVICE", "instrument", "device %s is not in meta.devices (%s)" % (dev, ", ".join(declared)))
    if method == "usability" and "warmup" not in purposes:
        if mode in ("moderated", "both"):
            E("C-WARMUP", "instrument", "a moderated usability test needs a warmup section (context questions before the tasks)")
        else:
            W("W-WARMUP", "instrument", "no warmup section — the participant starts the first task cold")
    inst_tree = None
    if method == "tree-test":
        inst_tree = _check_tree(inst, E)
    elif method == "card-sort":
        _check_cards(reg, inst, hyp_ids, tested, E, W)
    return inst_tree


def _check_plan_for_session(study, E, W):
    plan = as_dict(study.get("plan"))
    if not [x for x in as_list(plan.get("objectives")) if squash(x)]:
        E("C-PLAN", "plan", "a session study needs plan.objectives — `brief %s --file …` writes the research plan" % study.get("id"))
    if not [x for x in as_list(plan.get("researchQuestions")) if squash(x)]:
        E("C-PLAN", "plan", "a session study needs plan.researchQuestions")
    for label, ok in (("schedule", bool(as_dict(plan.get("schedule")))), ("recruitment", bool(as_dict(plan.get("recruitment")))),
                      ("participants.criteria", bool(as_list(as_dict(plan.get("participants")).get("criteria"))))):
        if not ok:
            W("W-PLAN", "plan", "the plan has no %s" % label)


def check_study(reg, study):
    errs, warns = [], []

    def E(code, where, msg):
        errs.append(_finding("error", code, where, msg))

    def W(code, where, msg):
        warns.append(_finding("warning", code, where, msg))

    method = study.get("method")
    session = method in SESSION_METHODS
    audience = as_dict(study.get("audience"))
    declared_roles = role_ids(reg)
    n_tasks = 0
    pending_correct = []        # tree-test answer keys, checked against the tree once the whole instrument is read

    if not STUDY_ID.match(sstr(study.get("id"))):
        E("C-ID", "study", "study id %r is not rs-<kebab>" % study.get("id"))
    if "scope" in study and study.get("scope") not in SCOPES:
        E("C-SCOPE", "study", "scope %r is not one of %s" % (study.get("scope"), "|".join(SCOPES)))
    for t in as_list(study.get("targets")):
        p = target_problem(reg, t)
        if p:
            E("C-TARGET", "targets", p)

    hyps = [h for h in as_list(study.get("hypotheses"))]
    hyp_ids, seen = [], set()
    for n, h in enumerate(hyps):
        w = "hypotheses[%d]" % n
        if not isinstance(h, dict):
            E("C-ID", w, "a hypothesis must be an object")
            continue
        hid = h.get("id")
        if not ITEM_ID.match(sstr(hid)):
            E("C-ID", w, "hypothesis id %r is malformed (lowercase letters, digits, - _)" % hid)
        elif hid in seen:
            E("C-ID", w, "duplicate hypothesis id %r" % hid)
        seen.add(hid)
        hyp_ids.append(hid)
        if not squash(h.get("statement")):
            E("C-HYP", w, "%s has no statement" % hid)
        for f in ("supportedIf", "refutedIf"):
            if not squash(h.get(f)):
                E("C-HYP-FALSIFIABLE", w, "%s has no %s — a hypothesis nothing could refute tests nothing" % (hid, f))
        for t in as_list(h.get("targets")):
            p = target_problem(reg, t)
            if p:
                E("C-TARGET", w, p)

    inst = study.get("instrument")
    if not isinstance(inst, dict):
        E("C-INSTRUMENT", "instrument", "the study has no instrument")
        inst = {}
    for f in ("intro", "consent"):
        if not squash(inst.get(f)):
            E("C-" + f.upper(), "instrument", "the instrument has no %s text" % f)

    sections = inst.get("sections")
    if not isinstance(sections, list):
        E("C-SECTION", "instrument", "sections must be a list")
        sections = []
    qinfo = []                  # (position, purpose, normalised text, question) — for the priming heuristic
    tested, qids = set(), set()
    purposes = []
    first_task = None
    n_questions = n_text = 0
    screens = {s.get("id") for s in screens_of(reg)}
    entry_ids = {e.get("id") for e in entries_of(reg)}
    feature_names = [key(t.get("id")) for t in as_list(study.get("targets"))
                     if isinstance(t, dict) and t.get("kind") == "feature" and len(key(t.get("id"))) >= 3]
    for t in as_list(study.get("targets")):
        if not isinstance(t, dict):
            continue
        pool = screens_of(reg) if t.get("kind") == "screen" else components_of(reg) if t.get("kind") == "component" else []
        for o in pool:
            if o.get("id") == t.get("id") and len(key(o.get("name"))) >= 3:
                feature_names.append(key(o["name"]))

    for si, sec in enumerate(sections):
        sw = "sections[%d]" % si
        if not isinstance(sec, dict):
            E("C-SECTION", sw, "a section must be an object")
            continue
        purpose = sec.get("purpose")
        purposes.append(purpose)
        if purpose not in PURPOSES:
            E("C-SECTION", sw, "section purpose %r is not one of %s" % (purpose, "|".join(PURPOSES)))
        if not isinstance(sec.get("questions"), list):
            E("C-SECTION", sw, "a section needs a questions list")
            continue
        sec_has_task = False
        sec_seq = False
        for q in sec["questions"]:
            if not isinstance(q, dict):
                E("C-ID", sw, "a question must be an object")
                continue
            qid = q.get("id")
            w = "%s.%s" % (sw, qid)
            n_questions += 1
            if not ITEM_ID.match(sstr(qid)):
                E("C-ID", w, "question id %r is malformed (lowercase letters, digits, - _)" % qid)
            elif qid in qids:
                E("C-ID", w, "duplicate question id %r" % qid)
            qids.add(qid)
            text = squash(q.get("text"))
            if not text:
                E("C-QUESTION", w, "%s has no text" % qid)
            is_task_q = session and any(k in q for k in TASK_KEYS)
            # the questions after a task question in its task section are its post-task questions (a SEQ, say)
            post_task = session and purpose == "task" and not is_task_q and sec_has_task
            sec_has_task = sec_has_task or is_task_q
            if is_task_q and purpose != "task":
                E("C-TASK", w, "%s is a task but sits in a %r section — tasks belong in a `task` section" % (qid, purpose))
            tests = q.get("tests")
            if not isinstance(tests, list):
                E("C-TESTS", w, "%s: tests must be a list of hypothesis ids" % qid)
                tests = []
            if purpose in ("main", "task") and not tests and not post_task:
                E("C-TESTS", w, "%s is a %s question that tests no hypothesis — cut it or name the hypothesis" % (qid, purpose))
            for h in tests:
                if h not in hyp_ids:
                    E("C-TESTS", w, "%s tests %r, which is not a hypothesis of this study" % (qid, h))
                else:
                    tested.add(h)
            lk = key(text).replace("’", "'")
            tpl = q.get("template")
            if "template" in q:
                _check_template(q, tpl, w, E, W)
            if method == "survey":
                typ = q.get("type")
                opts = q.get("options")
                if typ not in QTYPES:
                    E("C-TYPE", w, "%s has type %r, not one of %s" % (qid, typ, "|".join(QTYPES)))
                if typ == "text":
                    n_text += 1
                if typ in ("single", "multi"):
                    ol = [o for o in as_list(opts)]
                    if len(ol) < 2 or not all(isinstance(o, str) and squash(o) for o in ol):
                        E("C-OPTIONS", w, "%s (%s) needs at least 2 non-empty options" % (qid, typ))
                    elif len({key(o) for o in ol}) != len(ol):
                        E("C-OPTIONS", w, "%s has duplicate options" % qid)
                if typ == "scale":
                    sc = q.get("scale")
                    lo, hi = (sc.get("min"), sc.get("max")) if isinstance(sc, dict) else (None, None)
                    if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo < hi):
                        E("C-SCALE", w, "%s is a scale without numeric min < max" % qid)
                if "qualifies" in q:
                    ol = {key(o) for o in as_list(opts) if isinstance(o, str)}
                    bad = [v for v in as_list(q.get("qualifies")) if key(v) not in ol]
                    if bad:
                        E("C-QUALIFIES", w, "%s qualifies %s, which are not among its options" % (qid, bad))
                if CONJ.search(" " + lk + " ") and "," not in lk and typ != "multi" and "template" not in q:
                    W("W-DOUBLE", w, "%s may ask two things at once (' and ' / ' or ') — one question, one thing" % qid)
            elif session:
                if is_task_q:
                    n_tasks += 1
                    first_task = n_questions if first_task is None else first_task
                    if method == "usability":
                        if "task" not in q:
                            E("C-TASK", w, "%s: a usability task carries a `task` object {screen, success, …}" % qid)
                        else:
                            _check_usability_task(qid, w, _check_task_object(qid, w, q.get("task"), screens, declared_roles, entry_ids, E),
                                                  screens, E)
                    elif method == "tree-test":
                        tr = q.get("tree")
                        if not (isinstance(tr, dict) and isinstance(tr.get("correct"), list) and tr["correct"]
                                and all(isinstance(c, str) and c for c in tr["correct"])):
                            E("C-TREE", w, "%s: a tree-test task carries `tree: {correct: [node ids]}` (the answer key; participants never see it)" % qid)
                        else:
                            pending_correct.append((qid, w, tr["correct"]))
                    elif method == "first-click":
                        if "click" not in q:
                            E("C-CLICK", w, "%s: a first-click task carries a `click` object {screen, target?, rect?}" % qid)
                        else:
                            _check_click(qid, w, q.get("click"), screens, E)
                    else:
                        E("C-CARDS", w, "%s: a card sort has no tasks — the activity is instrument.cards and instrument.sort" % qid)
                elif purpose == "task" and not post_task:
                    E({"usability": "C-TASK", "tree-test": "C-TREE", "first-click": "C-CLICK"}.get(method, "C-CARDS"), w,
                      "%s sits in a task section before any task question — a task question opens the section" % qid)
                else:
                    _check_typed(q, qid, w, E)
                    if post_task and q.get("template") == "seq":
                        sec_seq = True
            else:
                if purpose == "main" and not as_list(q.get("probes")):
                    W("W-PROBES", w, "%s is a main interview question with no probes" % qid)
                if "task" in q:
                    first_task = n_questions if first_task is None else first_task
                    _check_task_object(qid, w, q.get("task"), screens, declared_roles, entry_ids, E)
            if "template" in q:         # standard wording: exempt from the wording heuristics and the priming check
                continue
            if not is_task_q:           # a scenario names a goal: "where would you go to …?" is not a hypothetical
                for p in HYPOTHETICAL:
                    if re.search(p, lk):
                        W("W-HYPOTHETICAL", w, "%s asks what people WOULD do — ask what they DID, last time" % qid)
                        break
            for p in LEADING:
                if re.search(p, lk):
                    W("W-LEADING", w, "%s leads the answer" % qid)
                    break
            qinfo.append((n_questions, purpose, lk, q))
        if session and purpose == "task":
            if not sec_has_task:
                E({"usability": "C-TASK", "tree-test": "C-TREE", "first-click": "C-CLICK"}.get(method, "C-CARDS"), sw,
                  "a task section needs a task question")
            elif method == "usability" and not sec_seq:
                W("W-SEQ", sw, "this task has no post-task SEQ question — add {\"id\": \"…\", \"template\": \"seq\"} after it")

    # a question that names the feature under test before the task primes the answer
    tkeys = TASK_KEYS if method in SESSION_METHODS else ("task",)
    for pos, purpose, lk, q in qinfo:
        before = (first_task is not None and pos < first_task) or (first_task is None and purpose in ("screener", "warmup"))
        if before and not any(k in q for k in tkeys) and any(f in lk for f in feature_names):
            W("W-PRIMING", str(q.get("id")), "%s names the feature under test before the task — it primes the answer" % q.get("id"))

    if method in SESSION_METHODS:
        tree_ids = _check_session_instrument(reg, study, inst, purposes, set(hyp_ids), tested, E, W)
        for qid, w, correct in pending_correct:
            for c in correct:
                if tree_ids is not None and c not in tree_ids:
                    E("C-TREE", w, "%s: the correct node %r is not a node of the tree" % (qid, c))
        if method in ("usability", "tree-test", "first-click") and not n_tasks:
            E({"usability": "C-TASK", "tree-test": "C-TREE"}.get(method, "C-CLICK"), "instrument",
              "a %s study needs at least one task question in a `task` section" % method)
        _check_plan_for_session(study, E, W)

    for h, hid in zip(hyps, hyp_ids):
        if isinstance(h, dict) and hid not in tested:
            E("C-HYP-UNTESTED", "hypotheses.%s" % hid, "%s is tested by no question" % hid)

    if method == "survey":
        if (as_list(audience.get("roles")) or squash(audience.get("segment"))) and "screener" not in purposes:
            E("C-SCREENER", "instrument", "the audience names a role or segment but the instrument has no screener section")
        if n_questions > 15:
            W("W-LENGTH", "instrument", "%d questions — past 15, completion falls" % n_questions)
        if n_questions and n_text * 5 > n_questions:
            W("W-OPEN", "instrument", "%d of %d questions are open text — over 20%%" % (n_text, n_questions))
    elif method == "interview":
        if "warmup" not in purposes:
            E("C-WARMUP", "instrument", "an interview guide needs a warmup section")
    elif method not in SESSION_METHODS:
        E("C-METHOD", "study", "method %r is not one of %s" % (method, ", ".join(METHODS)))
    return errs, warns


# ── verify ───────────────────────────────────────────────────────────────────

NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?!\w)")


def _numbers(text):
    out = set()
    for m in NUMBER.findall(sstr(text)):
        s = m.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", m) else m.replace(",", ".")
        try:
            out.add(round(float(s), 4))
        except ValueError:
            pass
    return out


def _decimals(x):
    s = repr(float(x))
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def verify_study(reg, study, base):
    errs, warns = [], []

    def E(code, where, msg):
        errs.append(_finding("error", code, where, msg))

    def W(code, where, msg):
        warns.append(_finding("warning", code, where, msg))

    sid = study.get("id")
    hyps = [h for h in as_list(study.get("hypotheses")) if isinstance(h, dict)]
    hyp_ids = {h.get("id") for h in hyps}
    findings = [f for f in as_list(study.get("findings")) if isinstance(f, dict)]
    cites = {}
    for f in findings:
        for h in as_list(f.get("hypotheses")):
            cites.setdefault(h, []).append(f.get("id"))

    seen = set()
    for n, f in enumerate(findings):
        fid = f.get("id")
        if not ITEM_ID.match(sstr(fid)):
            E("V-ID", "findings[%d]" % n, "finding id %r is malformed" % fid)
        elif fid in seen:
            E("V-ID", "findings[%d]" % n, "duplicate finding id %r" % fid)
        seen.add(fid)

    for h in hyps:
        hid, v = h.get("id"), h.get("verdict")
        if v is None or v == "":
            E("V-VERDICT", "hypotheses.%s" % hid, "%s has no verdict" % hid)
        elif v not in VERDICTS:
            E("V-VERDICT", "hypotheses.%s" % hid, "%s has verdict %r, not one of %s" % (hid, v, "|".join(VERDICTS)))
        elif v in ("supported", "refuted", "mixed") and hid not in cites:
            E("V-UNCITED", "hypotheses.%s" % hid, "%s is %s but no finding cites it" % (hid, v))

    # sstr: a hand-edited row whose id is a list or a dict must fail verification, not crash it
    rows = {sstr(e.get("id")): e for e in as_list(study.get("evidence")) if isinstance(e, dict)}
    cache = {}

    def file_of(eid):
        if eid not in cache:
            row = rows[eid]
            if row.get("dropped"):
                cache[eid] = ("dropped", None, "%s was dropped (%s)" % (eid, as_dict(row["dropped"]).get("reason", "")))
            else:
                cache[eid] = evidence_file(base, sid, row)
        return cache[eid]

    for eid, row in rows.items():
        if not row.get("dropped"):
            st, _raw, msg = file_of(eid)
            if st != "ok":
                E("V-EVIDENCE", "evidence.%s" % eid, msg)
        if not row.get("dropped") and row.get("consent") == "unknown":
            W("W-CONSENT", "evidence.%s" % eid, "%s has consent: unknown — confirm before the quotes go further" % eid)

    live_tally = [None]

    def tally_now():
        if live_tally[0] is None:
            try:
                live_tally[0] = compute_tally(study, base)[0]
            except ResearchError as e:
                live_tally[0] = str(e)
        return live_tally[0]

    allowed = set()
    stored = as_dict(study.get("tally"))
    for x in (stored.get("n"), stored.get("excluded")):
        if isinstance(x, (int, float)):
            allowed.add(round(float(x), 4))
    for q in as_dict(stored.get("byQuestion")).values():
        n = q.get("n") if isinstance(q, dict) else None
        if isinstance(n, (int, float)):
            allowed.add(float(n))
        for c in as_dict(as_dict(q).get("counts")).values():
            if isinstance(c, (int, float)):
                allowed.add(float(c))
                if n:
                    allowed.update((round(100.0 * c / n), round(100.0 * c / n, 1)))
        m = as_dict(q).get("mean")
        if isinstance(m, (int, float)):
            allowed.update((round(m, 1), round(m, 2), round(m)))
        for fld in ("value", "pct", "n"):                 # a template score is a known number
            sv = as_dict(as_dict(q).get("score")).get(fld)
            if isinstance(sv, (int, float)):
                allowed.update((round(float(sv), 4), round(sv, 1), round(sv, 2), float(round(sv))))
    people = {sstr(e.get("participant")) for e in live_evidence(study) if e.get("participant")}
    allowed.update((float(len(people)), float(len(live_evidence(study)))))

    # ── the UX additions: session analysis, observations, issues, themes ──
    session = study.get("method") in SESSION_METHODS
    observations = [o for o in as_list(study.get("observations")) if isinstance(o, dict)]
    issues = [i for i in as_list(study.get("issues")) if isinstance(i, dict)]
    themes = [t for t in as_list(study.get("themes")) if isinstance(t, dict)]
    obs_ids = {o.get("id") for o in observations if isinstance(o.get("id"), str)}
    issue_ids = {i.get("id") for i in issues if isinstance(i.get("id"), str)}
    fresh_box = []

    def fresh_analysis():
        """The analysis recomputed from the evidence on disk now: (analysis, None) or (None, why not)."""
        if not fresh_box:
            try:
                rs, pairs = _rs(), []
                for e in live_evidence(study):
                    if e.get("kind") != "session":
                        continue
                    stt, raw, msg = file_of(e["id"])
                    if stt != "ok":
                        raise ValueError(msg)
                    pairs.append((e, rs.parse_session_bytes(raw)))
                fresh_box.append((_ra().analyze(study, pairs), None))
            except Exception as ex:                 # a bad file is reported as V-EVIDENCE already; here it only blocks the recompute
                fresh_box.append((None, str(ex)))
        return fresh_box[0]

    if session:
        fresh, why = fresh_analysis()
        if fresh is not None:
            allowed.update(_ra().allowed_numbers(fresh))
    else:
        fresh = None

    for n, f in enumerate(findings):
        fw = "findings.%s" % f.get("id")
        allowed.update(_numbers(f.get("text")))
        for h in as_list(f.get("hypotheses")):
            if h not in hyp_ids:
                E("V-FINDING", fw, "%s cites hypothesis %r, which does not exist" % (f.get("id"), h))
        refs = as_list(f.get("evidence"))
        if not refs:
            E("V-FINDING", fw, "%s has no evidence — a finding is what its evidence says" % f.get("id"))
        who = set()
        quotes_only = bool(refs)
        for k, ref in enumerate(refs):
            rw = "%s.evidence[%d]" % (fw, k)
            if not isinstance(ref, dict):
                E("V-FINDING", rw, "an evidence entry must be an object")
                continue
            if "tally" in ref:
                quotes_only = False
                for fld in ("count", "of", "value"):
                    if isinstance(ref.get(fld), (int, float)):
                        allowed.add(round(float(ref[fld]), 4))
                _verify_tally_ref(ref, rw, study, tally_now, E)
                continue
            if "analysis" in ref:               # {"analysis": "usability.tasks.t1.success.rate", "value": 0.8}
                quotes_only = False
                if not session:
                    E("V-ANALYSIS", rw, "an analysis citation belongs to a session study; %s is a %s study" % (sid, study.get("method")))
                elif fresh is None:
                    E("V-ANALYSIS", rw, "cites %s but no analysis can be computed: %s" % (ref.get("analysis"), why))
                else:
                    msg = _ra().verify_ref(ref, fresh)
                    if msg:
                        E("V-ANALYSIS", rw, msg)
                    if isinstance(ref.get("value"), (int, float)) and not isinstance(ref.get("value"), bool):
                        allowed.add(round(float(ref["value"]), 4))
                continue
            if "issue" in ref:
                quotes_only = False
                if not _in(ref["issue"], issue_ids):
                    E("V-FINDING", rw, "cites issue %r, which is not an issue of this study" % ref["issue"])
                continue
            if "observation" in ref:
                if not _in(ref["observation"], obs_ids):
                    E("V-FINDING", rw, "cites observation %r, which is not an observation of this study" % ref["observation"])
                else:
                    ob = next(o for o in observations if o.get("id") == ref["observation"])
                    who.add(ob.get("participant") or as_dict(rows.get(ob.get("evidence"))).get("participant") or ob.get("evidence"))
                continue
            eid = ref.get("evidence")
            quote = squash(ref.get("quote"))
            if eid not in rows:
                E("V-EVIDENCE", rw, "cites evidence %r, which is not stored for this study" % eid)
                continue
            st, raw, msg = file_of(eid)
            if st != "ok":
                E("V-EVIDENCE", rw, msg)
                continue
            if not quote:
                E("V-QUOTE", rw, "an evidence entry needs a `quote` (or a `tally`)")
                continue
            text = decode_text(raw, sstr(rows[eid].get("file")))
            if text is None:
                E("V-QUOTE-OPAQUE", rw, "%s is a %s pb cannot read — a quote cannot be checked against it. "
                  "Import a text transcript too." % (eid, os.path.splitext(sstr(rows[eid].get("file")))[1] or "file"))
                continue
            if quote not in squash(text):
                E("V-QUOTE", rw, "the quote is not in %s word for word: %r" % (eid, ref.get("quote")))
            if len(quote) < 12:
                W("W-SHORT-QUOTE", rw, "the quote is under 12 characters — it proves little")
            for hit in _pii(quote):
                W("W-PII", rw, "the quote may hold personal data (%s)" % hit)
            who.add(ref.get("participant") or rows[eid].get("participant") or eid)
        if quotes_only and len(who) == 1:
            W("W-ONE-PARTICIPANT", fw, "%s rests on one participant" % f.get("id"))

    _verify_ux(reg, study, rows, file_of, session, fresh, why if session else None, observations, issues, themes,
               obs_ids, E, W)

    # below the target
    target = as_dict(study.get("audience")).get("targetN")
    if isinstance(target, int):
        if study.get("method") == "survey":
            n = stored.get("n")
            n = n if isinstance(n, int) else sum(e.get("responses") or 0 for e in live_evidence(study))
        elif session and fresh is not None:
            n = fresh.get("n") if isinstance(fresh.get("n"), int) else 0
        else:
            n = len({e.get("participant") for e in live_evidence(study) if e.get("participant")})
        if n < target:
            W("W-DIRECTIONAL", "audience", "%d of the target %d — directional, not conclusive" % (n, target))

    # numbers in the refill, and in the report's narrative, that no finding, tally or analysis holds
    allowed.update(float(k) for k in range(0, 5))                    # a severity
    allowed.update((float(len(issues)), float(len(observations)), float(len(themes))))
    texts = sorted(as_dict(study.get("refill")).items())
    rep = as_dict(study.get("report"))
    if isinstance(rep.get("summary"), str):
        texts.append(("report.summary", rep["summary"]))
    for i, r in enumerate(as_list(rep.get("recommendations"))):
        if isinstance(r, dict) and isinstance(r.get("text"), str):
            texts.append(("report.recommendations[%d]" % i, r["text"]))
    for k in ("nextSteps", "limitations"):
        for i, x in enumerate(as_list(rep.get(k))):
            if isinstance(x, str):
                texts.append(("report.%s[%d]" % (k, i), x))
    for fld, text in texts:
        for num in sorted(_numbers(text)):
            if num not in allowed:
                W("W-NUMBER", fld if fld.startswith("report") else "refill.%s" % fld,
                  "the number %g appears in no finding, tally or analysis" % num)
    return errs, warns


def _in(x, coll):
    """x in coll, where x may be any junk a hand-edited registry holds (a list is not a member of anything)."""
    return isinstance(x, str) and x in coll


def dup_participants(rows_and_objs):
    """{participant: [eids]} for a participant who has more than one session in the analysis."""
    seen = {}
    for row, obj in rows_and_objs:
        p = row.get("participant") or as_dict(obj).get("participant")
        if isinstance(p, str) and p:
            seen.setdefault(p, []).append(sstr(row.get("id")))
    return {p: ids for p, ids in sorted(seen.items()) if len(ids) > 1}


def _dup_warning(dups):
    return [_finding("warning", "W-DUP-PARTICIPANT", "analysis",
                     "%s has %d sessions (%s) — each counts as a separate participant in n; drop-evidence the extra one "
                     "unless that is the design" % (p, len(ids), ", ".join(ids))) for p, ids in dups.items()]


def _verify_ux(reg, study, rows, file_of, session, fresh, why, observations, issues, themes, obs_ids, E, W):
    """V-OBS · V-ISSUE · V-THEME · V-ANALYSIS · V-REPORT, and W-ONE-PARTICIPANT for a major issue on one person."""
    sid = study.get("id")
    screen_ids = {x.get("id") for x in screens_of(reg)}
    task_ids = None
    if session:
        task_ids = {q.get("id") for _s, q in all_questions(_expanded(study)) if any(k in q for k in TASK_KEYS)}
    sess_cache = {}

    def session_of(eid):
        if eid not in sess_cache:
            try:
                st_, raw, msg = file_of(eid)
                sess_cache[eid] = _rs().parse_session_bytes(raw) if st_ == "ok" else None
            except Exception:
                sess_cache[eid] = None
        return sess_cache[eid]

    # observations
    seen, tags_used = set(), set()
    for n, o in enumerate(observations):
        oid = o.get("id")
        w = "observations.%s" % oid
        if not ITEM_ID.match(sstr(oid)):
            E("V-OBS", "observations[%d]" % n, "observation id %r is malformed (lowercase letters, digits, - _)" % oid)
        elif oid in seen:
            E("V-OBS", "observations[%d]" % n, "duplicate observation id %r" % oid)
        seen.add(oid)
        tags = o.get("tags")
        tags = tags if isinstance(tags, list) else []
        for t in tags:
            if isinstance(t, str) and TAG.match(t):
                tags_used.add(t)
            else:
                E("V-OBS", w, "tag %r is not a lowercase-and-dashes word (a-z, 0-9, -)" % (t,))
        if not squash(o.get("note")):
            E("V-OBS", w, "%s has no note — say what was seen or said" % oid)
        else:
            for hit in _pii(squash(o.get("note"))):
                W("W-PII", w, "the note may hold personal data (%s)" % hit)
        eid = o.get("evidence")
        row = rows.get(eid)
        if row is None:
            E("V-OBS", w, "%s cites evidence %r, which is not stored for this study" % (oid, eid))
            continue
        if row.get("dropped"):
            E("V-OBS", w, "%s cites %s, which was dropped (a participant withdrew)" % (oid, eid))
            continue
        stt, raw, msg = file_of(eid)
        if stt != "ok":
            E("V-OBS", w, "%s cannot be checked: %s" % (oid, msg))
            continue
        if o.get("participant") and row.get("participant") and o["participant"] != row["participant"]:
            E("V-OBS", w, "%s says participant %s, but %s is %s's" % (oid, o["participant"], eid, row["participant"]))
        if o.get("task") is not None and task_ids is not None and not _in(o["task"], task_ids):
            E("V-OBS", w, "%s is about task %r, which this study does not have" % (oid, o["task"]))
        kinds = [k for k in ("event", "t", "quote") if o.get(k) is not None]
        if len(kinds) != 1:
            E("V-OBS", w, "%s must point at its evidence in exactly one way: `event` (an index into the session's events), "
              "`t` (milliseconds in) or `quote` (verbatim text)" % oid)
            continue
        k = kinds[0]
        if k in ("event", "t"):
            v = o[k]
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                E("V-OBS", w, "%s: `%s` must be a whole number, 0 or more" % (oid, k))
                continue
            if row.get("kind") == "session":
                obj = session_of(eid)
                if obj is None:
                    E("V-OBS", w, "%s: %s cannot be read as a session" % (oid, eid))
                elif k == "event" and v >= len(as_list(obj.get("events"))):
                    E("V-OBS", w, "%s: event %d is out of range — %s has %d events" % (oid, v, eid, len(as_list(obj.get("events")))))
                elif k == "t" and isinstance(obj.get("durationMs"), int) and v > obj["durationMs"]:
                    E("V-OBS", w, "%s: t=%d is after the end of the session (%d ms)" % (oid, v, obj["durationMs"]))
            elif k == "event":
                E("V-OBS", w, "%s: `event` points into a session; %s is %s evidence — use `quote`" % (oid, eid, row.get("kind")))
            elif row.get("kind") != "recording":
                E("V-OBS", w, "%s: `t` points into a session or a recording; %s is %s evidence — use `quote`" % (oid, eid, row.get("kind")))
        else:
            quote = squash(o.get("quote"))
            text = decode_text(raw, sstr(row.get("file")))
            if text is None:
                E("V-OBS", w, "%s: %s is a %s pb cannot read — a quote cannot be checked against it" %
                  (oid, eid, os.path.splitext(sstr(row.get("file")))[1] or "file"))
            elif quote not in squash(text):
                E("V-OBS", w, "%s: the quote is not in %s word for word: %r" % (oid, eid, o.get("quote")))
            if len(quote) < 12:
                W("W-SHORT-QUOTE", w, "the quote is under 12 characters — it proves little")
            for hit in _pii(quote):
                W("W-PII", w, "the quote may hold personal data (%s)" % hit)

    # themes
    seen = set()
    for n, t in enumerate(themes):
        tid = t.get("id")
        w = "themes.%s" % tid
        if not ITEM_ID.match(sstr(tid)):
            E("V-THEME", "themes[%d]" % n, "theme id %r is malformed" % tid)
        elif tid in seen:
            E("V-THEME", "themes[%d]" % n, "duplicate theme id %r" % tid)
        seen.add(tid)
        if not squash(t.get("title")):
            E("V-THEME", w, "%s has no title" % tid)
        if not squash(t.get("insight")):
            W("W-THEME", w, "%s has no insight — a theme says what the tagged observations add up to" % tid)
        ttags = as_list(t.get("tags"))
        if not ttags:
            E("V-THEME", w, "%s has no tags — a theme is a set of tagged observations" % tid)
        for g in ttags:
            if not _in(g, tags_used):
                E("V-THEME", w, "%s names tag %r, which no observation carries" % (tid, g))

    # issues
    metrics = _ra().issue_metrics(study, fresh) if fresh is not None else {}
    seen = set()
    for n, i in enumerate(issues):
        iid = i.get("id")
        w = "issues.%s" % iid
        if not ITEM_ID.match(sstr(iid)):
            E("V-ISSUE", "issues[%d]" % n, "issue id %r is malformed" % iid)
        elif iid in seen:
            E("V-ISSUE", "issues[%d]" % n, "duplicate issue id %r" % iid)
        seen.add(iid)
        if not squash(i.get("title")):
            E("V-ISSUE", w, "%s has no title" % iid)
        sev = i.get("severity")
        if isinstance(sev, bool) or not isinstance(sev, int) or not 0 <= sev <= 4:
            E("V-ISSUE", w, "%s has severity %r — Nielsen's scale is 0 (not a problem) to 4 (catastrophe)" % (iid, sev))
            sev = None
        cited = as_list(i.get("observations"))
        if not cited:
            E("V-ISSUE", w, "%s cites no observation — an issue is what its observations show" % iid)
        for oid in cited:
            if not _in(oid, obs_ids):
                E("V-ISSUE", w, "%s cites observation %r, which does not exist" % (iid, oid))
        if i.get("task") is not None and task_ids is not None and not _in(i["task"], task_ids):
            E("V-ISSUE", w, "%s is about task %r, which this study does not have" % (iid, i["task"]))
        if sstr(i.get("screen")) and screen_ids and i["screen"] not in screen_ids:
            E("V-ISSUE", w, "%s is on screen %r, which is not a screen of this registry" % (iid, i["screen"]))
        if not squash(i.get("recommendation")):
            W("W-ISSUE", w, "%s has no recommendation" % iid)
        m = metrics.get(iid)
        if sev is not None and sev >= 3 and m and m.get("participants") == 1:
            W("W-ONE-PARTICIPANT", w, "%s is severity %d and rests on one participant" % (iid, sev))

    # the stored analysis against a fresh one
    if session:
        stored = study.get("analysis")
        have_sessions = any(e.get("kind") == "session" for e in live_evidence(study))
        if fresh is None:
            E("V-ANALYSIS", "analysis", "the analysis cannot be recomputed: %s" % why)
        elif not isinstance(stored, dict):
            if have_sessions:
                E("V-ANALYSIS", "analysis", "no analysis is stored — run `analyze %s`" % sid)
        elif stored.get("inputsHash") != fresh.get("inputsHash"):
            E("V-ANALYSIS", "analysis", "the analysis is stale: the sessions changed since it was computed (stored n=%s, now n=%s) — "
              "run `analyze %s`" % (stored.get("n"), fresh.get("n"), sid))
        elif json.dumps(stored, sort_keys=True) != json.dumps(fresh, sort_keys=True):
            E("V-ANALYSIS", "analysis", "the stored analysis differs from the one recomputed from the evidence (edited by hand, "
              "or the instrument or the issues changed since) — run `analyze %s`" % sid)
        for p, ids in dup_participants([(r, {}) for r in live_evidence(study) if r.get("kind") == "session"]).items():
            W("W-DUP-PARTICIPANT", "analysis", "%s has %d sessions (%s) — each counts as a separate participant in n"
              % (p, len(ids), ", ".join(ids)))

    # the report narrative
    rep = study.get("report")
    if rep is not None:
        for p in report_shape_problems(rep):
            E("V-REPORT", "report", p)
        iids = {i.get("id") for i in issues}
        for k, r in enumerate(as_list(as_dict(rep).get("recommendations"))):
            for x in as_list(as_dict(r).get("issues")):
                if not _in(x, iids):
                    E("V-REPORT", "report.recommendations[%d]" % k, "cites issue %r, which does not exist" % (x,))


def _expanded(study):
    """The study with its template questions expanded (a task section's SEQ is a question like any other)."""
    s = dict(study)
    try:
        s["instrument"] = expand_templates(as_dict(study.get("instrument")))
    except ResearchError:
        pass
    return s


def _pii(text):
    out = []

    def add(sev, code, where, msg):
        out.append("%s %s" % (code, msg))
    security_scan.scan_text(add, text, "quote")
    return out


def _verify_tally_ref(ref, where, study, tally_now, E):
    t = tally_now()
    if isinstance(t, str) or t is None:
        E("V-TALLY", where, "cites tally %s but no tally can be computed: %s" % (ref.get("tally"), t))
        return
    q = as_dict(t.get("byQuestion")).get(ref.get("tally"))
    if not q:
        E("V-TALLY", where, "tally has no question %r" % ref.get("tally"))
        return
    if ref.get("of") != q["n"]:
        E("V-TALLY", where, "%s: cited of=%r but the tally has n=%d" % (ref.get("tally"), ref.get("of"), q["n"]))
    if ref.get("stat") in TEMPLATES:
        sc = as_dict(q.get("score"))
        if sc.get("metric") != ref["stat"] or sc.get("value") is None:
            E("V-TALLY", where, "%s: no %s score to cite (the tally holds %s)" %
              (ref.get("tally"), ref["stat"], sc.get("metric") or "none"))
            return
        for fld in ("value", "pct"):
            if fld not in ref and fld == "value":
                E("V-TALLY", where, "%s: a score citation needs `value` and `of`" % ref.get("tally"))
                continue
            if fld not in ref:
                continue
            v = ref[fld]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not isinstance(sc.get(fld), (int, float)):
                E("V-TALLY", where, "%s: no %s %s to cite" % (ref.get("tally"), ref["stat"], fld))
            elif abs(sc[fld] - v) > 0.5 * 10 ** -min(_decimals(v), 4) + 1e-9:
                E("V-TALLY", where, "%s: cited %s %s %r but the tally says %s" %
                  (ref.get("tally"), ref["stat"], fld, v, round(sc[fld], 2)))
    elif ref.get("stat") == "mean":
        v = ref.get("value")
        if not isinstance(v, (int, float)) or q.get("mean") is None:
            E("V-TALLY", where, "%s: no mean to cite" % ref.get("tally"))
        elif abs(q["mean"] - v) > 0.5 * 10 ** -min(_decimals(v), 4) + 1e-9:
            E("V-TALLY", where, "%s: cited mean %r but the tally says %s" % (ref.get("tally"), v, round(q["mean"], 2)))
    elif "option" in ref:
        have = q["counts"].get(ref["option"])
        if have is None:
            E("V-TALLY", where, "%s has no option %r in the tally" % (ref.get("tally"), ref["option"]))
        elif ref.get("count") != have:
            E("V-TALLY", where, "%s / %s: cited count %r but the tally says %d" % (ref.get("tally"), ref["option"], ref.get("count"), have))
    else:
        E("V-TALLY", where, "a tally citation needs `option` + `count` + `of`, or `stat: mean` + `value` + `of`")


# ── instrument files ─────────────────────────────────────────────────────────

def proto_link(entry=None, role=None):
    q = urllib.parse.quote
    if entry:
        return "/?entry=%s%s" % (q(entry, safe="-_.~"), "&role=" + q(role, safe="-_.~") if role else "")
    return "/?role=%s" % q(role, safe="-_.~") if role else "/"


def _header(study):
    lines = ["# %s" % squash(study.get("title") or study.get("id")),
             "",
             "DRAFT — not approved" if study.get("status") == "draft" else "Approved at G-STUDY",
             "",
             "- Study: `%s` (%s)" % (study.get("id"), study.get("method")),
             "- Question: %s" % squash(study.get("question"))]
    a = as_dict(study.get("audience"))
    who = ", ".join(as_list(a.get("roles")))
    if squash(a.get("segment")):
        who = (who + " — " if who else "") + squash(a["segment"])
    lines.append("- Audience: %s (target n = %s)" % (who or "unspecified", a.get("targetN", "?")))
    inst = as_dict(study.get("instrument"))
    if inst.get("durationMin"):
        lines.append("- Duration: about %s minutes" % inst["durationMin"])
    if inst.get("lang"):
        lines.append("- Language: %s" % inst["lang"])
    return lines


def _researcher_notes(study):
    lines = ["", "## Researcher notes — do not show to respondents", ""]
    lines.append("Targets: %s" % (", ".join(target_str(t) for t in as_list(study.get("targets"))) or "none"))
    lines.append("")
    for h in as_list(study.get("hypotheses")):
        if not isinstance(h, dict):
            continue
        lines.append("- **%s** %s" % (h.get("id"), squash(h.get("statement"))))
        lines.append("  - supported if: %s" % squash(h.get("supportedIf")))
        lines.append("  - refuted if: %s" % squash(h.get("refutedIf")))
        tq = [q.get("id") for _s, q in all_questions(study) if h.get("id") in as_list(q.get("tests"))]
        lines.append("  - tested by: %s" % (", ".join(tq) or "nothing"))
    return lines


def render_survey(study):
    inst = as_dict(study.get("instrument"))
    L = _header(study)
    L += ["", "## Introduction", "", squash(inst.get("intro")), "", "## Consent", "", squash(inst.get("consent"))]
    n = 0
    for sec in as_list(inst.get("sections")):
        if not isinstance(sec, dict):
            continue
        L += ["", "## %s" % squash(sec.get("title") or sec.get("purpose")), "", "_Purpose: %s_" % sec.get("purpose")]
        for q in as_list(sec.get("questions")):
            if not isinstance(q, dict):
                continue
            n += 1
            tags = [q.get("type", "?")]
            if q.get("required"):
                tags.append("required")
            L += ["", "%d. **%s** — %s (%s)" % (n, q.get("id"), squash(q.get("text")), ", ".join(tags))]
            keep = {key(v) for v in as_list(q.get("qualifies"))}
            for o in as_list(q.get("options")):
                L.append("   - [ ] %s%s" % (squash(o), " (keeps the respondent)" if key(o) in keep else ""))
            sc = q.get("scale")
            if isinstance(sc, dict):
                L.append("   - Scale %s to %s: %s … %s" % (sc.get("min"), sc.get("max"),
                                                           squash(sc.get("minLabel")), squash(sc.get("maxLabel"))))
    L += ["", "## Closing", "", squash(inst.get("closing"))]
    L += _researcher_notes(study)
    return "\n".join(L) + "\n"


def render_template(study):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow([q.get("id") for _s, q in all_questions(study)])
    return out.getvalue()


def render_interview(study):
    inst = as_dict(study.get("instrument"))
    L = _header(study)
    L += ["", "## Say first", "", squash(inst.get("intro")), "", "## Consent (read, then record the answer)", "",
          squash(inst.get("consent"))]
    n = 0
    for sec in as_list(inst.get("sections")):
        if not isinstance(sec, dict):
            continue
        L += ["", "## %s" % squash(sec.get("title") or sec.get("purpose")), "", "_Purpose: %s_" % sec.get("purpose")]
        for q in as_list(sec.get("questions")):
            if not isinstance(q, dict):
                continue
            n += 1
            L += ["", "%d. **%s** — %s" % (n, q.get("id"), squash(q.get("text")))]
            if as_list(q.get("tests")):
                L.append("   - tests: %s" % ", ".join(str(t) for t in q["tests"]))
            for p in as_list(q.get("probes")):
                L.append("   - probe: %s" % squash(p))
            tk = q.get("task")
            if isinstance(tk, dict):
                L.append("   - task screen: `%s`%s" % (tk.get("screen"), ", role `%s`" % tk["role"] if tk.get("role") else ""))
                L.append("   - open: `%s`" % proto_link(tk.get("entry"), tk.get("role")))
                L.append("   - done when: %s" % squash(tk.get("success")))
    L += ["", "## Closing", "", squash(inst.get("closing"))]
    L += _researcher_notes(study)
    return "\n".join(L) + "\n"


def write_instrument_files(base, study, reg=None):
    """The readable instrument (and a survey's CSV template), plus the research documents research_report.files_for
    makes for the method (plan, moderator guide, tasks, consent, screener, note-taking sheet). Generated files:
    the same study -> the same bytes, and a rewrite replaces them."""
    sid = study["id"]
    ensure_dir(base, study_rel(sid))
    ensure_dir(base, study_rel(sid) + "/instrument")
    method = study.get("method")
    files = ({"survey.md": render_survey(study), "responses-template.csv": render_template(study)}
             if method == "survey" else {"interview-guide.md": render_interview(study)} if method == "interview" else {})
    files.update(_rr().files_for(study, reg if isinstance(reg, dict) else {}))
    written = []
    for name, text in files.items():
        rel = "%s/instrument/%s" % (study_rel(sid), name)
        path = under(base, rel)
        if os.path.islink(path):
            raise ResearchError("%s is a symlink — refusing to write through it" % rel)
        pbslice.atomic_write_text(path, text)
        written.append(rel)
    return written


# ── gaps / seed ──────────────────────────────────────────────────────────────

def rule_open(r):
    """What the shell's pbRuleOpen reads: stillOpen items, and an unconfirmed ASSUMPTION."""
    d = as_dict(r.get("decision"))
    v = d["stillOpen"] if d.get("stillOpen") is not None else r.get("stillOpen")
    items = [x for x in v if x] if isinstance(v, list) else ([v] if v else [])
    live = [x for x in items if not (isinstance(x, dict) and sstr(x.get("status")).lower() in
                                     ("resolved", "closed", "answered", "accepted", "settled"))]
    assume = bool(re.search(r"\bASSUMPTION\b", sstr(d.get("why")) + " " + sstr(r.get("summary"))))
    return live, assume


def _open_text(x):
    if isinstance(x, dict):
        return sstr(x.get("question") or x.get("text") or x.get("q")) or json.dumps(x, ensure_ascii=False)
    return str(x)


def collect_gaps(reg):
    rows = {}

    def add(kind, ident, title, roles, why, score):
        r = rows.setdefault((kind, ident), {"kind": kind, "id": ident, "title": title, "roles": list(roles),
                                            "why": [], "score": 0})
        r["why"].append(why)
        r["score"] += score

    cited = set()
    for st in [s for s in studies_of(reg)]:
        for f in as_list(st.get("findings")):
            for t in as_list(as_dict(f).get("targets")):
                if isinstance(t, dict):
                    cited.add((t.get("kind"), t.get("id")))
    for r in rules_of(reg):
        rid, title = r.get("id"), sstr(r.get("title")) or r.get("id")
        live, assume = rule_open(r)
        if live:
            add("rule", rid, title, as_list(r.get("roles")),
                "%d open question%s: %s" % (len(live), "" if len(live) == 1 else "s", squash(_open_text(live[0]))[:140]),
                GAP_BASE + 5 * min(len(live), 4))
        if assume:
            add("rule", rid, title, as_list(r.get("roles")), "rests on an ASSUMPTION no one has confirmed", GAP_BASE)
        for b in as_list(r.get("blocks")):
            if isinstance(b, dict) and b.get("type") == "params":
                for it in as_list(b.get("items")):
                    if isinstance(it, dict) and it.get("source") in ("assumed", "invented"):
                        add("rule", rid, title, as_list(r.get("roles")),
                            "parameter %r is %s" % (it.get("name"), it["source"]),
                            GAP_BASE if it["source"] == "invented" else 25)
    for j in jobs_of(reg):
        jid = j.get("id")
        title = sstr(j.get("title")) or squash(j.get("want")) or jid
        reasons = []
        if squash(j.get("gap")):
            reasons.append(("gap: %s" % squash(j["gap"])[:140], 40))
        if ("job", jid) not in cited:
            reasons.append(("no research finding cites it", 10))
        if reasons:
            bonus = {"P1": 20, "P2": 10}.get(j.get("priority"), 0)
            for why, sc in reasons:
                add("job", jid, title, as_list(j.get("roles")), why, sc)
            rows[("job", jid)]["score"] += bonus
            if bonus:
                rows[("job", jid)]["priority"] = j.get("priority")
    story_names = {}
    for s in stories_of(reg):
        story_names[sstr(s.get("title"))] = s.get("id") or s.get("title")
        if sstr(s.get("status")).lower() == "open":
            add("story", s.get("id") or s.get("title"), sstr(s.get("title")), as_list(s.get("roles")),
                "the story is open", 15)
    for w in as_list(as_dict(reg.get("flow")).get("coverageWarnings")):
        d = w if isinstance(w, dict) else {"note": w}
        if sstr(d.get("status")).lower() in ("resolved", "accepted"):
            continue
        note = squash(d.get("note"))
        if sstr(d.get("title")) in story_names:
            add("story", story_names[d["title"]], d["title"], [], "uncovered: %s" % note[:140], 15)
        else:
            add("feature", squash(d.get("title") or note)[:80], squash(d.get("title") or note)[:80], [],
                "uncovered (%s): %s" % (d.get("category", "gap"), note[:140]), 15)
    for st in studies_of(reg):
        if scope_of(st) == "instrument":        # it legitimately ends at `approved`: no results are due, so nothing is open
            continue
        for h in as_list(st.get("hypotheses")):
            if isinstance(h, dict) and h.get("verdict") == "inconclusive":
                ts = [t for t in as_list(h.get("targets")) + as_list(st.get("targets")) if isinstance(t, dict)][:1] \
                    or [{"kind": "feature", "id": squash(h.get("statement"))[:80]}]
                add(ts[0]["kind"], ts[0]["id"], squash(h.get("statement"))[:80], as_list(as_dict(st.get("audience")).get("roles")),
                    "%s in %s was inconclusive" % (h.get("id"), st.get("id")), 35)
    out = sorted(rows.values(), key=lambda r: (-r["score"], r["kind"], str(r["id"])))
    for n, r in enumerate(out, 1):
        r["rank"] = n
        r["why"] = "; ".join(r["why"])
        r["target"] = "%s:%s" % (r["kind"], r["id"])
    return out


def _path_tokens(path):
    return [key(t) for t in re.split(r"\s*(?:→|->|>|/)\s*", sstr(path)) if t.strip()]


def _story_screens(reg, story):
    toks = set(_path_tokens(story.get("path")))
    return [s.get("id") for s in screens_of(reg) if key(s.get("id")) in toks or key(s.get("name")) in toks]


def _story_view(s):
    return {"id": s.get("id"), "title": s.get("title"), "priority": s.get("priority"), "path": s.get("path"),
            "jtbd": s.get("jtbd"),
            "scenarios": [sstr(x.get("text")) if isinstance(x, dict) else sstr(x) for x in as_list(s.get("scenarios"))]}


def _rule_view(r):
    d = as_dict(r.get("decision"))
    live, assume = rule_open(r)
    return {"id": r.get("id"), "title": r.get("title"), "kind": r.get("kind"), "summary": r.get("summary"),
            "decision": {k: d.get(k) for k in ("question", "chose", "why") if d.get(k)},
            "open": [squash(_open_text(x)) for x in live], "assumption": assume}


def seed_target(reg, t):
    k, i = t["kind"], t["id"]
    p = target_problem(reg, t)
    if p:
        raise ResearchError(p)
    jobs, stories, rules, screens, roles = [], [], [], [], []
    out = {"target": "%s:%s" % (k, i), "kind": k}
    all_jobs, all_stories, all_rules = jobs_of(reg), stories_of(reg), rules_of(reg)

    def touching_rules(screen_ids, job_id=None):
        res = []
        for r in all_rules:
            disp = {key(x) for x in as_list(r.get("displayedIn"))}
            sid_hit = any(key(s) in disp for s in screen_ids)
            if sid_hit or (job_id and job_id in as_list(r.get("jobs"))):
                res.append(r)
        return res

    if k == "job":
        j = next(x for x in all_jobs if x.get("id") == i)
        out["job"] = {f: j.get(f) for f in ("id", "priority", "when", "want", "so", "gap", "source") if j.get(f)}
        roles, screens = as_list(j.get("roles")), as_list(j.get("screens"))
        stories = [s for s in all_stories if i in as_list(s.get("jobs")) or s.get("job") == i
                   or set(_story_screens(reg, s)) & set(screens)]
        rules = touching_rules(screens, i)
    elif k == "story":
        s = next(x for x in all_stories if i in (x.get("id"), x.get("title")))
        stories, screens = [s], _story_screens(reg, s)
        jobs = [j for j in all_jobs if s.get("id") and s.get("id") in as_list(j.get("stories"))
                or set(as_list(j.get("screens"))) & set(screens)]
        roles = sorted({r for j in jobs for r in as_list(j.get("roles"))})
        rules = touching_rules(screens)
    elif k == "rule":
        r = next(x for x in all_rules if x.get("id") == i)
        rules = [r]
        screens = [s.get("id") for s in screens_of(reg) if key(s.get("id")) in {key(x) for x in as_list(r.get("displayedIn"))}]
        jobs = [j for j in all_jobs if i in as_list(j.get("rules")) or r.get("id") in as_list(j.get("rules"))
                or set(as_list(j.get("screens"))) & set(screens)]
        roles = sorted({x for j in jobs for x in as_list(j.get("roles"))} | set(as_list(r.get("roles"))))
        stories = [s for s in all_stories if set(_story_screens(reg, s)) & set(screens)]
    elif k == "screen":
        s = next(x for x in screens_of(reg) if x.get("id") == i)
        screens = [i]
        out["screen"] = {"id": i, "name": s.get("name")}
        jobs = [j for j in all_jobs if i in as_list(j.get("screens"))]
        roles = sorted({x for j in jobs for x in as_list(j.get("roles"))} | set(as_list(s.get("roles"))))
        stories = [x for x in all_stories if i in _story_screens(reg, x)]
        rules = touching_rules([i])
    elif k == "component":
        c = next(x for x in components_of(reg) if x.get("id") == i)
        out["component"] = {"id": i, "name": c.get("name"), "level": c.get("level")}
    else:
        out["feature"] = i
    if jobs:
        out["jobs"] = [{f: j.get(f) for f in ("id", "priority", "when", "want", "so") if j.get(f)} for j in jobs]
    out["roles"] = roles
    out["screens"] = screens
    out["stories"] = [_story_view(s) for s in stories]
    out["rules"] = [_rule_view(r) for r in rules]
    return out


def seed_links(reg, roles, screens):
    links, seen = [], set()
    ents = entries_of(reg)
    for r in roles:
        path = proto_link(None, r)
        if path not in seen:
            seen.add(path)
            links.append({"label": "as %s" % r, "path": path})
        for e in ents:
            if e.get("role") in (None, r) and (e.get("screen") in screens or not screens):
                p = proto_link(e.get("id"), r)
                if p not in seen:
                    seen.add(p)
                    links.append({"label": "%s as %s" % (e.get("name") or e.get("id"), r), "path": p})
    return links


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_gaps(a):
    reg = load_registry(a.registry)
    rows = collect_gaps(reg)
    if a.role:
        rows = [r for r in rows if not r["roles"] or a.role in r["roles"]]
        for n, r in enumerate(rows, 1):
            r["rank"] = n
    lines = ["%2d. %-24s %s — %s%s" % (r["rank"], r["target"], r["title"], r["why"],
                                     "  [%s]" % ", ".join(r["roles"]) if r["roles"] else "") for r in rows]
    return {"gaps": rows}, lines or ["nothing is unsure that the registry can see"], EXIT_OK


def cmd_seed(a):
    reg = load_registry(a.registry)
    targets = [parse_target(t) for t in a.targets]
    seeds = [seed_target(reg, t) for t in targets]
    roles, screens = [], []
    for s in seeds:
        roles += [r for r in s["roles"] if r not in roles]
        screens += [x for x in s["screens"] if x not in screens]
    links = seed_links(reg, roles, screens)
    lines = []
    for s in seeds:
        lines.append(s["target"] + "  roles: " + (", ".join(s["roles"]) or "-") + "  screens: " + (", ".join(s["screens"]) or "-"))
        for st in s["stories"]:
            lines.append("  story: %s" % st["title"])
        for r in s["rules"]:
            lines.append("  rule: %s%s" % (r["id"], " (open)" if r["open"] or r["assumption"] else ""))
    lines += ["  link: %s  %s" % (l["path"], l["label"]) for l in links]
    return {"seeds": seeds, "links": links, "entries": [e.get("id") for e in entries_of(reg)]}, lines, EXIT_OK


def cmd_init(a):
    sid = a.id
    if not STUDY_ID.match(sid):
        raise ResearchError("study id %r must match rs-<lowercase-kebab>" % sid, EXIT_USAGE)
    roles = list(dict.fromkeys(a.role or []))
    segment = squash(a.segment)
    if not roles and not segment:
        raise ResearchError("a study always names who it asks: give --role and/or --segment")
    targets = [parse_target(t) for t in (a.target or [])]
    if a.target_n is not None and a.target_n < 1:
        raise ResearchError("--target-n must be at least 1", EXIT_USAGE)
    with locked(a.registry, "research.py init") as reg:
        if any(s.get("id") == sid for s in studies_of(reg)):
            raise ResearchError("study %s already exists" % sid)
        declared = role_ids(reg)
        bad = [r for r in roles if declared and r not in declared]
        if bad:
            raise ResearchError("role %s is not declared in meta.roles (%s)" % (", ".join(bad), ", ".join(declared)))
        for t in targets:
            p = target_problem(reg, t)
            if p:
                raise ResearchError(p)
        audience = {"roles": roles}
        if segment:
            audience["segment"] = segment
        audience["targetN"] = a.target_n if a.target_n is not None else DEFAULT_N[a.method]
        mode = a.mode or "moderated"
        study = {"id": sid, "title": squash(a.title) or squash(a.question)[:80], "question": squash(a.question),
                 "method": a.method, "status": "draft", "scope": a.scope, "setup": squash(a.setup),
                 "createdAt": now_iso(), "audience": audience,
                 "targets": targets, "hypotheses": [],
                 "instrument": {"lang": "en", "intro": "", "consent": "", "durationMin": None, "closing": "", "sections": []},
                 "evidence": [], "findings": [], "gates": []}
        if a.method in SESSION_METHODS:
            study["instrument"]["mode"] = mode
        study["logistics"] = {"checklist": _rm().default_checklist(a.method, mode)}
        res = reg.get("research")
        if not isinstance(res, dict):
            res = reg["research"] = {"populated": True, "studies": []}
        res["populated"] = True
        res.setdefault("studies", []).append(study)
        pbslice._write(a.registry, reg)
    nxt = ("write the research plan (`brief %s --file …`), the hypotheses and the instrument, then `plan %s --file …`" % (sid, sid)
           if a.method in SESSION_METHODS else "write hypotheses + instrument, then `plan %s --file …`" % sid)
    return {"created": sid, "study": study}, ["created draft study %s (%s, scope %s) — next: %s"
                                              % (sid, a.method, a.scope, nxt)], EXIT_OK


def cmd_scope(a):
    if a.scope is None and a.setup is None:
        raise ResearchError("scope needs --scope instrument|collect and/or --setup \"<text>\"", EXIT_USAGE)
    with locked(a.registry, "research.py scope") as reg:
        st = find_study(reg, a.id)
        was = (scope_of(st), st.get("setup", ""))
        if a.scope is not None:
            st["scope"] = a.scope
        if a.setup is not None:
            st["setup"] = squash(a.setup)
        elif "setup" not in st:
            st["setup"] = ""
        pbslice._write(a.registry, reg)
    now = (scope_of(st), st["setup"])
    lines = ["%s: scope %s, setup %s" % (a.id, now[0], repr(now[1]) if now[1] else "none")]
    if was[0] != now[0]:
        lines.append("scope changed %s -> %s (no gate written)" % (was[0], now[0]))
    return {"scope": now[0], "setup": now[1], "was": {"scope": was[0], "setup": was[1]}}, lines, EXIT_OK


def _read_json_arg(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ResearchError("file not found: %s" % path, EXIT_USAGE)
    except ValueError as e:
        raise ResearchError("%s is not valid JSON: %s" % (path, e), EXIT_USAGE)
    if not isinstance(data, dict):
        raise ResearchError("%s must hold a JSON object" % path, EXIT_USAGE)
    return data


# ── the research plan document (study.plan), participants and logistics ──────

PLAN_TEXT = ("background", "decision", "methodRationale", "budget")
PLAN_LISTS = ("objectives", "researchQuestions", "materials")
PLAN_OBJECTS = {"participants": {"criteria": "list", "exclude": "list", "n": "int", "segments": "list"},
                "recruitment": {"channel": "text", "incentive": "text", "note": "text"},
                "schedule": {"start": "date", "end": "date", "sessionMinutes": "int"},
                "team": {"moderator": "text", "notetaker": "text", "observers": "list"}}
PLAN_ROWS = {"risks": ("risk", "mitigation"), "timeline": ("milestone", "date")}
PLAN_KEYS = PLAN_TEXT + PLAN_LISTS + tuple(PLAN_OBJECTS) + tuple(PLAN_ROWS)
# changing one of these changes what the study is for or who it asks, so G-STUDY is asked for again;
# the rest (schedule, team, recruitment, materials, risks, timeline, budget, background) is logistics
PLAN_GATE_KEYS = ("objectives", "researchQuestions", "decision", "methodRationale", "participants")


def refuse_pii(text, where):
    """Participants are pseudonyms: free text that carries an email, a phone number or a secret is refused."""
    found = []

    def add(sev, code, w, msg):
        found.append(code)
    security_scan.scan_text(add, sstr(text), where)
    if found:
        what = {"R-SEC-EMAIL": "an email address", "R-SEC-PII": "a phone number or an ID number",
                "R-SEC-KEY": "a credential"}.get(found[0], "personal data")
        raise ResearchError("%s looks like it holds %s — participants are pseudonyms (P01…); keep contact details out of the study"
                            % (where, what))


def validate_plan(plan):
    """The plan object cleaned (strings squashed), or a ResearchError (exit 2) naming every problem."""
    if not isinstance(plan, dict):
        raise ResearchError("the plan must be an object", EXIT_USAGE)
    problems, out = [], {}
    extra = sorted(set(plan) - set(PLAN_KEYS))
    if extra:
        problems.append("unknown plan key(s): %s (known: %s)" % (", ".join(extra), ", ".join(PLAN_KEYS)))

    def strings(v, w):
        if isinstance(v, list) and all(isinstance(x, str) and squash(x) for x in v):
            return [squash(x) for x in v]
        problems.append("%s must be a list of non-empty strings" % w)
        return []

    for k, v in plan.items():
        if k in PLAN_TEXT:
            if isinstance(v, str):
                out[k] = squash(v)
            else:
                problems.append("%s must be a string" % k)
        elif k in PLAN_LISTS:
            out[k] = strings(v, k)
        elif k in PLAN_OBJECTS:
            spec = PLAN_OBJECTS[k]
            if not isinstance(v, dict):
                problems.append("%s must be an object {%s}" % (k, ", ".join(spec)))
                continue
            sub = {}
            bad = sorted(set(v) - set(spec))
            if bad:
                problems.append("%s: unknown key(s) %s (known: %s)" % (k, ", ".join(bad), ", ".join(spec)))
            for sk, sv in v.items():
                kind = spec.get(sk)
                w = "%s.%s" % (k, sk)
                if kind == "list":
                    sub[sk] = strings(sv, w)
                elif kind == "text":
                    if isinstance(sv, str):
                        sub[sk] = squash(sv)
                    else:
                        problems.append("%s must be a string" % w)
                elif kind == "int":
                    if isinstance(sv, int) and not isinstance(sv, bool) and sv >= 1:
                        sub[sk] = sv
                    else:
                        problems.append("%s must be a whole number, 1 or more" % w)
                elif kind == "date":
                    if isinstance(sv, str) and DATE.match(sv) and _valid_date(sv):
                        sub[sk] = sv
                    else:
                        problems.append("%s must be a date, YYYY-MM-DD" % w)
            sch = sub if k == "schedule" else {}
            if sch.get("start") and sch.get("end") and sch["end"] < sch["start"]:
                problems.append("schedule.end is before schedule.start")
            out[k] = sub
        elif k in PLAN_ROWS:
            f1, f2 = PLAN_ROWS[k]
            if not isinstance(v, list):
                problems.append("%s must be a list of {%s, %s}" % (k, f1, f2))
                continue
            rows = []
            for i, r in enumerate(v):
                if not isinstance(r, dict) or sorted(set(r) - {f1, f2}) or not squash(r.get(f1) if isinstance(r.get(f1), str) else ""):
                    problems.append("%s[%d] must be {%s, %s?} with a non-empty %s" % (k, i, f1, f2, f1))
                    continue
                row = {f1: squash(r[f1])}
                if f2 in r:
                    if not isinstance(r[f2], str):
                        problems.append("%s[%d].%s must be a string" % (k, i, f2))
                    elif f2 == "date" and r[f2] and not (DATE.match(r[f2]) and _valid_date(r[f2])):
                        problems.append("%s[%d].date must be YYYY-MM-DD" % (k, i))
                    else:
                        row[f2] = squash(r[f2])
                rows.append(row)
            out[k] = rows
    if problems:
        raise ResearchError("the plan was not accepted: %d problem(s)" % len(problems),
                            EXIT_USAGE, data={"problems": problems,
                                              "errors": [{"code": "P-PLAN", "where": "plan", "msg": p} for p in problems]})
    for where, text in _plan_strings(out):
        refuse_pii(text, "plan." + where)
    return out


def _valid_date(s):
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _plan_strings(plan, prefix=""):
    for k, v in plan.items():
        w = prefix + k
        if isinstance(v, str):
            yield w, v
        elif isinstance(v, dict):
            for item in _plan_strings(v, w + "."):
                yield item
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, str):
                    yield "%s[%d]" % (w, i), x
                elif isinstance(x, dict):
                    for item in _plan_strings(x, "%s[%d]." % (w, i)):
                        yield item


def merge_plan(old, new):
    """`new` over `old`: a key replaces, except the four object keys, which merge key by key."""
    out = json.loads(json.dumps(as_dict(old)))
    for k, v in new.items():
        if k in PLAN_OBJECTS and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _plan_arg(data):
    """The plan inside a brief/plan file: the object itself, or {"plan": {...}}."""
    if set(data) == {"plan"} and isinstance(data["plan"], dict):
        return data["plan"]
    return data


def withdraw_gate(st):
    """G-STUDY is asked for again: back to a draft, the gate marked withdrawn, `plan-approved` unticked."""
    st["status"] = "draft"
    for g in as_list(st.get("gates")):
        if isinstance(g, dict) and g.get("gate") == "G-STUDY" and not g.get("withdrawnAt"):
            g["withdrawnAt"] = now_iso()
    tick(st, "plan-approved", False)


def checklist_of(st):
    cl = as_dict(st.get("logistics")).get("checklist")
    return [c for c in as_list(cl) if isinstance(c, dict)]


def tick(st, item_id, done):
    """Set a checklist item done / not done. True when the study has that item."""
    for c in checklist_of(st):
        if c.get("id") == item_id:
            c["done"] = bool(done)
            c["at"] = now_iso() if done else None
            return True
    return False


def sync_checklist(st):
    """Add any default checklist item the study's method and mode call for that it does not have yet."""
    method = st.get("method")
    mode = as_dict(st.get("instrument")).get("mode", "moderated")
    have = {c.get("id") for c in checklist_of(st)}
    if not isinstance(st.get("logistics"), dict):
        st["logistics"] = {"checklist": []}
    if not isinstance(st["logistics"].get("checklist"), list):
        st["logistics"]["checklist"] = []
    for item in _rm().default_checklist(method, mode):
        if item["id"] not in have:
            st["logistics"]["checklist"].append(item)


def cmd_brief(a):
    data = _plan_arg(_read_json_arg(a.file))
    if not data:
        raise ResearchError("the brief file has nothing to merge", EXIT_USAGE)
    new = validate_plan(data)
    with locked(a.registry, "research.py brief") as reg:
        st = find_study(reg, a.id)
        old = as_dict(st.get("plan"))
        merged = merge_plan(old, new)
        changed = sorted(k for k in new if merged.get(k) != old.get(k))
        gate_changed = [k for k in changed if k in PLAN_GATE_KEYS]
        withdrawn = st.get("status") == "approved" and bool(gate_changed)
        st["plan"] = merged
        if withdrawn:
            withdraw_gate(st)
        if st.get("status") != "draft" or withdrawn:
            write_instrument_files(base_of(a.registry), st, reg)       # plan.md et al. exist from G-STUDY on: keep them current
        pbslice._write(a.registry, reg)
    lines = ["plan of %s: %s" % (a.id, ("updated " + ", ".join(changed)) if changed else "nothing changed")]
    if withdrawn:
        lines.append("G-STUDY withdrawn (%s changed): the study is a draft again — run `check` and `approve` once more"
                     % ", ".join(gate_changed))
    elif changed and st.get("evidence"):
        lines.append("note: the plan changed after sessions were stored; the evidence is untouched")
    return {"briefed": a.id, "changed": changed, "withdrawn": withdrawn, "plan": merged}, lines, EXIT_OK


def cmd_plan(a):
    data = _read_json_arg(a.file)
    allowed = {"hypotheses", "instrument", "audience", "plan"}
    extra = sorted(set(data) - allowed)
    if extra:
        raise ResearchError("plan takes {hypotheses, instrument, audience?, plan?}; unexpected: %s" % ", ".join(extra), EXIT_USAGE)
    if "hypotheses" in data and not (isinstance(data["hypotheses"], list) and all(isinstance(h, dict) for h in data["hypotheses"])):
        raise ResearchError("hypotheses must be a list of objects", EXIT_USAGE)
    if "instrument" in data and not isinstance(data["instrument"], dict):
        raise ResearchError("instrument must be an object", EXIT_USAGE)
    if "audience" in data and not isinstance(data["audience"], dict):
        raise ResearchError("audience must be an object", EXIT_USAGE)
    if not (set(data) & allowed):
        raise ResearchError("the plan file has nothing to merge", EXIT_USAGE)
    if "instrument" in data:
        data["instrument"] = expand_templates(data["instrument"])     # raises a ResearchError on a bad template entry
    new_plan = validate_plan(data["plan"]) if "plan" in data else None
    study_part = bool(set(data) & {"hypotheses", "instrument", "audience"})
    with locked(a.registry, "research.py plan") as reg:
        st = find_study(reg, a.id)
        if study_part and st.get("evidence"):
            raise ResearchError("%s already holds evidence — a changed instrument would no longer match the "
                                "responses. Open a new study (`init`) instead." % a.id)
        if study_part and st.get("status") not in ("draft", "approved"):
            raise ResearchError("%s is %s; a plan can change only a draft or an approved study" % (a.id, st.get("status")))
        if "audience" in data:
            aud = dict(as_dict(st.get("audience")))
            aud.update(data["audience"])
            declared = role_ids(reg)
            bad = [r for r in as_list(aud.get("roles")) if declared and r not in declared]
            if bad:
                raise ResearchError("role %s is not declared in meta.roles" % ", ".join(bad))
            if not as_list(aud.get("roles")) and not squash(aud.get("segment")):
                raise ResearchError("a study always names who it asks: the audience needs a role or a segment")
            st["audience"] = aud
        if "hypotheses" in data:
            hs = []
            for h in data["hypotheses"]:
                h = dict(h)
                h["verdict"] = None
                h["why"] = ""
                hs.append(h)
            st["hypotheses"] = hs
        if "instrument" in data:
            inst = data["instrument"]
            old_mode = as_dict(st.get("instrument")).get("mode")
            if st.get("method") in SESSION_METHODS and "mode" not in inst and old_mode:
                inst["mode"] = old_mode            # the run mode chosen at `init` stands until a plan says otherwise
            st["instrument"] = inst
            if st.get("method") in SESSION_METHODS:
                sync_checklist(st)                 # an unmoderated plan adds the kit items
        gate_changed = []
        if new_plan is not None:
            old_plan = as_dict(st.get("plan"))
            merged = merge_plan(old_plan, new_plan)
            gate_changed = [k for k in new_plan if k in PLAN_GATE_KEYS and merged.get(k) != old_plan.get(k)]
            st["plan"] = merged
        if study_part:
            st.pop("biasReview", None)      # a review answers one instrument; any plan makes it stale
        withdrawn = st.get("status") == "approved" and (study_part or bool(gate_changed))
        if withdrawn:
            withdraw_gate(st)
        if withdrawn or (new_plan is not None and st.get("status") != "draft"):
            write_instrument_files(base_of(a.registry), st, reg)
        pbslice._write(a.registry, reg)
    lines = ["merged the plan into %s" % a.id]
    if withdrawn:
        lines.append("G-STUDY withdrawn: the study is a draft again — run `check` and `approve` once more")
    return {"planned": a.id, "withdrawn": withdrawn}, lines, EXIT_OK


def _report(findings_errs, findings_warns, title):
    lines = []
    for f in findings_errs:
        lines.append("ERROR %s %s: %s" % (f["code"], f["where"], f["msg"]))
    for f in findings_warns:
        lines.append("warn  %s %s: %s" % (f["code"], f["where"], f["msg"]))
    lines.append("%s: %d error(s), %d warning(s)" % (title, len(findings_errs), len(findings_warns)))
    return lines


def cmd_check(a):
    reg = load_registry(a.registry)
    errs, warns = check_study(reg, copy_study(find_study(reg, a.id)))
    return ({"ok": not errs, "errors": errs, "warnings": warns},
            _report(errs, warns, "check %s" % a.id), EXIT_FAIL if errs else EXIT_OK)


def copy_study(s):
    return json.loads(json.dumps(s))


# ── bias review (an independent read of the questions alone) ─────────────────

REVIEW_FILE = "bias-review.md"
ORDER_ITEM = "order.general-first"
# code -> the closed question. `yes` always means the check held.
REVIEW_ITEMS = {
    "neutral": "Is the wording neutral — does nothing in it signal a preferred answer?",
    # A prompt and its follow-up ("Tell me about it. What happened?") are one thing, and read as two without this.
    "single": "Does it ask about one thing only, counting a follow-up on that same thing as part of it?",
    "actual": "Does it ask what the person did or experienced, rather than what they would do?",
    "plain": "Can someone who has never used the product understand it without explanation?",
    "unnamed": "Does it avoid naming or describing a specific product feature, screen or control before any task has been shown?",
    "goal": "Does it state a goal without saying which steps, screens or controls to use?",
    "options": "Do the options cover the answers people may give, without overlapping each other?",
    "scale": "Is the scale balanced, with both ends labelled?",
    # the session methods: a task is a scenario, so it is held to the scenario rules, not to the survey ones
    "nolabels": "Does it avoid the words of buttons, menus, screens or fields — words the participant could find just by looking for them?",
    "treewords": "Does it avoid the words of the menu labels listed under the tree, so the answer cannot be found by matching words alone?",
    "cardlead": "Do the card labels avoid sharing a leading word — no word starts more than two cards — so the cards cannot be grouped by their first word?",
    "cardone": "Does every card name one thing, with none that is two things or two actions at once?",
    "cardneutral": "Do the card labels avoid naming a category or signalling which group a card belongs in?",
}
CARD_ITEMS = (("cards.leadword", "cardlead"), ("cards.single", "cardone"), ("cards.neutral", "cardneutral"))
# Screener questions set the topic on purpose, so they are not held against the order.
ORDER_QUESTION = ("Leaving the screener aside, do the general questions come before the specific ones, and does no "
                  "earlier question reveal the answer to a later one?")


def instrument_hash(study):
    inst = json.dumps(as_dict(study.get("instrument")), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(inst.encode("utf-8"))


def _review_questions(study):
    """[(section index, purpose, question)] in order. Refuses a question that has no usable, unique id."""
    out, seen = [], set()
    for si, sec in enumerate(as_list(as_dict(study.get("instrument")).get("sections")), 1):
        if not isinstance(sec, dict):
            continue
        for q in as_list(sec.get("questions")):
            if not isinstance(q, dict):
                continue
            qid = q.get("id")
            if not ITEM_ID.match(sstr(qid)) or qid in seen:
                raise ResearchError("question id %r is missing, malformed or duplicated — run `check` first" % qid)
            seen.add(qid)
            out.append((si, sstr(sec.get("purpose")), q))
    return out


def _session_review_codes(method, purpose, q):
    """The yes/no items for one question of a session-method study. A task is a scenario on the prototype, a menu
    or a screen, so it is read against the scenario rules; the questions around it are asked on a form."""
    if any(k in q for k in TASK_KEYS):
        if method == "tree-test":
            return ["neutral", "single", "treewords"]
        return ["neutral", "single", "goal", "nolabels"]        # usability, first-click: no leading, one goal, no steps, no UI words
    codes = ["neutral", "single", "plain"]
    if purpose == "warmup":
        codes.append("unnamed")
    typ = q.get("type")
    if typ in ("single", "multi"):
        codes.append("options")
    if typ == "scale":
        codes.append("scale")
    return codes


def reviewable(study):
    """True when there is something for a reviewer to read: a question, or a card sort's cards."""
    return bool(all_questions(study)) or bool(as_list(as_dict(study.get("instrument")).get("cards")))


def review_items(study):
    """[(item id, question text)] — the closed yes/no items, deterministic. Template questions get none."""
    items = []
    method = study.get("method")
    session = method in SESSION_METHODS
    n_q = 0
    for _si, purpose, q in _review_questions(study):
        if "template" in q:
            continue
        n_q += 1
        qid, typ = q["id"], q.get("type") if study.get("method") == "survey" else None
        if session:
            items += [("%s.%s" % (qid, c), REVIEW_ITEMS[c]) for c in _session_review_codes(method, purpose, q)]
            continue
        if purpose == "task":
            # A task is a scenario on the product by design, so the questions about past behaviour and about
            # product knowledge do not apply. What can go wrong in one is giving the route away.
            codes = ["neutral", "goal"]
        else:
            codes = ["neutral", "single"]
            if purpose != "screener":
                codes.append("actual")
            codes.append("plain")
            if purpose != "screener":
                codes.append("unnamed")
        if typ in ("single", "multi"):
            codes.append("options")
        if typ == "scale":
            codes.append("scale")
        items += [("%s.%s" % (qid, c), REVIEW_ITEMS[c]) for c in codes]
    if method == "card-sort" and as_list(as_dict(study.get("instrument")).get("cards")):
        items += [(iid, REVIEW_ITEMS[c]) for iid, c in CARD_ITEMS]
    if not session or n_q >= 2:
        items.append((ORDER_ITEM, ORDER_QUESTION))
    return items


def render_bias_review(study):
    """The reviewer's whole world: each question's text, type, options and scale, its section purpose and
    order. Nothing about the study (no title, question, hypothesis, threshold, test, target, audience or setup)."""
    qs = _review_questions(study)
    survey = study.get("method") == "survey"
    session = study.get("method") in SESSION_METHODS
    typed = survey or session                    # a form question has options and a scale worth showing
    inst = as_dict(study.get("instrument"))
    L = ["# Question review", "",
         "You are reading the questions of a research instrument cold. You have been told nothing else about it,",
         "and you need nothing else: judge each item from the words of the question alone.", "",
         "## How to answer", "",
         "- Answer every item under *Items*, one row per item, in exactly this form and nothing else:",
         "",
         "  `<id> · yes|no|blocked · <evidence quoting the words>`", "",
         "- `yes` means the check held. `no` means it did not. `blocked` means you could not tell (say why).",
         "- Evidence quotes the words of the question that decided your answer.",
         "- Do not reword a question or an item, and do not add items.", "",
         "## Questions, in the order they are asked"]
    cur = None
    for si, purpose, q in qs:
        if si != cur:
            cur = si
            L += ["", "### Section %d — purpose: %s" % (si, purpose or "unspecified")]
        kind = (sstr(q.get("type")) or "unspecified") if survey else \
            ("a task shown to the participant" if session and any(k in q for k in TASK_KEYS) else
             (sstr(q.get("type")) or "text") if session else "asked aloud")
        L += ["", "**%s** — type: %s%s" % (q["id"], kind, "  (standard wording; no items below)" if "template" in q else ""),
              "  text: %s" % squash(q.get("text"))]
        opts = [squash(o) for o in as_list(q.get("options")) if isinstance(o, str)]
        if typed and opts:
            L.append("  options: %s" % " | ".join(opts))
        sc = q.get("scale")
        if typed and isinstance(sc, dict):
            L.append("  scale: %s to %s, %s = %s, %s = %s" % (sc.get("min"), sc.get("max"), sc.get("min"), squash(sc.get("minLabel")),
                                                              sc.get("max"), squash(sc.get("maxLabel"))))
    if study.get("method") == "tree-test" and as_list(inst.get("tree")):
        # every label of the menu the tasks are about (the tasks are judged against these words); never the answer
        by_id = {n.get("id"): n for n in as_list(inst.get("tree")) if isinstance(n, dict) and isinstance(n.get("id"), str)}

        def depth(n, seen=()):
            p = n.get("parent")
            return 0 if p is None or p not in by_id or p in seen else 1 + depth(by_id[p], seen + (p,))
        L += ["", "## The menu labels the tasks are about", ""]
        L += ["%s- %s" % ("  " * depth(n), squash(n.get("label"))) for n in as_list(inst.get("tree")) if isinstance(n, dict)]
    if study.get("method") == "card-sort" and as_list(inst.get("cards")):
        L += ["", "## The cards, in the order they are listed", ""]
        L += ["- %s" % squash(c.get("label")) for c in as_list(inst.get("cards")) if isinstance(c, dict)]
    L += ["", "## Items", ""]
    L += ["%s · %s" % (iid, text) for iid, text in review_items(study)]
    return "\n".join(L) + "\n"


def parse_review_rows(text, expected):
    """(rows in item order, problems). A row is `<id> · yes|no|blocked · <evidence>`."""
    got, problems = {}, []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        s = re.sub(r"^(?:[-*]\s+)", "", s)
        if len(s) > 1 and s[0] == "`" and s[-1] == "`":
            s = s[1:-1].strip()
        parts = s.split("·", 2)
        if len(parts) < 3 or key(parts[1]) not in REVIEW_ANSWERS or not squash(parts[2]):
            problems.append("line %d is not `<id> · yes|no|blocked · <evidence>`: %r" % (n, line.strip()[:100]))
            continue
        iid, ans, ev = squash(parts[0]), key(parts[1]), squash(parts[2])
        if iid not in expected:
            problems.append("line %d: %r is not an item of this instrument" % (n, iid))
        elif iid in got:
            problems.append("line %d: %r is answered twice" % (n, iid))
        else:
            got[iid] = {"id": iid, "answer": ans, "evidence": ev}
    missing = [i for i in expected if i not in got]
    if missing:
        problems.append("%d item(s) have no row: %s" % (len(missing), ", ".join(missing[:12]) + (" …" if len(missing) > 12 else "")))
    return [got[i] for i in expected if i in got], problems


def review_flags(review):
    return [r for r in as_list(as_dict(review).get("rows")) if isinstance(r, dict) and r.get("answer") in ("no", "blocked")]


def cmd_review_plan(a):
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    if not reviewable(st):
        raise ResearchError("%s has no questions to review — `plan` first" % a.id)
    text = render_bias_review(st)
    base = base_of(a.registry)
    ensure_dir(base, study_rel(a.id))
    ensure_dir(base, study_rel(a.id) + "/instrument")
    rel = "%s/instrument/%s" % (study_rel(a.id), REVIEW_FILE)
    path = under(base, rel)
    if os.path.islink(path):
        raise ResearchError("%s is a symlink — refusing to write through it" % rel)
    pbslice.atomic_write_text(path, text)
    items = review_items(st)
    return ({"file": rel, "path": path, "items": [i for i, _t in items]},
            [rel, "%d item(s). Hand the reviewer this file and nothing else; save its rows and run "
                  "`review %s --file <rows>`." % (len(items), a.id)], EXIT_OK)


def cmd_review(a):
    try:
        with open(a.file, encoding="utf-8-sig") as f:
            text = f.read()
    except FileNotFoundError:
        raise ResearchError("file not found: %s" % a.file, EXIT_USAGE)
    except (OSError, UnicodeDecodeError) as e:
        raise ResearchError("cannot read %s: %s" % (a.file, e), EXIT_USAGE)
    with locked(a.registry, "research.py review") as reg:
        st = find_study(reg, a.id)
        if st.get("status") != "draft":
            raise ResearchError("%s is %s — a review is stored on a draft, before G-STUDY" % (a.id, st.get("status")))
        expected = [i for i, _t in review_items(st)]
        rows, problems = parse_review_rows(text, expected)
        if problems:
            raise ResearchError("the review was not stored: %d problem(s)" % len(problems),
                                data={"problems": problems, "errors": [{"code": "R-ROWS", "where": a.file, "msg": p} for p in problems]})
        summary = {k: sum(1 for r in rows if r["answer"] == k) for k in REVIEW_ANSWERS}
        st["biasReview"] = {"at": now_iso(), "instrumentHash": instrument_hash(st), "rows": rows, "summary": summary}
        pbslice._write(a.registry, reg)
    flags = review_flags(st["biasReview"])
    lines = ["review stored for %s: %d yes, %d no, %d blocked" % (a.id, summary["yes"], summary["no"], summary["blocked"])]
    lines += ["  %s %s · %s" % (r["answer"].upper(), r["id"], r["evidence"]) for r in flags]
    if flags:
        lines.append("approve will need --accept-review \"<why it stands>\" for the %d flagged row(s)" % len(flags))
    return {"reviewed": a.id, "summary": summary, "flags": flags}, lines, EXIT_OK


def cmd_approve(a):
    for flag, val in (("--skip-review", a.skip_review), ("--accept-review", a.accept_review)):
        if val is not None and not squash(val):
            raise ResearchError("%s needs a reason in words" % flag, EXIT_USAGE)
    with locked(a.registry, "research.py approve") as reg:
        st = find_study(reg, a.id)
        if st.get("status") != "draft":
            raise ResearchError("%s is %s — only a draft is approved (a plan on an approved study re-opens it)"
                                % (a.id, st.get("status")))
        errs, warns = check_study(reg, copy_study(st))
        if errs:
            raise ResearchError("G-STUDY refused: %d check error(s) — fix them first" % len(errs),
                                data={"errors": errs, "warnings": warns})
        rev = st.get("biasReview") if isinstance(st.get("biasReview"), dict) else None
        current = bool(rev) and rev.get("instrumentHash") == instrument_hash(st)
        gate = {"gate": "G-STUDY", "at": now_iso(), "note": squash(a.note)}
        flags = []
        if current:
            flags = review_flags(rev)
            gate["review"] = {"instrumentHash": rev["instrumentHash"], "summary": rev.get("summary")}
            if flags and a.accept_review is None:
                raise ResearchError(
                    "G-STUDY refused: the bias review has %d row(s) answered no or blocked. A human decides at the gate: "
                    "fix the question (`plan`, `review-plan`, `review`), or keep it and pass --accept-review \"<why it stands>\"." % len(flags),
                    data={"flags": flags, "errors": [{"code": "R-REVIEW", "where": r["id"], "msg": "%s · %s" % (r["answer"], r["evidence"])} for r in flags]})
            if flags:
                gate["acceptReview"] = squash(a.accept_review)
        elif a.skip_review is not None:
            gate["skipReview"] = squash(a.skip_review)
        else:
            raise ResearchError(
                "G-STUDY refused: %s. Run `review-plan %s`, have a fresh reviewer answer bias-review.md, then `review %s --file <rows>`; "
                "or pass --skip-review \"<the reason>\"." %
                ("the stored bias review is for an earlier version of the instrument" if rev else "the instrument has no bias review", a.id, a.id))
        st["status"] = "approved"
        st.setdefault("gates", []).append(gate)
        tick(st, "plan-approved", True)
        files = write_instrument_files(base_of(a.registry), st, reg)
        pbslice._write(a.registry, reg)
    lines = ["G-STUDY approved %s" % a.id] + files
    if "skipReview" in gate:
        lines.append("bias review SKIPPED: %s" % gate["skipReview"])
    lines += ["review %s %s · %s" % (r["answer"], r["id"], r["evidence"]) for r in flags]
    lines += ["warn  %s %s: %s" % (w["code"], w["where"], w["msg"]) for w in warns]
    return ({"approved": a.id, "files": files, "warnings": warns, "gate": gate, "reviewFlags": flags}, lines, EXIT_OK)


def cmd_export(a):
    reg = load_registry(a.registry)
    files = write_instrument_files(base_of(a.registry), copy_study(find_study(reg, a.id)), reg)
    return {"files": files}, files, EXIT_OK


def _import_session(a, raw):
    """--kind session: a pb-session file (a participant kit's download) becomes evidence, through the same store the
    preview server's POST uses. The study, the method, the task ids and the consent are checked there."""
    rs = _rs()
    if a.consent != "yes":
        raise ResearchError("consent: %s — a session is stored only with --consent yes (the participant agreed in the session; "
                            "the file's own consent.session is checked as well). Nothing was imported." % a.consent)
    for flag, val in (("--role", a.role), ("--segment", a.segment), ("--date", a.date), ("--drop-columns", a.drop_columns)):
        if val:
            raise ResearchError("%s does not apply to --kind session: the session file holds the date and the participant "
                                "tracker (`participant`) holds the role and segment" % flag, EXIT_USAGE)
    obj = rs.parse_session_bytes(raw)
    if a.participant and obj.get("participant") != a.participant:
        raise ResearchError("--participant %s, but the file is for participant %s" % (a.participant, obj.get("participant")))
    res = rs.store_session(a.registry, a.id, raw, keep_pii=a.keep_pii, source="import")
    digest = sha256_bytes(raw)
    if res["pilot"]:
        lines = ["stored pilot session %s as %s — a pilot is never evidence and is left out of every number" % (res["sessionId"], res["file"])]
    else:
        lines = ["stored session %s as %s in %s (sha256 %s…)" % (res["sessionId"], res["evidence"], res["file"], digest[:12])]
    lines += ["warn  %s" % w for w in res["warnings"]]
    return ({"imported": res["evidence"], "kind": "session", "sessionId": res["sessionId"], "pilot": res["pilot"],
             "file": res["file"], "sha256": digest, "warnings": res["warnings"]}, lines, EXIT_OK)


def _import_recording(a, src):
    """--kind recording --session <id>: the screen recording of a stored session. Refused unless that session's
    consent.recording is true."""
    rs = _rs()
    if a.consent != "yes":
        raise ResearchError("consent: %s — a recording is linked to a session only with --consent yes (and the session's own "
                            "consent.recording must be true). Nothing was imported." % a.consent)
    for flag, val in (("--role", a.role), ("--segment", a.segment), ("--date", a.date), ("--drop-columns", a.drop_columns),
                      ("--participant", a.participant)):
        if val:
            raise ResearchError("%s does not apply to a recording linked to a session: it takes the session's" % flag, EXIT_USAGE)
    res = rs.store_media(a.registry, a.id, a.session, src, move=False)
    where = "pilot recording of %s" % a.session if res["evidence"] is None else "%s" % res["evidence"]
    lines = ["stored the recording of session %s as %s in %s (%d bytes, sha256 %s…)" % (a.session, where, res["file"], res["bytes"], res["sha256"][:12])]
    return ({"imported": res["evidence"], "kind": "recording", "session": a.session, "file": res["file"], "sha256": res["sha256"],
             "bytes": res["bytes"], "warnings": []}, lines, EXIT_OK)


def cmd_import(a):
    if a.consent == "no":
        raise ResearchError("consent: no — a participant who did not consent is not stored. Nothing was imported.")
    src = a.file
    if not os.path.lexists(src):
        raise ResearchError("file not found: %s" % src, EXIT_USAGE)
    if os.path.islink(src):
        raise ResearchError("%s is a symlink — refusing to follow it; pass the real file" % src)
    if a.session and a.kind != "recording":
        raise ResearchError("--session links a recording to its session: use it with --kind recording", EXIT_USAGE)
    if a.kind == "recording" and a.session:
        return _import_recording(a, src)         # a video can be a gigabyte: never read it into memory here
    try:
        raw = read_nofollow(src)
    except OSError as e:
        raise ResearchError("cannot read %s: %s" % (src, e.strerror or e), EXIT_USAGE)
    if a.kind == "session":
        return _import_session(a, raw)
    name = safe_name(src)
    text = decode_text(raw, name)
    drop = [squash(c) for c in (a.drop_columns or "").split(",") if squash(c)]
    with locked(a.registry, "research.py import") as reg:
        st = find_study(reg, a.id)
        if scope_of(st) == "instrument":
            raise ResearchError("%s has scope `instrument`: the study ends at the approved questions and no results are expected, "
                                "so nothing is imported. If results will come back after all, change it first: "
                                "`research.py scope %s --scope collect`." % (a.id, a.id))
        if st.get("status") == "draft":
            raise ResearchError("%s is still a draft — approve it (G-STUDY) before any evidence is stored" % a.id)
        declared = role_ids(reg)
        if a.role and declared and a.role not in declared:
            raise ResearchError("role %s is not declared in meta.roles" % a.role)
        warnings, info, stored = [], {}, raw
        dropped_names, responses = [], None
        if a.kind == "responses":
            if os.path.splitext(name)[1] not in (".csv", ".tsv", ".txt") or text is None:
                raise ResearchError("--kind responses needs a UTF-8 CSV (re-export it as CSV, UTF-8)")
            _d, header, data = parse_csv(text)
            hkeys = [key(h) for h in header]
            for d in drop:
                if key(d) not in hkeys:
                    raise ResearchError("--drop-columns names %r, which is not a column of the file (columns: %s)"
                                        % (d, ", ".join(header)))
            drop_idx = {i for i, h in enumerate(hkeys) if h in {key(d) for d in drop}}
            pii = [h for i, h in enumerate(header) if i not in drop_idx and looks_pii(h)]
            if pii and not a.keep_pii:
                raise ResearchError("these columns look like personal data: %s. Name them in --drop-columns to remove "
                                    "them before the file is stored, or pass --keep-pii to keep them on purpose."
                                    % ", ".join(repr(h) for h in pii), data={"pii": pii})
            kept_cols = [i for i in range(len(header)) if i not in drop_idx]
            cols = [c for c in map_columns(st, [header[i] for i in kept_cols])]
            matched = [{"column": c["header"], "question": c["question"], "by": c["by"]} for c in cols if c["question"]]
            ignored = [{"column": c["header"], "why": c["why"]} for c in cols if not c["question"]]
            if not matched:
                raise ResearchError("no column matches a question of %s (by id or by text). Columns: %s"
                                    % (a.id, ", ".join(header)), data={"columns": header})
            mcols = [kept_cols[c["col"]] for c in cols if c["question"]]
            responses = sum(1 for r in data if any(squash(_cell(r, i)) for i in mcols))
            info = {"matched": matched, "ignored": ignored}
            if drop_idx:
                out = io.StringIO()
                w = csv.writer(out, lineterminator="\n")
                w.writerow([header[i] for i in kept_cols])
                for r in data:
                    w.writerow([_cell(r, i) for i in kept_cols])
                text = out.getvalue()
                stored = text.encode("utf-8")
                dropped_names = [header[i] for i in sorted(drop_idx)]
        elif drop:
            raise ResearchError("--drop-columns applies to --kind responses only")
        digest = sha256_bytes(stored)
        for e in as_list(st.get("evidence")):
            if isinstance(e, dict) and e.get("sha256") == digest:
                raise ResearchError("the same file is already stored as %s%s" %
                                    (e.get("id"), " (dropped — a withdrawn participant's file is not re-imported)" if e.get("dropped") else ""))
        if text is not None:
            warnings += _pii(text)
        else:
            info.setdefault("opaque", True)
        base = base_of(a.registry)
        num = next_evidence_number(st)
        eid = "e%d" % num
        stored_name = "%s-%s" % (eid, name)
        rel = "%s/%s" % (evidence_dir_rel(a.id), stored_name)
        ensure_dir(base, study_rel(a.id))
        ensure_dir(base, evidence_dir_rel(a.id))
        write_exclusive(under(base, rel), stored)
        stamp = now_iso()
        row = {"id": eid, "file": rel, "kind": a.kind, "sha256": digest, "importedAt": stamp,
               "date": a.date or stamp[:10], "participant": a.participant, "role": a.role, "segment": a.segment,
               "consent": a.consent, "responses": responses, "droppedColumns": dropped_names, "dropped": None}
        st.setdefault("evidence", []).append(row)
        prev = st.get("status")
        st["status"] = "fielding"
        try:
            pbslice._write(a.registry, reg)
        except BaseException:
            with contextlib.suppress(OSError):
                os.chmod(under(base, rel), 0o644)
                os.unlink(under(base, rel))
            raise
    if prev in ("analysed", "applied"):
        warnings.append("study was %s; it is fielding again — re-run tally/synthesize/verify" % prev)
    lines = ["stored %s as %s (sha256 %s…)" % (name, rel, digest[:12])]
    if info.get("matched") is not None:
        lines.append("matched: " + ", ".join("%s<-%r" % (m["question"], m["column"]) for m in info["matched"]))
        lines.append("ignored: " + (", ".join(repr(i["column"]) for i in info["ignored"]) or "none"))
    if dropped_names:
        lines.append("dropped columns before storing: " + ", ".join(dropped_names))
    lines += ["warn  %s" % w for w in warnings]
    return ({"imported": eid, "file": rel, "sha256": digest, "responses": responses, "droppedColumns": dropped_names,
             "warnings": warnings, **info}, lines, EXIT_OK)


def cmd_drop(a):
    if not squash(a.reason):
        raise ResearchError("--reason is required")
    with locked(a.registry, "research.py drop-evidence") as reg:
        st = find_study(reg, a.id)
        row = next((e for e in as_list(st.get("evidence")) if isinstance(e, dict) and e.get("id") == a.eid), None)
        if row is None:
            raise ResearchError("%s has no evidence %r" % (a.id, a.eid), EXIT_USAGE)
        if row.get("dropped"):
            raise ResearchError("%s is already dropped" % a.eid)
        base = base_of(a.registry)
        path = os.path.join(base, *sstr(row.get("file")).split("/"))
        if evidence_file(base, a.id, row)[0] == "unsafe":
            raise ResearchError("%s points outside the evidence folder — not deleting it" % row.get("file"))
        with contextlib.suppress(FileNotFoundError):
            os.chmod(path, 0o644)
            os.unlink(path)
        row["dropped"] = {"at": now_iso(), "reason": squash(a.reason)}
        # a session's screen recording is the same person's: a withdrawal takes it too
        also = []
        if row.get("kind") == "session":
            sess = as_dict(row.get("session")).get("id")
            for other in as_list(st.get("evidence")):
                if (isinstance(other, dict) and other.get("kind") == "recording" and sess and other.get("session") == sess
                        and not other.get("dropped")):
                    opath = os.path.join(base, *sstr(other.get("file")).split("/"))
                    if evidence_file(base, a.id, other)[0] == "unsafe":
                        raise ResearchError("%s points outside the evidence folder — not deleting it" % other.get("file"))
                    with contextlib.suppress(FileNotFoundError):
                        os.chmod(opath, 0o644)
                        os.unlink(opath)
                    other["dropped"] = {"at": now_iso(), "reason": "with %s: %s" % (a.eid, squash(a.reason))}
                    also.append(other["id"])
        pbslice._write(a.registry, reg)
    lines = ["dropped %s — the file is deleted, the row and its hash stay; re-run `tally` and `verify`" % a.eid]
    if also:
        lines.append("dropped %s too: the recording of the same session" % ", ".join(also))
    return ({"dropped": a.eid, "alsoDropped": also}, lines, EXIT_OK)


def _qtable(tally):
    lines = []
    for qid, q in tally["byQuestion"].items():
        body = ", ".join("%s=%s" % kv for kv in q["counts"].items()) if q["counts"] else ""
        sc = as_dict(q.get("score"))
        lines.append("  %s (%s) n=%d%s%s%s" % (qid, q["type"], q["n"], "  " + body if body else "",
                                              "  mean=%s" % round(q["mean"], 2) if q["mean"] is not None else "",
                                              "  %s=%s%s" % (sc.get("metric"), sc.get("value"),
                                                             " (%s%% at 5-7)" % round(sc["pct"], 1) if sc.get("pct") is not None else "")
                                              if sc else ""))
    return lines


def cmd_tally(a):
    reg_path = a.registry
    base = base_of(reg_path)
    if a.by:
        reg = load_registry(reg_path)
        st = find_study(reg, a.id)
        _need_survey(st)
        tally, warns, kept, mapped = compute_tally(st, base)
        q = next((q for _s, q in all_questions(st) if q.get("id") == a.by), None)
        if q is None or a.by not in mapped:
            raise ResearchError("--by %s: no such question in the imported responses" % a.by)
        if q.get("type") not in ("single", "multi", "scale"):
            raise ResearchError("--by needs a single, multi or scale question")
        groups = {}
        for r in kept:
            cell = r.get(a.by, "")
            if not squash(cell):
                continue
            vals = split_multi(cell, q) if q["type"] == "multi" else \
                [_opt_map(q).get(key(cell), OTHER)] if q["type"] == "single" else [squash(cell)]
            for v in set(vals):
                groups.setdefault(v, []).append(r)
        out = {v: {"n": len(rs), "byQuestion": tally_questions(st, rs, mapped)} for v, rs in groups.items()}
        lines = []
        for v, g in out.items():
            lines.append("%s = %s  (n=%d)" % (a.by, v, g["n"]))
            lines += _qtable(g)
        return {"by": a.by, "groups": out, "warnings": warns}, lines, EXIT_OK
    with locked(reg_path, "research.py tally") as reg:
        st = find_study(reg, a.id)
        _need_survey(st)
        tally, warns, _k, _m = compute_tally(st, base)
        st["tally"] = tally
        pbslice._write(reg_path, reg)
    lines = ["n=%d  excluded=%d %s" % (tally["n"], tally["excluded"], tally["excludedWhy"] or "")] + _qtable(tally)
    lines += ["warn  %s" % w for w in warns]
    return {"tally": tally, "warnings": warns}, lines, EXIT_OK


def _need_survey(st):
    if st.get("method") != "survey":
        raise ResearchError("tally is for surveys; %s is %s%s" % (
            st.get("id"), "an interview" if st.get("method") == "interview" else "a %s study" % st.get("method"),
            " — a session study is scored with `analyze`" if st.get("method") in SESSION_METHODS else ""))


def cmd_verify(a):
    reg = load_registry(a.registry)
    errs, warns = verify_study(reg, copy_study(find_study(reg, a.id)), base_of(a.registry))
    return ({"ok": not errs, "errors": errs, "warnings": warns},
            _report(errs, warns, "verify %s" % a.id), EXIT_FAIL if errs else EXIT_OK)


OBS_KEYS = ("id", "evidence", "participant", "task", "event", "t", "quote", "note", "tags")
THEME_KEYS = ("id", "title", "tags", "insight")
ISSUE_KEYS = ("id", "title", "task", "screen", "severity", "observations", "recommendation", "targets")
# what the tool computes from the sessions: a typed value here is refused, never merely overwritten
ISSUE_COMPUTED = ("participants", "frequency", "priority", "count", "rate", "share", "n")
REPORT_KEYS = ("summary", "recommendations", "nextSteps", "limitations")
REC_KEYS = ("text", "issues", "route")


def synthesis_shape_problems(data, method):
    """Problems with the shape of the observations / themes / issues / report in a synthesize file (exit 2)."""
    out = []
    for name, keys in (("observations", OBS_KEYS), ("themes", THEME_KEYS), ("issues", ISSUE_KEYS)):
        if name not in data:
            continue
        items = data[name]
        if not (isinstance(items, list) and all(isinstance(x, dict) for x in items)):
            out.append("%s must be a list of objects" % name)
            continue
        if name == "issues" and method not in SESSION_METHODS:
            out.append("issues belong to the session methods (usability, tree-test, card-sort, first-click): their frequency "
                       "and priority are computed from the sessions")
        for i, x in enumerate(items):
            w = "%s[%d]" % (name, i)
            computed = [k for k in ISSUE_COMPUTED if k in x] if name == "issues" else []
            for k in computed:
                out.append("%s: `%s` is computed by the tool (analyze) — remove it" % (w, k))
            bad = sorted(set(x) - set(keys) - set(computed))
            if bad:
                out.append("%s: unexpected key(s) %s (known: %s)" % (w, ", ".join(bad), ", ".join(keys)))
    if "report" in data:
        out += report_shape_problems(data["report"])
    return out


def report_shape_problems(rep):
    if not isinstance(rep, dict):
        return ["report must be an object {summary, recommendations, nextSteps, limitations}"]
    out = []
    bad = sorted(set(rep) - set(REPORT_KEYS))
    if bad:
        out.append("report: unexpected key(s) %s (known: %s)" % (", ".join(bad), ", ".join(REPORT_KEYS)))
    if "summary" in rep and not isinstance(rep["summary"], str):
        out.append("report.summary must be a string")
    for k in ("nextSteps", "limitations"):
        if k in rep and not (isinstance(rep[k], list) and all(isinstance(x, str) for x in rep[k])):
            out.append("report.%s must be a list of strings" % k)
    if "recommendations" in rep:
        recs = rep["recommendations"]
        if not (isinstance(recs, list) and all(isinstance(r, dict) for r in recs)):
            out.append("report.recommendations must be a list of {text, issues?, route?}")
        else:
            for i, r in enumerate(recs):
                w = "report.recommendations[%d]" % i
                if sorted(set(r) - set(REC_KEYS)):
                    out.append("%s: unexpected key(s) %s (known: %s)" % (w, ", ".join(sorted(set(r) - set(REC_KEYS))), ", ".join(REC_KEYS)))
                if not squash(r.get("text") if isinstance(r.get("text"), str) else ""):
                    out.append("%s needs a `text`" % w)
                if "issues" in r and not (isinstance(r["issues"], list) and all(isinstance(x, str) for x in r["issues"])):
                    out.append("%s.issues must be a list of issue ids" % w)
                if "route" in r and r["route"] not in ROUTES:
                    out.append("%s.route must be one of %s" % (w, "|".join(ROUTES)))
    return out


def _usage_problems(msg, problems, code):
    raise ResearchError(msg, EXIT_USAGE, data={"problems": problems,
                                               "errors": [{"code": code, "where": "synthesize", "msg": p} for p in problems]})


def cmd_synthesize(a):
    data = _read_json_arg(a.file)
    allowed = {"verdicts", "findings", "refill", "observations", "themes", "issues", "report"}
    extra = sorted(set(data) - allowed)
    if extra:
        raise ResearchError("synthesize takes {verdicts, findings, refill, observations, themes, issues, report}; unexpected: %s"
                            % ", ".join(extra), EXIT_USAGE)
    verdicts = data.get("verdicts", {})
    if not isinstance(verdicts, dict) or not all(isinstance(v, dict) for v in verdicts.values()):
        raise ResearchError("verdicts must be {h1: {verdict, why}}", EXIT_USAGE)
    if "findings" in data and not (isinstance(data["findings"], list) and all(isinstance(f, dict) for f in data["findings"])):
        raise ResearchError("findings must be a list of objects", EXIT_USAGE)
    refill = data.get("refill")
    if refill is not None:
        if not isinstance(refill, dict) or set(refill) - set(REFILL_KEYS) or \
                not all(isinstance(v, str) for v in refill.values()):
            raise ResearchError("refill takes only %s, each a string" % ", ".join(REFILL_KEYS), EXIT_USAGE)
    base = base_of(a.registry)
    with locked(a.registry, "research.py synthesize") as reg:
        st = find_study(reg, a.id)
        if st.get("status") not in ("fielding", "analysed", "applied"):
            raise ResearchError("%s is %s — there is no evidence to synthesise yet" % (a.id, st.get("status")))
        problems = synthesis_shape_problems(data, st.get("method"))
        if problems:
            _usage_problems("the synthesis was not accepted: %d problem(s)" % len(problems), problems, "S-SHAPE")
        hmap = {h.get("id"): h for h in as_list(st.get("hypotheses")) if isinstance(h, dict)}
        unknown = [h for h in verdicts if h not in hmap]
        if unknown:
            raise ResearchError("verdicts name unknown hypotheses: %s" % ", ".join(unknown))
        if st.get("method") == "survey":
            tally, _w, _k, _m = compute_tally(st, base)      # raises when there is nothing to tally
            st["tally"] = tally
        for hid, v in verdicts.items():
            hmap[hid]["verdict"] = v.get("verdict")
            hmap[hid]["why"] = sstr(v.get("why"))
        if "findings" in data:
            st["findings"] = data["findings"]
        for name in ("observations", "themes", "issues"):
            if name in data:
                st[name] = data[name]
        if refill is not None:
            merged = dict(as_dict(st.get("refill")))
            merged.update(refill)
            st["refill"] = merged
        if "report" in data:
            merged = dict(as_dict(st.get("report")))
            merged.update(data["report"])
            st["report"] = merged
        if st.get("method") in SESSION_METHODS:
            # a fresh analysis, computed AFTER the observations and issues landed: their frequency, priority and
            # affinity counts are the tool's, and every `analysis` citation in a finding is checked against it
            pairs = session_pairs(st, base)
            if not pairs:
                raise ResearchError("%s has no session evidence to analyse — import a session first" % a.id)
            st["analysis"] = _ra().analyze(st, pairs)
        errs, warns = verify_study(reg, copy_study(st), base)
        if not errs and st.get("status") == "fielding":
            st["status"] = "analysed"
        pbslice._write(a.registry, reg)
        status = st["status"]
    lines = _report(errs, warns, "verify %s" % a.id)
    lines.append("written; status %s%s" % (status, "" if not errs else " (not analysed: fix the errors and synthesize again)"))
    return ({"ok": not errs, "errors": errs, "warnings": warns, "status": status}, lines,
            EXIT_FAIL if errs else EXIT_OK)


def _unique_dir(path):
    p, n = path, 1
    while os.path.exists(p):
        n += 1
        p = "%s-%d" % (path, n)
    return p


def cmd_refill(a):
    if not a.approved:
        raise ResearchError("refill is gate G-INSIGHT: a human approves the text first. Re-run with --approved once they have.",
                            EXIT_USAGE)
    base = base_of(a.registry)
    with locked(a.registry, "research.py refill") as reg:
        st = find_study(reg, a.id)
        errs, warns = verify_study(reg, copy_study(st), base)
        if errs:
            raise ResearchError("refill refused: verify has %d error(s) — nothing was written" % len(errs),
                                data={"errors": errs, "warnings": warns})
        if st.get("status") not in ("analysed", "applied"):
            raise ResearchError("%s is %s — synthesize it cleanly before refilling" % (a.id, st.get("status")))
        refill = {k: v for k, v in as_dict(st.get("refill")).items() if k in REFILL_KEYS and squash(v)}
        if not refill:
            raise ResearchError("%s has no refill text — synthesize one first" % a.id)
        meta = reg.setdefault("meta", {})
        ui = meta.get("userInsights")
        plan, notes = {}, []
        prior = as_dict(as_dict(st.get("refilled")).get("fields"))
        ui_now = as_dict(ui)
        for k in REFILL_KEYS:
            if k not in refill:
                continue
            new = "%s [%s]" % (refill[k].strip(), a.id)
            cur = ui_now.get(k) if isinstance(ui_now.get(k), str) else ""
            old = prior.get(k)
            if new in cur:
                plan[k] = (cur, "unchanged")
            elif old and old in cur:
                plan[k] = (cur.replace(old, new, 1), "replaced")
            else:
                if old:
                    notes.append("%s: the text appended earlier was edited, so the new text was appended after it — "
                                 "review the two" % k)
                plan[k] = ((cur.rstrip("\n") + "\n\n" + new) if cur.strip() else new, "appended")
        changed = [k for k, (_t, how) in plan.items() if how != "unchanged"]
        if not changed and st.get("status") == "applied":
            rep = regenerate_report(base, st, reg, notes)
            return ({"refilled": a.id, "changed": [], "noop": True, "report": rep, "warnings": notes},
                    ["nothing to do: the insights already hold this text"] + (["report regenerated: " + ", ".join(rep)] if rep else [])
                    + ["warn  %s" % n for n in notes], EXIT_OK)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = _unique_dir(os.path.join(base, "memory", "backups", "research-%s-%s" % (a.id, stamp)))
        os.makedirs(backup)
        shutil.copyfile(a.registry, os.path.join(backup, os.path.basename(a.registry)))
        if not isinstance(ui, dict):
            ui = meta["userInsights"] = {}
        for k in REFILL_KEYS:
            ui.setdefault(k, None)
        for k, (text, _how) in plan.items():
            ui[k] = text
        fields = dict(prior)
        for k in plan:
            fields[k] = "%s [%s]" % (refill[k].strip(), a.id)
        st["refilled"] = {"at": now_iso(), "fields": fields}
        st["status"] = "applied"
        st.setdefault("gates", []).append({"gate": "G-INSIGHT", "at": now_iso(), "note": squash(a.note)})
        pbslice._write(a.registry, reg)
        rep = regenerate_report(base, st, reg, notes)    # the Draft banner goes: the report is only rewritten if one exists
    lines = ["G-INSIGHT: %s -> meta.userInsights" % a.id] + ["  %s: %s" % (k, plan[k][1]) for k in plan]
    lines += ["warn  %s" % n for n in notes]
    if rep:
        lines.append("report regenerated: " + ", ".join(rep))
    return ({"refilled": a.id, "changed": changed, "how": {k: v[1] for k, v in plan.items()},
             "backup": os.path.relpath(backup, base), "warnings": notes, "report": rep}, lines, EXIT_OK)


def _summary(st):
    v = {}
    for h in as_list(st.get("hypotheses")):
        k = as_dict(h).get("verdict") or "open"
        v[k] = v.get(k, 0) + 1
    ev = [e for e in as_list(st.get("evidence")) if isinstance(e, dict)]
    out = {"id": st.get("id"), "title": st.get("title"), "method": st.get("method"), "status": st.get("status"),
           "scope": scope_of(st), "audience": st.get("audience"), "evidence": len(ev), "dropped": sum(1 for e in ev if e.get("dropped")),
           "n": as_dict(st.get("tally")).get("n"), "verdicts": v}
    if st.get("method") in SESSION_METHODS:
        out["methodLabel"] = METHOD_LABELS.get(st.get("method"))
        out["sessions"] = sum(1 for e in ev if e.get("kind") == "session" and not e.get("dropped"))
        out["pilots"] = len(as_list(st.get("pilots")))
        out["issues"] = len(as_list(st.get("issues")))
        out["headline"] = analysis_headline(st)
    out["participants"] = len(as_list(st.get("participants")))
    return out


def analysis_headline(st):
    """One line from the stored analysis (nothing computed here), or None."""
    an = as_dict(st.get("analysis"))
    if not an:
        return None
    m = st.get("method")
    n = an.get("n")
    if m == "usability":
        s = as_dict(as_dict(an.get("usability")).get("overall")).get("success")
        sus = as_dict(an.get("usability")).get("sus")
        bits = ["n=%s" % n, "success %s" % _rate(s)]
        if sus:
            bits.append("SUS %s (%s)" % (_f(sus.get("mean"), 1), sus.get("grade")))
        return " · ".join(bits)
    if m == "tree-test":
        tasks = as_dict(as_dict(an.get("treeTest")).get("tasks"))
        return " · ".join(["n=%s" % n] + ["%s %s" % (t, _pct(as_dict(v.get("success")).get("rate"))) for t, v in tasks.items()])
    if m == "card-sort":
        cs = as_dict(an.get("cardSort"))
        return "n=%s · %s sort · %d cluster(s) at similarity %s" % (n, cs.get("kind"), len(as_list(cs.get("clusters"))), cs.get("threshold"))
    if m == "first-click":
        tasks = as_dict(as_dict(an.get("firstClick")).get("tasks"))
        return " · ".join(["n=%s" % n] + ["%s %s" % (t, _pct(as_dict(v.get("success")).get("rate"))) for t, v in tasks.items()])
    return None


def cmd_list(a):
    reg = load_registry(a.registry)
    rows = [_summary(s) for s in studies_of(reg)]
    lines = []
    for r in rows:
        line = "%-28s %-11s %-10s %-10s evidence=%d  %s" % (r["id"], r["method"], r["scope"], r["status"], r["evidence"],
                                                           ", ".join("%s %d" % kv for kv in sorted(r["verdicts"].items())))
        if "sessions" in r:
            line += "  [%s: %d session(s), %d pilot(s), %d issue(s)%s]" % (
                r["methodLabel"], r["sessions"], r["pilots"], r["issues"], " · " + r["headline"] if r.get("headline") else "")
        lines.append(line)
    return {"studies": rows}, lines or ["no studies yet — `gaps` shows what is unsure, `init` starts one"], EXIT_OK


def pipeline(st):
    """{status: [participant ids]} in tracker order."""
    out = {}
    for p in as_list(st.get("participants")):
        if isinstance(p, dict):
            out.setdefault(p.get("status") or "invited", []).append(p.get("id"))
    return out


def cmd_show(a):
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    s = _summary(st)
    label = METHOD_LABELS.get(st.get("method"), st.get("method"))
    lines = ["%s — %s" % (st["id"], st.get("title")), "  %s · %s · %s · %s" % (label, scope_of(st), st.get("status"), json.dumps(st.get("audience"), ensure_ascii=False)),
             "  question: %s" % st.get("question")]
    if squash(st.get("setup")):
        lines.append("  setup: %s" % squash(st["setup"]))
    plan = as_dict(st.get("plan"))
    for o in as_list(plan.get("objectives")):
        lines.append("  objective: %s" % squash(o))
    for h in as_list(st.get("hypotheses")):
        h = as_dict(h)
        lines.append("  %s [%s] %s" % (h.get("id"), h.get("verdict") or "open", h.get("statement")))
    for e in as_list(st.get("evidence")):
        e = as_dict(e)
        lines.append("  %s %s %s%s" % (e.get("id"), e.get("kind"), e.get("file"), " (dropped)" if e.get("dropped") else ""))
    people = [p for p in as_list(st.get("participants")) if isinstance(p, dict)]
    if people:
        lines.append("  participants: " + ", ".join("%s %s" % (k, ",".join(v)) for k, v in pipeline(st).items()))
    cl = checklist_of(st)
    if cl:
        lines.append("  logistics: %d of %d done" % (sum(1 for c in cl if c.get("done")), len(cl)))
    if "sessions" in s:
        lines.append("  sessions: %d · pilots: %d · observations: %d · themes: %d · issues: %d" % (
            s["sessions"], s["pilots"], len(as_list(st.get("observations"))), len(as_list(st.get("themes"))), s["issues"]))
        if s.get("headline"):
            lines.append("  analysis: %s" % s["headline"])
    return {"study": st, "summary": s}, lines, EXIT_OK


# ── the UX methods: catalog, participants, logistics, kit, link, analysis, report ──

def _f(x, d=2):
    """A stored number for a table: None is a dash, an int stays an int."""
    if x is None:
        return "-"
    if isinstance(x, bool):
        return str(x)
    return str(x) if isinstance(x, int) else "%.*f" % (d, x)


def _pct(x):
    return "-" if isinstance(x, bool) or not isinstance(x, (int, float)) else "%d%%" % int(math.floor(100.0 * x + 0.5))


def _rate(s):
    """'4/5 80% [38%-96%]' from an adjusted-Wald block."""
    s = as_dict(s)
    if not s or s.get("n") in (None, 0):
        return "-"
    return "%s/%s %s [%s-%s]" % (s.get("x"), s.get("n"), _pct(s.get("rate")), _pct(s.get("low")), _pct(s.get("high")))


def _need_session(st, verb):
    if st.get("method") not in SESSION_METHODS:
        raise ResearchError("%s is for the session methods (%s); %s is a %s study%s" % (
            verb, ", ".join(SESSION_METHODS), st.get("id"), st.get("method"),
            " — a survey is scored with `tally`" if st.get("method") == "survey" else
            " — an interview is read, then `synthesize`d" if st.get("method") == "interview" else ""))


def session_pairs(st, base):
    """[(evidence row, parsed session)] for every live session row, hash-checked. Raises on a changed or missing file."""
    rs = _rs()
    return [(e, rs.load_session(base, e)) for e in live_evidence(st) if e.get("kind") == "session"]


def analysis_lines(st, an):
    """The analysis as tables for the terminal. Every figure is read from the stored analysis."""
    L = ["%s  n=%s  inputs: %s" % (METHOD_LABELS.get(an.get("method"), an.get("method")), an.get("n"), ", ".join(as_list(an.get("inputs"))) or "none")]
    for eid, why in sorted(as_dict(an.get("excluded")).items()):
        L.append("  excluded %s: %s" % (eid, why))
    m = an.get("method")
    if m == "usability":
        u = as_dict(an.get("usability"))
        L.append("  %-6s %2s  %-24s %-5s %-24s %-6s %-5s %-5s %-6s %-8s %s" % (
            "task", "n", "success", "asst", "time s (geo mean)", "clicks", "dead", "rage", "errors", "lostness", "SEQ"))
        for tid, t in as_dict(u.get("tasks")).items():
            tm, ls, sq = as_dict(t.get("time")), as_dict(t.get("lostness")), as_dict(t.get("seq"))
            L.append("  %-6s %2s  %-24s %-5s %-24s %-6s %-5s %-5s %-6s %-8s %s" % (
                tid, t.get("n"), _rate(t.get("success")), t.get("assisted"),
                "%s [%s-%s] n=%s" % (_f(tm.get("geoMean"), 1), _f(tm.get("low"), 1), _f(tm.get("high"), 1), tm.get("n")) if tm.get("n") else "-",
                _f(as_dict(t.get("clicks")).get("mean"), 1), _f(as_dict(t.get("deadClicks")).get("total")), _f(t.get("rageClicks")),
                _f(as_dict(t.get("errors")).get("total")), _f(ls.get("mean")) if ls else "-", _f(sq.get("mean"), 1) if sq else "-"))
        ov = as_dict(as_dict(u.get("overall")).get("success"))
        if ov:
            L.append("  overall success %s" % _rate(ov))
        sus = u.get("sus")
        if isinstance(sus, dict):
            L.append("  SUS  n=%s  mean %s [%s-%s]  grade %s" % (sus.get("n"), _f(sus.get("mean"), 1), _f(sus.get("low"), 1),
                                                                _f(sus.get("high"), 1), sus.get("grade")))
    elif m == "tree-test":
        L.append("  %-6s %3s  %-24s %-24s %-24s %s" % ("task", "n", "success", "direct", "first click", "top destinations"))
        for tid, t in as_dict(as_dict(an.get("treeTest")).get("tasks")).items():
            L.append("  %-6s %3s  %-24s %-24s %-24s %s" % (
                tid, t.get("n"), _rate(t.get("success")), _rate(t.get("direct")), _rate(t.get("firstClick")),
                ", ".join("%s×%s" % (d.get("node"), d.get("count")) for d in as_list(t.get("destinations"))[:3]) or "-"))
    elif m == "card-sort":
        cs = as_dict(an.get("cardSort"))
        L.append("  %s sort, %d cards, clusters cut at similarity %s" % (cs.get("kind"), len(as_list(cs.get("cards"))), cs.get("threshold")))
        for i, c in enumerate(as_list(cs.get("clusters")), 1):
            L.append("  cluster %d: %s" % (i, ", ".join(c)))
        for k, c in as_dict(cs.get("categories")).items():
            L.append("  category %-20s used by %s of %s" % (c.get("label") or k, c.get("count"), cs.get("n")))
    elif m == "first-click":
        L.append("  %-6s %3s  %-24s %s" % ("task", "n", "success", "time s (median)"))
        for tid, t in as_dict(as_dict(an.get("firstClick")).get("tasks")).items():
            L.append("  %-6s %3s  %-24s %s" % (tid, t.get("n"), _rate(t.get("success")), _f(as_dict(t.get("time")).get("median"), 1)))
    iss = as_dict(an.get("issues"))
    if iss:
        L.append("  issues: " + "; ".join("%s %s of %s (frequency %s, priority %s)" % (
            k, v.get("participants"), an.get("n"), _f(v.get("frequency")), _f(v.get("priority"))) for k, v in iss.items()))
    tags = as_dict(as_dict(an.get("affinity")).get("tags"))
    if tags:
        L.append("  tags: " + ", ".join("%s (%d obs, %d people)" % (k, v.get("observations"), v.get("participants")) for k, v in tags.items()))
    return L


def cmd_analyze(a):
    base = base_of(a.registry)
    with locked(a.registry, "research.py analyze") as reg:
        st = find_study(reg, a.id)
        _need_session(st, "analyze")
        pairs = session_pairs(st, base)
        if not pairs:
            raise ResearchError("%s has no session evidence to analyse — import a session first "
                                "(`import %s <file> --kind session --consent yes`)" % (a.id, a.id))
        analysis = _ra().analyze(st, pairs)
        st["analysis"] = analysis
        pbslice._write(a.registry, reg)
    warns = _dup_warning(dup_participants(pairs))
    lines = analysis_lines(st, analysis) + ["warn  %s %s: %s" % (w["code"], w["where"], w["msg"]) for w in warns]
    lines.append("stored in study.analysis (inputsHash %s…); `verify` recomputes it" % analysis["inputsHash"][:12])
    return {"analysis": analysis, "warnings": warns}, lines, EXIT_OK


def cmd_affinity(a):
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    aff = _ra().affinity(st)
    tags = aff["tags"]
    n_obs = len(as_list(st.get("observations")))
    lines = ["%s: %d observation(s), %d tag(s)" % (a.id, n_obs, len(tags))]
    lines += ["  %-24s %2d obs · %d participant(s) · tasks: %s" % (k, v["observations"], v["participants"], ", ".join(v["tasks"]) or "-")
              for k, v in tags.items()]
    if not tags:
        lines.append("  no tagged observations yet — `synthesize` takes {observations: [{id, evidence, event|t|quote, note, tags}]}")
    return aff, lines, EXIT_OK


def cmd_methods(a):
    cat = _rm().METHOD_CATALOG
    lines = ["%-19s %-12s %-5s %-24s %s" % ("method", "kind", "data", "minutes", "in pb")]
    for c in cat:
        lines.append("%-19s %-12s %-5s %-24s %s" % (c["method"], c["kind"], c["data"], c["minutes"],
                                                     "runs here" if c.get("runner") else "listed only (field it elsewhere, import the notes)"))
        lines.append("    answers: %s" % c["answers"])
        lines.append("    sample:  %s" % c["n"])
        lines.append("    not for: %s" % c["notFor"])
    return {"methods": cat}, lines, EXIT_OK


def cmd_participant(a):
    pid = a.pid
    if not PARTICIPANT_ID.match(pid):
        raise ResearchError("%r is not a participant code: a pseudonym like P01 (P and two or three digits). Names are never stored." % pid,
                            EXIT_USAGE)
    for flag, val in (("--note", a.note), ("--segment", a.segment), ("--role", a.role)):
        if val:
            refuse_pii(val, flag)
    if a.status is not None and a.status not in PARTICIPANT_STATUSES:
        raise ResearchError("--status %r is not one of %s" % (a.status, ", ".join(PARTICIPANT_STATUSES)), EXIT_USAGE)
    if a.incentive is not None and a.incentive not in INCENTIVES:
        raise ResearchError("--incentive %r is not one of %s" % (a.incentive, ", ".join(INCENTIVES)), EXIT_USAGE)
    if a.at is not None and not ISO_AT.match(a.at):
        raise ResearchError("--at %r is not a date or a date and time (2026-03-02 or 2026-03-02T14:30)" % a.at, EXIT_USAGE)
    with locked(a.registry, "research.py participant") as reg:
        st = find_study(reg, a.id)
        people = st.get("participants")
        if not isinstance(people, list):
            people = st["participants"] = []
        cur = next((p for p in people if isinstance(p, dict) and p.get("id") == pid), None)
        if a.remove:
            if cur is None:
                raise ResearchError("%s has no participant %s" % (a.id, pid), EXIT_USAGE)
            held = [e["id"] for e in live_evidence(st) if e.get("participant") == pid]
            if held:
                raise ResearchError("%s still has evidence (%s) — a participant who withdrew is set to `withdrawn` and their evidence "
                                    "dropped with `drop-evidence`; the tracker row stays as the record" % (pid, ", ".join(held)))
            people.remove(cur)
            pbslice._write(a.registry, reg)
            return {"removed": pid}, ["removed %s from %s" % (pid, a.id)], EXIT_OK
        declared = role_ids(reg)
        if a.role and declared and a.role not in declared:
            raise ResearchError("role %s is not declared in meta.roles (%s)" % (a.role, ", ".join(declared)))
        created = cur is None
        if created:
            cur = {"id": pid, "segment": "", "role": "", "status": "invited", "incentive": "none", "pilot": False, "note": ""}
            people.append(cur)
        if a.status is not None:
            cur["status"] = a.status
        if a.segment is not None:
            cur["segment"] = squash(a.segment)
        if a.role is not None:
            cur["role"] = squash(a.role)
        if a.at is not None:
            cur["scheduledAt"] = a.at
        if a.incentive is not None:
            cur["incentive"] = a.incentive
        if a.pilot is not None:
            cur["pilot"] = a.pilot
        if a.note is not None:
            cur["note"] = squash(a.note)
        held = [e["id"] for e in live_evidence(st) if e.get("participant") == pid]
        pbslice._write(a.registry, reg)
    lines = ["%s participant %s in %s: %s%s" % ("added" if created else "updated", pid, a.id, cur["status"],
                                              " · pilot" if cur.get("pilot") else "")]
    if cur["status"] in ("withdrawn", "excluded") and held:
        lines.append("warn  %s still has evidence (%s) — `drop-evidence %s <eid> --reason …` removes it; "
                     "no further session of theirs is stored" % (pid, ", ".join(held), a.id))
    return {"participant": cur, "created": created, "evidence": held}, lines, EXIT_OK


def cmd_logistics(a):
    changing = bool(a.done or a.undo or a.add)
    if changing:
        with locked(a.registry, "research.py logistics") as reg:
            st = find_study(reg, a.id)
            if not checklist_of(st):
                sync_checklist(st)
            for iid in a.done or []:
                if not tick(st, iid, True):
                    raise ResearchError("%s has no checklist item %r (see `logistics %s`)" % (a.id, iid, a.id), EXIT_USAGE)
            for iid in a.undo or []:
                if not tick(st, iid, False):
                    raise ResearchError("%s has no checklist item %r (see `logistics %s`)" % (a.id, iid, a.id), EXIT_USAGE)
            if a.add:
                refuse_pii(a.add, "--add")
                text = squash(a.add)
                if not text:
                    raise ResearchError("--add needs the text of the item", EXIT_USAGE)
                ids = {c.get("id") for c in checklist_of(st)}
                base_id, n = "x-" + (slug(text, 40) or "item"), 1
                new_id = base_id
                while new_id in ids:
                    n += 1
                    new_id = "%s-%d" % (base_id, n)
                st["logistics"]["checklist"].append({"id": new_id, "text": text, "done": False, "at": None})
            pbslice._write(a.registry, reg)
    else:
        reg = load_registry(a.registry)
        st = find_study(reg, a.id)
    cl = checklist_of(st)
    if not cl:
        cl = [dict(c) for c in _rm().default_checklist(st.get("method"), as_dict(st.get("instrument")).get("mode", "moderated"))]
    sched = as_dict(as_dict(st.get("plan")).get("schedule"))
    pipe = pipeline(st)
    lines = ["%s — logistics: %d of %d done" % (a.id, sum(1 for c in cl if c.get("done")), len(cl))]
    lines += ["  [%s] %-22s %s" % ("x" if c.get("done") else " ", c.get("id"), c.get("text")) for c in cl]
    lines.append("participants:")
    for status in PARTICIPANT_STATUSES:
        if status in pipe:
            lines.append("  %-10s %d  %s" % (status, len(pipe[status]), ", ".join(pipe[status])))
    if not pipe:
        lines.append("  none yet — `participant %s P01 --status invited`" % a.id)
    if sched:
        lines.append("schedule: %s to %s, %s minutes per session" % (sched.get("start", "-"), sched.get("end", "-"), sched.get("sessionMinutes", "-")))
    when = [(p.get("scheduledAt"), p.get("id")) for p in as_list(st.get("participants")) if isinstance(p, dict) and p.get("scheduledAt")]
    lines += ["  %s  %s" % (w, pid) for w, pid in sorted(when)]
    return {"checklist": cl, "pipeline": pipe, "schedule": sched,
            "done": sum(1 for c in cl if c.get("done")), "total": len(cl)}, lines, EXIT_OK


def cmd_pilots(a):
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    pilots = [p for p in as_list(st.get("pilots")) if isinstance(p, dict)]
    lines = ["%s: %d pilot session(s) — never evidence, left out of every number" % (a.id, len(pilots))]
    lines += ["  %s  %s  %s  %s%s" % (p.get("sessionId"), p.get("participant"), p.get("at"), p.get("file"),
                                      "  + %d recording(s)" % len(as_list(p.get("media"))) if as_list(p.get("media")) else "") for p in pilots]
    if pilots:
        lines.append("replay one at /research/%s/replay/pilot-<sessionId> on the preview server (`link`)" % a.id)
    return {"pilots": pilots}, lines, EXIT_OK


def _project_path(base, out):
    """An --out path, absolute, refused when it leaves the project folder (a symlink in it included)."""
    root = os.path.realpath(base)
    path = os.path.abspath(out if os.path.isabs(out) else os.path.join(os.getcwd(), out))
    real = os.path.realpath(os.path.dirname(path))
    if real != root and not real.startswith(root + os.sep):
        raise ResearchError("--out %s is outside the project (%s) — pick a path inside it" % (out, base), EXIT_USAGE)
    if os.path.islink(path):
        raise ResearchError("%s is a symlink — refusing to write through it" % out)
    return path


def cmd_kit(a):
    rs = _rs()
    base = base_of(a.registry)
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    if st.get("method") not in SESSION_METHODS:
        raise ResearchError("%s is a %s study; a participant kit is for %s" % (a.id, st.get("method"), ", ".join(SESSION_METHODS)))
    html = rs.build_page(a.registry, a.id, "kit", pilot=bool(a.pilot))
    if a.out:
        path = _project_path(base, a.out)
        rel = os.path.relpath(path, base)
    else:
        rel = "%s/kit/%s-kit.html" % (study_rel(a.id), a.id)
        ensure_dir(base, study_rel(a.id))
        ensure_dir(base, study_rel(a.id) + "/kit")
        path = under(base, rel)
        if os.path.islink(path):
            raise ResearchError("%s is a symlink — refusing to write through it" % rel)
    pbslice.atomic_write_text(path, html)
    size = os.path.getsize(path)
    rec = as_dict(as_dict(st.get("instrument")).get("recording"))
    ask = "screen and voice recording is asked for (the participant can say no)" if rec.get("screen") or rec.get("voice") else "no recording is asked for"
    lines = ["kit for %s%s: %s (%d KB)" % (a.id, " (pilot)" if a.pilot else "", rel, size // 1024),
             "SEND: this one file. It runs from the participant's own disk — open it in a current Chrome or Edge (screen recording needs one). "
             "It carries the prototype and the tasks only: no hypotheses, no answers; nothing is uploaded — the results come back as files.",
             "ASK: the participant types a code you give them (P01, P02…, never a name); %s." % ask,
             "BACK: at the end the page offers a download of the session file (<…>.pbsession.json)%s. They send it to you by any private channel." % (
                 ", and the recording (.webm) if they agreed" if rec.get("screen") or rec.get("voice") else ""),
             "IMPORT: `import %s <file>.pbsession.json --kind session --consent yes`%s" % (
                 a.id, ", then `import %s <file>.webm --kind recording --session <sessionId> --consent yes`" % a.id if rec.get("screen") or rec.get("voice") else ""),
             "A pilot run (--pilot) is stored as a pilot: it is never evidence and never counted."]
    return {"kit": rel, "path": path, "bytes": size, "pilot": bool(a.pilot)}, lines, EXIT_OK


def preview_base(a, start=True):
    """(base url, started) of this registry's /pb:preview server; starts one unless start=False. Reuses explore.py's finder."""
    ex = _explore()
    reg_path = os.path.abspath(a.registry)
    base_dir = os.path.dirname(reg_path)
    rec = ex.server_record(base_dir)
    if rec and ex._ours(rec["url"].rstrip("/"), reg_path):
        return rec["url"].rstrip("/"), False
    if not start:
        return None, False
    try:
        rec = ex._start_server(reg_path, managed=True)
    except Exception as e:
        raise ResearchError("the preview server could not be started: %s" % e)
    return rec["url"].rstrip("/"), True


def cmd_link(a):
    rs = _rs()
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    if st.get("method") not in SESSION_METHODS:
        raise ResearchError("%s is a %s study; a session link is for %s" % (a.id, st.get("method"), ", ".join(SESSION_METHODS)))
    if not a.pilot:
        if st.get("status") == "draft":
            raise ResearchError("%s is still a draft — approve it (G-STUDY) first, or open a pilot session with --pilot" % a.id)
        if scope_of(st) == "instrument":
            raise ResearchError("%s has scope `instrument`: no sessions are expected (a pilot may still run: --pilot)" % a.id)
    if a.participant and not PARTICIPANT_ID.match(a.participant):
        raise ResearchError("--participant %r is not a pseudonym like P01" % a.participant, EXIT_USAGE)
    base, started = preview_base(a)
    q = []
    if a.participant:
        q.append("p=" + a.participant)
    if a.pilot:
        q.append("pilot=1")
    qs = ("?" + "&".join(q)) if q else ""
    url = "%s/research/%s/session%s" % (base, a.id, qs)
    obs_url = "%s/research/%s/observer%s" % (base, a.id, qs) if a.observer else None
    ex = _explore()
    problems = []
    for label, u in (("session page", url), ("observer page", obs_url)):
        if not u:
            continue
        code, _body = ex._get(u, timeout=60)
        if code != 200:
            problems.append("the %s did not answer 200 at %s (HTTP %s)%s" % (
                label, u, code, " — the preview server may predate the research routes: `serve.py --stop`, then run `link` again" if code in (404, None) else ""))
    if a.open and not problems:
        import webbrowser
        webbrowser.open(obs_url or url)
        if obs_url:
            webbrowser.open(url)
    lines = ["session: %s" % url] + (["observer: %s" % obs_url] if obs_url else [])
    lines += ["replay later: %s/research/%s/replay/<eid>" % (base, a.id)]
    lines += ["problem: " + p for p in problems]
    if started:
        lines.append("(started the preview server for this project)")
    return ({"url": url, "observer": obs_url, "started": started, "problems": problems, "ok": not problems},
            lines, EXIT_FAIL if problems else EXIT_OK)


def regenerate_report(base, st, reg, notes=None):
    """Rewrite report.md / report.html when a report already exists for this study; the files written ([] when none).
    A refusal to write (a symlink in the way) is a note, not a failure: the gate it follows has already been recorded."""
    rel = "%s/report/report.md" % study_rel(st["id"])
    if not os.path.isfile(os.path.join(base, *rel.split("/"))):
        return []
    try:
        return write_report(base, st, reg)
    except (ResearchError, OSError) as e:
        if notes is None:
            raise
        notes.append("the report was not regenerated: %s" % e)
        return []


def write_report(base, st, reg):
    rr = _rr()
    sid = st["id"]
    ensure_dir(base, study_rel(sid))
    ensure_dir(base, study_rel(sid) + "/report")
    written = []
    for name, text in (("report.md", rr.report_md(st, reg)), ("report.html", rr.report_html(st, reg))):
        rel = "%s/report/%s" % (study_rel(sid), name)
        path = under(base, rel)
        if os.path.islink(path):
            raise ResearchError("%s is a symlink — refusing to write through it" % rel)
        pbslice.atomic_write_text(path, text)
        written.append(rel)
    return written


def cmd_report(a):
    base = base_of(a.registry)
    reg = load_registry(a.registry)
    st = find_study(reg, a.id)
    errs, warns = verify_study(reg, copy_study(st), base)
    if errs:
        raise ResearchError("report refused: verify has %d error(s) — a report states only what verifies" % len(errs),
                            data={"errors": errs, "warnings": warns})
    if st.get("status") not in ("analysed", "applied"):
        raise ResearchError("%s is %s — synthesize it cleanly (status analysed) before a report" % (a.id, st.get("status")))
    with locked(a.registry, "research.py report") as reg2:           # re-read inside the lock: the report is of what is stored now
        st2 = find_study(reg2, a.id)
        written = write_report(base, st2, reg2)
    url = None
    note = ""
    try:
        pb, _s = preview_base(a, start=False)
    except Exception:                       # no preview to point at is not a reason to lose the report
        pb = None
    if pb:
        url = "%s/research/%s/report" % (pb, a.id)
        code, _b = _explore()._get(url, timeout=30)
        if code != 200:
            note = " (the running preview answered HTTP %s there — restart it to load the research routes)" % code
    lines = ["report for %s%s:" % (a.id, "" if st2.get("status") == "applied" else " — Draft until G-INSIGHT (`refill --approved`)")]
    lines += ["  " + w for w in written]
    if url:
        lines.append("  open: %s%s" % (url, note))
    lines += ["warn  %s %s: %s" % (w["code"], w["where"], w["msg"]) for w in warns]
    return {"report": written, "url": url, "status": st2.get("status"), "warnings": warns}, lines, EXIT_OK


# ── main ─────────────────────────────────────────────────────────────────────

def build_parser():
    ap = argparse.ArgumentParser(description="The executable half of /pb:research.")
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def sp(name, *args):
        p = sub.add_parser(name)
        for x in args:
            p.add_argument(x)
        return p
    p = sp("gaps")
    p.add_argument("--role")
    p = sub.add_parser("seed")
    p.add_argument("targets", nargs="+", metavar="kind:id")
    p = sp("init", "id")
    p.add_argument("--method", required=True, choices=METHODS)
    p.add_argument("--scope", required=True, choices=SCOPES)
    p.add_argument("--setup", default="")
    p.add_argument("--question", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--role", action="append")
    p.add_argument("--segment", default="")
    p.add_argument("--target", action="append")
    p.add_argument("--target-n", type=int)
    p.add_argument("--mode", choices=MODES, help="session methods: how it will be run (default moderated); sets the logistics checklist")
    p = sp("scope", "id")
    p.add_argument("--scope", choices=SCOPES)
    p.add_argument("--setup")
    p = sp("plan", "id")
    p.add_argument("--file", required=True)
    p = sp("brief", "id")
    p.add_argument("--file", required=True, help="the research plan: {background, objectives, researchQuestions, decision, methodRationale, "
                                                 "participants, recruitment, schedule, team, materials, risks, timeline, budget}")
    sp("check", "id")
    sp("review-plan", "id")
    p = sp("review", "id")
    p.add_argument("--file", required=True)
    p = sp("approve", "id")
    p.add_argument("--note", default="")
    p.add_argument("--skip-review")
    p.add_argument("--accept-review")
    sp("export", "id")
    p = sp("import", "id", "file")
    p.add_argument("--kind", required=True, choices=EVIDENCE_KINDS)
    p.add_argument("--consent", required=True, choices=("yes", "unknown", "no"))
    p.add_argument("--participant")
    p.add_argument("--role")
    p.add_argument("--segment")
    p.add_argument("--date")
    p.add_argument("--drop-columns", default="")
    p.add_argument("--keep-pii", action="store_true")
    p.add_argument("--session", help="with --kind recording: the sessionId (s-…) of the stored session this recording belongs to")
    p = sp("drop-evidence", "id", "eid")
    p.add_argument("--reason", required=True)
    p = sp("tally", "id")
    p.add_argument("--by")
    p = sp("analyze", "id")
    sp("affinity", "id")
    p = sp("synthesize", "id")
    p.add_argument("--file", required=True)
    sp("verify", "id")
    p = sp("refill", "id")
    p.add_argument("--approved", action="store_true")
    p.add_argument("--note", default="")
    sp("report", "id")
    sp("methods")
    p = sp("participant", "id", "pid")
    p.add_argument("--status", help="|".join(PARTICIPANT_STATUSES))
    p.add_argument("--segment")
    p.add_argument("--role")
    p.add_argument("--at", help="when it is scheduled: 2026-03-02 or 2026-03-02T14:30")
    p.add_argument("--incentive", help="|".join(INCENTIVES))
    p.add_argument("--pilot", dest="pilot", action="store_true", default=None)
    p.add_argument("--no-pilot", dest="pilot", action="store_false", default=None)
    p.add_argument("--note")
    p.add_argument("--remove", action="store_true")
    p = sp("logistics", "id")
    p.add_argument("--done", action="append", metavar="ID")
    p.add_argument("--undo", action="append", metavar="ID")
    p.add_argument("--add", metavar="TEXT")
    sp("pilots", "id")
    p = sp("kit", "id")
    p.add_argument("--out", help="write the kit here (inside the project) instead of memory/research/<id>/kit/")
    p.add_argument("--pilot", action="store_true", help="a kit for a rehearsal: its session is stored as a pilot, never as evidence")
    p = sp("link", "id")
    p.add_argument("--observer", action="store_true", help="also print (and check) the facilitator's observer window")
    p.add_argument("--participant", help="prefill the participant code, e.g. P01")
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--open", action="store_true", help="open it in the browser")
    sp("list")
    sp("show", "id")
    return ap


COMMANDS = {"gaps": cmd_gaps, "seed": cmd_seed, "init": cmd_init, "scope": cmd_scope, "plan": cmd_plan, "brief": cmd_brief,
            "check": cmd_check, "review-plan": cmd_review_plan, "review": cmd_review, "approve": cmd_approve, "export": cmd_export, "import": cmd_import, "drop-evidence": cmd_drop,
            "tally": cmd_tally, "analyze": cmd_analyze, "affinity": cmd_affinity, "synthesize": cmd_synthesize, "verify": cmd_verify,
            "refill": cmd_refill, "report": cmd_report, "methods": cmd_methods, "participant": cmd_participant,
            "logistics": cmd_logistics, "pilots": cmd_pilots, "kit": cmd_kit, "link": cmd_link,
            "list": cmd_list, "show": cmd_show}


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        result, lines, code = COMMANDS[a.cmd](a)
    except ResearchError as e:
        if a.json:
            print(json.dumps(dict(e.data, ok=False, error=str(e)), indent=2, ensure_ascii=False))
        else:
            print("research: %s" % e, file=sys.stderr)
            for f in as_list(e.data.get("errors")):
                print("  ERROR %s %s: %s" % (f["code"], f["where"], f["msg"]), file=sys.stderr)
        return e.code
    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())
