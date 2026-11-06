#!/usr/bin/env python3
"""
ticket.py — build, lint, index, diff and export front-end developer tickets from a project.

A front-end ticket is the page a developer opens to build one slice of the product. Written by
hand across several sessions, the same kind of ticket came out in a different shape every time:
sections renamed, the States table missing a row, an evidence link that pointed at nothing, a
decision id the recipient could not look up. None of that is judgement; it is structure, and
structure is arithmetic. So the shape lives in one template (pb/template/fe-ticket.template.md),
and this tool builds from it, checks against it, and keeps a ticket honest as the project moves.

WHY A TOOL AND NOT A PROMPT. Deterministic, byte-stable, no
timestamps in anything it derives (the one exception is the publish ledger, whose time the caller
passes in). A regenerated ticket or index diffs cleanly against the last one.

THE TEMPLATE IS THE SOURCE OF TRUTH. `new` and `lint` both read the `##` sections of
fe-ticket.template.md: their names, their order, whether each is Required or Optional, the six
State rows and the Edge-cases columns. Change the template and the tool follows.

A TICKET FILE (handoff/tickets/<ID>.md)
  1. a fenced block, info string `ticket`, holding JSON front matter (keys sorted, 2-space indent);
  2. `# <title>`;
  3. one `## <Section>` per template section, in template order.
  Prose the author must write is left as the marker `<!-- fill -->`.

IDS. Ticket ids match ^T-[a-z0-9]+(-[a-z0-9]+)*$ and are chosen by the caller, never counted, so
deleting a ticket cannot renumber the others. Scenarios have no id of their own in the registry, so
this tool names one: `<story-key>.<n>`, where story-key is the story's `id` when it has one (else
`s-` plus a slug of its title) and n is the scenario's 1-based position in that story.

DIGEST. `source.digest` is a sha1 over the registry entries a ticket was written from (screens,
components, rules, scenarios — each list sorted by id; a scenario's lastResult is left out, because a
test run is not a design change) plus the raw bytes of each screen and component renderSrc file. It
answers "has what this ticket describes moved since it was written?": `stale` lists tickets whose
digest differs, `refresh` re-stamps one after review, and `published` compares against the digest
recorded when the ticket was sent out.

READ-ONLY ON THE PROJECT. registry.json and every file outside <project>/handoff/tickets/ are only
ever read, so no registry lock is needed (writers replace it atomically). Files under
handoff/tickets/ are written atomically through a temp file.

Usage:  python3 ticket.py <cmd> [--project DIR]            (DIR default ".", must hold registry.json)
  new ID --title T --feature F --kind journey|component|rules|region
         [--screen S]... [--component C]... [--rule R]... [--scenario SC]... [--depends ID]...
         [--order N] [--base-url URL] [--evidence flow|annotation] [--force]
  lint [ID...] [--strict]        findings "<ID> <CODE> <message>", one per line, sorted
  index                          write handoff/tickets/index.md
  stale [ID...]                  ids whose digest changed (exit 1 if any)
  refresh ID                     recompute source.digest in the front matter only
  export ID --format notion|md   to stdout; refuses (exit 1) while lint has errors
  mark-published ID --target notion|jira --url URL [--at ISO]
  published ID                   the ledger entry, and whether the digest has moved since

Lint codes (ERROR unless noted):
  TK-FRONT     front matter missing, not valid JSON, or a key missing / of the wrong type
  TK-ID        id does not match the pattern, or does not match the file name
  TK-TITLE     title is not `[Area] outcome phrase`, or differs from the `# ` heading
  TK-SECTION   a required section is missing; a section is out of order, duplicated or unknown
  TK-EMPTY     a required section or table cell is blank or still holds `<!-- fill`
  TK-STATES    the States table is missing one of the six rows, or has an unexpected one
  TK-DEP       a depends id with no ticket file (or the ticket depends on itself)
  TK-REF       a front-matter screen / component / rule / scenario that no longer exists
  TK-LOGIC     a referenced screen or component whose logicSrc points at a missing file
  TK-DOC       Document lacks a `?screen=` deep link, or its evidence form is missing or points nowhere
  TK-INTERNAL  the body mentions something only the tool's author can see (decision ids, rule codes,
               the registry file, render / spec / logic paths, memory/decisions)
  TK-STALE     (WARNING) the recorded digest differs from the current one

Exit: 0 ok · 1 lint errors (or warnings under --strict), or a stale / differing result · 2 usage
(unknown id, missing file, refused overwrite, bad arguments). Stdlib only; Python 3.9-compatible.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "template", "fe-ticket.template.md")

FILL = "<!-- fill -->"
ID_RE = re.compile(r"^T-[a-z0-9]+(-[a-z0-9]+)*$")
TITLE_RE = re.compile(r"^\[[^\[\]]+\]\s+\S")
KINDS = ("journey", "component", "rules", "region")
EVIDENCE = ("flow", "annotation")
TARGETS = ("notion", "jira")
NONE_WORDS = ("none", "n/a", "không có", "không áp dụng")
FRONT_RE = re.compile(r"\A```ticket[ \t]*\n(.*?)\n```[ \t]*(?:\n|\Z)", re.S)
PLACEHOLDER_RE = re.compile(r"<!--\s*fill\b.*?-->", re.S)
SCREEN_LINK_RE = re.compile(r"[?&]screen=[A-Za-z0-9][\w.\-]*")
INTERNAL = (re.compile(r"\bD-\d+\b"),
            re.compile(r"\bR-[A-Z][A-Z0-9-]+\b"),
            re.compile(r"\bTK-[A-Z]+\b"),
            re.compile(r"registry\.json"),
            re.compile(r"render/(?:components|screens|styles)/"),
            re.compile(r"spec/(?:components|screens)/"),
            re.compile(r"logic/(?:components|screens)/"),
            re.compile(r"memory/decisions"))
FRONT_LISTS = ("depends", "screens", "components", "rules", "scenarios")
FRONT_STRINGS = ("id", "title", "feature")
FRONT_REQUIRED = FRONT_STRINGS + ("kind", "order", "evidence", "prototype", "source") + FRONT_LISTS


class Usage(Exception):
    """A caller error: unknown id, missing file, refused overwrite. Exit 2."""


# ───────────────────────────── small text helpers ─────────────────────────────

def _esc(s):
    """Markdown-safe table cell: a pipe would split it, a newline would end the row."""
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _flat(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def _slug(s):
    s = unicodedata.normalize("NFKD", str(s).replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _none_word(body):
    t = unicodedata.normalize("NFC", body).strip().rstrip(".").strip().casefold()
    return t in NONE_WORDS


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write_atomic(path, text):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ticket-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _inside(proj, rel):
    """The absolute path of `rel` under the project, or None if it would escape it."""
    if not rel or os.path.isabs(rel):
        return None
    full = os.path.realpath(os.path.join(proj, rel))
    root = os.path.realpath(proj)
    return full if full == root or full.startswith(root + os.sep) else None


# ───────────────────────────── markdown structure ─────────────────────────────

def parse_doc(text):
    """{'title': str|None, 'sections': [{'name','body','line'}]} — fence-aware, so a `## ` inside a
    code block is not a heading."""
    title, secs, cur, fence = None, [], None, False
    for i, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence:
            if line.startswith("## "):
                cur = {"name": line[3:].strip(), "lines": [], "line": i}
                secs.append(cur)
                continue
            if line.startswith("# ") and title is None and cur is None:
                title = line[2:].strip()
                continue
        if cur is not None:
            cur["lines"].append(line)
    for s in secs:
        s["body"] = "\n".join(s.pop("lines")).strip()
    return {"title": title, "sections": secs}


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def parse_tables(body):
    """Every pipe table in a section: [{'header': [...], 'rows': [[...]]}]. A table needs a header
    and a `---` separator row; anything else starting with a pipe is not one."""
    tables, block = [], []
    for line in body.split("\n") + [""]:
        if line.strip().startswith("|"):
            block.append(line)
            continue
        if len(block) >= 2 and re.match(r"^\s*\|?[\s:|\-]+\|?\s*$", block[1]) and "-" in block[1]:
            tables.append({"header": _cells(block[0]), "rows": [_cells(r) for r in block[2:]]})
        block = []
    return tables


def _table_md(header, rows):
    out = ["| " + " | ".join(_esc(h) for h in header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


# ───────────────────────────────── template ─────────────────────────────────

def load_template(path=None):
    """The section list, in order: [{'name','level','guide','tables'}]. `level` is required |
    optional | conditional, read from the `> **Required.**` / `> **Optional.**` line under each
    heading. A template section without one is a template bug, so it fails loudly."""
    path = path or TEMPLATE
    if not os.path.isfile(path):
        raise Usage("template not found: %s" % path)
    out = []
    for s in parse_doc(_read(path))["sections"]:
        m = None
        for line in s["body"].split("\n"):
            if line.strip():
                m = re.match(r">\s*\*\*(Required|Optional)\b([^*]*)\*\*\s*(.*)$", line.strip())
                break
        if not m:
            raise Usage("template section '%s' has no `> **Required.**` or `> **Optional.**` line" % s["name"])
        level = m.group(1).lower()
        if level == "required" and m.group(2).strip().startswith("when"):
            level = "conditional"
        out.append({"name": s["name"], "level": level, "guide": m.group(3).strip(),
                    "tables": parse_tables(s["body"])})
    if not out:
        raise Usage("template has no `## ` sections: %s" % path)
    return out


def _tpl(tpl, name):
    for s in tpl:
        if s["name"].casefold() == name.casefold():
            return s
    return None


def state_rows(tpl):
    s = _tpl(tpl, "States")
    t = s["tables"][0] if s and s["tables"] else None
    return t["header"], [r[0] for r in t["rows"] if r and r[0]] if t else []


def edge_header(tpl):
    s = _tpl(tpl, "Edge cases")
    return s["tables"][0]["header"] if s and s["tables"] else ["Case", "Preselected", "Message",
                                                                "Primary button", "Result"]


def annotation_header(tpl):
    s = _tpl(tpl, "Document")
    for t in (s["tables"] if s else []):
        if t["header"] and t["header"][0] == "#":
            return t["header"]
    return ["#", "Part", "Spec"]


# ───────────────────────────────── registry ─────────────────────────────────

def open_project(project):
    proj = os.path.abspath(project or ".")
    reg_path = os.path.join(proj, "registry.json")
    if not os.path.isfile(reg_path):
        raise Usage("no registry.json in %s (pass --project DIR)" % proj)
    try:
        reg = json.loads(_read(reg_path))
    except ValueError as e:
        raise Usage("registry.json is not valid JSON: %s" % e)
    if not isinstance(reg, dict):
        raise Usage("registry.json is not an object")
    return proj, reg


def tickets_dir(proj):
    return os.path.join(proj, "handoff", "tickets")


def _entries(reg, key):
    v = reg.get(key)
    if isinstance(v, dict):                       # {global: [...], local: [...]} tolerated
        v = [x for part in v.values() if isinstance(part, list) for x in part]
    return [x for x in (v or []) if isinstance(x, dict) and isinstance(x.get("id"), str)]


def reg_screens(reg):
    return {e["id"]: e for e in _entries(reg, "screens")}


def reg_components(reg):
    return {e["id"]: e for e in _entries(reg, "components")}


def reg_rules(reg):
    ia = reg.get("ia")
    rules = ia.get("rules") if isinstance(ia, dict) else None
    if not rules:
        rules = reg.get("rules")                  # the pre-ia location
    return {e["id"]: e for e in (rules or []) if isinstance(e, dict) and isinstance(e.get("id"), str)}


def role_ids(reg):
    roles = (reg.get("meta") or {}).get("roles")
    return [r["id"] for r in (roles or []) if isinstance(r, dict) and isinstance(r.get("id"), str)]


def scenario_index(reg):
    """{scenario id: (story key, scenario)} in registry order. See the module docstring for the id."""
    flow = reg.get("flow")
    stories = flow.get("stories") if isinstance(flow, dict) else None
    out, used = {}, set()
    for si, st in enumerate(stories or []):
        if not isinstance(st, dict):
            continue
        key = st.get("id") if isinstance(st.get("id"), str) and st.get("id") else None
        if key is None:
            slug = _slug(st.get("title") or "")
            key = "s-" + slug if slug else "s-story-%d" % (si + 1)
        base, n = key, 2
        while key in used:
            key, n = "%s-%d" % (base, n), n + 1
        used.add(key)
        for i, sc in enumerate(st.get("scenarios") or []):
            out["%s.%d" % (key, i + 1)] = (key, sc)
    return out


def scenario_title(sc, sid):
    if isinstance(sc, dict):
        return _flat(sc.get("title") or sc.get("text") or sid)
    return _flat(sc) or sid


def scenario_start(sc):
    t = sc.get("test") if isinstance(sc, dict) else None
    return t.get("start") if isinstance(t, dict) else None


def source_digest(proj, reg, front):
    """sha1 over the referenced registry entries and their renderSrc bytes. Deterministic."""
    def ids(key):
        v = front.get(key) if isinstance(front, dict) else None
        return sorted({x for x in (v or []) if isinstance(x, str)})

    screens, comps, rules, scen = reg_screens(reg), reg_components(reg), reg_rules(reg), scenario_index(reg)
    payload = {"screens": [screens[i] for i in ids("screens") if i in screens],
               "components": [comps[i] for i in ids("components") if i in comps],
               "rules": [rules[i] for i in ids("rules") if i in rules],
               "scenarios": []}
    for i in ids("scenarios"):
        if i in scen:
            key, sc = scen[i]
            if isinstance(sc, dict):
                sc = {k: v for k, v in sc.items() if k != "lastResult"}
            payload["scenarios"].append({"id": i, "story": key, "scenario": sc})
    h = hashlib.sha1(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    for entry in payload["screens"] + payload["components"]:
        src = entry.get("renderSrc")
        full = _inside(proj, src) if isinstance(src, str) else None
        if full and os.path.isfile(full):
            with open(full, "rb") as f:
                h.update(b"\0" + src.encode("utf-8") + b"\0" + f.read())
    return h.hexdigest()


# ─────────────────────────────── ticket files ───────────────────────────────

def ticket_path(proj, tid):
    return os.path.join(tickets_dir(proj), tid + ".md")


def ticket_ids(proj):
    d = tickets_dir(proj)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-3] for f in os.listdir(d)
                  if f.endswith(".md") and f != "index.md" and not f.startswith("."))


def parse_ticket(text):
    m = FRONT_RE.match(text)
    front = err = None
    if not m:
        err = "no ```ticket front-matter block at the top of the file"
        body, body_line = text, 0
    else:
        body, body_line = text[m.end():], text[:m.end()].count("\n")
        try:
            front = json.loads(m.group(1))
        except ValueError as e:
            err = "front matter is not valid JSON (%s)" % e
    return {"front": front, "err": err, "body": body, "body_line": body_line, "doc": parse_doc(body)}


def render_front(front):
    return "```ticket\n" + json.dumps(front, indent=2, sort_keys=True, ensure_ascii=False) + "\n```\n"


def render_ticket(front, title, sections):
    parts = [render_front(front).rstrip("\n"), "", "# " + title, ""]
    for name, body in sections:
        parts += ["## " + name, "", body, ""]
    return "\n".join(parts).rstrip("\n") + "\n"


def load_ticket(proj, tid):
    path = ticket_path(proj, tid)
    if not os.path.isfile(path):
        raise Usage("no ticket %s (looked for %s)" % (tid, os.path.relpath(path, proj)))
    return parse_ticket(_read(path))


# ───────────────────────────────────── new ─────────────────────────────────────

def _dedupe(xs):
    seen, out = set(), []
    for x in xs or []:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def cmd_new(a):
    proj, reg = open_project(a.project)
    tid = a.id
    if not ID_RE.match(tid):
        raise Usage("id %r does not match ^T-[a-z0-9]+(-[a-z0-9]+)*$" % tid)
    path = ticket_path(proj, tid)
    if os.path.exists(path) and not a.force:
        raise Usage("%s already exists (pass --force to overwrite)" % os.path.relpath(path, proj))
    tpl = load_template()
    screens, comps, rules, scen = reg_screens(reg), reg_components(reg), reg_rules(reg), scenario_index(reg)
    sel = {"screens": _dedupe(a.screen), "components": _dedupe(a.component),
           "rules": _dedupe(a.rule), "scenarios": _dedupe(a.scenario), "depends": _dedupe(a.depends)}
    for key, known, label in (("screens", screens, "screen"), ("components", comps, "component"),
                              ("rules", rules, "rule"), ("scenarios", scen, "scenario")):
        for i in sel[key]:
            if i not in known:
                raise Usage("unknown %s id: %s" % (label, i))
    for d in sel["depends"]:
        if d == tid:
            raise Usage("a ticket cannot depend on itself: %s" % d)
        if not os.path.isfile(ticket_path(proj, d)):
            raise Usage("unknown ticket in --depends: %s (no %s)" % (d, os.path.relpath(ticket_path(proj, d), proj)))
    if not sel["scenarios"]:                      # the scenarios that start on a screen this ticket covers
        sel["scenarios"] = [sid for sid, (_, sc) in scen.items() if scenario_start(sc) in sel["screens"]]
    title, feature = _flat(a.title), _flat(a.feature)
    if not title or not feature:
        raise Usage("--title and --feature must not be empty")
    evidence = a.evidence or ("flow" if a.kind in ("journey", "rules") else "annotation")

    base = a.base_url or (reg.get("meta") or {}).get("prototypeUrl") or ""
    first = sel["screens"][0] if sel["screens"] else ""
    front = {"id": tid, "title": title, "feature": feature, "kind": a.kind, "order": a.order,
             "depends": sel["depends"], "screens": sel["screens"], "components": sel["components"],
             "rules": sel["rules"], "scenarios": sel["scenarios"], "evidence": evidence,
             "prototype": {"url": base, "opens": first}, "figma": None, "jira": None,
             "source": {"digest": ""}}
    front["source"]["digest"] = source_digest(proj, reg, front)

    ctx = {"tid": tid, "front": front, "reg": reg, "rules": rules, "scen": scen, "base": base,
           "first": first, "evidence": evidence}
    sections = [(s["name"], _skeleton(s["name"], tpl, ctx)) for s in tpl]
    _write_atomic(path, render_ticket(front, title, sections))
    print(os.path.relpath(path, proj))
    return 0


def _skeleton(name, tpl, ctx):
    key = name.casefold()
    if key == "states":
        header, names = state_rows(tpl)
        rows = [[_esc(n)] + [FILL] * (len(header) - 1) for n in names]
        return _table_md(header, rows)
    if key == "edge cases":
        header = edge_header(tpl)
        rows = [[_esc(ctx["rules"][r].get("title") or r)] + [FILL] * (len(header) - 1)
                for r in ctx["front"]["rules"]]
        return _table_md(header, rows or [[FILL] * len(header)])
    if key == "roles":
        roles = role_ids(ctx["reg"])
        if len(roles) <= 1:
            return "None"
        return _table_md(["Capability"] + roles, [[FILL] * (len(roles) + 1)])
    if key == "acceptance":
        items = ["- [ ] %s \u2014 scenario %s" % (scenario_title(ctx["scen"][s][1], s), s)
                 for s in ctx["front"]["scenarios"]]
        return "\n".join(items + ["- [ ] " + FILL])
    if key == "document":
        base = ctx["base"] or "<!-- fill: prototype url -->"
        sep = "&" if "?" in ctx["base"] else "?"
        link = "%s%sscreen=%s" % (base, sep, ctx["first"] or FILL)
        lines = ["- Prototype: " + link, "- Opens at: " + FILL]
        if ctx["evidence"] == "flow":
            lines.append("- Hand-off flow: <!-- fill: handoff/tickets/%s/flow.html -->" % ctx["tid"])
        else:
            lines.append("- Annotation: <!-- fill: handoff/tickets/%s/annotation.png -->" % ctx["tid"])
            lines += ["", _table_md(annotation_header(tpl), [[FILL] * len(annotation_header(tpl))])]
        return "\n".join(lines)
    return FILL


# ───────────────────────────────────── lint ─────────────────────────────────────

def check_front(f):
    """Problems with the front matter's shape, as messages."""
    if not isinstance(f, dict):
        return ["front matter is not a JSON object"]
    out = ["missing key '%s'" % k for k in FRONT_REQUIRED if k not in f]
    for k in FRONT_STRINGS:
        if k in f and not (isinstance(f[k], str) and f[k].strip()):
            out.append("'%s' must be a non-empty string" % k)
    if "kind" in f and f["kind"] not in KINDS:
        out.append("'kind' must be one of %s" % "|".join(KINDS))
    if "evidence" in f and f["evidence"] not in EVIDENCE:
        out.append("'evidence' must be one of %s" % "|".join(EVIDENCE))
    if "order" in f and (not isinstance(f["order"], int) or isinstance(f["order"], bool)):
        out.append("'order' must be an integer")
    for k in FRONT_LISTS:
        if k in f and not (isinstance(f[k], list) and all(isinstance(x, str) for x in f[k])):
            out.append("'%s' must be a list of strings" % k)
    p = f.get("prototype")
    if "prototype" in f and not (isinstance(p, dict) and isinstance(p.get("url"), str)
                                 and isinstance(p.get("opens"), str)):
        out.append("'prototype' must be {url: string, opens: string}")
    s = f.get("source")
    if "source" in f and not (isinstance(s, dict) and isinstance(s.get("digest"), str)):
        out.append("'source' must be {digest: string}")
    for k in ("figma", "jira"):
        if k in f and f[k] is not None and not isinstance(f[k], str):
            out.append("'%s' must be a string or null" % k)
    return out


