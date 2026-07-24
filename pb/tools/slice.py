#!/usr/bin/env python3
"""
slice.py — read/write ONE slice of registry.json by id (token lever #1, at scale).

The build loop's core promise is "read/edit only the touched slice" (CLAUDE.md rule #1).
On a small registry that's free; on a big one (a real project can reach 8–10k lines) the
only way to *locate* a component/screen slice is to load the whole file — which drags the
entire registry into model context on every tweak and defeats the lever.

This tool closes that gap. It loads the whole file internally (unavoidable in Python) but
**emits / accepts only the one slice**, so the model's context stays a slice-sized. That is
where the token cost lives, not in the Python process.

  get   — print one slice as JSON (no whole-file read into context)
  set   — merge a patch into one slice, write the file back, everything else untouched
  list  — enumerate ids so the loop can find a target without loading bodies

Kinds:
  components | screens — a list of entries keyed by `id`; <id> selects one entry.
  tokens | meta        — a nested dict; <id> is a **dotted key path** (e.g. `meta.name`,
                         `tokens.brand`, `tokens.color.bg`).

Writes use the canonical registry format — `json.dumps(indent=2, ensure_ascii=False)` + a
trailing newline — so an empty-patch `set` is byte-identical (idempotent). Pure stdlib (NS4).

Usage:
  python3 slice.py get  <kind> <id> [--registry PATH]
  python3 slice.py set  <kind> <id> [--registry PATH] [--patch FILE]   # patch from FILE or stdin
  python3 slice.py list <kind>      [--registry PATH]

Exit: 0 on success; non-zero with a message on error (unknown kind, missing id/key, bad JSON).
"""
import argparse
import json
import os
import sys

LIST_KINDS = ("components", "screens")   # id-keyed lists
DICT_KINDS = ("tokens", "meta")          # dotted-key dicts
KINDS = LIST_KINDS + DICT_KINDS


def _load(reg_path):
    if not os.path.isfile(reg_path):
        sys.exit(f"slice: no registry at {reg_path}")
    with open(reg_path, encoding="utf-8") as f:
        return json.load(f)


def _write(reg_path, reg):
    # Canonical registry format (matches how pb writes registry.json): 2-space indent,
    # unicode preserved, one trailing newline. Keeps `set` byte-stable / idempotent.
    with open(reg_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")


def _find_entry(reg, kind, ident):
    """Return the id-keyed entry for LIST_KINDS, or exit if absent."""
    for item in reg.get(kind, []):
        if item.get("id") == ident:
            return item
    sys.exit(f"slice: no {kind[:-1]} with id {ident!r}")


def _dotted_get(reg, kind, key):
    """Resolve a dotted key path under a DICT_KIND. Exit if any segment is missing."""
    node = reg.get(kind, {})
    trail = kind
    for seg in key.split("."):
        if not isinstance(node, dict) or seg not in node:
            sys.exit(f"slice: no key {trail}.{seg!r}")
        node = node[seg]
        trail += "." + seg
    return node


def _deep_merge(dst, patch):
    """Recursively merge patch into dst: dicts merge, everything else (incl. lists) replaces.
    Cannot delete keys — a targeted patch adds/overwrites, matching the build loop's intent."""
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _read_patch(patch_file):
    raw = open(patch_file, encoding="utf-8").read() if patch_file else sys.stdin.read()
    if not raw.strip():
        return None  # empty patch → no-op (byte-stable rewrite)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        sys.exit(f"slice: patch is not valid JSON: {e}")


def cmd_get(args):
    reg = _load(args.registry)
    if args.kind in LIST_KINDS:
        entry = _find_entry(reg, args.kind, args.id)
    else:
        entry = _dotted_get(reg, args.kind, args.id)
    print(json.dumps(entry, indent=2, ensure_ascii=False))


def cmd_set(args):
    reg = _load(args.registry)
    patch = _read_patch(args.patch)

    if args.kind in LIST_KINDS:
        entry = _find_entry(reg, args.kind, args.id)
        if isinstance(patch, dict):
            before = json.dumps(entry, sort_keys=True)
            _deep_merge(entry, patch)
            changed = json.dumps(entry, sort_keys=True) != before
            keys = ", ".join(patch.keys()) if patch else "—"
        elif patch is None:
            changed, keys = False, "—"
        else:
            sys.exit("slice: a component/screen patch must be a JSON object")
    else:
        # DICT_KIND dotted set: merge dicts, otherwise replace the leaf.
        parts = args.id.split(".")
        parent = reg.setdefault(args.kind, {})
        for seg in parts[:-1]:
            parent = parent.setdefault(seg, {})
            if not isinstance(parent, dict):
                sys.exit(f"slice: {args.kind}.{seg} is not an object")
        leaf = parts[-1]
        before = json.dumps(parent.get(leaf), sort_keys=True)
        if patch is None:
            changed, keys = False, "—"
        elif isinstance(patch, dict) and isinstance(parent.get(leaf), dict):
            _deep_merge(parent[leaf], patch)
            changed = json.dumps(parent[leaf], sort_keys=True) != before
            keys = leaf
        else:
            parent[leaf] = patch
            changed = json.dumps(parent.get(leaf), sort_keys=True) != before
            keys = leaf

    _write(args.registry, reg)
    target = args.id if args.kind in DICT_KINDS else f"{args.kind[:-1]} {args.id}"
    print(f"{'✓ patched' if changed else '· no change'} {target}" + (f"  ({keys})" if changed else ""))


def cmd_list(args):
    reg = _load(args.registry)
    if args.kind in LIST_KINDS:
        for item in reg.get(args.kind, []):
            bits = [item.get("id", "?")]
            if item.get("name"):
                bits.append(item["name"])
            if item.get("level"):
                bits.append(f"[{item['level']}]")
            print("  ".join(bits))
    elif args.kind == "meta":
        for k in reg.get("meta", {}):
            print(k)
    else:  # tokens — print dotted paths of leaves (DTCG leaves carry $value)
        def walk(node, trail):
            if isinstance(node, dict) and "$value" in node:
                print(trail)
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{trail}.{k}" if trail else k)
        walk(reg.get("tokens", {}), "")


def main():
    p = argparse.ArgumentParser(prog="slice.py", description="Read/write one registry.json slice by id.")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp, with_id=True):
        sp.add_argument("kind", choices=KINDS)
        if with_id:
            sp.add_argument("id", help="entry id (components/screens) or dotted key (tokens/meta)")
        sp.add_argument("--registry", default="registry.json", help="path to registry.json")

    g = sub.add_parser("get", help="print one slice as JSON")
    add_common(g)
    g.set_defaults(func=cmd_get)

    s = sub.add_parser("set", help="merge a patch into one slice (patch from --patch FILE or stdin)")
    add_common(s)
    s.add_argument("--patch", help="JSON patch file (default: read stdin)")
    s.set_defaults(func=cmd_set)

    l = sub.add_parser("list", help="enumerate ids/keys for a kind")
    add_common(l, with_id=False)
    l.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
