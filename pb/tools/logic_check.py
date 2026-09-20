#!/usr/bin/env python3
"""
logic_check.py — gate the logic graph `logic_extract.py` derives (I4).

Reuses lint_registry.py's Finding / severity / exit-code SHAPE (0 clean, 1 warnings,
2 errors) as a plain convention, not a dependency — this file imports nothing from
lint_registry.py and lint_registry.py is never modified to know about this one. It
runs alongside `pb/tools/lint_registry.py`, not instead of it: lint checks registry
SHAPE (kebab ids, required `level`, DTCG tokens, …); this checks LOGIC (does the
code contradict itself, or contradict what it declares about itself).

THE FALSE-POSITIVE DISCIPLINE (the whole point of this file — read before editing)
Every check here is exactly one of two kinds:
  Kind A — derived vs. derived: a contradiction INSIDE the code, with no outside
           opinion involved. ERROR, or WARN when the code itself guards the
           contradiction at runtime (see `_classify_guard` in logic_extract.py).
  Kind B — declared vs. observed: a registry field claims something a render body's
           actual pbUse() composition doesn't back up. Both sides are always printed.
           An ABSENT declaration is never a finding — only a PRESENT one that
           disagrees with reality is (see `check_elements`/`check_anatomy`).
No check here gates on a count, a ratio, or a diff against a captured baseline —
the one baseline-shaped feature (`--freeze`) is opt-in, prints its own results, and
is never part of the default run or its exit code. The reference project's own
gates/README.md is blunt about why: "when a gate and the code disagree, suspect the
gate first — in this project it was wrong every time but one." A baseline is also
provably the wrong tool for the seam check specifically: this project's baseline
gate MISSED all 10 of its real dead reads, because the baseline was re-captured
*after* the deletion that orphaned them — a fresh cross-check has no such blind spot.

CHECKS
  Kind A  L-DEADSEAM   a DOM handle a handler reads that no body and not the shell
                       produces (logic_extract.py already applied the four producer
                       guards — see its module docstring — so what's left here is
                       real). WARN if every occurrence is guarded at runtime
                       (`if (el)`, `el ? … : …`, `el && …`, `a.closest(x) || b`, or
                       a `querySelectorAll` result, which is never null), else ERROR.
  Kind A  L-UNDEF      a `pb*`-named helper called but defined nowhere (no body, not
                       the shell, not a nested closure).
  Kind A  L-DUPDEF     the same top-level function name defined in two files.
  Kind A  L-RULEREF    a declared rule cites a function name — implementedBy[],
                       readers[], implemented[].name, invariants[].enforcedBy — that no
                       render body defines. The rule still renders as the explanation of
                       how the product works while pointing at nothing.
  Kind A  L-HAS-R1     a `:has()`-toggled element (its selector's SUBJECT — the last
                       compound, not every class the rule mentions) also carries an
                       inline `display` in the same tag on the same line. Inline
                       beats a class rule at any specificity, so the reveal never
                       fires. Fires ONLY on the subject, and ONLY when `class=` and
                       `style=` share one tag — see `_leaf_targets`/`check_has_rules`.
  Kind A  L-HAS-R2     a `:has()`-revealed `<tr>` sets a `display` other than
                       `table-row` (flex/block drop it out of the column grid).
  Kind B  L-ELEMENTS   a screen's `elements[].orgId` names a component the screen's
                       render body never `pbUse()`s.
  Kind B  L-ANATOMY    a component's `anatomy.parts[].orgId` names a component its
                       own render body never `pbUse()`s.
  INFO    L-HAS-R3     a group toggle hidden with `display:none` (keyboard-unreach-
                       able; prefer `position:absolute;opacity:0`) — a NOTE per the
                       brief, never a finding, never counted toward the exit code.
  INFO    L-HAS-R4     `:has()` rule count per file — information, never a gate.

`--explain <CODE>` prints a code's rationale and its known false-positive modes —
required for every code above, so `tests/logic_check.py`'s corpus can quote it.

`--freeze {capture,compare} <file> <project-dir>` hashes every handler's body
(`bodyHash`, from logic_extract.py) to prove a change touched no logic — e.g. a
pure CSS/copy pass. It is a side command: it never runs as part of the default
check, has no bearing on the exit code of a normal run, and is not itself a
"standing gate" — nothing calls it automatically.

Usage:
  logic_check.py <project-dir> [--shell <prototype.html>]
  logic_check.py --explain <CODE>
  logic_check.py --freeze capture <out.json>   <project-dir> [--shell <path>]
  logic_check.py --freeze compare <base.json>  <project-dir> [--shell <path>]
Exit:  0 clean · 1 warnings only · 2 at least one error  (freeze: 0 same · 1 diff)
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logic_extract as extract_mod  # noqa: E402  (sibling module; never the reverse)

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


class Finding:
    __slots__ = ("severity", "code", "where", "msg")

    def __init__(self, severity, code, where, msg):
        self.severity = severity
        self.code = code
        self.where = where
        self.msg = msg

    def line(self):
        return f"{self.severity} [{self.code}] {self.where}: {self.msg}"


# ───────────────────────── --explain text (one entry per code this file defines) ──

EXPLAIN = {
    "L-DEADSEAM": """\
