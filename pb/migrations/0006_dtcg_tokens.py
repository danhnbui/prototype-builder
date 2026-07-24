"""
0006_dtcg_tokens — schema 7 (v1.8) → schema 8: the `tokens` slice becomes a W3C DTCG document.

pb's tokens were a flat map of `name → { value, kind }`. As of schema 8 the top-level
`tokens` object is a **W3C Design Tokens (DTCG)** document — each token is
`name → { $value, $type[, $description] }` — so the source of truth is standards-compliant
and round-trips with Figma variables / Style-Dictionary / Tokens Studio. The document stays
FLAT (token name == CSS custom-property name), so render bodies keep using `var(--name)`
unchanged; a cloned DS may add nested groups + aliases (also valid DTCG) on top.

Only the top-level `tokens` slice is reshaped. The `{ name, value, kind }` display objects
inside `components[].anatomy.parts[].token` / `spec` are redline *annotations*, not the token
document — left untouched.

Maps are inlined (a migration is a deterministic point-in-time snapshot; it must not import a
live module that could later change). They mirror tokens.py KIND_TO_TYPE / display_kind.

up(reg):   { value, kind } → { $value, $type }  (idempotent: skips tokens already in DTCG); stamp 8.
down(reg): { $value, $type } → { value, kind }  (best-effort: `dimension` → radius/space/size/
           fontSize is recovered by name); stamp 7.
"""
import copy

FROM = 7
TO = 8

# pb legacy `kind` → DTCG `$type`. `dimension` collapses space/size/radius/fontSize.
_KIND_TO_TYPE = {
    "color": "color",
    "radius": "dimension", "space": "dimension", "size": "dimension",
    "fontSize": "dimension", "breakpoint": "dimension",
    "type": "fontFamily", "font": "fontFamily", "fontWeight": "fontWeight",
    "shadow": "shadow", "border": "border",
    "opacity": "number", "zIndex": "number", "number": "number",
    "duration": "duration", "cubicBezier": "cubicBezier",
}


def _kind_from(name, dtcg_type):
    """DTCG $type (+ name) → a legacy `kind`, for down(). Cosmetic recovery only."""
    if dtcg_type == "color":
        return "color"
    if dtcg_type == "fontFamily":
        return "font"
    if dtcg_type == "shadow":
        return "shadow"
    if dtcg_type == "number":
        return "opacity"
    if dtcg_type == "dimension":
        n = (name or "").lower()
        if n.startswith("radius") or "-radius" in n:
            return "radius"
        if n.startswith(("space", "gap", "pad")) or "-space" in n or "-gap" in n:
            return "space"
        if n.startswith(("text", "font-size", "fontsize")):
            return "fontSize"
        return "size"
    return "other"


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    toks = reg.get("tokens")
    if isinstance(toks, dict):
        for name, t in list(toks.items()):
            if not isinstance(t, dict) or "$value" in t:
                continue  # not a legacy token / already DTCG — idempotent
            dt = {"$value": t.get("value")}
            typ = _KIND_TO_TYPE.get(t.get("kind"))
            if typ:
                dt["$type"] = typ
            if t.get("description"):
                dt["$description"] = t["description"]
            toks[name] = dt
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    toks = reg.get("tokens")
    if isinstance(toks, dict):
        for name, t in list(toks.items()):
            if not isinstance(t, dict) or "$value" not in t:
                continue
            legacy = {"value": t.get("$value"), "kind": _kind_from(name, t.get("$type"))}
            if t.get("$description"):
                legacy["description"] = t["$description"]
            toks[name] = legacy
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1.8 → schema 8: `tokens` becomes a W3C DTCG document "
            "({ value, kind } → { $value, $type }) — standards-compliant, Figma/Style-Dictionary round-trippable.")


def memory_notes():
    return ("Design tokens are now authored in the W3C Design Tokens (DTCG) format: each token is "
            "`{ \"$value\": ..., \"$type\": ... }` (space/size/radius/fontSize all map to $type "
            "\"dimension\"). The document stays flat, so `var(--name)` in render bodies is unchanged. "
            "Update the constitution's token principle to name the DTCG standard; a cloned DS may add "
            "nested groups + `{alias}` references (also valid DTCG).")
