"""
0011_specs_shape — schema 12 → schema 13.

The component spec sidecar (`spec/components/<id>.json`, schema 10) carried its anatomy and its
redlines in two hand-authored shapes:

    anatomy: string | { renderProps, parts: [ {n, name, anchor, orgId?, required, token?} ] }
    spec:    string | { renderProps, marginX, legend[], stack: [ {name, anchor} ] }

Nobody measured any of it. `required: false` was typed by hand, a token was copied in by hand, and
nothing noticed when the render body moved on. Schema 13 replaces both with the shape the Specs
plugin uses (specsplugin.com/schema: anatomy, layout, elements, styles), and the numbers in it are
MEASURED from the live render by `tools/spec_measure.py`, which `/pb:build` §3a runs when a
component is built or changed:

    anatomy:  { <part>: { type: text|glyph|vector|container|slot|instance, instanceOf? } }
    layout:   [ { "root": [ <part> | { <part>: [ … ] } ] } ]
    elements: { <part>: { parent, anchor?, styles?{ padding, itemSpacing, cornerRadius,
                                                     backgroundColor, textColor }, visibleWhen? } }
    shape:    "card" (root has a fill, a radius and padding, is not a native control element —
              <button>/<a>/<input>/<select>/<textarea> — and holds >= 2 non-root parts) | absent
    measured: { at, by, props }

Required vs optional is DERIVED, never typed: a part is optional iff it carries `visibleWhen`.

What up() does, per component sidecar (components only — a screen's sidecar is left as it is):
  - a prose `anatomy` / `spec` string → `anatomyNote` / `specNote` (verbatim).
  - a structured `anatomy.parts[]` / `spec.stack[]` → best-effort anatomy/layout/elements:
      part name → a kebab key; `orgId` → `type: instance` + `instanceOf`; otherwise the type is
      guessed from the name (text / glyph / container); `anchor` is kept on the element so
      spec_measure can find the part in a body that has no `data-part` markers yet;
      `required: false` → `visibleWhen: { prop: null, is: "set" }` — optional, condition not yet
      measured (the next `/pb:build` binds it to the real prop).
  - the WHOLE original object goes under `legacy.anatomy` / `legacy.spec`, so nothing is dropped:
    `n`, `token`, `renderProps`, `marginX`, `legend` and anything else this mapping does not name.
  - a sidecar already in the new shape is left alone (idempotent).
down() restores `anatomy` / `spec` from `legacy` / the notes. The new-shape keys are parked under
`schema13` unless up() would rebuild exactly those keys, with exactly those values, from the legacy
alone (a measurement written since, or a sidecar that arrived with new keys of its own, is never
rebuildable). The next up() restores what is parked and derives nothing beside it, so up→down→up is
lossless — including for a sidecar that already carries new keys AND a legacy `spec.stack`: the
derivation fills in only a sidecar that has no new key at all, and never overwrites one.

File I/O happens only on --apply (the runner never calls up()/down() on a dry-run). base_dir None
(pure-dict tests) converts the fields still inline on a component instead (0008's pure mode leaves
them there).

Rollback: the runner snapshots `spec/components` and `spec/screens` next to the registry backup
(`.pb-backups/spec.<from>.<ts>/`) and `--rollback` restores them with the registry; so does a failed
apply, since this migration rewrites the sidecars while the chain runs, before the registry is written.
"""
import copy
import json
import os
import re
import tempfile

FROM = 12
TO = 13

NEW_KEYS = ("anatomy", "layout", "elements", "shape", "measured")
_NOTE = {"anatomy": "anatomyNote", "spec": "specNote"}

_TEXTY = re.compile(r"label|title|text|caption|help|hint|heading|sub|amount|value|name|desc", re.I)
_GLYPHY = re.compile(r"icon|glyph|chevron|arrow|badge-dot|avatar", re.I)


def _key(name, taken, i):
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-") or "part-%d" % (i + 1)
    if base in ("root", "parts"):
        base = base + "-part"
    k, n = base, 2
    while k in taken:
        k, n = "%s-%d" % (base, n), n + 1
    taken.add(k)
    return k