L-DEADSEAM — a handler reads a DOM handle (id/class/data-*) that no render body and
not the shell ever produces, after logic_extract.py's four producer guards:
  1. an id handed to a composed atom as a PROP        — pbUse('input', {id: 'x'})
  2. an id built through a VARIABLE prefix            — var t = 'x-' + id
  3. a runtime write                                  — setAttribute/dataset/.id=
  4. idPrefix:/name: props an atom expands per-option
Kind A (derived vs. derived — no baseline, no declaration involved). WARN when every
occurrence is guarded at runtime (if(el)/ternary/&&/closest(...)||fallback, or the
read is a querySelectorAll, which is never null); ERROR when at least one occurrence
is not provably guarded. Known false-positive mode: any of the four forms above
missed by the extractor reads as a false dead-seam — see logic_extract.py's
ProducerIndex.scan(). A guard shape this checker doesn't recognize (something other
than if/ternary/&&/||-fallback/querySelectorAll) reads as UNGUARDED, i.e. ERROR
instead of WARN — a real but narrower false positive than the finding itself.""",
    "L-UNDEF": """\
L-UNDEF — a `pb*`-named function is called but defined nowhere (no render body, not
the shell, not a nested closure). Kind A. Scoped to the `pb*` naming convention on
purpose: without it, every call to a JS builtin or third-party global would also
need checking against this project's own definitions and would mostly read as
"undefined" — exactly the false-positive flood this scoping avoids. Known
false-positive mode: a project-local helper that does NOT follow the `pb*`
convention is invisible to this check by design (a real typo there is a miss, not
a false positive — it simply isn't in scope).""",
    "L-DUPDEF": """\
L-DUPDEF — the same top-level function name is defined at column 0 in two different
files; the second silently shadows the first wherever both are loaded. Kind A.
Known false-positive mode: none identified against the reference project (measured
0); a same-named function nested INSIDE another function (not top-level) is
correctly excluded, since it is a distinct closure, not a redefinition.""",
    "L-RULEREF": """\
L-RULEREF — a rule in `ia.rules[]` names a function that is defined nowhere in the
render bodies. Rules link themselves to their implementation by NAME (implementedBy[],
readers[], implemented[].name, and a constraint's invariants[].enforcedBy); nothing
re-checked those names, so a rename left the Logic tab presenting a rule as the
explanation of how the product works while its link pointed at a function that no
longer existed. Kind A: the graph knows every top-level definition, so a name absent
from it is absent — no baseline and no outside opinion involved. Skipped entirely when
the graph derived no handlers (an empty graph would flag every name). Known
false-positive mode: a rule may legitimately cite a function that lives in the SHELL
rather than a render body (pbUse, pbToast); those are not in handlers[] and would read
as missing — cite the render-body function that calls them instead."""
,
    "L-HAS-R1": """\
L-HAS-R1 — a `:has()`-toggled element carries an inline `display` in `style=`
alongside `class=` in the SAME tag on the SAME line. Inline style beats any class
rule regardless of specificity, so the `:has()` reveal silently never fires. Kind A.
Fires only for the selector's SUBJECT (the last compound selector — not every class
the rule mentions; an intermediate ancestor in the same selector may legitimately
carry its own inline display) and only when class= and style= share one tag on one
line. Known false-positive modes fixed here on purpose: (a) a long backward
character-count lookback for `class=` can grab the attribute off a NEIGHBOURING
element instead of the toggled one — this checker requires both attributes in the
same `<tag ...>` span, not a lookback distance; (b) taking every class token after
the closing `)` instead of the selector's subject flags legitimate intermediate
wrapper elements that carry their own unrelated inline display.""",
    "L-HAS-R2": """\
L-HAS-R2 — a `:has()`-revealed `<tr>` sets `display` to something other than
`table-row` (flex/block drops the row out of the table's column grid). Kind A.
Known false-positive mode: none identified against the reference project (measured
0 alongside R1).""",
    "L-ELEMENTS": """\
L-ELEMENTS — a screen's `elements[].orgId` names a component id the screen's own
render body never composes via pbUse(). Kind B: both sides are printed (the
declared orgId + its element's label, and the full observed pbUse() set). Only
elements that DECLARE an orgId are checked; a screen with no elements[], or an
element with no orgId, produces no finding at all — absence of a declaration is
never a finding, only a present one that disagrees with the body is.""",
    "L-ANATOMY": """\
L-ANATOMY — a component's `anatomy.parts[].orgId` names a component id its own
render body never composes via pbUse(). Kind B, same rule as L-ELEMENTS: only parts
that declare an orgId are checked, and a component with no anatomy/parts produces
no finding.""",
    "L-HAS-R3": """\
L-HAS-R3 — a group toggle (a class matching *toggle*/*radio*/*check*) is hidden
with `display:none` rather than `position:absolute;opacity:0`; `display:none`
removes it from the tab order so its paired `:checked` state becomes unreachable by
keyboard. This is a NOTE per the brief, not a Finding — it never affects the exit
code and is not counted as a warning or error, because it is one plausible reading
of a class-name pattern, not a derived contradiction or a declared/observed
mismatch.""",
    "L-HAS-R4": """\
L-HAS-R4 — the number of `:has()` rules per file. INFORMATION ONLY. This project
uses `:has()` deliberately and heavily (dozens of rules per file in places, from
loops emitting one rule per item) — the count is never, under any circumstance, a
gate; printing it is purely so a human skimming output has context.""",
}


