"""
0004_export_tier — schema 5 (v1.6 contract) → schema 6 (v1.7 "export tiers" contract).

R2 lets a project emit code, not just the HTML prototype, at one of three tiers. Two additive
meta fields carry that:

  - `meta.outputTier`   — which tier the project's export targets:
                          "host"     (the default — the runnable single-file prototype, /pb:validate),
                          "scaffold" (deterministic registry → React+Tailwind, no MCP),
                          "hardened" (DS-integrated, repo-matched — resolved via MCP + review).
                          Defaults to "host" (== pre-R2 behavior).
  - `meta.exportTarget` — the machine-readable export/production target, mirroring the Stack Lock
                          (e.g. "html", "react-tailwind", "react-antd"). null until set at
                          /pb:init or /pb:handoff-dev. The Stack Lock in constitution.md is the
                          human-facing record; this is the field tools read. (Migrations never
                          write constitution.md — memory_notes() advises recording it there.)

Both are ADDITIVE and optional in spirit — a project that only ever hosts the prototype keeps
`outputTier: "host"` / `exportTarget: null` and behaves exactly as before.

up(reg):   add meta.outputTier ("host") and meta.exportTarget (null) if absent; stamp 6.
down(reg): remove them; stamp 5. Pure dict transform; base_dir accepted and ignored.
"""
import copy

FROM = 5
TO = 6


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.setdefault("outputTier", "host")
    meta.setdefault("exportTarget", None)
    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.pop("outputTier", None)
    meta.pop("exportTarget", None)
    meta["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1.6 → v1.7: add meta.outputTier (default \"host\") and meta.exportTarget "
            "(null until set) — the code-export tier fields.")


def memory_notes():
    return ("Projects can now export code via /pb:handoff-dev --tier=host|scaffold|hardened. "
            "Record the intended export target in the Stack Lock of memory/constitution.md "
            "(e.g. \"Export target: react-tailwind\") — meta.exportTarget mirrors it for the "
            "tooling. No constitution edit is auto-applied; defaults are safe (tier \"host\", "
            "target null == the existing runnable-prototype behavior).")
