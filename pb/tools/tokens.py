#!/usr/bin/env python3
"""
tokens.py — the W3C DTCG token resolver (schema 8+, the token source of truth).

registry.json `tokens` is a **W3C Design Tokens (DTCG)** document
(https://tr.designtokens.org/format/): each token is an object with `$value` and,
optionally (inheritable from its enclosing group), `$type`; a group is a plain nested
object (no `$value`); a `$value` of the form `"{group.token}"` is an **alias** to another
token. `$description` is optional prose.

pb writes a **flat** DTCG document for its own projects — the token name IS the CSS
custom-property name (`brand` → `--brand`) — but a cloned DS (e.g. the ghn-ds MCP's
semantic/primitive tiers) may be **nested with aliases**. Both are valid DTCG and both
resolve here, so this module is the single token authority for every Python consumer
(render_react.py, ds_serve.py, clone_ds.py, lint_registry.py, and the Figma bridge). The
shell mirrors `resolve()` in JS (`pbResolveTokens` / `applyRegistryTokens`) for the live
prototype.

Dimension `$value`s stay strings ("16px") — the interoperable community form — so a
resolved value drops straight into a CSS custom property.

Pure stdlib. No I/O. Deterministic.
"""

# The W3C DTCG $type set — 7 primitive + 6 composite. Used by lint (R-DTCG-TYPE).
DTCG_TYPES = {
    "color", "dimension", "fontFamily", "fontWeight", "duration", "cubicBezier", "number",
    "strokeStyle", "border", "transition", "shadow", "gradient", "typography",
}

# pb's legacy `kind` → DTCG `$type`. Used by migration 0006 and by DS import normalization.
# `dimension` intentionally collapses space/size/radius/fontSize (DTCG has no finer type);
# the cosmetic swatch bucket is recovered by display_kind().
KIND_TO_TYPE = {
    "color": "color",
    "radius": "dimension", "space": "dimension", "size": "dimension",
    "fontSize": "dimension", "breakpoint": "dimension",
    "type": "fontFamily", "font": "fontFamily",
    "fontWeight": "fontWeight",
    "shadow": "shadow", "border": "border",
    "opacity": "number", "zIndex": "number", "number": "number",
    "duration": "duration", "cubicBezier": "cubicBezier",
    "other": None,  # no compliant $type — emit the token without one (valid: $type is optional)
}

# Figma Variable resolvedType ↔ DTCG $type (the Figma bridge, WS3). Figma has only
# COLOR / FLOAT / STRING / BOOLEAN, so this is intentionally lossy on the FLOAT side.
FIGMA_TO_TYPE = {"COLOR": "color", "FLOAT": "dimension", "STRING": "fontFamily", "BOOLEAN": "number"}
TYPE_TO_FIGMA = {
    "color": "COLOR",
    "dimension": "FLOAT", "number": "FLOAT", "fontWeight": "FLOAT", "duration": "FLOAT",
    "fontFamily": "STRING",
}


def is_group(node):
    """A DTCG group is a dict that is NOT a token (a token carries `$value`)."""
    return isinstance(node, dict) and "$value" not in node


def is_alias(value):
    """A `$value` alias reference: `"{group.token}"`."""
    return isinstance(value, str) and len(value) >= 2 and value[0] == "{" and value[-1] == "}"


def alias_ref(value):
    """`"{color.brand}"` → `"color.brand"` (the dot-path of the referenced token)."""
    return value[1:-1] if is_alias(value) else None


def walk(doc, _prefix=(), _inherited_type=None):
    """Yield `(path_tuple, token_dict, resolved_type)` for every token in a DTCG doc.

    A group may carry `$type` that descendant tokens inherit; a token's own `$type` wins.
    `$`-prefixed keys and non-dict members are skipped.
    """
    if not isinstance(doc, dict):
        return
    group_type = doc.get("$type", _inherited_type)
    for key, node in doc.items():
        if isinstance(key, str) and key.startswith("$"):
            continue
        if not isinstance(node, dict):
            continue
        if "$value" in node:
            yield (_prefix + (key,), node, node.get("$type", group_type))
        else:
            yield from walk(node, _prefix + (key,), group_type)


def css_var_name(path):
    """A token path → its CSS custom-property name (no leading `--`).
    Flat: `("brand",)` → `"brand"`. Nested: `("color","brand")` → `"color-brand"`."""
    return "-".join(path)


def _index(doc):
    """Map dot-path → (path, token, type) for alias resolution."""
    return {".".join(path): (path, tok, typ) for path, tok, typ in walk(doc)}


