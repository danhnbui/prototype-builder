"""
0010_tradeoff_rules — schema 11 → schema 12.

A trade-off IS a rule. It was already recorded as one everywhere except the schema: D-30 moved
`meta.tradeoffs[]` out of Project Summary and into UX Design → Logic *because* it belonged beside
the rules it produced, and then left it as a separate array with a separate view and a separate
capture step in `/pb:clarify`. Two shapes for one thing, and the half that answers "why is this
rule what it is" sat in a tab of its own that you had to know to open.

So the array collapses into `ia.rules[]`, and every rule may now carry the one thing a rule could
not say for itself:

    decision: { question, options[], chose, why, status?, supersededOn?, affects? }

`options[]` is the part no rule can carry on its own — what LOST. That is the whole reason a
trade-off was a separate record, and it is now a field.

A migrated trade-off becomes a rule of `kind: 'decision'`: a rule we have decided but not yet
expressed as a machine, a matrix or a constraint. That is an honest state, and the kind is a
standing invitation to upgrade it — the renderer draws the decision block for EVERY kind, so
adding `states[]` to one of these later loses nothing.

`[SUPERSEDED <date>]` in the title — a convention the projects invented because the schema had no
status field (D-30 §2) — is read here and written into `decision.status` / `decision.supersededOn`,
because now there is one. The title comes out clean.

Provenance, and why the rollback is lossless
--------------------------------------------
Each migrated rule is stamped `origin: "tradeoff"`. `down()` turns exactly those back into
`meta.tradeoffs[]` entries and removes them from `ia.rules[]` — but a rule that has been EDITED
since (its kind changed, states or invariants added, the decision rewritten) is left in place and
reported, the same discipline 0009 applies to a hand-edited sidecar. Rolling a schema back is not
a reason to throw away work someone did after the migration.

One caveat, and it is the whole of it: `options` was authored either as a list or as an
`"A | B"` string, and `down()` always writes the string — the form the template, the golden and
`/pb:clarify` all used. A list-authored trade-off therefore comes back as the equivalent string.
Both were legal and the old renderer read both, so nothing is lost but the authoring style.

The field is EMPTIED, not deleted (`AGENTS.md` §3: never remove a field in place — add, then
deprecate, and let a major release do the removing). `meta.tradeoffs` stays in the registry as
`[]`, the way `staleness` and `others` stay: nothing reads it, nothing writes it, and the shell's
"not yet migrated" banner keys off it being non-empty, so an emptied field is silent.

up(reg):
  - each meta.tradeoffs[] entry → an ia.rules[] entry with a decision{} block, `kind: 'decision'`,
    `origin: 'tradeoff'`; a `[SUPERSEDED …]` title prefix becomes decision.status
  - empty meta.tradeoffs (the data moved; the field stays, per AGENTS.md §3)
  - stamp meta.schemaVersion = 12
down(reg):
  - every ia.rules[] entry still shaped as up() left it → back to meta.tradeoffs[]; edited ones kept
  - stamp meta.schemaVersion = 11
"""
import re
import unicodedata

FROM = 11
TO = 12

_SUPERSEDED = re.compile(r"^\s*\[SUPERSEDED([^\]]*)\]\s*", re.I)


def _slug(text, taken, index=0):
    """A rule id from a title: kebab, ascii, unique against the ids already in the slice.

    Accented text is TRANSLITERATED first, not stripped. A title is very often not in English —
    the project this was measured on is written in Vietnamese — and dropping the marks character
    by character turns `Luồng tạo chu kỳ` into `lu-ng-t-o-chu-k`, an id nobody can read, search
    or type. NFD splits each letter from its marks so the base letter survives; `đ` carries no
    combining mark and needs saying out loud. A title with no latin letters at all (Chinese,
    Japanese, Korean) yields nothing to transliterate, so it falls back to its position."""
    folded = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:48].strip("-")
    base = base or ("decision-%d" % (index + 1))
    slug, n = base, 2
    while slug in taken:
        slug, n = "%s-%d" % (base, n), n + 1
    taken.add(slug)
    return slug


