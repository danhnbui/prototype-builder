#!/usr/bin/env python3
"""
logic_check.py (tests) — the false-positive corpus for pb/tools/logic_extract.py +
pb/tools/logic_check.py (I4).

Every fixture is a tiny, self-contained pb project (a temp dir with a registry.json
+ one or two render bodies) run through the REAL extractor and checker — not a
hand-built graph — so these tests catch a regression in the regex pipeline itself,
not just in a mocked-up call to a check function.

Two groups, matching the brief's false-positive discipline:
  1. NEGATIVE fixtures — each reproduces one known false-positive shape and asserts
     the relevant check fires ZERO times: the four dead-seam producer guards, the
     :has() selector-subject case, and the :has() inline-display same-tag case.
  2. POSITIVE fixtures — one genuine defect per check, asserting it DOES fire (a
     check that never fires on anything is not verified — only asserting silence
     would let a check that's ALWAYS silent pass every negative fixture for free).

Usage: python3 tests/logic_check.py   ·   Exit 0/1.
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import logic_extract as LE  # noqa: E402
import logic_check as LC    # noqa: E402

fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def _pascal(kebab):
    return "".join(part[:1].upper() + part[1:] for part in kebab.split("-") if part)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def make_project(root, components=(), screens=()):
    """Write a minimal-but-real pb project into `root`. Each of components/screens
    is a dict with at least {id, body}; any other keys are merged straight into the
    registry entry (e.g. `elements=[...]`, `anatomy={...}`, `level=...`)."""
    reg = {"meta": {"schemaVersion": 10}, "components": [], "screens": []}
    for spec in components:
        spec = dict(spec)
        body = spec.pop("body")
        cid = spec["id"]
        rel = "render/components/%s.js" % cid
        _write(root, rel, body)
        entry = {"renderSrc": rel, "level": "molecule", "scope": "local",
                 "renderFn": "renderCmp" + _pascal(cid)}
        entry.update(spec)
        reg["components"].append(entry)
    for spec in screens:
        spec = dict(spec)
        body = spec.pop("body")
        sid = spec["id"]
        rel = "render/screens/%s.js" % sid
        _write(root, rel, body)
        entry = {"renderSrc": rel, "renderFn": "renderScreen" + _pascal(sid)}
        entry.update(spec)
        reg["screens"].append(entry)
    _write(root, "registry.json", json.dumps(reg))
    return root


def _dead_tokens(graph):
    return {(d["kind"], d["token"]) for d in graph["deadSeam"]}


# ───────────────────────── 1a. producer guard 1 — id as a PROP ────────────────

def test_producer_prop_id():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "s1",
            "body": (
                "function renderScreenS1() {\n"
                "  return pbUse('input', { id: 'cq-search' });\n"
                "}\n"
                "function s1Search() {\n"
                "  var el = document.getElementById('cq-search');\n"
                "  if (el) { el.focus(); }\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        check(("id", "cq-search") not in _dead_tokens(graph),
              "guard 1 (id-as-prop): pbUse('input', {id: 'cq-search'}) is recognized as a producer")
        check(LC.check_dead_seam(graph) == [], "guard 1: check_dead_seam fires zero times")


# ───────────────────────── 1b. producer guard 2 — id via a VARIABLE prefix ─────

def test_producer_variable_prefix():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "s2",
            "body": (
                "function renderScreenS2() {\n"
                "  var tid = 'hpb-reject-dlg-' + 'x';\n"
                "  return '<div id=\"' + tid + '\"></div>';\n"
                "}\n"
                "function s2Open(memberId) {\n"
                "  var el = document.getElementById('hpb-reject-dlg-' + memberId);\n"
                "  if (el) { el.classList.add('open'); }\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        check(("id", "hpb-reject-dlg-") not in _dead_tokens(graph),
              "guard 2 (variable prefix): 'hpb-reject-dlg-' + x is recognized as a producer")
        check(LC.check_dead_seam(graph) == [], "guard 2: check_dead_seam fires zero times")


# ───────────────────────── 1c. producer guard 3 — a runtime write ─────────────

def test_producer_runtime_write():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "s3",
            "body": (
                "function renderScreenS3() {\n"
                "  return '<div></div>';\n"
                "}\n"
                "function s3Mark(el) {\n"
                "  el.setAttribute('data-marked', '1');\n"
                "}\n"
                "function s3Check(el) {\n"
                "  var v = el.getAttribute('data-marked');\n"
                "  if (v) { console.log(v); }\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        check(("data", "marked") not in _dead_tokens(graph),
              "guard 3 (runtime write): setAttribute('data-marked', …) is recognized as a producer")
        check(LC.check_dead_seam(graph) == [], "guard 3: check_dead_seam fires zero times")


# ───────────────────────── 1d. producer guard 4 — idPrefix:/name: props ───────

def test_producer_name_prop():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "s4",
            "body": (
                "function renderScreenS4() {\n"
                "  return pbUse('radio-group', { name: 'cd-pop', options: [] });\n"
                "}\n"
                "function s4Pick(key) {\n"
                "  var el = document.getElementById('cd-pop-' + key);\n"
                "  if (el) { el.checked = true; }\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        check(("id", "cd-pop-") not in _dead_tokens(graph),
              "guard 4 (name: prop): getElementById('cd-pop-' + key) is recognized as a producer")
        check(LC.check_dead_seam(graph) == [], "guard 4: check_dead_seam fires zero times")


# ───────────────────────── 2a. :has() selector-subject case ───────────────────

def test_has_selector_subject():
    """The declaration applies to the selector's SUBJECT (`.target`), not the
    intermediate `.mid` the combinator merely passes through. `.mid` carries its
    own inline display in the SAME tag as its class — R1 must not blame it."""
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[{
            "id": "subject-case",
            "body": (
                "function renderCmpSubjectCase() {\n"
                "  return '<style>.wrap:has(#x:checked) ~ .mid .target{display:flex}</style>'\n"
                "    + '<div class=\"mid\" style=\"display:block\">'\n"
                "    + '<div class=\"target\"></div></div>';\n"
                "}\n"
            ),
        }])
        findings = LC.check_has_rules(tmp)
        r1 = [f for f in findings if f.code == "L-HAS-R1"]
        check(r1 == [], "selector-subject case: R1 does not blame the intermediate .mid (found: %r)" % r1)


# ───────────────────────── 2b. :has() inline-display lookback case ────────────

def test_has_inline_lookback():
    """Two tags on ONE line: a neighbor carries class+style (an unrelated toggle),
    immediately followed by the REAL :has() subject's tag, which carries no style
    attribute at all. A backward-lookback implementation can misattribute the
    neighbor's style to the subject; this checker only ever looks inside one tag's
    own span, so it must not."""
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[{
            "id": "lookback-case",
            "body": (
                "function renderCmpLookbackCase() {\n"
                "  return '<style>.host:has(#y:checked) ~ .target{display:flex}</style>'\n"
                "    + '<span class=\"neighbor\" style=\"display:block\"></span>"
                "<span class=\"target\"></span>';\n"
                "}\n"
            ),
        }])
        findings = LC.check_has_rules(tmp)
        r1 = [f for f in findings if f.code == "L-HAS-R1"]
        check(r1 == [], "inline-lookback case: the neighbor's style is not attributed to .target (found: %r)" % r1)


# ───────────────────────── 3a. dead-seam FIRES (unguarded -> ERROR) ────────────

def test_dead_seam_fires_unguarded():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "boom",
            "body": (
                "function renderScreenBoom() { return '<div></div>'; }\n"
                "function boomGo() {\n"
                "  document.getElementById('totally-missing').classList.add('x');\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        findings = LC.check_dead_seam(graph)
        check(len(findings) == 1, "an unproduced, unguarded read produces exactly one finding (got %d)" % len(findings))
        if findings:
            check(findings[0].severity == LC.ERROR, "…and it is an ERROR, since nothing guards it")
            check(findings[0].code == "L-DEADSEAM", "…with code L-DEADSEAM")


# ───────────────────────── 3b. dead-seam FIRES (guarded -> WARN) ───────────────

def test_dead_seam_fires_guarded():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "safe",
            "body": (
                "function renderScreenSafe() { return '<div></div>'; }\n"
                "function safeGo() {\n"
                "  var el = document.getElementById('also-missing');\n"
                "  if (el) { el.classList.add('x'); }\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        findings = LC.check_dead_seam(graph)
        check(len(findings) == 1, "an unproduced, GUARDED read still produces exactly one finding (got %d)" % len(findings))
        if findings:
            check(findings[0].severity == LC.WARN, "…but it is a WARN, since `if (el)` guards it at runtime")


# ───────────────────────── 3c. undefined-helper FIRES ──────────────────────────

def test_undefined_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "u1",
            "body": (
                "function renderScreenU1() { return '<div></div>'; }\n"
                "function u1Go() {\n"
                "  pbTotallyMissingHelper();\n"
                "}\n"
            ),
        }])
        graph = LE.extract(tmp)
        findings = LC.check_undefined(graph)
        check(len(findings) == 1 and findings[0].code == "L-UNDEF",
              "a pb*-named call with no definition anywhere fires exactly one L-UNDEF (got %r)" % findings)


# ───────────────────────── 3d. duplicate-def FIRES ─────────────────────────────

def test_duplicate_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[
            {"id": "dup-a", "body": "function renderCmpDupA(){return '';}\nfunction pbDupFn(){return 1;}\n"},
            {"id": "dup-b", "body": "function renderCmpDupB(){return '';}\nfunction pbDupFn(){return 2;}\n"},
        ])
        graph = LE.extract(tmp)
        findings = LC.check_duplicates(graph)
        check(len(findings) == 1 and findings[0].code == "L-DUPDEF",
              "the same top-level fn name in two files fires exactly one L-DUPDEF (got %r)" % findings)


# ───────────────────────── 3e/3f. :has() R1 / R2 FIRE on genuine defects ───────

def test_has_r1_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[{
            "id": "r1-bug",
            "body": (
                "function renderCmpR1Bug() {\n"
                "  return '<style>.host:has(#y:checked) ~ .target{display:flex}</style>'\n"
                "    + '<div class=\"target\" style=\"display:none\"></div>';\n"
                "}\n"
            ),
        }])
        findings = [f for f in LC.check_has_rules(tmp) if f.code == "L-HAS-R1"]
        check(len(findings) == 1, "an inline display on the :has()-toggled subject itself fires R1 (got %r)" % findings)
        if findings:
            check(findings[0].severity == LC.ERROR, "…as an ERROR")


def test_has_r2_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[{
            "id": "r2-bug",
            "body": (
                "function renderCmpR2Bug() {\n"
                "  return '<style>.host:has(#y:checked) ~ tr.row{display:flex}</style>'\n"
                "    + '<tr class=\"row\"></tr>';\n"
                "}\n"
            ),
        }])
        findings = [f for f in LC.check_has_rules(tmp) if f.code == "L-HAS-R2"]
        check(len(findings) == 1, "a revealed <tr> using display:flex instead of table-row fires R2 (got %r)" % findings)
        if findings:
            check(findings[0].severity == LC.ERROR, "…as an ERROR")


# ───────────────────────── 3g/3h. Kind B (elements[] / anatomy.parts[]) FIRE ───

def test_elements_kind_b_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "e1",
            "body": "function renderScreenE1() { return pbUse('button', {}); }\n",
            "elements": [{"id": "phantom", "orgId": "nonexistent-component", "label": "A phantom part"}],
        }])
        graph = LE.extract(tmp)
        registry = LC._load_registry_with_specs(tmp)
        findings = LC.check_elements(graph, registry)
        check(len(findings) == 1 and findings[0].code == "L-ELEMENTS",
              "a screen elements[] orgId absent from the composed set fires L-ELEMENTS (got %r)" % findings)


def test_elements_kind_b_silent_without_declaration():
    """The converse: a screen with NO elements[] at all (or none carrying orgId)
    must be silent — absence of a declaration is never a finding."""
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, screens=[{
            "id": "e2",
            "body": "function renderScreenE2() { return pbUse('button', {}); }\n",
        }])
        graph = LE.extract(tmp)
        registry = LC._load_registry_with_specs(tmp)
        check(LC.check_elements(graph, registry) == [], "a screen with no elements[] produces no L-ELEMENTS finding")


def test_anatomy_kind_b_fires():
    with tempfile.TemporaryDirectory() as tmp:
        make_project(tmp, components=[{
            "id": "a1",
            "body": "function renderCmpA1() { return pbUse('icon', {}); }\n",
            "anatomy": {"parts": [{"n": 1, "name": "Ghost", "orgId": "missing-thing"}]},
        }])
        graph = LE.extract(tmp)
        registry = LC._load_registry_with_specs(tmp)
        findings = LC.check_anatomy(graph, registry)
        check(len(findings) == 1 and findings[0].code == "L-ANATOMY",
              "a component anatomy.parts[] orgId absent from the composed set fires L-ANATOMY (got %r)" % findings)


# ───────────────────────── plumbing: --explain / exit codes / determinism ──────

def test_explain_every_code():
    for code in sorted(LC.EXPLAIN):
        text = LC.EXPLAIN[code]
        check(bool(text.strip()), "--explain has non-empty text for %s" % code)
    check(LC.explain("NOT-A-REAL-CODE") == 2, "--explain on an unknown code returns exit 2, not a crash")


def test_report_exit_codes():
    only_warn = [LC.Finding(LC.WARN, "L-DEADSEAM", "x", "m")]
    only_info = [LC.Finding(LC.INFO, "L-HAS-R4", "x", "m")]
    with_error = [LC.Finding(LC.ERROR, "L-UNDEF", "x", "m")]
    check(LC._report([], "t", "ok") == 0, "no findings -> exit 0")
    check(LC._report(only_info, "t", "ok") == 0, "INFO-only findings never affect the exit code")
    check(LC._report(only_warn, "t", "ok") == 1, "a WARN with no ERROR -> exit 1")
    check(LC._report(with_error, "t", "ok") == 2, "any ERROR -> exit 2")



def test_default_shell_is_resolved():
    """The DEFAULT path must not invent errors.

    Caught in review, not by the original build: run against a real project WITHOUT
    `--shell`, the checker reported 6 false L-UNDEF errors and 1 false L-DEADSEAM and
    exited 2 — because pbUse / pbToast / pbEscape / pbResetSandbox / pbSortTable all
    live in the pb shell, and with no shell read they look undefined. A tool whose own
    default path invents seven defects is worse than no tool.

    Two guarantees, both pinned here: extract() defaults to the plugin's own shell, and
    if a shell genuinely cannot be read the undefined check does not run at all.
    """
    assert LE.default_shell_path(), "the plugin's own shell must be findable from __file__"
    with tempfile.TemporaryDirectory() as d:
        make_project(d, screens=[{
            "id": "s",
            "body": "function renderScreenS(props) {\n"
                    "  return pbUse('x', {}) + pbToast('hi') + pbEscape('a');\n}\n",
        }])
        g = LE.extract(d)
        check(g.get("shellResolved") is True, "extract() defaults to the plugin's own shell")
        codes = [f.code for f in LC.check_undefined(g)]
        check("L-UNDEF" not in codes,
              "shell globals (pbUse/pbToast/pbEscape) are NOT reported undefined by default")

        g2 = LE.extract(d, shell_path="/nonexistent/prototype.html")
        check(g2.get("shellResolved") is False, "a missing shell is reported as unresolved")
        f2 = LC.check_undefined(g2)
        check([f.code for f in f2] == ["L-UNDEF-SKIP"],
              "with no shell the undefined check SKIPS and says so, never accuses")
        check(f2 and f2[0].severity == "INFO", "the skip note is information, never a finding")


if __name__ == "__main__":
    test_producer_prop_id()
    test_producer_variable_prefix()
    test_producer_runtime_write()
    test_producer_name_prop()
    test_has_selector_subject()
    test_has_inline_lookback()
    test_dead_seam_fires_unguarded()
    test_dead_seam_fires_guarded()
    test_undefined_fires()
    test_duplicate_fires()
    test_has_r1_fires()
    test_has_r2_fires()
    test_elements_kind_b_fires()
    test_elements_kind_b_silent_without_declaration()
    test_anatomy_kind_b_fires()
    test_explain_every_code()
    test_report_exit_codes()
    test_default_shell_is_resolved()

    print()
    if fails:
        print(f"FAIL — {len(fails)} regression(s)")
        sys.exit(1)
    print("PASS — logic_check.py false-positive corpus intact")