def resolve_value(value, index, _seen=None):
    """Follow aliases to the terminal literal. An unresolved/cyclic ref is returned
    verbatim (a visible gap signal, never a crash)."""
    if not is_alias(value):
        return value
    ref = alias_ref(value)
    _seen = _seen or set()
    if ref in _seen or ref not in index:
        return value
    _seen.add(ref)
    _, tok, _ = index[ref]
    return resolve_value(tok.get("$value"), index, _seen)


def resolve(doc):
    """DTCG doc → `{cssVarName: scalarValue}` for every token (aliases resolved).
    Composite object values (shadow/typography/…) are skipped — they aren't a single CSS
    custom property. This is what feeds `:root` custom properties and `tokens.css`."""
    if not isinstance(doc, dict):
        return {}
    index = _index(doc)
    out = {}
    for path, tok, _typ in walk(doc):
        val = resolve_value(tok.get("$value"), index)
        if isinstance(val, (str, int, float)):
            out[css_var_name(path)] = val
    return out


def display_kind(css_name, dtcg_type):
    """Cosmetic swatch bucket from `$type` + name. `$type=dimension` collapses
    space/size/radius/fontSize, so the fine bucket is recovered by name — cosmetic only,
    never load-bearing (nothing renders differently by its being 'radius' vs 'size')."""
    if dtcg_type == "color":
        return "color"
    if dtcg_type == "fontFamily":
        return "font"
    if dtcg_type == "fontWeight":
        return "fontWeight"
    if dtcg_type == "shadow":
        return "shadow"
    if dtcg_type == "dimension":
        n = (css_name or "").lower()
        if n.startswith("radius") or "-radius" in n:
            return "radius"
        if n.startswith(("space", "gap", "pad")) or "-space" in n or "-gap" in n:
            return "space"
        if n.startswith(("text", "font-size", "fontsize")):
            return "fontSize"
        return "size"
    return "other"


def to_list(doc):
    """`[{name, cssVar, value, rawValue, type, displayKind, description, path}]` for
    swatch / catalog UIs (the design-system site token foundations; ds_serve.py). `value` is
    alias-resolved; `name`/`cssVar` are the CSS custom-property name."""
    index = _index(doc)
    rows = []
    for path, tok, typ in walk(doc):
        cname = css_var_name(path)
        rows.append({
            "name": cname,
            "cssVar": "--" + cname,
            "value": resolve_value(tok.get("$value"), index),
            "rawValue": tok.get("$value"),
            "type": typ,
            "displayKind": display_kind(cname, typ),
            "description": tok.get("$description"),
            "path": list(path),
        })
    return rows


def from_legacy(name, value, kind):
    """Build a DTCG token object from pb's legacy `{value, kind}`. Used by migration 0006
    and by DS import when a source still speaks the old shape. `$type` is omitted when the
    kind has no compliant DTCG type (valid — `$type` is optional)."""
    tok = {"$value": value}
    typ = KIND_TO_TYPE.get(kind)
    if typ:
        tok["$type"] = typ
    return tok


def _selftest():
    """`python3 tokens.py` — exercise flat, nested, alias, and legacy paths."""
    flat = {
        "brand": {"$value": "#4f46e5", "$type": "color"},
        "space-4": {"$value": "16px", "$type": "dimension"},
        "radius-small": {"$value": "8px", "$type": "dimension"},
        "text-sm": {"$value": "14px", "$type": "dimension"},
        "text-muted": {"$value": "#5e6873", "$type": "color"},
    }
    r = resolve(flat)
    assert r["brand"] == "#4f46e5" and r["space-4"] == "16px", r
    kinds = {row["name"]: row["displayKind"] for row in to_list(flat)}
    assert kinds == {"brand": "color", "space-4": "space", "radius-small": "radius",
                     "text-sm": "fontSize", "text-muted": "color"}, kinds

    nested = {
        "color": {"$type": "color",
                  "primitive": {"orange-500": {"$value": "#ff5200"}},
                  "brand": {"$value": "{color.primitive.orange-500}"}},
    }
    rn = resolve(nested)
    assert rn["color-brand"] == "#ff5200", rn  # alias resolved through the group
    assert rn["color-primitive-orange-500"] == "#ff5200", rn

    assert from_legacy("brand", "#fff", "color") == {"$value": "#fff", "$type": "color"}
    assert from_legacy("z", "5", "other") == {"$value": "5"}  # no compliant $type
    print("tokens.py selftest: ok")


if __name__ == "__main__":
    _selftest()
