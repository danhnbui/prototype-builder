#!/usr/bin/env python3
"""
clone_ds.py — materialize a normalized design-system export into a pb project (R1, v1.6).

pb's "DS truth": a design system is a cloned, verifiable source — not a loose label. The
model-driven `/pb:pull-ds` resolves the DS via the fallback ladder (a dedicated DS MCP → a
Figma design-system link → the current code library → a common DS) and normalizes it into a
single **DS-export** JSON. This tool is the deterministic half — given that export it:

  1. merges its `tokens` into `registry.json`'s `tokens{}` (additive by default),
  2. sets `meta.designSystem` / `meta.platform` / `meta.dsSource` (provenance),
  3. writes `design-system/<name>/<name>.md` — the scannable DS reference,
  4. writes `design-system/<name>/.source.json` — the snapshot `/pb:check-drift` compares
     the live source against to detect DS drift.

Pure stdlib (NS4). Deterministic except for the `clonedAt` provenance stamp.

DS-export shape (normalized — what the ladder produces / a fixture supplies):
  {
    "name": "acme-ds",
    "platform": "web",
    "source": { "type": "figma|code-library|mcp|common", "ref": "<url|path|name>" },
    "tokens": { "color-brand": { "value": "#2563eb", "kind": "color" }, ... },
    "components": [ { "id": "button", "level": "atom", "variants": ["primary"],
                     "purpose": "...", "renderFn": "renderCmpButton" }, ... ]
  }

Usage:
  python3 clone_ds.py --from <ds-export.json> [--registry registry.json] [--name NAME]
                      [--overwrite-tokens]
  python3 clone_ds.py --drift <current-export.json> [--registry registry.json] [--name NAME]

Exit: 0 ok / in-sync · 2 usage or IO error · 3 drift detected (--drift only)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

_KINDS_ORDER = ["color", "type", "font", "fontSize", "space", "size", "radius",
                "shadow", "border", "opacity", "duration", "zIndex", "breakpoint", "other"]


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ds_dir(registry_path, name):
    root = os.path.dirname(os.path.abspath(registry_path))
    return os.path.join(root, "design-system", name)


def _render_reference_md(name, tokens, components):
    """Deterministic DS reference: foundations grouped by kind + a component index + the rules."""
    by_kind = {}
    for tname, t in sorted(tokens.items()):
        by_kind.setdefault(t.get("kind", "other"), []).append(tname)
    lines = [f"# {name}", "",
             "> The global design-system reference for this project, cloned by `/pb:pull-ds`.",
             "> The build loop reads this **DS-first** (R0) before creating any component.",
             "> Regenerate it by re-cloning — never hand-edit (it must match `.source.json`).", "",
             "## Foundations (tokens → CSS vars)", "",
             "| Kind | Tokens |", "|---|---|"]
    kinds = [k for k in _KINDS_ORDER if k in by_kind] + [k for k in sorted(by_kind) if k not in _KINDS_ORDER]
    for k in kinds:
        names = ", ".join(f"`--{n}`" for n in by_kind[k])
        lines.append(f"| {k} | {names} |")
    lines += ["",
              f"Foundations map to the `tokens{{}}` block of `registry.json` (`{{ name, value, kind }}`) "
              "and are applied onto `:root` at render.", "",
              "## Component index  ← scan this first", "",
              "| Component | renderFn | Variants | Purpose | Level |", "|---|---|---|---|---|"]
    if components:
        for c in components:
            variants = ", ".join(c.get("variants", [])) or "—"
            lines.append("| `%s` | `%s` | %s | %s | %s |" % (
                c.get("id", "?"), c.get("renderFn", ""), variants,
                c.get("purpose", "").replace("|", "\\|"), c.get("level", "")))
    else:
        lines.append("| _(none exported yet)_ | | | | |")
    lines += ["",
              "## Rules", "",
              "- **R0 · DS-first, Local-first.** Reuse a global or local component before building anything.",
              "- **R0.5 · Atomic composition.** Tag every component with a `level` and compose upward.",
              "- **R1 · Reuse.** If a component covers the function, reuse it (point the element's `orgId` at it).",
              "- **R2 · Variant before spawn.** New state/size/style → add a variant, never a second component.",
              "- **R3 · Auto-layout.** Every Figma frame uses auto-layout; no absolutely positioned children.",
              "- **R4 · Naming.** Kebab-case `id`, unique; `renderFn` = `renderCmp{PascalCase}`.", "",
              "## Naming contract  (enforced by `/pb:build-check-design-system` and `/pb:build-figma-handoff`)", "",
              "- `id` — kebab-case, globally unique. tokens — `kind ∈ color|type|space|size|radius|…`; no raw hex/px.", ""]
    return "\n".join(lines)


def clone(export, registry_path, name=None, overwrite_tokens=False):
    reg = _load(registry_path)
    name = name or export.get("name") or reg.get("meta", {}).get("designSystem", {}).get("name") or "design-system"
    source = export.get("source") or {"type": "common", "ref": name}
    platform = export.get("platform", "web")
    ex_tokens = export.get("tokens", {})
    ex_components = export.get("components", [])

    # 1 · merge tokens (additive by default)
    reg.setdefault("tokens", {})
    added, updated, skipped = [], [], []
    for tname, tval in ex_tokens.items():
        if tname not in reg["tokens"]:
            reg["tokens"][tname] = tval
            added.append(tname)
        elif overwrite_tokens and reg["tokens"][tname] != tval:
            reg["tokens"][tname] = tval
            updated.append(tname)
        else:
            skipped.append(tname)

    # 2 · meta provenance
    meta = reg.setdefault("meta", {})
    ds = meta.setdefault("designSystem", {"name": "", "designLink": None, "codeLibrary": None, "linked": False})
    ds["name"] = name
    if source.get("type") == "figma":
        ds["designLink"] = source.get("ref")
    elif source.get("type") == "code-library":
        ds["codeLibrary"] = source.get("ref")
    ds["linked"] = bool(ds.get("name") and (ds.get("codeLibrary") or ds.get("designLink")))
    meta["platform"] = platform
    clonedAt = _now()
    meta["dsSource"] = {"type": source.get("type"), "ref": source.get("ref"), "clonedAt": clonedAt}

    # 3 + 4 · write DS reference + provenance snapshot
    dsdir = _ds_dir(registry_path, name)
    os.makedirs(dsdir, exist_ok=True)
    with open(os.path.join(dsdir, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(_render_reference_md(name, ex_tokens, ex_components))
    snapshot = {"name": name, "platform": platform, "source": source, "clonedAt": clonedAt,
                "tokens": ex_tokens, "components": ex_components}
    with open(os.path.join(dsdir, ".source.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)

    print(f"✓ cloned DS '{name}' ({platform}) from {source.get('type')}:{source.get('ref')}")
    print(f"  tokens: +{len(added)} added, {len(updated)} updated, {len(skipped)} unchanged "
          f"({len(reg['tokens'])} total) · components: {len(ex_components)}")
    print(f"  wrote design-system/{name}/{name}.md + design-system/{name}/.source.json")
    print(f"  meta.dsSource = {json.dumps(meta['dsSource'])}")
    return 0


def _diff_tokens(a, b):
    """(added, removed, changed) token-name lists comparing snapshot a → current b."""
    ak, bk = set(a), set(b)
    added = sorted(bk - ak)
    removed = sorted(ak - bk)
    changed = sorted(k for k in ak & bk if a[k] != b[k])
    return added, removed, changed


def drift(current_export, registry_path, name=None):
    """Compare a freshly-fetched source export against the stored .source.json snapshot."""
    reg = _load(registry_path)
    name = name or current_export.get("name") or reg.get("meta", {}).get("designSystem", {}).get("name") or "design-system"
    snap_path = os.path.join(_ds_dir(registry_path, name), ".source.json")
    if not os.path.isfile(snap_path):
        print(f"⚠ no clone to audit: {os.path.relpath(snap_path)} missing — run /pb:pull-ds first")
        return 2
    snap = _load(snap_path)
    added, removed, changed = _diff_tokens(snap.get("tokens", {}), current_export.get("tokens", {}))
    snap_c = {c.get("id") for c in snap.get("components", [])}
    cur_c = {c.get("id") for c in current_export.get("components", [])}
    comp_added, comp_removed = sorted(cur_c - snap_c), sorted(snap_c - cur_c)
    n = len(added) + len(removed) + len(changed) + len(comp_added) + len(comp_removed)
    if n == 0:
        print(f"✅ DS in sync — '{name}' clone matches source (cloned {snap.get('clonedAt')}).")
        return 0
    print(f"⚠ DS DRIFT — '{name}' clone diverges from source (cloned {snap.get('clonedAt')}); {n} change(s):")
    for label, items in (("token changed", changed), ("token added at source", added),
                         ("token removed at source", removed),
                         ("component added at source", comp_added),
                         ("component removed at source", comp_removed)):
        for it in items:
            print(f"  · {label}: {it}")
    print("  → re-run /pb:pull-ds to re-clone, or reconcile intentionally.")
    return 3


def main(argv=None):
    p = argparse.ArgumentParser(prog="clone_ds.py", add_help=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--from", dest="src", metavar="EXPORT.json", help="clone this normalized DS export")
    g.add_argument("--drift", dest="drift_src", metavar="CURRENT.json", help="audit a fresh source export vs the clone")
    p.add_argument("registry", nargs="?", default=None, help="path to registry.json (default: ./registry.json)")
    p.add_argument("--registry", dest="registry_opt", default=None, help="alias for the positional registry arg")
    p.add_argument("--name", default=None)
    p.add_argument("--overwrite-tokens", action="store_true")
    args = p.parse_args(argv)
    registry = args.registry or args.registry_opt or "registry.json"
    try:
        if args.src:
            return clone(_load(args.src), registry, args.name, args.overwrite_tokens)
        return drift(_load(args.drift_src), registry, args.name)
    except (OSError, json.JSONDecodeError) as e:
        print(f"clone_ds: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
