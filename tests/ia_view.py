#!/usr/bin/env python3
"""
ia_view.py — UX Design → Information Architecture and the Project Summary, measured in a browser
(round 3 · wave B2).

Information Architecture used to be two columns — the job list beside the site map, with a row of role
pills of its own above the jobs. It is now ONE column, and ONE filter bar drives it:

  1. vertical      the heading, ONE filter bar, the site map (full width), then the jobs — stacked, never
                   side by side, at 1440px and at 430px (no `.ia-layout`, no `.ia-roles` pills). Below 720px
                   the chart is a plain box the finger pans sideways, and the zoom controls are gone
  2. one bar       search · Role · Priority · Screens · the quick chip "Not handled" (jobs with no screen),
                   in that order. Role = meta.roles ∪ the roles the jobs name; one nobody declared says so
  3. the filter    filters the job rows AND the map: a screen no shown job is placed on dims (`pb:filter`).
                   Role is multi-select (OR), chips are AND-ed, "Not handled" selects the jobs with no
                   screen, Clear brings everything back, and the filter survives the tab being rebuilt
  4. rows          a job shows its `title` when it has one; opened it shows the `gap` and the `source`, and
                   marks a role that meta.roles never declared

Project Summary reads like a page, not a form:

  5. prose         objectives / insights go through pbRichText (paragraphs, "·" bullets, marks, .pb-num),
                   held to a 760px measure, the first paragraph set larger than the rest
  6. principles    a numbered list — number · bold title · body — not a stack of cards
  7. headings      sections are real headings (h2 / h3), and the table of contents is built from them: it
                   appears at three or more, beside the text, and is hidden below 1100px

The project is a copy of the golden fixture with the IA jobs and the Summary
text replaced by fixtures of this test's own, so every count below is known.

Usage:  .venv/bin/python tests/ia_view.py
Exit:   0 = clean · 1 = a failure · 2 = Playwright/browser not available (skip)
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "pb", "tools")
TPL = os.path.join(ROOT, "pb", "template")
GOLDEN = os.path.join(ROOT, "fixtures", "golden")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright not installed (pip install playwright && playwright install chromium)")
    sys.exit(2)

_fail = []


def check(cond, msg):
    print(f"  {'✓' if cond else '✗'} {msg}")
    if not cond:
        _fail.append(msg)


def _load(stem, path):
    spec = importlib.util.spec_from_file_location(stem, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[stem] = m
    spec.loader.exec_module(m)
    return m


render = _load("render", os.path.join(TOOLS, "render.py"))
SRC = GOLDEN
FREEZE = "*,*::before,*::after{transition:none!important;animation:none!important}"


def build_project(tmp):
    """A copy of the golden project whose IA jobs and Summary text are this test's own."""
    proj = os.path.join(tmp, "proj")
    shutil.copytree(SRC, proj)
    path = os.path.join(proj, "registry.json")
    reg = json.load(open(path, encoding="utf-8"))
    screens = [s["id"] for s in reg["screens"]]
    declared = [r["id"] for r in reg["meta"]["roles"]]
    r1, r2 = declared[0], declared[1]
    base = {"when": "something happens", "want": "to do the thing", "so": "the outcome follows"}
    jobs = [
        dict(base, id="jA", title="J1 · First job title", priority="P0", roles=[r1], screens=[screens[0], screens[1]],
             gap="**Gap:** the prototype covers it; the app does not yet.", source="PRD §1"),
        dict(base, id="jB", priority="P1", roles=[r1, r2], screens=[screens[1]], want="to see the second job"),
        dict(base, id="jC", priority="P1", roles=[r2], screens=[], want="to find the third job"),
        dict(base, id="jD", priority="P2", roles=["ghost"], screens=[], want="to reach the fourth job"),
        dict(base, id="jE", priority="P0", roles=[r2], screens=[screens[2]], want="to open the fifth job"),
    ]
    reg.setdefault("ia", {})["jobs"] = jobs
    reg["ia"]["populated"] = True
    # The golden fixture names no nav hub, so it derives no site map; a two-tab hub (as in
    # tests/bracket_path.py) gives the canvas, dimming and wheel checks a map to act on.
    reg["meta"]["navHub"] = "ia-tabs"
    reg["components"] += [
        {"id": "ia-tab", "level": "atom", "renderSrc": "render/components/ia-tab.js", "renderFn": "renderCmpIaTab"},
        {"id": "ia-tabs", "level": "organism", "renderSrc": "render/components/ia-tabs.js", "renderFn": "renderCmpIaTabs"},
    ]
    with open(os.path.join(proj, "render", "components", "ia-tab.js"), "w", encoding="utf-8") as f:
        f.write("return '<button data-nav=\"' + pbEscape(props.screen) + '\">' + pbEscape(props.label) + '</button>';\n")
    with open(os.path.join(proj, "render", "components", "ia-tabs.js"), "w", encoding="utf-8") as f:
        f.write("var TABS = [\n  { label: 'One', screen: %s },\n  { label: 'Two', screen: %s }\n];\n"
                "return TABS.map(function (t) { return pbUse('ia-tab', { label: t.label, screen: t.screen }); }).join('');\n"
                % (json.dumps(screens[0]), json.dumps(screens[1])))
    reg["meta"]["overview"] = {
        "objectives": "A lead sentence with ==a highlight== and **a bold run**.\n\nA second paragraph that is not the lead, with 98.7% in it.",
        "principles": [
            {"num": 1, "title": "First principle", "body": "Body with `code` and **bold**."},
            {"num": 2, "title": "Second principle", "body": "Another body, 11,042 of them."},
            {"num": 3, "title": "Third principle", "body": "A plain body."},
        ],
    }
    reg["meta"]["userInsights"] = {
        "quantitative": "Intro line of the data.\n· first figure 98.7%\n· second figure\n· third figure",
        "researchSummary": "Paragraph one of the research.\n\nParagraph two of the research.",
        "executiveSummary": "The executive summary.",
    }
    json.dump(reg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return path, {"r1": r1, "r2": r2, "declared": declared, "screens": screens, "jobs": jobs}


GO_IA = "setMetaView('flow'); pbSetUxView('ia')"
VIS = "[...document.querySelectorAll('[data-fb-list=\"ia\"][data-key]')].filter(r => !r.hidden).map(r => r.getAttribute('data-key'))"
RECT = """(s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
  return { l: b.left, t: b.top, r: b.right, b: b.bottom, w: b.width, h: b.height }; }"""


def vertical(pg, w, h, label):
    pg.set_viewport_size({"width": w, "height": h})
    pg.evaluate(GO_IA)
    pg.wait_for_selector(".ia-scroll")
    pg.wait_for_timeout(250)
    q = lambda s: pg.evaluate(RECT, s)  # noqa: E731
    bar, mp, jobs, tabs = q(".ia-bar"), q(".ia-map"), q(".ia-jobs"), q(".ux-subtabs")
    check(all((bar, mp, jobs)), f"{label}: the bar, the map and the jobs are all there")
    if not all((bar, mp, jobs)):
        return
    title, lst = q(".ia-jobs-title"), q(".ia-jobs .pb-scan")
    check(bool(title and lst) and mp["b"] <= jobs["t"] + 1 and title["b"] <= bar["t"] + 1 and bar["b"] <= lst["t"] + 1,
          f"{label}: stacked — map ({mp['t']:.0f}–{mp['b']:.0f}), then the Jobs title, then the bar ({bar['t']:.0f}–{bar['b']:.0f}), "
          f"then the list ({lst['t'] if lst else 0:.0f}–…)")
    check(abs(mp["w"] - jobs["w"]) < 2 and mp["w"] >= tabs["w"] - 16,
          f"{label}: the map is the column's full width ({mp['w']:.0f}px of {tabs['w']:.0f}px), the jobs the same")
    check(pg.evaluate("document.querySelectorAll('.ia-layout, .ia-roles, .ia-jobs-col, .ia-map-col').length") == 0,
          f"{label}: no two-column layout and no role-pill row is left")
    check(pg.evaluate("document.querySelectorAll('.pb-fbar').length") == 1, f"{label}: ONE filter bar, for both")
    order = pg.evaluate("""() => { const b = document.querySelector('.pb-fbar');
      const seq = [b.querySelector('.pb-fbar-q'), b.querySelector('[data-pb-chip="role"]'), b.querySelector('[data-pb-chip="priority"]'),
        b.querySelector('[data-pb-chip="screens"]'), b.querySelector('[data-pb-quick="unhandled"]')];
      return seq.map((e, i) => !e ? 'missing:' + i : i === 0 ? true : !!(seq[i - 1].compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING)); }""")
    check(all(o is True for o in order), f"{label}: search → Role → Priority → Screens → Not handled ({order})")
    canvas = pg.evaluate("!!document.getElementById('iamap-stage')")
    if not canvas:
        print(f"  – {label}: this project derives no site map, so the canvas checks are skipped")
        return
    if w < 720:
        info = pg.evaluate("""() => { const v = document.querySelector('.ia-canvas .flow-viewport'), c = getComputedStyle(v);
          const z = document.querySelector('.ia-canvas .flow-zoom-controls');
          return { sw: v.scrollWidth, cw: v.clientWidth, ox: c.overflowX, zoomShown: z && getComputedStyle(z).display !== 'none' }; }""")
        check(info["sw"] > info["cw"] and info["ox"] == "auto",
              f"{label}: the chart is a box the finger pans sideways ({info['sw']}px of content in {info['cw']}px)")
        check(not info["zoomShown"], f"{label}: …and the zoom controls, which a phone cannot use, are gone")
    else:
        ch = pg.evaluate(RECT, ".ia-canvas")["h"]
        check(abs(ch - h * 0.5) <= 2, f"{label}: the chart is half the viewport tall ({ch:.0f}px of {h}px)")


def filtering(pg, ctx):
    print("2 · one filter bar, jobs and map")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.evaluate("pbFilterClear('ia')")
    pg.evaluate(GO_IA)
    pg.wait_for_selector(".ia-scroll")
    pg.wait_for_timeout(250)
    r1, r2, screens, jobs = ctx["r1"], ctx["r2"], ctx["screens"], ctx["jobs"]
    keys = lambda: pg.evaluate(VIS)  # noqa: E731
    canvas = pg.evaluate("!!document.getElementById('iamap-stage')")
    dimmed = lambda: pg.evaluate("[...document.querySelectorAll('.ia-node[data-screen].is-dim')].map(n => n.getAttribute('data-screen'))")  # noqa: E731
    nodes = pg.evaluate("[...document.querySelectorAll('.ia-node[data-screen]')].map(n => n.getAttribute('data-screen'))")

    check(keys() == [j["id"] for j in jobs], f"every job is listed to start with ({keys()})")
    qlabel = pg.inner_text('.pb-fbar [data-pb-quick="unhandled"]')
    check(qlabel.replace("\n", " ").split() == ["Not", "handled", "2"], f"the quick chip counts the jobs with no screen ({qlabel!r})")
    check(pg.inner_text(".pb-fbar-cnt").strip() == "5 of 5 jobs", f"the count reads N of N ({pg.inner_text('.pb-fbar-cnt').strip()!r})")

    # roles: declared ∪ used, with the one nobody declared marked
    pg.click('.pb-fbar [data-pb-chip="role"]')
    opts = pg.evaluate("[...document.querySelectorAll('.pb-fbar input[data-pb-opt=\"role\"]')].map(i => [i.value, i.closest('label').innerText.replace(/\\s+/g, ' ').trim()])")
    check([o[0] for o in opts] == ctx["declared"] + ["ghost"], f"the Role chip lists meta.roles then the roles the jobs add ({[o[0] for o in opts]})")
    check("undeclared" in opts[-1][1] and all("undeclared" not in o[1] for o in opts[:-1]),
          f"…and only the role nobody declared says so ({opts[-1][1]!r})")
    # multi-select, OR within the chip: jB has both roles
    pg.locator(f'.pb-fbar input[data-pb-opt="role"][value="{r2}"]').check()
    check(sorted(keys()) == ["jB", "jC", "jE"], f"Role {r2}: its jobs, including the one that has two roles ({keys()})")
    if canvas:
        lit = sorted(set(nodes) - set(dimmed()))
        want = sorted({screens[1], screens[2]} & set(nodes))
        check(lit == want, f"the map lights exactly the screens those jobs are placed on ({lit} vs {want})")
        check("serve the 3 jobs shown" in pg.inner_text("#iamap-live"), f"…and says what the dimming means ({pg.inner_text('#iamap-live').strip()!r})")
    pg.locator(f'.pb-fbar input[data-pb-opt="role"][value="{r1}"]').check()
    check(sorted(keys()) == ["jA", "jB", "jC", "jE"], f"a second role ORs ({keys()})")
    pg.keyboard.press("Escape")

    # Not handled: AND-ed with the chips
    pg.click('.pb-fbar [data-pb-quick="unhandled"]')
    check(sorted(keys()) == ["jC"], f"Not handled ANDs with Role — the jobs with no screen ({keys()})")
    pg.click('.pb-fbar [data-pb-fclear]')
    check(keys() == [j["id"] for j in jobs] and not dimmed(), "Clear brings every job back and un-dims the map")
    pg.click('.pb-fbar [data-pb-quick="unhandled"]')
    check(sorted(keys()) == ["jC", "jD"], f"Not handled alone: exactly the jobs with no screen ({keys()})")
    check(pg.inner_text(".pb-fbar-cnt").strip() == "2 of 5 jobs", "…and the count follows")
    if canvas:
        check(sorted(dimmed()) == sorted(nodes), "…none of them is placed on a screen, so the whole map dims")
        check("none of the 2 jobs" in pg.inner_text("#iamap-live"), f"…and the line under the title explains why ({pg.inner_text('#iamap-live').strip()!r})")

    # search narrows too; the filter survives the tab being rebuilt
    pg.click('.pb-fbar [data-pb-fclear]')
    pg.fill(".pb-fbar input[data-pb-fq]", "fifth")
    check(keys() == ["jE"], f"search matches what a row says ({keys()})")
    pg.evaluate("pbSetUxView('logic'); pbSetUxView('ia')")
    pg.wait_for_timeout(250)
    check(keys() == ["jE"] and pg.input_value(".pb-fbar input[data-pb-fq]") == "fifth",
          "…and survives leaving the tab and coming back")
    pg.evaluate("pbFilterClear('ia')")
    pg.fill(".pb-fbar input[data-pb-fq]", "nothing-matches-this")
    check(keys() == [] and "No jobs match" in pg.inner_text('[data-pb-fnone="ia"]'), "no match → the empty message names the noun")
    pg.evaluate("pbFilterClear('ia')")


def rows(pg, ctx):
    print("3 · job rows")
    pg.evaluate(GO_IA)
    pg.wait_for_selector(".ia-scroll")
    pg.wait_for_timeout(250)
    ti = lambda k: pg.inner_text(f'[data-fb-list="ia"][data-key="{k}"] .ti').strip()  # noqa: E731
    check(ti("jA") == "J1 · First job title", f"a job with a title shows the title ({ti('jA')!r})")
    check(ti("jB") == "To see the second job", f"a job without one shows its want ({ti('jB')!r})")

    def open_row(k):
        pg.click(f'[data-fb-list="ia"][data-key="{k}"] button')
        pg.wait_for_timeout(120)
        return pg.inner_text(f'[data-fb-list="ia"][data-key="{k}"]')

    a = open_row("jA")
    check("Gap" in a and "the prototype covers it; the app does not yet." in a and "Source" in a and "PRD §1" in a,
          "opened, a job shows its gap and its source")
    check(pg.evaluate("!!document.querySelector('[data-fb-list=\"ia\"][data-key=\"jA\"] .pb-rt strong')"), "…and the gap is rich text (its **bold** is bold)")
    d = open_row("jD")
    check("(undeclared)" in d and "ghost" in d, "a role meta.roles never declared is marked where the job lists it")
    check("(undeclared)" not in a, "…and a declared one is not")
    c = open_row("jC")
    check("Plan a screen" in c or "No screen yet" in c, "a job with no screen says so, and what to run")


DIM_PROBE = """() => {
  const bgOf = el => { while (el) { const c = getComputedStyle(el).backgroundColor; if (c !== 'rgba(0, 0, 0, 0)') return c; el = el.parentElement; } return 'rgb(255, 255, 255)'; };
  const parse = c => c.match(/[\\d.]+/g).map(Number).slice(0, 3);
  const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
  const cr = (a, b) => (Math.max(lum(a), lum(b)) + .05) / (Math.min(lum(a), lum(b)) + .05);
  const canvas = parse(bgOf(document.getElementById('iamap-stage')));
  const out = [];
  document.querySelectorAll('.ia-node.is-dim').forEach(n => {
    const op = parseFloat(getComputedStyle(n).opacity);
    n.querySelectorAll('.ia-node-t, .ia-node-t strong, .ia-node-id, .ia-node-m').forEach(e => {
      if (!e.textContent.trim()) return;
      const eff = parse(getComputedStyle(e).color).map((v, i) => op * v + (1 - op) * canvas[i]);
      out.push({ cls: e.className || e.tagName, op, ratio: cr(eff, canvas) });
    });
  });
  return out;
}"""


def dimming(pg):
    print("5 · a dimmed map node is set back, not gone")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.evaluate("pbFilterClear('ia')")
    pg.evaluate(GO_IA)
    pg.wait_for_selector(".ia-scroll")
    pg.wait_for_timeout(250)
    if not pg.evaluate("!!document.getElementById('iamap-stage')"):
        print("  – this project derives no site map, so the dimming checks are skipped")
        return
    pg.click('.pb-fbar [data-pb-quick="unhandled"]')           # nothing is placed on a screen → every node dims
    pg.wait_for_timeout(150)
    try:
        for theme in ("light", "dark"):
            pg.evaluate(f"pbSetTheme('{theme}')")
            pg.wait_for_timeout(200)
            rows = pg.evaluate(DIM_PROBE)
            check(len(rows) >= 3, f"{theme}: dimmed nodes have text to measure ({len(rows)} lines)")
            if rows:
                worst = min(rows, key=lambda r: r["ratio"])
                check(worst["ratio"] >= 3.0, f"{theme}: every line of a dimmed node stays at 3:1 or better against the canvas "
                      f"(worst {worst['ratio']:.2f}:1 on `{worst['cls']}`)")
                check(all(0.4 <= r["op"] <= 0.65 for r in rows), f"{theme}: …and the node is still clearly set back (opacity {rows[0]['op']})")
    finally:
        pg.evaluate("pbSetTheme('light')")
        pg.click('.pb-fbar [data-pb-fclear]')


def wheel(pg):
    print("5b · the map never traps the page's scroll")
    pg.set_viewport_size({"width": 1440, "height": 700})
    pg.evaluate("pbFilterClear('ia')")
    pg.evaluate(GO_IA)
    pg.wait_for_selector(".ia-scroll")
    pg.wait_for_timeout(400)
    if not pg.evaluate("!!document.getElementById('iamap-stage')"):
        print("  – this project derives no site map, so the wheel checks are skipped")
        return
    pg.evaluate("document.getElementById('ia-scroll').scrollTop = 0")
    over = pg.evaluate("document.getElementById('ia-scroll').scrollHeight > document.getElementById('ia-scroll').clientHeight")
    check(over, "(at 700px tall the IA column overflows, so there is something to scroll to)")
    box = pg.locator("#iamap-viewport").bounding_box()
    cx, cy = box["x"] + box["width"] / 2, box["y"] + min(box["height"] / 2, 300)
    zoom = lambda: pg.inner_text("#iamap-zoom-readout").strip()  # noqa: E731
    z0 = zoom()
    pg.mouse.move(cx, cy)
    pg.mouse.wheel(0, 600)
    pg.wait_for_timeout(300)
    top = pg.evaluate("document.getElementById('ia-scroll').scrollTop")
    check(top > 0 and zoom() == z0, f"a plain wheel over the map scrolls the page (scrollTop {top}) and leaves the zoom alone ({z0} → {zoom()})")
    pg.evaluate("document.getElementById('ia-scroll').scrollTop = 0")
    pg.wait_for_timeout(100)
    pg.mouse.move(cx, cy)
    pg.keyboard.down("Control")
    pg.mouse.wheel(0, -300)
    pg.keyboard.up("Control")
    pg.wait_for_timeout(300)
    top = pg.evaluate("document.getElementById('ia-scroll').scrollTop")
    check(zoom() != z0 and top == 0, f"Ctrl + wheel (and a trackpad pinch, which sends it) zooms the map instead ({z0} → {zoom()}, scrollTop {top})")
    pg.set_viewport_size({"width": 1440, "height": 900})


def table_width(pg):
    print("6 · a scan list takes the width its filter bar does")
    for w in (1440, 1920):
        pg.set_viewport_size({"width": w, "height": 900})
        for view in ("ia", "logic", "tests"):
            pg.evaluate(f"setMetaView('flow'); pbSetUxView('{view}')")
            pg.wait_for_timeout(250)
            r = pg.evaluate("""() => { const t = document.querySelector('.pb-scan'), b = document.querySelector('.pb-fbar');
              if (!t || !b || !t.offsetParent) return null;
              const tr = t.getBoundingClientRect(), br = b.getBoundingClientRect();
              return { tr: tr.right, br: br.right, tl: tr.left, bl: br.left }; }""")
            if r is None:
                print(f"  – {view}: this project has no list here")
                continue
            check(abs(r["tr"] - r["br"]) <= 2 and abs(r["tl"] - r["bl"]) <= 2,
                  f"{w}px · {view}: the list ({r['tl']:.0f}–{r['tr']:.0f}) and its filter bar ({r['bl']:.0f}–{r['br']:.0f}) span the same width")
    pg.set_viewport_size({"width": 1440, "height": 900})


def summary(pg):
    print("4 · Project Summary")
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.evaluate("setMetaView('summary')")
    pg.wait_for_selector(".sum-sec")
    pg.wait_for_timeout(250)
    check(pg.evaluate("document.querySelectorAll('.sum-sec h2.sum-h2').length") == 1
          and pg.evaluate("document.querySelectorAll('.sum-sec h3.sum-h3').length") == 2,
          "Overview: the page number is an h2 and its two sections are h3s")
    obj = pg.evaluate("""() => { const l = document.querySelector('.sum-lead'); if (!l) return null;
      const ps = l.querySelectorAll(':scope > p'), c = s => getComputedStyle(s);
      return { rt: l.classList.contains('pb-rt'), mark: !!l.querySelector('mark.pb-hl'), strong: !!l.querySelector('strong'), num: !!l.querySelector('b.pb-num'),
               paras: ps.length, lead: parseFloat(c(ps[0]).fontSize), rest: parseFloat(c(ps[1]).fontSize), ws: c(l).whiteSpace,
               measure: document.querySelector('.sum-sec').getBoundingClientRect().width }; }""")
    check(obj and obj["rt"] and obj["paras"] == 2, f"the objective is rich text with its paragraphs ({obj and obj['paras']})")
    check(obj and obj["mark"] and obj["strong"] and obj["num"], "…its ==highlight==, **bold** and number are marked")
    check(obj and obj["lead"] > obj["rest"], f"…and the first paragraph is the lead, set larger ({obj and obj['lead']}px vs {obj and obj['rest']}px)")
    check(obj and obj["ws"] == "normal", f"…and white-space is handled by the rich text ({obj and obj['ws']})")
    check(obj and obj["measure"] <= 761, f"the text is held to a 760px measure ({obj and obj['measure']:.0f}px)")

    pr = pg.evaluate("""() => [...document.querySelectorAll('ol.sum-principles > li')].map(li => ({
        n: li.querySelector('.sum-pn').textContent.trim(), t: li.querySelector('.sum-pt').textContent.trim(),
        w: parseInt(getComputedStyle(li.querySelector('.sum-pt')).fontWeight, 10), d: li.querySelector('.sum-pd').textContent.trim(),
        code: !!li.querySelector('.sum-pd code'), card: getComputedStyle(li).borderTopLeftRadius })) """)
    check([p["n"] for p in pr] == ["1", "2", "3"] and [p["t"] for p in pr] == ["First principle", "Second principle", "Third principle"],
          f"principles are a numbered list — number then title ({[(p['n'], p['t']) for p in pr]})")
    check(all(p["w"] >= 600 and p["d"] for p in pr), "…each with a bold title and a body")
    check(pr and pr[0]["code"], "…whose body takes inline marks (`code`)")
    check(pg.evaluate("document.querySelectorAll('.meta-principle, .meta-principle-num').length") == 0 and all(p["card"] == "0px" for p in pr),
          "…set off by hairlines, not stacked in cards")

    toc = pg.evaluate("""() => { const a = document.querySelector('.summary-toc'); if (!a) return null;
      return { shown: getComputedStyle(a).display !== 'none', items: a.querySelectorAll('.summary-toc-item').length,
               left: a.getBoundingClientRect().left, sec: document.querySelector('.sum-sec').getBoundingClientRect().right }; }""")
    check(toc and toc["shown"] and toc["items"] == 3, f"three headings earn a table of contents ({toc and toc['items']} entries)")
    check(toc and 0 <= toc["left"] - toc["sec"] <= 80, "…sitting beside the text, not stranded at the far edge")
    pg.set_viewport_size({"width": 1000, "height": 800})
    pg.wait_for_timeout(120)
    check(pg.evaluate("getComputedStyle(document.querySelector('.summary-toc')).display") == "none", "below 1100px the contents are hidden")
    pg.set_viewport_size({"width": 1440, "height": 900})

    pg.evaluate("setSummarySubTab('insights')")
    pg.wait_for_timeout(200)
    ins = pg.evaluate("""() => ({ h3: document.querySelectorAll('.sum-sec h3.sum-h3').length, leads: document.querySelectorAll('.sum-lead').length,
      bullets: document.querySelectorAll('.sum-sec .pb-rt ul li').length, num: !!document.querySelector('.sum-sec li b.pb-num'),
      toc: document.querySelectorAll('.summary-toc-item').length }) """)
    check(ins["h3"] == 3 and ins["toc"] == 4, f"Insights: three sections, four contents entries ({ins['h3']}, {ins['toc']})")
    check(ins["leads"] == 1, f"…and one lead, the first section's ({ins['leads']})")
    check(ins["bullets"] == 3 and ins["num"], f"…its '·' lines are a real list, with the number marked ({ins['bullets']} items)")


def main():
    tmp = tempfile.mkdtemp()
    try:
        reg_path, ctx = build_project(tmp)
        out = os.path.join(tmp, "p.html")
        render.render_file(reg_path, os.path.join(TPL, "prototype.html"), out)
        with sync_playwright() as pw:
            try:
                br = pw.chromium.launch()
            except Exception as e:  # noqa: BLE001
                print(f"SKIP: could not launch Chromium ({e})")
                sys.exit(2)
            c = br.new_context(viewport={"width": 1440, "height": 900})
            c.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("file:", "data:"))
                    else r.fulfill(status=200, body="", content_type="text/plain"))
            pg = c.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("file://" + out, wait_until="domcontentloaded")
            pg.wait_for_selector(".pb-product", state="attached", timeout=10000)
            pg.add_style_tag(content=FREEZE)
            pg.wait_for_timeout(300)
            print("1 · one column")
            vertical(pg, 1440, 900, "1440px")
            vertical(pg, 430, 932, "430px")
            filtering(pg, ctx)
            rows(pg, ctx)
            dimming(pg)
            wheel(pg)
            table_width(pg)
            summary(pg)
            check(errs == [], f"no page errors ({errs[:2]})")
            br.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    if _fail:
        print(f"✗ {len(_fail)} ia-view failure(s):")
        for f in _fail:
            print(f"    - {f}")
        sys.exit(1)
    print("✓ ia-view clean.")


if __name__ == "__main__":
    main()
