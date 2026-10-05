#!/usr/bin/env python3
"""
spec_measure.py — measure a component's anatomy and spec from its live render (schema 13).

    python3 spec_measure.py --registry <registry.json> [--component <id> ...] [--write] [--width N]

Renders each component headlessly, the way render.py composes a page (the same render bodies,
project runtime modules, shared runtime.js and `.pb-product`-scoped tokens; this file builds no
render function of its own), with the component's demo props (`properties[].default`, then the
sidecar's `usage.example`). It then reads, per part:

  - the parts: `data-part="<name>"` in the body (the root is `data-part="root"` or the body's first
    element); a child composed through `pbUse('<id>')` is an `instance` part of that id; a migrated
    sidecar's `elements.<part>.anchor` selector still finds a part in a body that has no markers.
  - computed padding and margin (a side set to `auto` is recorded as "auto", not as the pixels it
    resolved to), item spacing (flex/grid `gap` or the margins that create it, and which), corner
    radius, background colour, and text colour on text/glyph parts. A value is mapped to a registry
    token (pb/tools/tokens.py) only when it equals that token's resolved value.
  - optional parts: each prop is re-rendered unset (a boolean `true` → `false`), and a part that
    disappears gets `visibleWhen: {prop, is}`. Optional is derived, never typed.

and writes `anatomy`, `layout`, `elements`, `shape` and `measured` into the component's spec
sidecar (`spec/components/<id>.json`, created with `specSrc` when absent), leaving every other key
alone. Without `--write` it prints the JSON. Output is deterministic (sorted keys, rounded numbers);
a re-run that measures the same thing leaves the file untouched, `measured.at` included.

The stage is a `pb-screen` inline-size container (product.css's name) and the page carries
product.css plus every component/screen `styleSrc` sheet, exactly as the shells do — so a component
whose layout lives in its sheet's `@container pb-screen (…)` rules is measured WITH its sheet, at the
stage width (`--width`, default by meta.device: mobile 375 · tablet 768 · anything else 960).

`--write` needs schema 13 (the shape it writes) and takes the registry lock (tools/slice.py) for the
write phase: sidecars are replaced atomically, a sidecar that is not valid JSON is reported and left
exactly as it is (only a MISSING one is created), and registry.json is re-read under the lock before
`specSrc` is added so a change made while the browser was measuring is not overwritten.

`/pb:build` §3a runs it for a component that was built or changed. Never per page load.

Exit:
  0  measured (and written, with --write)
  1  at least one component could not be measured or written — its body threw or returned nothing,
     the id does not exist, or its sidecar is not valid JSON (stderr names which); the rest are done
  2  Playwright is not installed (and nothing else)
  3  Chromium could not be launched (`playwright install chromium`)
  4  the registry, a spec sidecar it names, or a render body could not be read
  5  the measuring page did not load (a project runtime module threw at load)
  6  `--write` refused: registry.json is below schema 13 — run /pb:update-version first
  7  `--write` refused: another pb process holds the registry lock past the timeout
"""
import argparse
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib  # noqa: E402
import render as R  # noqa: E402
import tokens as T  # noqa: E402
# Every headless browser pb opens goes through here — the machine-wide limit (see browser.py).
import browser as pbbrowser  # noqa: E402
# slice.py is the registry's write path: the advisory lock and the atomic write. Imported by name
# because `import slice` would shadow the builtin of the same name here (serve.py does the same).
pbslice = importlib.import_module("slice")

(EXIT_FAIL, EXIT_NO_PLAYWRIGHT, EXIT_NO_CHROMIUM, EXIT_UNREADABLE,
 EXIT_PAGE, EXIT_REFUSED_SCHEMA, EXIT_LOCKED) = 1, 2, 3, 4, 5, 6, 7
MIN_SCHEMA = 13      # the sidecar shape this tool writes (migration 0011)
PART_TYPES = ("text", "glyph", "vector", "container", "slot", "instance")
OWNED = ("anatomy", "layout", "elements", "shape", "measured")
_WIDTH_BY_DEVICE = {"mobile": 375, "tablet": 768}