def explain(code):
    text = EXPLAIN.get(code)
    if text is None:
        print(f"no such code: {code!r}. Known codes: {', '.join(sorted(EXPLAIN))}", file=sys.stderr)
        return 2
    print(text)
    return 0


# ───────────────────────── Kind A: dead seam ───────────────────────────────────

def check_dead_seam(graph):
    findings = []
    for entry in graph.get("deadSeam", []):
        kind, token = entry["kind"], entry["token"]
        where = f"{kind}={token!r}"
        occ_desc = "; ".join(f"{o['file']}:{o['line']} in {o['handler']}() via {o['how']}"
                             for o in entry["occurrences"])
        sev = WARN if entry["guarded"] else ERROR
        guard_note = "every occurrence is runtime-guarded" if entry["guarded"] \
            else "at least one occurrence is NOT provably guarded"
        findings.append(Finding(
            sev, "L-DEADSEAM", where,
            f"read by {len(entry['occurrences'])} occurrence(s) — {occ_desc} — "
            f"but no render body and not the shell produces it ({guard_note})"))
    return findings


# ───────────────────────── Kind A: undefined helper / duplicate def ────────────

def check_undefined(graph):
    """L-UNDEF — a `pb*` helper called but defined nowhere.

    FAILS SAFE WITHOUT A SHELL. `pbUse`, `pbToast`, `pbEscape`, `pbResetSandbox` and
    `pbSortTable` are all defined in the pb shell, so with no shell to read, every one
    of them looks undefined. Measured on a real project: 6 false ERRORs and exit 2 — a
    tool whose own default path invents seven defects is worse than no tool, and this
    is exactly the false-positive class the whole design exists to prevent.

    `logic_extract` now defaults to the plugin's own shell, so this is the belt to that
    braces: if a shell genuinely could not be read, the check does not run and says so.
    """
    if not graph.get("shellResolved"):
        return [Finding(INFO, "L-UNDEF-SKIP", "shell",
                        "no shell could be read, so shell-provided globals (pbUse, pbToast, "
                        "pbEscape, …) cannot be told apart from genuinely undefined helpers — "
                        "the undefined-helper check did NOT run. Pass --shell <prototype.html>.")]
    return [Finding(ERROR, "L-UNDEF", f"fn={name!r}", f"called from {', '.join(files)} but defined nowhere")
            for name, files in sorted(graph.get("undefined", {}).items())]


def check_duplicates(graph):
    return [Finding(ERROR, "L-DUPDEF", f"fn={name!r}", f"defined at top level in more than one file: {', '.join(files)}")
            for name, files in sorted(graph.get("duplicates", {}).items())]


