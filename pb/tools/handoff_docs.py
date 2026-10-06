#!/usr/bin/env python3
"""
handoff_docs.py — project the logic contract and the declared rules into Markdown.

The engineering hand-off ships two HTML files a person can open (the prototype and the
design-system site) and two Markdown files a person — or an agent, or a diff — can read:

  logic.md   what each screen and component DOES: the handlers it owns, the store slices it
             writes, the affordances it offers and why, the DOM seam it produces and reads.
  rules.md   the rules the product declares about itself: ia.rules, the IA jobs and layers,
             and a pointer at the constitution's locks.

WHY A TOOL AND NOT A PROMPT (D-23). This is arithmetic over a large set — on the project pb
was measured against, 137 contracts, 432 handlers and 14 store slices. Asking a model to
transcribe that is expensive, non-deterministic, and wrong in ways nobody can diff. Here it
is a projection: same inputs, byte-identical output, so a hand-off regenerated next month
diffs cleanly against this one.

DERIVED, NEVER AUTHORED. Everything here is computed from the render bodies plus whatever
the registry already declares. Nothing is invented and nothing is written back. No timestamp
is emitted, deliberately — a doc that changes every run cannot be diffed.

Usage:  handoff_docs.py <project-dir> [--out <dir>]        (default: <project-dir>/handoff-dev)
        handoff_docs.py <project-dir> --stdout logic|rules
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _esc(s):
    """Markdown-safe inline text: a pipe would split a table cell."""
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ").strip()


def _code(s):
    return "`%s`" % _esc(s) if s else "—"


def _join(xs, fmt=_code, sep=", ", empty="—"):
    xs = [x for x in (xs or []) if x]
    return sep.join(fmt(x) for x in xs) if xs else empty


def _join_cap(xs, cap=8, fmt=_code):
    """Same, but a cell nobody can read is not information. On the project this was measured
    against one store slice had 53 readers, which rendered as a single unbroken table cell.
    Lead with the count, name the first few, and say how many were left off."""
    xs = [x for x in (xs or []) if x]
    if not xs:
        return "—"
    head = ", ".join(fmt(x) for x in xs[:cap])
    if len(xs) <= cap:
        return "%d — %s" % (len(xs), head) if len(xs) > 1 else head
    return "%d — %s … +%d" % (len(xs), head, len(xs) - cap)


def _h(level, text):
    return "\n%s %s\n" % ("#" * level, text)


def build_logic_md(reg, graph):
    """The derived half + the authored half of every item's contract, as one document."""
    name = (reg.get("meta") or {}).get("name") or "(unnamed project)"
    items = sorted(graph.get("items") or [], key=lambda i: (i.get("kind") != "screen", i.get("id") or ""))
    handlers = {h["name"]: h for h in (graph.get("handlers") or [])}
    contracts = graph.get("contracts") or {}
    stats = graph.get("stats") or {}

    out = ["# %s — logic" % name,
           "",
           "Derived from the render bodies by `pb/tools/logic_extract.py`; written by "
           "`pb/tools/handoff_docs.py`. **Do not hand-edit** — regenerate with `/pb:handoff` "
           "(mode 2). The authored half (`writes[]`, `affordances[].why`) lives in "
           "`logic/{components,screens}/<id>.json`; everything else is computed.",
           ""]

    out.append(_h(2, "At a glance"))
    out += ["| | |", "|---|---:|"]
    for label, key in (("Screens + components", None), ("Functions total", "totalFunctions"),
                       ("Render functions", "renderFunctions"), ("Handlers", "handlers"),
                       ("Cross-file helpers", "crossFileHelpers"), ("Store slices", "slices"),
                       ("Save handlers", "saves")):
        val = len(items) if key is None else stats.get(key, 0)
        out.append("| %s | %s |" % (label, val))

    # ── store slices ──────────────────────────────────────────────────────────
    slices = graph.get("slices") or {}
    if slices:
        out.append(_h(2, "Store slices"))
        out.append("Who mutates each slice, and who reads it back.")
        out += ["", "| Slice | Writers | Readers |", "|---|---|---|"]
        for key in sorted(slices):
            s = slices[key] or {}
            out.append("| %s | %s | %s |" % (_code(key), _join_cap(s.get("writers")),
                                             _join_cap(s.get("readers"))))

    # ── navigation ────────────────────────────────────────────────────────────
    nav = graph.get("nav") or {}
    layers = nav.get("layers") if isinstance(nav, dict) else None
    if layers:
        out.append(_h(2, "Navigation layers"))
        out += ["", "| Layer | Opened by | Closed by |", "|---|---|---|"]
        for lyr in layers:
            if not isinstance(lyr, dict):
                continue
            out.append("| %s | %s | %s |" % (_code(lyr.get("id") or lyr.get("name")),
                                             _join(lyr.get("openedBy")), _join(lyr.get("closedBy"))))

    # ── per item ──────────────────────────────────────────────────────────────
    out.append(_h(2, "Per screen and component"))
    for it in items:
        cid, kind = it.get("id"), it.get("kind")
        # render.load_contracts keys on "<kind-plural>/<id>" — NOT the sidecar path. Getting
        # this wrong loses the authored half silently: the doc still renders, just without the
        # two fields no tool can derive. tests/handoff_docs.py §3 is the guard.
        c = contracts.get("%s/%s" % ("screens" if kind == "screen" else "components", cid)) or {}
        out.append(_h(3, "%s — `%s`" % (cid, kind)))
        meta_bits = [b for b in (
            ("level %s" % it.get("level")) if it.get("level") else None,
            ("scope %s" % it.get("scope")) if it.get("scope") else None,
            ("%s lines" % it.get("lines")) if it.get("lines") else None,
        ) if b]
        out.append("*%s* — `%s`" % (" · ".join(meta_bits), it.get("file") or "?"))
        out.append("")

        writes = c.get("writes") or []
        if writes:
            out.append("**Writes** (authored — static derivation cannot see a mutation inside a "
                       "store helper): %s" % _join(writes, fmt=lambda w: "`store.%s`" % _esc(w)))
            out.append("")
        affs = [a for a in (c.get("affordances") or []) if isinstance(a, dict)]
        if affs:
            out.append("**Affordances**")
            out.append("")
            for a in affs:
                why = _esc(a.get("why")) or "_no reason given_"
                out.append("- %s — %s" % (_code(a.get("id") or a.get("name")), why))
            out.append("")

        rows = [
            ("Composes", _join(it.get("composes"))),
            ("Composed by", _join_cap(it.get("composedBy"), cap=12)),
            ("Logic defined here", _join(it.get("ownLogic"), fmt=lambda n: "`%s()`" % _esc(n))),
            ("Handlers wired in its markup", _join(it.get("wires"), fmt=lambda n: "`%s()`" % _esc(n))),
            ("Handlers that read its DOM", _join(it.get("readBy"), fmt=lambda n: "`%s()`" % _esc(n))),
            ("Shell verbs used", _join(it.get("shellVerbs"))),
        ]
        out += ["| | |", "|---|---|"]
        for label, val in rows:
            if val != "—":
                out.append("| %s | %s |" % (label, val))

        own = it.get("ownLogic") or []
        detail = [handlers[n] for n in own if n in handlers]
        if detail:
            out.append("")
            out.append("| Handler | Reads | Writes |")
            out.append("|---|---|---|")
            for h in detail:
                reads = _join_cap(["%s:%s" % (r.get("kind"), r.get("token"))
                                   for r in (h.get("reads") or [])], cap=6)
                out.append("| `%s()` | %s | %s |" % (_esc(h.get("name")), reads, _join(h.get("writes"))))

    dead = graph.get("deadSeam") or []
    if dead:
        out.append(_h(2, "Dead seam"))
        out.append("A handler reads a DOM handle no markup in the project produces. Each is "
                   "either a rename that missed a caller, or markup that has not shipped yet.")
        out += ["", "| Handle | Read in |", "|---|---|"]
        for d in dead:
            occ = sorted({o.get("file") for o in (d.get("occurrences") or []) if o.get("file")})
            out.append("| `%s:%s` | %s |" % (_esc(d.get("kind")), _esc(d.get("token")), _join(occ)))

    return "\n".join(out).rstrip() + "\n"


