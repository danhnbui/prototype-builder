"""
0005_entry — schema 6 (v1.7 contract) → schema 7 (v1.8 "entry" contract).

R3 adds a second entry door: a project can be born from a **Figma frame** (`/pb:init --figma`)
instead of a PRD. One additive meta field records which door it came through, so later commands
(and the hand-off) can reason about provenance.

  - `meta.entry` — "prd" (the original PRD/Q&A intake) | "figma" (resolved from a Figma frame).
                   Defaults to "prd" (== every pre-R3 project).

Additive and optional in spirit — a PRD-born project keeps `entry: "prd"` and behaves exactly as
before.

up(reg):   add meta.entry ("prd") if absent; stamp 7.
down(reg): remove meta.entry; stamp 6. Pure dict transform; base_dir accepted and ignored.
"""
import copy

FROM = 6
TO = 7


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.setdefault("entry", "prd")
    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.pop("entry", None)
    meta["schemaVersion"] = FROM
    return reg


def describe():
    return "v1.7 → v1.8: add meta.entry (\"prd\" | \"figma\", default \"prd\") — the intake provenance."


def memory_notes():
    return ("Projects can now be born from a Figma frame via /pb:init --figma (meta.entry = \"figma\") "
            "in addition to a PRD (meta.entry = \"prd\", the default). Unmapped Figma layers are logged "
            "to gaps.md as labeled placeholders — never invented components. No constitution edit is "
            "required; the default \"prd\" preserves existing behavior.")