# ── the measuring page ───────────────────────────────────────────────────────────────────

_MEASURE_JS = r"""
(function () {
  var TYPES = %(types)s;
  // Mark every pbUse'd child with the id it was composed from, so it becomes an `instance` part.
  // Only on this measuring page: the shells' pbUse is untouched.
  var __pbUse = pbUse;
  pbUse = function (id, props) {
    var html = __pbUse(id, props);
    return String(html).replace(/^(\s*<[a-zA-Z][\w-]*)/, '$1 data-cmp="' + pbEscape(id) + '"');
  };
  function num(v) { var n = parseFloat(v); return isFinite(n) ? Math.round(n * 100) / 100 : 0; }
  function visible(el) {
    var cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (cs.position === 'absolute' || cs.position === 'fixed') return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  }
  function spacing(el) {
    var kids = Array.prototype.filter.call(el.children, visible);
    if (kids.length < 2) return null;
    var cs = getComputedStyle(el), gaps = [], axis = null, margin = false;
    for (var i = 1; i < kids.length; i++) {
      var a = kids[i - 1].getBoundingClientRect(), b = kids[i].getBoundingClientRect();
      var ma = getComputedStyle(kids[i - 1]), mb = getComputedStyle(kids[i]);
      var g, ax, m;
      if (b.top >= a.bottom - 0.5) { g = b.top - a.bottom; ax = 'vertical'; m = num(ma.marginBottom) + num(mb.marginTop); }
      else if (b.left >= a.right - 0.5) { g = b.left - a.right; ax = 'horizontal'; m = num(ma.marginRight) + num(mb.marginLeft); }
      else continue;
      if (axis && ax !== axis) return { mixed: true };
      if (m > 0) margin = true;
      axis = ax; gaps.push(Math.round(g * 100) / 100);
    }
    if (!gaps.length) return null;
    var flex = cs.display.indexOf('flex') >= 0, grid = cs.display.indexOf('grid') >= 0;
    var gapProp = (flex || grid) ? num(axis === 'vertical' ? cs.rowGap : cs.columnGap) : 0;
    var jc = cs.justifyContent || '';
    var mainAxis = flex ? ((cs.flexDirection || 'row').indexOf('column') === 0 ? 'vertical' : 'horizontal') : null;
    return { axis: axis, gaps: gaps, gapProp: gapProp, margin: margin,
             spread: !!(mainAxis === axis && /space-(between|around|evenly)/.test(jc)) ? jc : null };
  }
  function styles(el, type) {
    var cs = getComputedStyle(el), s = {};
    var pad = [num(cs.paddingTop), num(cs.paddingRight), num(cs.paddingBottom), num(cs.paddingLeft)];
    if (pad.some(function (p) { return p > 0; })) s.padding = pad;
    // Margin, like padding. getComputedStyle reports an `auto` margin as the pixels it resolved to
    // (a centred 600px card in a 960px stage "has" 180px margins); computedStyleMap keeps the
    // keyword, so an auto side is recorded as 'auto' and not as a number that depends on the stage.
    var mar = [num(cs.marginTop), num(cs.marginRight), num(cs.marginBottom), num(cs.marginLeft)];
    var autos = [false, false, false, false];
    try {
      var cm = el.computedStyleMap();
      autos = ['margin-top', 'margin-right', 'margin-bottom', 'margin-left'].map(function (k) { return String(cm.get(k)) === 'auto'; });
    } catch (e) {}
    if (mar.some(function (m, i) { return m !== 0 || autos[i]; })) s.margin = mar.map(function (m, i) { return autos[i] ? 'auto' : m; });
    var sp = spacing(el);
    if (sp) s.spacing = sp;
    var box = el.getBoundingClientRect();
    // A computed radius may stay a percentage (50%% of a 40px circle); in px it is 20.
    function px(v) { return /%%\s*$/.test(v) ? Math.round(parseFloat(v) * Math.min(box.width, box.height)) / 100 : num(v); }
    var rad = [px(cs.borderTopLeftRadius), px(cs.borderTopRightRadius),
               px(cs.borderBottomRightRadius), px(cs.borderBottomLeftRadius)];
    if (rad.some(function (r) { return r > 0; })) s.radius = rad;
    if (cs.backgroundColor && !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(cs.backgroundColor)) s.background = cs.backgroundColor;
    if (type === 'text' || type === 'glyph') s.color = cs.color;
    return s;
  }
  function typeOf(el, isRoot, isInstance) {
    var t = el.getAttribute('data-part-type');
    if (t && TYPES.indexOf(t) >= 0) return t;
    if (isInstance && !isRoot) return 'instance';
    // A root is the component's frame — unless it is nothing but text (a heading atom).
    if (isRoot) return (!el.children.length && (el.textContent || '').trim()) ? 'text' : 'container';
    var tag = el.tagName.toLowerCase();
    if (tag === 'svg' || tag === 'img' || tag === 'canvas') return 'vector';
    if (tag === 'slot' || el.hasAttribute('data-slot')) return 'slot';
    if (el.querySelector('[data-part],[data-cmp]')) return 'container';
    var text = (el.textContent || '').trim();
    if (text) return (text.length <= 2 && !/[\p{L}\p{N}]/u.test(text)) ? 'glyph' : 'text';
    if (el.querySelector('svg,img')) return 'vector';
    return 'container';
  }
  window.pbMeasure = function (fnName, props, anchors) {
    var stage = document.getElementById('pb-measure-stage');
    stage.innerHTML = '';
    var html;
    try { html = window[fnName](props); }
    catch (e) { return { error: 'render threw: ' + (e && e.message || e) }; }
    if (typeof html !== 'string' || !html.trim())
      return { error: 'render returned ' + (typeof html === 'string' ? 'an empty string' : typeof html) };
    stage.innerHTML = html;
    var root = stage.querySelector('[data-part="root"]') || stage.firstElementChild;
    if (!root) return { error: 'render produced no element' };
    Object.keys(anchors || {}).sort().forEach(function (name) {
      if (root.querySelector('[data-part="' + name + '"]')) return;
      var el = null;
      try { el = root.matches(anchors[name]) ? root : root.querySelector(anchors[name]); } catch (e) {}
      if (el && el !== root && !el.hasAttribute('data-part')) el.setAttribute('data-part', name);
    });
    var parts = [];
    (function walk(el, parent) {
      var isRoot = el === root, cmp = el.getAttribute('data-cmp');
      var named = el.getAttribute('data-part');
      var me = parent;
      if (isRoot || named || cmp) {
        var type = typeOf(el, isRoot, !!cmp);
        // An instance is named by the component it composes: a data-part on its root is the CHILD's own.
        var p = { base: isRoot ? 'root' : (type === 'instance' ? cmp : named), parent: parent, type: type, styles: styles(el, type) };
        if (type === 'instance') p.instanceOf = cmp;
        parts.push(p);
        me = parts.length - 1;
        if (type === 'instance') return;            // an instance's insides belong to its own spec
      }
      Array.prototype.forEach.call(el.children, function (c) { walk(c, me); });
    })(root, null);
    // Names: a name used once stays; a repeated one becomes name-1 … name-n, in document order.
    var count = {}, seen = {};
    parts.forEach(function (p) { count[p.base] = (count[p.base] || 0) + 1; });
    parts.forEach(function (p) {
      if (p.base === 'root' && p.parent === null) { p.name = 'root'; return; }
      if (count[p.base] > 1 || p.base === 'root') { seen[p.base] = (seen[p.base] || 0) + 1; p.name = p.base + '-' + seen[p.base]; }
      else p.name = p.base;
    });
    // A root that IS a native control element is never a card, however it is painted. (A clickable
    // div — role=button — is a clickable card, and can still be one.)
    var control = ['button', 'a', 'input', 'select', 'textarea'].indexOf(root.tagName.toLowerCase()) >= 0;
    return { control: control, parts: parts.map(function (p) {
      var o = { name: p.name, parent: p.parent === null ? null : parts[p.parent].name, type: p.type, styles: p.styles };
      if (p.instanceOf) o.instanceOf = p.instanceOf;
      return o;
    }) };
  };
})();
"""

