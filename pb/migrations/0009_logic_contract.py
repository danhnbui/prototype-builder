"""
0009_logic_contract — schema 10 → schema 11.

Three additive things, one migration, and nothing anywhere is deleted or rewritten.

1. `logicSrc` — the logic contract sidecar, `logic/{components,screens}/<id>.json`, mirroring
   `specSrc` (0008). Two halves, by design (D-28):
     DERIVED, rewritten on every `logic_extract.py --contracts` run — `seam`, `handlers`,
       `disclosure`. A tool owns these; a human never edits them.
     HAND-AUTHORED, never touched by a tool — `writes[]` (which store slices the item mutates)
       and `affordances[].why`. Static derivation traces reads but NOT writes, because the
       mutations happen inside store helpers, so `writes[]` is the one thing a human must state.
   This migration writes neither half. It writes only `notes[]`.

2. `ia` — the Information Architecture slice (D-16): `jobs[]` in the three-field JTBD form and
   `layers[]` with one declared purpose each. Seeded unpopulated, like `flow` and `erd`.

3. `runtime[]` — the project's own module layer (D-28). Seeded empty.

`notes[]` — the reason this rollback is lossless
------------------------------------------------
Logic prose today lands in two fields that were never meant to hold it: `logicNotes` (inline on
the entry) and `uiLogic` (in the schema-10 spec sidecar, or inline on older projects). Sampling a
real project found most of it is dated rationale — *"RESTRUCTURED 2026-08-10 to Figma 8110:35213…"*
— that belongs in `decisions.md` and landed there because nothing routed it anywhere else.

Classifying it needs a judgement call a deterministic migration cannot make, and translating it
needs a model call inside a deterministic pipeline. So this migration does neither. It **copies**
each piece **verbatim** into `notes[]` beside a `source` pointer to where the original still is,
and leaves the original exactly where it was — not deleted, not moved, not one character rewritten.

Because the prose never moves, `down()` is pb's first information-lossless rollback: it removes
only what `up()` created. A sidecar that has since been hand-authored is LEFT ON DISK and
reported, rather than deleted — rolling a schema back is not a reason to throw away someone's
`writes[]`.

up(reg, base_dir):
  - write logic/<kind>/<id>.json for every entry carrying logic prose; set `logicSrc`
  - seed `ia` (unpopulated) and `runtime` (empty) if absent
  - stamp meta.schemaVersion = 11
down(reg, base_dir):
  - delete each sidecar whose content still matches what up() wrote; drop `logicSrc`
  - drop the seeded `ia` / `runtime` ONLY while they are still empty
  - stamp meta.schemaVersion = 10
"""
import copy
import json
import os

FROM = 10
TO = 11

_SUBDIR = {"components": "logic/components", "screens": "logic/screens"}
_PROSE = ("logicNotes", "uiLogic")


def _notes_from(value, pointer):
    """One prose value → note entries, copied VERBATIM. A list becomes one entry per element so
    the `source` pointer stays precise; a string becomes one. Anything else is JSON-encoded
    rather than dropped — an unreadable note is still better than a lost one."""
    if value is None or value == "" or value == []:
        return []
    if isinstance(value, list):
        out = []
        for i, part in enumerate(value):
            text = part if isinstance(part, str) else json.dumps(part, ensure_ascii=False)
            if text:
                out.append({"source": "%s/%d" % (pointer, i), "text": text})
        return out
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return [{"source": pointer, "text": text}] if text else []


def _spec_prose(item, base_dir):
    """`uiLogic` as schema 10 left it: in the spec sidecar. Returns (value, pointer) or (None, None).
    The sidecar is only READ here — 0008 owns it, and this migration does not touch it."""
    src = item.get("specSrc")
    if not src or base_dir is None:
        return None, None
    path = os.path.normpath(os.path.join(base_dir, src))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, None
    if isinstance(data, dict) and data.get("uiLogic") not in (None, "", []):
        return data["uiLogic"], "%s#/uiLogic" % src
    return None, None


