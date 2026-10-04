#!/usr/bin/env python3
"""
report.py — the facts behind /pb:report: what one project's history says pb should change.

The audience is the Product Builder MAINTAINER, not the project owner. Two hand-written feedback
reports from real projects were assembled by reading a 3,264-line and a 9,761-line decisions log, 40 backup folders and a dozen
render bodies by eye. Most of that evidence is countable: a `revert` in an entry, a heading that
recurs, a `pre-*` backup a day, a promoted body that still calls itself a CANDIDATE. This tool
counts it, deterministically, and writes the counts as one markdown file with a fixed section
order. The model then reads that file and writes the interpretation (/pb:report §2). Arithmetic
over a large set is I-6 (c); the reading is not, and stays in the prompt.

Read-only on the project. The only write is `--out` (default
`memory/reports/pb-report-<YYYY-MM-DD>.md`), and its parent folder.

  Bracket paths. A project folder named `[HR] Project` is a character class to `glob.glob`, which
  then matches nothing. Nothing here uses glob: every walk is os.walk /
  os.listdir, which take the path literally. tests/report_tool.py runs on a folder named `[x]`.

  Decisions logs are NOT in date order, and they rotate by size. Readers glob `decisions*.md`
  (decisions_rotate.py) — this one lists `memory/` and keeps every `decisions*.md`. Entries are
  split with decisions_rotate's own heading regex, so the two can never disagree about what an
  entry is. HTML comments are blanked first: the template's `## YYYY-MM-DD` example lives in one.

  Backups are copies. `memory/backups/`, `.pb-backups/` and `memory/reports/` are excluded from
  every text scan, or each snapshot would count the log again.

  Session transcripts are opt-in (`--sessions`). Only counts and sequences leave them: which
  /pb:* ran, in what order, how many human turns between runs, which flag NAMES were passed.
  No message text is ever copied into the report.

  report.py [--project DIR] [--out FILE] [--json] [--sessions [DIR]] [--since YYYY-MM-DD]

  --json        print the facts as JSON on stdout (the markdown is still written)
  --sessions    scan ~/.claude/projects/<slug>/*.jsonl, where <slug> is the project path with
                every non-alphanumeric character turned into `-`; give DIR when the sessions ran
                from another folder (the slug is never guessed beyond that one exact name)
  --since       window the dated facts (decisions, backups, explore rounds, sessions)

Exit: 0 = written · 2 = no registry.json under --project, or bad arguments.
"""
import argparse
import bisect
import collections
import contextlib
import datetime
import io
import json
import os
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True        # a vendored pb inside the project must stay untouched
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import decisions_rotate as _rot  # noqa: E402  (sibling; the heading + date regexes and the threshold)

PLUGIN = os.path.dirname(HERE)
COMMANDS_DIR = os.path.join(PLUGIN, "commands")
SKILLS_DIR = os.path.join(PLUGIN, "skills")
SHELL = os.path.join(PLUGIN, "template", "prototype.html")
MANIFEST = os.path.join(PLUGIN, "migrations", "manifest.py")
PLUGIN_JSON = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")

TOP = 5            # evidence lines per fact
TOP_TERM = 3       # evidence lines per vocabulary term
TOP_ROWS = 12      # rows in a ranked table
BUDGET_BUILD_MS = 100.0     # DESIGN.md constraint 5
BUDGET_PIPELINE_MS = 1500.0
LINT_TIMEOUT_S = 60

SECTIONS = [
    ("shape", "1 · Project shape"),
    ("decisions", "2 · Decisions log"),
    ("mentions", "3 · Commands, flags and skills named in memory"),
    ("explore", "4 · Explore"),
    ("backups", "5 · Backups"),
    ("performance", "6 · Performance"),
    ("tests", "7 · Tests"),
    ("sessions", "8 · Sessions"),
    ("hygiene", "9 · Hygiene"),
    ("workarounds", "10 · Workarounds"),
]

# Copied from tests/command_refs.py RETIRED (a tool does not import a test), with the replacement
# each name points at, plus the never-shipped names tests/skill_refs_lint.py also retires.
RETIRED = {
    "flow": "/pb:plan --flow", "data": "/pb:plan --data",
    "sync-flow": "/pb:plan --flow", "sync-erd": "/pb:plan --data", "sync-data": "/pb:plan --data",
    "check-drift": "/pb:test --drift",
    "handoff-close": "/pb:handoff", "handoff-dev": "/pb:handoff", "hand-off": "/pb:handoff",
    "build-figma-handoff": "/pb:handoff",
    "build-check-design-system": "/pb:build §3a",
    "preview-ds": "/pb:preview §2b",
    "validate": "/pb:handoff --tier=host",
    "build-generate": "(never shipped)", "build-explore": "/pb:explore",
    "build-flow": "/pb:plan --flow", "build-logic": "/pb:build",
}
# tests/skill_refs_lint.py SKILL_SHAPE: skills are capability-prefixed.
_SKILL_SHAPE = re.compile(
    r"(?<![\w-])((?:think|ref|craft|agent|design-component|sandbox)-[a-z0-9-]+|figma-use)(?![\w-])")

# memory/ entries a command, tool or template owns. Anything else in memory/ was written by hand.
OWNED_MEMORY = {
    "prd.md": "/pb:init · /pb:specify",
    "spec.md": "/pb:specify",
    "plan.md": "/pb:plan",
    "tasks.md": "/pb:plan",
    "constitution.md": "/pb:init (template)",
    "gaps.md": "/pb:init --figma",
    "scenarios.md": "pb name (no current writer)",
    "doctor.json": "lint_registry.py --report",
    "design-options.json": "pb-builder (explore option mode)",
    "explore/": "/pb:explore",
    "backups/": "/pb:explore promote · risky writes",
    "reports/": "/pb:report",
    "test-plans/": "/pb:test",
    "drift-reports/": "/pb:test --save",
    "figma-pushes/": "/pb:handoff (Figma)",
    ".pb-backups/": "decisions_rotate.py",
}
_DECISIONS_FILE = re.compile(r"^decisions.*\.md$")
SKIP_SCAN = {"backups", ".pb-backups", "reports"}      # copies, or this tool's own output

# Root entries the pb layout accounts for; everything else is listed as "outside the layout".
ROOT_LAYOUT = {
    "registry.json", "prototype.html", "design-system.html", "render", "spec", "logic", "runtime",
    "memory", "design-system", ".pb-backups", "figma-tokens.json", "figma-transfer.json",
    "figma-nodes.json", "ds-catalog.json", "gaps.md", "handoff", "handoff-dev", "CLAUDE.md",
    "AGENTS.md", ".claude", ".git", ".gitignore", ".DS_Store", "README.md",
}
_BAK = re.compile(r"\.bak\b|\.bak-|\.orig$|\.old$|~$|\bcopy\b", re.I)
SCRIPT_DIRS = ("tools", "scripts", ".pb-patches", "patches", os.path.join("memory", "patches"))

# Back-and-forth vocabulary. One label per idea; `override` covers overriding / overridden.
VOCAB = [
    ("revert", r"\brevert"),
    ("rolled back", r"\broll(?:ed|s|ing)?[- ]back\b|\brollback\b"),
    ("supersede", r"\bsupersed"),
    ("override", r"\boverrid"),
    ("again", r"\bagain\b"),
    ("rework", r"\brework"),
    ("redo", r"\bre-?do(?:ne|ing)?\b"),
    ("re-open", r"\bre-?open"),
    ("contradict", r"\bcontradict"),
    ("regress", r"\bregress"),
    ("stale", r"\bstale\b"),
    ("wrong", r"\bwrong\b"),
    ("mistake", r"\bmistake"),
    ("workaround", r"\bwork-?arounds?\b"),
    ("manual", r"\bmanual(?:ly)?\b"),
    ("hand-edit / by hand", r"\bhand[- ]edit|\bby hand\b"),
    ("touch registry", r"\btouch\s+\S*registry"),
]
VOCAB = [(label, re.compile(rx, re.I)) for label, rx in VOCAB]

NOTICES = [
    ("skill degrade (NS6)", r"skill degrade|\bNS6\b|failed to load"),
    ("schema gap / blocked write", r"schema gap|blocked: run /pb:update-version"),
    ("gate override", r"gate override|overrid\w* (?:the )?(?:drift|DS|stack|trio)[- ](?:gate|lock)"),
    ("did not run / blocked", r"\bexit(?:ed|s)? 3\b|did(?:n't| not) run\b|playwright (?:absent|missing|not installed|unavailable)"),
    ("lint false positive", r"false[- ]positive"),
    ("preview did not reload", r"did(?:n't| not) (?:pick up|reload)|not picked up|hard[- ]refresh"),
]
NOTICES = [(label, re.compile(rx, re.I)) for label, rx in NOTICES]

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_CMD_REF = re.compile(r"/pb:([a-z][a-z0-9-]*)")
_CMD_FLAGS = re.compile(r"/pb:([a-z][a-z0-9-]*)((?:[ \t]+--[a-z][a-z-]*(?:=\S+)?)+)")
_FLAG = re.compile(r"--[a-z][a-z-]*")
_CODE_SPAN = re.compile(r"`[^`\n]+`")
_FIELD = re.compile(r"^\s*(?:[-*+]\s+)?\**\s*([A-Za-z][\w .-]*?)\s*\**\s*[:=]\s*(.*)$")  # orchestrate.py
_ALT = re.compile(r"^\s*(?:[-*+]\s+)?\*{0,2}\s*Alternatives?\b[^:\n*]*\*{0,2}\s*:\s*\*{0,2}\s*(.*)$", re.I)
_RULE = re.compile(r"^\s*(?:[-*+]\s+)?\*{0,2}\s*Rules?(?:\s+id)?\*{0,2}\s*:\s*\*{0,2}\s*(.*)$", re.I)
_EMPTY = {"", "—", "-", "–", "none", "n/a", "na", "(none)", "nil", "tbd"}
_SUB_BULLET = re.compile(r"^\s+[-*+]\s+\S")
_DATE_ANY = re.compile(r"20\d\d-\d\d-\d\d")
_JS_TOKEN = re.compile(r"//[^\n]*|/\*.*?(?:\*/|\Z)|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`", re.S)
_HEADER_NAMES = re.compile(r"\bCANDIDATE\b|\bopt-\d+\b|registry\.opt-\d+")
_EXPLORE_WORD = re.compile(r"\bexplor(?:e|ation|ed|ing)\b|/pb:explore", re.I)
_EXPLORE_NONE = re.compile(r"\breject(?:ed|s)?\b|none of the options|nothing (?:was )?(?:chosen|picked|promoted)|no option", re.I)
_STOP = set("""a an the of to in on for and or is are be by with from at as it its into via vs no not
now one two this that these those than then when what which who why how do does did per out up over
under after before only also all any each every new old same so but""".split())


