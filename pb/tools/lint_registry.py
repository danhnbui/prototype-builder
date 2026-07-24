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

Usage:  python3 lint_registry.py [--strict] <registry.json>
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
        _scan_body(add, _resolve_body(add, c, where, base_dir), where, hex_px_sev)

    # ── anatomy nesting: declared globals must be instanced (R-NEST / R-NEST-HINT) ──
    # Mirrors screens[].elements[].orgId (R-ORGID): a component anatomy part that IS a
    # reused global declares it via `orgId`, so the Figma hand-off nests an INSTANCE of
    # the global instead of baking a copy (constitution Principle 10). The hand-off can't
    # infer reuse from the render JS, so the registry must make it explicit. The matching
    # terms are DERIVED from the registry's actual global ids — no hardcoded names.
    global_ids = {cid for cid, c in comp_by_id.items()
                  if isinstance(c, dict) and c.get("scope") == "global"}
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
                target = comp_by_id.get(org)
                if target is None:
                    add(ERROR, "R-NEST", where,
                        f"part orgId {org!r} resolves to no component")
                elif target.get("scope") != "global":
                    add(ERROR, "R-NEST", where,
                        f"part orgId {org!r} is scope={target.get('scope')!r}; only "
                        f"scope:'global' components may be nested as reused instances")
            elif c.get("scope") != "global":
                # drift detector: a part that LOOKS like a global but doesn't declare it
                nm = str(p.get("name", "")).lower()
                hit = next((g for g in global_ids if g in nm), None)
                if hit:
                    add(WARN, "R-NEST-HINT", where,
                        f"part name {p.get('name')!r} looks like it nests global {hit!r} "
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


def main():
    args = sys.argv[1:]
    strict = "--strict" in args
    figma = "--figma" in args
    args = [a for a in args if a not in ("--strict", "--figma")]

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
        sys.exit("usage: lint_registry.py [--strict] <registry.json>  |  "
                 "lint_registry.py --figma <registry.json> <figma-transfer.json>")
    path = args[0]
    reg = _load_json(path)
    findings = check(reg, strict=strict, base_dir=os.path.dirname(os.path.abspath(path)))
    _report(findings, "lint_registry.py --strict" if strict else "lint_registry.py", f"clean — {path}")


if __name__ == "__main__":
    main()