_ESCAPE_FN = ("function pbEscape(s){ return String(s == null ? '' : s).replace(/[&<>\"']/g, function(c){"
              " return {'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]; }); }")


def build_page(reg, base_dir, width):
    """The measuring page: render.py's own pieces (bodies, project runtime, shared runtime, the
    inlined registry, product.css + every `styleSrc` sheet), a `.pb-product` stage the registry
    tokens are scoped to — and which is a `pb-screen` inline-size container, so a sheet's
    `@container pb-screen (…)` rules answer the stage width the way they answer a frame — and
    pbMeasure."""
    bodies, _missing = R._render_fn_bodies(reg)
    rt_js, rt_deps, _rt_missing = R.load_runtime(reg, base_dir)
    inlined = json.dumps(R._strip_render(reg), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    runtime = R.shared_runtime(R.load_shared_runtime())
    product_css = R._product_css_js(reg)
    measure = _MEASURE_JS % {"types": json.dumps(list(PART_TYPES))}
    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\">\n%s\n"
            "<style>html,body{margin:0;background:#fff;font:14px/1.4 system-ui,-apple-system,sans-serif}"
            "#pb-measure-stage{width:%dpx;padding:24px;color:rgb(1, 2, 3);container:pb-screen/inline-size}</style>\n"
            "<script>\nvar PB_REGISTRY = %s;\n%s\n%s\n%s%s%s\n</script></head>\n"
            "<body><div class=\"pb-product\" id=\"pb-measure-stage\"></div>\n"
            "<script>applyRegistryTokens(PB_REGISTRY);\n%s</script></body></html>"
            % ("\n".join(rt_deps), width, inlined, _ESCAPE_FN, runtime, product_css, rt_js, bodies, measure))