def check_rule_refs(graph, registry):
    """Kind A — every function name a declared rule cites must resolve in the derived graph.

    A rule links itself to the code that implements it by NAME: `implementedBy[]`, `readers[]`,
    `implemented[].name`, and a constraint's `invariants[].enforcedBy`. Nothing re-checked those
    names, so a rename left the rule pointing at a function that no longer exists while the Logic
    tab went on rendering it as the explanation of how the product works. Derived-vs-derived, so
    ERROR: the graph knows every top-level definition, and a name absent from it is absent.

    The rule half is authored, but the NAMES are claims about derived facts — which is why this
    is Kind A and not the declared-vs-observed Kind B (where a baseline can legitimately lag).
    """
    known = {h["name"] for h in graph.get("handlers", [])}
    if not known:
        return []                       # no graph derived — the check would be noise, not signal
    rules = ((registry.get("ia") or {}).get("rules")) or registry.get("rules") or []
    out = []
    for rule in (rules if isinstance(rules, list) else []):
        if not isinstance(rule, dict):
            continue
        rid = rule.get("id")
        cites = [("implementedBy", n) for n in (rule.get("implementedBy") or [])]
        cites += [("readers", n) for n in (rule.get("readers") or [])]
        cites += [("implemented[].name", (e or {}).get("name")) for e in (rule.get("implemented") or [])]
        cites += [("invariants[].enforcedBy", (i or {}).get("enforcedBy"))
                  for i in (rule.get("invariants") or [])]
        for field, name in cites:
            if isinstance(name, str) and name and name not in known:
                out.append(Finding(
                    ERROR, "L-RULEREF", f"rule={rid!r} {field}",
                    f"cites {name!r}, which is defined nowhere in the render bodies — "
                    f"renamed or deleted, and the rule still points at it"))
    return out


# ───────────────────────── Kind A: the :has() reveal contract ───────────────────
# A fresh implementation of the same four rules the reference project's battle-
# tested gates/has_rules.py verified (R1-R4; see that file's own header for the
# failure history) — not a copy of it (reference data is read-only and never
# copied into a committed file), independently re-derived from first principles
# against the same measured target: 80 rule sites / 222 occurrences / 0 R1+R2 / 1 R3.

_HAS_RULE = re.compile(r"([^{}]*:has\([^{}]*\)[^{}]*)\{([^{}]*)\}")
_DISPLAY_DECL = re.compile(r"(?<![-\w])display\s*:\s*([a-z-]+)")
_TAG_OPEN = re.compile(r"<\w+\b[^<>]*>")
_STYLE_ATTR = re.compile(r"""style\s*=\s*\\?["']([^"'\\]*)""")
_CLASS_ATTR = re.compile(r"""class\s*=\s*\\?["']([^"'\\]*)""")
_TR_SELECTOR = re.compile(r"\btr[.\s]|\btr\.")
_TOGGLE_CLASS = re.compile(r"\.([\w-]*(?:toggle|radio|check)[\w-]*)\s*\{([^{}]*)\}", re.I)


def _leaf_targets(selector):
    """The class/id tokens a `:has()` declaration block actually applies to: the
    selector's SUBJECT (its final compound, after the last combinator) — not every
    class the whole rule mentions. An intermediate ancestor earlier in the selector
    may legitimately carry its own, unrelated inline display; crediting it to this
    rule is exactly the false-positive mode this function exists to avoid."""
    tail = selector.split(")")[-1]
    if not tail.strip():
        return set()
    subject = re.split(r"[\s>+~]+", tail.strip())[-1]
    return set(re.findall(r"[.#]([\w-]+)", subject))


