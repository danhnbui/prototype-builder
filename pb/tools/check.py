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

Usage:  python3 check.py [--strict] <registry.json>
"""
import json
import os
import re
import sys

# Token kinds the contract recognizes. Extend here, not inline.
KIND_ENUM = {
    "color", "radius", "space", "size", "fontSize", "font", "shadow",
    "border", "opacity", "duration", "zIndex", "breakpoint", "other",
}
# Tokens the shell's runtime references by name; absence is a latent Principle-1 gap.
RUNTIME_REQUIRED_TOKENS = ("danger",)

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
_SCRIPT_CLOSE = re.compile(r"</\s*script", re.IGNORECASE)

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

    components = reg.get("components") if isinstance(reg.get("components"), list) else []
    screens = reg.get("screens") if isinstance(reg.get("screens"), list) else []
    tokens = reg.get("tokens") if isinstance(reg.get("tokens"), dict) else {}

    comp_ids = set()

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
        _check_renderfn(add, c, "renderCmp", where)
        _scan_body(add, _resolve_body(add, c, where, base_dir), where, hex_px_sev)

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

    # ── tokens: kind enum, runtime-required presence ──────────────────────────
    for name, t in tokens.items():
        if isinstance(t, dict):
            kind = t.get("kind")
            if kind is not None and kind not in KIND_ENUM:
                add(ERROR, "R-KIND", f"tokens.{name}",
                    f"kind {kind!r} is not in the enum ({', '.join(sorted(KIND_ENUM))})")
    for req in RUNTIME_REQUIRED_TOKENS:
        if req not in tokens:
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


def main():
    args = sys.argv[1:]
    strict = "--strict" in args
    args = [a for a in args if a != "--strict"]
    if len(args) != 1:
        sys.exit("usage: check.py [--strict] <registry.json>")
    path = args[0]
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except FileNotFoundError:
        print(f"ERROR [R-IO] {path}: file not found", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR [R-JSON] {path}: invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}",
              file=sys.stderr)
        sys.exit(2)

    findings = check(reg, strict=strict, base_dir=os.path.dirname(os.path.abspath(path)))
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    for f in findings:
        print(f.line())

    label = "check.py --strict" if strict else "check.py"
    if not findings:
        print(f"✓ {label}: clean — {path}")
        sys.exit(0)
    print(f"{label}: {len(errors)} error(s), {len(warns)} warning(s) — {path}")
    sys.exit(2 if errors else 1)


if __name__ == "__main__":
    main()