# ── values → tokens ──────────────────────────────────────────────────────────────────────

_NAMED = {"white": "#ffffff", "black": "#000000"}


def _n(v):
    """A stable number: ints stay ints, everything else to 2 decimals."""
    v = round(float(v), 2)
    return int(v) if v == int(v) else v


def norm_color(value):
    """Any CSS colour this tool meets → '#rrggbb' or '#rrggbbaa' (lowercase); None if not a colour."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    v = _NAMED.get(v, v)
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) == 8 and h.endswith("ff"):
            h = h[:6]
        return "#" + h if len(h) in (6, 8) else None
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)", v)
    if m:
        r, g, b = (max(0, min(255, round(float(x)))) for x in m.group(1, 2, 3))
        a = m.group(4)
        alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        out = "#%02x%02x%02x" % (r, g, b)
        return out if alpha >= 1 else out + "%02x" % round(alpha * 255)
    return None


def to_px(value):
    if isinstance(value, (int, float)):
        return _n(value)
    m = re.fullmatch(r"\s*(-?[\d.]+)\s*(px|rem)?\s*", str(value))
    if not m:
        return None
    n = float(m.group(1)) * (16 if m.group(2) == "rem" else 1)
    return _n(n)


class TokenMap:
    """Resolved registry tokens, indexed by value. `pb-*` is the tool's and never matches."""

    def __init__(self, doc):
        doc = doc if isinstance(doc, dict) else {}
        flat = T.resolve(doc)
        types = {T.css_var_name(path): typ for path, _tok, typ in T.walk(doc)}
        self.colors, self.dims = {}, {}
        for name in sorted(flat):
            if name.startswith("pb-"):
                continue
            val, typ = flat[name], types.get(name)
            if typ == "color" or (typ is None and norm_color(val)):
                c = norm_color(val)
                if c:
                    self.colors.setdefault(c, name)
            elif typ in ("dimension", None):
                px = to_px(val)
                if px is not None:
                    bucket = T.display_kind(name, "dimension")
                    self.dims.setdefault(bucket, {}).setdefault(px, name)

    def dim(self, px, buckets):
        for b in buckets:
            hit = self.dims.get(b, {}).get(px)
            if hit:
                return hit
        return None

    def color(self, css):
        return self.colors.get(norm_color(css) or "")


