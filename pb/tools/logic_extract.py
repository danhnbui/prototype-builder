#!/usr/bin/env python3
"""
logic_extract.py — derive a logic graph from a project's render bodies (I4).

Regex-based, stdlib-only, and deliberately NOT a JS parser: it reads `render/*/*.js`
(plus, optionally, the pb shell that hosts them) the same way a careful human skims
them — literal `id=`/`class=`/`data-*` in emitted markup, `pbUse('id', {...})` calls,
`document.getElementById(...)` / `.querySelector(...)` / `.closest(...)` reads, and
`function NAME() { ... }` declarations at column 0. It answers, for a whole project:

  * which top-level functions exist, which are render bodies vs LOGIC (handlers[]),
  * which DOM handles each handler reads, and who (if anyone) actually emits them,
  * which app-store slices each handler touches, and whether it reads or writes,
  * how components/screens compose each other (items[]), and
  * the navigation graph implied by the sidebar + data-nav/data-go/setProtoScreen.

Ported from two throwaway spikes proven against a real 141-body project (the seam
cross-check's four producer guards, and the ripple graph's handler/nav derivation);
see the module-level section comments below for what changed on the way to here.

FOUR PRODUCER GUARDS (the point of this file — without them, dead-seam is noise)
An id/class/data-* handle can be *produced* four ways beyond a literal
`id="foo"`/`class="foo"` in the same file's markup, and missing any one of them
turns a real pattern into a false "nothing produces this":
  1. an id handed to a composed atom as a PROP        — pbUse('input', {id: 'cq-search'})
  2. an id built through a VARIABLE prefix             — var tid = 'hpb-x-' + member.id
  3. a runtime write                                   — setAttribute('data-x', …) /
                                                          el.dataset.x = … / el.id = …
  4. `idPrefix:`/`name:` props an atom expands per-option — {idPrefix: 'cd-normal'} /
                                                            {name: 'cd-pop'}
All four are handled in `scan_producers()` below (see the guard-numbered comments).

OUTPUT SHAPE  (see `extract()`)
  handlers[]  — every top-level NON-render function: name/file/line/length, the
                registry item(s) that own its file (`owners`, plural — one render
                body can back more than one screen, e.g. three role-scoped screens
                sharing one file; see OWNERSHIP below), cross-file vs local calls,
                DOM `reads[]` (each with the owners that PRODUCE it — "grouped by
                the component that emits them" — and a best-effort `guarded` flag),
                app-store `slices` touched + the `writes` subset (read vs write),
                the two-hop transitive helper path to indirect store access (`via`),
                what it re-renders, guard-shaped helpers it calls, and whether it is
                wired from markup at all (`wiredInline`/`exported`). Each also carries
                a `bodyHash` (sha256 of its brace-matched body) — logic_check.py's
                opt-in `--freeze` mode diffs these to prove a UI-only change touched
                no logic, without re-scanning files itself.
  items[]     — every registry component AND screen: composes/composedBy, handlers
                wired in its markup vs merely reading its DOM, its own logic, and a
                pure `:has()` rule count (information only — never a gate here).
  slices{}    — per app-store slice, its writer and reader handler names.
  nav         — sidebar-derived hubs, edges from data-nav/data-go/setProtoScreen,
                activeScreenId as a fallback parent, BFS layer depth per screen,
                and overlay (drawer/modal/dialog) components per screen.
  deadSeam[]  — DOM handles a handler reads that NO body and NOT the shell produces
                (after all four guards), grouped by (kind, token), each occurrence
                tagged `guarded`. This is what `logic_check.py`'s dead-seam check
                reports — the extractor does the scanning once, the checker only
                classifies severity, so the two tools can't disagree about the scan.
  stats       — total/render/handler function counts, cross-file helper count,
                undefined/duplicate counts, exported/save/slice counts, dead-seam
                count — the same numbers this module's callers report against the
                measured baseline. `undefined{}`/`duplicates{}` carry the detail
                behind those two counts (name -> defining/calling file(s)) so
                logic_check.py's L-UNDEF/L-DUPDEF checks don't re-scan for it.

OWNERSHIP (a deliberate fix over the throwaway spikes)
Both spikes keyed `owner` by render-body PATH, so a file shared by several registry
screens (this project has one: three role-scoped performance screens all render
via `hpbRenderScoped()` in one file) silently lost all but the last screen — items[]
came up short by exactly the number of such collisions. Here `owners` is a list per
path, so `items[]` always has one entry per registry component + screen, full stop.

GENERICITY (also a deliberate fix — see AGENTS.md "match pb conventions")
The ripple spike hardcoded this ONE project's guard-helper names (`pbCanWriteDept`,
`pbBulkWriteAllowed`, …) and rerender-helper names (`pbAppRerender`, …) — neither is
part of the pb shell (`pb/template/prototype.html`); they're this project's OWN
render-body conventions. A tool meant to run over any pb project can't hardcode
another project's function names, so both are re-derived from NAMING CONVENTIONS
instead: a "guard" is any of this project's own top-level helpers whose name looks
like one (`^pbCan`, `^pbGuard`, `^pbAllow`, or a `Guard`/`Allowed`/`Valid` suffix —
see `_GUARD_NAME_RE`); a "rerender" is the one shell-guaranteed entry point
(`renderPrototype`, confirmed present in pb/template/prototype.html) plus any
project-local helper whose name contains "rerender" (case-insensitive). The
`pbAppStore()` store-accessor convention is kept as a single named constant
(`STORE_ACCESSOR`) for the same reason: it is a pb ecosystem naming convention,
not literally part of the shipped shell, so a project without one simply reports
zero slices rather than erroring.

GUARD DETECTION (dead-seam severity, not a separate check — see logic_check.py)
A dead read is Kind A — a contradiction inside the code — so it is only ever an
ERROR when nothing guards it; the survivors on the reference project are all
protected by an `if (el)`, an `if (!el) return`, a `el ? el.x : y` ternary/optional
chain, or a chained `el.closest(...) || fallback`, and `querySelectorAll` reads are
inherently safe (a NodeList is never null). `_classify_guard()` recognizes exactly
those shapes from the statement enclosing each read; anything it can't prove is
conservatively UNGUARDED rather than silently downgraded (never hide a maybe-bug
by assuming the best of code we can't fully parse).

Usage:  logic_extract.py <project-dir> [--shell <prototype.html>] [--out <file>]
Exit:   0 always (this is a graph dump, not a gate — pb/tools/logic_check.py gates).
"""
import collections
import glob
import hashlib
import json
import os
import re
import sys

