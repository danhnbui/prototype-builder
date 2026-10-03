#!/usr/bin/env python3
"""
spec_measure.py — tools/spec_measure.py measures a component's anatomy + spec from its live render.

  1. Without Playwright it exits 2 with a one-line reason and writes nothing (never a crash).
  2. Parts come from data-part; a pbUse child is an `instance` part of its id, numbered when repeated.
  3. Padding / item spacing / radius / colours are read from the computed style, through the
     registry tokens applied to `.pb-product` and the project's runtime modules — and a value
     carries a `token` only when it equals one; a raw value stays raw.
  4. itemSpacing records what makes it: flex gap, margins, or `auto` for space-between.
  5. Optional is derived: a part that disappears when its prop is unset gets visibleWhen.
  6. shape "card" = fill + radius + padding on the root, the root is not a native control element
     (<button>, <a>, <input>, <select>, <textarea>), and ≥ 2 non-root parts. A clickable div
     (role=button) is still a card; a painted button around one label is not.
  7. Without --write it prints and writes nothing; --write merges into the sidecar (hand-authored
     keys kept), adds specSrc when absent, and a re-run is byte-identical.
  8. A body that throws is reported (exit 1) and does not stop the others; an unknown id exits 1.

  9. Margin is measured like padding (four sides, a token on an exact match, per-side tokens
     otherwise); a side that is `auto` is recorded as "auto", not as the pixels it resolved to.
 10. The measuring page carries product.css and every `styleSrc` sheet, and its stage is a `pb-screen`
     inline-size container: a component whose padding changes at `@container pb-screen (min-width:
     600px)` measures differently at --width 375 and 768, as it does in a device frame.
 11. A sidecar that is not valid JSON (or not an object) is reported against its component, left
     byte-for-byte as it is, and does not stop the others; only a MISSING one becomes `{}`.
 12. `--write` below schema 13 (or with no schemaVersion) is refused with exit 6 and a message naming
     /pb:update-version, and writes nothing; print mode still works.
 13. Exit codes are split: 2 is Playwright missing and nothing else; 3 Chromium cannot launch; 4 the
     registry / a sidecar / a body cannot be read; 5 the measuring page did not load; 6 the schema
     refusal; 7 the registry lock; 1 a component failed. build.md documents every one of them.
 14. The write phase takes the registry lock (refused with 7, naming the holder, nothing written),
     replaces sidecars atomically (no temp file left), and re-reads registry.json under the lock so a
     change made while the browser was measuring is kept.

Usage: python3 tests/spec_measure.py  ·  Exit 0 = pass · 1 = fail · 2 = skipped (no Playwright).
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "pb", "tools", "spec_measure.py")
fails = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


BODIES = {
    "tile": """var props = props || {};
return '<div data-part="root" style="background:var(--color-card);border-radius:var(--radius-md);padding:var(--space-4)">'
  + '<div data-part="label" style="color:var(--color-ink-soft)">' + pbEscape(props.label) + '</div>'
  + '<div data-part="amount" style="margin-top:var(--space-1);color:var(--color-ink)">' + fmtAmount(props.amount) + '</div>'
  + (props.sub ? '<div data-part="sub" style="margin-top:var(--space-1)">' + pbEscape(props.sub) + '</div>' : '')
  + '</div>';""",
    "stack": """var props = props || {};
return '<div data-part="root" style="display:flex;flex-direction:column;gap:var(--space-2);padding:12px 16px">'
  + '<span data-part="a">A</span>' + (props.showB ? '<span data-part="b">B</span>' : '') + '</div>';""",
    "item": """var props = props || {};
return '<button type="button" data-part="root" style="display:flex;gap:var(--space-1)"><span data-part="glyph">★</span>'
  + '<span data-part="label">' + pbEscape(props.label) + '</span></button>';""",
    "bar": """var props = props || {};
return '<nav data-part="root" style="display:flex">' + ['One', 'Two', 'Three'].map(function (l) {
  return pbUse('item', { label: l }); }).join('') + '</nav>';""",
    "row": """var props = props || {};
