#!/usr/bin/env python3
"""
research_session.py — the session half of /pb:research's UX methods (usability, tree-test, card-sort,
first-click). Stdlib only; Python 3.9+.

One file format (`pb-session` v1) is written by every in-browser runner. This module is everything the
tool does with it, apart from the statistics (research_analysis.py):

  validate_session   refuses a malformed, unconsented or personal-data-bearing session file
  summarize · task_metrics · tree_results · sort_result · click_results     read a session, no judgement
  participant_config the `window.PB_RS_SESSION` a runner page is given — NEVER the study's hypotheses,
                     thresholds, title, question, audience, targets or findings, and no right answer
  kit_registry       the registry stripped to what the Prototype tab draws, for an outside participant
  build_page         session | observer | replay | kit  ->  one HTML string (the prototype + the runner)
  load_session       an evidence row -> the parsed, hash-checked session
  store_session      the evidence store for a session file (or a pilot, which is never evidence)
  store_media        the evidence store for its screen recording

`research` (research.py) is imported lazily inside the functions that need it, never at module load:
research.py imports this module, so a top-level import here would be a cycle.

Nothing here serves a request. serve.py calls build_page / store_session / store_media after its own
loopback and same-origin checks; the paths in a request are validated here by anchored regular expression
before any is joined, and every path built from input is checked against a realpath root.
"""
import contextlib
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FORMAT, VERSION = "pb-session", 1
SESSION_METHODS = ("usability", "tree-test", "card-sort", "first-click")
PAGES = ("session", "observer", "replay", "kit")
MODES = ("moderated", "unmoderated")
# "answered" = a tree-test choice made without the answer key on the page; research_analysis scores it.
OUTCOMES = ("success", "fail", "abandoned", "timeout", "skipped", "answered")
OUTCOME_SOURCES = ("criteria", "self", "facilitator")
SINKS = ("server", "download")

EVENT_TYPES = ("session-start", "session-end", "consent", "task-start", "task-end", "criteria", "nav", "click",
               "rage", "input", "submit", "field-error", "toast", "step", "role", "reset", "scroll", "visibility",
               "answer", "note", "assist", "mark", "tt-open", "tt-choose", "cs-group", "cs-move", "fc-click",
               "media-start", "media-stop", "error")

SESSION_ID = re.compile(r"^s-[a-z0-9-]{4,40}\Z")
PARTICIPANT_ID = re.compile(r"^P[0-9]{2,3}\Z")
EVIDENCE_ID = re.compile(r"^e[0-9]{1,6}\Z")
PILOT_EID = re.compile(r"^pilot-(s-[a-z0-9-]{4,40})\Z")
_HEX64 = re.compile(r"^[0-9a-f]{64}\Z")
_ISO = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?Z\Z")

SESSION_MAX_BYTES = 16 * 1024 * 1024
MAX_EVENTS = 50000
MEDIA_MAX_BYTES = 1024 ** 3
JSON_MAX_DEPTH = 64
MAX_FINDINGS = 50                 # one broken file must not produce 50,000 lines of findings
LONG_TEXT = 5000                  # a string field longer than this is not something the runner wrote
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"  # the EBML header every WebM (and Matroska) file starts with
CHUNK = 1 << 20

# Where the page's JavaScript comes from, read at call time (a test points this at a folder of stubs).
DEFAULT_TEMPLATE_DIR = os.path.join(os.path.dirname(HERE), "template")
TEMPLATE_DIR = DEFAULT_TEMPLATE_DIR
JS_FILES = {"session": "research-session.js", "methods": "research-methods.js", "replay": "research-replay.js"}

# One character each: linear whatever the input (the same scan serve.py uses before it parses a body).
_JSON_SPECIAL = re.compile(r'[\[\]{}"\\]')
_SCRIPT_CLOSE = re.compile(r"</(?=script)", re.IGNORECASE)
_HEAD_OPEN = re.compile(r"<head(?:\s[^>]*)?>", re.IGNORECASE)

# Per event type: the fields a runner may write and their kind. A field that is present with the wrong kind
# is an error; a type with `required` fields must carry them. Unknown extra fields are tolerated (a newer
# runner), except where a rule below forbids them.
_EVENT_FIELDS = {
    "session-start": {}, "session-end": {}, "consent": {"recording": "bool"}, "task-start": {},
    "task-end": {"outcome": "outcome", "source": "strnull"}, "criteria": {"met": "bool"},
    "nav": {"from": "strnull", "to": "str", "back": "bool"},
    "click": {"x": "unit", "y": "unit", "target": "strnull", "cmp": "strnull", "interactive": "bool", "dead": "bool"},
    "rage": {"x": "unit", "y": "unit", "count": "int"},
    "input": {"field": "strnull", "len": "int"},
    "submit": {"ok": "bool", "errors": "int"},
    "field-error": {"field": "strnull", "msg": "strnull"}, "toast": {"msg": "strnull"},
    "step": {"machine": "str", "step": "str"}, "role": {"role": "strnull"}, "reset": {},
    "scroll": {"y": "unit"}, "visibility": {"hidden": "bool"},
    "answer": {"q": "str", "value": "answer"}, "note": {"text": "str", "by": "strnull"},
    "assist": {}, "mark": {"outcome": "outcome"},
    "tt-open": {"node": "str"}, "tt-choose": {"node": "str"},
    "cs-group": {"group": "str", "name": "strnull", "category": "strnull"},
    "cs-move": {"card": "str", "group": "strnull"},
    "fc-click": {"x": "unit", "y": "unit", "hit": "bool", "target": "strnull"},
    "media-start": {"kind": "strnull"}, "media-stop": {"kind": "strnull"}, "error": {"msg": "strnull"},
}
_EVENT_REQUIRED = {
    "task-end": ("outcome",), "nav": ("to",), "click": ("x", "y"), "rage": ("x", "y"), "input": ("field", "len"),
    "answer": ("q", "value"), "note": ("text",), "mark": ("outcome",), "tt-open": ("node",),
    "tt-choose": ("node",), "cs-group": ("group",), "cs-move": ("card",), "fc-click": ("x", "y", "hit"),
    "step": ("machine", "step"),
}
# An `input` event is the proof that a typed value is never kept: these keys must not appear on it.
_INPUT_FORBIDDEN = ("value", "text", "val", "content", "data", "typed")


def _R():
    """research.py, imported on first use (it imports this module, so never at load time). When research.py is
    running as the CLI (`__main__`), that copy is used, so a ResearchError raised here is the one its main()
    catches rather than a twin from a second import."""
    m = sys.modules.get("research")
    if m is not None:
        return m
    main = sys.modules.get("__main__")
    if main is not None and os.path.basename(getattr(main, "__file__", "") or "") == "research.py" and hasattr(main, "ResearchError"):
        return main
    import research
    return research


def _render():
    import render
    return render


def _err(msg, code=1, data=None):
    return _R().ResearchError(msg, code, data)


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and x not in (float("inf"), float("-inf"))


def _dict(x):
    return x if isinstance(x, dict) else {}


def _list(x):
    return x if isinstance(x, list) else []


def _str(x):
    return x if isinstance(x, str) else ""


# ── parsing ──────────────────────────────────────────────────────────────────

def _too_deep(text, limit=JSON_MAX_DEPTH):
    """True when JSON text nests past `limit`, counted before parsing (3.11's parser raises RecursionError on
    deep input, 3.14's parses it — the answer must not depend on the version)."""
    depth, in_str, escaped = 0, False, -1
    for m in _JSON_SPECIAL.finditer(text):
        i, ch = m.start(), m.group()
        if i == escaped:
            continue
        if in_str:
            if ch == "\\":
                escaped = i + 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def _bad_constant(name):
    raise ValueError("%s is not valid JSON" % name)