# ───────────────────────── shared literals: string/comment scanning ──────────────

STR = r"""(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")"""  # a single- or double-quoted JS string


def _sval(m):
    """The matched STR group's text, whichever quote style fired."""
    return m.group(1) if m.group(1) is not None else m.group(2)


def strip_comments(src):
    """Remove `//` and `/* */` comments, but never inside a string/template literal.

    A cheap state machine (quote-aware) rather than a regex, because a regex can't
    tell `"// not a comment"` from a real one without the same state anyway. A
    multi-line `/* */` block keeps its newlines (dropped otherwise) so every
    downstream line number (handlers[].line, reads[].line, …) still lines up with
    the real file.
    """
    out = []
    i, n, q = 0, len(src), None
    while i < n:
        c = src[i]
        if q:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c in ('"', "'", '`'):
            q = c
            out.append(c)
            i += 1
            continue
        if src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            end = n if j < 0 else j + 2
            out.append('\n' * src.count('\n', i, end))
            i = end
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ───────────────────────── producers: the four guards ─────────────────────────
# Each regex is tagged with which guard (1-4, see the module docstring) it serves;
# guard 0 is the baseline literal-markup case every extractor gets for free.

_ID_STATIC = re.compile(r'''\bid=\\?["']([A-Za-z][\w-]*)(?:["'$]|\\)''')                    # guard 0
_ID_DYNAMIC_PREFIX = re.compile(r'''\bid=\\?["']([A-Za-z][\w-]*-)(?:\$\{|["']\s*\+)''')      # guard 0, dynamic
_CLASS_STATIC = re.compile(r'''\bclass=\\?["']([^"'\\${]*)''')                               # guard 0
_CLASS_RUNTIME_ADD = re.compile(r'classList\.add\(\s*' + STR + r'\s*\)')                     # guard 3
_DATA_STATIC = re.compile(r'''\bdata-([a-z][a-z0-9-]*)(?=\s*=|[\s>"'\\])''')                 # guard 0
_NAME_PROP = re.compile(r'''\bname\s*:\s*['"]([A-Za-z][\w-]*)['"]''')                        # guard 4
_IDPREFIX_PROP = re.compile(r'''\bidPrefix\s*:\s*['"]([A-Za-z][\w-]*)['"]''')                # guard 4
_ID_PROP = re.compile(r'''\bid\s*:\s*['"]([A-Za-z][\w-]*)['"]\s*([,}]|\+)''')                # guard 1
_CLASS_PROP = re.compile(r'''\b(?:className|class|cls|wrapClass|rowClass)\s*:\s*['"]([^'"$]*)['"]''')  # guard 1
_ID_PREFIX_VAR = re.compile(r'''['"]([A-Za-z][\w-]*-)['"]\s*\+''')                           # guard 2
_SET_ATTR_DATA = re.compile(r'''setAttribute\(\s*['"]data-([a-z][a-z0-9-]*)['"]''')          # guard 3
_DATASET_WRITE = re.compile(r'\.dataset\.([A-Za-z]\w*)\s*=[^=]')                             # guard 3
_ID_OR_CLASS_WRITE = re.compile(r'''\.(id|className)\s*=\s*['"]([A-Za-z][\w-]*)['"]''')      # guard 3
_CAMEL_TO_KEBAB = re.compile(r'([A-Z])')


def _kebab(camel):
    return _CAMEL_TO_KEBAB.sub(lambda m: '-' + m.group(1).lower(), camel)