def _cell(v):
    if isinstance(v, (dict, list)):
        return _esc(json.dumps(v, ensure_ascii=False))
    return _esc(v)


def _table(head, rows):
    out = ["", "| " + " | ".join(_esc(h) for h in head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out + [""]


def _invariants_md(items):
    rows = []
    for i in items or []:
        if not isinstance(i, dict):
            continue
        must = _esc(i.get("must"))
        if i.get("code"):
            must += " `%s`" % _esc(i["code"])
        if i.get("message"):
            must += " — “%s”" % _esc(i["message"])
        by = _code(i["enforcedBy"] + "()") if i.get("enforcedBy") else (_code(i["enforcedIn"]) if i.get("enforcedIn") else "**nothing**")
        rows.append([must, by, _cell(i.get("when") or "")])
    return _table(["Must hold", "Enforced by", "When"], rows) if rows else []


def _matrix_md(b):
    axis = ("- **Rows are roles.**", "") if b.get("axis") == "role" else ()
    return list(axis) + _matrix_table(b)


def _matrix_table(b):
    cols = b.get("cols") or []
    cells = b.get("cells") or {}
    mark = lambda v: "✓" if v is True else ("—" if v is False or v is None else _esc(v))  # noqa: E731
    return _table([b.get("rowLabel") or "role"] + cols,
                  [[_esc(r)] + [mark((cells.get(r) or {}).get(c)) for c in cols] for r in b.get("rows") or []])


def _block_md(b):
    """One `blocks[]` entry (v2.1.0) as markdown — the same shapes the Logic tab draws."""
    t = b.get("type")
    out = ["**%s**" % _esc(b["title"])] if b.get("title") else []
    if t == "cases":
        inputs = b.get("inputs") if any(isinstance(r.get("when"), dict) for r in b.get("rows") or [] if isinstance(r, dict)) else None
        head = ["#"] + (list(inputs) if inputs else [b.get("whenLabel") or "When"]) + [b.get("thenLabel") or "Then"]
        rows = []
        for n, r in enumerate([r for r in b.get("rows") or [] if isinstance(r, dict)], 1):
            when = [_cell((r.get("when") or {}).get(i, "·")) for i in inputs] if inputs else [_cell(r.get("when"))]
            rows.append([str(n)] + when + [_cell(r.get("then")) + (" (%s)" % _esc(r["tone"]) if r.get("tone") else "")])
        if b.get("else") is not None:
            e = b["else"]
            rows.append([""] + ["*otherwise*"] + [""] * ((len(inputs) - 1) if inputs else 0)
                        + [_cell(e.get("then") if isinstance(e, dict) else e)])
        out += _table(head, rows)
    elif t == "scope":
        if b.get("unit"):
            out.append("- **Scoped to:** %s" % _esc(b["unit"]))
        out += ["- **%s:** %s" % (_esc(b.get("actsLabel") or "Acts on"), _join(b.get("acts"), fmt=_esc, sep="; ")),
                "- **%s:** %s" % (_esc(b.get("untouchedLabel") or "Leaves untouched"), _join(b.get("untouched"), fmt=_esc, sep="; ")), ""]
    elif t == "placement":
        out += _table([b.get("surfaceLabel") or "Surface", "Holds", "Never"],
                      [[_esc(x.get("surface")), _join(x.get("holds"), fmt=_esc, sep="; "), _join(x.get("never"), fmt=_esc, sep="; ")]
                       for x in b.get("surfaces") or [] if isinstance(x, dict)])
    elif t == "matrix":
        out += _matrix_md(b)
    elif t == "validation":
        f = b.get("field")
        if isinstance(f, dict) and (f.get("label") or f.get("sample")):
            out.append("- **Field:** %s%s" % (_esc(f.get("label") or ""), (" (e.g. `%s`)" % _esc(f["sample"])) if f.get("sample") else ""))
        out += _invariants_md(b.get("items"))
    elif t == "formula":
        out += ["", "```", str(b.get("expr") or ""), "```"]
        out += ["- `%s` — %s" % (_esc(x.get("name")), _esc(x.get("means"))) for x in b.get("terms") or [] if isinstance(x, dict)]
        ex = b.get("example") or {}
        if ex:
            ins = ", ".join("%s = %s" % (k, v) for k, v in (ex.get("inputs") or {}).items())
            out.append("- *Example:* %s → **%s**" % (_esc(ins), _esc(ex.get("result"))))
        if b.get("split"):
            out.append("- *Split:* %s" % "; ".join("%s %s%s" % (_esc(x.get("label")), _esc(x.get("value")), (" (%s)" % _esc(x["tone"])) if x.get("tone") else "")
                                                   for x in b["split"] if isinstance(x, dict)))
        out.append("")
    elif t == "steps":
        for n, x in enumerate(b.get("items") or [], 1):
            if not isinstance(x, dict):
                out.append("%d. %s" % (n, _esc(x)))
                continue
            line = "%d. **%s**%s" % (n, _esc(x.get("label")), (" — " + _esc(x["detail"])) if x.get("detail") else "")
            if x.get("guard"):
                line += " *(guard: %s)*" % _esc(x["guard"])
            if x.get("back"):
                line += " *(back to: %s)*" % _esc(x["back"])
            out.append(line)
        oc = b.get("outcome")
        if isinstance(oc, dict) and oc.get("label"):
            out.append("- **Outcome:** %s%s" % (_esc(oc["label"]), (" — " + _esc(oc["detail"])) if oc.get("detail") else ""))
        out.append("")
    elif t == "params":
        out += _table(["Parameter", "Value", "Note"],
                      [[_esc(x.get("name")), "%s%s" % (_esc(x.get("value")), (" " + _esc(x["unit"])) if x.get("unit") else ""),
                        (_esc(x.get("note") or "") + ((" — *%s%s*" % (_esc(x["source"]), (": " + _esc(x["ref"])) if x.get("ref") else "")) if x.get("source") else ""))]
                       for x in b.get("items") or [] if isinstance(x, dict)])
    elif t == "effects":
        if b.get("writes"):
            out.append("- **Writes:** %s" % _join(["store." + str(w).replace("store.", "") for w in b["writes"]]))
        out += ["- **Also changes** %s — %s" % (_esc(x.get("screen") or x.get("on")), _esc(x.get("shows") or x.get("what")))
                for x in b.get("ripple") or [] if isinstance(x, dict)]
        toasts = b.get("toast")
        for tt in ([toasts] if isinstance(toasts, str) else (toasts or [])):
            out.append("- **Toast:** “%s”" % _esc(tt))
        out.append("")
    elif t == "swatches":
        out += _table(["State", "Means", "Token", "Value"],
                      [[_esc(x.get("label")), _esc(x.get("meaning") or ""), "`%s`" % _esc(x["token"]) if x.get("token") else "",
                        "`%s`" % _esc(x["value"]) if x.get("value") else ""]
                       for x in b.get("items") or [] if isinstance(x, dict)])
    elif t == "anatomy":
        if b.get("sample"):
            out += ["`%s`" % _esc(b["sample"]), ""]
        out += _table(["#", "Part", "Name", "Rule"],
                      [[str(i + 1), "`%s`" % _esc(x.get("text")), _esc(x.get("name") or ""),
                        _esc(x.get("rule") or "") + ((" — " + _esc(x["note"])) if x.get("note") else "")]
                       for i, x in enumerate(x for x in b.get("parts") or [] if isinstance(x, dict))])
    elif t == "examples":
        out += _table(["Input", "Renders as", "Note"],
                      [[_esc(x.get("input") or ""), "`%s`" % _esc(x.get("output")), _esc(x.get("note") or "")]
                       for x in b.get("items") or [] if isinstance(x, dict)])
    elif t == "states":
        if b.get("component"):
            out.append("- **Component:** %s" % _code(b["component"]))
        out += _table(["State", "Shows", "Tone"],
                      [[_esc(x.get("label") or x.get("key")), _esc(x.get("shows") or ""), _esc(x.get("tone") or "")]
                       for x in b.get("items") or [] if isinstance(x, dict)])
        if b.get("interaction"):
            out += ["- **Interaction states:** %s" % _join(b["interaction"]), ""]
    elif t == "nav":
        out.append("- **Tabs, in order:** %s" % " · ".join(_esc(x.get("label") or x.get("key")) if isinstance(x, dict) else _esc(x)
                                                         for x in b.get("tabs") or []))
        if b.get("pushed"):
            out.append("- **Pushed over a tab:** %s" % _join(b["pushed"], fmt=_esc, sep="; "))
        if b.get("reset"):
            out.append("- **Resets to the tab root:** %s" % _join(b["reset"], fmt=_esc, sep="; "))
        if b.get("note"):
            out.append("- %s" % _esc(b["note"]))
        out.append("")
    elif t == "branches":
        out += _table(["When", "Shows", "Tone"],
                      [[_cell(x.get("when")), _cell(x.get("shows")), _esc(x.get("tone") or "")]
                       for x in b.get("rows") or [] if isinstance(x, dict)])
        e = b.get("else")
        if e:
            out += ["- **Otherwise:** %s" % _cell(e.get("shows") if isinstance(e, dict) else e), ""]
    elif t == "async":
        if b.get("order"):
            out.append("- **Order:** %s" % " → ".join(_esc(x) for x in b["order"]))
        out += _table(["Outcome", "Label", "Copy"],
                      [[_esc(x.get("key")), _esc(x.get("label") or ""), _cell(x.get("copy") or "")]
                       for x in b.get("outcomes") or [] if isinstance(x, dict)])
        if b.get("note"):
            out += ["- %s" % _esc(b["note"]), ""]
    elif t == "timeline":
        marks = [x for x in b.get("marks") or [] if isinstance(x, dict)]
        label = {x.get("key"): x.get("label") or x.get("key") for x in marks}
        out.append("- **Marks, in time order:** %s" % " → ".join(_esc(x.get("label") or x.get("key")) for x in marks))
        out += _table(["From", "To", "Then", "Note"],
                      [[_esc(label.get(x.get("from"), x.get("from")) or "(open)"), _esc(label.get(x.get("to"), x.get("to")) or "(open)"),
                        _esc(x.get("then") or "") + (" (%s)" % _esc(x["tone"]) if x.get("tone") else ""), _esc(x.get("note") or "")]
                       for x in b.get("bands") or [] if isinstance(x, dict)])
    elif t == "order":
        for n, k in enumerate([k for k in b.get("keys") or [] if isinstance(k, dict)], 1):
            vals = (" (%s)" % " > ".join(_esc(v) for v in k["values"])) if k.get("values") else ""
            out.append("%d. **%s** %s%s" % (n, _esc(k.get("by")), _esc(k.get("dir") or "asc"), vals))
        if b.get("tiebreak"):
            out.append("- **Tie-break:** %s" % _esc(b["tiebreak"]))
        if b.get("never"):
            out.append("- **Never:** %s" % _join(b["never"], fmt=_esc, sep="; "))
        out.append("")
    elif t == "ladder":
        for n, x in enumerate(b.get("items") or [], 1):
            out.append("%d. %s" % (n, _esc(x) if not isinstance(x, dict) else
                                   "**%s**%s" % (_esc(x.get("label")), (" — " + _esc(x["detail"])) if x.get("detail") else "")))
        if b.get("fallback"):
            out.append("- **Last resort:** %s" % _esc(b["fallback"]))
        out.append("")
    elif t == "gate":
        out.append("- **%s** stays disabled until:" % _esc(b.get("control")))
        out += ["  - %s" % _esc(x.get("label") if isinstance(x, dict) else x) for x in b.get("requires") or []]
        out += ["- **Not gated:** %s%s" % (_esc(x.get("what")), (" — " + _esc(x["why"])) if x.get("why") else "")
                for x in b.get("notGated") or [] if isinstance(x, dict)]
        if b.get("message"):
            out.append("- **Message when blocked:** “%s”" % _esc(b["message"]))
        out.append("")
    elif t == "inputs":
        out += _table(["Input", "When", "Does", "Never"],
                      [[_esc(x.get("input")), _cell(x.get("when") or ""), _cell(x.get("does")), _cell(x.get("never") or "")]
                       for x in b.get("rows") or [] if isinstance(x, dict)])
    elif t == "edges":
        out += _table(["Case", "Shows", "Recovery", "Status"],
                      [[_cell(x.get("case")), _cell(x.get("shows") or ""), _cell(x.get("recovery") or ""), _esc(x.get("status") or "")]
                       for x in b.get("rows") or [] if isinstance(x, dict)])
    else:
        out += [_esc(b.get("text") or json.dumps(b, ensure_ascii=False)), ""]
    return out


def _rule_md(r):
    """A rule as the Logic tab shows it: the lead, its structure, then how it was decided."""
    out = [_h(3, _esc(r.get("title") or r.get("id") or "rule"))]
    d = r.get("decision") if isinstance(r.get("decision"), dict) else {}
    meta = ["`%s`" % _esc(r["id"])] if r.get("id") else []
    if r.get("kind"):
        meta.append(_esc(r["kind"]))
    if d.get("status") == "superseded" or r.get("status") == "superseded":
        meta.append("**superseded**%s" % ((" " + _esc(d.get("supersededOn") or r.get("supersededOn"))) if (d.get("supersededOn") or r.get("supersededOn")) else ""))
    if meta:
        out += [" · ".join(meta), ""]
    if r.get("summary"):
        out += [_esc(r["summary"]), ""]
    for label, key in (("When", "when"), ("Then", "then"), ("Because", "why"),
                       ("Shown in", "displayedIn")):
        v = r.get(key)
        if v:
            out.append("- **%s** — %s" % (label, _join(v, fmt=_code) if isinstance(v, list) else _esc(v)))
    states = r.get("states") or []
    if states and isinstance(states[0], dict):
        out += _table(["State", "Condition"], [[_esc(st.get("label") or st.get("key")), _esc(st.get("condition") or "")] for st in states])
        if r.get("transitions"):
            out.append("- **Transitions** — %s" % "; ".join("%s → %s" % (a, b) for a, b in
                                                            (t for t in r["transitions"] if isinstance(t, list) and len(t) == 2)))
    elif states:
        out.append("- **States** — %s" % _join(states, fmt=_code))
    if r.get("kind") == "matrix":
        out += _matrix_md(r)
    out += _invariants_md(r.get("invariants"))
    for b in r.get("blocks") or []:
        if isinstance(b, dict):
            out += _block_md(b)
    if d.get("chose") or d.get("why"):
        lost = [o for o in (d.get("options") or []) if o != d.get("chose")] if isinstance(d.get("options"), list) else []
        if d.get("question"):
            out.append("- **Question** — %s" % _esc(d["question"]))
        if d.get("chose"):
            out.append("- **Decided** — %s%s" % (_esc(d["chose"]), (" (over %s)" % "; ".join(_esc(o) for o in lost)) if lost else ""))
        if d.get("why"):
            out.append("- **Why** — %s" % _esc(d["why"]))
    open_ = d.get("stillOpen") if d.get("stillOpen") is not None else r.get("stillOpen")
    for q in (open_ if isinstance(open_, list) else ([open_] if open_ else [])):
        out.append("- **Still open** — %s" % _cell(q))
    for label, key in (("Superseded by", "supersededBy"), ("Supersedes", "supersedes")):
        v = d.get(key) or r.get(key)
        if v:
            out.append("- **%s** — %s" % (label, _join(v, fmt=_code) if isinstance(v, list) else _code(v)))
    out.append("")
    return out


def build_rules_md(reg, graph, has_constitution=False):
    """What the product declares about itself — authored, never derived."""
    name = (reg.get("meta") or {}).get("name") or "(unnamed project)"
    ia = graph.get("ia") if isinstance(graph.get("ia"), dict) else (reg.get("ia") or {})
    rules = graph.get("rules") or (ia.get("rules") if isinstance(ia, dict) else None) or []

    out = ["# %s — rules" % name,
           "",
           "The rules the product declares about itself. Authored, not derived: every line "
           "here was written by a person and no tool rewrites it. Written by "
           "`pb/tools/handoff_docs.py` — regenerate with `/pb:handoff` (mode 2).",
           ""]

    if rules:
        out.append(_h(2, "Declared rules (%d)" % len(rules)))
        for r in rules:
            if not isinstance(r, dict):
                out.append("- %s" % _esc(r))
                continue
            out += _rule_md(r)
    else:
        out.append(_h(2, "Declared rules"))
        out.append("None declared. Rules live in `registry.json` → `ia.rules[]`; author them with "
                   "`/pb:plan` or `/pb:build`. An empty section here means the product's rules are "
                   "only in people's heads — not that it has none.")

    jobs = ia.get("jobs") if isinstance(ia, dict) else None
    if jobs:
        out.append(_h(2, "Jobs (%d)" % len(jobs)))
        out += ["", "| Job | Roles | Surface |", "|---|---|---|"]
        for j in jobs:
            if isinstance(j, dict):
                text = ("When %s, I want to %s, so I can %s" % (j.get("when") or "…", j.get("want") or "…", j.get("so") or "…")
                        if j.get("want") else (j.get("title") or j.get("id")))
                out.append("| %s | %s | %s |" % (_esc(text), _join(j.get("roles"), fmt=_esc), _join(j.get("screens"))))
            else:
                out.append("| %s | — |" % _esc(j))

    layers = ia.get("layers") if isinstance(ia, dict) else None
    if layers:
        out.append(_h(2, "Layers (%d)" % len(layers)))
        out += ["", "| Layer | Name | Purpose |", "|---|---|---|"]
        for lyr in layers:
            if isinstance(lyr, dict):
                out.append("| %s | %s | %s |" % (_esc(lyr.get("depth", lyr.get("id"))), _esc(lyr.get("name") or lyr.get("title") or ""),
                                                 _esc(lyr.get("purpose") or lyr.get("kind") or "")))
            else:
                out.append("| %s | — |" % _esc(lyr))

    out.append(_h(2, "The locks"))
    out.append("The Stack Lock and Design System Lock — the two constraints every change is "
               "checked against — live in "
               + ("`constitution.md`, shipped beside this file."
                  if has_constitution else
                  "`memory/constitution.md` in the source project (not included in this hand-off).")
               )
    return "\n".join(out).rstrip() + "\n"


def write_docs(project_dir, out_dir):
    import logic_extract
    import render as R

    reg_path = os.path.join(project_dir, "registry.json")
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
    graph = R.load_logic(project_dir, reg) or logic_extract.extract(project_dir)
    has_const = os.path.exists(os.path.join(out_dir, "constitution.md")) or \
        os.path.exists(os.path.join(project_dir, "memory", "constitution.md"))

    os.makedirs(out_dir, exist_ok=True)
    written = []
    for fname, text in (("logic.md", build_logic_md(reg, graph)),
                        ("rules.md", build_rules_md(reg, graph, has_const))):
        path = os.path.join(out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append((path, text.count("\n") + 1))
    return written


def main():
    args = [a for a in sys.argv[1:]]
    out_dir = None
    stdout_which = None
    if "--out" in args:
        i = args.index("--out")
        out_dir = args[i + 1]
        args = args[:i] + args[i + 2:]
    if "--stdout" in args:
        i = args.index("--stdout")
        stdout_which = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        sys.exit("usage: handoff_docs.py <project-dir> [--out <dir>] [--stdout logic|rules]")
    project_dir = args[0]

    if stdout_which:
        import logic_extract
        import render as R
        with open(os.path.join(project_dir, "registry.json"), encoding="utf-8") as f:
            reg = json.load(f)
        graph = R.load_logic(project_dir, reg) or logic_extract.extract(project_dir)
        sys.stdout.write(build_logic_md(reg, graph) if stdout_which == "logic"
                         else build_rules_md(reg, graph))
        return 0

    out_dir = out_dir or os.path.join(project_dir, "handoff-dev")
    for path, lines in write_docs(project_dir, out_dir):
        print("handoff_docs: %s (%d lines)" % (path, lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