def check_has_rules(project_dir):
    findings = []
    per_file = {}
    r3_notes = []
    for path in sorted(glob.glob(os.path.join(project_dir, "render", "*", "*.js"))):
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        rel = os.path.relpath(path, project_dir)
        # Prose-only comment strip (whole-line `//`), matching the reference gate's
        # own scope: a JS block comment inside these bodies is rare and full
        # tokenizing isn't needed to find `:has()` rules and inline attributes.
        text = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
        rules = _HAS_RULE.findall(text)
        if rules:
            per_file[rel] = len(rules)

        toggled_with_display = set()
        for selector, decl in rules:
            disp = _DISPLAY_DECL.search(decl)
            targets = _leaf_targets(selector)
            if disp:
                toggled_with_display |= targets
            if _TR_SELECTOR.search(selector) and disp and disp.group(1) != "table-row":
                findings.append(Finding(
                    ERROR, "L-HAS-R2", f"{rel}",
                    f"revealed <tr> uses display:{disp.group(1)} (must be table-row) — "
                    f"{selector.strip()[:110]}"))

        # R1: class= and style= sharing ONE tag on ONE line, targeting a subject
        # this file's own :has() rules assign `display` to.
        if toggled_with_display:
            for line in text.split("\n"):
                for tag in _TAG_OPEN.finditer(line):
                    span = tag.group(0)
                    sm = _STYLE_ATTR.search(span)
                    cm = _CLASS_ATTR.search(span)
                    if not (sm and cm and _DISPLAY_DECL.search(sm.group(1))):
                        continue
                    hit = set(re.findall(r"[\w-]+", cm.group(1))) & toggled_with_display
                    if hit:
                        findings.append(Finding(
                            ERROR, "L-HAS-R1", f"{rel}",
                            f"inline display on :has()-toggled {sorted(hit)} — {span[:120]}"))

        for m in _TOGGLE_CLASS.finditer(text):
            decl = m.group(2)
            d = _DISPLAY_DECL.search(decl)
            if d and d.group(1) == "none" and "position" not in decl:
                r3_notes.append(f"{rel}: .{m.group(1)} uses display:none (prefer position:absolute;opacity:0)")

    for rel, count in sorted(per_file.items(), key=lambda kv: -kv[1]):
        findings.append(Finding(INFO, "L-HAS-R4", rel, f"{count} :has() rule(s) in this file (information only)"))
    for note in r3_notes:
        findings.append(Finding(INFO, "L-HAS-R3", note.split(":")[0], note.split(": ", 1)[1]))
    return findings


# ───────────────────────── Kind B: declared vs. composed ───────────────────────

def _load_registry_with_specs(project_dir):
    """registry.json, with `anatomy` re-inlined from a component's specSrc sidecar
    (schema 10) when present. The sidecar always WINS over any inline copy —
    mirroring lint_registry.py's own `_resolve_specs` (`item[k] = v` unconditionally)
    — because the sidecar is the file CLAUDE.md says to "edit directly"; an inline
    `anatomy` surviving next to a `specSrc` is leftover pre-migration (or hand-
    edited) state, not a second opinion. Concretely: this reference project's own
    `leaf-config-drawer` carries a stale inline anatomy with 5 parts (table,
    typography, avatar, tabs, progress) that its CURRENT sidecar no longer declares
    — they moved into the child component `leaf-detail-body` — and preferring the
    inline copy over the sidecar reproduced exactly that as 5 false L-ANATOMY
    findings before this function was fixed to prefer the sidecar, per lint's own
    precedent. Best-effort otherwise: a missing/unreadable sidecar just leaves that
    item's anatomy as whatever (if anything) was already inline, and no anatomy at
    all reads as "no declaration" to check_anatomy — never a finding either way.
    """
    with open(os.path.join(project_dir, "registry.json"), encoding="utf-8") as f:
        reg = json.load(f)
    for c in reg.get("components") or []:
        if isinstance(c, dict) and c.get("specSrc"):
            try:
                with open(os.path.join(project_dir, c["specSrc"]), encoding="utf-8") as f:
                    sidecar = json.load(f)
                if isinstance(sidecar, dict) and "anatomy" in sidecar:
                    c["anatomy"] = sidecar["anatomy"]
            except (OSError, json.JSONDecodeError):
                pass
    return reg


def check_elements(graph, registry):
    findings = []
    composes_by_id = {it["id"]: set(it["composes"]) for it in graph.get("items", []) if it["kind"] == "screen"}
    for screen in registry.get("screens") or []:
        if not isinstance(screen, dict):
            continue
        sid = screen.get("id")
        composed = composes_by_id.get(sid)
        if composed is None:
            continue  # no render body reachable — nothing to compare against
        for el in screen.get("elements") or []:
            if not isinstance(el, dict):
                continue
            org = el.get("orgId")
            if not org:
                continue  # no declaration made for this element -> never a finding
            if org not in composed:
                findings.append(Finding(
                    WARN, "L-ELEMENTS", f"screen={sid!r} element={el.get('id')!r}",
                    f"declares orgId={org!r} ({el.get('label', '')[:80]!r}) but the render body's "
                    f"composed set is {sorted(composed) or '(empty)'}"))
    return findings