class ProducerIndex:
    """Every id/class/data-* handle this project (or its shell) PRODUCES, and by whom.

    `exact[kind][token]` and `prefix[token]` (id-prefixes only — the dynamic-id and
    idPrefix/name-prop forms never resolve to one static id) each map to the set of
    OWNER ids that produce it — a registry component/screen id, a bare relative path
    for a body with no registry owner, or the literal 'SHELL'.
    """

    def __init__(self):
        self.exact = {'id': collections.defaultdict(set), 'class': collections.defaultdict(set),
                      'data': collections.defaultdict(set)}
        self.prefix = collections.defaultdict(set)

    def scan(self, text, owner_ids):
        add = lambda kind, tok: [self.exact[kind][tok].add(o) for o in owner_ids]
        add_pfx = lambda tok: [self.prefix[tok].add(o) for o in owner_ids]

        for m in _ID_STATIC.finditer(text):
            add('id', m.group(1))
        for m in _ID_DYNAMIC_PREFIX.finditer(text):
            add_pfx(m.group(1))
        for m in _CLASS_STATIC.finditer(text):
            for tok in m.group(1).split():
                if re.match(r'^[A-Za-z_][\w-]*$', tok):
                    add('class', tok)
        for m in _CLASS_RUNTIME_ADD.finditer(text):
            add('class', _sval(m))
        for m in _DATA_STATIC.finditer(text):
            add('data', m.group(1))
        for m in _NAME_PROP.finditer(text):
            add_pfx(m.group(1) + '-')
        for m in _IDPREFIX_PROP.finditer(text):
            add_pfx(m.group(1) + '-')
        for m in _ID_PROP.finditer(text):
            (add_pfx(m.group(1) + '') if m.group(2) == '+' else add('id', m.group(1)))
        for m in _CLASS_PROP.finditer(text):
            for tok in m.group(1).split():
                if re.match(r'^[A-Za-z_][\w-]*$', tok):
                    add('class', tok)
        for m in _ID_PREFIX_VAR.finditer(text):
            add_pfx(m.group(1))
        for m in _SET_ATTR_DATA.finditer(text):
            add('data', m.group(1))
        for m in _DATASET_WRITE.finditer(text):
            add('data', _kebab(m.group(1)))
        for m in _ID_OR_CLASS_WRITE.finditer(text):
            add('id' if m.group(1) == 'id' else 'class', m.group(2))

    def producers_of(self, kind, token):
        """Owner ids that produce `token`, exact match first then (ids only) prefix."""
        if token in self.exact[kind]:
            return sorted(self.exact[kind][token])
        if kind == 'id':
            for pfx, owners in self.prefix.items():
                if token.startswith(pfx):
                    return sorted(owners)
        return []

    def has_producer(self, kind, token):
        if token in self.exact[kind]:
            return True
        if kind == 'id':
            return any(token.startswith(pfx) for pfx in self.prefix)
        return False


# ───────────────────────── consumers: DOM handles a handler reads ─────────────────

_QUERY_SEL = re.compile(r'\.querySelector(All)?\(\s*' + STR + r'\s*\)')
_CLOSEST = re.compile(r'\.(?:closest|matches)\(\s*' + STR + r'\s*\)')
_GET_BY_ID = re.compile(r'getElementById\(\s*' + STR + r'\s*([+)])')
_GET_ATTR = re.compile(r'(?:get|has|removeAttribute)Attribute\(\s*' + STR)
_DATASET_READ = re.compile(r'\.dataset\.([A-Za-z]\w*)')


def _sel_tokens(selector):
    ids = re.findall(r'#([A-Za-z_][\w-]*)', selector)
    classes = re.findall(r'\.([A-Za-z_][\w-]*)', selector)
    data = re.findall(r'\[data-([a-z][a-z0-9-]*)', selector)
    return ids, classes, data


def iter_reads(text):
    """Yield (kind, token, how, start, end) for every DOM-handle read in `text`,
    in left-to-right document order (multiple regex passes merged and re-sorted —
    each pass alone is document-order, but the passes interleave)."""
    hits = []
    for m in _QUERY_SEL.finditer(text):
        how = 'querySelectorAll' if m.group(1) else 'querySelector'
        ids, classes, data = _sel_tokens(_sval2(m))
        for i in ids:
            hits.append(('id', i, how, m.start(), m.end()))
        for c in classes:
            hits.append(('class', c, how, m.start(), m.end()))
        for d in data:
            hits.append(('data', d, how, m.start(), m.end()))
    for m in _CLOSEST.finditer(text):
        ids, classes, data = _sel_tokens(_sval(m))
        for i in ids:
            hits.append(('id', i, 'closest', m.start(), m.end()))
        for c in classes:
            hits.append(('class', c, 'closest', m.start(), m.end()))
        for d in data:
            hits.append(('data', d, 'closest', m.start(), m.end()))
    for m in _GET_BY_ID.finditer(text):
        how = 'getElementById+' if m.group(3) == '+' else 'getElementById'
        hits.append(('id', _sval(m), how, m.start(), m.end()))
    for m in _GET_ATTR.finditer(text):
        v = _sval(m)
        if v.startswith('data-'):
            hits.append(('data', v[5:], 'getAttribute', m.start(), m.end()))
    for m in _DATASET_READ.finditer(text):
        hits.append(('data', _kebab(m.group(1)), 'dataset', m.start(), m.end()))
    hits.sort(key=lambda h: (h[3], h[4]))
    return hits


def _sval2(m):
    """Like _sval but for a match whose group 1 is a leading flag (querySelectorAll's
    'All'), shifting the STR groups to 2/3."""
    return m.group(2) if m.group(2) is not None else m.group(3)


# ───────────────────────── guard detection (dead-read severity) ───────────────────

