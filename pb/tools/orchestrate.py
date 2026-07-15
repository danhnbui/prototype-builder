#!/usr/bin/env python3
"""
pb-orchestrate — turn a per-tab task breakdown into an ordered execution plan (waves).

Reads memory/tasks.md (authored by /pb:plan). Each task carries the fields /pb:plan now
writes: `acceptance:`, `skill:`, and the newer `agent:` (one of the 8 pb-* agents), `deps:`
(comma-separated task ids, or "none"), and `slice:` (screen|component|logic|tokens|flow|erd|meta).

It topologically sorts the tasks into WAVES — a wave is every task whose dependencies are
already satisfied by earlier waves, so independent tasks share a wave and can run in parallel.

Contract errors (exit 2): a dependency cycle, an `agent:` value outside the 8-agent roster,
or a `deps:` entry referencing an unknown task id. Missing new fields (a tasks.md that predates
the agent/deps/slice contract) degrade to a WARN — deps are treated as none and the agent is
inferred from `skill:` when possible.

Severity → exit code (mirrors check.py):
  0  clean (no findings)
  1  warnings only
  2  at least one error

Each finding prints as:  <SEVERITY> [<CODE>] <where>: <msg>   (to stdout in text mode, stderr
under --json so the JSON on stdout stays machine-parseable).

Usage:  python3 orchestrate.py <memory/tasks.md> [--json]
"""
import json
import os
import re
import sys

# The 8-agent roster (S4 contract). An `agent:` value outside this set is an error.
AGENT_ROSTER = {
    "pb-clarifier", "pb-planner", "pb-builder", "pb-design-system",
    "pb-flow", "pb-data", "pb-tester", "pb-reviewer",
}
# The registry slices a task may touch.
SLICE_ENUM = {"screen", "component", "logic", "tokens", "flow", "erd", "meta"}

# Best-effort skill → agent inference for a legacy tasks.md that predates `agent:`.
SKILL_TO_AGENT = {
    "think-clarify": "pb-clarifier",
    "think-critique-prd": "pb-clarifier",
    "ref-prd": "pb-clarifier",
    "agent-orchestrate-tasks": "pb-planner",
    "ref-blueprint": "pb-planner",
    "think-layout": "pb-builder",
    "think-logic": "pb-builder",
    "craft-connect-flow": "pb-flow",
    "sync-flow": "pb-flow",
    "sync-erd": "pb-data",
    "design-component-build": "pb-design-system",
    "build-check-design-system": "pb-design-system",
    "figma-use": "pb-design-system",
    "build-figma-handoff": "pb-design-system",
}

# Canonical field name for the aliases an author might write.
FIELD_ALIASES = {
    "acceptance": "acceptance", "accept": "acceptance",
    "skill": "skill", "skills": "skill",
    "agent": "agent", "agents": "agent", "owner": "agent",
    "deps": "deps", "dep": "deps", "dependencies": "deps",
    "depends": "deps", "depends-on": "deps", "depends on": "deps",
    "slice": "slice", "slices": "slice",
    "id": "id",
}

_HEADING = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*\S)\s*$")
# key: value  — tolerates a leading list marker, **bold** wrapping, and : or = separators.
_FIELD = re.compile(
    r"^\s*(?:[-*+]\s+)?\**\s*([A-Za-z][\w .-]*?)\s*\**\s*[:=]\s*(.*)$")

ERROR, WARN = "ERROR", "WARN"


class Finding:
    __slots__ = ("severity", "code", "where", "msg")

    def __init__(self, severity, code, where, msg):
        self.severity = severity
        self.code = code
        self.where = where
        self.msg = msg

    def line(self):
        return f"{self.severity} [{self.code}] {self.where}: {self.msg}"


class Task:
    __slots__ = ("id", "title", "agent", "deps", "slice", "skill", "order")

    def __init__(self, order):
        self.order = order
        self.id = None
        self.title = ""
        self.agent = None
        self.deps = []
        self.slice = None
        self.skill = None


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def _strip_title(text):
    """Drop leading markdown emphasis / backticks / trailing punctuation from a heading."""
    t = text.strip().strip("*`").strip()
    return t


_TITLE_SEP = re.compile(r"\s+[—–]\s+|\s+-\s+|:\s+")


def _id_basis(title):
    """The 'name' portion of a 'Name — description' title (used to derive a compact id)."""
    return _TITLE_SEP.split(title, 1)[0].strip() if title else title


def _label_from_title(title):
    """If a heading begins with a short id-like token (e.g. 'T1', 'T1.2', 'P3-2', '1'),
    return that token as the id; else None (caller slugifies the whole title)."""
    if not title:
        return None
    first = title.split()[0].rstrip(".:)—-")
    if re.fullmatch(r"[A-Za-z]*\d[\w.\-]*", first) and any(ch.isdigit() for ch in first):
        return first
    return None