def _filled(cell):
    return bool(cell.strip()) and "<!-- fill" not in cell


def _evidence_path(value):
    v = value.strip()
    m = re.search(r"\]\(([^)]+)\)", v)
    return (m.group(1) if m else v).strip().strip("`").strip()


def lint_one(proj, reg, tid, tpl):
    """Findings for one ticket: [(id, code, severity, message)]."""
    out = []

    def add(code, msg, warn=False):
        out.append((tid, code, "warn" if warn else "error", msg))

    p = load_ticket(proj, tid)
    front, doc = p["front"], p["doc"]
    if front is None:
        add("TK-FRONT", p["err"])
    else:
        for m in check_front(front):
            add("TK-FRONT", m)
    f = front if isinstance(front, dict) else {}

    # TK-ID
    if not ID_RE.match(tid):
        add("TK-ID", "file name '%s.md' does not match ^T-[a-z0-9]+(-[a-z0-9]+)*$" % tid)
    if isinstance(f.get("id"), str):
        if not ID_RE.match(f["id"]):
            add("TK-ID", "id '%s' does not match ^T-[a-z0-9]+(-[a-z0-9]+)*$" % f["id"])
        elif f["id"] != tid:
            add("TK-ID", "id '%s' does not match the file name '%s.md'" % (f["id"], tid))

    # TK-TITLE
    ftitle = f.get("title") if isinstance(f.get("title"), str) else None
    for label, t in (("title", ftitle), ("heading", doc["title"])):
        if t is not None and not TITLE_RE.match(t):
            add("TK-TITLE", "%s '%s' is not `[Area] outcome phrase`" % (label, t))
    if doc["title"] is None:
        add("TK-TITLE", "no `# ` heading under the front matter")
    elif ftitle is not None and doc["title"] != ftitle:
        add("TK-TITLE", "heading '%s' differs from the front-matter title '%s'" % (doc["title"], ftitle))

    # TK-SECTION
    multi_role = len(role_ids(reg)) > 1
    order = {s["name"].casefold(): i for i, s in enumerate(tpl)}
    present, seen, last = {}, set(), -1
    for s in doc["sections"]:
        key = s["name"].casefold()
        if key not in order:
            add("TK-SECTION", "unknown section '%s'" % s["name"])
        elif key in seen:
            add("TK-SECTION", "section '%s' appears twice" % s["name"])
        else:
            seen.add(key)
            present[key] = s
            if order[key] < last:
                add("TK-SECTION", "section '%s' is out of order (template: %s)"
                    % (s["name"], " \u00b7 ".join(t["name"] for t in tpl)))
            last = max(last, order[key])

    def required(t):
        return t["level"] == "required" or (t["level"] == "conditional" and multi_role)

    for t in tpl:
        if required(t) and t["name"].casefold() not in present:
            add("TK-SECTION", "required section '%s' is missing" % t["name"])

    # TK-EMPTY
    for t in tpl:
        s = present.get(t["name"].casefold())
        if not s or not required(t):
            continue
        body, name = s["body"], t["name"]
        if not body:
            add("TK-EMPTY", "%s is empty (write the content, or one of: None, N/A)" % name)
            continue
        if _none_word(body):
            continue
        if "<!-- fill" in body:
            add("TK-EMPTY", "%s still holds a <!-- fill --> placeholder" % name)
        if name.casefold() != "document":
            for tb in parse_tables(body):
                for row in tb["rows"]:
                    if any(not c.strip() for c in row):
                        add("TK-EMPTY", "%s: row '%s' has a blank cell (write N/A if it does not apply)"
                            % (name, row[0] or "?"))
        if name.casefold() == "acceptance" and not re.search(r"^\s*[-*]\s+\[[ xX]\]", body, re.M):
            add("TK-EMPTY", "Acceptance has no `- [ ]` items")

    # TK-STATES
    st = present.get("states")
    if st:
        _, wanted = state_rows(tpl)
        tables = [tb for tb in parse_tables(st["body"]) if tb["rows"]]
        got = [r[0] for r in tables[0]["rows"] if r] if tables else []
        if not tables:
            add("TK-STATES", "States has no table")
        else:
            have = {g.casefold() for g in got}
            for w in wanted:
                if w.casefold() not in have:
                    add("TK-STATES", "States table is missing the row '%s'" % w)
            for g in got:
                if g.casefold() not in {w.casefold() for w in wanted}:
                    add("TK-STATES", "States table has an unexpected row '%s'" % g)

    # TK-DEP
    for d in f.get("depends") if isinstance(f.get("depends"), list) else []:
        if d == tid:
            add("TK-DEP", "depends on itself")
        elif not isinstance(d, str) or not os.path.isfile(ticket_path(proj, d)):
            add("TK-DEP", "depends on '%s', which has no ticket file" % d)

    # TK-REF, TK-LOGIC
    screens, comps, rules, scen = reg_screens(reg), reg_components(reg), reg_rules(reg), scenario_index(reg)
    for key, known, label in (("screens", screens, "screen"), ("components", comps, "component"),
                              ("rules", rules, "rule"), ("scenarios", scen, "scenario")):
        for i in f.get(key) if isinstance(f.get(key), list) else []:
            if not isinstance(i, str):
                continue                      # TK-FRONT already named the bad type
            if i not in known:
                add("TK-REF", "%s '%s' no longer exists in the project" % (label, i))
            elif key in ("screens", "components"):
                src = known[i].get("logicSrc")
                if isinstance(src, str):
                    full = _inside(proj, src)
                    if not full or not os.path.isfile(full):
                        add("TK-LOGIC", "%s '%s' points at a logic file that does not exist (%s)" % (label, i, src))

    # TK-DOC
    d = present.get("document")
    if d:
        if not SCREEN_LINK_RE.search(d["body"]):
            add("TK-DOC", "Document has no prototype deep link (`?screen=<screen id>`)")
        ev = f.get("evidence")
        flow_line = re.search(r"^\s*[-*]\s*Hand-off flow:\s*(.+)$", d["body"], re.M | re.I)
        ann_line = re.search(r"^\s*[-*]\s*Annotation:\s*(.+)$", d["body"], re.M | re.I)
        if ev in EVIDENCE:
            mine, other, label, olabel = ((flow_line, ann_line, "Hand-off flow", "Annotation") if ev == "flow"
                                          else (ann_line, flow_line, "Annotation", "Hand-off flow"))
            if not mine:
                add("TK-DOC", "evidence is '%s' but Document has no '%s:' line" % (ev, label))
            else:
                rel = _evidence_path(mine.group(1))
                if "<!--" not in rel:
                    full = _inside(proj, rel)
                    if not full or not os.path.exists(full):
                        add("TK-DOC", "%s file does not exist: %s" % (label, rel))
            if other:
                add("TK-DOC", "Document carries a '%s:' line but the ticket's evidence is '%s' (one form only)"
                    % (olabel, ev))
            if ev == "annotation":
                hdr = [h.casefold() for h in annotation_header(tpl)]
                good = [r for tb in parse_tables(d["body"]) if [h.casefold() for h in tb["header"]] == hdr
                        for r in tb["rows"] if r and all(_filled(c) for c in r)]
                if not good:
                    add("TK-DOC", "annotation needs a filled row in the `| %s |` table"
                        % " | ".join(annotation_header(tpl)))

    # TK-INTERNAL
    seen_hits = set()
    for rx in INTERNAL:
        for m in rx.finditer(p["body"]):
            if m.group(0) in seen_hits:
                continue
            seen_hits.add(m.group(0))
            line = p["body_line"] + p["body"][:m.start()].count("\n") + 1
            add("TK-INTERNAL", "line %d mentions '%s', which the recipient cannot look up" % (line, m.group(0)))

    # TK-STALE
    rec = f.get("source", {}).get("digest") if isinstance(f.get("source"), dict) else None
    if isinstance(rec, str):
        cur = source_digest(proj, reg, f)
        if rec != cur:
            add("TK-STALE", "recorded digest %s differs from current %s; review, then `refresh`"
                % (rec[:10] or "(none)", cur[:10]), warn=True)
    return out