def _guess_type(part):
    if part.get("orgId"):
        return "instance"
    probe = "%s %s" % (part.get("name") or "", part.get("anchor") or "")
    if _GLYPHY.search(probe):
        return "glyph"
    if _TEXTY.search(probe):
        return "text"
    return "container"


def is_new_anatomy(a):
    """The schema-13 anatomy: a map of part → {type}. An empty dict counts (nothing measured yet)."""
    return (isinstance(a, dict) and "parts" not in a and "renderProps" not in a
            and all(isinstance(v, dict) and "type" in v for v in a.values()))


def _derive(legacy_anatomy, legacy_spec):
    """anatomy/layout/elements from the legacy structured objects. Pure; deterministic."""
    rows = []
    parts = legacy_anatomy.get("parts") if isinstance(legacy_anatomy, dict) else None
    for p in parts if isinstance(parts, list) else []:
        if isinstance(p, dict):
            rows.append(p)
    stack = legacy_spec.get("stack") if isinstance(legacy_spec, dict) else None
    known = {(r.get("name") or "").strip().lower() for r in rows}
    for s in stack if isinstance(stack, list) else []:
        if isinstance(s, dict) and (s.get("name") or "").strip().lower() not in known:
            rows.append({"name": s.get("name"), "anchor": s.get("anchor"), "required": True})
            known.add((s.get("name") or "").strip().lower())
    if not rows:
        return None
    rows.sort(key=lambda r: (r.get("n") if isinstance(r.get("n"), (int, float)) else 1e9))
    taken = set()
    anatomy = {"root": {"type": "container"}}
    elements = {"root": {"parent": None}}
    order = []
    for i, r in enumerate(rows):
        k = _key(r.get("name"), taken, i)
        entry = {"type": _guess_type(r)}
        if r.get("orgId"):
            entry["instanceOf"] = r["orgId"]
        anatomy[k] = entry
        el = {"parent": "root"}
        if r.get("anchor"):
            el["anchor"] = r["anchor"]
        if r.get("required") is False:
            el["visibleWhen"] = {"prop": None, "is": "set"}
        elements[k] = el
        order.append(k)
    return {"anatomy": anatomy, "layout": [{"root": order}], "elements": elements}


def _has_new(s):
    """Does this sidecar already hold any schema-13 key (or a parked set of them)? Then it is a
    measured / hand-typed new-shape sidecar, and the legacy derivation has no business adding to it."""
    if isinstance(s.get("schema13"), dict) and s["schema13"]:
        return True
    return any(k in s and (k != "anatomy" or is_new_anatomy(s[k])) for k in NEW_KEYS)


def convert(side):
    """One sidecar dict, legacy → schema 13. Returns (new_dict, changed)."""
    s = copy.deepcopy(side)
    legacy = dict(s.get("legacy") or {}) if isinstance(s.get("legacy"), dict) else {}
    has_new = _has_new(s)
    changed = False
    la = ls = None
    for field in ("anatomy", "spec"):
        if field not in s:
            continue
        v = s[field]
        if field == "anatomy" and is_new_anatomy(v):
            continue
        if isinstance(v, str):
            s[_NOTE[field]] = v
        else:
            legacy[field] = v
            if field == "anatomy":
                la = v
            else:
                ls = v
        del s[field]
        changed = True
    if changed:
        derived = _derive(la, ls)
        if derived and not has_new:        # a sidecar with ANY new key keeps exactly those keys
            s.update(derived)
        if legacy:
            s["legacy"] = legacy
    stash = s.pop("schema13", None)
    if isinstance(stash, dict):
        s.update(stash)
        changed = True
    return s, changed