def _field(line):
    """Return (canonical_key, value) if the line is a recognized `key: value`, else None."""
    m = _FIELD.match(line)
    if not m:
        return None
    key = re.sub(r"\s+", " ", m.group(1).strip().lower())
    canon = FIELD_ALIASES.get(key) or FIELD_ALIASES.get(key.replace(" ", "-"))
    if not canon:
        return None
    return canon, m.group(2).strip()


def parse_tasks(text):
    """Parse tasks.md into a list[Task] plus parse-level findings.

    A task begins at a heading or a non-field bullet ("title"); `key: value` lines attach to
    the current task. A candidate is kept only if it carried at least one recognized field, so
    tab-group headings (Prototype / UX Design / …) with no fields are naturally skipped.
    """
    findings = []
    tasks = []
    cur = None          # the Task currently accumulating fields
    cur_has_field = False
    order = [0]

    def flush():
        if cur is not None and cur_has_field:
            tasks.append(cur)

    def start(title):
        nonlocal cur, cur_has_field
        flush()
        order[0] += 1
        cur = Task(order[0])
        cur.title = title
        cur_has_field = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        fld = _field(line)
        # A field line attaches to the current task (start an anonymous one if none yet).
        if fld is not None:
            if cur is None:
                start("")
            key, val = fld
            cur_has_field = True
            if key == "id":
                cur.id = val.strip().strip("`").strip() or cur.id
            elif key == "agent":
                cur.agent = (val.split()[0].strip("`").strip().lower() if val.strip() else None)
            elif key == "skill":
                cur.skill = (val.split()[0].strip("`,").strip() if val.strip() else None)
            elif key == "slice":
                cur.slice = (val.split()[0].strip("`").strip().lower() if val.strip() else None)
            elif key == "deps":
                cur.deps = _parse_deps(val)
            continue
        # Otherwise, a heading or a non-field bullet starts a new task candidate.
        mh = _HEADING.match(line)
        if mh:
            start(_strip_title(mh.group(2)))
            continue
        mb = _BULLET.match(line)
        if mb:
            start(_strip_title(mb.group(2)))
            continue
        # plain prose — ignore
    flush()

    # Resolve ids (explicit id: > leading title token > slug of title > task-N) and dedupe.
    seen = {}
    for t in tasks:
        if not t.id:
            t.id = (_label_from_title(t.title) or slugify(_id_basis(t.title))
                    or slugify(t.title) or f"task-{t.order}")
        if t.id in seen:
            findings.append(Finding(
                ERROR, "O-DUPID", f"task {t.id!r}",
                f"duplicate task id (also earlier task) — ids must be unique so deps resolve"))
        else:
            seen[t.id] = t
    return tasks, findings


def _parse_deps(val):
    """'none' / empty -> []; else split on commas/semicolons into stripped id tokens."""
    v = val.strip().strip("`").strip()
    if not v or v.lower() in ("none", "-", "n/a", "[]"):
        return []
    return [d.strip().strip("`").strip() for d in re.split(r"[,;]", v) if d.strip()]


def validate(tasks):
    """Resolve deps against known ids, check the agent roster + slice enum, infer/degrade
    missing new fields. Returns findings; mutates task.deps to resolved ids, task.agent."""
    findings = []
    by_id = {t.id: t for t in tasks}
    lower_index = {t.id.lower(): t.id for t in tasks}
    # Fallback index so a dep written as the task's human title (not its id) still resolves.
    alias_index = {}
    for t in tasks:
        for key in (slugify(t.title), slugify(_id_basis(t.title))):
            if key:
                alias_index.setdefault(key, t.id)

    for t in tasks:
        where = f"task {t.id!r}"

        # --- new-field presence: WARN once when a task predates the agent/deps/slice contract
        missing = []
        if t.agent is None:
            missing.append("agent")
        if t.slice is None:
            missing.append("slice")
        # deps missing is indistinguishable from "deps: none"; only warn as part of the set
        if missing:
            note = f"missing {', '.join(missing)} (predates the agent/deps/slice contract)"
            if t.agent is None and t.skill:
                inferred = SKILL_TO_AGENT.get(t.skill.lower())
                if inferred:
                    t.agent = inferred
                    note += f"; inferred agent {inferred!r} from skill {t.skill!r}"
                else:
                    note += "; agent unassigned"
            elif t.agent is None:
                note += "; agent unassigned"
            findings.append(Finding(WARN, "O-LEGACY", where, note))

        # --- agent roster
        if t.agent is not None and t.agent not in AGENT_ROSTER:
            findings.append(Finding(
                ERROR, "O-AGENT", where,
                f"agent {t.agent!r} is not in the roster ({', '.join(sorted(AGENT_ROSTER))})"))

        # --- slice enum
        if t.slice is not None and t.slice not in SLICE_ENUM:
            findings.append(Finding(
                WARN, "O-SLICE", where,
                f"slice {t.slice!r} is not one of ({', '.join(sorted(SLICE_ENUM))})"))

        # --- resolve each dep to a canonical id: exact > case-insensitive > title alias
        resolved = []
        for d in t.deps:
            if d in by_id:
                rid = d
            elif d.lower() in lower_index:
                rid = lower_index[d.lower()]
            elif slugify(d) in alias_index:
                rid = alias_index[slugify(d)]
            else:
                findings.append(Finding(
                    ERROR, "O-DEP", where, f"dep {d!r} references an unknown task id"))
                continue
            if rid == t.id:
                findings.append(Finding(ERROR, "O-DEP", where,
                                        f"task depends on itself ({d!r})"))
                continue
            resolved.append(rid)
        # de-dupe while preserving order (a task listing the same dep twice is harmless)
        t.deps = list(dict.fromkeys(resolved))

    return findings


