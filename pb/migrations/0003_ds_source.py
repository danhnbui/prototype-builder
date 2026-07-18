"""
0003_ds_source — schema 4 (v1.4 contract) → schema 5 (v1.6 "DS truth" contract).

R1 makes the design system a first-class, cloned-and-verifiable source rather than a loose
`meta.designSystem` label. Two additive meta fields carry that:

  - `meta.platform`  — the DS/target platform the clone belongs to ("web" | "ios" |
                       "android" | "desktop" | ...). Defaults to "web".
  - `meta.dsSource`  — provenance of the cloned DS: null until `/pb:pull-ds` (or
                       `/pb:init`'s clone step) runs, then an object
                       `{ type, ref, clonedAt }` where type ∈ {figma, code-library,
                       mcp, common}. The full token/component snapshot lives in
                       `design-system/<name>/.source.json`; this is the pointer to it.

Both are ADDITIVE and optional in spirit — a project that never clones a DS keeps
`dsSource: null` and behaves exactly as before. The bump exists so the fields are part of
the contract (backfilled with defaults) and `check-drift` can rely on them.

up(reg):   add meta.platform ("web") and meta.dsSource (null) if absent; stamp 5.
down(reg): remove meta.platform and meta.dsSource; stamp 4.

Pure dict transform — no sidecar file I/O, so base_dir is accepted and ignored.
up→down→up is exactly reversible for a registry that had neither field.
"""
import copy

FROM = 4
TO = 5


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.setdefault("platform", "web")
    meta.setdefault("dsSource", None)
    meta["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    meta = reg.setdefault("meta", {})
    meta.pop("platform", None)
    meta.pop("dsSource", None)
    meta["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1.4 → v1.6: add meta.platform (default \"web\") and meta.dsSource "
            "(null until a DS is cloned) — the DS-truth provenance fields.")


def memory_notes():
    return ("The design system is now a cloned, verifiable source. Run /pb:pull-ds to clone "
            "your DS into design-system/<name>/ (+ registry tokens + a .source.json snapshot); "
            "meta.dsSource then records where it came from and meta.platform its platform. "
            "/pb:check-drift will audit the clone against that source. No constitution edit is "
            "required — these fields default safely (platform \"web\", dsSource null).")