# ── small helpers ─────────────────────────────────────────────────────────────────

def _rel(project, path):
    return os.path.relpath(path, project).replace(os.sep, "/")


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def _tree(path):
    """(bytes, files) under a folder, or a file's own size."""
    if os.path.isfile(path):
        return os.path.getsize(path), 1
    total = n = 0
    for root, dirs, files in os.walk(path):
        dirs.sort()
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
                n += 1
            except OSError:
                pass
    return total, n


def _walk(root, exts=None, skip=()):
    """Every file under root, sorted, pruning folders named in `skip`. Bracket-safe."""
    out = []
    if not os.path.isdir(root):
        return out
    for cur, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for f in sorted(files):
            if exts is None or f.endswith(exts):
                out.append(os.path.join(cur, f))
    return out


def _kb(n):
    if n is None:
        return "—"
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1048576.0)
    return "%.0f KB" % (n / 1024.0) if n >= 1024 else "%d B" % n


def _short(text, n=100):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _week(datestr):
    try:
        y, w, _ = datetime.date.fromisoformat(datestr[:10]).isocalendar()
        return "%d-W%02d" % (y, w)
    except ValueError:
        return "invalid date"


def _ranked(counter, n=TOP_ROWS):
    return sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[:n]


def _blank_comments(text):
    """HTML comments → the same number of newlines, so line numbers still match the file."""
    return _HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


class _Lines:
    """A markdown file's lines plus the nearest heading above any line."""

    def __init__(self, text):
        self.lines = text.split("\n")
        self.marks, self.heads = [], []
        for i, line in enumerate(self.lines, 1):
            m = _MD_HEADING.match(line)
            if m:
                self.marks.append(i)
                self.heads.append(m.group(2))

    def heading(self, lineno):
        k = bisect.bisect_right(self.marks, lineno) - 1
        return self.heads[k] if k >= 0 else ""


def _ev(where, heading, date=None):
    e = {"where": where, "heading": _short(heading)}
    if date:
        e["date"] = date
    return e


def _add_ev(bucket, rel, lineno, heading, cap):
    """Append one evidence line unless the cap is reached or this file + heading is already in."""
    if len(bucket) < cap and not any(e["where"].rsplit(":", 1)[0] == rel and e["heading"] == _short(heading)
                                     for e in bucket):
        bucket.append(_ev("%s:%d" % (rel, lineno), heading))


# ── the plugin side ───────────────────────────────────────────────────────────────

def shipped_commands():
    try:
        return sorted(f[:-3] for f in os.listdir(COMMANDS_DIR) if f.endswith(".md"))
    except OSError:
        return []


def shipped_skills():
    try:
        return sorted(d for d in os.listdir(SKILLS_DIR)
                      if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md")))
    except OSError:
        return []


_FLAG_CACHE = {}


def documented_flags(cmd):
    """The flags pb/commands/<cmd>.md documents — the same rule as tests/skill_refs_lint.py S3."""
    if cmd not in _FLAG_CACHE:
        _FLAG_CACHE[cmd] = set(_FLAG.findall(_read(os.path.join(COMMANDS_DIR, cmd + ".md")) or ""))
    return _FLAG_CACHE[cmd]


def current_schema():
    m = re.search(r"(?m)^CURRENT_SCHEMA\s*=\s*(\d+)", _read(MANIFEST) or "")
    return int(m.group(1)) if m else None


def plugin_version():
    try:
        with open(PLUGIN_JSON, encoding="utf-8") as f:
            return json.load(f).get("version") or "unknown"
    except (OSError, ValueError):
        return "unknown"


def plugin_tools():
    try:
        names = {f for f in os.listdir(HERE) if f.endswith(".py")}
    except OSError:
        names = set()
    return names | {"migrate_runner.py"}


# ── 1 · project shape ─────────────────────────────────────────────────────────────

def _token_count(node):
    n = 0
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict) and ("$value" in v or "value" in v):
                n += 1
            elif isinstance(v, dict) and not str(k).startswith("$"):
                n += _token_count(v)
    return n


def _memory_owner(name, is_dir):
    if is_dir:
        return OWNED_MEMORY.get(name + "/")
    if _DECISIONS_FILE.match(name):
        return "/pb:clarify · /pb:build (append)"
    return OWNED_MEMORY.get(name)


def facts_shape(project, reg, reg_err):
    meta = reg.get("meta") if isinstance(reg.get("meta"), dict) else {}
    schema = meta.get("schemaVersion")
    ds = meta.get("dsSource")
    bodies = [p for p in _walk(os.path.join(project, "render"), (".js",), skip={"_candidates"})]
    by_kind = collections.Counter()
    for p in bodies:
        parts = _rel(os.path.join(project, "render"), p).split("/")
        by_kind[parts[0] if len(parts) > 1 else "(top level)"] += 1
    mem = os.path.join(project, "memory")
    memory = []
    if os.path.isdir(mem):
        for name in sorted(os.listdir(mem)):
            path = os.path.join(mem, name)
            is_dir = os.path.isdir(path)
            size, files = _tree(path)
            memory.append({"name": name + ("/" if is_dir else ""), "bytes": size, "files": files,
                           "owner": _memory_owner(name, is_dir)})
    comps = reg.get("components") if isinstance(reg.get("components"), list) else []
    return {
        "name": meta.get("name") or os.path.basename(os.path.abspath(project)),
        "registryError": reg_err,
        "registryBytes": os.path.getsize(os.path.join(project, "registry.json")),
        "schemaVersion": schema,
        "schemaAbsent": schema is None,
        "currentSchema": current_schema(),
        "dsSource": (ds.get("type") if isinstance(ds, dict) else ds),
        "components": len(comps),
        "localComponents": sum(1 for c in comps if isinstance(c, dict) and c.get("scope") == "local"),
        "screens": len(reg.get("screens") or []) if isinstance(reg.get("screens"), list) else 0,
        "tokens": _token_count(reg.get("tokens") or {}),
        "runtimeModules": len(reg.get("runtime") or []) if isinstance(reg.get("runtime"), list) else 0,
        "renderBodies": len(bodies),
        "renderByKind": dict(sorted(by_kind.items())),
        "sidecars": {d: (len(_walk(os.path.join(project, d))) if os.path.isdir(os.path.join(project, d)) else None)
                     for d in ("spec", "logic", "runtime")},
        "memory": memory,
        "handWritten": [m["name"] for m in memory if not m["owner"]],
    }


# ── 2 · decisions log ─────────────────────────────────────────────────────────────

def _field_state(lines, idx, value):
    v = value.strip().strip("*").strip()
    if v.lower().rstrip(".") in _EMPTY or (v.startswith("<") and v.endswith(">")):
        if not v and idx + 1 < len(lines) and _SUB_BULLET.match(lines[idx + 1]):
            return "filled"
        return "empty"
    return "filled"


def parse_decisions(project):
    """Every entry across memory/decisions*.md, in file order, with its file:line."""
    mem = os.path.join(project, "memory")
    files = sorted(f for f in os.listdir(mem) if _DECISIONS_FILE.match(f)) if os.path.isdir(mem) else []
    out, sizes = [], []
    for fn in files:
        path = os.path.join(mem, fn)
        raw = _read(path) or ""
        sizes.append({"file": "memory/" + fn, "bytes": len(raw.encode("utf-8"))})
        text = _blank_comments(raw)
        marks = [m.start() for m in _rot._HEADING.finditer(text)]
        for i, start in enumerate(marks):
            end = marks[i + 1] if i + 1 < len(marks) else len(text)
            chunk = text[start:end]
            head = chunk.split("\n", 1)[0][3:].strip()
            m = _rot._DATE.search(head)
            lines = chunk.split("\n")
            alt = rule = "absent"
            for j, line in enumerate(lines):
                if alt == "absent":
                    a = _ALT.match(line)
                    if a:
                        alt = _field_state(lines, j, a.group(1))
                if rule == "absent":
                    r = _RULE.match(line)
                    if r:
                        rule = _field_state(lines, j, r.group(1))
            out.append({"file": "memory/" + fn, "line": text.count("\n", 0, start) + 1,
                        "heading": head, "date": m.group(0) if m else None, "text": chunk,
                        "alternatives": alt, "rule": rule})
    return out, sizes