_SPACE, _RADIUS = ("space", "size"), ("radius",)
# The stage's text colour: a value no design uses, so a part that reports it inherited it.
_INHERIT = "rgb(1, 2, 3)"


def _styles(raw, tm):
    out = {}
    pad = raw.get("padding")
    if pad:
        t, r, b, l = (_n(x) for x in pad)
        p = {"top": t, "right": r, "bottom": b, "left": l}
        if t == r == b == l:
            tok = tm.dim(t, _SPACE)
            if tok:
                p["token"] = tok
        else:
            toks = {side: tm.dim(v, _SPACE) for side, v in (("top", t), ("right", r), ("bottom", b), ("left", l))}
            toks = {k: v for k, v in toks.items() if v}
            if toks:
                p["tokens"] = toks
        out["padding"] = p
    mar = raw.get("margin")
    if mar:
        # Like padding: four sides, a `token` when all four are one value that is a token, per-side
        # `tokens` otherwise. A side that is `auto` stays the keyword and never matches a token.
        t, r, b, l = ("auto" if x == "auto" else _n(x) for x in mar)
        m = {"top": t, "right": r, "bottom": b, "left": l}
        if t == r == b == l and t != "auto":
            tok = tm.dim(t, _SPACE)
            if tok:
                m["token"] = tok
        else:
            toks = {side: tm.dim(v, _SPACE) for side, v in (("top", t), ("right", r), ("bottom", b), ("left", l))
                    if v != "auto"}
            toks = {k: v for k, v in toks.items() if v}
            if toks:
                m["tokens"] = toks
        out["margin"] = m
    sp = raw.get("spacing")
    if sp and not sp.get("mixed"):
        gaps = [_n(g) for g in sp["gaps"]]
        gp = _n(sp.get("gapProp") or 0)
        s = {"direction": sp["axis"]}
        if sp.get("spread"):
            # space-between & co.: the distance is whatever is left over, so it is `auto`; a gap
            # declared beside it is the floor it never goes under.
            s.update({"value": "auto", "via": sp["spread"]})
            if gp > 0:
                s["min"] = gp
                tok = tm.dim(gp, _SPACE)
                if tok:
                    s["token"] = tok
        else:
            if len(set(gaps)) == 1:
                s["value"] = gaps[0]
                tok = tm.dim(gaps[0], _SPACE)
                if tok:
                    s["token"] = tok
            else:
                s["value"] = None
                s["values"] = gaps
            # What creates the distance: a flex/grid `gap`, the children's margins, both — or
            # neither, when it is only line boxes (an inline child after a block one).
            m = bool(sp.get("margin"))
            s["via"] = ("gap+margin" if gp > 0 and m else "gap" if gp > 0 else "margin" if m else
                        "layout" if any(gaps) else "none")
        out["itemSpacing"] = s
    rad = raw.get("radius")
    if rad:
        corners = [_n(x) for x in rad]
        if len(set(corners)) == 1:
            c = {"value": corners[0]}
            tok = tm.dim(corners[0], _RADIUS)
        else:
            c = dict(zip(("topLeft", "topRight", "bottomRight", "bottomLeft"), corners))
            tok = None
        if tok:
            c["token"] = tok
        out["cornerRadius"] = c
    if raw.get("color") == _INHERIT:
        out["textColor"] = {"value": "inherit"}      # the body never sets it; the screen decides
    for key, field in (("background", "backgroundColor"), ("color", "textColor")):
        if raw.get(key) and raw[key] != _INHERIT:
            v = norm_color(raw[key])
            if v:
                entry = {"value": v}
                tok = tm.color(raw[key])
                if tok:
                    entry["token"] = tok
                out[field] = entry
    return out


# ── one component ────────────────────────────────────────────────────────────────────────

def demo_props(comp):
    """properties[].default, then the sidecar's usage.example (render.py's own rule), then a
    migrated sidecar's legacy renderProps for whatever is still missing."""
    props = R._default_props(comp)
    legacy = comp.get("legacy") if isinstance(comp.get("legacy"), dict) else {}
    for src in (legacy.get("anatomy"), legacy.get("spec")):
        rp = src.get("renderProps") if isinstance(src, dict) else None
        if isinstance(rp, dict):
            for k, v in rp.items():
                props.setdefault(k, v)
    return props