def lint_many(proj, reg, ids, tpl):
    findings = []
    for tid in ids:
        findings += lint_one(proj, reg, tid, tpl)
    return sorted(findings, key=lambda x: (x[0], x[1], x[3]))


def _want_ids(proj, ids):
    ids = _dedupe(ids)
    for i in ids:
        if not os.path.isfile(ticket_path(proj, i)):
            raise Usage("no ticket %s (looked for %s)" % (i, os.path.relpath(ticket_path(proj, i), proj)))
    return ids or ticket_ids(proj)


def _line(fd):
    return "%s %s %s%s" % (fd[0], fd[1], "warning: " if fd[2] == "warn" else "", fd[3])


def cmd_lint(a):
    proj, reg = open_project(a.project)
    ids = _want_ids(proj, a.ids)
    findings = lint_many(proj, reg, ids, load_template())
    for fd in findings:
        print(_line(fd))
    bad = [fd for fd in findings if fd[2] == "error" or a.strict]
    return 1 if bad else 0


# ───────────────────────────── index / stale / refresh ─────────────────────────────

def cmd_index(a):
    proj, reg = open_project(a.project)
    ids = ticket_ids(proj)
    tpl = load_template()
    counts = {}
    for fd in lint_many(proj, reg, ids, tpl):
        counts[fd[0]] = counts.get(fd[0], 0) + 1
    rows = []
    for tid in ids:
        f = parse_ticket(_read(ticket_path(proj, tid)))["front"]
        f = f if isinstance(f, dict) else {}
        order = f.get("order") if isinstance(f.get("order"), int) else 0
        deps = ", ".join(x for x in f.get("depends", []) if isinstance(x, str)) \
            if isinstance(f.get("depends"), list) else ""
        n = counts.get(tid, 0)
        rows.append((order, tid, [str(order), _esc(tid), _esc(f.get("title") or "\u2014"),
                                  _esc(f.get("feature") or "\u2014"), _esc(deps) or "\u2014",
                                  "ok" if n == 0 else "%d finding%s" % (n, "" if n == 1 else "s")]))
    out = ["# Ticket index", "",
           "Generated by `ticket.py index`; do not edit by hand.", "",
           "| Order | ID | Title | Feature | Depends | Status |",
           "|---:|---|---|---|---|---|"]
    out += ["| " + " | ".join(r[2]) + " |" for r in sorted(rows, key=lambda r: (r[0], r[1]))]
    _write_atomic(os.path.join(tickets_dir(proj), "index.md"), "\n".join(out) + "\n")
    print(os.path.relpath(os.path.join(tickets_dir(proj), "index.md"), proj))
    return 0


