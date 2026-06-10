"""
0002_v13_to_v14 — schema 3 (v1.3 contract) → schema 4 (v1.4 contract).

The strategic v1.4 change: render bodies stop living as strings inside registry.json and
become real .js files. The registry becomes pure DATA (exactly what the playbook always
claimed), the resident state shrinks (token lever #1), and bodies become lintable/diffable
with no triple-escaping.

up(reg, base_dir):
  - For every component/screen with an inline `render`, write the body to
    render/components/<id>.js or render/screens/<id>.js (under base_dir),
    set `renderSrc` to that relative path, and delete the inline `render` string.
  - Stamp meta.schemaVersion = 4.
down(reg, base_dir):
  - Re-inline: read each renderSrc file back into `render`, delete `renderSrc`.
  - Stamp meta.schemaVersion = 3.

Bodies are written/read byte-for-byte (no newline normalization) so up→down→up is exactly
reversible. File I/O happens only on --apply: the runner never calls up()/down() on a
dry-run. base_dir is None only in pure-dict tests — then paths are set/cleared but no files
are touched.
"""
import copy
import os

FROM = 3
TO = 4

_SUBDIR = {"components": "render/components", "screens": "render/screens"}


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for kind, subdir in _SUBDIR.items():
        for item in reg.get(kind, []):
            if "render" not in item:
                continue
            body = item.get("render")
            rel = "%s/%s.js" % (subdir, item.get("id"))
            if base_dir is not None and body is not None:
                abspath = os.path.normpath(os.path.join(base_dir, rel))
                os.makedirs(os.path.dirname(abspath), exist_ok=True)
                with open(abspath, "w", encoding="utf-8") as f:
                    f.write(body)
            item["renderSrc"] = rel
            del item["render"]
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for kind in _SUBDIR:
        for item in reg.get(kind, []):
            if "renderSrc" not in item:
                continue
            src = item.get("renderSrc")
            if base_dir is not None and src:
                path = os.path.normpath(os.path.join(base_dir, src))
                try:
                    with open(path, encoding="utf-8") as f:
                        item["render"] = f.read()
                except FileNotFoundError:
                    # The file is gone — re-inline as empty rather than crash rollback.
                    item["render"] = item.get("render", "")
            else:
                item["render"] = item.get("render", "")
            del item["renderSrc"]
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1.3 → v1.4: extract inline render bodies to "
            "render/{components,screens}/<id>.js files (renderSrc); registry becomes pure data.")


def memory_notes():
    return ("Render bodies are now real files under render/components/ and render/screens/. "
            "Edit those .js files directly (lint/diff them like any code); the registry's "
            "renderSrc field points at each one. /pb:build --render still regenerates "
            "prototype.html. Do NOT re-add inline `render` strings.")
