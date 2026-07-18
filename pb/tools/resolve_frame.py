#!/usr/bin/env python3
"""
resolve_frame.py — the Figma-frame entry door (R3, v1.8): map a frame's layers to DS components.

pb's second entry door (`/pb:init --figma`): instead of a PRD, start from a real Figma frame.
The model-driven half reads the frame via the Figma MCP and normalizes it to a **frame-export**;
this deterministic half maps each layer to a **design-system component that already exists in the
project** (the DS cloned by `/pb:pull-ds`, plus any registry components) and emits a registry screen
patch. A layer with no match is **never invented** — it becomes a labeled placeholder element and a
line in `gaps.md`, so the gap is visible and honest.

Pure stdlib. Deterministic. Holds DS fidelity at entry: nothing is created that isn't a real,
already-known component.

frame-export shape (normalized — what /pb:init --figma produces from the Figma MCP):
  {
    "frame":  { "id": "1:23", "name": "Checkout" },
    "layers": [
      { "name": "Primary Button", "type": "INSTANCE", "component": "button" },   // explicit DS hint
      { "name": "Search Field",   "type": "INSTANCE" },                          // matched by name
      { "name": "Promo Banner",   "type": "FRAME" }                              // no match → gap
    ]
  }

A layer maps when `component` (or the kebab of `name`) equals a known component id. Known ids =
`registry.components[].id` ∪ every `design-system/<name>/.source.json` `components[].id`.

Usage:
  python3 resolve_frame.py --from <frame-export.json> [--registry registry.json]
Exit: 0 ok (even with gaps — gaps are expected, not errors) · 2 usage/IO error
"""
import argparse
import glob
import json
import os
import re
import sys


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _kebab(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def _known_components(registry_path, reg):
    ids = {c.get("id") for c in reg.get("components", []) if c.get("id")}
    root = os.path.dirname(os.path.abspath(registry_path))
    for sp in glob.glob(os.path.join(root, "design-system", "*", ".source.json")):
        try:
            for c in _load(sp).get("components", []):
                if c.get("id"):
                    ids.add(c["id"])
        except (OSError, json.JSONDecodeError):
            pass
    return ids


def _uniq(base, taken):
    cid, n = base or "el", 1
    while cid in taken:
        n += 1
        cid = f"{base}-{n}"
    taken.add(cid)
    return cid


def resolve(frame, registry_path):
    reg = _load(registry_path)
    known = _known_components(registry_path, reg)
    frame_meta = frame.get("frame", {})
    screen_id = _kebab(frame_meta.get("name") or frame_meta.get("id") or "screen") or "screen"
    screen_name = frame_meta.get("name") or screen_id

    elements, gaps, taken = [], [], set()
    mapped = 0
    for layer in frame.get("layers", []):
        label = layer.get("name", "layer")
        candidate = layer.get("component") or _kebab(label)
        eid = _uniq(_kebab(label), taken)
        if candidate in known:
            elements.append({"id": eid, "label": label, "orgId": candidate})
            mapped += 1
        else:
            # NEVER invent a component — placeholder + gap.
            elements.append({"id": eid, "label": label, "placeholder": True})
            gaps.append({"layer": label, "type": layer.get("type", "?"), "candidate": candidate, "element": eid})

    # screen patch (data skeleton — /pb:build fills the render body later)
    screen = {"id": screen_id, "name": screen_name, "elements": elements,
              "figmaFrameId": frame_meta.get("id"), "layout": {"type": "stack"}}
    screens = reg.setdefault("screens", [])
    screens[:] = [s for s in screens if s.get("id") != screen_id] + [screen]
    reg.setdefault("meta", {})["entry"] = "figma"

    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)

    if gaps:
        _write_gaps(registry_path, screen_name, frame_meta.get("id"), gaps)

    print(f"✓ resolved frame '{screen_name}' → screen '{screen_id}': "
          f"{mapped}/{len(elements)} layers mapped to DS components, {len(gaps)} gap(s).")
    if gaps:
        print(f"  {len(gaps)} unmapped layer(s) logged to gaps.md as placeholders (nothing invented).")
    print("  Next: /pb:build to flesh out the screen's render body from these elements.")
    return 0


_GAPS_HEADER = ("# Gaps — unmapped Figma layers\n\n"
                "Layers resolved from Figma frames that had **no matching design-system component**.\n"
                "They are labeled **placeholders** in the registry — pb never invents a component to fill\n"
                "a gap. Resolve each by cloning/adding the component (then re-resolve) or building it with\n"
                "`/pb:build`.\n")


def _write_gaps(registry_path, screen_name, frame_id, gaps):
    path = os.path.join(os.path.dirname(os.path.abspath(registry_path)), "gaps.md")
    existing = open(path, encoding="utf-8").read() if os.path.isfile(path) else _GAPS_HEADER
    block = [f"\n## {screen_name} (frame {frame_id})\n"]
    for g in gaps:
        block.append(f"- **{g['layer']}** ({g['type']}) — no DS component matched "
                     f"`{g['candidate']}`. Placeholder element `{g['element']}`.\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(existing + "".join(block))


def main(argv=None):
    p = argparse.ArgumentParser(prog="resolve_frame.py")
    p.add_argument("--from", dest="src", required=True, metavar="FRAME-EXPORT.json")
    p.add_argument("--registry", default="registry.json")
    args = p.parse_args(argv)
    if not os.path.isfile(args.registry):
        sys.exit(f"resolve_frame: no registry at {args.registry}")
    try:
        return resolve(_load(args.src), args.registry)
    except (OSError, json.JSONDecodeError) as e:
        print(f"resolve_frame: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