def _anchors(comp):
    els = comp.get("elements") if isinstance(comp.get("elements"), dict) else {}
    return {k: v["anchor"] for k, v in els.items()
            if isinstance(v, dict) and isinstance(v.get("anchor"), str) and v["anchor"].strip()}


def _variants(props):
    """(prop, is, props-with-it-unset) for every prop worth unsetting, in sorted order."""
    for k in sorted(props):
        v = props[k]
        if v is False or v is None or v == "":
            continue
        p = dict(props)
        if v is True:
            p[k] = False
            yield k, "true", p
        else:
            del p[k]
            yield k, "set", p


def _layout(parts):
    kids = {}
    for p in parts:
        if p["parent"] is not None:
            kids.setdefault(p["parent"], []).append(p["name"])

    def node(name):
        if name not in kids:
            return name
        return {name: [node(c) for c in kids[name]]}
    tree = node("root")
    return [tree if isinstance(tree, dict) else {"root": []}]


def measure_component(page, comp, tm):
    """→ (fields, error). `fields` holds the five owned sidecar keys minus `measured.at`."""
    fn = comp.get("renderFn")
    if not fn:
        return None, "no renderFn"
    props = demo_props(comp)
    anchors = _anchors(comp)
    base = page.evaluate("([f, p, a]) => window.pbMeasure(f, p, a)", [fn, props, anchors])
    if base.get("error"):
        return None, base["error"]
    parts = base["parts"]
    names = [p["name"] for p in parts]
    when = {}
    for prop, is_, p in _variants(props):
        alt = page.evaluate("([f, p, a]) => window.pbMeasure(f, p, a)", [fn, p, anchors])
        if alt.get("error"):
            continue                    # a prop the component cannot render without: required
        left = {x["name"] for x in alt["parts"]}
        for n in names:
            if n != "root" and n not in left and n not in when:
                when[n] = {"prop": prop, "is": is_}
    anatomy, elements = {}, {}
    for p in parts:
        a = {"type": p["type"]}
        if p.get("instanceOf"):
            a["instanceOf"] = p["instanceOf"]
        anatomy[p["name"]] = a
        el = {"parent": p["parent"]}
        if p["name"] in anchors:
            el["anchor"] = anchors[p["name"]]
        # An instance's own padding and spacing are ITS spec (its own sidecar), not this one's.
        st = _styles(p["styles"], tm) if p["type"] != "instance" else {}
        if st:
            el["styles"] = st
        if p["name"] in when:
            el["visibleWhen"] = when[p["name"]]
        elements[p["name"]] = el
    fields = {"anatomy": anatomy, "layout": _layout(parts), "elements": elements,
              "measured": {"by": "spec_measure.py", "props": props}}
    rs = elements["root"].get("styles", {})
    pad = rs.get("padding") or {}
    bg = (rs.get("backgroundColor") or {}).get("value") or ""
    opaque = bool(bg) and not (len(bg) == 9 and bg.endswith("00"))
    # Q-G1 (b): a card is a painted root (fill + radius > 0 + padding > 0) that is NOT a native control
    # element (<button>, <a>, <input>, <select>, <textarea>) and that holds at least two parts. A clickable
    # div (role=button) is still a card; a painted button around one label is not.
    if (opaque and not base.get("control") and rs.get("cornerRadius")
            and any(pad.get(s, 0) for s in ("top", "right", "bottom", "left"))
            and sum(1 for p in parts if p["name"] != "root") >= 2):
        fields["shape"] = "card"
    return fields, None


# ── read / write ─────────────────────────────────────────────────────────────────────────