def parse_session_bytes(raw):
    """The session object in `raw`, or a ResearchError: size, UTF-8, nesting depth (before json.loads) and
    NaN/Infinity are all refused."""
    if not isinstance(raw, (bytes, bytearray)):
        raise _err("a session file arrives as bytes")
    if len(raw) == 0:
        raise _err("the session file is empty")
    if len(raw) > SESSION_MAX_BYTES:
        raise _err("the session file is %d bytes; the limit is %d" % (len(raw), SESSION_MAX_BYTES))
    try:
        text = bytes(raw).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise _err("the session file is not UTF-8")
    if _too_deep(text):
        raise _err("the session file is nested too deeply")
    try:
        obj = json.loads(text, parse_constant=_bad_constant)
    except RecursionError:
        raise _err("the session file is nested too deeply")
    except ValueError as e:
        raise _err("the session file is not valid JSON: %s" % e)
    if not isinstance(obj, dict):
        raise _err("a session file holds one JSON object")
    return obj


def _parse_iso(s):
    m = _ISO.match(s) if isinstance(s, str) else None
    if not m:
        return None
    y, mo, d, h, mi, se = (int(m.group(i)) for i in range(1, 7))
    us = int((m.group(7) or "0")[:6].ljust(6, "0"))
    try:
        return datetime.datetime(y, mo, d, h, mi, se, us, tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def _events(obj):
    return [e for e in _list(_dict(obj).get("events")) if isinstance(e, dict)]


# ── what a study declares ────────────────────────────────────────────────────

def _study_questions(study):
    """Every question of the study's instrument, templates expanded: [(section, question)]."""
    R = _R()
    try:
        inst = R.expand_templates(_dict(_dict(study).get("instrument")))
    except Exception:
        inst = _dict(_dict(study).get("instrument"))
    out = []
    for sec in _list(inst.get("sections")):
        if isinstance(sec, dict):
            for q in _list(sec.get("questions")):
                if isinstance(q, dict):
                    out.append((sec, q))
    return out


def _study_task_ids(study):
    return {q.get("id") for _s, q in _study_questions(study)
            if isinstance(q.get("id"), str) and any(isinstance(q.get(k), dict) for k in ("task", "tree", "click"))}


def _study_question_ids(study):
    return {q.get("id") for _s, q in _study_questions(study) if isinstance(q.get("id"), str)}


# ── validate_session ─────────────────────────────────────────────────────────

def _check_kind(v, kind):
    if kind == "bool":
        return isinstance(v, bool)
    if kind == "int":
        return _is_int(v) and v >= 0
    if kind == "unit":
        return _is_num(v) and 0 <= v <= 1
    if kind == "str":
        return isinstance(v, str)
    if kind == "strnull":
        return v is None or isinstance(v, str)
    if kind == "outcome":
        return v in OUTCOMES
    if kind == "answer":
        return (_is_num(v) or isinstance(v, str) or (isinstance(v, list) and all(isinstance(i, str) for i in v)))
    return True


def validate_session(obj, study=None, keep_pii=False):
    """(errors, warnings): lists of "CODE: message". Errors block storing the file; warnings are stored with it.

    With a `study`, the file is also held to it: same study id and method, task ids that exist in the
    instrument, answers to questions that exist, tree nodes and cards that exist. `keep_pii=True` turns a
    personal-data finding in free text from an error into a warning (a secret is always an error)."""
    errors, warnings = [], []
    over = {"e": 0, "w": 0}

    def E(code, msg):
        if len(errors) < MAX_FINDINGS:
            errors.append("%s: %s" % (code, msg))
        else:
            over["e"] += 1

    def W(code, msg):
        if len(warnings) < MAX_FINDINGS:
            warnings.append("%s: %s" % (code, msg))
        else:
            over["w"] += 1

    if not isinstance(obj, dict):
        return ["S-JSON: a session file holds one JSON object"], []

    if obj.get("format") != FORMAT:
        E("S-FORMAT", "format must be %r (got %r)" % (FORMAT, obj.get("format")))
    if obj.get("version") != VERSION or isinstance(obj.get("version"), bool):
        E("S-FORMAT", "version must be %d (got %r)" % (VERSION, obj.get("version")))

    method = obj.get("method")
    if method not in SESSION_METHODS:
        E("S-METHOD", "method must be one of %s (got %r)" % (", ".join(SESSION_METHODS), method))
    st = study if isinstance(study, dict) else None
    if st is not None:
        if obj.get("study") != st.get("id"):
            E("S-STUDY", "the file is for study %r, not %r" % (obj.get("study"), st.get("id")))
        if method in SESSION_METHODS and st.get("method") != method:
            E("S-METHOD", "the file is a %s session; study %s is %s" % (method, st.get("id"), st.get("method")))
    elif not isinstance(obj.get("study"), str) or not obj.get("study"):
        E("S-STUDY", "study must name the study")

    sid = obj.get("sessionId")
    if not isinstance(sid, str) or not SESSION_ID.match(sid):
        E("S-ID", "sessionId %r does not match %s" % (sid, SESSION_ID.pattern))
    part = obj.get("participant")
    if not isinstance(part, str) or not PARTICIPANT_ID.match(part):
        E("S-PARTICIPANT", "participant %r is not a pseudonym like P01 (%s)" % (part, PARTICIPANT_ID.pattern))
    if obj.get("mode") not in MODES:
        E("S-MODE", "mode must be moderated or unmoderated (got %r)" % (obj.get("mode"),))
    if not isinstance(obj.get("pilot"), bool):
        E("S-PILOT", "pilot must be true or false")

    # time
    t0, t1 = _parse_iso(obj.get("startedAt")), _parse_iso(obj.get("endedAt"))
    if t0 is None:
        E("S-TIME", "startedAt must be an ISO-8601 UTC time (YYYY-MM-DDTHH:MM:SSZ)")
    if t1 is None:
        E("S-TIME", "endedAt must be an ISO-8601 UTC time (YYYY-MM-DDTHH:MM:SSZ)")
    if t0 is not None and t1 is not None and t1 < t0:
        E("S-TIME", "endedAt is before startedAt")
    dur = obj.get("durationMs")
    if not _is_int(dur) or dur < 0:
        E("S-TIME", "durationMs must be a whole number of milliseconds, 0 or more")
        dur = None
    elif dur > 12 * 3600 * 1000:
        W("W-DURATION", "durationMs is over 12 hours — a session left open?")

    # consent
    consent = obj.get("consent")
    if not isinstance(consent, dict):
        E("S-CONSENT", "consent is missing — a participant who did not consent is not stored")
        consent = {}
    else:
        if consent.get("session") is not True:
            E("S-CONSENT", "consent.session is not true — a participant who did not consent is not stored")
        if not isinstance(consent.get("recording"), bool):
            E("S-CONSENT", "consent.recording must be true or false")
        if _parse_iso(consent.get("at")) is None:
            W("W-CONSENT-AT", "consent.at is not an ISO-8601 UTC time")
        h = consent.get("textSha256")
        if not isinstance(h, str) or not _HEX64.match(h):
            W("W-CONSENT-TEXT", "consent.textSha256 is missing or not a sha256 — which consent text was shown is unknown")
        elif st is not None:
            shown = _str(_dict(st.get("instrument")).get("consent"))
            if shown and h != hashlib.sha256(shown.encode("utf-8")).hexdigest():
                W("W-CONSENT-TEXT", "consent.textSha256 differs from the study's consent text — it may have been shown reworded")

    env = obj.get("env")
    if not isinstance(env, dict):
        W("W-ENV", "env is missing (viewport, device, sink)")

    # what the study declares
    known_tasks = None
    if st is not None:
        known_tasks = _study_task_ids(st)
    else:
        ct = _list(_dict(obj.get("config")).get("tasks"))
        if ct:
            known_tasks = {t.get("id") for t in ct if isinstance(t, dict)}
    known_q = _study_question_ids(st) if st is not None else None

    config = obj.get("config")
    if not isinstance(config, dict):
        E("S-CONFIG", "config must be an object (the tasks as shown)")
        config = {}
    for i, t in enumerate(_list(config.get("tasks"))):
        if not isinstance(t, dict) or not isinstance(t.get("id"), str):
            E("S-CONFIG", "config.tasks[%d] needs an id" % i)
        elif known_tasks is not None and st is not None and t["id"] not in known_tasks:
            E("S-TASK-ID", "config.tasks[%d] is task %r, which the study does not have" % (i, t["id"]))

    # tasks
    R = _R()
    tasks = obj.get("tasks")
    seen_tasks = set()
    if not isinstance(tasks, list):
        E("S-TASKS", "tasks must be a list")
        tasks = []
    for i, t in enumerate(tasks):
        where = "tasks[%d]" % i
        if not isinstance(t, dict):
            E("S-TASKS", "%s must be an object" % where)
            continue
        tid = t.get("id")
        if not isinstance(tid, str) or not R.ITEM_ID.match(tid):
            E("S-TASKS", "%s.id %r is not a task id" % (where, tid))
            continue
        if tid in seen_tasks:
            E("S-TASK-DUP", "task %r appears twice" % tid)
        seen_tasks.add(tid)
        if known_tasks is not None and tid not in known_tasks:
            E("S-TASK-ID", "%s is task %r, which %s does not have" % (where, tid, "the study" if st is not None else "the file's config"))
        if t.get("outcome") not in OUTCOMES:
            E("S-TASKS", "%s (%s) outcome %r is not one of %s" % (where, tid, t.get("outcome"), ", ".join(OUTCOMES)))
        src = t.get("outcomeSource")
        if src is not None and src not in OUTCOME_SOURCES:
            E("S-TASKS", "%s (%s) outcomeSource %r is not one of %s" % (where, tid, src, ", ".join(OUTCOME_SOURCES)))
        a, b = t.get("startT"), t.get("endT")
        if not (_is_int(a) and a >= 0 and _is_int(b) and b >= 0):
            E("S-TASKS", "%s (%s) startT and endT must be whole milliseconds, 0 or more" % (where, tid))
        elif b < a:
            E("S-TASKS", "%s (%s) ends before it starts" % (where, tid))
        c = t.get("criteriaT")
        if c is not None and not (_is_int(c) and c >= 0):
            E("S-TASKS", "%s (%s) criteriaT must be a whole number of milliseconds or null" % (where, tid))
        if t.get("selfReport") not in (None, "done", "gave-up"):
            E("S-TASKS", "%s (%s) selfReport must be done, gave-up or null" % (where, tid))
        if not isinstance(t.get("answers", {}), dict):
            E("S-TASKS", "%s (%s) answers must be an object" % (where, tid))

    # answers
    answers = obj.get("answers", {})
    if not isinstance(answers, dict):
        E("S-ANSWERS", "answers must be an object")
        answers = {}
    if known_q is not None:
        for qid in answers:
            if qid not in known_q:
                W("W-ANSWER-ID", "answers.%s is not a question of the study" % qid)

    # events
    events = obj.get("events")
    if not isinstance(events, list):
        E("S-EVENTS", "events must be a list")
        events = []
    if len(events) > MAX_EVENTS:
        E("S-EVENTS", "%d events; the limit is %d" % (len(events), MAX_EVENTS))
        events = events[:MAX_EVENTS]
    prev_t, unknown_seen, last_t = -1, set(), 0
    types_seen = set()
    for i, ev in enumerate(events):
        where = "events[%d]" % i
        if not isinstance(ev, dict):
            E("S-EVENT", "%s must be an object" % where)
            continue
        typ = ev.get("type")
        if typ not in EVENT_TYPES:
            E("S-EVENT-TYPE", "%s has unknown type %r" % (where, typ))
            continue
        types_seen.add(typ)
        t = ev.get("t")
        if not _is_int(t) or t < 0:
            E("S-EVENT-T", "%s (%s) t must be a whole number of milliseconds, 0 or more" % (where, typ))
        else:
            if t < prev_t:
                E("S-EVENT-ORDER", "%s (%s) t=%d is before the previous event's t=%d — events must not go back in time"
                  % (where, typ, t, prev_t))
            prev_t = max(prev_t, t)
            last_t = max(last_t, t)
        et = ev.get("task")
        if et is not None:
            if not isinstance(et, str):
                E("S-EVENT", "%s task must be a task id or null" % where)
            elif known_tasks is not None and et not in known_tasks and et not in unknown_seen:
                unknown_seen.add(et)
                E("S-TASK-ID", "%s (%s) names task %r, which %s does not have" % (where, typ, et, "the study" if st is not None else "the file's config"))
        es = ev.get("screen")
        if es is not None and not isinstance(es, str):
            E("S-EVENT", "%s screen must be a screen id or null" % where)
        if typ == "input":
            bad = [k for k in _INPUT_FORBIDDEN if k in ev]
            if bad:
                E("S-INPUT-VALUE", "%s: an input event carries %s — only the field and the length of what was typed are kept, never the value"
                  % (where, ", ".join(repr(k) for k in bad)))
        for k in _EVENT_REQUIRED.get(typ, ()):
            if k not in ev:
                E("S-EVENT-FIELD", "%s (%s) is missing %r" % (where, typ, k))
        for k, kind in _EVENT_FIELDS[typ].items():
            if k in ev and not _check_kind(ev[k], kind):
                E("S-EVENT-FIELD", "%s (%s).%s has the wrong kind of value (%s expected)" % (where, typ, k, kind))
        for k, v in ev.items():
            if isinstance(v, str) and len(v) > LONG_TEXT:
                E("S-EVENT-FIELD", "%s (%s).%s is %d characters long" % (where, typ, k, len(v)))
    if dur is not None and events and last_t > dur + 2000:
        W("W-DURATION", "the last event is at %d ms, after durationMs %d" % (last_t, dur))
    if events and "session-end" not in types_seen:
        W("W-NO-END", "no session-end event — the session may have been cut short")

    # result
    result = obj.get("result", {})
    if not isinstance(result, dict):
        E("S-RESULT", "result must be an object")
        result = {}
    stray = [k for k in result if k != method]
    if stray:
        E("S-RESULT", "result holds %s; only the key for method %r belongs there" % (", ".join(repr(k) for k in stray), method))
    if method in ("tree-test", "card-sort", "first-click") and method in result:
        _check_result(method, result[method], st, E, W)
    elif method in ("tree-test", "card-sort", "first-click") and not result:
        W("W-RESULT", "no %s result in the file" % method)

    # media
    media = obj.get("media", [])
    if not isinstance(media, list):
        E("S-MEDIA", "media must be a list")
        media = []
    for i, m in enumerate(media):
        if not isinstance(m, dict) or m.get("kind") != "screen" or not _str(m.get("mime")).startswith("video/webm"):
            E("S-MEDIA", "media[%d] must be {kind: screen, mime: video/webm, …}" % i)
        elif not (_is_int(m.get("startT", 0)) and _is_int(m.get("durationMs", 0))):
            E("S-MEDIA", "media[%d] startT and durationMs must be whole milliseconds" % i)
    if media and consent.get("recording") is not True:
        E("S-CONSENT", "the file lists a recording but consent.recording is not true")

    # personal data in what a person typed (never in what the prototype itself says)
    for where, text in _free_text(obj):
        found = []

        def add(sev, code, w, msg, _f=found):
            _f.append((sev, code, msg))
        _R().security_scan.scan_text(add, text, where)
        for sev, code, msg in found:
            if sev == _R().security_scan.ERROR:
                E("S-SECRET", "%s: %s" % (where, msg))
            elif keep_pii:
                W("S-PII", "%s: %s (kept on purpose)" % (where, msg))
            else:
                E("S-PII", "%s: %s — personal data is not stored; re-export without it, or pass keep_pii" % (where, msg))

    if over["e"]:
        errors.append("S-MORE: %d further errors not listed" % over["e"])
    if over["w"]:
        warnings.append("S-MORE: %d further warnings not listed" % over["w"])
    return errors, warnings


def _free_text(obj):
    """[(where, text)] of every string a person typed or said: notes, answers, group names."""
    out = []
    for i, ev in enumerate(_events(obj)):
        typ = ev.get("type")
        if typ == "note" and isinstance(ev.get("text"), str):
            out.append(("events[%d].text" % i, ev["text"]))
        elif typ == "answer":
            v = ev.get("value")
            for s in ([v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []):
                out.append(("events[%d].value" % i, s))
        elif typ == "cs-group" and isinstance(ev.get("name"), str):
            out.append(("events[%d].name" % i, ev["name"]))
    for k, v in _dict(obj.get("answers")).items():
        for s in ([v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []):
            out.append(("answers.%s" % str(k)[:40], s))
    for t in _list(obj.get("tasks")):
        if isinstance(t, dict):
            for k, v in _dict(t.get("answers")).items():
                if isinstance(v, str):
                    out.append(("tasks.%s.answers.%s" % (str(t.get("id"))[:40], str(k)[:40]), v))
    for g in _list(_dict(_dict(obj.get("result")).get("card-sort")).get("groups")):
        if isinstance(g, dict) and isinstance(g.get("name"), str):
            out.append(("result.card-sort.groups.name", g["name"]))
    return out


def _check_result(method, res, st, E, W):
    inst = _dict(_dict(st).get("instrument")) if st is not None else {}
    if method == "tree-test":
        if not isinstance(res, dict):
            return E("S-RESULT", "result.tree-test must map task ids to {chosen, path}")
        nodes = {n.get("id") for n in _list(inst.get("tree")) if isinstance(n, dict)} if st is not None else None
        for tid, r in res.items():
            if not isinstance(r, dict) or not (r.get("chosen") is None or isinstance(r.get("chosen"), str)) \
                    or not isinstance(r.get("path", []), list) or not all(isinstance(p, str) for p in r.get("path", [])):
                E("S-RESULT", "result.tree-test.%s must be {chosen: node id|null, path: [node ids]}" % str(tid)[:40])
            elif nodes is not None and nodes and any(n not in nodes for n in [r.get("chosen")] + r.get("path", []) if n is not None):
                E("S-RESULT", "result.tree-test.%s names a node the tree does not have" % str(tid)[:40])
    elif method == "card-sort":
        if not isinstance(res, dict) or not isinstance(res.get("groups"), list) or not isinstance(res.get("unsorted", []), list):
            return E("S-RESULT", "result.card-sort must be {groups: [{name, category, cards}], unsorted: [card ids]}")
        cards = {c.get("id") for c in _list(inst.get("cards")) if isinstance(c, dict)} if st is not None else None
        seen = {}
        for gi, g in enumerate(res["groups"]):
            if not isinstance(g, dict) or not isinstance(g.get("name", ""), str) or not isinstance(g.get("cards"), list) \
                    or not all(isinstance(c, str) for c in g["cards"]):
                E("S-RESULT", "result.card-sort.groups[%d] must be {name, category, cards: [card ids]}" % gi)
                continue
            for c in g["cards"]:
                if c in seen:
                    E("S-RESULT", "card %r is in two groups" % c)
                seen[c] = gi
        for c in res.get("unsorted", []):
            if not isinstance(c, str):
                E("S-RESULT", "result.card-sort.unsorted holds card ids")
            elif c in seen:
                E("S-RESULT", "card %r is both grouped and unsorted" % c)
        if cards:
            for c in list(seen) + [c for c in res.get("unsorted", []) if isinstance(c, str)]:
                if c not in cards:
                    E("S-RESULT", "card %r is not a card of the study" % c)
    else:
        if not isinstance(res, dict):
            return E("S-RESULT", "result.first-click must map task ids to {x, y, hit, …}")
        for tid, r in res.items():
            if not isinstance(r, dict) or not (_is_num(r.get("x")) and 0 <= r["x"] <= 1 and _is_num(r.get("y")) and 0 <= r["y"] <= 1) \
                    or not isinstance(r.get("hit"), bool):
                E("S-RESULT", "result.first-click.%s must be {x: 0..1, y: 0..1, hit: bool, …}" % str(tid)[:40])


# ── reading a session ────────────────────────────────────────────────────────

def _outcomes(obj):
    out = {}
    for t in _list(_dict(obj).get("tasks")):
        if isinstance(t, dict) and isinstance(t.get("outcome"), str):
            out[t["outcome"]] = out.get(t["outcome"], 0) + 1
    return out


def summarize(obj):
    """{id, method, mode, pilot, participant, durationMs, tasks, outcomes, recording, events}."""
    o = _dict(obj)
    return {"id": o.get("sessionId"), "method": o.get("method"), "mode": o.get("mode"), "pilot": o.get("pilot") is True,
            "participant": o.get("participant"), "durationMs": o.get("durationMs"),
            "tasks": len([t for t in _list(o.get("tasks")) if isinstance(t, dict)]),
            "outcomes": _outcomes(o), "recording": _dict(o.get("consent")).get("recording") is True,
            "events": len(_events(o))}


def task_metrics(obj):
    """Usability: {task id: {outcome, source, assisted, ms, criteriaMs, screens, clicks, dead, rage, errors, answers}}.

    `ms` is endT - startT; `criteriaMs` is criteriaT - startT (both are session times). `screens` is the visit
    sequence: the screen at task-start, then each nav target, consecutive repeats collapsed. `clicks` counts click
    events (a rage event is not a click), `dead` the clicks marked dead, `rage` the rage events, `errors` the
    field-error events — all of the events carrying that task id."""
    by_task = {}
    for ev in _events(obj):
        tid = ev.get("task")
        if isinstance(tid, str):
            by_task.setdefault(tid, []).append(ev)
    out = {}
    for t in _list(_dict(obj).get("tasks")):
        if not isinstance(t, dict) or not isinstance(t.get("id"), str):
            continue
        tid = t["id"]
        evs = by_task.get(tid, [])
        a, b, c = t.get("startT"), t.get("endT"), t.get("criteriaT")
        screens = []
        start = next((e for e in evs if e.get("type") == "task-start"), None)
        if start is not None and isinstance(start.get("screen"), str):
            screens.append(start["screen"])
        for e in evs:
            if e.get("type") == "nav" and isinstance(e.get("to"), str) and (not screens or screens[-1] != e["to"]):
                screens.append(e["to"])
        out[tid] = {
            "outcome": t.get("outcome"), "source": t.get("outcomeSource"), "assisted": t.get("assisted") is True,
            "ms": b - a if _is_int(a) and _is_int(b) else None,
            "criteriaMs": c - a if _is_int(a) and _is_int(c) else None,
            "screens": screens,
            "clicks": sum(1 for e in evs if e.get("type") == "click"),
            "dead": sum(1 for e in evs if e.get("type") == "click" and e.get("dead") is True),
            "rage": sum(1 for e in evs if e.get("type") == "rage"),
            "errors": sum(1 for e in evs if e.get("type") == "field-error"),
            "answers": dict(_dict(t.get("answers"))),
        }
    return out


def _task_times(obj):
    return {t["id"]: t for t in _list(_dict(obj).get("tasks")) if isinstance(t, dict) and isinstance(t.get("id"), str)}


def tree_results(obj):
    """Tree test: {task id: {chosen, path, firstNode, ms, backtracked}}.

    `firstNode` is the first node the participant opened or chose in that task. `backtracked` is true when
    they opened a node that is not a child of the one they opened before it (they went back up and tried
    another branch); without the tree in the file's config it is true when they opened a node that is not on
    the final path."""
    res = _dict(_dict(obj).get("result")).get("tree-test")
    res = res if isinstance(res, dict) else {}
    parent = {}
    for n in _list(_dict(_dict(obj).get("config")).get("tree")):
        if isinstance(n, dict) and isinstance(n.get("id"), str):
            parent[n["id"]] = n.get("parent")
    have_tree = bool(parent)
    times = _task_times(obj)
    by_task = {}
    for ev in _events(obj):
        if ev.get("type") in ("tt-open", "tt-choose") and isinstance(ev.get("task"), str):
            by_task.setdefault(ev["task"], []).append(ev)
    out = {}
    for tid in list(res) + [t for t in by_task if t not in res]:
        r = _dict(res.get(tid))
        evs = by_task.get(tid, [])
        opened = [e["node"] for e in evs if e.get("type") == "tt-open" and isinstance(e.get("node"), str)]
        chosen_evs = [e["node"] for e in evs if e.get("type") == "tt-choose" and isinstance(e.get("node"), str)]
        chosen = r["chosen"] if "chosen" in r else (chosen_evs[-1] if chosen_evs else None)
        path = [p for p in _list(r.get("path")) if isinstance(p, str)]
        first = next((e["node"] for e in evs if isinstance(e.get("node"), str)), None)
        back = False
        if have_tree:
            prev = None
            for n in opened:
                if prev is not None and parent.get(n) != prev:
                    back = True
                prev = n
        else:
            back = any(n not in path for n in opened)
        tt = times.get(tid)
        ms = tt["endT"] - tt["startT"] if tt and _is_int(tt.get("startT")) and _is_int(tt.get("endT")) else None
        out[tid] = {"chosen": chosen, "path": path, "firstNode": first, "ms": ms, "backtracked": back}
    return out


def sort_result(obj):
    """Card sort: {groups: [{name, category, cards}], unsorted: [card ids]} as the participant left it."""
    res = _dict(_dict(obj).get("result")).get("card-sort")
    res = res if isinstance(res, dict) else {}
    groups = []
    for g in _list(res.get("groups")):
        if isinstance(g, dict):
            groups.append({"name": _str(g.get("name")), "category": g.get("category") if isinstance(g.get("category"), str) else None,
                           "cards": [c for c in _list(g.get("cards")) if isinstance(c, str)]})
    return {"groups": groups, "unsorted": [c for c in _list(res.get("unsorted")) if isinstance(c, str)]}


def click_results(obj):
    """First click: {task id: {x, y, hit, ms, target}}. `ms` is the recorded time to click, else the task's duration."""
    res = _dict(_dict(obj).get("result")).get("first-click")
    res = res if isinstance(res, dict) else {}
    times = _task_times(obj)
    out = {}
    for tid, r in res.items():
        if not isinstance(r, dict):
            continue
        ms = r.get("ms") if _is_int(r.get("ms")) else None
        tt = times.get(tid)
        if ms is None and tt and _is_int(tt.get("startT")) and _is_int(tt.get("endT")):
            ms = tt["endT"] - tt["startT"]
        out[tid] = {"x": r.get("x"), "y": r.get("y"), "hit": r.get("hit") is True, "ms": ms, "target": r.get("target")}
    return out


# ── what a runner page is given ──────────────────────────────────────────────

def _js_json(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _participant_question(q):
    """A question as a participant may see it: no hypothesis ids, no probes, no screener qualifiers, no success
    description, no optimal path, no right answer."""
    out = {k: v for k, v in q.items() if k not in ("tests", "probes", "qualifies", "task", "tree", "click")}
    if isinstance(q.get("task"), dict):
        out["task"] = {k: v for k, v in q["task"].items() if k not in ("success", "optimalPath")}
    if isinstance(q.get("tree"), dict):
        out["tree"] = {k: v for k, v in q["tree"].items() if k not in ("correct",)}
    if isinstance(q.get("click"), dict):
        out["click"] = dict(q["click"])
    return out


def participant_config(reg, study, *, sink, participant=None, pilot=False, mode=None, post=None):
    """The `window.PB_RS_SESSION` dict (§8.1) for `study`. Built from an allow-list: the study's title, question,
    audience, targets, hypotheses (statements, thresholds, ids), findings and every right answer are absent.
    Screener sections are not run in a session and are left out. `page` is "session"; build_page sets the others."""
    R = _R()
    st = _dict(study)
    if not isinstance(st.get("id"), str) or not R.STUDY_ID.match(st["id"]):
        raise _err("the study has no valid id")
    method = st.get("method")
    if method not in SESSION_METHODS:
        raise _err("%s is a %s study; only %s run in a session" % (st["id"], method, ", ".join(SESSION_METHODS)))
    if sink not in SINKS:
        raise _err("sink must be server or download (got %r)" % (sink,))
    if participant is not None and not (isinstance(participant, str) and PARTICIPANT_ID.match(participant)):
        raise _err("participant %r is not a pseudonym like P01" % (participant,))
    inst = R.expand_templates(_dict(st.get("instrument")))
    if mode is None:
        mode = "unmoderated" if (sink == "download" or inst.get("mode") == "unmoderated") else "moderated"
    if mode not in MODES:
        raise _err("mode must be moderated or unmoderated (got %r)" % (mode,))
    if sink == "download":
        post = None
    elif post is None:
        post = {"session": "/__pb_research/%s/session" % st["id"], "media": "/__pb_research/%s/media" % st["id"]}
    else:
        post = {k: v for k, v in _dict(post).items() if k in ("session", "media") and isinstance(v, str)}
    sections = []
    for sec in _list(inst.get("sections")):
        if not isinstance(sec, dict) or sec.get("purpose") == "screener":
            continue
        sections.append({"title": _str(sec.get("title")), "purpose": sec.get("purpose"),
                         "questions": [_participant_question(q) for q in _list(sec.get("questions")) if isinstance(q, dict)]})
    rec = _dict(inst.get("recording"))
    device = inst.get("device") if isinstance(inst.get("device"), str) and inst.get("device") else _str(_dict(_dict(reg).get("meta")).get("device")) or "laptop"
    cfg = {
        "page": "session", "study": st["id"], "method": method, "mode": mode, "sink": sink, "post": post,
        "participant": participant, "pilot": bool(pilot), "channel": "pb-rs-%s" % st["id"],
        "instrument": {
            "lang": _str(inst.get("lang")) or "en", "intro": _str(inst.get("intro")), "consent": _str(inst.get("consent")),
            "closing": _str(inst.get("closing")),
            "thinkAloud": bool(inst["thinkAloud"]) if "thinkAloud" in inst else method == "usability",
            "recording": {"screen": bool(rec.get("screen")), "voice": bool(rec.get("voice"))},
            "device": device, "sections": sections},
        "shell": _render().plugin_version(),
    }
    if method == "tree-test":
        cfg["tree"] = [{"id": n.get("id"), "label": _str(n.get("label")), "parent": n.get("parent")}
                       for n in _list(inst.get("tree")) if isinstance(n, dict)]
    if method == "card-sort":
        cfg["cards"] = [{"id": c.get("id"), "label": _str(c.get("label"))} for c in _list(inst.get("cards")) if isinstance(c, dict)]
        sort = _dict(inst.get("sort"))
        cfg["sort"] = {"kind": sort.get("kind") if sort.get("kind") in ("open", "closed", "hybrid") else "open",
                       "categories": [{"id": c.get("id"), "label": _str(c.get("label"))}
                                      for c in _list(sort.get("categories")) if isinstance(c, dict)]}
    return cfg


def _moderator_view(study):
    """What only the facilitator's observer window gets: each task's success description and every probe."""
    out = {"tasks": {}, "probes": {}}
    for _sec, q in _study_questions(study):
        qid = q.get("id")
        if not isinstance(qid, str):
            continue
        probes = [p for p in _list(q.get("probes")) if isinstance(p, str)]
        if probes:
            out["probes"][qid] = probes
        if isinstance(q.get("task"), dict) and isinstance(q["task"].get("success"), str):
            out["tasks"][qid] = {"success": q["task"]["success"]}
    return out


_KIT_DROP_TOP = ("research", "ia", "flow", "erd", "content", "staleness", "_about")
_KIT_DROP_META = ("userInsights", "tradeoffs", "others", "overview")
_KIT_DROP_ITEM = ("uiLogic", "logicNotes", "usage", "specSrc", "logicSrc")


def kit_registry(reg):
    """A deep copy of `reg` stripped for an outside participant.

    Dropped: `research` (hypotheses, thresholds, findings), `meta.userInsights` / `tradeoffs` / `others` /
    `overview`, and `ia`, `flow`, `erd`, `content` (checked against pb/template/prototype.html: the Prototype
    tab reads only meta, components, screens, tokens, runtime and config; `flow`, `erd` and `content` feed
    only the UX Design and Data tabs, `ia` only the site map and the undesigned-draft outline, and a demo's
    seed data lives in `meta.demo`, which is kept). Also dropped from each component and screen: the prose
    behind the Logic and hand-off drawers (`uiLogic`, `logicNotes`, `usage`) and the pointers to the spec and
    logic sidecars. `meta.designSystem.designLink` goes too. `config.viewOnly` is set."""
    import copy
    out = copy.deepcopy(reg) if isinstance(reg, dict) else {}
    for k in _KIT_DROP_TOP:
        out.pop(k, None)
    out.pop("rules", None)
    meta = out.get("meta")
    if isinstance(meta, dict):
        for k in _KIT_DROP_META:
            meta.pop(k, None)
        if isinstance(meta.get("designSystem"), dict):
            meta["designSystem"].pop("designLink", None)
    for kind in ("components", "screens"):
        for item in _list(out.get(kind)):
            if isinstance(item, dict):
                for k in _KIT_DROP_ITEM:
                    item.pop(k, None)
    cfg = out.get("config") if isinstance(out.get("config"), dict) else {}
    cfg["viewOnly"] = True
    out["config"] = cfg
    return out


# ── pages ────────────────────────────────────────────────────────────────────

def _template_js(name):
    path = os.path.join(TEMPLATE_DIR, JS_FILES[name])
    try:
        with open(path, encoding="utf-8") as f:
            return _SCRIPT_CLOSE.sub("<\\/", f.read())
    except OSError as e:
        raise _err("the page script %s cannot be read (%s)" % (JS_FILES[name], e.strerror or e))


def _inject_head(html, script_tag):
    m = _HEAD_OPEN.search(html)
    if not m:
        raise _err("the shell has no <head>")
    return html[:m.end()] + script_tag + html[m.end():]


def _inject_body_end(html, tags):
    i = html.rfind("</body>")
    if i == -1:
        raise _err("the shell has no </body>")
    return html[:i] + tags + html[i:]


_OBSERVER_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Observer</title>
<style>
/*__PB_CHROME__*/
</style>
</head>
<body>
</body>
</html>
"""


def _prototype_html(reg, base, shell_path, runtime_path):
    """The prototype for a participant: the kit registry rendered through the same pipeline serve.py uses,
    with no logic graph (it carries the rules and their prose) and nothing of the preview server."""
    render = _render()
    shell_path = shell_path or os.path.join(DEFAULT_TEMPLATE_DIR, "prototype.html")
    try:
        with open(shell_path, encoding="utf-8") as f:
            shell = f.read()
        kreg = render.load_bodies(kit_registry(reg), base)
        rt_js, rt_deps, _missing = render.load_runtime(kreg, base)
        html, _m = render.build_html(kreg, shell, render.plugin_version(), logic=None,
                                     runtime_js=render.load_shared_runtime(runtime_path or render.default_runtime_path()),
                                     project_js=rt_js, project_deps=rt_deps)
    except OSError as e:
        raise _err("cannot read the shell: %s" % (e.strerror or e))
    except render.RenderError as e:
        raise _err("render error: %s" % e)
    return _strip_cdn_scripts(html)


# The shell loads Mermaid from a CDN for the flow and ERD canvases. A participant page draws neither, and a
# kit opened on a participant's machine must not call out to a third party (their address would reach it,
# and offline it logs an error). The shell already runs without Mermaid, so the tag is removed. The input is
# our own rendered template, never a request body.
_CDN_SCRIPT = re.compile(r'<script\b[^>]*\bsrc="https://cdn\.jsdelivr\.net/npm/mermaid@[^"]*"[^>]*>\s*</script>', re.IGNORECASE)


def _strip_cdn_scripts(html):
    return _CDN_SCRIPT.sub("", html)


def build_page(reg_path, sid, page, *, participant=None, pilot=False, eid=None, shell_path=None, runtime_path=None):
    """The HTML of one research page. page: session | observer | replay | kit.

    session  the prototype + `PB_RS_SESSION` (sink server) + research-session.js + research-methods.js
    kit      the same with sink download and no post — the file a researcher sends (unmoderated)
    observer a small tool page (the tool's chrome only) for the facilitator: live notes, assist, the guide
    replay   the prototype + `PB_RS_REPLAY` (the stored session and its recordings) + research-replay.js
    Every page is built from the kit registry: a participant's page never carries the study. No live-reload
    client and no `window.PB_PREVIEW` is added, ever. Raises research.ResearchError on a refusal."""
    R = _R()
    if page not in PAGES:
        raise _err("page must be one of %s" % ", ".join(PAGES))
    if not isinstance(sid, str) or not R.STUDY_ID.match(sid):
        raise _err("%r is not a study id" % (sid,))
    if participant is not None and not (isinstance(participant, str) and PARTICIPANT_ID.match(participant)):
        raise _err("participant %r is not a pseudonym like P01" % (participant,))
    reg = R.load_registry(reg_path)
    st = R.find_study(reg, sid)
    if st.get("method") not in SESSION_METHODS:
        raise _err("%s is a %s study; it has no session page" % (sid, st.get("method")))
    base = R.base_of(reg_path)

    if page in ("session", "kit"):
        if not pilot:
            if st.get("status") == "draft":
                raise _err("%s is still a draft — approve it (G-STUDY) before it is fielded; a pilot (pilot=1) may run on a draft" % sid)
            if R.scope_of(st) == "instrument":
                raise _err("%s has scope `instrument`: no sessions are expected; a pilot may still run" % sid)
        cfg = participant_config(reg, st, sink="server" if page == "session" else "download",
                                 participant=participant, pilot=pilot, mode=None if page == "session" else "unmoderated")
        cfg["page"] = page
        html = _prototype_html(reg, base, shell_path, runtime_path)
        html = _inject_head(html, "<script>window.PB_RS_SESSION=%s;</script>" % _js_json(cfg))
        return _inject_body_end(html, "<script id=\"pb-rs-session-js\">%s</script>\n<script id=\"pb-rs-methods-js\">%s</script>\n"
                                % (_template_js("session"), _template_js("methods")))

    if page == "observer":
        cfg = participant_config(reg, st, sink="server", participant=participant, pilot=pilot)
        cfg["page"] = "observer"
        cfg["moderator"] = _moderator_view(st)
        shell = _OBSERVER_SHELL.replace("<title>Observer</title>", "<title>Observer · %s</title>" % _esc(sid))
        html = _render().inject_chrome(shell)
        html = _inject_head(html, "<script>window.PB_RS_SESSION=%s;</script>" % _js_json(cfg))
        return _inject_body_end(html, "<script id=\"pb-rs-session-js\">%s</script>\n" % _template_js("session"))

    # replay
    if not isinstance(eid, str):
        raise _err("replay needs the evidence id of a session (e3) or pilot-<sessionId>")
    obj, media = _replay_source(base, st, eid)
    payload = {"study": sid, "eid": eid, "session": obj, "media": media}
    html = _prototype_html(reg, base, shell_path, runtime_path)
    html = _inject_head(html, "<script>window.PB_RS_REPLAY=%s;</script>" % _js_json(payload))
    return _inject_body_end(html, "<script id=\"pb-rs-replay-js\">%s</script>\n" % _template_js("replay"))


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _session_row(study, session_id):
    for e in _list(study.get("evidence")):
        if isinstance(e, dict) and e.get("kind") == "session" and _dict(e.get("session")).get("id") == session_id:
            return e
    return None


def _pilot_entry(study, session_id):
    for p in _list(study.get("pilots")):
        if isinstance(p, dict) and p.get("sessionId") == session_id:
            return p
    return None


def _pilot_dir_rel(sid):
    return "%s/pilot" % _R().study_rel(sid)


def _guarded(base, rel):
    """base/rel with one realpath check: the file's real folder must be inside base's real path."""
    root = os.path.realpath(base)
    path = os.path.join(root, *rel.split("/"))
    real = os.path.realpath(os.path.dirname(path))
    if real != root and not real.startswith(root + os.sep):
        raise _err("path %r leaves the project" % rel)
    return path


def _pilot_file(base, sid, session_id, suffix=".json"):
    """The pilot file for a validated session id, checked to lie inside memory/research/<sid>/pilot/."""
    if not SESSION_ID.match(session_id):
        raise _err("%r is not a session id" % (session_id,))
    rel = "%s/%s%s" % (_pilot_dir_rel(sid), session_id, suffix)
    path = _guarded(base, rel)
    root = os.path.realpath(os.path.join(base, *_pilot_dir_rel(sid).split("/")))
    real = os.path.realpath(path)
    if not real.startswith(root + os.sep):
        raise _err("path %r leaves the pilot folder" % rel)
    return path, rel


def _load_pilot(base, sid, entry):
    R = _R()
    path, _rel = _pilot_file(base, sid, _str(entry.get("sessionId")))
    if os.path.islink(path):
        raise _err("pilot file is a symlink")
    try:
        raw = R.read_nofollow(path)
    except OSError as e:
        raise _err("pilot file cannot be read (%s)" % (e.strerror or e))
    return parse_session_bytes(raw)


def load_session(base, row):
    """The parsed session of an evidence row (kind session), after research.evidence_file has checked its path,
    that it exists and that its sha256 still matches. Raises ResearchError otherwise."""
    R = _R()
    if not isinstance(row, dict) or row.get("kind") != "session":
        raise _err("%s is not a session" % _dict(row).get("id"))
    if row.get("dropped"):
        raise _err("%s was dropped (a participant withdrew)" % row.get("id"))
    sid = None
    m = re.match(r"^memory/research/(rs-[a-z0-9-]+)/evidence/", _str(row.get("file")))
    if m:
        sid = m.group(1)
    if sid is None:
        raise _err("evidence path %r is not inside a study's evidence folder" % row.get("file"))
    status, raw, msg = R.evidence_file(base, sid, row)
    if status != "ok":
        raise _err(msg)
    return parse_session_bytes(raw)


def _replay_source(base, st, eid):
    sid = st["id"]
    m = PILOT_EID.match(eid)
    if m:
        entry = _pilot_entry(st, m.group(1))
        if entry is None:
            raise _err("%s has no pilot %s" % (sid, m.group(1)))
        obj = _load_pilot(base, sid, entry)
        media = []
        for rel in _list(entry.get("media")):
            if isinstance(rel, str) and rel == "%s/%s-screen.webm" % (_pilot_dir_rel(sid), m.group(1)):
                media.append({"eid": "pilot-%s-screen" % m.group(1), "url": "/__pb_research/%s/evidence/pilot-%s-screen" % (sid, m.group(1)),
                              "mime": "video/webm"})
        return obj, media
    if not EVIDENCE_ID.match(eid):
        raise _err("%r is not an evidence id" % eid)
    row = next((e for e in _list(st.get("evidence")) if isinstance(e, dict) and e.get("id") == eid), None)
    if row is None:
        raise _err("%s has no evidence %s" % (sid, eid))
    obj = load_session(base, row)
    sess_id = _dict(row.get("session")).get("id")
    media = []
    for e in _list(st.get("evidence")):
        if isinstance(e, dict) and e.get("kind") == "recording" and e.get("session") == sess_id and not e.get("dropped") \
                and isinstance(e.get("id"), str) and EVIDENCE_ID.match(e["id"]):
            media.append({"eid": e["id"], "url": "/__pb_research/%s/evidence/%s" % (sid, e["id"]),
                          "mime": _str(e.get("mime")) or "video/webm"})
    return obj, media


# ── the evidence store ───────────────────────────────────────────────────────

def _upsert_participant(st, pid, when, pilot):
    people = st.get("participants")
    if not isinstance(people, list):
        people = st["participants"] = []
    for p in people:
        if isinstance(p, dict) and p.get("id") == pid:
            if pilot:
                return
            p["status"] = "done"
            p["sessionAt"] = when
            return
    people.append({"id": pid, "segment": "", "role": "", "status": "done", "sessionAt": when,
                   "incentive": "none" if pilot else "due", "pilot": bool(pilot), "note": ""})


def _participant_of(st, pid):
    for p in _list(st.get("participants")):
        if isinstance(p, dict) and p.get("id") == pid:
            return p
    return None


def _unlink_quiet(path):
    with contextlib.suppress(OSError):
        os.chmod(path, 0o644)
        os.unlink(path)


def store_session(reg_path, sid, raw, *, keep_pii=False, source="server"):
    """Store one session file. A real session becomes an evidence row (kind session, 0444, sha256), moves the
    study to `fielding` and upserts the participant (done, sessionAt); a pilot goes to
    memory/research/<id>/pilot/ and study.pilots[] and is never evidence. Returns
    {evidence: eid|None, sessionId, pilot, file, warnings}.

    Refusals (ResearchError), in this order: not a session study; scope `instrument` and draft (a pilot is
    allowed on both); a withdrawn or excluded participant; validation errors; a sessionId already stored; the
    same file (sha256) already stored. A row is written only after the file is, and the file is removed again
    if the registry write fails."""
    R = _R()
    if not isinstance(sid, str) or not R.STUDY_ID.match(sid):
        raise _err("%r is not a study id" % (sid,))
    obj = parse_session_bytes(raw)
    raw = bytes(raw)
    pilot = obj.get("pilot") is True
    digest = R.sha256_bytes(raw)
    with R.locked(reg_path, "research_session store (%s)" % source) as reg:
        st = R.find_study(reg, sid)
        if st.get("method") not in SESSION_METHODS:
            raise _err("%s is a %s study; only %s sessions are stored here" % (sid, st.get("method"), ", ".join(SESSION_METHODS)))
        if not pilot:
            if R.scope_of(st) == "instrument":
                raise _err("%s has scope `instrument`: the study ends at the approved questions and no results are expected, "
                           "so nothing is stored. A pilot session is still accepted." % sid)
            if st.get("status") == "draft":
                raise _err("%s is still a draft — approve it (G-STUDY) before any evidence is stored; a pilot session is accepted" % sid)
        errors, warnings = validate_session(obj, st, keep_pii=keep_pii)
        if errors:
            raise _err("the session file is not valid: %s" % "; ".join(errors[:5]) + (" (+%d more)" % (len(errors) - 5) if len(errors) > 5 else ""),
                       data={"errors": errors, "warnings": warnings})
        pid, session_id = obj["participant"], obj["sessionId"]
        person = _participant_of(st, pid)
        if person is not None and person.get("status") in ("withdrawn", "excluded"):
            raise _err("participant %s is %s — their session is not stored" % (pid, person.get("status")))
        if _session_row(st, session_id) is not None or _pilot_entry(st, session_id) is not None:
            raise _err("session %s is already stored" % session_id, data={"duplicate": True})
        for e in _list(st.get("evidence")):
            if isinstance(e, dict) and e.get("sha256") == digest:
                raise _err("the same file is already stored as %s%s" % (e.get("id"), " (dropped)" if e.get("dropped") else ""),
                           data={"duplicate": True})
        base = R.base_of(reg_path)
        stamp = R.now_iso()
        day = obj["startedAt"][:10]
        prev = st.get("status")
        if pilot:
            R.ensure_dir(base, R.study_rel(sid))
            R.ensure_dir(base, _pilot_dir_rel(sid))
            path, rel = _pilot_file(base, sid, session_id)
            R.write_exclusive(path, raw)
            st.setdefault("pilots", []).append({"sessionId": session_id, "participant": pid, "at": obj["startedAt"],
                                                "file": rel, "media": []})
            _upsert_participant(st, pid, day, True)
            eid = None
        else:
            num = R.next_evidence_number(st)
            eid = "e%d" % num
            rel = "%s/%s-%s.json" % (R.evidence_dir_rel(sid), eid, session_id)
            R.ensure_dir(base, R.study_rel(sid))
            R.ensure_dir(base, R.evidence_dir_rel(sid))
            path = R.under(base, rel)
            R.write_exclusive(path, raw)
            summ = summarize(obj)
            person = _participant_of(st, pid) or {}
            st.setdefault("evidence", []).append({
                "id": eid, "file": rel, "kind": "session", "sha256": digest, "importedAt": stamp, "date": day,
                "participant": pid, "role": person.get("role") or None, "segment": person.get("segment") or None,
                "consent": "yes", "responses": None, "droppedColumns": [], "dropped": None,
                "session": {"id": session_id, "method": obj["method"], "mode": obj["mode"], "durationMs": obj["durationMs"],
                            "tasks": summ["tasks"], "outcomes": summ["outcomes"], "recording": summ["recording"], "media": []}})
            st["status"] = "fielding"
            _upsert_participant(st, pid, day, False)
        try:
            R.pbslice._write(reg_path, reg)
        except BaseException:
            _unlink_quiet(path)
            raise
    out_warnings = list(warnings)
    if not pilot and prev in ("analysed", "applied"):
        out_warnings.append("W-REFIELD: study was %s; it is fielding again — re-run analyze/synthesize/verify" % prev)
    return {"evidence": eid, "sessionId": session_id, "pilot": pilot, "file": rel, "warnings": out_warnings}


def _hash_stream(fd):
    h, n, first = hashlib.sha256(), 0, b""
    while True:
        b = os.read(fd, CHUNK)
        if not b:
            break
        if n == 0:
            first = b[:4]
        h.update(b)
        n += len(b)
    return h.hexdigest(), n, first


def _open_regular(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    import stat as _stat
    try:
        if not _stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
    except BaseException:
        os.close(fd)
        raise
    return fd


def store_media(reg_path, sid, session_id, src_path, *, mime="video/webm", move=False):
    """Link a screen recording to a stored session (an evidence row, or a pilot). Refused unless that session's
    consent.recording is true. move=True: `src_path` must be a regular file whose realpath is inside
    memory/research/<id>/.incoming/ (the server's temp upload) and is renamed into place; move=False: it is
    copied. The hash and size are computed here; the file is stored 0444. The recording row (kind recording)
    and the session row link to each other. Returns {evidence: eid|None, file, sha256, bytes}."""
    R = _R()
    if not isinstance(sid, str) or not R.STUDY_ID.match(sid):
        raise _err("%r is not a study id" % (sid,))
    if not isinstance(session_id, str) or not SESSION_ID.match(session_id):
        raise _err("%r is not a session id" % (session_id,))
    if _str(mime).split(";")[0].strip().lower() != "video/webm":
        raise _err("only video/webm recordings are stored (got %r)" % (mime,))
    base = R.base_of(reg_path)
    src = os.path.abspath(src_path)
    if move:
        incoming = os.path.realpath(os.path.join(base, *R.study_rel(sid).split("/"), ".incoming"))
        real = os.path.realpath(src)
        if not real.startswith(incoming + os.sep):
            raise _err("a moved upload must be inside memory/research/%s/.incoming/" % sid)
        if os.path.islink(src):
            raise _err("the upload is a symlink")
        src = real
    elif os.path.islink(src):
        raise _err("%s is a symlink — refusing to follow it" % src_path)
    try:
        fd = _open_regular(src)
    except FileNotFoundError:
        raise _err("recording not found: %s" % src_path, 2)
    except OSError as e:
        raise _err("cannot read the recording: %s" % (e.strerror or e))
    try:
        size = os.fstat(fd).st_size
        if size == 0:
            raise _err("the recording is empty")
        if size > MEDIA_MAX_BYTES:
            raise _err("the recording is %d bytes; the limit is %d" % (size, MEDIA_MAX_BYTES))
        digest, n, first = _hash_stream(fd)
    finally:
        os.close(fd)
    if first != WEBM_MAGIC:
        raise _err("the file is not a WebM recording (no EBML header)")

    with R.locked(reg_path, "research_session media") as reg:
        st = R.find_study(reg, sid)
        row = _session_row(st, session_id)
        pilot = None
        if row is None:
            pilot = _pilot_entry(st, session_id)
            if pilot is None:
                raise _err("session %s is not stored in %s — store the session file first" % (session_id, sid))
        elif row.get("dropped"):
            raise _err("session %s was dropped (a participant withdrew)" % session_id)
        if row is not None:
            obj = load_session(base, row)
        else:
            obj = _load_pilot(base, sid, pilot)
        if _dict(obj.get("consent")).get("recording") is not True:
            raise _err("session %s has no recording consent — a recording is not stored without it" % session_id)
        if row is not None:
            for e in _list(st.get("evidence")):
                if isinstance(e, dict) and e.get("sha256") == digest:
                    raise _err("the same file is already stored as %s" % e.get("id"), data={"duplicate": True})
                if isinstance(e, dict) and e.get("kind") == "recording" and e.get("session") == session_id and not e.get("dropped"):
                    raise _err("session %s already has a recording (%s)" % (session_id, e.get("id")), data={"duplicate": True})
            num = R.next_evidence_number(st)
            eid = "e%d" % num
            rel = "%s/%s-%s-screen.webm" % (R.evidence_dir_rel(sid), eid, session_id)
            R.ensure_dir(base, R.study_rel(sid))
            R.ensure_dir(base, R.evidence_dir_rel(sid))
            dest = R.under(base, rel)
        else:
            if _list(pilot.get("media")):
                raise _err("pilot %s already has a recording" % session_id)
            eid = None
            R.ensure_dir(base, R.study_rel(sid))
            R.ensure_dir(base, _pilot_dir_rel(sid))
            dest, rel = _pilot_file(base, sid, session_id, "-screen.webm")
        if os.path.lexists(dest):
            raise _err("%s already exists" % os.path.relpath(dest, base))
        moved = False
        if move:
            try:
                os.rename(src, dest)
                moved = True
            except OSError:
                _copy_in(src, dest, digest)
                with contextlib.suppress(OSError):
                    os.unlink(src)
                    moved = True
            with contextlib.suppress(OSError):
                os.chmod(dest, 0o444)
        else:
            _copy_in(src, dest, digest)
        try:
            if row is not None:
                st.setdefault("evidence", []).append({
                    "id": eid, "file": rel, "kind": "recording", "sha256": digest, "importedAt": R.now_iso(),
                    "date": row.get("date"), "participant": row.get("participant"), "role": row.get("role"),
                    "segment": row.get("segment"), "consent": "yes", "responses": None, "droppedColumns": [],
                    "dropped": None, "session": session_id, "mime": "video/webm", "bytes": n})
                sess = row["session"]
                sess["media"] = _list(sess.get("media")) + [eid]
                sess["recording"] = True
            else:
                pilot["media"] = _list(pilot.get("media")) + [rel]
            R.pbslice._write(reg_path, reg)
        except BaseException:
            if moved:
                with contextlib.suppress(OSError):
                    os.chmod(dest, 0o644)
                    os.rename(dest, src)
            else:
                _unlink_quiet(dest)
            raise
    return {"evidence": eid, "file": rel, "sha256": digest, "bytes": n}


def _copy_in(src, dest, expect):
    """Stream src into a NEW dest (O_EXCL, no symlink), 0444; the copy must hash to `expect`."""
    h = hashlib.sha256()
    sfd = _open_regular(src)
    try:
        dfd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        try:
            while True:
                b = os.read(sfd, CHUNK)
                if not b:
                    break
                h.update(b)
                view = memoryview(b)
                while view:
                    view = view[os.write(dfd, view):]
        except BaseException:
            os.close(dfd)
            _unlink_quiet(dest)
            raise
        os.close(dfd)
    finally:
        os.close(sfd)
    if h.hexdigest() != expect:
        _unlink_quiet(dest)
        raise _err("the recording changed while it was being stored")
    os.chmod(dest, 0o444)
