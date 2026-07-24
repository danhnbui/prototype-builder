#!/usr/bin/env python3
"""
registry_to_figma.py — the deterministic registry → GHN DS Bridge node-JSON transformer (WS3).

The analog of render.py, but the target is the GHN DS Bridge plugin's declarative node JSON
instead of HTML — so a code→Figma push costs ~0 model tokens (a token lever). The model NEVER
hand-writes the node JSON. The output is pasted into the plugin's *Code → Figma* tab, which
rebuilds it as real, linked component INSTANCES.

Because the registry is a machine-readable COMPOSITION TREE (component-first / atomic — WS1), the
lowering is 1:1 and faithful:
  - a screen  → a root FRAME with auto-layout (from screens[].layout)
  - each screens[].elements[] (orgId) → an INSTANCE of that component's DS publish `key`, with
    componentProperties derived from the element's props + state (never re-drawing its internals)
  - a LOCAL component (no DS key) → a FRAME built from its anatomy.parts[], each part with an
    orgId nested as an INSTANCE (the "instance, don't bake" contract lint --figma verifies)
  - layout spacing (gap/padding) → a numeric value PLUS a {token,id,key} sidecar, so the plugin
    binds the Figma variable once it ships the spacing-binding fix (numeric works meanwhile)
Anything without a DS key / variable is FLAGGED as a gap (mirrors the plugin's `untokenized`) —
a key is NEVER invented (AGENT_GUIDE rule 5).

Publish keys + variables come from the DS catalog (design-system/<name>/ds-catalog.json, produced
from the plugin's Scan DS at /pb:pull-ds). figma-transfer.json (per-component dsKey +
propertyMapping) and figma-tokens.json (token-name → variable) override/augment when present.

Pure stdlib. Deterministic (no timestamps in build_nodes — the fixture test compares byte output).

Usage:
  python3 registry_to_figma.py <registry.json>
      [--out nodes.json] [--scope components|screens|both]
      [--screen ID] [--component ID]
      [--catalog ds-catalog.json] [--tokens figma-tokens.json] [--transfer figma-transfer.json]
      [--gaps gaps.md] [--strict-gaps]
Exit: 0 ok · 2 usage/IO/shape error · 3 gaps present (only with --strict-gaps)
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tokens as _tokens  # noqa: E402  (the DTCG token resolver)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


class Ctx:
    def __init__(self, reg, catalog, tokens_map, transfer):
        self.reg = reg
        self.catalog = catalog or {}
        self.tokens_map = tokens_map or {}          # css-name -> {name,key,id}
        self.transfer = transfer or {}
        self.gaps = []
        self.comp_by_id = {c.get("id"): c for c in reg.get("components", []) if isinstance(c, dict)}
        # catalog component lookup by normalized name
        self.cat_by_name = {}
        for c in self.catalog.get("components", []) or []:
            if isinstance(c, dict) and c.get("name"):
                self.cat_by_name[_norm(c["name"])] = c
        # catalog variable lookup by normalized name
        self.var_by_name = {}
        for v in self.catalog.get("variables", []) or []:
            if isinstance(v, dict) and v.get("name"):
                self.var_by_name[_norm(v["name"])] = v
        # resolved-value -> css token name (for spacing value → token matching). When several
        # tokens share a value (e.g. radius-medium and space-4 are both 16px), prefer a
        # spacing/size token — a layout gap/padding is spacing, not a radius.
        self.value_index = {}
        rows = _tokens.to_list(reg.get("tokens", {}))
        for r in sorted(rows, key=lambda x: (0 if x["displayKind"] in ("space", "size") else 1, x["name"])):
            if isinstance(r["value"], (str, int, float)):
                self.value_index.setdefault(str(r["value"]), r["name"])

    def catalog_for(self, comp):
        """The catalog component a registry component resolves to (by dsMatch / name / id)."""
        if not isinstance(comp, dict):
            return None
        dm = comp.get("dsMatch") or {}
        for n in (dm.get("component"), comp.get("name"), comp.get("id")):
            if n and _norm(n) in self.cat_by_name:
                return self.cat_by_name[_norm(n)]
        return None


def resolve_key(comp, ctx):
    """The DS publish key for a registry component, or None (→ a gap / local build). Never invents."""
    if not isinstance(comp, dict):
        return None
    t = (ctx.transfer.get("components", {}) or {}).get(comp.get("id"), {})
    if t.get("dsKey"):
        return t["dsKey"]
    dm = comp.get("dsMatch") or {}
    if dm.get("key"):  # a key carried inline on the registry component (e.g. from an ingest)
        return dm["key"]
    cat = ctx.catalog_for(comp)
    return cat.get("key") if cat else None


def token_ref_by_name(cssname, ctx):
    """A {token,id,key} ref for a CSS-var token name, from figma-tokens.json then the catalog."""
    m = ctx.tokens_map.get(cssname)
    if isinstance(m, dict) and (m.get("key") or m.get("id")):
        return {"token": cssname, "id": m.get("id"), "key": m.get("key")}
    v = ctx.var_by_name.get(_norm(cssname))
    if v:
        return {"token": cssname, "id": v.get("id"), "key": v.get("key")}
    return None


def token_for_value(v, ctx):
    """A token ref for a numeric px value (e.g. layout gap 16 → space-4 → its variable), or None."""
    css = ctx.value_index.get("%gpx" % v) or ctx.value_index.get("%spx" % v)
    return token_ref_by_name(css, ctx) if css else None


def _spacing(lay, key, v, ctx):
    """Set a layout spacing field to the numeric value + a *Token sidecar the plugin can bind."""
    if not isinstance(v, (int, float)):
        return
    lay[key] = v
    tr = token_for_value(v, ctx)
    if tr:
        lay[key + "Token"] = tr
    else:
        ctx.gaps.append({"kind": "token", "ref": "%gpx" % v, "where": key})


def screen_layout(screen, ctx):
    L = screen.get("layout") or {}
    typ = L.get("type")
    lay = {"mode": "VERTICAL", "layoutWrap": "NO_WRAP"}
    _spacing(lay, "itemSpacing", L.get("gap"), ctx)
    pad = L.get("padding")
    for side in ("Top", "Right", "Bottom", "Left"):
        _spacing(lay, "padding" + side, pad, ctx)
    if typ == "centered":
        lay["primaryAxisAlignItems"] = "CENTER"
        lay["counterAxisAlignItems"] = "CENTER"
        lay["primaryAxisSizingMode"] = "FIXED"
        lay["counterAxisSizingMode"] = "FIXED"
    else:  # stack / default
        lay["primaryAxisSizingMode"] = "AUTO"
        lay["counterAxisSizingMode"] = "FIXED"
    return lay


def instance_props(comp, props, ctx):
    """Map a registry element's props → the DS component's componentProperties (by name, against
    the catalog's propertyDefinitions + variant axes). data-* / layout props are skipped (they are
    prototype-runtime attrs, not DS properties). Variant values are matched to the axis casing."""
    cat = ctx.catalog_for(comp)
    defs = (cat.get("propertyDefinitions") if cat else None) or {}
    axis_options = {}
    if cat:
        for v in cat.get("variants", []) or []:
            for k, val in (v.get("variantValues") or {}).items():
                axis_options.setdefault(k, set()).add(val)
    else:
        # No catalog match (e.g. an ingested component that carries its DS key inline): use the
        # registry component's own enum properties as the variant axes, so the instance still
        # round-trips its variant props.
        for p in comp.get("properties", []) or []:
            if isinstance(p, dict) and p.get("type") == "enum" and p.get("id"):
                opts = {o.get("value") for o in (p.get("options") or [])
                        if isinstance(o, dict) and o.get("value") is not None}
                if opts:
                    axis_options[p["id"]] = opts
    if not defs and not axis_options:
        return {}
    dsprops = {}  # normalized name -> (realName, type)
    for name, d in defs.items():
        typ = d.get("type") if isinstance(d, dict) else "VARIANT"
        dsprops[_norm(name)] = (name, typ)
    for axis in axis_options:
        dsprops.setdefault(_norm(axis), (axis, "VARIANT"))
    skip = {"full", "id", "classname", "dir", "gap", "padding", "maxwidth", "grow", "align", "justify"}
    out = {}
    for pk, pv in (props or {}).items():
        nk = _norm(pk)
        if nk.startswith("data") or nk in skip:
            continue
        hit = dsprops.get(nk)
        if not hit:
            continue
        real, typ = hit
        if typ == "VARIANT" and real in axis_options:
            opt = next((o for o in sorted(axis_options[real]) if _norm(o) == _norm(pv)), None)
            out[real] = opt if opt is not None else str(pv)
        elif isinstance(pv, bool):
            out[real] = pv
        else:
            out[real] = str(pv)
    return out


def component_frame(comp, ctx, name=None):
    """A LOCAL component (no DS key) → a FRAME (auto-layout) whose children are its anatomy parts:
    a part with an orgId → a nested INSTANCE (instance, don't bake); other parts are skipped
    (their content lives in the render body, which the deterministic transformer does not parse)."""
    frame = {"type": "FRAME", "name": name or comp.get("name") or comp.get("id"),
             "layout": {"mode": "VERTICAL", "primaryAxisSizingMode": "AUTO", "counterAxisSizingMode": "AUTO"},
             "sizingH": "HUG", "sizingV": "HUG", "children": []}
    an = comp.get("anatomy")
    parts = (an.get("parts") if isinstance(an, dict) else None) or []
    for p in parts:
        if not isinstance(p, dict):
            continue
        org = p.get("orgId")
        if not org:
            continue
        child = ctx.comp_by_id.get(org)
        key = resolve_key(child, ctx)
        if key:
            frame["children"].append({
                "type": "INSTANCE", "name": p.get("name") or org,
                "component": {"key": key},
                "componentProperties": instance_props(child, {}, ctx)})
        else:
            ctx.gaps.append({"kind": "component", "ref": org, "where": comp.get("id")})
    return frame


def element_node(el, ctx):
    org = el.get("orgId")
    comp = ctx.comp_by_id.get(org)
    key = resolve_key(comp, ctx) if comp else None
    if key:
        props = dict(el.get("props") or {})
        if el.get("state") and "state" not in props:  # element state → the DS State variant axis
            props["state"] = el["state"]
        return {"type": "INSTANCE", "name": el.get("id") or org,
                "component": {"key": key},
                "componentProperties": instance_props(comp, props, ctx)}
    ctx.gaps.append({"kind": "component", "ref": org, "where": el.get("id")})
    if comp:
        return component_frame(comp, ctx, name=el.get("id"))
    return {"type": "FRAME", "name": el.get("id") or org or "unknown",
            "layout": {"mode": "VERTICAL"}, "dsGap": True, "children": []}


def screen_root(screen, ctx):
    root = {"type": "FRAME", "name": screen.get("name") or screen.get("id"),
            "layout": screen_layout(screen, ctx), "sizingH": "FILL", "sizingV": "FILL",
            "children": [element_node(el, ctx) for el in (screen.get("elements") or []) if isinstance(el, dict)]}
    return root


def build_nodes(reg, catalog=None, tokens_map=None, transfer=None, scope="both", only=None):
    """Pure core: registry (+ catalog/maps) → { meta, roots[], gaps[] }. No I/O, no timestamps."""
    ctx = Ctx(reg, catalog, tokens_map, transfer)
    roots = []
    if scope in ("components", "both"):
        for c in reg.get("components", []) or []:
            if not isinstance(c, dict):
                continue
            if only and c.get("id") not in only:
                continue
            if resolve_key(c, ctx):
                continue  # a DS-matched component is a reference, not a local build — skip
            roots.append(component_frame(c, ctx))
    if scope in ("screens", "both"):
        for s in reg.get("screens", []) or []:
            if not isinstance(s, dict):
                continue
            if only and s.get("id") not in only:
                continue
            roots.append(screen_root(s, ctx))
    # de-dupe gaps deterministically
    seen, gaps = set(), []
    for g in ctx.gaps:
        k = (g.get("kind"), g.get("ref"), g.get("where"))
        if k not in seen:
            seen.add(k)
            gaps.append(g)
    return {"meta": {"source": "registry", "scope": scope,
                     "rootCount": len(roots), "gapCount": len(gaps)},
            "roots": roots, "gaps": gaps}


def build_component_nodes(reg, comp_id, catalog=None, tokens_map=None, transfer=None, props=None):
    """One component → its node (INSTANCE if it resolves to a DS key, else a FRAME from anatomy)
    — for the design-system site's per-component "Push to Figma". Pure; deterministic."""
    ctx = Ctx(reg, catalog, tokens_map, transfer)
    comp = ctx.comp_by_id.get(comp_id)
    if not isinstance(comp, dict):
        return {"meta": {"source": "registry", "component": comp_id},
                "roots": [], "gaps": [{"kind": "component", "ref": comp_id, "where": "push"}]}
    node = element_node({"id": comp_id, "orgId": comp_id, "props": props or {}}, ctx)
    seen, gaps = set(), []
    for g in ctx.gaps:
        k = (g.get("kind"), g.get("ref"), g.get("where"))
        if k not in seen:
            seen.add(k)
            gaps.append(g)
    return {"meta": {"source": "registry", "component": comp_id, "gapCount": len(gaps)},
            "roots": [node], "gaps": gaps}


def _write_gaps(gaps, path):
    lines = ["# Figma bridge gaps", "",
             "Emitted by `registry_to_figma.py` — a DS component or token with no publish key/variable.",
             "Resolve each at `/pb:pull-ds` (Scan DS) or the G-FP3/G-FP4 match, then re-run. Never invented.", ""]
    for g in gaps:
        lines.append("- **%s** `%s` (at `%s`) — no %s in the DS catalog." % (
            g.get("kind"), g.get("ref"), g.get("where"),
            "publish key" if g.get("kind") == "component" else "variable"))
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(prog="registry_to_figma.py")
    p.add_argument("registry", nargs="?", default="registry.json")
    p.add_argument("--out", default=None)
    p.add_argument("--scope", choices=("components", "screens", "both"), default="both")
    p.add_argument("--screen", default=None)
    p.add_argument("--component", default=None)
    p.add_argument("--catalog", default=None)
    p.add_argument("--tokens", default=None)
    p.add_argument("--transfer", default=None)
    p.add_argument("--gaps", default=None)
    p.add_argument("--strict-gaps", action="store_true")
    args = p.parse_args(argv)

    def _load(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    try:
        reg = _load(args.registry)
        catalog = _load(args.catalog) if args.catalog else None
        tokens_map = (_load(args.tokens) or {}).get("tokens") if args.tokens else None
        transfer = _load(args.transfer) if args.transfer else None
    except (OSError, json.JSONDecodeError) as e:
        print("registry_to_figma: %s" % e, file=sys.stderr)
        return 2

    only = {x for x in (args.screen, args.component) if x} or None
    out = build_nodes(reg, catalog, tokens_map, transfer, args.scope, only)
    payload = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(payload + "\n")
    else:
        sys.stdout.write(payload + "\n")
    if args.gaps and out["gaps"]:
        _write_gaps(out["gaps"], args.gaps)
    print("✓ %d root node(s), %d gap(s)%s" % (
        out["meta"]["rootCount"], out["meta"]["gapCount"],
        (" → " + args.out) if args.out else ""), file=sys.stderr)
    if args.strict_gaps and out["gaps"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