def build_waves(tasks):
    """Layer tasks into waves: wave N holds every remaining task whose deps are all in
    earlier waves. Order within a wave preserves file order. Detects cycles."""
    findings = []
    placed = set()
    remaining = list(tasks)
    waves = []
    while remaining:
        ready = [t for t in remaining if all(d in placed for d in t.deps)]
        if not ready:
            cyc = ", ".join(t.id for t in remaining)
            findings.append(Finding(
                ERROR, "O-CYCLE", "tasks",
                f"dependency cycle — cannot order these tasks: {cyc}"))
            break
        waves.append(ready)
        for t in ready:
            placed.add(t.id)
        remaining = [t for t in remaining if t.id not in placed]
    return waves, findings


def _emit(findings, stream):
    for f in findings:
        print(f.line(), file=stream)


def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    args = [a for a in args if a != "--json"]
    def _fail(code, where, msg, exit_code):
        # On --json, ALWAYS emit a parseable object on stdout — including IO/usage errors —
        # so a machine consumer never gets empty stdout on any error path.
        print(f"ERROR [{code}] {where}: {msg}", file=sys.stderr)
        if json_mode:
            print(json.dumps({"error": True, "waves": [], "findings": [
                {"severity": "ERROR", "code": code, "where": where, "msg": msg}]}, ensure_ascii=False))
        sys.exit(exit_code)

    if len(args) != 1:
        _fail("O-USAGE", "<args>", "usage: orchestrate.py <memory/tasks.md> [--json]", 2)
    path = args[0]

    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        _fail("O-IO", path, "file not found", 2)
    except UnicodeDecodeError:
        _fail("O-IO", path, "not valid UTF-8 text", 2)
    except OSError as e:
        _fail("O-IO", path, str(e), 2)

    findings = []
    tasks, parse_findings = parse_tasks(text)
    findings += parse_findings

    if not tasks:
        msg = Finding(WARN, "O-EMPTY", path, "no tasks found (no headings/bullets carried "
                      "acceptance/skill/agent/deps/slice fields)")
        _emit([msg], sys.stderr if json_mode else sys.stdout)
        if json_mode:
            print(json.dumps({"waves": []}, ensure_ascii=False))
        sys.exit(1)

    findings += validate(tasks)

    # Only lay out waves if the graph is well-formed (deps all resolve, no dup ids).
    has_error = any(f.severity == ERROR for f in findings)
    waves = []
    if not has_error:
        waves, wave_findings = build_waves(tasks)
        findings += wave_findings
        has_error = any(f.severity == ERROR for f in findings)

    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]

    # ── error path: no plan, findings + summary, exit 2 ──────────────────────
    if has_error:
        _emit(findings, sys.stderr if json_mode else sys.stdout)
        if json_mode:
            # Always emit a parseable JSON object on stdout — even on the error path —
            # so a machine consumer never gets empty stdout.
            print(json.dumps({"error": True, "waves": [], "findings": [
                {"severity": f.severity, "code": f.code, "where": f.where, "msg": f.msg}
                for f in findings]}, ensure_ascii=False))
        print(f"orchestrate.py: {len(errors)} error(s), {len(warns)} warning(s)",
              file=sys.stderr if json_mode else sys.stdout)
        sys.exit(2)

    # ── success path: print the plan ─────────────────────────────────────────
    if json_mode:
        payload = {"waves": [
            [{"id": t.id, "agent": t.agent, "slice": t.slice, "deps": t.deps} for t in wave]
            for wave in waves
        ]}
        print(json.dumps(payload, ensure_ascii=False))
        _emit(findings, sys.stderr)
        if warns:
            print(f"orchestrate.py: 0 error(s), {len(warns)} warning(s)", file=sys.stderr)
        else:
            print(f"✓ orchestrate.py: clean — {path}", file=sys.stderr)
    else:
        for i, wave in enumerate(waves, 1):
            for t in wave:
                agent = t.agent or "(unassigned)"
                print(f"Wave {i}: {t.id} -> {agent} [{t.slice or '?'}]")
        _emit(findings, sys.stdout)
        if warns:
            print(f"orchestrate.py: 0 error(s), {len(warns)} warning(s)")
        else:
            print(f"✓ orchestrate.py: clean — {path}")

    sys.exit(1 if warns else 0)


if __name__ == "__main__":
    main()
