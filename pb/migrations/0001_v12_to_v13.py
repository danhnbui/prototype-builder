"""
0001_v12_to_v13 — schema 2 (v1.2 contract) → schema 3 (v1.3 contract).

Changes applied by up() — all additive; no existing fields are removed:
  - meta.device: defaults to 'desktop' (new in v1.3 for the icon device switcher)
  - components[].scope: 'global' if a dsMatch is present, else 'local'
    (new in v1.3 for the Global | Local sub-tabs in UI Design)
  - flow: ensures the structured { populated, ... } dict shape;
    any existing flow.html is preserved as a legacy fallback — NOT stripped.
  - erd: same structural guarantee; existing erd.html preserved.
  - meta.schemaVersion set to 3.

down() is best-effort (additive-fields-only reversal):
  - Removes meta.device and components[].scope.
  - Sets meta.schemaVersion = 2.
  - Does NOT strip structured flow/erd fields (mermaid, stories[], table[]) that were
    added in v1.3 — v1.2 code ignores unknown keys, so the registry remains usable.
    Document this caveat clearly if rollback is performed.
"""

FROM = 2
TO = 3


def up(reg, base_dir=None):
    import copy
    reg = copy.deepcopy(reg)

    meta = reg.setdefault("meta", {})

    # meta.device — new in v1.3; default 'desktop' (safe for any existing project)
    if "device" not in meta:
        meta["device"] = "desktop"

    # components[].scope — new in v1.3; inferred from dsMatch presence
    for comp in reg.get("components", []):
        if "scope" not in comp:
            comp["scope"] = "global" if comp.get("dsMatch") else "local"

    # flow — ensure structured dict shape; preserve any legacy flow.html
    flow = reg.get("flow", {})
    if not isinstance(flow, dict):
        flow = {}
    flow.setdefault("populated", False)
    reg["flow"] = flow

    # erd — ensure structured dict shape; preserve any legacy erd.html
    erd = reg.get("erd", {})
    if not isinstance(erd, dict):
        erd = {}
    erd.setdefault("populated", False)
    reg["erd"] = erd

    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    import copy
    reg = copy.deepcopy(reg)

    meta = reg.get("meta", {})
    meta.pop("device", None)
    reg["meta"] = meta

    for comp in reg.get("components", []):
        comp.pop("scope", None)

    reg.get("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return "v1.2 → v1.3: add meta.device, components[].scope, structured flow/erd shape (legacy html preserved)."


def memory_notes():
    return None  # No constitution.md rule changes in this migration
