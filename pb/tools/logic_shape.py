#!/usr/bin/env python3
"""
logic_shape.py — which visual would a prose rule become? (logic visuals)

A rule in UX Design -> Logic is drawn from structure: `states[]`, `invariants[]`, `blocks[]`.
A rule written only as prose draws nothing. This module reads that prose and names the block
types the sentences already describe, so the shell can say "Looks like: steps, async" and
`logic_check.py` can say "give it structure with /pb:clarify". It never writes anything and
never decides — a suggestion is a hint, not a finding.

    suggest(rule, roles=None) -> [{"type": <block type>, "why": <matched phrase, <= 80 chars>}]
    suggest_all(registry)     -> {rule_id: [...]}   (only rules that have suggestions)

CLI:  logic_shape.py <registry.json> [--rule ID] [--json]      (stdlib only, Python 3.9+)

TEXT READ: title, summary, decision.question/chose/why, invariants[].must/when/message.

PRECISION OVER RECALL. A type fires on ONE strong signal (a phrase that is nearly always that
shape) or on TWO DISTINCT weak signals (a single weak keyword never fires). Strong signals:

  lifecycle  a chain `A -> B -> C` of three states (arrow or ->)
  steps      `s0 ... s4`, `step 1 ... step 2`, numbered `1. ... 2.`, "never fewer steps",
             `first ... then ... then`.   weak: then, step(s), wizard, flow of
  nav        bottom bar/nav, tab bar, back control, pushed.   weak: tab(s), back button, push, stack
  branches   `when/if ... shows/renders ... otherwise/else`.   weak: otherwise/else, shows
  async      succeeded ... failed (either order), optimistic.   weak: pending, succeeded,
             failed, partial, retry, in flight, timeout
  cases      two or more `if/when X then Y` rows, "first match", "top-down"
  timeline   `N days/hours before/after`, `expires in N`.   weak: deadline, within N days,
             overdue, due date, ISO date
  matrix     two or more role names (meta.roles; else common ones) AND a verb (can, cannot,
             may, approves, only)
  order      `sorts by ... then`, oldest/newest first, tie-break.   weak: sort(s) by, priority, then by
  ladder     falls back to, fallback, `then ... then ... otherwise/default`.   weak: defaults to,
             prefer, if missing/absent/empty
  placement  never (shown) on.   weak: home, shown on, lives on, appears (only) on
  scope      only ... untouched/unchanged, never reaches, does not affect/touch, untouched
  validation UPPER_SNAKE error codes, must be between.   weak: required, must be/not, at least N,
             at most N, max/maximum.  With invariants[] present only a code in the prose counts
  gate       disabled until, stays off/disabled until, blocks submit, enabled only when/once.
             weak: disabled, greyed out
  formula    `a x b`, `a / b` (times or division sign), `x = a + b`.
             weak: sum of, percent of, %, =, multipl*, divid*
  params     two or more `number + unit` phrases (px, ms, s, h, days, %, items)
  inputs     shift-click, double-click, Cmd/Ctrl+key.   weak: Enter, Esc, Tab, Space, drag,
             keyboard, shortcut
  effects    toast, `updates ... screen/page/tab`, `writes ... store/slice/record/field`.
             weak: writes, ripple
  edges      empty state, no results, offline, error state, loading state.   weak: loading,
             empty, error, nothing to show

SKIPPED when the rule already has it: a block of that type; `lifecycle` when the rule has
states[] or is a state-machine; `matrix` when kind is matrix; `validation` when invariants[]
carry the structure (see above). Suggestions are ranked strong-first, then in a fixed type
order, and capped at 5, so the output is deterministic.
"""
import json
import re
import sys

MAX_SUGGESTIONS = 5
DEFAULT_ROLES = ("admin", "editor", "viewer", "owner", "member", "guest", "manager", "reviewer")

# Fixed order = the shell's stacking order (flow, tables, values, effects).
TYPE_ORDER = ("lifecycle", "steps", "nav", "branches", "async", "cases", "timeline", "matrix",
              "order", "ladder", "placement", "scope", "validation", "gate", "formula",
              "params", "inputs", "effects", "edges")

I = re.IGNORECASE
S = r"[^.\n]"   # a sentence-bounded gap