def topic_key(heading):
    h = _rot._DATE.sub(" ", heading.lower())
    h = re.sub(r"\(\d+\)|\[[^\]]*\]", " ", h)
    words = [w for w in re.findall(r"[^\W\d_][\w'-]*", h) if w not in _STOP and len(w) > 1]
    return " ".join(words[:3])


_HEAD_PREFIX = re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2})?\s*(?:\(\d+\))?\s*[—–·:-]*\s*")


def subject_key(heading):
    """`2026-09-28 (212) — Tách: a result card…` → `tách`. Empty when there is no early colon."""
    h = re.sub(r"\[[^\]]*\]", " ", _HEAD_PREFIX.sub("", heading)).strip(" —–·-")
    if ":" not in h[:60]:
        return ""
    subj = h.split(":", 1)[0]
    subj = re.sub(r"[`*_\"'()]", "", subj).strip().lower()
    return " ".join(subj.split()) if 0 < len(subj) <= 60 else ""


def facts_decisions(project, since):
    entries, sizes = parse_decisions(project)
    total_bytes = sum(s["bytes"] for s in sizes)
    threshold = _rot.DEFAULT_THRESHOLD_KB * 1024
    undated = [e for e in entries if not e["date"]]
    window = [e for e in entries if e["date"] and (not since or e["date"] >= since)]
    if not since:
        window = window + undated            # undated entries count when nothing is windowed
        window.sort(key=lambda e: (e["file"], e["line"]))

    inversions = pairs = 0
    for fname in sorted({e["file"] for e in entries}):
        dated = [e["date"] for e in entries if e["file"] == fname and e["date"]]
        for a, b in zip(dated, dated[1:]):
            pairs += 1
            inversions += b > a          # newest-first: a later line must not be newer

    per_week = collections.Counter(_week(e["date"]) for e in window if e["date"])

    vocab = []
    any_hit = set()
    for label, rx in VOCAB:
        hits = []
        for k, e in enumerate(window):
            n = len(rx.findall(e["text"]))
            if n:
                hits.append((n, k, e))
                any_hit.add(k)
        hits.sort(key=lambda t: (-t[0], t[1]))
        vocab.append({"term": label, "entries": len(hits), "hits": sum(h[0] for h in hits),
                      "evidence": [_ev("%s:%d" % (e["file"], e["line"]), e["heading"], e["date"])
                                   for _n, _k, e in hits[:TOP_TERM]]})

    def bucket(keyfn, minimum=3):
        groups = collections.OrderedDict()
        for e in window:
            k = keyfn(e["heading"])
            if k:
                groups.setdefault(k, []).append(e)
        rows = [{"topic": k, "entries": len(v),
                 "first": min((x["date"] for x in v if x["date"]), default=None),
                 "last": max((x["date"] for x in v if x["date"]), default=None),
                 "evidence": [_ev("%s:%d" % (x["file"], x["line"]), x["heading"], x["date"]) for x in v[:3]]}
                for k, v in groups.items() if len(v) >= minimum]
        rows.sort(key=lambda r: (-r["entries"], r["topic"]))
        return rows

    state = lambda key: dict(collections.Counter(e[key] for e in window))  # noqa: E731
    no_alt = [e for e in window if e["alternatives"] != "filled"]
    return {
        "files": sizes,
        "totalBytes": total_bytes,
        "thresholdBytes": int(threshold),
        "rotatedSiblings": [s["file"] for s in sizes if s["file"] != "memory/decisions.md"],
        "entries": len(entries),
        "undated": len(undated),
        "undatedEvidence": [_ev("%s:%d" % (e["file"], e["line"]), e["heading"]) for e in undated[:TOP]],
        "inWindow": len(window),
        "dateOrder": {"adjacentPairs": pairs, "inversions": inversions},
        "perWeek": dict(sorted(per_week.items())),
        "backAndForthEntries": len(any_hit),
        "vocabulary": vocab,
        "alternatives": state("alternatives"),
        "alternativesMissingEvidence": [_ev("%s:%d" % (e["file"], e["line"]), e["heading"], e["date"])
                                        for e in no_alt if e["alternatives"] == "empty"][:TOP],
        "rule": state("rule"),
        "recurringTopics": bucket(lambda h: topic_key(h))[:TOP_ROWS],
        "recurringSubjects": bucket(subject_key)[:TOP_ROWS],
    }, entries


# ── 3 · commands, flags, skills named in memory ───────────────────────────────────

def _memory_docs(project):
    return [p for p in _walk(os.path.join(project, "memory"), (".md",), skip=SKIP_SCAN)]


def _flags_on_line(line):
    """[(cmd, flag)] — flags inside the same code span as the command, or flags that directly
    follow it in prose. A bare `--x` elsewhere on the line is a CSS variable as often as a flag."""
    out = []
    spans = list(_CODE_SPAN.finditer(line))
    for sp in spans:
        seg = sp.group(0)
        for m in _CMD_REF.finditer(seg):
            nxt = seg.find("/pb:", m.end())
            tail = seg[m.end(): nxt if nxt >= 0 else len(seg)]
            out += [(m.group(1), f) for f in _FLAG.findall(tail)]
    prose = _CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
    for m in _CMD_FLAGS.finditer(prose):
        out += [(m.group(1), f) for f in _FLAG.findall(m.group(2))]
    return out


def _task_skills(project):
    """(assigned Counter, tasks with a skill field, of which no skill) from memory/tasks.md."""
    text = _read(os.path.join(project, "memory", "tasks.md"))
    assigned, fields, none_ = collections.Counter(), 0, 0
    if not text:
        return assigned, 0, 0
    col = None
    for line in text.split("\n"):
        values = []
        if line.lstrip().startswith("|"):
            cells = [c.strip().strip("*`").strip().lower() for c in line.strip().strip("|").split("|")]
            if col is None and any(re.fullmatch(r"skills?", c) for c in cells):
                col = next(i for i, c in enumerate(cells) if re.fullmatch(r"skills?", c))
                continue
            if col is not None and col < len(cells) and not set(cells[col]) <= set("-: "):
                values = [cells[col]]
        else:
            col = None
            m = _FIELD.match(line)
            if m and m.group(1).strip().lower() in ("skill", "skills"):
                values = [m.group(2)]
        for v in values:
            fields += 1
            names = [t.strip(" `*.()") for t in re.split(r"[,;/+&]|\s+and\s+|\s+", v) if t.strip(" `*.()")]
            names = [n for n in names if _SKILL_SHAPE.fullmatch(n.lower())]
            if not names:
                none_ += 1
            for n in names:
                assigned[n.lower()] += 1
    return assigned, fields, none_


def facts_mentions(project):
    cmds, skills = set(shipped_commands()), set(shipped_skills())
    docs = _memory_docs(project)
    cmd_count, cmd_ev = collections.Counter(), collections.defaultdict(list)
    flag_count, flag_ev = collections.Counter(), collections.defaultdict(list)
    skill_count = collections.Counter()
    notice_count, notice_ev = collections.Counter(), collections.defaultdict(list)
    chains, chain_ev = 0, []
    for path in docs:
        rel = _rel(project, path)
        lines = _Lines(_blank_comments(_read(path) or ""))
        # A decisions log opens with the template's house note, which itself names "gate
        # override" and the rotation tool: that is pb talking, not the project. Skip to entry one.
        start = 1
        if _DECISIONS_FILE.match(os.path.basename(path)):
            start = next((i for i, ln in enumerate(lines.lines, 1) if ln.startswith("## ")), len(lines.lines) + 1)
        for n, line in enumerate(lines.lines, 1):
            if n < start:
                continue
            names = _CMD_REF.findall(line)
            for name in names:
                cmd_count[name] += 1
                if name not in cmds:
                    _add_ev(cmd_ev[name], rel, n, lines.heading(n), TOP)
            if len({x for x in names if x in cmds}) >= 3:
                chains += 1
                _add_ev(chain_ev, rel, n, lines.heading(n), TOP)
            for cmd, flag in _flags_on_line(line):
                if cmd in cmds:
                    flag_count[(cmd, flag)] += 1
                    if flag not in documented_flags(cmd):
                        _add_ev(flag_ev[(cmd, flag)], rel, n, lines.heading(n), TOP)
            for m in _SKILL_SHAPE.finditer(line):
                name = m.group(1)
                before = line[max(0, m.start(1) - 7):m.start(1)]
                marked = before.endswith(("`", "pb:", "skills/"))
                if name in skills or marked:
                    skill_count[name] += 1
            for label, rx in NOTICES:
                if rx.search(line):
                    notice_count[label] += 1
                    _add_ev(notice_ev[label], rel, n, lines.heading(n), TOP_TERM)

    def status(name):
        if name in cmds:
            return "shipped"
        if name in RETIRED:
            return "retired"
        if name in skills:
            return "skill named as a command"
        return "unknown"

    assigned, task_fields, task_none = _task_skills(project)
    return {
        "scannedFiles": len(docs),
        "commands": [{"name": k, "mentions": v, "status": status(k), "replacement": RETIRED.get(k),
                      "evidence": cmd_ev.get(k, [])} for k, v in _ranked(cmd_count, 999)],
        "flags": [{"command": c, "flag": f, "mentions": v, "documented": f in documented_flags(c),
                   "evidence": flag_ev.get((c, f), [])} for (c, f), v in _ranked(flag_count, 999)],
        "skills": [{"name": k, "mentions": v, "shipped": k in skills} for k, v in _ranked(skill_count, 999)],
        "tasks": {"skillFields": task_fields, "noSkill": task_none,
                  "assigned": dict(_ranked(assigned, 999)),
                  "neverAssigned": sorted(skills - set(assigned)) if task_fields else [],
                  "assignedNotShipped": sorted(set(assigned) - skills)},
        "notices": [{"notice": label, "lines": notice_count.get(label, 0),
                     "evidence": notice_ev.get(label, [])} for label, _rx in NOTICES],
        "chains": {"lines": chains, "evidence": chain_ev},
    }