_ASSIGN_TAIL = re.compile(r'(?:\bvar\b|\blet\b|\bconst\b)?\s*([A-Za-z_$][\w$]*)\s*=\s*[A-Za-z_$][\w$.]*$')
_IF_OPEN = re.compile(r'\bif\s*\(')


def _guarded_after_assignment(rest, name):
    """The FIRST subsequent reference to `name` is guard-shaped: `if (name`,
    `if (!name`, `name?` (ternary or optional chaining), or `name &&`. A bare
    `name.prop`/`name(` with nothing checked first is UNGUARDED."""
    m = re.search(r'\b' + re.escape(name) + r'\b', rest)
    if not m:
        return False
    before = rest[max(0, m.start() - 12):m.start()]
    after = rest[m.end():m.end() + 3].lstrip()
    if re.search(r'if\s*\(\s*!?\s*$', before):
        return True
    return after.startswith('?') or after.startswith('&&')


def _inside_if_condition(prefix):
    """Is position `len(prefix)` still inside the LAST `if (...)` condition opened
    in `prefix` (paren depth > 0 counting from that `if (`'s own '(')?"""
    last = None
    for m in _IF_OPEN.finditer(prefix):
        last = m
    if not last:
        return False
    depth = 0
    for ch in prefix[last.end() - 1:]:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
    return depth > 0


def _classify_guard(body, start, end, how):
    """Best-effort: is the read spanning body[start:end] guarded before use?

    `querySelectorAll` is inherently safe (a NodeList, never null) regardless of
    surrounding code. Everything else is classified from the statement enclosing
    it: an assignment (`var x = <call>;`) is guarded if the first later reference
    to `x` is if/ternary/&&-shaped (`_guarded_after_assignment`); a direct/inline
    use is guarded if immediately chained with `||`/`?.` or already inside an open
    `if (...)` condition. Anything this can't prove guard-shaped is UNGUARDED —
    conservative on purpose (a missed guard just means an extra WARN-vs-ERROR
    downgrade doesn't happen, never that a real dead read goes unreported).
    """
    if how == 'querySelectorAll':
        return True
    prev_semi = body.rfind(';', 0, start)
    prev_brace = max(body.rfind('{', 0, start), body.rfind('}', 0, start))
    stmt_start = max(prev_semi, prev_brace) + 1
    prefix = body[stmt_start:start]
    am = _ASSIGN_TAIL.search(prefix)
    if am:
        next_semi = body.find(';', end)
        rest = body[next_semi + 1:] if next_semi != -1 else ''
        return _guarded_after_assignment(rest, am.group(1))
    after = body[end:end + 3].lstrip()
    if after.startswith('||') or after.startswith('?.'):
        return True
    return _inside_if_condition(prefix)


# ───────────────────────── top-level function definitions ─────────────────────────

_TOP_FN = re.compile(r'^function\s+([A-Za-z_$][\w$]*)', re.M)
_NESTED_FN = re.compile(r'^[ \t]+function\s+([A-Za-z_$][\w$]*)', re.M)
RENDER_FN_RE = re.compile(r'^(renderCmp|renderScreen)[A-Z]')


def collect_top_level_defs(text):
    """{name: (line, body)} for every `function NAME(...) { ... }` at column 0,
    body brace-matched line by line (handles a same-line open+close; stops at the
    line where depth returns to 0 after having gone positive). Braces inside a
    string/template literal are NOT distinguished from real syntax, so a function
    whose only body content is an UNBALANCED brace inside a string would mis-scan
    — never observed on the reference project's 141 bodies, and re-litigating it
    would mean writing a JS parser, which is out of scope for a regex extractor.
    """
    lines = text.split('\n')
    defs = {}
    for i, line in enumerate(lines):
        m = re.match(r'^function\s+([A-Za-z_$][\w$]*)', line)
        if not m:
            continue
        depth, seen, end = 0, False, None
        for j in range(i, len(lines)):
            for ch in lines[j]:
                if ch == '{':
                    depth += 1
                    seen = True
                elif ch == '}':
                    depth -= 1
            if seen and depth <= 0:
                end = j + 1
                break
        body = '\n'.join(lines[i:end or i + 1])
        defs[m.group(1)] = (i + 1, body)
    return defs


def collect_nested_names(text):
    return set(_NESTED_FN.findall(text))


def collect_shell_defs(text):
    """Names the shell exposes at the top level: `function NAME`, `const NAME =
    function|(...)`, or `window.NAME = ...` — anything a render body may call
    without it being a project-local "undefined helper"."""
    names = set(re.findall(r'^\s*function\s+([A-Za-z_$][\w$]*)', text, re.M))
    names |= set(re.findall(r'^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:function|\()', text, re.M))
    names |= set(re.findall(r'window\.([A-Za-z_$][\w$]*)\s*=', text))
    return names


# ───────────────────────── generic (cross-project) naming conventions ─────────────
# See the module docstring's GENERICITY section: these are pb ECOSYSTEM naming
# conventions (documented in CLAUDE.md, or confirmed present in the shipped shell),
# never one project's own bespoke helper names.