def _options(value):
    """`options` is authored either as a list or as a 'A | B | C' string. Keep every branch:
    the ones that lost are the reason this record exists."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [p.strip() for p in value.split("|") if p.strip()]
    return []


def _rule_from(tradeoff, taken, index=0):
    raw = (tradeoff.get("title") or "").strip()
    sup = _SUPERSEDED.match(raw)
    title = _SUPERSEDED.sub("", raw).strip() or "Untitled decision"
    decision = {}
    if tradeoff.get("question"):
        decision["question"] = tradeoff["question"]
    opts = _options(tradeoff.get("options"))
    if opts:
        decision["options"] = opts
    if tradeoff.get("decision"):
        decision["chose"] = tradeoff["decision"]
    if tradeoff.get("why"):
        decision["why"] = tradeoff["why"]
    if tradeoff.get("tabsAffected"):
        decision["affects"] = tradeoff["tabsAffected"]
    if sup:
        decision["status"] = "superseded"
        when = (sup.group(1) or "").strip()
        if when:
            decision["supersededOn"] = when
    # No `summary`. It would be the same string as decision.chose — on a real project those run to
    # several lines, and a card that prints them twice is not a summary, it is an echo. The decision
    # block says what now holds; a one-line summary is something a human adds later if they want one.
    rule = {
        "id": _slug(title, taken, index),
        "title": title,
        "kind": "decision",
        "decision": decision,
        "origin": "tradeoff",
    }
    # Anything the trade-off carried that this mapping does not name is kept verbatim rather than
    # dropped — an unrecognised field is someone's data, not noise.
    extra = {k: v for k, v in tradeoff.items()
             if k not in ("title", "question", "options", "decision", "why", "tabsAffected")}
    if extra:
        rule["decision"]["extra"] = extra
    return rule


def _tradeoff_from(rule):
    """The inverse of _rule_from, for down()."""
    d = rule.get("decision") or {}
    title = rule.get("title") or ""
    if d.get("status") == "superseded":
        title = "[SUPERSEDED%s] %s" % ((" " + d["supersededOn"]) if d.get("supersededOn") else "", title)
    out = {"title": title}
    if d.get("question"):
        out["question"] = d["question"]
    if d.get("options"):
        out["options"] = " | ".join(d["options"])
    if d.get("chose"):
        out["decision"] = d["chose"]
    if d.get("why"):
        out["why"] = d["why"]
    if d.get("affects"):
        out["tabsAffected"] = d["affects"]
    for k, v in (d.get("extra") or {}).items():
        out.setdefault(k, v)
    return out


def _untouched(rule):
    """Is this rule still exactly what up() produced? A rule whose kind changed, or that grew
    states / transitions / invariants / links, has been worked on since — it is a rule now, and
    down() must not demote it back into a flat trade-off row."""
    if rule.get("kind") != "decision" or not isinstance(rule.get("decision"), dict):
        return False
    known = {"id", "title", "kind", "summary", "decision", "origin"}
    return not (set(rule.keys()) - known)


def up(reg, base_dir=None):
    meta = reg.setdefault("meta", {})
    tradeoffs = meta.get("tradeoffs")
    if isinstance(tradeoffs, list) and tradeoffs:
        ia = reg.get("ia")
        if not isinstance(ia, dict):
            ia = {}
            reg["ia"] = ia
        rules = ia.get("rules")
        if not isinstance(rules, list):
            rules = []
            ia["rules"] = rules
        taken = {r.get("id") for r in rules if isinstance(r, dict) and r.get("id")}
        for i, t in enumerate(tradeoffs):
            if isinstance(t, dict):
                rules.append(_rule_from(t, taken, i))
    if "tradeoffs" in meta:
        meta["tradeoffs"] = []          # emptied, never removed — AGENTS.md §3
    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    ia = reg.get("ia") if isinstance(reg.get("ia"), dict) else {}
    rules = ia.get("rules") if isinstance(ia.get("rules"), list) else []
    back, kept, keep_rules = [], [], []
    for rule in rules:
        if isinstance(rule, dict) and rule.get("origin") == "tradeoff":
            if _untouched(rule):
                back.append(_tradeoff_from(rule))
                continue
            kept.append(rule.get("id") or "?")       # worked on since — it stays a rule
        keep_rules.append(rule)
    meta = reg.setdefault("meta", {})
    if back or "tradeoffs" in meta:
        meta["tradeoffs"] = back
    if rules:
        ia["rules"] = keep_rules
        if not keep_rules:
            del ia["rules"]
        if not ia:
            del reg["ia"]
    if kept:
        print("  note: %d migrated rule(s) kept as rules — edited since the migration: %s"
              % (len(kept), ", ".join(sorted(kept)[:5]) + (" …" if len(kept) > 5 else "")))
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1 schema 11 → 12: meta.tradeoffs[] collapses into ia.rules[] — each trade-off becomes a "
            "rule of kind 'decision' carrying decision{question, options[], chose, why}, and a "
            "[SUPERSEDED …] title prefix becomes decision.status. The field is emptied, not removed "
            "(AGENTS.md §3); rollback refills it (list-authored `options` return as 'A | B').")


def memory_notes():
    return ("A trade-off is a rule, and is now stored as one. `meta.tradeoffs[]` is emptied (the field "
            "stays, per AGENTS.md §3): every entry is now an `ia.rules[]` rule of kind 'decision', "
            "carrying `decision{ question, options[], "
            "chose, why }` — `options[]` holds what LOST, which is the one thing a rule could not say "
            "for itself.\n"
            "ANY rule may carry a decision block, whatever its kind, and the Logic tab draws it on the "
            "card. A rule of kind 'decision' is one you have decided but not yet expressed as a state "
            "machine, a matrix or a constraint — when you do, change the kind and keep the block.\n"
            "/pb:clarify no longer captures trade-offs as a separate task: it authors the rule and its "
            "decision together, and still appends one entry per decision to memory/decisions.md.")