def _current_digest(proj, reg, p):
    return source_digest(proj, reg, p["front"] if isinstance(p["front"], dict) else {})


def cmd_stale(a):
    proj, reg = open_project(a.project)
    hit = False
    for tid in _want_ids(proj, a.ids):
        p = load_ticket(proj, tid)
        if not isinstance(p["front"], dict):
            continue
        src = p["front"].get("source")
        rec = src.get("digest") if isinstance(src, dict) else None
        if rec != _current_digest(proj, reg, p):
            print(tid)
            hit = True
    return 1 if hit else 0


def cmd_refresh(a):
    proj, reg = open_project(a.project)
    path = ticket_path(proj, a.id)
    p = load_ticket(proj, a.id)
    if not isinstance(p["front"], dict):
        raise Usage("%s has no readable front matter (%s)" % (a.id, p["err"]))
    text = _read(path)
    m = FRONT_RE.match(text)
    front = dict(p["front"])
    src = dict(front.get("source") if isinstance(front.get("source"), dict) else {})
    src["digest"] = _current_digest(proj, reg, p)
    front["source"] = src
    _write_atomic(path, render_front(front) + text[m.end():])
    print("%s %s" % (a.id, src["digest"]))
    return 0


# ───────────────────────────────────── export ─────────────────────────────────────