# type -> (strong patterns, weak patterns). A pattern is (regex, flags).
_SPEC = {
    "steps": (
        [r"\bs\d\b" + S + r"{0,40}\bs\d\b", r"\bstep\s*\d\b" + S + r"{0,60}\bstep\s*\d\b",
         r"(?:^|\s)\(?1[.)]\s+\S" + S + r"{2,}\s\(?2[.)]\s+\S", r"\bnever fewer (?:than \d+ )?steps\b",
         r"\bfirst\b" + S + r"{1,60}\bthen\b" + S + r"{1,60}\bthen\b"],
        [r"\bthen\b", r"\bsteps?\b", r"\bwizard\b", r"\bflow of\b"]),
    "nav": (
        [r"\bbottom (?:bar|nav\w*)\b", r"\btab bar\b", r"\bback control\b", r"\bpushed\b"],
        [r"\btabs?\b", r"\bback (?:button|arrow)\b", r"\bpush(?:es)?\b", r"\bstack\b"]),
    "branches": (
        [r"\b(?:when|if)\b" + S + r"{3,60}\b(?:shows?|renders?|displays?)\b" + S + r"{1,80}\b(?:otherwise|else)\b"],
        [r"\b(?:otherwise|else)\b", r"\b(?:shows?|renders?|displays?)\b"]),
    "async": (
        [r"\bsucceed(?:s|ed)\b" + S + r"{0,60}\bfail(?:s|ed|ure)?\b", r"\bfail(?:s|ed|ure)?\b" + S + r"{0,60}\bsucceed(?:s|ed)\b",
         r"\boptimistic\b"],
        [r"\bpending\b", r"\bsucceed(?:s|ed)\b", r"\bfail(?:s|ed|ure)\b", r"\bpartial(?:ly)?\b",
         r"\bretry\b|\bretries\b", r"\bin flight\b", r"\btime[sd]? ?out\b"]),
    "timeline": (
        [r"\b\d+\s*(?:hours?|h|days?|d|weeks?|min(?:utes?)?)\s+(?:before|after)\b", r"\bexpires?\s+in\s+\d+\s*\w+"],
        [r"\bdeadline\b", r"\bwithin\s+\d+\s*(?:hours?|h|days?|d|weeks?)\b", r"\boverdue\b",
         r"\bdue date\b", r"\b\d{4}-\d{2}-\d{2}\b"]),
    "order": (
        [r"\bsort(?:s|ed)?\s+by\b" + S + r"{1,80}\bthen\b", r"\b(?:oldest|newest|latest)\s+first\b", r"\btie-?break\w*\b"],
        [r"\bsort(?:s|ed)?\s+by\b", r"\bpriority\b", r"\bthen by\b", r"\border(?:ed)? by\b"]),
    "ladder": (
        [r"\bfalls?\s+back\s+(?:to|on)\b", r"\bfallbacks?\b",
         r"\bthen\b" + S + r"{1,40}\bthen\b" + S + r"{1,60}\b(?:otherwise|default)\b"],
        [r"\bdefaults? to\b", r"\bprefer(?:s|red|ence)?\b", r"\bif (?:missing|absent|empty|unset)\b"]),
    "placement": (
        [r"\bnever\s+(?:shown\s+)?on\b"],
        [r"\bhome\b", r"\bshown on\b", r"\blives on\b", r"\bappears (?:only )?on\b"]),
    "scope": (
        [r"\bonly\b" + S + r"{1,60}\b(?:untouched|unchanged)\b", r"\bnever reaches\b",
         r"\bdoes(?: not|n't)\s+(?:affect|touch)\b", r"\buntouched\b"],
        []),
    "validation": (
        [r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b", r"\bmust be between\b"],
        [r"\brequired\b", r"\bmust (?:be|not)\b", r"\bat least \d", r"\bat most \d", r"\bmax(?:imum)?\b"]),
    "gate": (
        [r"\bdisabled until\b", r"\bstays? (?:off|disabled) until\b", r"\bblocks? (?:the )?submi\w+",
         r"\benabled (?:only )?(?:when|once|after)\b"],
        [r"\bdisabled\b", r"\bgrey?ed out\b"]),
    "formula": (
        [r"\w\s*[×÷]\s*[\w(]", r"\w\s+/\s+\w", r"\b\w+\s*=\s*[^=\s]" + S + r"{0,30}[+\-*/×÷]"],
        [r"\bsum of\b", r"\bpercent(?:age)? of\b", r"%", r"=", r"\bmultipl\w+", r"\bdivid\w+"]),
    "inputs": (
        [r"\bshift-?\s?click", r"\bdouble-?\s?click", r"(?:\bCmd|\bCtrl|⌘)\s*\+\s*\w"],
        [r"\bEnter\b", r"\bEsc(?:ape)?\b", r"\bTab\b", r"\bSpace\b", r"\bdrag(?:s|ging)?\b",
         r"\bkeyboard\b", r"\bshortcut\b"]),
    "effects": (
        [r"\btoast\b", r"\bupdates?\b" + S + r"{0,40}\b(?:screen|page|tab|view)s?\b",
         r"\bwrites?\b" + S + r"{0,40}\b(?:store|slice|record|field)\b"],
        [r"\bwrites?\b", r"\bripples?\b"]),
    "edges": (
        [r"\bempty state\b", r"\bno results\b", r"\boffline\b", r"\berror state\b", r"\bloading state\b"],
        [r"\bloading\b", r"\bempty\b", r"\berror\b", r"\bnothing to show\b"]),
}
# Patterns that must match case-sensitively (key names, error codes).
_CASE_SENSITIVE = {"validation": 0, "inputs": 1}

_COMPILED = {}
for _t, (_strong, _weak) in _SPEC.items():
    _cs = _t in _CASE_SENSITIVE
    _flags = 0 if _cs else I
    if _t == "validation":
        # strong[0] (the code) is case-sensitive, the rest are not
        _COMPILED[_t] = ([re.compile(_strong[0])] + [re.compile(p, I) for p in _strong[1:]],
                         [re.compile(p, I) for p in _weak])
    elif _t == "inputs":
        # shift/double-click read case-insensitively; key names exactly as written
        _COMPILED[_t] = ([re.compile(p, I) for p in _strong], [re.compile(p) for p in _weak])
    else:
        _COMPILED[_t] = ([re.compile(p, _flags) for p in _strong], [re.compile(p, _flags) for p in _weak])

_CHAIN = re.compile(r"[\w-]+\s*(?:→|->)\s*[\w-]+\s*(?:→|->)\s*[\w-]+")
_FROM_TO = re.compile(r"\b(?:status|stage|state)\b" + S + r"{0,40}\bfrom\b" + S + r"{1,30}\bto\b", I)
_ARROW = re.compile(r"\w\s*(?:→|->)\s*\w")
_CASE_ROW = re.compile(r"\b(?:if|when)\b" + S + r"{3,80}?(?:,\s*|\s+)(?:then\b|→|->)", I)
_CASE_STRONG = re.compile(r"\bfirst[- ]match(?:es)?\b|\btop-down\b", I)
_PARAM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?\s*(?:px|ms|sec(?:onds?)?|s|h|hours?|days?|items?)\b|(?<![\w.])\d+(?:\.\d+)?\s*%", I)
_VERB = re.compile(r"\b(?:can|cannot|can't|may|may not|approves?|approved|only)\b", I)


def _clean(m, text):
    s = re.sub(r"\s+", " ", m.group(0)).strip()
    return s if len(s) <= 80 else s[:79].rstrip() + "…"


def _texts(rule):
    d = rule.get("decision") if isinstance(rule.get("decision"), dict) else {}
    prose = [rule.get("title"), rule.get("summary"), d.get("question"), d.get("chose"), d.get("why")]
    inv = []
    for i in rule.get("invariants") or []:
        if isinstance(i, dict):
            inv += [i.get("must"), i.get("when"), i.get("message")]
    ok = lambda xs: "\n".join(x for x in xs if isinstance(x, str) and x.strip())  # noqa: E731
    return ok(prose), ok(inv)


def _generic(t, text):
    """(strength, phrase) or None: one strong match, or two distinct weak ones."""
    strong, weak = _COMPILED[t]
    for rx in strong:
        m = rx.search(text)
        if m:
            return (1, _clean(m, text))
    hits = []
    for rx in weak:
        m = rx.search(text)
        if m:
            hits.append(m)
    if len(hits) >= 2:
        return (0, " + ".join(_clean(m, text) for m in hits[:2])[:80])
    return None


def _lifecycle(text):
    m = _CHAIN.search(text)
    if m:
        return (1, _clean(m, text))
    a, b = _FROM_TO.search(text), _ARROW.search(text)
    if a and b:
        return (0, _clean(a, text))
    return None


def _cases(text):
    rows = _CASE_ROW.findall(text)
    m = _CASE_STRONG.search(text)
    if m:
        return (1, _clean(m, text))
    if len(rows) >= 2:
        first = _CASE_ROW.search(text)
        return (1, _clean(first, text))
    return None


def _params(text):
    seen, phrases = set(), []
    for m in _PARAM.finditer(text):
        k = re.sub(r"\s+", "", m.group(0).lower())
        if k not in seen:
            seen.add(k)
            phrases.append(re.sub(r"\s+", " ", m.group(0)))
    if len(seen) >= 2:
        return (0, ", ".join(phrases)[:80])
    return None


def _matrix(text, roles):
    low = text.lower()
    found = []
    for r in roles:
        r = str(r).strip().lower()
        if r and r not in found and re.search(r"\b%s\b" % re.escape(r), low):
            found.append(r)
    v = _VERB.search(text)
    if len(found) >= 2 and v:
        return (1, ("%s + %s, %s" % (found[0], found[1], v.group(0).lower()))[:80])
    return None


def _present(rule):
    """Block types the rule already carries, including kind-level equivalents."""
    have = set()
    for b in rule.get("blocks") or []:
        if isinstance(b, dict) and b.get("type"):
            have.add(b["type"])
    if rule.get("kind") == "state-machine" or rule.get("states"):
        have.add("lifecycle")
    if rule.get("kind") == "matrix":
        have.add("matrix")
    if "states" in have:
        have.add("lifecycle")
    return have


def suggest(rule, roles=None):
    """Block types the rule's prose describes but its structure lacks. See module docstring."""
    if not isinstance(rule, dict):
        return []
    prose, inv = _texts(rule)
    text = (prose + "\n" + inv).strip()
    if not text:
        return []
    have = _present(rule)
    has_inv = bool(inv)
    roles = list(roles) if roles else list(DEFAULT_ROLES)
    found = []
    for n, t in enumerate(TYPE_ORDER):
        if t in have:
            continue
        if t == "lifecycle":
            r = _lifecycle(text)
        elif t == "cases":
            r = _cases(text)
        elif t == "params":
            r = _params(text)
        elif t == "matrix":
            r = _matrix(text, roles)
        elif t == "validation":
            # invariants already carry the structure; then only a code written in the prose counts
            r = None
            if has_inv:
                m = _COMPILED["validation"][0][0].search(prose)
                r = (1, _clean(m, prose)) if m else None
            else:
                r = _generic("validation", text)
        else:
            r = _generic(t, text)
        if r:
            found.append((-r[0], n, {"type": t, "why": r[1]}))
    found.sort(key=lambda x: (x[0], x[1]))
    return [f[2] for f in found[:MAX_SUGGESTIONS]]


def _rules(registry):
    reg = registry if isinstance(registry, dict) else {}
    rules = (reg.get("ia") or {}).get("rules") if isinstance(reg.get("ia"), dict) else None
    rules = rules or reg.get("rules") or []
    return [r for r in rules if isinstance(r, dict)] if isinstance(rules, list) else []


def _role_names(registry):
    out = []
    for r in ((registry.get("meta") or {}).get("roles") or []) if isinstance(registry, dict) else []:
        if isinstance(r, dict):
            out += [r.get("name"), r.get("id")]
        elif isinstance(r, str):
            out.append(r)
    return [x for x in out if x]


def suggest_all(registry):
    """{rule_id: [{"type","why"}, ...]} — only rules with at least one suggestion; rule order kept."""
    roles = _role_names(registry) or None
    out = {}
    for r in _rules(registry):
        rid = r.get("id")
        if not rid or r.get("status") == "superseded":
            continue
        s = suggest(r, roles)
        if s:
            out[str(rid)] = s
    return out


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print("usage: logic_shape.py <registry.json> [--rule ID] [--json]")
        return 0 if args else 2
    as_json = "--json" in args
    rule_id = None
    if "--rule" in args:
        rule_id = args[args.index("--rule") + 1]
    with open(args[0], encoding="utf-8") as f:
        reg = json.load(f)
    shapes = suggest_all(reg)
    if rule_id:
        shapes = {k: v for k, v in shapes.items() if k == rule_id}
    if as_json:
        print(json.dumps(shapes, ensure_ascii=False, indent=2))
        return 0
    if not shapes:
        print("no shape suggestions")
        return 0
    for rid, items in shapes.items():
        print("%s: looks like %s" % (rid, ", ".join(i["type"] for i in items)))
        for i in items:
            print("    %-10s %s" % (i["type"], i["why"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
