"""
spec_parts.py — one reader for a component's anatomy parts, in either sidecar shape.

The tools that check or lower anatomy (lint_registry R-NEST / R-COMPOSE-MATCH, logic_check
L-ANATOMY, registry_to_figma.component_frame) all ask the same question — what parts does this
component declare, and which of them are instances of another component? — and there are two
shapes to answer it from:

  schema ≤ 12  anatomy: { parts: [ {n, name, anchor?, orgId?, required} ] }        (hand-typed)
  schema 13    anatomy: { <part>: {type, instanceOf?} } + layout + elements        (measured)

`parts(comp)` returns the legacy row shape for both, so a reader keeps one loop and a migrated
project is checked exactly as hard as an un-migrated one. A schema-13 `instance` part becomes a
row with `orgId = instanceOf`; required is `not visibleWhen`; the order is the layout's
(depth-first, root excluded), then any part the layout does not place, sorted.

Pure stdlib. No I/O. Deterministic.
"""


def is_new_anatomy(a):
    """The schema-13 anatomy: a map of part → {type}. (Mirrors 0011_specs_shape.is_new_anatomy.)"""
    return (isinstance(a, dict) and "parts" not in a and "renderProps" not in a
            and all(isinstance(v, dict) and "type" in v for v in a.values()))


def _layout_order(layout):
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for k in node:
                out.append(k)
                for child in node[k] if isinstance(node[k], list) else []:
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(layout)
    return out


def parts(comp):
    """→ [ {n, name, orgId?, anchor?, required, type?} ] for either shape; [] when none."""
    if not isinstance(comp, dict):
        return []
    a = comp.get("anatomy")
    if isinstance(a, dict) and isinstance(a.get("parts"), list):
        return [p for p in a["parts"] if isinstance(p, dict)]
    if not is_new_anatomy(a) or not a:
        return []
    els = comp.get("elements") if isinstance(comp.get("elements"), dict) else {}
    order = [k for k in _layout_order(comp.get("layout")) if k in a and k != "root"]
    seen = set(order)
    order += sorted(k for k in a if k != "root" and k not in seen)
    rows = []
    for i, name in enumerate(dict.fromkeys(order)):
        spec, el = a[name], els.get(name) if isinstance(els.get(name), dict) else {}
        row = {"n": i + 1, "name": name, "type": spec.get("type"), "required": "visibleWhen" not in el}
        if spec.get("type") == "instance" and spec.get("instanceOf"):
            row["orgId"] = spec["instanceOf"]
        if el.get("anchor"):
            row["anchor"] = el["anchor"]
        rows.append(row)
    return rows


def label(comp):
    """How a finding names the declaration it read: the field a human would go and fix."""
    a = comp.get("anatomy") if isinstance(comp, dict) else None
    return "anatomy.parts[]" if isinstance(a, dict) and "parts" in a else "anatomy (instanceOf)"
