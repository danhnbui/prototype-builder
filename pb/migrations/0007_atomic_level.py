"""
0007_atomic_level — schema 8 → schema 9: atomic `level` becomes REQUIRED (component-first law).

The component-first / strict-atomic-design contract makes `components[].level` a required field
(`atom | molecule | organism | template`) and treats every screen as `level: "page"`. Render
bodies above the atom level must be pure composition (pbUse) — enforced by lint's
R-LEVEL / R-COMPOSE / R-LEVEL-ORDER — which is what lowers 1:1 to a Figma INSTANCE tree.

This migration only backfills the field so the schema-9 contract holds; it cannot rewrite render
bodies to compose (that's a hand edit per component, gated by lint). Legacy components without a
level get a conservative heuristic (a DS-matched or primitive-named component → `atom`, else
`organism`), which the author should review.

up(reg):   backfill missing components[].level (heuristic); set screens[].level = "page"; stamp 9.
down(reg): remove screens[].level (new in 9); leave components[].level (valid pre-9 too); stamp 8.
"""
import copy

FROM = 8
TO = 9

_ATOM_HINTS = ("button", "input", "icon", "label", "badge", "text", "link", "checkbox",
               "radio", "avatar", "chip", "tag", "switch", "toggle", "field", "heading", "paragraph")


def _infer_level(c):
    if c.get("level"):
        return c["level"]
    if c.get("dsMatch"):
        return "atom"
    name = (str(c.get("id", "")) + " " + str(c.get("name", ""))).lower()
    return "atom" if any(k in name for k in _ATOM_HINTS) else "organism"


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for c in reg.get("components", []) or []:
        if isinstance(c, dict):
            c["level"] = _infer_level(c)
    for s in reg.get("screens", []) or []:
        if isinstance(s, dict):
            s.setdefault("level", "page")
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for s in reg.get("screens", []) or []:
        if isinstance(s, dict):
            s.pop("level", None)
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("schema 8 → 9: atomic `level` is now required on every component "
            "(atom|molecule|organism|template); screens are `page`. Component-first / atomic-design law.")


def memory_notes():
    return ("Component-first is now enforced: every component declares an atomic `level` and only "
            "`atom` render bodies may emit raw HTML primitives — molecules/organisms/screens must be "
            "pure composition via pbUse() of lower-level components (lint R-LEVEL / R-COMPOSE / "
            "R-LEVEL-ORDER, ERROR under --strict). Add the component-first + atomic-composition law to "
            "the constitution, and note the rule that a component's level follows its DS-component "
            "granularity (a dsMatch'd component is an atom even if visually composite).")