# ── 4 · explore ───────────────────────────────────────────────────────────────────

def _manifest_row(path, man):
    opts = [o for o in man.get("options") or [] if isinstance(o, dict)]
    rubric = [c for c in man.get("rubric") or [] if isinstance(c, dict)]
    scores = man.get("scores") or {}
    cells = len(opts) * len(rubric)
    scored = 0
    avg = {}
    for o in opts:
        vals = []
        for c in rubric:
            v = scores.get("%s:%s" % (c.get("id"), o.get("slot")))
            if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5:
                vals.append(v)
        scored += len(vals)
        if vals:
            avg[o.get("slot")] = round(sum(vals) / float(len(vals)), 2)
    return {"file": path, "target": man.get("target"), "mode": man.get("mode", "target"),
            "status": man.get("status", "open"), "options": len(opts), "cells": cells,
            "scored": scored, "averages": avg, "pick": (man.get("verdict") or {}).get("pick"),
            "createdAt": man.get("createdAt"), "closedAt": man.get("closedAt")}


def facts_explore(project, since, entries):
    root = os.path.join(project, "memory", "explore")
    rounds = []
    for sub in ("", "_closed"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if not (f.endswith(".json") and os.path.isfile(p)):
                continue
            try:
                with open(p, encoding="utf-8") as fh:
                    man = json.load(fh)
            except (OSError, ValueError):
                rounds.append({"file": _rel(project, p), "status": "unreadable"})
                continue
            if isinstance(man, dict):
                rounds.append(_manifest_row(_rel(project, p), man))
    if since:
        rounds = [r for r in rounds if not r.get("createdAt") or str(r["createdAt"])[:10] >= since]
    open_targets = {r.get("target") for r in rounds if r.get("status") == "open"}
    cand_root = os.path.join(project, "render", "_candidates")
    candidates = []
    if os.path.isdir(cand_root):
        for t in sorted(os.listdir(cand_root)):
            if os.path.isdir(os.path.join(cand_root, t)):
                candidates.append({"target": t, "files": _tree(os.path.join(cand_root, t))[1],
                                   "openManifest": t in open_targets})
    status = collections.Counter(r.get("status") for r in rounds)
    named = [e for e in entries if _EXPLORE_WORD.search(e["text"])
             and (not since or (e["date"] or "") >= since)]
    rejected = [e for e in named if _EXPLORE_NONE.search(e["text"])]
    return {
        "rounds": rounds,
        "byStatus": dict(sorted(status.items(), key=lambda kv: str(kv[0]))),
        "optionsPerRound": round(sum(r.get("options", 0) for r in rounds) / float(len(rounds)), 2) if rounds else None,
        "cells": sum(r.get("cells", 0) for r in rounds),
        "unscored": sum(r.get("cells", 0) - r.get("scored", 0) for r in rounds),
        "unscoredRounds": sum(1 for r in rounds if r.get("cells") and not r.get("scored")),
        "candidates": candidates,
        "orphanedCandidates": [c["target"] for c in candidates if not c["openManifest"]],
        "decisionsNamingExplore": len(named),
        "decisionsNamingRejection": len(rejected),
        "rejectionEvidence": [_ev("%s:%d" % (e["file"], e["line"]), e["heading"], e["date"]) for e in rejected[:TOP]],
    }


# ── 5 · backups ───────────────────────────────────────────────────────────────────

def _name_date(name):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", name) or re.search(r"(\d{4})(\d{2})(\d{2})T\d{4,6}", name)
    if not m:
        return None
    return m.group(1) if len(m.groups()) == 1 else "%s-%s-%s" % m.groups()


def facts_backups(project, since):
    d = os.path.join(project, "memory", "backups")
    snaps = []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            size, files = _tree(os.path.join(d, name))
            snaps.append({"name": name, "date": _name_date(name), "bytes": size, "files": files})
    if since:
        snaps = [s for s in snaps if not s["date"] or s["date"] >= since]
    pre = [s for s in snaps if re.search(r"(?:^|-)pre-", s["name"])]
    dates = sorted(s["date"] for s in pre if s["date"])
    span = None
    if dates:
        span = (datetime.date.fromisoformat(dates[-1]) - datetime.date.fromisoformat(dates[0])).days + 1
    per_day = collections.Counter(s["date"] for s in snaps if s["date"])
    pb_backups = {}
    for where in (".pb-backups", os.path.join("memory", ".pb-backups")):
        p = os.path.join(project, where)
        pb_backups[where.replace(os.sep, "/")] = _tree(p)[1] if os.path.isdir(p) else None
    return {
        "snapshots": len(snaps),
        "bytes": sum(s["bytes"] for s in snaps),
        "pre": [s["name"] for s in pre],
        "preFirst": dates[0] if dates else None,
        "preLast": dates[-1] if dates else None,
        "preSpanDays": span,
        "perDay": dict(sorted(per_day.items())),
        "busiestDays": [{"date": k, "snapshots": v} for k, v in _ranked(per_day, 3)],
        "other": [s["name"] for s in snaps if s not in pre],
        "pbBackups": pb_backups,
    }


# ── 6 · performance (measured) ────────────────────────────────────────────────────

def measure_render(project, reg):
    """Time the render pipeline in-process, exactly as render_file runs it. Never writes."""
    out = {"measured": False}
    sink = io.StringIO()
    try:
        import render  # noqa: E402  (sibling)
        with open(SHELL, encoding="utf-8") as f:
            shell = f.read()
        with contextlib.redirect_stdout(sink):
            t = time.perf_counter()
            r = render.load_bodies(reg, project)          # returns a new dict; reg is untouched
            t1 = time.perf_counter()
            r = render.load_specs(r, project)
            t2 = time.perf_counter()
            logic = render.load_logic(project, r)
            t3 = time.perf_counter()
            rt_js, rt_deps, _missing = render.load_runtime(r, project)
            runtime_js = render.load_shared_runtime()
            t4 = time.perf_counter()
            best = None
            html = ""
            for _ in range(3):
                b0 = time.perf_counter()
                html, _m = render.build_html(r, shell, "report", logic=logic, runtime_js=runtime_js,
                                             project_js=rt_js, project_deps=rt_deps)
                ms = (time.perf_counter() - b0) * 1000.0
                best = ms if best is None else min(best, ms)
        out.update({
            "measured": True,
            "loadBodiesMs": round((t1 - t) * 1000.0, 1),
            "loadSpecsMs": round((t2 - t1) * 1000.0, 1),
            "loadLogicMs": round((t3 - t2) * 1000.0, 1),
            "loadRuntimeMs": round((t4 - t3) * 1000.0, 1),
            "buildHtmlMs": round(best, 1),
            "pipelineMs": round((t4 - t) * 1000.0 + best, 1),
            "htmlBytes": len(html.encode("utf-8")),
            "logicItems": len((logic or {}).get("items") or []),
            "logicHandlers": len((logic or {}).get("handlers") or []),
            "logicSkipped": logic is None,
        })
        out["_itemHash"] = (logic or {}).get("itemHash") or {}
    except Exception as exc:                                        # noqa: BLE001
        out["error"] = "%s: %s" % (type(exc).__name__, _short(exc, 160))
    return out


def measure_lint(reg_path):
    out = {"measured": False}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    t = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, "-B", os.path.join(HERE, "lint_registry.py"), "--strict", reg_path],
                           capture_output=True, text=True, timeout=LINT_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        out["error"] = "timed out after %d s" % LINT_TIMEOUT_S
        return out
    except OSError as exc:
        out["error"] = str(exc)
        return out
    codes = collections.Counter()
    sev = collections.Counter()
    for line in (p.stdout + "\n" + p.stderr).split("\n"):
        m = re.match(r"^(ERROR|WARN) \[([A-Z0-9-]+)\]", line)
        if m:
            sev[m.group(1)] += 1
            codes[(m.group(2), m.group(1))] += 1
    out.update({"measured": True, "exit": p.returncode, "errors": sev.get("ERROR", 0),
                "warnings": sev.get("WARN", 0), "seconds": round(time.perf_counter() - t, 2),
                "codes": [{"code": c, "severity": s, "count": n} for (c, s), n in _ranked(codes)]})
    return out


def facts_performance(project, reg, reg_path):
    render_ = measure_render(project, reg)
    by_key = {}
    if isinstance(reg, dict):
        for k, v in reg.items():
            by_key[k] = len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    on_disk = os.path.join(project, "prototype.html")
    return {
        "render": render_,
        "lint": measure_lint(reg_path),
        "registryBytes": os.path.getsize(reg_path),
        "registryByKey": [{"key": k, "bytes": b} for k, b in _ranked(by_key, 8)
                          if b * 100 >= os.path.getsize(reg_path)],      # keys under 1% are noise
        "prototypeHtmlBytes": os.path.getsize(on_disk) if os.path.isfile(on_disk) else None,
    }