return '<div data-part="root" style="display:flex;justify-content:space-between;background:var(--color-card)">'
  + '<span data-part="label">Left</span><span data-part="hint">Right</span></div>';""",
    "raw": """return '<div data-part="root" style="padding:13px;border-radius:3px;background:#fafafa">x</div>';""",
    "broken": """throw new Error('kaboom');""",
    "cta": """return '<button type="button" data-part="root" style="background:var(--color-card);border-radius:var(--radius-md);padding:var(--space-3)"><span data-part="label">Go</span></button>';""",
    "rolecard": """return '<div data-part="root" role="button" tabindex="0" style="background:var(--color-card);border-radius:var(--radius-md);padding:var(--space-3)"><span data-part="title">Open</span><span data-part="meta">3 items</span></div>';""",
    "holder": """return '<div data-part="root" style="background:var(--color-card);border-radius:var(--radius-md);padding:var(--space-3)"><button type="button" data-part="minus">−</button><button type="button" data-part="plus">+</button></div>';""",
    "lonely": """return '<div data-part="root" style="background:var(--color-card);border-radius:var(--radius-md);padding:var(--space-3)"><span data-part="label">Only</span></div>';""",
    "migrated": """return '<div class="card"><h3 class="card__title">Title</h3><p class="card__body">Body</p></div>';""",
}


def make_project(tmp):
    comps = []
    for cid, body in BODIES.items():
        os.makedirs(os.path.join(tmp, "render", "components"), exist_ok=True)
        open(os.path.join(tmp, "render", "components", cid + ".js"), "w", encoding="utf-8").write(body)
        pascal = "".join(w.capitalize() for w in cid.split("-"))
        comps.append({"id": cid, "level": "molecule" if cid == "bar" else "atom", "scope": "local",
                      "renderSrc": "render/components/%s.js" % cid, "renderFn": "renderCmp" + pascal})
    stack = next(c for c in comps if c["id"] == "stack")
    stack["properties"] = [{"id": "showB", "type": "boolean", "default": True}]
    tile = next(c for c in comps if c["id"] == "tile")
    tile["specSrc"] = "spec/components/tile.json"
    os.makedirs(os.path.join(tmp, "spec", "components"))
    json.dump({"usage": {"example": {"label": "Total", "amount": 1200, "sub": "this month"}},
               "uiLogic": ["hand-authored — keep me"]},
              open(os.path.join(tmp, "spec", "components", "tile.json"), "w"), indent=2)
    mg = next(c for c in comps if c["id"] == "migrated")
    mg["specSrc"] = "spec/components/migrated.json"
    json.dump({"anatomy": {"root": {"type": "container"}, "title": {"type": "text"}},
               "elements": {"root": {"parent": None}, "title": {"parent": "root", "anchor": ".card__title"}},
               "legacy": {"anatomy": {"parts": [{"name": "Title", "anchor": ".card__title"}]}}},
              open(os.path.join(tmp, "spec", "components", "migrated.json"), "w"), indent=2)
    os.makedirs(os.path.join(tmp, "runtime"))
    open(os.path.join(tmp, "runtime", "fmt.js"), "w").write(
        "function fmtAmount(n) { return Number(n || 0).toLocaleString('en-US') + ' ₫'; }\n")
    reg = {"meta": {"name": "measure fixture", "schemaVersion": 13, "device": "mobile"},
           "tokens": {"color": {"$type": "color", "card": {"$value": "#FFFFFF"}, "ink": {"$value": "#1D2939"},
                                "ink-soft": {"$value": "#667085"}},
                      "space": {"$type": "dimension", "1": {"$value": "4px"}, "2": {"$value": "8px"},
                                "3": {"$value": "12px"}, "4": {"$value": "16px"}},
                      "radius": {"$type": "dimension", "md": {"$value": "12px"}}},
           "runtime": [{"id": "fmt", "src": "runtime/fmt.js", "why": "amount formatting"}],
           "components": comps, "screens": []}
    rp = os.path.join(tmp, "registry.json")
    json.dump(reg, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return rp


def run(args, env=None):
    return subprocess.run([sys.executable, TOOL] + args, capture_output=True, text=True, env=env)


def snapshot(tmp):
    out = {}
    for d, _dirs, files in os.walk(tmp):
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, tmp)] = open(p, "rb").read()
    return out


with tempfile.TemporaryDirectory() as tmp:
    rp = make_project(tmp)

    print("1 · without Playwright: exit 2, one line, nothing written")
    shim = os.path.join(tmp, "_noplaywright", "playwright")
    os.makedirs(shim)
    open(os.path.join(shim, "__init__.py"), "w").write("raise ImportError('blocked for the test')\n")
    # no bytecode: importing the shim would write its __pycache__ inside tmp, which the snapshot watches
    env = dict(os.environ, PYTHONPATH=os.path.dirname(shim), PYTHONDONTWRITEBYTECODE="1")
    before = snapshot(tmp)
    r = run(["--registry", rp, "--write"], env=env)
    check(r.returncode == 2, "exit 2 (got %d)" % r.returncode)
    check("Playwright is not installed" in r.stderr and "Traceback" not in r.stderr, "a clear message, not a traceback")
    check(snapshot(tmp) == before, "nothing written")

    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        print("\nSKIP — Playwright not installed; the measuring half needs it.")
        sys.exit(1 if fails else 2)

    print("2 · print mode measures and writes nothing")
    r = run(["--registry", rp])
    check(r.returncode == 1, "exit 1 because one body throws (got %d)" % r.returncode)
    check("broken: render threw: kaboom" in r.stderr, "the throwing body is named with its error")
    out = json.loads(r.stdout)
    check(sorted(out) == ["bar", "cta", "holder", "item", "lonely", "migrated", "raw", "rolecard", "row", "stack", "tile"],
          "every other component was measured")
    check(snapshot(tmp) == before, "nothing written without --write")

    tile, stack, bar, row, raw = (out[k] for k in ("tile", "stack", "bar", "row", "raw"))

    print("3 · parts, layout, instances")
    check(tile["layout"] == [{"root": ["label", "amount", "sub"]}], "tile layout in DOM order")
    check(tile["anatomy"]["label"] == {"type": "text"} and tile["anatomy"]["root"] == {"type": "container"},
          "text parts and a container root")
    check(out["item"]["anatomy"]["glyph"] == {"type": "glyph"}, "a lone symbol is a glyph")
    inst = {k: v for k, v in bar["anatomy"].items() if v["type"] == "instance"}
    check(sorted(inst) == ["item-1", "item-2", "item-3"] and all(v["instanceOf"] == "item" for v in inst.values()),
          "three pbUse children → item-1…3, instanceOf item (the child's own data-part is not used)")
    check(bar["layout"] == [{"root": ["item-1", "item-2", "item-3"]}], "instances are leaves of the layout")
    check("styles" not in bar["elements"]["item-1"], "an instance's own spec is not copied into the parent's")
    mg = out["migrated"]
    check(mg["layout"] == [{"root": ["title"]}] and mg["elements"]["title"].get("anchor") == ".card__title",
          "a migrated sidecar's anchor finds its part in a body with no data-part, and is kept")

    print("4 · measured values, tokens only on an exact match")
    ts = tile["elements"]["root"]["styles"]
    check(ts["padding"] == {"top": 16, "right": 16, "bottom": 16, "left": 16, "token": "space-4"},
          "uniform padding 16 → space-4 (registry tokens reached .pb-product)")
    check(ts["cornerRadius"] == {"value": 12, "token": "radius-md"}, "radius 12 → radius-md")
    check(ts["backgroundColor"] == {"value": "#ffffff", "token": "color-card"}, "background → color-card")
    check(ts["itemSpacing"] == {"direction": "vertical", "value": 4, "token": "space-1", "via": "margin"},
          "margins create 4px vertical spacing → space-1, via margin")
    check(tile["elements"]["label"]["styles"]["textColor"] == {"value": "#667085", "token": "color-ink-soft"},
          "text colour → its token")
    check(tile["elements"]["sub"]["styles"]["textColor"] == {"value": "inherit"}, "a colour the body never sets is `inherit`")
    check(tile["measured"]["props"]["amount"] == 1200, "usage.example props were used")
    ss = stack["elements"]["root"]["styles"]
    check(ss["padding"] == {"top": 12, "right": 16, "bottom": 12, "left": 16,
                            "tokens": {"top": "space-3", "right": "space-4", "bottom": "space-3", "left": "space-4"}},
          "12×16 padding: raw sides + per-side tokens")
    check(ss["itemSpacing"] == {"direction": "vertical", "value": 8, "token": "space-2", "via": "gap"}, "flex gap 8 → via gap")
    check(row["elements"]["root"]["styles"]["itemSpacing"] == {"direction": "horizontal", "value": "auto", "via": "space-between"},
          "space-between → auto")
    rs = raw["elements"]["root"]["styles"]
    check(rs["padding"] == {"top": 13, "right": 13, "bottom": 13, "left": 13} and rs["cornerRadius"] == {"value": 3},
          "a value no token holds stays raw, with no token key")

    print("5 · optional is derived")
    check(tile["elements"]["sub"].get("visibleWhen") == {"prop": "sub", "is": "set"}, "sub disappears when unset → visibleWhen set")
    check(stack["elements"]["b"].get("visibleWhen") == {"prop": "showB", "is": "true"}, "a boolean prop → is: true")
    check(not any("visibleWhen" in e for k, e in tile["elements"].items() if k != "sub"), "nothing else is optional")

    print("6 · shape")
    check(tile.get("shape") == "card", "fill + radius + padding + 3 parts → card")
    check("shape" not in raw, "painted, but no parts inside the root → not a card")
    check("shape" not in stack and "shape" not in row and "shape" not in bar,
          "no fill, no radius or no padding → no shape")
    check("padding" in out["cta"]["elements"]["root"]["styles"] and "shape" not in out["cta"],
          "a painted <button> around one label part is not a card")
    check(out["rolecard"].get("shape") == "card", "a painted div role=button with 2 parts IS a card (clickable card)")
    check(out["holder"].get("shape") == "card", "a painted container that holds two buttons is a card")
    check("shape" not in out["lonely"], "a painted div with only 1 non-root part is not a card")

    print("7 · --write merges, adds specSrc, and is deterministic")
    r = run(["--registry", rp, "--write"])
    check(r.returncode == 1, "exit 1 still (the broken body)")
    side = json.load(open(os.path.join(tmp, "spec", "components", "tile.json"), encoding="utf-8"))
    check(side["uiLogic"] == ["hand-authored — keep me"] and side["usage"]["example"]["sub"] == "this month",
          "hand-authored keys kept")
    check(side["elements"] == tile["elements"] and side["measured"]["by"] == "spec_measure.py", "measured keys written")
    reg = json.load(open(rp, encoding="utf-8"))
    by = {c["id"]: c for c in reg["components"]}
    check(by["stack"].get("specSrc") == "spec/components/stack.json"
          and os.path.isfile(os.path.join(tmp, "spec", "components", "stack.json")), "specSrc added for a new sidecar")
    check("specSrc" not in by["broken"] and not os.path.exists(os.path.join(tmp, "spec", "components", "broken.json")),
          "nothing written for the body that threw")
    first = snapshot(tmp)
    r = run(["--registry", rp, "--write"])
    check(snapshot(tmp) == first, "a re-run leaves every file byte-identical (measured.at included)")
    check(r.stdout.count("unchanged") == 11, "and says so per component")
    text = open(os.path.join(tmp, "spec", "components", "stack.json"), encoding="utf-8").read()
    check(text == json.dumps(json.loads(text), indent=2, ensure_ascii=False, sort_keys=True) + "\n", "sorted keys, stable form")

    print("8 · --component narrows; an unknown id fails")
    r = run(["--registry", rp, "--component", "row"])
    check(r.returncode == 0 and sorted(json.loads(r.stdout)) == ["row"], "--component row measures only row")
    r = run(["--registry", rp, "--component", "nope"])
    check(r.returncode == 1 and "nope: no such component" in r.stderr, "an unknown id exits 1 and is named")


# ── round 3 ──────────────────────────────────────────────────────────────────────────────
TOKENS = {"color": {"$type": "color", "card": {"$value": "#FFFFFF"}, "ink": {"$value": "#1D2939"}},
          "space": {"$type": "dimension", "1": {"$value": "4px"}, "2": {"$value": "8px"},
                    "3": {"$value": "12px"}, "4": {"$value": "16px"}},
          "radius": {"$type": "dimension", "md": {"$value": "12px"}}}


def mini(tmp, comps, schema=13, device="mobile", files=None, runtime=None, screens=None):
    """A small project: comps = {id: body | (body, {extra registry fields})}; files = {relpath: text}."""
    entries = []
    for cid, spec in comps.items():
        body, extra = spec if isinstance(spec, tuple) else (spec, {})
        os.makedirs(os.path.join(tmp, "render", "components"), exist_ok=True)
        open(os.path.join(tmp, "render", "components", cid + ".js"), "w", encoding="utf-8").write(body)
        e = {"id": cid, "level": "atom", "scope": "local", "renderSrc": "render/components/%s.js" % cid,
             "renderFn": "renderCmp" + "".join(w.capitalize() for w in cid.split("-"))}
        e.update(extra)
        entries.append(e)
    for rel, text in (files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
        open(os.path.join(tmp, rel), "w", encoding="utf-8").write(text)
    meta = {"name": "mini", "device": device}
    if schema is not None:
        meta["schemaVersion"] = schema
    reg = {"meta": meta, "tokens": TOKENS, "components": entries, "screens": screens or []}
    if runtime:
        reg["runtime"] = runtime
    rp = os.path.join(tmp, "registry.json")
    json.dump(reg, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    return rp


def sub(tmp, name):
    d = os.path.join(tmp, name)
    os.makedirs(d)
    return d


def sidecars(tmp):
    return {f: open(os.path.join(tmp, "spec", "components", f), "rb").read()
            for f in sorted(os.listdir(os.path.join(tmp, "spec", "components")))} \
        if os.path.isdir(os.path.join(tmp, "spec", "components")) else {}


GOOD = "return '<div data-part=\"root\" style=\"padding:8px\"><span data-part=\"t\">x</span></div>';"

print("9 · margin")
MARGINED = ("return '<div data-part=\"root\" style=\"margin:0 auto;max-width:300px;margin-top:var(--space-2)\">'"
            " + '<span data-part=\"a\" style=\"margin:var(--space-4)\">A</span>'"
            " + '<span data-part=\"b\" style=\"margin:-3px 5px 0 var(--space-1)\">B</span>'"
            " + '<span data-part=\"c\" style=\"display:block;margin-left:auto\">C</span>'"
            " + '<span data-part=\"d\">D</span></div>';")
with tempfile.TemporaryDirectory() as tmp:
    rp = mini(tmp, {"spaced": MARGINED})
    r = run(["--registry", rp])
    out = json.loads(r.stdout)["spaced"]["elements"]
    check(r.returncode == 0, "measured (exit %d)" % r.returncode)
    st = lambda part: out[part].get("styles", {})
    check(st("a")["margin"] == {"top": 16, "right": 16, "bottom": 16, "left": 16, "token": "space-4"},
          "a uniform 16px margin → space-4, like padding (%s)" % st("a").get("margin"))
    check(st("b")["margin"] == {"top": -3, "right": 5, "bottom": 0, "left": 4, "tokens": {"left": "space-1"}},
          "mixed sides: raw numbers (negative too) and a per-side token only where one matches (%s)" % st("b").get("margin"))
    check(st("root")["margin"] == {"top": 8, "right": "auto", "bottom": 0, "left": "auto", "tokens": {"top": "space-2"}},
          "`margin: 0 auto` on the root is recorded as auto, not as the pixels the stage gave it (%s)" % st("root").get("margin"))
    check(st("c")["margin"]["left"] == "auto" and st("c")["margin"]["right"] == 0, "an auto margin-left on a child is `auto` too")
    check("margin" not in st("d"), "a part with no margin records none")

print("10 · a styleSrc sheet is measured, at the width of the stage")
SHEET = """.c-wide { padding: var(--space-1); }
@container pb-screen (min-width: 600px) { .c-wide { padding: var(--space-3); } }
"""
WIDE = ("return '<div data-part=\"root\" class=\"c-wide\"><span data-part=\"t\">x</span></div>';", {"styleSrc": "render/styles/wide.css"})
with tempfile.TemporaryDirectory() as tmp:
    rp = mini(tmp, {"wide": WIDE}, files={"render/styles/wide.css": SHEET})
    pads = {}
    for w in (375, 768):
        r = run(["--registry", rp, "--width", str(w)])
        pads[w] = json.loads(r.stdout)["wide"]["elements"]["root"]["styles"]["padding"] if r.returncode == 0 else r.stderr
    check(pads[375] == {"top": 4, "right": 4, "bottom": 4, "left": 4, "token": "space-1"},
          "at 375 the compact rule applies (padding 4 → space-1): %s" % pads[375])
    check(pads[768] == {"top": 12, "right": 12, "bottom": 12, "left": 12, "token": "space-3"},
          "at 768 the @container pb-screen (min-width: 600px) rule applies (padding 12 → space-3): %s" % pads[768])
    r = run(["--registry", rp])      # device mobile → 375
    check(json.loads(r.stdout)["wide"]["elements"]["root"]["styles"]["padding"]["top"] == 4, "the default width follows meta.device (mobile → 375)")
    # product.css is on the page too: its r-cols utility is one column in a compact stage, three in an expanded one
    UTIL = ("return '<div data-part=\"root\"><div class=\"r-cols\" data-part=\"grid\">"
            "<span>1</span><span>2</span><span>3</span></div></div>';")
    rp2 = mini(sub(tmp, "u"), {"util": UTIL})
    dirs = {}
    for w in (375, 1100):
        r = run(["--registry", rp2, "--width", str(w)])
        dirs[w] = (json.loads(r.stdout)["util"]["elements"]["grid"]["styles"].get("itemSpacing") or {}).get("direction") if r.returncode == 0 else r.stderr
    check(dirs == {375: "vertical", 1100: "horizontal"},
          "product.css's r-cols stacks at 375 and runs across at 1100 (%s)" % dirs)

print("11 · a sidecar that does not parse is reported, never written over")
BROKEN = '{"usage": {"example": {"x": 1}}, "uiLogic": ["hand-authored'      # truncated mid-edit
with tempfile.TemporaryDirectory() as tmp:
    rp = mini(tmp, {"good": GOOD, "bad": (GOOD, {"specSrc": "spec/components/bad.json"}), "list": (GOOD, {"specSrc": "spec/components/list.json"}),
                    "dflt": GOOD},
              files={"spec/components/bad.json": BROKEN, "spec/components/list.json": "[1, 2]",
                     "spec/components/dflt.json": "not json at all",
                     "spec/screens/home.json": "{oops"},
              screens=[{"id": "home", "name": "Home", "specSrc": "spec/screens/home.json", "renderFn": "renderScrHome"}])
    before = snapshot(tmp)
    r = run(["--registry", rp])
    out = json.loads(r.stdout) if r.returncode in (0, 1) and r.stdout.strip() else {}
    check(r.returncode == 1 and "Traceback" not in r.stderr, "print mode: exit 1, no traceback (got %d)" % r.returncode)
    check(sorted(out) == ["good"], "…the others are still measured; the three unusable ones are not (%s)" % sorted(out))
    check("bad: spec/components/bad.json is not valid JSON" in r.stderr,
          "…the broken one is named with its file: %s" % [l for l in r.stderr.splitlines() if l.startswith("spec_measure: bad:")])
    check("list: spec/components/list.json must hold a JSON object" in r.stderr, "…so is one that parses but is not an object")
    check("dflt: spec/components/dflt.json is not valid JSON" in r.stderr, "…and one at the default path that specSrc does not name yet")
    check("warning: screen home" in r.stderr, "…a broken SCREEN sidecar is only a warning (screens are not measured)")
    r = run(["--registry", rp, "--write"])
    after = snapshot(tmp)
    check(r.returncode == 1, "--write: exit 1 (got %d)" % r.returncode)
    for rel in ("spec/components/bad.json", "spec/components/list.json", "spec/components/dflt.json", "spec/screens/home.json"):
        check(after[rel] == before[rel], "%s is byte-identical after --write" % rel)
    check("spec/components/good.json" in after and json.loads(after["spec/components/good.json"])["anatomy"]["root"],
          "the good component's sidecar was written")
    reg = json.load(open(rp, encoding="utf-8"))
    byid = {c["id"]: c for c in reg["components"]}
    check(byid["good"].get("specSrc") == "spec/components/good.json" and "specSrc" not in byid["dflt"],
          "specSrc added for the good one only (the default-path broken one gets none)")
    r = run(["--registry", rp, "--component", "bad", "--write"])
    check(r.returncode == 1 and snapshot(tmp)["spec/components/bad.json"] == before["spec/components/bad.json"],
          "asking for the broken one by name fails the same way")
    # only a MISSING sidecar becomes {}: a component whose specSrc names a file that is not there
    # fails closed (render.py's rule), it is not silently created
    rp3 = mini(sub(tmp, "m"), {"gone": (GOOD, {"specSrc": "spec/components/gone.json"})})
    r = run(["--registry", rp3, "--write"])
    check(r.returncode == 4 and "specSrc not found" in r.stderr, "a specSrc naming a file that does not exist exits 4, not a crash (got %d)" % r.returncode)

print("12 · --write below schema 13 is refused")
for label, schema in (("schema 12", 12), ("schema 9", 9), ("no schemaVersion", None)):
    with tempfile.TemporaryDirectory() as tmp:
        rp = mini(tmp, {"good": GOOD}, schema=schema)
        before = snapshot(tmp)
        r = run(["--registry", rp, "--write"])
        check(r.returncode == 6 and "/pb:update-version" in r.stderr and "Traceback" not in r.stderr,
              "%s: exit 6 naming /pb:update-version (got %d: %s)" % (label, r.returncode, r.stderr.strip()[:90]))
        check(snapshot(tmp) == before, "%s: nothing written" % label)
        r = run(["--registry", rp])
        check(r.returncode == 0 and "good" in json.loads(r.stdout), "%s: print mode still measures" % label)

print("13 · exit codes")
with tempfile.TemporaryDirectory() as tmp:
    r = run(["--registry", os.path.join(tmp, "nope.json")])
    check(r.returncode == 4 and "cannot read" in r.stderr and "Traceback" not in r.stderr, "no registry → 4 (got %d)" % r.returncode)
    open(os.path.join(tmp, "bad.json"), "w").write("{nope")
    r = run(["--registry", os.path.join(tmp, "bad.json")])
    check(r.returncode == 4, "a registry that is not JSON → 4 (got %d)" % r.returncode)
    open(os.path.join(tmp, "arr.json"), "w").write("[]")
    r = run(["--registry", os.path.join(tmp, "arr.json")])
    check(r.returncode == 4, "a registry that is not an object → 4 (got %d)" % r.returncode)
    rp = mini(sub(tmp, "p1"), {"good": GOOD})
    os.remove(os.path.join(tmp, "p1", "render", "components", "good.js"))
    r = run(["--registry", rp])
    check(r.returncode == 4 and "renderSrc not found" in r.stderr, "a missing render body → 4 (got %d)" % r.returncode)
    # 4 is decided before Playwright is asked for, so 2 stays "Playwright missing, and only that"
    shim = os.path.join(tmp, "_np", "playwright")
    os.makedirs(shim)
    open(os.path.join(shim, "__init__.py"), "w").write("raise ImportError('blocked for the test')\n")
    noplay = dict(os.environ, PYTHONPATH=os.path.dirname(shim))
    r = run(["--registry", rp], env=noplay)
    check(r.returncode == 4, "…even with Playwright absent, an unreadable project is 4, not 2 (got %d)" % r.returncode)
    rp = mini(sub(tmp, "p2"), {"good": GOOD})
    r = run(["--registry", rp], env=noplay)
    check(r.returncode == 2 and "Playwright is not installed" in r.stderr, "Playwright absent → 2 (got %d)" % r.returncode)
    empty = os.path.join(tmp, "nobrowsers")
    os.makedirs(empty)
    r = run(["--registry", rp], env=dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=empty))
    check(r.returncode == 3 and "could not launch Chromium" in r.stderr and "playwright install chromium" in r.stderr,
          "Chromium not installed → 3 (got %d)" % r.returncode)
    rp = mini(sub(tmp, "p3"), {"good": GOOD},
              files={"runtime/bad.js": "function ( {\n"}, runtime=[{"id": "bad", "src": "runtime/bad.js", "why": "t"}])
    r = run(["--registry", rp])
    check(r.returncode == 5 and "measuring page did not load" in r.stderr, "a runtime module the page cannot parse → 5 (got %d)" % r.returncode)
    rp = mini(sub(tmp, "p4"), {"broken": "throw new Error('x');"})
    r = run(["--registry", rp])
    check(r.returncode == 1, "a body that throws → 1 (got %d)" % r.returncode)
    spec = importlib.util.spec_from_file_location("spec_measure_codes", TOOL)
    sm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm)
    codes = {"EXIT_FAIL": 1, "EXIT_NO_PLAYWRIGHT": 2, "EXIT_NO_CHROMIUM": 3, "EXIT_UNREADABLE": 4, "EXIT_PAGE": 5,
             "EXIT_REFUSED_SCHEMA": 6, "EXIT_LOCKED": 7}
    check(all(getattr(sm, k) == v for k, v in codes.items()) and len(set(codes.values())) == 7, "the seven failure codes are distinct constants in the tool")
    doc = open(os.path.join(ROOT, "pb", "commands", "build.md"), encoding="utf-8").read()
    section = doc[doc.index("**Measure the spec"):]
    section = section[:section.index("**Report the decision**")]
    rows = {int(m.group(1)): m.group(2) for m in re.finditer(r"(?m)^\|\s*(\d)\s*\|(.*)$", section)}
    check(sorted(rows) == list(range(0, 8)), "build.md has one table row per exit code 0-7 (found %s)" % sorted(rows))
    check("Playwright" in rows.get(2, "") and "nothing else" in rows.get(2, "") and "Playwright" not in "".join(rows.get(n, "") for n in (3, 4, 5, 6, 7)),
          "…and says exit 2 is Playwright missing only — no other row blames it")
    check("update-version" in rows.get(6, "") and "Chromium" in rows.get(3, "") and "lock" in rows.get(7, ""),
          "…with 6 naming /pb:update-version, 3 Chromium, 7 the lock")

print("14 · the write phase: lock, atomic, re-read under the lock")
spec = importlib.util.spec_from_file_location("pbslice_t", os.path.join(ROOT, "pb", "tools", "slice.py"))
pbsl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pbsl)
with tempfile.TemporaryDirectory() as tmp:
    rp = mini(tmp, {"good": GOOD})
    before = snapshot(tmp)
    with pbsl.registry_lock(rp, "a test holding the lock"):
        r = run(["--registry", rp, "--write"], env=dict(os.environ, PB_LOCK_TIMEOUT="0.5"))
        check(r.returncode == 7 and "being written" in r.stderr and "a test holding the lock" in r.stderr and "Traceback" not in r.stderr,
              "--write while the lock is held → 7, naming the holder (got %d: %s)" % (r.returncode, r.stderr.strip()[:110]))
        r2 = run(["--registry", rp])
        check(r2.returncode == 0, "print mode needs no lock")
    check({k: v for k, v in snapshot(tmp).items() if not k.endswith(".lock")} == {k: v for k, v in before.items() if not k.endswith(".lock")},
          "…and nothing was written")
    r = run(["--registry", rp, "--write"])
    check(r.returncode == 0, "once released the same --write goes through")
    left = [f for d, _s, fs in os.walk(tmp) for f in fs if f.endswith(".tmp")]
    check(left == [], "no temp file is left behind")
    # a change to registry.json made while the browser was measuring is kept, not overwritten
    reg = json.load(open(rp, encoding="utf-8"))
    reg["components"][0].pop("specSrc", None)
    reg["meta"]["editedWhileMeasuring"] = "kept"
    json.dump(reg, open(rp, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    fields = {"anatomy": {"root": {"type": "container"}}, "layout": [{"root": []}], "elements": {"root": {"parent": None}},
              "measured": {"by": "spec_measure.py", "props": {}}}
    ns = type("A", (), {"registry": rp})()
    errs = {}
    with contextlib.redirect_stdout(io.StringIO()):
        rc = sm._write_results(ns, tmp, {"good": fields}, errs, "2026-01-01T00:00:00Z")
    now = json.load(open(rp, encoding="utf-8"))
    check(rc == 0 and now["meta"].get("editedWhileMeasuring") == "kept" and now["components"][0].get("specSrc") == "spec/components/good.json",
          "a registry edit made after the measuring started survives the specSrc write")
    check(sm._write_results(ns, tmp, {"vanished": fields}, errs, "x") == 0 and "vanished" in errs,
          "a component removed from the registry while measuring is reported, not crashed on")

print()
if fails:
    print("FAIL — %d check(s)" % len(fails))
    sys.exit(1)
print("PASS")