def _strip_placeholders(body):
    """Remove `<!-- fill ... -->` markers; drop a list item or table row that held only one."""
    out = []
    for line in body.split("\n"):
        if "<!-- fill" not in line:
            out.append(line)
            continue
        cleaned = PLACEHOLDER_RE.sub("", line)
        if re.sub(r"[\s|\-*]|\[\s?\]", "", cleaned) == "":
            continue
        out.append(cleaned.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def cmd_export(a):
    proj, reg = open_project(a.project)
    p = load_ticket(proj, a.id)
    errors = [fd for fd in lint_one(proj, reg, a.id, load_template()) if fd[2] == "error"]
    if errors:
        for fd in errors:
            print(_line(fd), file=sys.stderr)
        print("ticket.py: %s has lint errors; fix them before exporting" % a.id, file=sys.stderr)
        return 1
    if a.format == "md":
        sys.stdout.write(p["body"].lstrip("\n").rstrip("\n") + "\n")
        return 0
    f = p["front"]
    parts = []
    for s in p["doc"]["sections"]:
        body = _strip_placeholders(s["body"])
        if body:
            parts.append("## %s\n\n%s" % (s["name"], body))
    payload = {"properties": {"Name": f["title"], "Ticket ID": f["id"], "Feature": f["feature"],
                              "Order": f["order"], "Depends": ", ".join(f["depends"]),
                              "Jira": f.get("jira") or ""},
               "content": "\n\n".join(parts) + "\n"}
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


# ───────────────────────────────── publish ledger ─────────────────────────────────

def _ledger_path(proj):
    return os.path.join(tickets_dir(proj), ".published.json")


def _load_ledger(proj):
    path = _ledger_path(proj)
    if not os.path.isfile(path):
        return {}
    try:
        data = json.loads(_read(path))
    except ValueError as e:
        raise Usage(".published.json is not valid JSON: %s" % e)
    return data if isinstance(data, dict) else {}


def cmd_mark_published(a):
    proj, reg = open_project(a.project)
    p = load_ticket(proj, a.id)
    if not isinstance(p["front"], dict):
        raise Usage("%s has no readable front matter (%s)" % (a.id, p["err"]))
    at = a.at or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ledger = _load_ledger(proj)
    entry = ledger.get(a.id) if isinstance(ledger.get(a.id), dict) else {}
    entry[a.target] = {"url": a.url, "digest": _current_digest(proj, reg, p), "at": at}
    ledger[a.id] = entry
    _write_atomic(_ledger_path(proj), json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print("%s %s %s" % (a.id, a.target, entry[a.target]["digest"]))
    return 0


def cmd_published(a):
    proj, reg = open_project(a.project)
    p = load_ticket(proj, a.id)
    entry = _load_ledger(proj).get(a.id)
    if not isinstance(entry, dict) or not entry:
        print("%s not published" % a.id)
        return 0
    cur = _current_digest(proj, reg, p)
    differs = False
    for target in sorted(entry):
        e = entry[target] if isinstance(entry[target], dict) else {}
        moved = e.get("digest") != cur
        differs = differs or moved
        print("%s %s %s at %s digest %s \u2014 current %s: %s"
              % (a.id, target, e.get("url", ""), e.get("at", ""), str(e.get("digest", ""))[:10],
                 cur[:10], "differs" if moved else "same"))
    return 1 if differs else 0


# ────────────────────────────────────── CLI ──────────────────────────────────────

def build_parser():
    ap = argparse.ArgumentParser(prog="ticket.py", description="Build, lint, index, diff and export "
                                 "front-end developer tickets from a Product Builder project.")
    sub = ap.add_subparsers(dest="cmd", metavar="<cmd>")
    sub.required = True
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", default=".", metavar="DIR",
                        help="project folder holding registry.json (default .); tickets live in DIR/handoff/tickets/")

    p = sub.add_parser("new", parents=[common], help="write a ticket skeleton from the template")
    p.add_argument("id", help="T-kebab-case id, never renumbered")
    p.add_argument("--title", required=True, help="[Area] outcome phrase")
    p.add_argument("--feature", required=True)
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--screen", action="append", default=[], metavar="S")
    p.add_argument("--component", action="append", default=[], metavar="C")
    p.add_argument("--rule", action="append", default=[], metavar="R")
    p.add_argument("--scenario", action="append", default=[], metavar="SC")
    p.add_argument("--depends", action="append", default=[], metavar="ID")
    p.add_argument("--order", type=int, default=0, help="reading/build order (default 0)")
    p.add_argument("--base-url", default="", metavar="URL", help="prototype base address")
    p.add_argument("--evidence", choices=EVIDENCE, help="default: flow for journey/rules, else annotation")
    p.add_argument("--force", action="store_true", help="overwrite an existing ticket")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("lint", parents=[common], help="check tickets against the template")
    p.add_argument("ids", nargs="*", metavar="ID")
    p.add_argument("--strict", action="store_true", help="count warnings as failures")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("index", parents=[common], help="write handoff/tickets/index.md")
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("stale", parents=[common], help="list tickets whose source digest changed")
    p.add_argument("ids", nargs="*", metavar="ID")
    p.set_defaults(fn=cmd_stale)

    p = sub.add_parser("refresh", parents=[common], help="recompute source.digest (front matter only)")
    p.add_argument("id")
    p.set_defaults(fn=cmd_refresh)

    p = sub.add_parser("export", parents=[common], help="print a ticket for Notion or as Markdown")
    p.add_argument("id")
    p.add_argument("--format", required=True, choices=("notion", "md"))
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("mark-published", parents=[common], help="record where a ticket was sent")
    p.add_argument("id")
    p.add_argument("--target", required=True, choices=TARGETS)
    p.add_argument("--url", required=True)
    p.add_argument("--at", help="ISO time (default: now, UTC)")
    p.set_defaults(fn=cmd_mark_published)

    p = sub.add_parser("published", parents=[common], help="show the ledger entry; exit 1 if the digest moved")
    p.add_argument("id")
    p.set_defaults(fn=cmd_published)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Usage as e:
        print("ticket.py: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