# ── 7 · tests ─────────────────────────────────────────────────────────────────────

def facts_tests(reg, item_hash):
    flow = reg.get("flow") if isinstance(reg.get("flow"), dict) else {}
    stories = [s for s in flow.get("stories") or [] if isinstance(s, dict)]
    total = runnable = prose = never = stale = no_inputs = 0
    status = collections.Counter()
    ran = []
    for s in stories:
        for sc in s.get("scenarios") or []:
            total += 1
            if not isinstance(sc, dict) or not isinstance(sc.get("test"), dict):
                prose += 1
                continue
            runnable += 1
            lr = sc.get("lastResult")
            if not isinstance(lr, dict):
                never += 1
                continue
            status[str(lr.get("status") or "unknown")] += 1
            if lr.get("ranAt"):
                ran.append(str(lr["ranAt"]))
            inputs = lr.get("inputs")
            if not inputs:
                no_inputs += 1
            elif item_hash and any(item_hash.get(k) not in (None, v) for k, v in inputs.items()):
                stale += 1
    return {"populated": bool(flow.get("populated")), "stories": len(stories), "scenarios": total,
            "runnable": runnable, "proseOnly": prose, "neverRun": never,
            "lastResult": dict(sorted(status.items())), "stale": stale if item_hash else None,
            "noInputs": no_inputs, "ranFirst": min(ran) if ran else None, "ranLast": max(ran) if ran else None}


# ── 8 · sessions (opt-in) ─────────────────────────────────────────────────────────

_TS = re.compile(r'"timestamp":"([0-9T:.\-]+Z?)"')
_CMD_TAG = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")
_ARGS_TAG = re.compile(r"<command-args>(.*?)</command-args>", re.S)
_TOOL_RUN = re.compile(r"([a-z_]+\.py)\b")
_TOUCH = re.compile(r"\btouch\s+[^\n;&|]*registry\.json")
_PW_INSTALL = re.compile(r"pip3?\s+install[^\n;&|]*playwright|playwright\s+install")


def sessions_dir(arg, project, given):
    if arg != "auto":
        d = os.path.abspath(os.path.expanduser(arg))
        return (d if os.path.isdir(d) else None), d
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    tried = None
    for p in (os.path.abspath(given), os.path.realpath(given), os.path.abspath(project), os.path.realpath(project)):
        d = os.path.join(base, "projects", re.sub(r"[^A-Za-z0-9]", "-", p))
        tried = tried or d
        if os.path.isdir(d):
            return d, d
    return None, tried


def _text_of(content):
    if isinstance(content, str):
        return content, False
    if not isinstance(content, list):
        return "", False
    tool = any(isinstance(x, dict) and x.get("type") == "tool_result" for x in content)
    return " ".join(x.get("text", "") for x in content if isinstance(x, dict) and x.get("type") == "text"), tool


def _scan_session(path, since, cmds, skills, tools, acc):
    seq = []                 # ("turn",) | ("run", name, source)
    first = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            # Substring prefilter before json.loads: a transcript is mostly tool output, and parsing
            # every line of 450 MB is the difference between one second and a minute. Both the
            # compact and the spaced JSON spellings are accepted.
            is_user = '"type":"user"' in line or '"type": "user"' in line
            is_tool = (('"type":"assistant"' in line or '"type": "assistant"' in line)
                       and any(k in line for k in ('"name":"Skill"', '"name":"Bash"',
                                                   '"name": "Skill"', '"name": "Bash"')))
            if not (is_user or is_tool):
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("isSidechain") or o.get("isMeta"):
                continue
            ts = str(o.get("timestamp") or "")
            if since and ts and ts[:10] < since:
                continue
            msg = o.get("message") or {}
            if o.get("type") == "user":
                text, tool = _text_of(msg.get("content"))
                if tool:
                    continue
                m = _CMD_TAG.search(text)
                if m:
                    name = m.group(1)
                    first = first or ts
                    if name.startswith("pb:"):
                        n = name[3:]
                        a = _ARGS_TAG.search(text)
                        acc["typed"][n] += 1
                        seq.append(("run", n, "typed"))
                        for f in _FLAG.findall(a.group(1) if a else ""):
                            acc["flags"][(n, f)] += 1
                    elif name == "compact":
                        acc["compactions"] += 1
                    else:
                        acc["otherCommands"][name] += 1
                    continue
                stripped = text.lstrip()
                if stripped.startswith("[Request interrupted"):
                    acc["interrupts"] += 1
                    continue
                if stripped.startswith(("<local-command", "This session is being continued", "<task-notification")):
                    continue
                if (o.get("origin") or {}).get("kind") in (None, "human") and stripped:
                    first = first or ts
                    seq.append(("turn",))
                    acc["turns"] += 1
            elif o.get("type") == "assistant":
                for item in msg.get("content") or []:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    inp = item.get("input") or {}
                    if item.get("name") == "Skill":
                        sk = str(inp.get("skill") or "")
                        if not sk.startswith("pb:"):
                            continue
                        n = sk[3:]
                        if n in cmds or n in RETIRED or n not in skills:
                            prev = seq[-1] if seq else None
                            if prev and prev[0] == "run" and prev[1] == n and prev[2] == "typed":
                                acc["merged"] += 1          # the model loading what the user typed
                            else:
                                seq.append(("run", n, "invoked"))
                            acc["invoked"][n] += 1
                            for f in _FLAG.findall(str(inp.get("args") or "")):
                                acc["flags"][(n, f)] += 1
                        else:
                            acc["skillLoads"][n] += 1
                    elif item.get("name") == "Bash":
                        c = str(inp.get("command") or "")
                        for t in set(_TOOL_RUN.findall(c)):
                            if t in tools:
                                acc["toolRuns"][t] += 1
                        acc["touchRegistry"] += len(_TOUCH.findall(c))
                        acc["playwrightInstalls"] += len(_PW_INSTALL.findall(c))
    return first, seq