STORE_ACCESSOR = 'pbAppStore'                        # convention, not a shell literal
SHELL_RERENDER_FN = 'renderPrototype'                 # confirmed in pb/template/prototype.html
_RERENDER_NAME_RE = re.compile(r'rerender', re.I)
_GUARD_NAME_RE = re.compile(r'^pbCan|^pbGuard|^pbAllow|Guard$|Allowed$|Valid$')
_SAVE_VERB_RE = re.compile(r'(?:Save|Submit|Post|Write|Add|Delete|Remove|Toggle|Mark|Reset'
                            r'|Apply|Grant|Revoke|Extend|Close|Approve|Reject)\w*$')
_PBUSE = re.compile(r"pbUse\(\s*['\"]([a-z0-9][a-z0-9-]*)['\"]")
_INLINE_WIRE = re.compile(r'''on\w+=\\?["'][^"']*?\b([A-Za-z_$][\w$]*)\s*\(''')
_SHELL_VERB_RE = re.compile(r'\bdata-(action|nav|go|toast|roles|validate|required|minlength|redirect)\b')
_STORE_READ = re.compile(re.escape(STORE_ACCESSOR) + r'\(\)\.([A-Za-z_]\w*)')
_STORE_WRITE = re.compile(re.escape(STORE_ACCESSOR) + r'\(\)\.([A-Za-z_]\w*)[\w.\[\]\'"]*\s*(?:=[^=]|\.push\(|\.splice\()')
_NAV_TARGET_RES = (re.compile(r"data-nav=\\?[\"']([\w-]+)"),
                   re.compile(r"data-go=\\?[\"']([\w-]+)"),
                   re.compile(r"setProtoScreen\(\s*['\"]([\w-]+)"))
_OVERLAY_RE = re.compile(r'drawer|modal|dialog|popover|sheet')


# ───────────────────────── registry / owner index ─────────────────────────────────

def _load_registry(project_dir):
    with open(os.path.join(project_dir, 'registry.json'), encoding='utf-8') as f:
        return json.load(f)


def build_owner_index(registry):
    """{normalized renderSrc: [owner, ...]} — a LIST because one render body can
    back more than one registry item (see OWNERSHIP in the module docstring)."""
    owner = collections.defaultdict(list)
    for c in registry.get('components') or []:
        if isinstance(c, dict) and c.get('renderSrc'):
            owner[os.path.normpath(c['renderSrc'])].append(
                {'kind': 'component', 'id': c.get('id'), 'level': c.get('level'), 'scope': c.get('scope')})
    for s in registry.get('screens') or []:
        if isinstance(s, dict) and s.get('renderSrc'):
            owner[os.path.normpath(s['renderSrc'])].append(
                {'kind': 'screen', 'id': s.get('id'), 'level': 'page', 'scope': 'screen'})
    return owner


def _owners_for(owner_index, rel_path):
    found = owner_index.get(os.path.normpath(rel_path))
    if found:
        return found
    return [{'kind': 'file', 'id': rel_path, 'level': None, 'scope': None}]


# ───────────────────────── main extraction ─────────────────────────────────────

def default_shell_path():
    """The plugin's own prototype shell, resolved from this file — the same trick serve.py
    uses. Returns None when it is not there (a stripped install, a bare checkout)."""
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.normpath(os.path.join(here, '..', 'template', 'prototype.html'))
    return cand if os.path.isfile(cand) else None


