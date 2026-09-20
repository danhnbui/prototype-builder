#!/usr/bin/env python3
"""
pb-check — the contract validator (refit plan Phase 1, T1.1).

Machine-checks a registry.json against the data contract the playbook promises, so
violations are caught before render / hand-off instead of compiled silently. Pure
stdlib (NS4); a validator is not a render, so the token levers (NS2/NS3) are untouched.

Severity → exit code:
  0  clean (no findings)
  1  warnings only
  2  at least one error

--strict promotes the raw-hex / raw-px warnings to errors (default is WARN so existing
projects don't hard-break — NS6, a migration path). Other rules are fixed severity.

Each finding prints as:  <SEVERITY> [<CODE>] <location>: <message>

Usage:  python3 lint_registry.py [--strict] [--report] [--sync-elements] <registry.json>

--report        rank, never gate: a histogram by code, the items carrying the most, the
                shape metrics, and a "fix first" list. ALWAYS exits 0 — at 87 findings on a
                real project a flat list is unreadable, and the ordering is the product.
                Thresholds from an optional memory/doctor.json beside the registry.
--sync-elements APPEND a screens[].elements[] entry per composed-but-undeclared component.
                Append-only and idempotent; never edits, reorders or removes an entry.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokens as _tok  # noqa: E402  (sibling module; the W3C DTCG token resolver)

# Tokens the shell's runtime references by name; absence is a latent Principle-1 gap.
RUNTIME_REQUIRED_TOKENS = ("danger",)

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
_SCRIPT_CLOSE = re.compile(r"</\s*script", re.IGNORECASE)

# Atomic-design levels + their composition rank (higher composes lower). `foundation` = tokens;
# a screen is implicitly `page`. Component-first / atomic law: only atoms emit raw primitives;
# every level above composes lower-level components via pbUse() (mirrors the shell runtime).
LEVEL_ENUM = {"atom", "molecule", "organism", "template", "page"}
LEVEL_RANK = {"foundation": 0, "atom": 1, "molecule": 2, "organism": 3, "template": 4, "page": 5}
_CONTROL_TAGS = ("button", "input", "select", "textarea", "a", "form", "img", "video", "canvas", "iframe")
_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "label", "small", "strong", "em")
_CONTROL_RE = re.compile(r"<(" + "|".join(_CONTROL_TAGS) + r")(?=[\s/>])", re.IGNORECASE)
_TEXT_RE = re.compile(r"<(" + "|".join(_TEXT_TAGS) + r")(?=[\s/>])", re.IGNORECASE)
_PBUSE = re.compile(r"pbUse\(\s*['\"]([a-z0-9][a-z0-9-]*)['\"]")

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


def pascal(id_):
    return "".join(part[:1].upper() + part[1:] for part in str(id_).split("-") if part)


# A part name that is PROSE, not a label: it carries sentence punctuation. R-NEST-HINT skips
# these outright. Measured: 6 of the 12 hints on a real project came from matching a word
# inside a description like "Toolbar — search + three filter comboboxes + download" (→ combobox)
# or "Hidden input carrying the value" (→ input). A substring/token test cannot tell those from
# a real label, so the discriminator is the punctuation that marks it as a sentence.
_PROSE_NAME = re.compile(r"[—–,:;+()/]|\.\s|\S\s+\S+\s+\S+\s+\S+")
_WORDS = re.compile(r"[a-z0-9]+")


def _hint_component(name, ids_by_len):
    """The component id a part NAME most likely refers to, or None (R-NEST-HINT).

    Whole-token, longest-match, prose-rejecting — in that order. The old rule was a bare
    substring test (`g in name.lower()`), which fired on any id appearing anywhere in a
    10-word description. `ids_by_len` is the component-id list sorted longest-first so
    'Department Tag Select' resolves to 'department-tag-select', not 'select', and
    'Label Wrap' to 'label-wrap', not 'label' — the specific answer, not the first one.
    """
    raw = str(name or "").strip()
    if not raw or _PROSE_NAME.search(raw):
        return None
    toks = _WORDS.findall(raw.lower())
    if not toks or len(toks) > 4:
        return None
    joined = "-".join(toks)
    for cid in ids_by_len:                     # longest id first → most specific wins
        parts = cid.split("-")
        n = len(parts)
        if n > len(toks):
            continue
        if joined == cid:
            return cid
        # the id's words as a CONSECUTIVE run of the name's words
        if any(toks[i:i + n] == parts for i in range(len(toks) - n + 1)):
            return cid
    return None


# A `default` that is a STRING but opens like a collection literal. `'[]'` is not an empty
# list — it is a two-character string, and `'[]'.map` is not a function.
_COLLECTION_LITERAL = re.compile(r"^\s*[\[{]")


def _check_prop_types(add, comp, where):
    """R-PROPTYPE — a collection prop whose declared type and default disagree (D-26).

    Two shapes, both measured on a real project and both wrong in the hand-off bundle a
    developer receives:
      1. type array/object, default a string   — `{"type":"array","default":"[{name:'…'}]"}`
      2. type string, default a collection lit — `{"type":"string","default":"[]"}`

    Why it matters beyond documentation: the design-system site builds a demo from
    `default`, so a component whose body does `props.rows.map(...)` gets the STRING `'[]'`
    and throws. 11 of 133 components on the real project fail exactly this way. The
    prototype is unaffected — there a parent passes real props via pbUse and the default
    never fires — which is why nothing caught it until the second site existed.
    """
    for j, pr in enumerate(comp.get("properties") or []):
        if not isinstance(pr, dict):
            continue
        typ, dflt, pid = pr.get("type"), pr.get("default"), pr.get("id", f"#{j}")
        if typ in ("array", "object") and isinstance(dflt, str):
            add(WARN, "R-PROPTYPE", f"{where} properties[{pid!r}]",
                f"type {typ!r} but default is a string ({dflt[:40]!r}…) — a demo built from "
                f"this default gets a string, not a {typ}; use a real {typ} literal")
        elif typ == "string" and isinstance(dflt, str) and _COLLECTION_LITERAL.match(dflt):
            add(WARN, "R-PROPTYPE", f"{where} properties[{pid!r}]",
                f"default {dflt[:40]!r} looks like a collection but type is 'string' — "
                f"declare \"type\":\"array\" (or \"object\") and give a real literal")


def check(reg, strict=False, base_dir=None):
    """Return a list of Finding for the registry dict. strict promotes hex/px to errors.

    base_dir (the registry's directory) lets the validator resolve `renderSrc` body files
    so it scans the real bodies — exactly what render.py compiles.
    """
    findings = []
    hex_px_sev = ERROR if strict else WARN
    # Component-first / atomic law: enforced (ERROR) under the strict contract (r0_hygiene / CI),
    # WARN otherwise so an un-migrated project isn't hard-broken mid-flight (NS6). R-LEVEL is
    # always ERROR — `level` is a required field like renderFn (schema 9).
    compose_sev = ERROR if strict else WARN

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    # ── shape sanity ─────────────────────────────────────────────────────────
    if not isinstance(reg, dict):
        add(ERROR, "R-SHAPE", "<root>", "registry must be a JSON object")
        return findings
    for key, typ, label in (("components", list, "array"),
                            ("screens", list, "array"),
                            ("tokens", dict, "object"),
                            ("meta", dict, "object")):
        if key in reg and not isinstance(reg[key], typ):
            add(ERROR, "R-SHAPE", key, f"{key} must be a JSON {label}")

    # Re-inline anatomy/spec/usage/uiLogic from specSrc sidecars (schema 10) before the
    # anatomy-dependent checks read them; mutates `reg` in place so the loops below see them.
    _resolve_specs(add, reg, base_dir)

    components = reg.get("components") if isinstance(reg.get("components"), list) else []
    screens = reg.get("screens") if isinstance(reg.get("screens"), list) else []
    tokens = reg.get("tokens") if isinstance(reg.get("tokens"), dict) else {}

    comp_ids = set()
    comp_by_id = {}

    # ── components: kebab id, uniqueness, renderFn, render-body scans ─────────
    seen_comp = {}
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            add(ERROR, "R-SHAPE", f"components[{i}]", "component must be an object")
            continue
        cid = c.get("id", "")
        where = f"components[{i}] id={cid!r}"
        if not _KEBAB.match(str(cid)):
            add(ERROR, "R-KEBAB", where, "component id must be kebab-case")
        if cid in seen_comp:
            add(ERROR, "R-DUPID", where,
                f"duplicate component id (also components[{seen_comp[cid]}]) — "
                f"ids must be unique across global+local (R4)")
        else:
            seen_comp[cid] = i
        comp_ids.add(cid)
        comp_by_id.setdefault(cid, c)
        _check_renderfn(add, c, "renderCmp", where)
        if c.get("level") not in LEVEL_ENUM:
            add(ERROR, "R-LEVEL", where,
                f"level {c.get('level')!r} missing or not in {sorted(LEVEL_ENUM)} — required (schema 9)")
        _check_prop_types(add, c, where)
        _scan_body(add, _resolve_body(add, c, where, base_dir), where, hex_px_sev)

    # ── anatomy nesting: declared globals must be instanced (R-NEST / R-NEST-HINT) ──
    # Mirrors screens[].elements[].orgId (R-ORGID): a component anatomy part that IS a
    # reused global declares it via `orgId`, so the Figma hand-off nests an INSTANCE of
    # the global instead of baking a copy (constitution Principle 10). The hand-off can't
    # infer reuse from the render JS, so the registry must make it explicit. The matching
    # terms are DERIVED from the registry's actual global ids — no hardcoded names.
    global_ids = {cid for cid, c in comp_by_id.items()
                  if isinstance(c, dict) and c.get("scope") == "global"}
    # R-NEST-HINT stays scoped to GLOBALS. D-10 makes a local orgId legal, but the hint's job
    # is DS instance reuse in the Figma hand-off, which is a global concern; widening it to
    # every component turned 12 hints into 64 on a real project — precise, and exactly the
    # noise D-22 exists to remove. The local-child case is served by making it legal (above)
    # and by --sync-elements for the screen half.
    # Sorted longest-first so the most specific id wins (see _hint_component).
    all_ids_by_len = sorted((cid for cid in comp_by_id if isinstance(cid, str)),
                            key=lambda s: (-len(s.split("-")), -len(s), s))
    for i, c in enumerate(components):
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "")
        _anatomy = c.get("anatomy")
        parts = ((_anatomy.get("parts") if isinstance(_anatomy, dict) else None)) or []
        for p in parts:
            if not isinstance(p, dict):
                continue
            where = f"components[{i}] id={cid!r} part#{p.get('n')}"
            org = p.get("orgId")
            if org is not None:
                # D-10: an orgId may reference ANY registry component, local or global.
                # The old rule ERRORed on a local target, which contradicted R-COMPOSE-MATCH
                # by construction: on a real project non-atom components compose 132
                # local-child edges, so of 57 components carrying the composed-not-declared
                # warning only 4 could be cleared by declaring globals — 39 were blocked
                # outright. registry_to_figma.py already lowers a non-DS child as a FRAME
                # from anatomy, so the restriction guarded nothing. The Figma publish-key
                # concern stays with R-NEST-FIGMA.
                if comp_by_id.get(org) is None:
                    add(ERROR, "R-NEST", where,
                        f"part orgId {org!r} resolves to no component")
            elif c.get("scope") != "global":
                # drift detector: a part that LOOKS like a component but doesn't declare it
                # Resolve against EVERY component, then emit only when the best match is a
                # global. A part named 'Toggle Input' resolves to the local `toggle-input`,
                # not the global `input` — and now that a local orgId is legal (D-10),
                # suggesting `input` there would be wrong advice. A check that would print a
                # wrong answer stays quiet instead (D-08).
                hit = _hint_component(p.get("name"), all_ids_by_len)
                if hit and hit in global_ids:
                    add(WARN, "R-NEST-HINT", where,
                        f"part name {p.get('name')!r} looks like the component {hit!r} "
                        f"but has no orgId — add \"orgId\":\"{hit}\" to force instance reuse "
                        f"in the Figma hand-off")

    # ── screens: kebab id, uniqueness, renderFn, orgId refs, render-body ──────
    seen_screen = {}
    for i, s in enumerate(screens):
        if not isinstance(s, dict):
            add(ERROR, "R-SHAPE", f"screens[{i}]", "screen must be an object")
            continue
        sid = s.get("id", "")
        where = f"screens[{i}] id={sid!r}"
        if not _KEBAB.match(str(sid)):
            add(ERROR, "R-KEBAB", where, "screen id must be kebab-case")
        if sid in seen_screen:
            add(ERROR, "R-DUPID", where,
                f"duplicate screen id (also screens[{seen_screen[sid]}])")
        else:
            seen_screen[sid] = i
        _check_renderfn(add, s, "renderScreen", where)
        _scan_body(add, _resolve_body(add, s, where, base_dir), where, hex_px_sev)
        for j, el in enumerate(s.get("elements", []) or []):
            if not isinstance(el, dict):
                continue
            org = el.get("orgId")
            if org is not None and org not in comp_ids:
                add(ERROR, "R-ORGID", f"{where} elements[{j}]",
                    f"orgId {org!r} resolves to no component")

    # ── composition law: only atoms emit primitives; molecules+ compose via pbUse() ─────
    # R-COMPOSE (no inlined controls above atom level), R-COMPOSE-TEXT (prefer text atoms),
    # R-COMPOSE-MATCH (the pbUse tree matches declared elements[]/anatomy.parts[] orgIds),
    # R-LEVEL-ORDER (compose strictly lower levels; atoms are leaves). This is what lowers
    # 1:1 to a clean Figma INSTANCE tree in the bridge.
    def _declared_orgids(kind, item):
        if kind == "screen":
            return {el.get("orgId") for el in (item.get("elements") or [])
                    if isinstance(el, dict) and el.get("orgId")}
        an = item.get("anatomy")
        parts = (an.get("parts") if isinstance(an, dict) else None) or []
        return {p.get("orgId") for p in parts if isinstance(p, dict) and p.get("orgId")}

    for kind, items in (("component", components), ("screen", screens)):
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            where = f"{kind}s[{i}] id={item.get('id', '')!r}"
            lvl = item.get("level") or ("page" if kind == "screen" else None)
            rank = LEVEL_RANK.get(lvl)
            body = _body_of(item, base_dir)
            composed = set(_PBUSE.findall(body or ""))
            declared = _declared_orgids(kind, item)
            if lvl == "atom":
                if composed:
                    add(ERROR, "R-LEVEL-ORDER", where,
                        f"an atom composes {sorted(composed)} via pbUse — atoms are leaves; only molecules+ compose")
                continue
            if lvl is None:
                continue  # component missing level already flagged by R-LEVEL
            ctl = sorted({m.lower() for m in _CONTROL_RE.findall(body or "")})
            if ctl:
                add(compose_sev, "R-COMPOSE", where,
                    f"non-atom ({lvl}) body inlines raw control tag(s) <{'>, <'.join(ctl)}> — compose a component via pbUse() instead")
            txt = sorted({m.lower() for m in _TEXT_RE.findall(body or "")})
            if txt:
                add(WARN, "R-COMPOSE-TEXT", where,
                    f"non-atom body inlines raw text tag(s) <{'>, <'.join(txt)}> — prefer a heading/paragraph atom")
            missing = declared - composed
            extra = composed - declared
            if missing:
                add(compose_sev, "R-COMPOSE-MATCH", where,
                    f"declared component(s) {sorted(missing)} are not composed (pbUse) in the render body")
            if extra:
                add(WARN, "R-COMPOSE-MATCH", where,
                    f"body composes {sorted(extra)} not declared in "
                    f"{'elements[]' if kind == 'screen' else 'anatomy.parts[]'}")
            if rank is not None:
                for oid in sorted(composed):
                    child = comp_by_id.get(oid)
                    crank = LEVEL_RANK.get(child.get("level")) if isinstance(child, dict) else None
                    if crank is not None and crank >= rank:
                        add(compose_sev, "R-LEVEL-ORDER", where,
                            f"composes {oid!r} at level {child.get('level')!r} (>= its own {lvl!r}) — compose strictly lower levels")
                if lvl in ("molecule", "organism", "template") and not composed:
                    add(WARN, "R-LEVEL-ORDER", where,
                        f"{lvl} composes no lower-level component (no pbUse) — inlining markup that should be a component?")

    # ── tokens: W3C DTCG $type validity + legacy-shape + runtime-required presence ──
    # tokens is a DTCG document (flat or nested-with-aliases). Validate each token's $type
    # against the DTCG type set; flag any surviving legacy {value, kind} token; and confirm
    # the runtime-required tokens resolve (by CSS-var name, so nesting is handled).
    for name, t in tokens.items():
        if isinstance(name, str) and name.startswith("$"):
            continue
        if isinstance(t, dict) and "$value" not in t and "value" in t and "kind" in t:
            add(WARN, "R-DTCG-TYPE", f"tokens.{name}",
                "legacy {value, kind} token — run /pb:update-version to convert to DTCG {$value, $type}")
    for row in _tok.to_list(tokens):
        typ = row.get("type")
        if typ is not None and typ not in _tok.DTCG_TYPES:
            add(ERROR, "R-DTCG-TYPE", f"tokens.{'.'.join(row['path'])}",
                f"$type {typ!r} is not a W3C DTCG type ({', '.join(sorted(_tok.DTCG_TYPES))})")
    resolved = _tok.resolve(tokens)
    for req in RUNTIME_REQUIRED_TOKENS:
        if req not in resolved:
            add(WARN, "R-DANGER", "tokens",
                f"runtime-required token {req!r} is missing — the error runtime styles "
                f"with var(--{req}); add it or fresh submits show no danger border")

    # ── flow / erd shape sanity when populated ────────────────────────────────
    flow = reg.get("flow") or {}
    if isinstance(flow, dict) and flow.get("populated"):
        if not isinstance(flow.get("mermaid"), str) or not flow.get("mermaid"):
            add(WARN, "R-FLOW", "flow", "populated flow needs a non-empty mermaid string")
        if not isinstance(flow.get("stories"), list):
            add(WARN, "R-FLOW", "flow", "populated flow needs a stories[] array")
    erd = reg.get("erd") or {}
    if isinstance(erd, dict) and erd.get("populated"):
        if not isinstance(erd.get("mermaid"), str) or not erd.get("mermaid"):
            add(WARN, "R-ERD", "erd", "populated erd needs a non-empty mermaid string")
        if not isinstance(erd.get("table"), list):
            add(WARN, "R-ERD", "erd", "populated erd needs a table[] array")

    return findings


def check_nesting_figma(reg, transfer):
    """Verify every anatomy part that declares a nested global (`orgId`) has a recorded
    INSTANCE in figma-transfer.json — proof the hand-off reused the global instead of
    baking a local copy (G-FP6 invariant #7 / constitution Principle 10). Runs over the
    two committed contracts, so CI asserts it without needing the Figma plugin.

    Returns a list of Finding (R-NEST-FIGMA)."""
    findings = []

    def add(sev, code, where, msg):
        findings.append(Finding(sev, code, where, msg))

    components = reg.get("components") if isinstance(reg.get("components"), list) else []
    comp_by_id = {}
    for c in components:
        if isinstance(c, dict):
            comp_by_id.setdefault(c.get("id", ""), c)
    tcomps = transfer.get("components", {}) if isinstance(transfer, dict) else {}

    for i, c in enumerate(components):
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "")
        _anatomy = c.get("anatomy")
        parts = ((_anatomy.get("parts") if isinstance(_anatomy, dict) else None)) or []
        for p in parts:
            if not isinstance(p, dict):
                continue
            org = p.get("orgId")
            if not org:
                continue
            where = f"components[{i}] id={cid!r} part#{p.get('n')} -> {org!r}"
            parent = tcomps.get(cid) or {}
            nested = (parent.get("nestedInstances") or {}) if isinstance(parent, dict) else {}
            rec = nested.get(org)
            if not isinstance(rec, dict) or not rec.get("instanceId"):
                add(ERROR, "R-NEST-FIGMA", where,
                    f"declared nested global {org!r} has no recorded instance in "
                    f"figma-transfer.components.{cid}.nestedInstances — the hand-off baked "
                    f"it in instead of instancing the global")
                continue
            # the nested instance must reuse the SAME published DS component as the global
            want = ((tcomps.get(org) or {}).get("dsMatch") or {}).get("componentKey")
            got = rec.get("componentKey")
            if want and got and want != got:
                add(ERROR, "R-NEST-FIGMA", where,
                    f"nested instance componentKey {got!r} != the global {org!r}'s DS key "
                    f"{want!r} — it instances a different component than the global reuses")
    return findings


def _resolve_specs(add, reg, base_dir):
    """Re-inline anatomy/spec/usage/uiLogic from `specSrc` sidecars (schema 10) so the anatomy
    checks (R-NEST/R-ORGID/R-COMPOSE-MATCH) see the real parts. Mirrors render.load_specs but,
    like _resolve_body, emits an ERROR finding on a missing sidecar rather than raising."""
    if base_dir is None:
        return
    for kind in ("components", "screens"):
        items = reg.get(kind)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            src = item.get("specSrc")
            if not src:
                continue
            where = f"{kind}[id={item.get('id')!r}]"
            path = os.path.normpath(os.path.join(base_dir, src))
            try:
                with open(path, encoding="utf-8") as f:
                    for k, v in json.load(f).items():
                        item[k] = v
            except FileNotFoundError:
                add(ERROR, "R-SPECSRC", where, f"specSrc file not found: {src}")
            except json.JSONDecodeError as e:
                add(ERROR, "R-SPECSRC", where, f"specSrc is invalid JSON: {src} ({e.msg})")


def _resolve_body(add, item, where, base_dir):
    """Return the render body to scan, resolving renderSrc (v1.4 schema 4).

    Precedence: renderSrc > legacy render. Both present -> WARN (R-RENDERSRC). A
    renderSrc pointing at a missing file -> ERROR (mirrors render.py failing closed).
    """
    src = item.get("renderSrc")
    legacy = item.get("render", "")
    if not src:
        return legacy
    if legacy:
        add(WARN, "R-RENDERSRC", where,
            "both renderSrc and a legacy render string are present — renderSrc wins; "
            "remove the inline render")
    if base_dir is None:
        return legacy  # can't resolve without a path; skip body scan
    path = os.path.normpath(os.path.join(base_dir, src))
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        add(ERROR, "R-RENDERSRC", where, f"renderSrc file not found: {src}")
        return ""


def _body_of(item, base_dir):
    """Read a render body WITHOUT emitting findings — the compose pass re-reads bodies the
    id/renderFn loops already resolved (via _resolve_body), so this avoids double warnings."""
    src = item.get("renderSrc")
    if src and base_dir is not None:
        try:
            with open(os.path.normpath(os.path.join(base_dir, src)), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""
    return item.get("render", "") or ""


def _check_renderfn(add, item, prefix, where):
    fn = item.get("renderFn")
    expected = prefix + pascal(item.get("id", ""))
    if not fn:
        add(ERROR, "R-RENDERFN", where, f"missing renderFn (expected {expected!r})")
    elif fn != expected:
        add(ERROR, "R-RENDERFN", where,
            f"renderFn {fn!r} breaks the naming contract (expected {expected!r})")


def _scan_body(add, body, where, hex_px_sev):
    """Scan a render-body string for the page-killer and raw hex/px."""
    if not isinstance(body, str) or not body:
        return
    if _SCRIPT_CLOSE.search(body):
        add(ERROR, "R-SCRIPT", where,
            "render body contains a literal '</script>' — it kills the page; "
            "emit it split (e.g. '<\\/scr'+'ipt>') or via the </ -> <\\/ render escape")
    for m in dict.fromkeys(_HEX.findall(body)):  # de-dup, preserve order
        add(hex_px_sev, "R-HEX", where, f"raw hex {m} in render body — use a token (Principle 2)")
    for m in dict.fromkeys(_PX.findall(body)):
        add(hex_px_sev, "R-PX", where, f"raw px {m} in render body — use a token (Principle 2)")


def _load_json(path):
    """Load a JSON file, failing closed with a one-line R-IO/R-JSON message (no traceback)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)


def _report(findings, label, ok_msg):
    """Print findings, then exit 0 (clean) / 1 (warnings) / 2 (any error)."""
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    for f in findings:
        print(f.line())
    if not findings:
        print(f"✓ {label}: {ok_msg}")
        sys.exit(0)
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(2 if errors else 1)


def sync_elements(reg, path, base_dir):
    """--sync-elements (D-11): APPEND a screens[].elements[] entry per composed-but-undeclared
    component. Returns (added, undeclared_report).

    Append-only, and every rule here is load-bearing:
      * never edit, reorder or remove an existing entry — on a real project the 208 existing
        entries carry hand-written labels averaging 345 chars (111 with a date) plus token
        lists; regenerating them destroys authoring nobody can reproduce;
      * declared-but-not-composed is REPORTED, never deleted (it may be a not-yet-built part);
      * idempotent — a second run is a byte-for-byte no-op.
    Measured on a real project: 66 composed-but-undeclared, 0 declared-but-not-composed, so
    append-only clears the screen half of R-COMPOSE-MATCH completely.
    """
    added, stale = [], []
    for s in reg.get("screens") or []:
        if not isinstance(s, dict):
            continue
        body = _body_of(s, base_dir) or ""
        composed = set(_PBUSE.findall(body))
        els = s.setdefault("elements", [])
        declared = {e.get("orgId") for e in els if isinstance(e, dict) and e.get("orgId")}
        for oid in sorted(composed - declared):
            els.append({"id": oid, "label": f"(auto) composed {oid}",
                        "orgId": oid, "state": "default"})
            added.append((s.get("id"), oid))
        for oid in sorted(declared - composed):
            stale.append((s.get("id"), oid))
    if added:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    return added, stale


def _pascal_calls(text, cid):
    """True when `text` reaches component `cid` other than through pbUse — i.e. a direct
    `renderCmpX(...)` or `window['renderCmpX'](...)`. The sidebar is reached exactly this
    way from header-footer-app, and missing it is what made a naive orphan check report 36
    orphans on a project that has none."""
    return f"renderCmp{pascal(cid)}" in text


def report(reg, path, base_dir, findings):
    """--report (D-22): rank, never gate. Always exits 0.

    lint emits 87 flat warnings on a real project — accurate and unreadable. The product
    here is the ORDERING: which code dominates, which item carries the most, and what the
    shape metrics say. Thresholds come from an optional memory/doctor.json beside the
    registry (absent → the measured defaults below), which is what keeps this at schema 10.
    """
    import collections
    th = {"body_lines_warn": 500, "body_lines_high": 1000, "registry_kb": 500,
          "slice_kb": 20, "decisions_kb": 500}
    cfg = os.path.join(base_dir or ".", "memory", "doctor.json")
    if os.path.isfile(cfg):
        try:
            th.update(json.load(open(cfg, encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            print("note: memory/doctor.json unreadable — using defaults")

    comps = reg.get("components") or []
    screens = reg.get("screens") or []
    items = [x for x in comps + screens if isinstance(x, dict)]
    bodies = {}
    for it in items:
        b = _body_of(it, base_dir)
        if b:
            bodies[it.get("id")] = b
    joined = "\n".join(bodies.values())

    print("── findings by code " + "─" * 40)
    by_code = collections.Counter(f.code for f in findings)
    for code, n in by_code.most_common():
        sev = "ERROR" if any(f.severity == ERROR for f in findings if f.code == code) else "warn"
        print(f"  {n:5d}  {code:<18s} {sev}")
    if not findings:
        print("  (none)")

    print("\n── items carrying the most " + "─" * 33)
    per_item = collections.Counter(
        m.group(1) for f in findings for m in [re.search(r"id='([^']+)'", f.where)] if m)
    for iid, n in per_item.most_common(8):
        print(f"  {n:5d}  {iid}")
    if not per_item:
        print("  (none)")

    print("\n── shape " + "─" * 51)
    reg_kb = os.path.getsize(path) / 1024 if os.path.isfile(path) else 0
    # Count each BODY FILE once. Three screens can share one renderSrc (they do on a real
    # project), and counting it per screen would report 16 oversized bodies where there are 14.
    by_src = {}
    for it in items:
        src = it.get("renderSrc") or it.get("id")
        if it.get("id") in bodies:
            by_src.setdefault(src, (it.get("id"), bodies[it["id"]]))
    lines = {ident: text.count("\n") + 1 for ident, text in by_src.values()}
    over = sorted((n, k) for k, n in lines.items() if n > th["body_lines_warn"])
    high = [x for x in over if x[0] > th["body_lines_high"]]
    biggest = max(lines.items(), key=lambda kv: kv[1], default=("—", 0))
    slices = sorted(((len(json.dumps(it, ensure_ascii=False)), it.get("id")) for it in items),
                    reverse=True)
    def flag(cond):
        return "  ⚠" if cond else ""
    print(f"  registry            {reg_kb:8.0f} KB{flag(reg_kb > th['registry_kb'])}")
    print(f"  components/screens  {len(comps):5d} / {len(screens)}")
    print(f"  tokens              {len(reg.get('tokens') or {}):5d}")
    print(f"  bodies > {th['body_lines_warn']:<4d} lines {len(over):5d}{flag(over)}"
          f"   > {th['body_lines_high']} lines: {len(high)}")
    print(f"  largest body        {biggest[0]} ({biggest[1]} lines)")
    if slices:
        print(f"  largest slice       {slices[0][1]} ({slices[0][0] / 1024:.0f} KB)"
              f"{flag(slices[0][0] / 1024 > th['slice_kb'])}")
    dec = os.path.join(base_dir or ".", "memory", "decisions.md")
    if os.path.isfile(dec):
        d_kb = os.path.getsize(dec) / 1024
        print(f"  decisions log       {d_kb:8.0f} KB{flag(d_kb > th['decisions_kb'])}")

    print("\n── information (never a finding) " + "─" * 27)
    # Orphans. GUARDED: a component is reached by pbUse OR by a direct renderCmp* call.
    # Without the second clause this reports 36 on a project whose true count is 0.
    used = set(_PBUSE.findall(joined))
    orphans = [c.get("id") for c in comps if isinstance(c, dict)
               and c.get("id") not in used and not _pascal_calls(joined, c.get("id", ""))]
    print(f"  components reached by nothing      {len(orphans)}"
          + (f"  {orphans[:6]}" if orphans else ""))
    # Unused tokens. INFORMATION by decision: a design system ships full ramps, so an
    # unreferenced token is not a defect. Runtime-composed names are honoured.
    names = []
    _tok_walk(reg.get("tokens") or {}, "", names)
    dyn = set(re.findall(r"var\(--([a-z0-9-]*)'\s*\+", joined)) | \
          set(re.findall(r"'--([a-z0-9-]*)'\s*\+", joined))
    unref = [n for n in names
             if f"--{n}" not in joined and not any(p and n.startswith(p) for p in dyn)]
    print(f"  tokens never referenced            {len(unref)} of {len(names)}"
          f"   (a DS ships full ramps — not a defect)")
    st = reg.get("staleness")
    if isinstance(st, dict) and st and all(
            all(v == 0 for v in g.values()) for g in st.values() if isinstance(g, dict)):
        print("  staleness                          present but all zero — nothing writes it (deprecated)")

    print("\n── fix first " + "─" * 47)
    rank = []
    if any(f.severity == ERROR for f in findings):
        rank.append(f"{sum(1 for f in findings if f.severity == ERROR)} error(s) — these block --strict")
    if by_code.get("R-COMPOSE-MATCH"):
        # --sync-elements only writes screens[].elements[]; components declare theirs by hand.
        # Recommending it once the screen half is already clear sends the reader in a circle.
        screen_half = sum(1 for f in findings
                          if f.code == "R-COMPOSE-MATCH" and f.where.startswith("screens["))
        rank.append(f"{by_code['R-COMPOSE-MATCH']} R-COMPOSE-MATCH — run --sync-elements to clear "
                    f"the screen half ({screen_half})" if screen_half else
                    f"{by_code['R-COMPOSE-MATCH']} R-COMPOSE-MATCH, all on components — the screen "
                    f"half is clear; declare each component's elements[] by hand or drop the claim")
    if by_code.get("R-PROPTYPE"):
        rank.append(f"{by_code['R-PROPTYPE']} R-PROPTYPE — each one is a component that cannot demo, and wrong docs in the hand-off")
    if high:
        rank.append(f"{len(high)} body/bodies over {th['body_lines_high']} lines — use slice.py --no-prose to keep context small")
    for i, r in enumerate(rank, 1):
        print(f"  {i}. {r}")
    if not rank:
        print("  nothing ranked — clean")
    print()


def _tok_walk(node, trail, out):
    for k, v in node.items():
        if isinstance(k, str) and k.startswith("$"):
            continue
        name = f"{trail}-{k}" if trail else k
        if isinstance(v, dict) and "$value" in v:
            out.append(name)
        elif isinstance(v, dict):
            _tok_walk(v, name, out)


def main():
    args = sys.argv[1:]
    strict = "--strict" in args
    figma = "--figma" in args
    do_report = "--report" in args
    do_sync = "--sync-elements" in args
    args = [a for a in args if a not in ("--strict", "--figma", "--report", "--sync-elements")]

    # --figma: cross-check the registry against figma-transfer.json (nested-global reuse).
    if figma:
        if len(args) != 2:
            sys.exit("usage: lint_registry.py --figma <registry.json> <figma-transfer.json>")
        reg = _load_json(args[0])
        transfer = _load_json(args[1])
        _report(check_nesting_figma(reg, transfer),
                "lint_registry.py --figma", f"clean — {args[0]} × {args[1]}")
        return

    if len(args) != 1:
        sys.exit("usage: lint_registry.py [--strict] [--report] [--sync-elements] <registry.json>"
                 "  |  lint_registry.py --figma <registry.json> <figma-transfer.json>")
    path = args[0]
    reg = _load_json(path)
    base_dir = os.path.dirname(os.path.abspath(path))

    # --sync-elements: an append-only registry write, then stop. Never combined with a report
    # run, so the numbers a report prints always describe the file as it is on disk.
    if do_sync:
        added, stale = sync_elements(reg, path, base_dir)
        for sid, oid in added:
            print(f"  + screens[{sid!r}].elements[]: {oid}")
        for sid, oid in stale:
            print(f"  ? screens[{sid!r}] declares {oid!r} but the body does not compose it "
                  f"— left in place; remove it by hand if it is stale")
        print(f"lint_registry.py --sync-elements: {len(added)} appended, "
              f"{len(stale)} declared-but-not-composed, 0 removed — {path}")
        sys.exit(0)

    findings = check(reg, strict=strict, base_dir=base_dir)

    # --report: ranks and never gates (D-22). Always exit 0, whatever the findings say.
    if do_report:
        report(reg, path, base_dir, findings)
        sys.exit(0)

    _report(findings, "lint_registry.py --strict" if strict else "lint_registry.py", f"clean — {path}")


if __name__ == "__main__":
    main()