def facts_sessions(arg, project, given, since):
    if not arg:
        return {"scanned": False, "reason": "not requested — pass --sessions"}
    d, tried = sessions_dir(arg, project, given)
    if not d:
        return {"scanned": False, "reason": "no transcript folder at %s — pass --sessions <dir>"
                % tried.replace(os.path.expanduser("~"), "~")}
    cmds, skills, tools = set(shipped_commands()), set(shipped_skills()), plugin_tools()
    acc = {"typed": collections.Counter(), "invoked": collections.Counter(), "flags": collections.Counter(),
           "skillLoads": collections.Counter(), "otherCommands": collections.Counter(),
           "toolRuns": collections.Counter(), "compactions": 0, "interrupts": 0, "turns": 0, "merged": 0,
           "touchRegistry": 0, "playwrightInstalls": 0}
    files = sorted(f for f in os.listdir(d) if f.endswith(".jsonl") and os.path.isfile(os.path.join(d, f)))
    weeks = collections.Counter()
    bigrams, trigrams = collections.Counter(), collections.Counter()
    gaps, runs_per = [], []
    active = 0
    for f in files:
        first, seq = _scan_session(os.path.join(d, f), since, cmds, skills, tools, acc)
        if not seq:
            continue
        active += 1
        if first:
            weeks[_week(first)] += 1
        runs = [e[1] for e in seq if e[0] == "run"]
        runs_per.append(len(runs))
        for a, b in zip(runs, runs[1:]):
            bigrams["%s → %s" % (a, b)] += 1
        for a, b, c in zip(runs, runs[1:], runs[2:]):
            trigrams["%s → %s → %s" % (a, b, c)] += 1
        turns, seen_build = 0, False
        for e in seq:
            if e[0] == "turn":
                turns += 1
            elif e[1] == "build":
                if seen_build:
                    gaps.append(turns)
                seen_build, turns = True, 0

    def status(n):
        return ("shipped" if n in cmds else "retired" if n in RETIRED
                else "skill named as a command" if n in skills else "unknown")

    names = sorted(set(acc["typed"]) | set(acc["invoked"]))
    runs_sorted = sorted(runs_per)
    gaps_sorted = sorted(gaps)
    return {
        "scanned": True,
        "dir": d.replace(os.path.expanduser("~"), "~"),
        "transcripts": len(files),
        "activeSessions": active,
        "perWeek": dict(sorted(weeks.items())),
        "commands": sorted(({"name": n, "typed": acc["typed"][n], "invoked": acc["invoked"][n],
                             "status": status(n)} for n in names),
                           key=lambda r: (-(r["typed"] + r["invoked"]), r["name"])),
        "mergedTypedInvoked": acc["merged"],
        "flags": [{"command": c, "flag": fl, "count": v,
                   "documented": (fl in documented_flags(c)) if c in cmds else None}
                  for (c, fl), v in _ranked(acc["flags"], 999)],
        "skillLoads": [{"name": k, "count": v} for k, v in _ranked(acc["skillLoads"], 999)],
        "bigrams": [{"sequence": k, "count": v} for k, v in _ranked(bigrams, 10)],
        "trigrams": [{"sequence": k, "count": v} for k, v in _ranked(trigrams, 10)],
        "runsPerSession": {"max": runs_sorted[-1] if runs_sorted else 0,
                           "median": runs_sorted[len(runs_sorted) // 2] if runs_sorted else 0},
        "turnsBetweenBuilds": {"pairs": len(gaps),
                               "mean": round(sum(gaps) / float(len(gaps)), 1) if gaps else None,
                               "median": gaps_sorted[len(gaps_sorted) // 2] if gaps else None},
        "humanTurns": acc["turns"],
        "compactions": acc["compactions"],
        "interrupts": acc["interrupts"],
        "otherCommands": [{"name": k, "count": v} for k, v in _ranked(acc["otherCommands"], 10)],
        "toolRuns": [{"tool": k, "count": v} for k, v in _ranked(acc["toolRuns"], 999)],
        "touchRegistry": acc["touchRegistry"],
        "playwrightInstalls": acc["playwrightInstalls"],
    }


# ── 9 · hygiene ───────────────────────────────────────────────────────────────────

def _comments(src):
    """(header_comment_text, all_comment_text) — quote-aware, regex-tokenized. A heuristic: a regex
    literal containing a quote can confuse it, which is acceptable for counting dates."""
    header, allc, pos, in_header = [], [], 0, True
    for m in _JS_TOKEN.finditer(src):
        tok = m.group(0)
        if src[pos:m.start()].strip():
            in_header = False
        pos = m.end()
        if tok.startswith(("//", "/*")):
            allc.append(tok)
            if in_header:
                header.append(tok)
        else:
            in_header = False
    return "\n".join(header), "\n".join(allc)


def facts_hygiene(project):
    files = _walk(os.path.join(project, "render"), (".js",), skip={"_candidates"})
    files += _walk(os.path.join(project, "runtime"), (".js",))
    candidates, layered = [], []
    for p in files:
        src = _read(p) or ""
        head, allc = _comments(src)
        names = sorted(set(_HEADER_NAMES.findall(head)))
        if names:
            candidates.append({"file": _rel(project, p), "names": names})
        dates = _DATE_ANY.findall(allc)
        if len(dates) >= 3:
            layered.append({"file": _rel(project, p), "dates": len(dates), "distinct": len(set(dates)),
                            "first": min(dates), "last": max(dates)})
    layered.sort(key=lambda r: (-r["dates"], r["file"]))
    return {"bodiesScanned": len(files), "candidateHeaders": candidates,
            "datedLayers": layered[:TOP_ROWS], "datedLayerFiles": len(layered)}


# ── 10 · workarounds ──────────────────────────────────────────────────────────────

def facts_workarounds(project, shape, decisions):
    root_entries = sorted(os.listdir(project))
    scripts = []
    for d in SCRIPT_DIRS:
        p = os.path.join(project, d)
        if os.path.isdir(p):
            scripts.append({"dir": d.replace(os.sep, "/") + "/", "files": _tree(p)[1]})
    bak = [n for n in root_entries if os.path.isfile(os.path.join(project, n)) and _BAK.search(n)]
    zero = [n for n in root_entries if os.path.isfile(os.path.join(project, n))
            and os.path.getsize(os.path.join(project, n)) == 0]
    outside = [n + ("/" if os.path.isdir(os.path.join(project, n)) else "") for n in root_entries
               if n not in ROOT_LAYOUT and n not in bak and n not in zero
               and n.rstrip("/") not in {s["dir"].rstrip("/") for s in scripts}]
    vocab = {v["term"]: v["entries"] for v in decisions["vocabulary"]}
    hand = [m for m in shape["memory"] if not m["owner"]]
    return {
        "handWritten": [{"name": m["name"], "bytes": m["bytes"]} for m in hand],
        "scriptDirs": scripts,
        "rootBackupCopies": bak,
        "zeroByteFiles": [_short(n, 60) for n in zero],
        "outsideLayout": outside,
        "decisionRituals": {k: vocab.get(k, 0) for k in ("workaround", "manual", "hand-edit / by hand", "touch registry")},
    }


# ── assemble ──────────────────────────────────────────────────────────────────────

def resolve_project(given):
    p = os.path.abspath(given)
    if os.path.isfile(os.path.join(p, "registry.json")):
        return p, None
    inner = os.path.join(p, ".prototype")
    if os.path.isfile(os.path.join(inner, "registry.json")):
        return inner, "registry found under .prototype/ (adopt-in-place) — reported from there"
    return None, None


def gather(given, since=None, sessions=None, today=None):
    project, note = resolve_project(given)
    if not project:
        return None
    reg_path = os.path.join(project, "registry.json")
    reg, reg_err = {}, None
    try:
        with open(reg_path, encoding="utf-8") as f:
            reg = json.load(f)
        if not isinstance(reg, dict):
            reg, reg_err = {}, "registry.json is not a JSON object"
    except ValueError as exc:
        reg_err = "invalid JSON: %s" % _short(exc, 120)
    shape = facts_shape(project, reg, reg_err)
    decisions, entries = facts_decisions(project, since)
    perf = facts_performance(project, reg, reg_path) if not reg_err else {
        "render": {"measured": False, "error": reg_err}, "lint": {"measured": False, "error": reg_err},
        "registryBytes": os.path.getsize(reg_path), "registryByKey": [], "prototypeHtmlBytes": None}
    item_hash = perf["render"].pop("_itemHash", None)
    facts = collections.OrderedDict()
    facts["meta"] = {
        "tool": "pb/tools/report.py",
        "pluginVersion": plugin_version(),
        "date": today or datetime.date.today().isoformat(),
        "project": project,
        "projectNote": note,
        "since": since,
        "sessionsScanned": False,
    }
    facts["shape"] = shape
    facts["decisions"] = decisions
    facts["mentions"] = facts_mentions(project)
    facts["explore"] = facts_explore(project, since, entries)
    facts["backups"] = facts_backups(project, since)
    facts["performance"] = perf
    facts["tests"] = facts_tests(reg, item_hash)
    facts["sessions"] = facts_sessions(sessions, project, given, since)
    facts["meta"]["sessionsScanned"] = facts["sessions"].get("scanned", False)
    facts["hygiene"] = facts_hygiene(project)
    facts["workarounds"] = facts_workarounds(project, shape, decisions)
    return facts


# ── markdown ──────────────────────────────────────────────────────────────────────

def _cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def _table(out, headers, rows):
    if not rows:
        out.append("(none)")
        out.append("")
        return
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "---|" * len(headers))
    for r in rows:
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    out.append("")


def _evidence(out, items, indent=""):
    for e in items:
        out.append("%s- `%s` — %s%s" % (indent, e["where"], (e["date"] + " · ") if e.get("date") and e["date"] not in e["heading"] else "",
                                         _cell(e["heading"]) or "(no heading)"))


def _pct(a, b):
    return "%d%%" % round(100.0 * a / b) if b else "—"


def md_shape(f, out):
    s = f["shape"]
    cur = s["currentSchema"]
    sv = s["schemaVersion"]
    gap = ("current" if sv == cur else "behind by %d" % (cur - sv) if isinstance(sv, int) and isinstance(cur, int) and sv < cur
           else "ahead of the plugin" if isinstance(sv, int) and isinstance(cur, int) and sv > cur else "—")
    rk = s["renderByKind"]
    sc = s["sidecars"]
    _table(out, ["Fact", "Value"], [
        ["Registry", "`registry.json` · %s%s" % (_kb(s["registryBytes"]), (" · **%s**" % s["registryError"]) if s["registryError"] else "")],
        ["Schema", "%s · plugin `CURRENT_SCHEMA` %s (%s)" % ("absent (treated as 2)" if s["schemaAbsent"] else sv, cur, gap)],
        ["DS source (`meta.dsSource.type`)", s["dsSource"] or "none"],
        ["Components · local · screens · tokens", "%d · %d · %d · %d" % (s["components"], s["localComponents"], s["screens"], s["tokens"])],
        ["Runtime modules (`registry.runtime[]`)", s["runtimeModules"]],
        ["Render bodies (`render/**`, excluding `_candidates`)", "%d (%s)" % (s["renderBodies"], " · ".join("%s %d" % kv for kv in rk.items()) or "—")],
        ["Sidecar trees", " · ".join("%s/ %s" % (k, "%d files" % v if v is not None else "absent") for k, v in sc.items())],
    ])
    out.append("### memory/")
    out.append("")
    _table(out, ["Entry", "Size", "Files", "Owner"],
           [["`%s`" % m["name"], _kb(m["bytes"]), m["files"], m["owner"] or "**none — hand-written**"] for m in s["memory"]])
    hw = s["handWritten"]
    out.append("**Hand-written context files** (in `memory/`, owned by no command or template): %s" %
               ("%d — %s" % (len(hw), ", ".join("`%s`" % n for n in hw)) if hw else "(none)"))
    out.append("")


def md_decisions(f, out):
    d = f["decisions"]
    if not d["files"]:
        out.append("(none) — no `memory/decisions*.md`")
        out.append("")
        return
    alt, rule = d["alternatives"], d["rule"]
    w = d["inWindow"]
    _table(out, ["Fact", "Value"], [
        ["Files", " · ".join("`%s` %s" % (x["file"], _kb(x["bytes"])) for x in d["files"])],
        ["Size vs the rotation threshold", "%s of %s (%s)%s" % (_kb(d["totalBytes"]), _kb(d["thresholdBytes"]), _pct(d["totalBytes"], d["thresholdBytes"]),
                                                           "" if d["rotatedSiblings"] else " · no rotated sibling exists")],
        ["Entries", "%d · undated %d · in window %d" % (d["entries"], d["undated"], w)],
        ["File order vs date order", "%d of %d adjacent dated pairs break newest-first" % (d["dateOrder"]["inversions"], d["dateOrder"]["adjacentPairs"])],
        ["Entries using back-and-forth vocabulary", "%d (%s of the window)" % (d["backAndForthEntries"], _pct(d["backAndForthEntries"], w))],
        ["`Alternatives:`", "filled %d · empty or — %d · absent %d" % (alt.get("filled", 0), alt.get("empty", 0), alt.get("absent", 0))],
        ["`Rule:`", "filled %d · empty or — %d · absent %d" % (rule.get("filled", 0), rule.get("empty", 0), rule.get("absent", 0))],
    ])
    if d["undatedEvidence"]:
        out.append("Undated entries (never rotated, never windowed):")
        _evidence(out, d["undatedEvidence"])
        out.append("")
    out.append("### Entries per week")
    out.append("")
    _table(out, ["ISO week", "Entries"], [[k, v] for k, v in d["perWeek"].items()])
    out.append("### Back-and-forth vocabulary")
    out.append("")
    hit = [v for v in d["vocabulary"] if v["entries"]]
    _table(out, ["Term", "Entries", "Hits"], [[v["term"], v["entries"], v["hits"]] for v in sorted(hit, key=lambda v: (-v["entries"], v["term"]))])
    for v in sorted(hit, key=lambda v: (-v["entries"], v["term"])):
        out.append("**%s**" % v["term"])
        _evidence(out, v["evidence"])
        out.append("")
    if d["alternativesMissingEvidence"]:
        out.append("**`Alternatives:` present but empty**")
        _evidence(out, d["alternativesMissingEvidence"])
        out.append("")
    out.append("### Recurring topics (first three significant heading words, seen 3+ times)")
    out.append("")
    _topics(out, d["recurringTopics"])
    out.append("### Recurring subjects (heading text before the first colon, seen 3+ times)")
    out.append("")
    _topics(out, d["recurringSubjects"])


def _topics(out, rows):
    if not rows:
        out.append("(none)")
        out.append("")
        return
    for r in rows:
        out.append("- **%s** ×%d (%s → %s)" % (_cell(r["topic"]), r["entries"], r["first"] or "undated", r["last"] or "undated"))
        _evidence(out, r["evidence"], indent="  ")
    out.append("")


def md_mentions(f, out):
    m = f["mentions"]
    out.append("Scanned %d markdown files under `memory/` (`backups/`, `.pb-backups/` and `reports/` excluded — copies and this tool's own output)." % m["scannedFiles"])
    out.append("")
    out.append("### Commands")
    out.append("")
    _table(out, ["Name", "Mentions", "Status"],
           [["`/pb:%s`" % c["name"], c["mentions"],
             c["status"] if c["status"] == "shipped" else "**%s**%s" % (c["status"], (" → `%s`" % c["replacement"]) if c["replacement"] else "")]
            for c in m["commands"]])
    for c in m["commands"]:
        if c["evidence"]:
            out.append("**`/pb:%s`** (%s)" % (c["name"], c["status"]))
            _evidence(out, c["evidence"])
            out.append("")
    out.append("### Flags on commands")
    out.append("")
    _table(out, ["Flag", "Mentions", "Documented in the command file"],
           [["`/pb:%s %s`" % (x["command"], x["flag"]), x["mentions"], "yes" if x["documented"] else "**no**"] for x in m["flags"]])
    for x in m["flags"]:
        if x["evidence"]:
            out.append("**`/pb:%s %s`** (not documented)" % (x["command"], x["flag"]))
            _evidence(out, x["evidence"])
            out.append("")
    out.append("### Skills")
    out.append("")
    _table(out, ["Skill", "Mentions", "Shipped"], [["`%s`" % s["name"], s["mentions"], "yes" if s["shipped"] else "**no**"] for s in m["skills"]])
    t = m["tasks"]
    if not t["skillFields"]:
        out.append("`memory/tasks.md` skill column: (none) — no `skill:` field found")
    else:
        out.append("`memory/tasks.md` skill column: %d tasks · %d with no skill · assigned %s" % (
            t["skillFields"], t["noSkill"], ", ".join("`%s` ×%d" % kv for kv in t["assigned"].items()) or "(none)"))
        out.append("")
        out.append("- Shipped skills never assigned: %s" % (", ".join("`%s`" % s for s in t["neverAssigned"]) or "(none)"))
        out.append("- Assigned but not shipped: %s" % (", ".join("`%s`" % s for s in t["assignedNotShipped"]) or "(none)"))
    out.append("")
    out.append("### Degrade and gate notices")
    out.append("")
    _table(out, ["Notice", "Lines"], [[n["notice"], n["lines"]] for n in m["notices"]])
    for n in m["notices"]:
        if n["evidence"]:
            out.append("**%s**" % n["notice"])
            _evidence(out, n["evidence"])
            out.append("")
    out.append("### Command chains (one line naming 3+ distinct shipped commands)")
    out.append("")
    if m["chains"]["lines"]:
        out.append("%d lines" % m["chains"]["lines"])
        _evidence(out, m["chains"]["evidence"])
    else:
        out.append("(none)")
    out.append("")


def md_explore(f, out):
    e = f["explore"]
    if not e["rounds"] and not e["candidates"] and not e["decisionsNamingExplore"]:
        out.append("(none) — no manifests under `memory/explore/`, no `render/_candidates/`, no decisions entry naming explore")
        out.append("")
        return
    _table(out, ["Fact", "Value"], [
        ["Rounds (manifests)", "%d (%s)" % (len(e["rounds"]), " · ".join("%s %d" % kv for kv in e["byStatus"].items()) or "—")],
        ["Options per round", e["optionsPerRound"] if e["optionsPerRound"] is not None else "—"],
        ["Unscored cells", "%d of %d · rounds with no score at all: %d" % (e["unscored"], e["cells"], e["unscoredRounds"])],
        ["`render/_candidates/`", ("%d target(s) · orphaned (no open manifest): %s" % (len(e["candidates"]), ", ".join("`%s`" % c for c in e["orphanedCandidates"]) or "none")) if e["candidates"] else "empty"],
        ["Decisions entries naming explore", "%d · of which name a rejection %d" % (e["decisionsNamingExplore"], e["decisionsNamingRejection"])],
    ])
    out.append("Per round (`memory/explore/*.json` and `_closed/`):")
    out.append("")
    _table(out,["Target", "Mode", "Status", "Options", "Scored", "Best average", "Pick", "Created"],
           [[r.get("target") or r["file"], r.get("mode", "—"), r.get("status"), r.get("options", "—"),
             "%s/%s" % (r.get("scored", 0), r.get("cells", 0)),
             (lambda a: ("%s %.2f" % max(a.items(), key=lambda kv: (kv[1], kv[0]))) if a else "—")(r.get("averages") or {}),
             r.get("pick") or "—", str(r.get("createdAt") or "—")[:10]] for r in e["rounds"]])
    if e["rejectionEvidence"]:
        out.append("Decisions entries naming explore and a rejection:")
        _evidence(out, e["rejectionEvidence"])
        out.append("")


def md_backups(f, out):
    b = f["backups"]
    if not b["snapshots"] and not any(v for v in b["pbBackups"].values()):
        out.append("(none)")
        out.append("")
        return
    _table(out, ["Fact", "Value"], [
        ["`memory/backups/`", "%d snapshots · %s" % (b["snapshots"], _kb(b["bytes"]))],
        ["`pre-*` snapshots (one per risky write)", ("%d over %d day(s), %s → %s" % (len(b["pre"]), b["preSpanDays"], b["preFirst"], b["preLast"])) if b["pre"] else "0"],
        ["Busiest days", " · ".join("%s: %d" % (x["date"], x["snapshots"]) for x in b["busiestDays"]) or "—"],
        ["`.pb-backups/`", " · ".join("`%s` %s" % (k, "%d files" % v if v is not None else "absent") for k, v in b["pbBackups"].items())],
    ])
    if b["pre"]:
        out.append("`pre-*` names: " + ", ".join("`%s`" % n for n in b["pre"]))
        out.append("")
    if b["other"]:
        out.append("Other snapshots: " + ", ".join("`%s`" % n for n in b["other"]))
        out.append("")


def md_performance(f, out):
    p = f["performance"]
    r, lint = p["render"], p["lint"]
    out.append("> Timings are **measured** on this machine during this run and vary between runs; every other number is a count. Budgets: DESIGN.md constraint 5.")
    out.append("")
    if r.get("measured"):
        _table(out, ["Step", "ms (measured)", "Budget"], [
            ["load_bodies", r["loadBodiesMs"], ""], ["load_specs", r["loadSpecsMs"], ""],
            ["load_logic", r["loadLogicMs"], ""], ["load_runtime", r["loadRuntimeMs"], ""],
            ["build_html (best of 3)", r["buildHtmlMs"], "%.0f%s" % (BUDGET_BUILD_MS, " **over**" if r["buildHtmlMs"] > BUDGET_BUILD_MS else "")],
            ["pipeline", r["pipelineMs"], "%.0f%s" % (BUDGET_PIPELINE_MS, " **over**" if r["pipelineMs"] > BUDGET_PIPELINE_MS else "")],
        ])
    else:
        out.append("Render: not measured (%s)" % r.get("error", "unknown"))
        out.append("")
    rows = []
    if r.get("measured"):
        rows.append(["Rendered prototype (in memory)", _kb(r["htmlBytes"])])
        rows.append(["Logic graph", "skipped (load_logic returned nothing)" if r["logicSkipped"] else "%d items · %d handlers" % (r["logicItems"], r["logicHandlers"])])
    rows.append(["`prototype.html` on disk", _kb(p["prototypeHtmlBytes"]) if p["prototypeHtmlBytes"] is not None else "absent"])
    rows.append(["`registry.json` by top-level key", " · ".join("%s %s" % (x["key"], _pct(x["bytes"], p["registryBytes"])) for x in p["registryByKey"]) or "—"])
    if lint.get("measured"):
        rows.append(["`lint_registry.py --strict`", "%d errors · %d warnings · exit %d (%.2f s measured)" % (lint["errors"], lint["warnings"], lint["exit"], lint["seconds"])])
    else:
        rows.append(["`lint_registry.py --strict`", "not measured (%s)" % lint.get("error", "unknown")])
    _table(out, ["Fact", "Value"], rows)
    if lint.get("measured") and lint["codes"]:
        out.append("Lint findings by code:")
        out.append("")
        _table(out, ["Code", "Severity", "Count"], [[c["code"], c["severity"], c["count"]] for c in lint["codes"]])


def md_tests(f, out):
    t = f["tests"]
    if not t["scenarios"]:
        out.append("(none) — no `flow.stories[].scenarios[]`")
        out.append("")
        return
    lr = t["lastResult"]
    _table(out, ["Fact", "Value"], [
        ["Stories · scenarios", "%d · %d" % (t["stories"], t["scenarios"])],
        ["Runnable (`test{}`) · prose only", "%d · %d" % (t["runnable"], t["proseOnly"])],
        ["Last result", "%s · never run %d" % (" · ".join("%s %d" % kv for kv in lr.items()) or "none recorded", t["neverRun"])],
        ["Stale (an input digest changed since the run)", "not computed (no logic graph)" if t["stale"] is None else t["stale"]],
        ["Results with no `inputs` (undated evidence)", t["noInputs"]],
        ["`ranAt` range", "%s → %s" % (t["ranFirst"], t["ranLast"]) if t["ranFirst"] else "—"],
    ])


def md_sessions(f, out):
    s = f["sessions"]
    if not s.get("scanned"):
        out.append("(none) — %s" % s["reason"])
        out.append("")
        return
    out.append("Scanned `%s`: %d transcripts, %d with activity in the window. Counts and sequences only; no message text is quoted." % (s["dir"], s["transcripts"], s["activeSessions"]))
    out.append("")
    tb = s["turnsBetweenBuilds"]
    _table(out, ["Fact", "Value"], [
        ["Sessions per ISO week", " · ".join("%s: %d" % kv for kv in s["perWeek"].items()) or "—"],
        ["Human turns", s["humanTurns"]],
        ["/pb:* runs per session", "max %d · median %d" % (s["runsPerSession"]["max"], s["runsPerSession"]["median"])],
        ["Human turns between consecutive `/pb:build` runs", ("mean %.1f · median %d over %d pairs" % (tb["mean"], tb["median"], tb["pairs"])) if tb["pairs"] else "(none)"],
        ["Context compactions (`/compact`)", s["compactions"]],
        ["Interrupted turns", s["interrupts"]],
        ["`touch … registry.json` in Bash", s["touchRegistry"]],
        ["Playwright installs in Bash", s["playwrightInstalls"]],
        ["Typed command immediately loaded again by the model", s["mergedTypedInvoked"]],
    ])
    _table(out, ["Command", "Typed", "Invoked by the model", "Status"],
           [["`/pb:%s`" % c["name"], c["typed"], c["invoked"], c["status"] if c["status"] == "shipped" else "**%s**" % c["status"]] for c in s["commands"]])
    out.append("Most common run sequences inside one session (three runs, then two):")
    out.append("")
    _table(out, ["Sequence", "Count"], [[x["sequence"], x["count"]] for x in (s["trigrams"][:5] + s["bigrams"])])
    out.append("Flag names passed to a command (names only):")
    out.append("")
    _table(out, ["Flag passed", "Count", "Documented"],
           [["`/pb:%s %s`" % (x["command"], x["flag"]), x["count"], "—" if x["documented"] is None else ("yes" if x["documented"] else "**no**")] for x in s["flags"]])
    out.append("Skill loads: " + (", ".join("`%s` ×%d" % (x["name"], x["count"]) for x in s["skillLoads"]) or "(none)"))
    out.append("")
    out.append("Plugin tools run through Bash: " + (", ".join("`%s` ×%d" % (x["tool"], x["count"]) for x in s["toolRuns"]) or "(none)"))
    out.append("")
    if s["otherCommands"]:
        out.append("Other slash commands: " + ", ".join("`/%s` ×%d" % (x["name"], x["count"]) for x in s["otherCommands"]))
        out.append("")


def md_hygiene(f, out):
    h = f["hygiene"]
    out.append("Scanned %d body files (`render/**`, `runtime/*.js`; comments only)." % h["bodiesScanned"])
    out.append("")
    out.append("### Candidate headers left in bodies")
    out.append("")
    _table(out, ["File", "Names in the header comment"], [["`%s`" % c["file"], ", ".join(c["names"])] for c in h["candidateHeaders"]])
    out.append("### Comment-dated layers (3+ dates in one body's comments)")
    out.append("")
    if h["datedLayerFiles"] > len(h["datedLayers"]):
        out.append("%d files; the %d with the most dates:" % (h["datedLayerFiles"], len(h["datedLayers"])))
        out.append("")
    _table(out, ["File", "Dates", "Distinct", "Span"], [["`%s`" % r["file"], r["dates"], r["distinct"], "%s → %s" % (r["first"], r["last"])] for r in h["datedLayers"]])


def md_workarounds(f, out):
    w = f["workarounds"]
    r = w["decisionRituals"]
    _table(out, ["Fact", "Value"], [
        ["Hand-written context files in `memory/`", ", ".join("`%s` (%s)" % (x["name"], _kb(x["bytes"])) for x in w["handWritten"]) or "(none)"],
        ["Project-own script folders", ", ".join("`%s` %d files" % (x["dir"], x["files"]) for x in w["scriptDirs"]) or "(none)"],
        ["Backup copies at the root", ", ".join("`%s`" % n for n in w["rootBackupCopies"]) or "(none)"],
        ["Zero-byte files at the root", ", ".join("`%s`" % n for n in w["zeroByteFiles"]) or "(none)"],
        ["Root entries outside the pb layout (may be the project's own assets)", ", ".join("`%s`" % n for n in w["outsideLayout"][:20]) + (" …" if len(w["outsideLayout"]) > 20 else "") or "(none)"],
        ["Decisions entries naming a ritual", " · ".join("%s %d" % kv for kv in r.items())],
    ])


RENDER = {"shape": md_shape, "decisions": md_decisions, "mentions": md_mentions, "explore": md_explore,
          "backups": md_backups, "performance": md_performance, "tests": md_tests,
          "sessions": md_sessions, "hygiene": md_hygiene, "workarounds": md_workarounds}


def to_markdown(facts):
    m = facts["meta"]
    out = ["# pb report — %s — %s" % (facts["shape"]["name"], m["date"]), ""]
    out.append("> Facts gathered by `%s` (pb %s) from `%s`, read-only. Audience: the Product Builder maintainer."
               % (m["tool"], m["pluginVersion"], m["project"]))
    out.append("> Window: %s. Sessions: %s." % (
        ("dated facts since %s" % m["since"]) if m["since"] else "all history",
        "scanned with `--sessions` — counts and sequences only, no message text" if m["sessionsScanned"] else "not scanned"))
    if m["projectNote"]:
        out.append("> %s." % m["projectNote"])
    out.append("> Every number is a deterministic count over the files except the timings in §6, which are measured.")
    out.append("")
    for key, title in SECTIONS:
        out.append("## " + title)
        out.append("")
        RENDER[key](facts, out)
    out.append("<!-- facts end — /pb:report §2 appends `## Reading` and `## Proposals for the next pb release` below -->")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Gather the facts behind /pb:report — read-only on the project.")
    ap.add_argument("--project", default=".", help="project folder holding registry.json (default .)")
    ap.add_argument("--out", help="markdown file to write (default memory/reports/pb-report-<date>.md under --project)")
    ap.add_argument("--json", action="store_true", help="also print the facts as JSON on stdout")
    ap.add_argument("--sessions", nargs="?", const="auto", default=None, metavar="DIR",
                    help="scan Claude Code session transcripts (counts and sequences only)")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="window the dated facts")
    args = ap.parse_args(argv)
    if args.since:
        try:
            datetime.date.fromisoformat(args.since)
        except ValueError:
            ap.error("--since takes YYYY-MM-DD")
    t0 = time.perf_counter()
    facts = gather(args.project, since=args.since, sessions=args.sessions)
    if facts is None:
        print("report: no registry.json in %s" % os.path.abspath(args.project), file=sys.stderr)
        return 2
    project = facts["meta"]["project"]
    out = os.path.abspath(args.out) if args.out else os.path.join(
        project, "memory", "reports", "pb-report-%s.md" % facts["meta"]["date"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    existed = os.path.exists(out)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(to_markdown(facts))
    os.replace(tmp, out)
    elapsed = time.perf_counter() - t0
    if args.json:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        print("report: %s %s (%.1f s measured)" % ("overwrote" if existed else "wrote", out, elapsed), file=sys.stderr)
    else:
        d = facts["decisions"]
        print("✓ report: %s %s — %d decisions entries, %d hand-written memory files, %d backups (%.1f s measured)"
              % ("overwrote" if existed else "wrote", out, d["entries"], len(facts["shape"]["handWritten"]),
                 facts["backups"]["snapshots"], elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