def check_anatomy(graph, registry):
    findings = []
    composes_by_id = {it["id"]: set(it["composes"]) for it in graph.get("items", []) if it["kind"] == "component"}
    for comp in registry.get("components") or []:
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id")
        composed = composes_by_id.get(cid)
        if composed is None:
            continue
        anatomy = comp.get("anatomy")
        parts = (anatomy.get("parts") if isinstance(anatomy, dict) else None) or []
        for part in parts:
            if not isinstance(part, dict):
                continue
            org = part.get("orgId")
            if not org:
                continue
            if org not in composed:
                findings.append(Finding(
                    WARN, "L-ANATOMY", f"component={cid!r} part#{part.get('n')}",
                    f"declares orgId={org!r} ({part.get('name', '')!r}) but the render body's "
                    f"composed set is {sorted(composed) or '(empty)'}"))
    return findings


# ───────────────────────── orchestration ───────────────────────────────────────

def run(project_dir, shell_path=None):
    """Run every default check; return (findings, graph) — the graph is handed
    back so a caller (or a test) can inspect it without re-extracting."""
    graph = extract_mod.extract(project_dir, shell_path=shell_path)
    registry = _load_registry_with_specs(project_dir)
    findings = []
    findings += check_dead_seam(graph)
    findings += check_undefined(graph)
    findings += check_duplicates(graph)
    findings += check_rule_refs(graph, registry)
    findings += check_has_rules(project_dir)
    findings += check_elements(graph, registry)
    findings += check_anatomy(graph, registry)
    return findings, graph


def _report(findings, label, ok_msg):
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    infos = [f for f in findings if f.severity == INFO]
    for f in findings:
        print(f.line())
    gating = errors or warns
    if not gating:
        if infos:
            print(f"✓ {label}: {ok_msg} ({len(infos)} information note(s) above, never gating)")
        else:
            print(f"✓ {label}: {ok_msg}")
        return 0
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s), {len(infos)} note(s)")
    return 2 if errors else 1


# ───────────────────────── --freeze (opt-in, side command, never a gate) ────────

def _freeze_capture(graph):
    return {f"{h['file']}::{h['name']}": h["bodyHash"] for h in graph["handlers"]}


def freeze_capture(project_dir, shell_path, out_path):
    graph = extract_mod.extract(project_dir, shell_path=shell_path)
    snapshot = _freeze_capture(graph)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"--freeze capture: {len(snapshot)} handler(s) -> {out_path}")
    return 0


def freeze_compare(project_dir, shell_path, baseline_path):
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    graph = extract_mod.extract(project_dir, shell_path=shell_path)
    current = _freeze_capture(graph)
    added = sorted(set(current) - set(baseline))
    removed = sorted(set(baseline) - set(current))
    changed = sorted(k for k in set(current) & set(baseline) if current[k] != baseline[k])
    for k in added:
        print(f"  + {k} (new handler)")
    for k in removed:
        print(f"  - {k} (handler removed)")
    for k in changed:
        print(f"  ~ {k} (body changed)")
    if not (added or removed or changed):
        print("--freeze compare: identical — no top-level logic entity changed")
        return 0
    print(f"--freeze compare: {len(added)} added, {len(removed)} removed, {len(changed)} changed")
    return 1


# ───────────────────────── CLI ─────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--explain" in args:
        i = args.index("--explain")
        if i + 1 >= len(args):
            sys.exit("usage: logic_check.py --explain <CODE>")
        return explain(args[i + 1])

    shell_path = None
    if "--shell" in args:
        i = args.index("--shell")
        shell_path = args[i + 1]
        args = args[:i] + args[i + 2:]

    if "--freeze" in args:
        i = args.index("--freeze")
        rest = args[:i] + args[i + 1:]
        if len(rest) != 3 or rest[0] not in ("capture", "compare"):
            sys.exit("usage: logic_check.py --freeze {capture|compare} <file> <project-dir> [--shell <path>]")
        mode, path, project_dir = rest
        if mode == "capture":
            return freeze_capture(project_dir, shell_path, path)
        return freeze_compare(project_dir, shell_path, path)

    if len(args) != 1:
        sys.exit("usage: logic_check.py <project-dir> [--shell <prototype.html>]  |  "
                 "logic_check.py --explain <CODE>  |  "
                 "logic_check.py --freeze {capture|compare} <file> <project-dir>")
    findings, graph = run(args[0], shell_path=shell_path)
    return _report(findings, "logic_check.py", f"clean — {args[0]} ({graph['stats']['handlers']} handler(s) scanned)")


if __name__ == "__main__":
    sys.exit(main())