def _contract_for(kind, item, base_dir):
    """The sidecar up() writes: copied prose plus the two empty hand-authored fields. The derived
    half is deliberately absent — `logic_extract.py --contracts` owns it and rewrites it every run,
    so writing a snapshot of it here would only create something to go stale."""
    notes = []
    for field in _PROSE:
        if field in item:
            notes += _notes_from(item[field], "registry.json#/%s/%s/%s" % (kind, item.get("id"), field))
    value, pointer = _spec_prose(item, base_dir)
    if value is not None:
        notes += _notes_from(value, pointer)
    if not notes:
        return None
    return {"notes": notes, "writes": [], "affordances": []}


def _dump(contract):
    return json.dumps(contract, indent=2, ensure_ascii=False) + "\n"


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    for kind, subdir in _SUBDIR.items():
        for item in reg.get(kind, []):
            contract = _contract_for(kind, item, base_dir)
            if contract is None:
                continue
            rel = "%s/%s.json" % (subdir, item.get("id"))
            if base_dir is not None:
                path = os.path.normpath(os.path.join(base_dir, rel))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(_dump(contract))
            item["logicSrc"] = rel
    # The two new slices. setdefault, never overwrite: a project may already carry them from a
    # hand-authored /pb:init, and this migration is not entitled to reset them.
    reg.setdefault("ia", {"populated": False})
    reg.setdefault("runtime", [])
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    kept = []
    for kind, subdir in _SUBDIR.items():
        for item in reg.get(kind, []):
            if "logicSrc" not in item:
                continue
            rel = item.get("logicSrc")
            if base_dir is not None and rel:
                path = os.path.normpath(os.path.join(base_dir, rel))
                expected = _contract_for(kind, item, base_dir)
                try:
                    with open(path, encoding="utf-8") as f:
                        on_disk = f.read()
                except OSError:
                    on_disk = None
                if on_disk is None:
                    pass                                   # already gone — nothing to undo
                elif expected is not None and on_disk == _dump(expected):
                    os.remove(path)                        # exactly what up() wrote; safe to undo
                else:
                    kept.append(rel)                       # hand-authored since — never delete
            del item["logicSrc"]
    for rel, empty in (("ia", {"populated": False}), ("runtime", [])):
        if reg.get(rel) == empty:
            del reg[rel]
    if kept:
        print("  note: %d logic contract(s) kept — edited since the migration: %s"
              % (len(kept), ", ".join(sorted(kept)[:5]) + (" …" if len(kept) > 5 else "")))
    if base_dir is not None:
        for subdir in _SUBDIR.values():
            path = os.path.normpath(os.path.join(base_dir, subdir))
            try:
                os.rmdir(path)                             # only when it emptied out
            except OSError:
                pass
        try:
            os.rmdir(os.path.normpath(os.path.join(base_dir, "logic")))
        except OSError:
            pass
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1 schema 10 → 11: add the logic contract (logic/{components,screens}/<id>.json via "
            "logicSrc, prose COPIED into notes[] and left in place), the `ia` slice, and "
            "registry.runtime[]; nothing is deleted, so the rollback is lossless.")


def memory_notes():
    return ("Logic now has a home of its own: logic/components/<id>.json and logic/screens/<id>.json, "
            "pointed at by each entry's `logicSrc`. Two halves — `seam`/`handlers`/`disclosure` are "
            "DERIVED (rewritten by `logic_extract.py --contracts`; never hand-edit them), while "
            "`writes[]` and `affordances[].why` are yours to write and no tool will touch them.\n"
            "The migration COPIED existing `logicNotes`/`uiLogic` prose into `notes[]` with a pointer "
            "back to the original, which is still exactly where it was. Most of it is dated rationale "
            "that belongs in memory/decisions.md — move it there as you touch each item, then delete "
            "the copy. Nothing is deleted for you.\n"
            "Two new slices: `ia` (jobs + layers — author it at /pb:init or /pb:plan) and `runtime[]` "
            "(the project's own modules, inlined before every render body — a real file per entry, "
            "instead of a component whose render body returns '').")