def _canon(obj):
    return json.loads(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def merge_sidecar(existing, fields, now):
    """The owned keys replaced, everything else kept. Returns (new, changed)."""
    old = existing if isinstance(existing, dict) else {}
    new = {k: v for k, v in old.items() if k not in OWNED}
    new.update(_canon(fields))
    prev_at = (old.get("measured") or {}).get("at") if isinstance(old.get("measured"), dict) else None
    same = all(_canon({k: v for k, v in (old.get(k) or {}).items() if k != "at"} if k == "measured" else old.get(k))
               == _canon({k: v for k, v in (new.get(k) or {}).items() if k != "at"} if k == "measured" else new.get(k))
               for k in OWNED)
    new["measured"]["at"] = prev_at if (same and prev_at) else now
    return new, not same


def _dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _read_sidecar(path):
    """→ (dict, None) · ({}, None) when the file is MISSING (the one case that means "start one") ·
    (None, reason) when it exists but cannot be used. A sidecar that does not parse is never
    treated as empty: writing over it would destroy the hand-authored keys the person is mid-edit on."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}, None
    except UnicodeDecodeError as e:
        return None, "is not valid UTF-8 (%s)" % e
    except ValueError as e:
        return None, "is not valid JSON (%s)" % e
    except OSError as e:
        return None, "cannot be read (%s)" % (e.strerror or e)
    if not isinstance(data, dict):
        return None, "must hold a JSON object, not %s" % type(data).__name__
    return data, None


def _schema_of(raw):
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    v = meta.get("schemaVersion", 2)         # absent → schema 2, as everywhere else in pb
    return v if isinstance(v, int) and not isinstance(v, bool) else 2


def _write_results(args, base_dir, results, errors, now):
    """The write phase, under the registry lock. Re-reads registry.json (it may have changed while
    the browser measured), replaces each sidecar atomically, and adds `specSrc` only where it was
    missing. Fills `errors` for what could not be written; returns an exit code (0 or EXIT_*)."""
    try:
        with open(args.registry, encoding="utf-8") as f:
            fresh = json.load(f)
    except (OSError, ValueError) as e:
        print("spec_measure: cannot re-read %s to write: %s" % (args.registry, e), file=sys.stderr)
        return EXIT_UNREADABLE
    by_id = {c["id"]: c for c in fresh.get("components", []) or [] if isinstance(c, dict) and c.get("id")}
    reg_dirty = False
    for cid in sorted(results):
        comp = by_id.get(cid)
        if comp is None:
            errors[cid] = "no longer in registry.json — nothing written"
            continue
        rel = comp.get("specSrc") or "spec/components/%s.json" % cid
        path = os.path.normpath(os.path.join(base_dir, rel))
        existing, why = _read_sidecar(path)
        if why:
            errors[cid] = "%s %s — left exactly as it is, nothing written for it" % (rel, why)
            continue
        new, changed = merge_sidecar(existing, results[cid], now)
        if changed or not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            pbslice.atomic_write_text(path, _dump(new))
            print("measured %s → %s" % (cid, rel))
        else:
            print("measured %s — unchanged" % cid)
        if not comp.get("specSrc"):
            comp["specSrc"] = rel
            reg_dirty = True
    if reg_dirty:
        pbslice._write(args.registry, fresh)
        print("registry: specSrc added for new sidecar(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure component anatomy + spec from the live render.")
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--component", action="append", default=[], metavar="ID")
    ap.add_argument("--write", action="store_true", help="write the sidecars (default: print JSON)")
    ap.add_argument("--width", type=int, default=None, help="stage width in px (default: by meta.device)")
    args = ap.parse_args(argv)

    try:
        with open(args.registry, encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("the registry must be a JSON object")
    except (OSError, ValueError) as e:
        print("spec_measure: cannot read %s: %s" % (args.registry, e), file=sys.stderr)
        return EXIT_UNREADABLE
    if args.write and _schema_of(raw) < MIN_SCHEMA:
        print("spec_measure: %s is schema %d; --write needs schema %d, the sidecar shape this tool writes. "
              "Run /pb:update-version --apply, then measure again (nothing was written)."
              % (args.registry, _schema_of(raw), MIN_SCHEMA), file=sys.stderr)
        return EXIT_REFUSED_SCHEMA
    base_dir = os.path.dirname(os.path.abspath(args.registry))

    # A sidecar that does not parse must not stop the others, and must never be written over: it is
    # reported against its component and left out of this run (a corrupt SCREEN sidecar is only
    # warned about — nothing here measures a screen, but the page inlines the registry around it).
    # A MISSING specSrc file is not "bad": load_specs fails closed on it, below.
    bad = {}
    loadable = copy.deepcopy(raw)
    for kind in ("components", "screens"):
        for item in loadable.get(kind, []) or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            src = item.get("specSrc")
            if src:
                data, why = _read_sidecar(os.path.normpath(os.path.join(base_dir, src)))
                if why:
                    bad[(kind, item["id"])] = "%s %s" % (src, why)
                    item.pop("specSrc")
    try:
        reg = R.load_specs(R.load_bodies(loadable, base_dir), base_dir)
    except R.RenderError as e:
        print("spec_measure: %s" % e, file=sys.stderr)
        return EXIT_UNREADABLE
    comps = [c for c in reg.get("components", []) or [] if isinstance(c, dict) and c.get("id")]
    for c in comps:            # a sidecar at the default path that specSrc does not name yet
        if c.get("specSrc") or ("components", c["id"]) in bad:
            continue
        default = os.path.join(base_dir, "spec", "components", c["id"] + ".json")
        data, why = _read_sidecar(default)
        if why:
            bad[("components", c["id"])] = "spec/components/%s.json %s" % (c["id"], why)
        else:
            for k, v in data.items():
                c.setdefault(k, v)
    for (kind, ident), why in sorted(bad.items()):
        if kind == "screens":
            print("spec_measure: warning: screen %s: %s — ignored (screens are not measured)" % (ident, why),
                  file=sys.stderr)
    by_id = {c["id"]: c for c in comps}
    wanted = args.component or [c["id"] for c in comps]
    unknown = [w for w in wanted if w not in by_id]
    unreadable = {cid: why for (kind, cid), why in bad.items() if kind == "components"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("spec_measure: Playwright is not installed, so nothing was measured "
              "(pip install playwright && playwright install chromium).", file=sys.stderr)
        return EXIT_NO_PLAYWRIGHT

    device = (reg.get("meta") or {}).get("device")
    width = args.width or _WIDTH_BY_DEVICE.get(device, 960)
    tm = TokenMap(reg.get("tokens"))
    results = {}
    errors = {w: "no such component" for w in unknown}
    for cid in wanted:
        if cid in unreadable:
            errors[cid] = "%s — not measured, nothing written for it" % unreadable[cid]
    with sync_playwright() as p:
        try:
            browser = pbbrowser.open_browser(p, "spec_measure")
        except Exception as e:
            print("spec_measure: could not launch Chromium (%s). Run: playwright install chromium"
                  % str(e).splitlines()[0], file=sys.stderr)
            return EXIT_NO_CHROMIUM
        page = browser.new_page()
        page_errors = []
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.set_content(build_page(reg, base_dir, width), wait_until="load")
        if not page.evaluate("typeof window.pbMeasure === 'function'"):
            browser.close()
            print("spec_measure: the measuring page did not load: %s"
                  % ("; ".join(page_errors) or "unknown error"), file=sys.stderr)
            return EXIT_PAGE
        for cid in wanted:
            if cid in unknown or cid in unreadable:
                continue
            fields, err = measure_component(page, by_id[cid], tm)
            if err:
                errors[cid] = err
            else:
                results[cid] = fields
        browser.close()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not args.write:
        out = {cid: dict(_canon(f), measured=dict(f["measured"], at=now)) for cid, f in results.items()}
        print(json.dumps(out, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        try:
            with pbslice.registry_lock(args.registry, "spec_measure --write"):
                rc = _write_results(args, base_dir, results, errors, now)
        except pbslice.RegistryLocked as e:
            print("spec_measure: %s Nothing was written." % e, file=sys.stderr)
            return EXIT_LOCKED
        if rc:
            return rc
    for cid in sorted(errors):
        print("spec_measure: %s: %s" % (cid, errors[cid]), file=sys.stderr)
    return EXIT_FAIL if errors else 0


if __name__ == "__main__":
    sys.exit(main())
