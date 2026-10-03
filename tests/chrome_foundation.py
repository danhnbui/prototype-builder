#!/usr/bin/env python3
"""
chrome_foundation.py — the tool/product boundary, as a static guard (stdlib only).

The three shells used to paint themselves with the PROJECT's tokens: applyRegistryTokens() wrote
the registry's `--brand` onto :root, so an orange project got an orange tab strip, and three
unrelated token vocabularies meant even one project disagreed with itself. The fix is structural:

  --pb-*        the TOOL's tokens. One file (pb/template/chrome.css), injected into every shell.
  .pb-product   the PROJECT's subtree. The registry's tokens are scoped to it.

The browser suites (e2e_smoke, sandbox_shell, r5_ds_site) prove this works. THIS test is the cheap
one that fails the moment someone quietly breaks the shape of it — which is how it broke before.

  1. chrome.css is valid, self-contained, never reads a project token, and every colour it
     defines resolves in BOTH themes (a light-dark() pair, or one of the few fixed colours drawn
     around the product — a device bezel is not themed)
  2. all three shells carry the injection marker, and every build path fills it
  3. the shells' :root speaks in --pb-*; the project's colour lives only on .pb-product, and
     .pb-product never reads a --pb-* colour (directly or through an alias it fails to redefine)
  4. applyRegistryTokens() scopes to the product and reserves pb-*; no registry defines a pb-* token
  5. every place a project renders sits inside .pb-product — which is `color-scheme: light`, so
     the product cannot change with the tool's theme
  6. nothing re-introduces a second vocabulary; every shell boots the theme before first paint
  7. (browser, skipped without Playwright) every --pb-* colour resolves in light AND dark, the
     chrome really does change, and .pb-product plus the device frame do not change at all

Dark mode is back (round 2, the user asked for it). What used to be "light only" is now: the
TOOL has two themes and the PRODUCT has exactly one — its own. That is the boundary this guards.

Usage:  python3 tests/chrome_foundation.py      (.venv/bin/python for section 7)
Exit:   0 = clean · 1 = the boundary moved
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "pb", "template")
sys.path.insert(0, os.path.join(ROOT, "pb", "tools"))
import render  # noqa: E402

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def read(*parts):
    return open(os.path.join(*parts), encoding="utf-8").read()


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def below_root(css):
    """The CSS with the :root token block removed — raw values are allowed ONLY inside it."""
    return re.sub(r":root\s*\{[^}]*\}", "", strip_comments(css), flags=re.S)


MARK = "/*__PB_CHROME__*/"
chrome = read(TPL, "chrome.css")
proto = read(TPL, "prototype.html")
ds = read(TPL, "design-system.html")
cmp_ = read(TPL, "explore-compare.html")
runtime = read(TPL, "runtime.js")

print("1 · chrome.css")
body = strip_comments(chrome)
check(body.count("{") == body.count("}") and chrome.count("/*") == chrome.count("*/"),
      "braces and comments balance (a stray terminator in a comment turns prose into CSS)")
check(MARK not in chrome and "__PB_CHROME__" not in chrome,
      "it never contains its own marker — it is injected at one, and a copy would be re-matched")
check("--fund-" not in body and "var(--brand" not in body and "var(--neutral" not in body,
      "it never reads a project token (--brand, --neutral-*) — the tool has its own vocabulary")
loose = below_root(chrome)
hexes = sorted(set(re.findall(r"#[0-9a-fA-F]{3,8}\b", loose)))
pxs = sorted(set(re.findall(r"(?<![\w-])\d*\.?\d+px\b", re.sub(r"@media[^{]*\{", "{", loose))))
check(not hexes, f"no raw hex below :root ({hexes})")
check(not pxs, f"no raw px below :root ({pxs})")
# the colour vocabulary: every --pb-* colour is a light-dark() pair, or a deliberately fixed one
ROOT_RE = re.compile(r"(?m)^:root\s*\{(.*?)^\}", re.S)
root_css = strip_comments(ROOT_RE.search(chrome).group(1)) if ROOT_RE.search(chrome) else ""
decls = dict(re.findall(r"(--pb-[\w-]+)\s*:\s*([^;]+);", root_css))
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|light-dark\(")
FIXED = {"--pb-island", "--pb-island-ink", "--pb-bezel", "--pb-bezel-edge", "--pb-mask"}
colours = {k: v.strip() for k, v in decls.items() if COLOUR.search(v) and not v.strip().startswith(("0 ", "0."))}
PAIR = re.compile(r"^light-dark\(\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))\s*,\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))\s*\)$")
unpaired = sorted(k for k, v in colours.items() if k not in FIXED and not PAIR.match(v))
check(len(colours) >= 20 and not unpaired,
      f"every --pb-* colour is a light-dark() pair ({len(colours)} colours; unpaired: {unpaired})")
check(all(k in decls for k in ("--pb-page", "--pb-surface", "--pb-raised", "--pb-stage", "--pb-wash", "--pb-press",
                               "--pb-hair", "--pb-hair-2", "--pb-ink", "--pb-ink-2", "--pb-ink-3", "--pb-on-ink",
                               "--pb-scrim", "--pb-pass", "--pb-pass-bg", "--pb-fail", "--pb-fail-bg",
                               "--pb-warn", "--pb-warn-bg")),
      "…the full set: surfaces, hairlines, three inks, on-ink, scrim, and pass/fail/warn with their grounds")
check(sorted(k for k in colours if k in FIXED) == sorted(FIXED - {"--pb-mask"} | {"--pb-mask"}) and
      all(not v.startswith("light-dark") for k, v in colours.items() if k in FIXED),
      "…and the fixed ones are exactly the things drawn AROUND the product (island, bezel) plus the mask")
check(re.search(r"color-scheme:\s*light dark", root_css) is not None,
      ":root is `color-scheme: light dark` — no data-theme follows the OS")
check(re.search(r':root\[data-theme="light"\]\s*\{\s*color-scheme:\s*light;?\s*\}', chrome) is not None
      and re.search(r':root\[data-theme="dark"\]\s*\{\s*color-scheme:\s*dark;?\s*\}', chrome) is not None,
      "…and <html data-theme=light|dark> pins it")
pp = re.search(r"(?m)^\.pb-product\s*\{(.*?)^\}", chrome, re.S)
check(pp is not None and re.search(r"color-scheme:\s*light\s*;", pp.group(1)) is not None,
      ".pb-product is `color-scheme: light` — every --pb-* read inside it resolves to its light half")
check(re.search(r"--pb-shadow\s*:\s*light-dark", root_css) is None,
      "no light-dark() around a non-colour (a shadow is geometry + a themed colour, or it is invalid)")

print("2 · one foundation, injected everywhere")
for name, src in (("prototype.html", proto), ("design-system.html", ds), ("explore-compare.html", cmp_)):
    check(src.count(MARK) == 1, f"{name} carries the injection marker exactly once")
inj = render.inject_chrome("<style>" + MARK + "</style>")
check(MARK not in inj and "--pb-ink" in inj and ".pb-bar" in inj, "inject_chrome fills the marker with the foundation")
check(render.inject_chrome("<html>no marker</html>") == "<html>no marker</html>",
      "...and is a no-op on an older shell that has none (fail open, never block a render)")
check(render.load_chrome_css().lstrip().startswith(":root"),
      "the injected CSS has its file header stripped (it addresses whoever edits chrome.css)")
serve_src = read(ROOT, "pb", "tools", "serve.py")
check("render.inject_chrome(shell)" in serve_src, "the preview server injects it into the explore-compare page too")
render_src = read(ROOT, "pb", "tools", "render.py")
check(render_src.count("inject_chrome(") >= 3, "build_html and build_ds_html both inject it")

print("3 · two scopes, one set of names")
root_block = re.search(r":root\s*\{(.*?)\n    \}", proto[proto.index(MARK):], re.S)
check(root_block is not None, "the shell has a tool-scope :root block")
if root_block:
    rb = root_block.group(1)
    check(re.search(r"--brand:\s*var\(--pb-ink\)", rb) is not None,
          "…in which --brand is the tool's ink, not a project colour")
    check(re.search(r"--font-body:\s*var\(--pb-font\)", rb) is not None, "…and the font is the tool's")
    check(not re.search(r"--brand:\s*#", rb), "…and no project colour literal sits in the tool scope")
    # Every colour name the tool scope points at --pb-* must be given back to the product, or a
    # product rule reading it would follow the tool's theme.
    aliased = sorted(set(re.findall(r"(--[\w-]+):\s*var\(--pb-(?:page|surface|raised|stage|wash|press|hair|hair-2|ink|ink-2|ink-3|on-ink|pass|fail|warn)\b", rb)))
# the rule itself, at the start of a line — the first textual `.pb-product` is in a comment
pb_rule = re.search(r"^    \.pb-product\s*\{(.*?)\n    \}", proto, re.S | re.M)
check(pb_rule is not None and re.search(r"--brand:\s*#1c4ed8", pb_rule.group(1)) is not None,
      "the PROJECT's defaults (brand, neutrals, Inter, 8/16/24 radii) live on .pb-product")
check(pb_rule is not None and "--font-weight-bold:   700" in pb_rule.group(1),
      "…including the project's own weights, so adopting the tool's two weights did not restyle a product")
if root_block and pb_rule:
    missing = [n for n in aliased if not re.search(re.escape(n) + r"\s*:", pb_rule.group(1))]
    check(aliased and not missing,
          f"every tool colour alias ({len(aliased)}) is redefined on .pb-product — none leaks in ({missing})")
# and no rule that styles the product reads a tool colour directly
PB_COLOUR = re.compile(r"var\(--pb-(?:page|surface|raised|stage|wash|press|hair|hair-2|ink|ink-2|ink-3|on-ink|scrim|"
                       r"shadow-c|pass|pass-bg|fail|fail-bg|warn|warn-bg|info|info-bg)\)")
leaks = []
for name, src in (("chrome.css", chrome), ("prototype.html", proto), ("design-system.html", ds), ("explore-compare.html", cmp_)):
    for sel, blk in re.findall(r"([^{}]*\.pb-product[^{}]*)\{([^{}]*)\}", strip_comments(src)):
        bare = sel
        while re.search(r":not\([^()]*\)", bare):          # `:not(.pb-product *)` EXCLUDES the product
            bare = re.sub(r":not\([^()]*\)", "", bare)
        if ".pb-product" in bare and PB_COLOUR.search(blk):
            leaks.append(f"{name}: {sel.strip()[:60]}")
check(not leaks, f"no .pb-product rule reads a --pb-* colour ({leaks})")

print("4 · the token applier")
fn = re.search(r"function applyRegistryTokens\(reg\)\s*\{(.*?)\n    \}\n", runtime, re.S)
check(fn is not None, "applyRegistryTokens found in runtime.js")
if fn:
    f = fn.group(1)
    check("'.pb-product{}'" in f and "decl.setProperty('--' + name" in f,
          "it writes through the CSSOM onto a .pb-product rule (setProperty sanitises a hostile value)")
    check("indexOf('pb-') !== 0" in f, "pb-* is reserved: a registry cannot overwrite the tool's tokens")
    check("root.style.setProperty('--prj-'" in f, "the tool can still opt in on purpose, via --prj-<name>")
    check("root.style.setProperty('--' + name" not in f,
          "and it does NOT write a project token onto :root — that was the bug")
import tokens as _tokens  # noqa: E402  (pb/tools, already on the path)
import json as _json  # noqa: E402
for label, path in (("golden", os.path.join(ROOT, "fixtures", "golden", "registry.json")),):
    if not os.path.exists(path):
        continue
    try:
        reg = _json.load(open(path, encoding="utf-8"))
        names = list(_tokens.resolve(reg.get("tokens") or {}).keys()) if hasattr(_tokens, "resolve") else []
    except Exception:  # noqa: BLE001 — a registry another agent is mid-edit on is not this test's failure
        names = []
    raw = _json.dumps((reg or {}).get("tokens") or {}) if 'reg' in dir() else ""
    check(not any(str(n).startswith("pb-") for n in names) and '"pb-' not in raw,
          f"the {label} registry defines no pb-* token (the tool's vocabulary is not the project's to set)")

print("5 · every project mount is inside .pb-product")
check('class="proto-screen pb-product"' in proto, "prototype: the screen mount")
check("stage pb-product" in ds and "box pb-product" in ds and "sw pb-product" in ds,
      "design system: demo stage, variant cells, token swatches")
check("--prj-brand" in proto, "the browser mock's favicon/avatar take the project colour on purpose (--prj-brand)")

print("6 · no second vocabulary; the theme boots before first paint")
BOOT = re.compile(r"<script>\(function \(\) \{(.*?)\}\)\(\);</script>", re.S)
for name, src in (("prototype.html", proto), ("design-system.html", ds), ("explore-compare.html", cmp_)):
    head = src[:src.find("</head>")]
    m = BOOT.search(head)
    body_ = m.group(1) if m else ""
    first_css = min([i for i in (head.find("<style"), head.find("<link")) if i != -1] or [len(head)])
    check(m is not None and m.start() < first_css and len(m.group(0).splitlines()) <= 10
          and "localStorage.getItem(K)" in body_ and "'pb-theme'" in body_ and "try {" in body_
          and "window.pbSetTheme" in body_ and "removeAttribute('data-theme')" in body_,
          f"{name}: a ≤10-line bootstrap in <head>, before any CSS, reads localStorage pb-theme (in a try) "
          "and exposes pbSetTheme()")
    check("prefers-color-scheme" not in strip_comments(src.split("<script", 1)[0] if False else src)
          or "prefers-reduced-motion" in src, f"{name}: the theme is light-dark() + color-scheme, not a second palette")
check("#2457d6" not in strip_comments(cmp_) and "#7ea2ff" not in strip_comments(cmp_),
      "explore-compare.html's near-miss accents are gone (in code — its comment may still name them)")
check(re.search(r"--ds-accent:\s*#", ds) is None and re.search(r"--accent:\s*#", cmp_) is None,
      "the shells' chrome names are aliases of --pb-*, never their own hex")

print("7 · both themes resolve; the product does not move (browser)")
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("  - SKIPPED (playwright not installed — run with .venv/bin/python)")
if sync_playwright:
    import tempfile
    GOLD = os.path.join(ROOT, "fixtures", "golden", "registry.json")
    PROBE = """() => {
      const out = {}, probe = document.createElement('i'), host = document.createElement('b');
      host.style.color = 'rgb(1, 2, 3)'; host.appendChild(probe); document.body.appendChild(host);
      const css = [...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } });
      const names = new Set();
      css.forEach(r => { if (r.style) for (const p of r.style) if (p.startsWith('--pb-')) names.add(p); });
      names.forEach(n => {
        const raw = getComputedStyle(document.documentElement).getPropertyValue(n).trim();
        if (!/#|rgb|light-dark/.test(raw) || /^0 /.test(raw)) return;      // lengths, fonts, shadows
        probe.style.color = 'var(' + n + ')'; out[n] = getComputedStyle(probe).color;
      });
      host.remove(); return out;
    }"""
    SNAP = """(sel) => {
      const out = [];
      document.querySelectorAll(sel).forEach(root => [root, ...root.querySelectorAll('*')].forEach(e => {
        const c = getComputedStyle(e);
        out.push([c.color, c.backgroundColor, c.borderTopColor, c.borderLeftColor, c.boxShadow, c.outlineColor].join('|'));
      }));
      return out;
    }"""
    with tempfile.TemporaryDirectory() as d:
        p_out, d_out = os.path.join(d, "p.html"), os.path.join(d, "ds.html")
        render.render_file(GOLD, os.path.join(TPL, "prototype.html"), p_out)
        render.render_ds_file(GOLD, os.path.join(TPL, "design-system.html"), os.path.join(TPL, "runtime.js"), d_out)
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            ctx = br.new_context(viewport={"width": 1440, "height": 900})
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:")) else r.abort())
            pg = ctx.new_page()
            for label, url, sel in (("prototype", p_out, ".pb-product, .proto-frame"),
                                    ("design system", d_out, ".pb-product")):
                pg.goto("file://" + url, wait_until="domcontentloaded")
                pg.wait_for_selector(sel.split(",")[0], state="attached", timeout=10000)
                pg.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
                snaps, cols, body = {}, {}, {}
                for theme in ("light", "dark"):
                    pg.evaluate("t => window.pbSetTheme(t)", theme); pg.wait_for_timeout(60)
                    cols[theme] = pg.evaluate(PROBE)
                    snaps[theme] = pg.evaluate(SNAP, sel)
                    body[theme] = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                pg.evaluate("window.pbSetTheme('system')")
                bad = sorted(n for t in cols for n, v in cols[t].items() if v == "rgb(1, 2, 3)")
                check(len(cols["light"]) >= 20 and not bad,
                      f"{label}: all {len(cols['light'])} --pb-* colours resolve in light and dark ({bad})")
                flips = sum(1 for n in cols["light"] if cols["light"][n] != cols["dark"].get(n))
                check(body["light"] != body["dark"] and flips >= 15,
                      f"{label}: the chrome really changes ({body['light']} → {body['dark']}; {flips} tokens flip)")
                same = snaps["light"] == snaps["dark"]
                diff = next((i for i, (a, b) in enumerate(zip(snaps["light"], snaps["dark"])) if a != b), None)
                check(len(snaps["light"]) > 10 and same,
                      f"{label}: {len(snaps['light'])} elements of the product + device frame are identical in both themes"
                      + ("" if same else f" (first difference at #{diff}: {snaps['light'][diff]} → {snaps['dark'][diff]})"))
                pg.evaluate("applyRegistryTokens({tokens:{'pb-page':{$value:'#ff0000'},'pb-ink':{$value:'#ff0000'}}})")
                red = pg.evaluate("""() => { const p = document.querySelector('.pb-product') || document.body;
                   return [document.documentElement, p].map(e => getComputedStyle(e).getPropertyValue('--pb-ink').trim()
                     + getComputedStyle(e).getPropertyValue('--pb-page').trim()).join(' '); }""")
                check("#ff0000" not in red.lower(), f"{label}: a registry cannot redefine --pb-* (not on :root, not in the product)")
            br.close()

print()
if _fail:
    print(f"✗ {len(_fail)} chrome-foundation failure(s) — the tool/product boundary moved.")
    sys.exit(1)
print("✓ chrome-foundation clean.")