def extract(project_dir, shell_path=None):
    """Derive the logic graph for the pb project at `project_dir`.

    `shell_path` is optional (a project can be analyzed with no shell reference —
    tests do this); when given, its markup counts as a valid producer/consumer
    source ('SHELL') and its top-level names are excluded from "undefined helper".
    Deterministic: same files in, byte-identical JSON out (every list is sorted;
    nothing depends on set/dict iteration order or wall-clock time).
    """
    registry = _load_registry(project_dir)
    owner_index = build_owner_index(registry)

    body_paths = sorted(glob.glob(os.path.join(project_dir, 'render', '*', '*.js')))
    texts = {}          # rel_path -> comment-stripped text
    owners_by_rel = {}  # rel_path -> [owner, ...]
    for p in body_paths:
        rel = os.path.relpath(p, project_dir)
        texts[rel] = strip_comments(_read(p))
        owners_by_rel[rel] = _owners_for(owner_index, rel)

    # Resolve the shell. DEFAULTING MATTERS MORE THAN IT LOOKS: the shell defines pbUse,
    # pbToast, pbEscape, pbResetSandbox, pbSortTable and friends, so analysing a project
    # WITHOUT one makes every shell-provided global look undefined. Measured on a real
    # project: 6 false L-UNDEF errors and 1 false L-DEADSEAM, exit 2 — the exact
    # false-positive class this tool exists to avoid, produced by its own default path.
    # So the default is the plugin's own shell, resolved from __file__ the way serve.py
    # resolves it, and `shell_resolved` records whether we actually got one.
    shell_text = ''
    if shell_path is None:
        shell_path = default_shell_path()
    if shell_path and os.path.isfile(shell_path):
        shell_text = strip_comments(_read(shell_path))

    # ---- producers (whole file — markup is emitted throughout a render body) ----
    shell_resolved = bool(shell_text)
    prod = ProducerIndex()
    for rel, text in texts.items():
        prod.scan(text, [o['id'] for o in owners_by_rel[rel]])
    if shell_text:
        prod.scan(shell_text, ['SHELL'])

    # ---- top-level defs per file (+ nested names, for the undefined-helper check) ----
    defs_by_name = collections.defaultdict(list)   # name -> [rel_path, ...]
    body_of = {}                                   # (rel_path, name) -> body text
    line_of = {}                                   # (rel_path, name) -> def line
    nested_names = set()
    calls_index = collections.defaultdict(lambda: collections.defaultdict(int))  # name -> rel -> count
    for rel, text in texts.items():
        for name, (line, body) in collect_top_level_defs(text).items():
            defs_by_name[name].append(rel)
            body_of[(rel, name)] = body
            line_of[(rel, name)] = line
        nested_names |= collect_nested_names(text)
        for m in re.finditer(r'\b([A-Za-z_$][\w$]*)\s*\(', text):
            calls_index[m.group(1)][rel] += 1
    shell_defs = collect_shell_defs(shell_text) if shell_text else set()

    all_names = set(defs_by_name)

    # ---- handlers: every top-level NON-render function ----
    handlers = []
    for name, rels in sorted(defs_by_name.items()):
        if RENDER_FN_RE.match(name):
            continue
        for rel in rels:  # duplicates (len(rels) > 1) get one handler entry per file
            body = body_of[(rel, name)]
            line = line_of[(rel, name)]
            owners = owners_by_rel[rel]
            local_calls, cross_calls = collections.Counter(), collections.Counter()
            for m in re.finditer(r'\b([A-Za-z_$][\w$]*)\s*\(', body):
                callee = m.group(1)
                if callee == name or callee not in all_names:
                    continue
                (local_calls if rel in defs_by_name[callee] else cross_calls)[callee] += 1

            reads = []
            for kind, token, how, start, end in iter_reads(body):
                reads.append({
                    'kind': kind, 'token': token, 'how': how,
                    'producers': prod.producers_of(kind, token),
                    'guarded': _classify_guard(body, start, end, how),
                    'line': line + body[:start].count('\n'),
                })
            seen_rt = set()
            dedup_reads = []
            for r in reads:
                key = (r['kind'], r['token'])
                if key in seen_rt:
                    continue
                seen_rt.add(key)
                dedup_reads.append(r)

            store_slices = set(_STORE_READ.findall(body))
            store_writes = set(_STORE_WRITE.findall(body)) & store_slices
            called_names = set(local_calls) | set(cross_calls)
            rerender = sorted(({SHELL_RERENDER_FN} & called_names)
                              | {n for n in called_names if _RERENDER_NAME_RE.search(n)})
            guards = sorted({n for n in list(local_calls) + list(cross_calls) if _GUARD_NAME_RE.search(n)})
            is_toast = bool(re.search(r'\bpbToast\s*\(', body))
            called_from = sorted({r for r, t in texts.items() if r != rel and re.search(r'\b%s\s*\(' % re.escape(name), t)})
            wired_inline = sorted({r for r, t in texts.items() if re.search(
                r'''on\w+=\\?["'][^"']*\b%s\s*\(''' % re.escape(name), t)})
            savey = bool(_SAVE_VERB_RE.search(name))
            nav_targets = sorted(set(re.findall(r"setProtoScreen\(\s*['\"]([\w-]+)", body)))

            handlers.append({
                'name': name, 'file': rel, 'line': line, 'length': body.count('\n') + 1,
                'bodyHash': hashlib.sha256(body.encode('utf-8')).hexdigest(),
                'owners': sorted(({'kind': o['kind'], 'id': o['id']} for o in owners),
                                 key=lambda o: (o['kind'], o['id'])),
                'calls': dict(sorted(cross_calls.items())),
                'localCalls': dict(sorted(local_calls.items())),
                'reads': dedup_reads,
                'slices': sorted(store_slices),
                'writes': sorted(store_writes),
                'via': {},  # filled below (transitive access needs the full handler set first)
                'rerender': rerender,
                'nav': nav_targets,
                'toast': is_toast,
                'guards': guards,
                'calledFrom': called_from,
                'wiredInline': wired_inline,
                'isSave': bool(store_writes) or (bool(store_slices) and (savey or is_toast) and bool(rerender)),
                'exported': bool(called_from) or bool(wired_inline),
            })

    # ---- transitive store access (two hops: a helper that calls a slice-toucher) ----
    by_key = {(h['file'], h['name']): h for h in handlers}
    direct = {k: set(h['slices']) for k, h in by_key.items()}
    name_to_keys = collections.defaultdict(list)
    for (rel, name) in by_key:
        name_to_keys[name].append((rel, name))
    for _hop in range(2):
        for key, h in by_key.items():
            via = collections.defaultdict(set)
            for callee in list(h['calls']) + list(h['localCalls']):
                for ckey in name_to_keys.get(callee, []):
                    for slice_ in direct.get(ckey, ()):
                        if slice_ not in direct[key]:
                            via[slice_].add(callee)
            for slice_, helpers in via.items():
                h['via'].setdefault(slice_, set()).update(helpers)
                direct[key].add(slice_)
        for key, h in by_key.items():
            h['slices'] = sorted(direct[key])
    for h in handlers:
        h['via'] = {k: sorted(v) for k, v in sorted(h['via'].items())}

    # ---- slices{}: writers/readers, now that transitive access is folded in ----
    slices = collections.defaultdict(lambda: {'writers': set(), 'readers': set()})
    for h in handlers:
        for slice_ in h['slices']:
            writer = slice_ in h['writes'] or (h['isSave'] and slice_ not in h['via'])
            (slices[slice_]['writers'] if writer else slices[slice_]['readers']).add(h['name'])
            if writer and slice_ not in h['writes']:
                h['writes'] = sorted(set(h['writes']) | {slice_})

    handlers.sort(key=lambda h: (h['file'], h['line'], h['name']))
    handlers_by_name = collections.defaultdict(list)
    for h in handlers:
        handlers_by_name[h['name']].append(h)

    # ---- dead seam: a read with NO producer anywhere, grouped by (kind, token) ----
    dead = collections.defaultdict(list)
    for h in handlers:
        for r in h['reads']:
            if not r['producers']:
                dead[(r['kind'], r['token'])].append({
                    'file': h['file'], 'handler': h['name'], 'line': r['line'],
                    'how': r['how'], 'guarded': r['guarded'],
                })
    dead_seam = []
    for (kind, token), occurrences in sorted(dead.items()):
        occurrences = sorted(occurrences, key=lambda o: (o['file'], o['line']))
        dead_seam.append({
            'kind': kind, 'token': token, 'occurrences': occurrences,
            'guarded': all(o['guarded'] for o in occurrences),
        })

    # ---- items[]: every registry component AND screen (never fewer — see OWNERSHIP) ----
    items = []
    for kind, key in (('component', 'components'), ('screen', 'screens')):
        for entry in registry.get(key) or []:
            if not isinstance(entry, dict) or not entry.get('renderSrc'):
                continue
            rel = os.path.normpath(entry['renderSrc'])
            text = texts.get(rel)
            if text is None:
                continue
            cid = entry.get('id')
            composes = sorted(set(_PBUSE.findall(text)))
            wired = sorted({n for n in set(_INLINE_WIRE.findall(text)) if n in handlers_by_name})
            read_by = sorted({h['name'] for h in handlers
                              if any(cid in r['producers'] for r in h['reads'])} - set(wired))
            own_logic = sorted({h['name'] for h in handlers if h['file'] == rel})
            shell_verbs = sorted(set(_SHELL_VERB_RE.findall(text)))
            items.append({
                'kind': kind, 'id': cid,
                'level': entry.get('level') if kind == 'component' else 'page',
                'scope': entry.get('scope') if kind == 'component' else 'screen',
                'file': rel, 'lines': text.count('\n') + 1,
                'composes': composes, 'composedBy': [],  # filled below
                'wires': wired, 'readBy': read_by, 'ownLogic': own_logic,
                'shellVerbs': shell_verbs, 'hasRules': text.count(':has('),
            })
    composed_by = collections.defaultdict(set)
    for it in items:
        for c in it['composes']:
            composed_by[c].add(it['id'])
    for it in items:
        it['composedBy'] = sorted(composed_by.get(it['id'], ()))
    items.sort(key=lambda it: (it['kind'], it['id']))

    # ---- navigation graph ----
    nav = _build_nav(registry, texts, items)

    # ---- stats ----
    render_count = sum(1 for n in defs_by_name if RENDER_FN_RE.match(n))
    total_fns = sum(len(v) for v in defs_by_name.values())
    undefined = _find_undefined(calls_index, defs_by_name, shell_defs, nested_names)
    duplicates = {n: sorted(v) for n, v in defs_by_name.items() if len(v) > 1}
    bodies_with_logic = len({h['file'] for h in handlers})
    cross_file_helpers = sum(1 for n, rels in defs_by_name.items()
                             if any(rel not in rels for rel in calls_index.get(n, {})))

    stats = {
        'totalFunctions': total_fns,
        'renderFunctions': render_count,
        'handlers': len(handlers),
        'crossFileHelpers': cross_file_helpers,
        'bodiesWithLogic': bodies_with_logic,
        'undefined': len(undefined),
        'duplicates': len(duplicates),
        'exported': sum(1 for h in handlers if h['exported']),
        'saves': sum(1 for h in handlers if h['isSave']),
        'slices': len(slices),
        'deadReads': len(dead_seam),
    }

    return {
        'handlers': handlers,
        'items': items,
        'slices': {k: {'writers': sorted(v['writers']), 'readers': sorted(v['readers'])}
                  for k, v in sorted(slices.items())},
        'nav': nav,
        'deadSeam': dead_seam,
        'undefined': {n: sorted(files) for n, files in sorted(undefined.items())},
        'duplicates': duplicates,
        'stats': stats,
        # Whether a shell was actually read. The undefined-helper check is MEANINGLESS
        # without one — the shell is where pbUse/pbToast/pbEscape live — so the checker
        # must skip that check rather than report every shell global as undefined.
        'shellResolved': shell_resolved,
        'shellPath': shell_path if shell_resolved else None,
    }


