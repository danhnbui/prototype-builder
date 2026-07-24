"""
0008_externalize_spec — schema 9 → schema 10.

The v1.4 change (0002) moved render *bodies* out of registry.json into real files. This does
the same for the four bulky **handoff / spec-drawer** fields that were still inline and, on a
real project, dominate the file — measured at ~56% of a 7.9k-line registry:

    anatomy · spec · usage · uiLogic

They are consumed only by the client-side spec drawer in prototype.html and (anatomy only) by
lint_registry.py — never by the render bodies. So they can live in a sidecar and be re-inlined
at render/lint time, exactly like renderSrc. The registry gets ~half its lines back and the
build loop's touched-slice reads stay small (token lever #1 at scale).

up(reg, base_dir):
  - For every component/screen carrying any of the four fields, write those fields (only the
    present ones) as one JSON object to spec/components/<id>.json or spec/screens/<id>.json
    (under base_dir), set `specSrc` to that relative path, and delete the four inline fields.
  - Items with none of the four fields are left untouched (no sidecar, no specSrc).
  - Stamp meta.schemaVersion = 10.
down(reg, base_dir):
  - Re-inline: read each specSrc file back, restore its fields onto the entry, delete `specSrc`.
  - Stamp meta.schemaVersion = 9.

Sidecars are pretty-printed JSON (diffable/lintable). File I/O happens only on --apply: the
runner never calls up()/down() on a dry-run. base_dir is None only in pure-dict tests — then
`specSrc` is set/cleared but no files are touched (the fields are preserved in memory so up→down
is still reversible in that mode).
"""
import copy
import json
import os

FROM = 9
TO = 10

_SUBDIR = {"components": "spec/components", "screens": "spec/screens"}
_FIELDS = ("anatomy", "spec", "usage", "uiLogic")


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for kind, subdir in _SUBDIR.items():
        for item in reg.get(kind, []):
            present = {f: item[f] for f in _FIELDS if f in item}
            if not present:
                continue
            rel = "%s/%s.json" % (subdir, item.get("id"))
            if base_dir is not None:
                abspath = os.path.normpath(os.path.join(base_dir, rel))
                os.makedirs(os.path.dirname(abspath), exist_ok=True)
                with open(abspath, "w", encoding="utf-8") as f:
                    f.write(json.dumps(present, indent=2, ensure_ascii=False) + "\n")
                for f in present:
                    del item[f]
            item["specSrc"] = rel
            # In pure-dict mode (base_dir None) the fields stay inline so down() can reverse.
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for kind in _SUBDIR:
        for item in reg.get(kind, []):
            if "specSrc" not in item:
                continue
            src = item.get("specSrc")
            if base_dir is not None and src:
                path = os.path.normpath(os.path.join(base_dir, src))
                try:
                    with open(path, encoding="utf-8") as f:
                        for k, v in json.load(f).items():
                            item[k] = v
                except FileNotFoundError:
                    # Sidecar gone — restore nothing rather than crash rollback.
                    pass
            del item["specSrc"]
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1 schema 9 → 10: extract inline anatomy/spec/usage/uiLogic to "
            "spec/{components,screens}/<id>.json sidecars (specSrc); registry sheds its bulkiest fields.")


def memory_notes():
    return ("Component/screen handoff docs (anatomy, spec, usage, uiLogic) now live in "
            "spec/components/<id>.json and spec/screens/<id>.json, pointed at by each entry's "
            "`specSrc`. Edit those sidecar files directly; the UI Design spec drawer still shows "
            "them (render.py re-inlines them). Do NOT re-add inline anatomy/spec fields to registry.json.")