def revert(side):
    """One sidecar dict, schema 13 → legacy. Returns (new_dict, changed)."""
    s = copy.deepcopy(side)
    legacy = s.get("legacy") if isinstance(s.get("legacy"), dict) else {}
    present = {k: s[k] for k in NEW_KEYS if k in s and (k != "anatomy" or is_new_anatomy(s[k]))}
    if not present and not legacy and not any(n in s for n in _NOTE.values()):
        return s, False
    # What up() would rebuild from the legacy alone needs no parking — but only when it is the
    # same set of keys with the same values. A key that is present and not rebuilt (shape, measured),
    # one that differs, or one that is ABSENT and would be rebuilt (a sidecar with anatomy but no
    # layout) all make the rebuild wrong, so the whole new-shape set is parked and up() restores it.
    rebuilt = _derive(legacy.get("anatomy"), legacy.get("spec")) or {}
    exact = set(present) == set(rebuilt) and all(rebuilt[k] == present[k] for k in present)
    park = {} if exact else present
    for k in present:
        del s[k]
    s.pop("legacy", None)
    for field, note in _NOTE.items():
        if field in legacy:
            s[field] = legacy[field]
        elif note in s:
            s[field] = s[note]
        s.pop(note, None)
    extra = {k: v for k, v in legacy.items() if k not in _NOTE}
    if extra:
        s["legacy"] = extra
    if park:
        s["schema13"] = park
    return s, True


def _sidecars(reg, base_dir):
    for item in reg.get("components", []) or []:
        if isinstance(item, dict) and item.get("specSrc"):
            yield os.path.normpath(os.path.join(base_dir, item["specSrc"]))


def _write_atomic(path, text):
    """Temp file beside the sidecar, then os.replace: a crash mid-write leaves the old sidecar,
    never half of one. (The runner backs the sidecars up as well; this closes the smaller hole.)"""
    d, base = os.path.split(path)
    fd, tmp = tempfile.mkstemp(prefix="." + base + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except OSError:
            os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _rewrite(path, fn):
    try:
        with open(path, encoding="utf-8") as f:
            side = json.load(f)
    except (OSError, ValueError):
        return  # a missing / unreadable sidecar is lint's to report (R-SPECSRC), not ours to crash on
    if not isinstance(side, dict):
        return
    new, changed = fn(side)
    if changed:
        _write_atomic(path, json.dumps(new, indent=2, ensure_ascii=False) + "\n")


def _inline(reg, fn):
    for item in reg.get("components", []) or []:
        if not isinstance(item, dict):
            continue
        side = {k: item[k] for k in list(item.keys())
                if k in NEW_KEYS + ("spec", "legacy", "schema13") + tuple(_NOTE.values())}
        if not side:
            continue
        new, changed = fn(side)
        if changed:
            for k in side:
                item.pop(k, None)
            item.update(new)


def up(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    if base_dir is not None:
        for path in _sidecars(reg, base_dir):
            _rewrite(path, convert)
    else:
        _inline(reg, convert)
    reg.setdefault("meta", {})["schemaVersion"] = TO
    return reg


def down(reg, base_dir=None):
    reg = copy.deepcopy(reg)
    if base_dir is not None:
        for path in _sidecars(reg, base_dir):
            _rewrite(path, revert)
    else:
        _inline(reg, revert)
    reg.setdefault("meta", {})["schemaVersion"] = FROM
    return reg


def describe():
    return ("v1 schema 12 → 13: component spec sidecars take the Specs-plugin shape — "
            "anatomy{part:{type}} + layout + elements{styles, visibleWhen} + shape, measured by "
            "spec_measure.py; legacy anatomy.parts[]/spec.stack[] kept under `legacy`, prose under anatomyNote/specNote.")


def memory_notes():
    return ("Component specs are now MEASURED, not typed. spec/components/<id>.json carries "
            "`anatomy` (part → type), `layout`, `elements` (padding / item spacing / radius / colours, "
            "each mapped to a token when the value matches one) and `shape`; a part is optional iff it "
            "has `visibleWhen`. /pb:build re-measures a component on its next build (§3a runs "
            "`tools/spec_measure.py --component <id> --write`), which replaces the best-effort "
            "conversion this update made. Mark parts in render bodies with `data-part=\"<name>\"` "
            "(design-component-build §3). Old structured anatomy/spec stay under `legacy` in each sidecar.")