def _find_undefined(calls_index, defs_by_name, shell_defs, nested_names):
    """Calls to a `pb*`-named function that is defined NOWHERE (body, shell, or a
    nested closure). Scoped to the `pb*` naming convention deliberately: without
    it, every call to a JS builtin or third-party global (`Array.isArray`,
    `setTimeout`, …) would also need checking against `defs_by_name` and mostly
    read as "undefined" — the exact kind of noise this tool exists to avoid. See
    the module docstring's GENERICITY note: `pb*` is the shared pb runtime/helper
    convention, not this project's own choice.
    """
    undefined = {}
    for name, files in calls_index.items():
        if name.startswith('pb') and name not in defs_by_name and name not in shell_defs \
                and name not in nested_names:
            undefined[name] = files
    return undefined


def _build_nav(registry, texts, items):
    screen_ids = {s['id'] for s in registry.get('screens') or [] if isinstance(s, dict)}
    sidebar_rel = next((r for r in texts if r.replace('\\', '/').endswith('/sidebar.js')
                        or r.replace('\\', '/') == 'render/components/sidebar.js'), None)
    hubs = []
    if sidebar_rel:
        text = texts[sidebar_rel]
        item_rx = re.compile(r"\{\s*key:\s*'([\w-]+)'\s*,\s*label:\s*'([^']*)'[^{}]*?"
                             r"(?:roles:\s*'([^']*)')?[^{}]*?\}")
        child_spans = []
        for m in re.finditer(r"children:\s*\[", text):
            depth, i = 1, m.end()
            while i < len(text) and depth:
                depth += {'[': 1, ']': -1}.get(text[i], 0)
                i += 1
            labels = re.findall(r"label:\s*'([^']*)'", text[max(0, m.start() - 400):m.start()])
            child_spans.append((m.start(), i, labels[-1] if labels else 'group'))

        def span_of(pos):
            return next((c for c in child_spans if c[0] <= pos < c[1]), None)

        groups = {}
        group_order = []
        top_items = []
        for m in item_rx.finditer(text):
            key, label, roles = m.group(1), m.group(2), (m.group(3) or '').split()
            entry = {'key': key, 'label': label, 'roles': roles}
            span = span_of(m.start())
            if span:
                if span not in groups:
                    groups[span] = {'key': 'group:' + re.sub(r'\W+', '-', span[2].lower()),
                                    'label': span[2], 'roles': [], 'children': []}
                    group_order.append(span)
                groups[span]['children'].append(entry)
                groups[span]['roles'] = sorted(set(groups[span]['roles']) | set(roles))
            else:
                top_items.append((m.start(), entry))
        merged = [(span[0], groups[span]) for span in group_order] + top_items
        hubs = [entry for _, entry in sorted(merged, key=lambda x: x[0])]

    composed_by = {it['id']: it['composedBy'] for it in items}

    def screens_owning(oid, seen=None):
        seen = seen or set()
        if oid in screen_ids:
            return {oid}
        out = set()
        for parent in composed_by.get(oid, []):
            if parent not in seen:
                seen.add(parent)
                out |= screens_owning(parent, seen)
        return out

    edges = set()
    active_parent = {}
    item_by_file = {it['file']: it['id'] for it in items}
    for rel, text in texts.items():
        owner_id = item_by_file.get(rel, rel)
        targets = set()
        for rx in _NAV_TARGET_RES:
            targets |= set(rx.findall(text))
        for target in targets & screen_ids:
            for src in screens_owning(owner_id):
                if src != target:
                    edges.add((src, target))
        if owner_id in screen_ids:
            m = re.search(r"activeScreenId:\s*'([\w-]+)'", text)
            if m and m.group(1) != owner_id:
                active_parent[owner_id] = m.group(1)

    children = collections.defaultdict(list)
    parent = {}
    for a, b in sorted(edges):
        children[a].append(b)
        parent.setdefault(b, a)
    for b, a in sorted(active_parent.items()):
        if b not in parent:
            parent[b] = a
            children[a].append(b)
    for a in children:
        children[a] = sorted(set(children[a]))

    level0 = [h['key'] for h in hubs if h['key'] in screen_ids]
    level0 += [c['key'] for h in hubs for c in h.get('children', []) if c['key'] in screen_ids]
    depth = {}
    frontier = collections.deque((k, 0) for k in level0)
    while frontier:
        key, d = frontier.popleft()
        if key in depth:
            continue
        depth[key] = d
        for child in children.get(key, []):
            frontier.append((child, d + 1))

    overlays = {}
    for s in registry.get('screens') or []:
        if not isinstance(s, dict) or not s.get('renderSrc'):
            continue
        text = texts.get(os.path.normpath(s['renderSrc']), '')
        composed = set(_PBUSE.findall(text))
        overlays[s['id']] = sorted(c for c in composed if _OVERLAY_RE.search(c)
                                   and c not in ('drawer-footer', 'drawer-header'))

    return {
        'hubs': hubs,
        'edges': [list(e) for e in sorted(edges)],
        'parent': dict(sorted(parent.items())),
        'children': dict(sorted(children.items())),
        'depth': dict(sorted(depth.items())),
        'overlays': dict(sorted(overlays.items())),
        'activeParent': dict(sorted(active_parent.items())),
    }


# ───────────────────────── CLI ─────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    out_path = None
    shell_path = None
    if '--out' in args:
        i = args.index('--out')
        out_path = args[i + 1]
        args = args[:i] + args[i + 2:]
    if '--shell' in args:
        i = args.index('--shell')
        shell_path = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        sys.exit('usage: logic_extract.py <project-dir> [--shell <prototype.html>] [--out <file>]')
    graph = extract(args[0], shell_path=shell_path)
    text = json.dumps(graph, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"logic_extract: {graph['stats']} -> {out_path}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
