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
            out.append(_h(3, _esc(r.get("title") or r.get("id") or "rule")))
            if r.get("id"):
                out.append("`%s`" % _esc(r["id"]))
                out.append("")
            for label, key in (("When", "when"), ("Then", "then"), ("Because", "why"),
                               ("Shown in", "displayedIn"), ("States", "states")):
                v = r.get(key)
                if not v:
                    continue
                out.append("- **%s** — %s" % (label, _join(v, fmt=_code) if isinstance(v, list) else _esc(v)))
            out.append("")
    else:
        out.append(_h(2, "Declared rules"))
        out.append("None declared. Rules live in `registry.json` → `ia.rules[]`; author them with "
                   "`/pb:plan` or `/pb:build`. An empty section here means the product's rules are "
                   "only in people's heads — not that it has none.")

    jobs = ia.get("jobs") if isinstance(ia, dict) else None
    if jobs:
        out.append(_h(2, "Jobs (%d)" % len(jobs)))
        out += ["", "| Job | Surface |", "|---|---|"]
        for j in jobs:
            if isinstance(j, dict):
                out.append("| %s | %s |" % (_esc(j.get("title") or j.get("id")), _join(j.get("screens"))))
            else:
                out.append("| %s | — |" % _esc(j))

    layers = ia.get("layers") if isinstance(ia, dict) else None
    if layers:
        out.append(_h(2, "Layers (%d)" % len(layers)))
        out += ["", "| Layer | Kind |", "|---|---|"]
        for lyr in layers:
            if isinstance(lyr, dict):
                out.append("| %s | %s |" % (_esc(lyr.get("id") or lyr.get("title")), _code(lyr.get("kind"))))
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
