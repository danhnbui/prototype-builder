#!/usr/bin/env python3
"""
spike/measure.py — Phase 0.5 token-validation spike (the abort gate).

Proves (or refutes) the v1.1.1 premise: editing a compact registry.json + batched
deterministic render is materially cheaper, in MODEL tokens, than editing the
v0.4.0 single-file HTML monolith — across 5 representative tweaks.

HONESTY GUARDS baked in:
  * Monolith WRITE is modeled as a real Edit-tool diff (old+new string), NOT a
    full-function re-emit. (Re-emit is reported separately as a pessimistic bound.)
  * Monolith READ is reported under TWO assumptions — "surgical" (minimal window,
    best case for the monolith → hardest test for registry; used for the HEADLINE)
    and "careful" (reads the whole function).
  * The drift/stack/DS GATE is charged IDENTICALLY on both paths for trio tweaks in
    the headline full-loop, so it cancels — the registry can't win on gate-skip alone.
    Gate-skip is reported separately as upside.
  * The batched RENDER is modeled both as intended (deterministic generator ≈ free
    model tokens) and as the anti-pattern (model hand-emits HTML — the "1.8x worse" trap).

Run:  python3 spike/measure.py        (uses tiktoken if available, else a labeled heuristic)
Out:  prints a table + writes spike/RESULTS.md
"""
import json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- tokenizer
def get_counter():
    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken / o200k_base", False
    except Exception:
        return (lambda s: round(len(s) / 4)), "HEURISTIC len/4 (tiktoken absent)", True

count, TOKENIZER, HEURISTIC = get_counter()
PASS_BAR = 0.55 if HEURISTIC else 0.50  # raise the bar when using the inferior heuristic

# ---------------------------------------------------------------- artifacts
mono = open(os.path.join(HERE, "monolith.html"), encoding="utf-8").read()
reg  = json.load(open(os.path.join(HERE, "registry.json"), encoding="utf-8"))

def region(name):
    """Text of a /* ====== REGION: name ====== */ block in monolith.html."""
    m = re.search(r"/\* ====== REGION: " + re.escape(name) + r" ====== \*/(.*?)(?=/\* ====== REGION:|</script>)", mono, re.S)
    return m.group(1).strip() if m else ""

def root_block():
    m = re.search(r"(:root \{.*?\n    \})", mono, re.S)
    return m.group(1) if m else ""

def jd(o):       return json.dumps(o, indent=2, ensure_ascii=False)
def comp(cid):   return next(c for c in reg["components"] if c["id"] == cid)
def screen(sid): return next(s for s in reg["screens"] if s["id"] == sid)
def elem(sid, eid): return next(e for e in screen(sid)["elements"] if e["id"] == eid)

# ---------------------------------------------------------------- gate blob (realistic)
# What the drift/stack/DS gate must READ (constitution Principles + DS rules excerpt)
# and EMIT (a per-principle verdict) on a trio-touching write. Charged identically on
# both paths in the headline full-loop, so it cancels.
G_TRIO_BLOB = """Read constitution.md → ## Principles:
  1. Error states show BOTH a danger border AND error text — never border alone.
  2. One primary action per screen; secondary actions use secondary/ghost.
  3. Every interactive element has a visible focus state; outline:none alone is forbidden.
  4. Touch/keyboard users get a non-hover affordance for every interactive element.
  5. All color/space/radius/shadow come from tokens — no raw hex or arbitrary px.
Read design-system rules (relevant slice):
  - Use --space-1..16 only; --space-3 control padding, --space-4 card padding.
  - Control radius --radius-md (8px); card radius --radius-lg (12px); never mix radii.
  - Elevation from --shadow-sm/md/lg; inline box-shadow forbidden.
  - Form inputs use the canonical Input; custom inputs go to local-components/ with justification.
Verdict: proposed write adds a tel field reusing text-input (token-bound, focus state intact,
no new primary). Checked principles 1-5 + DS rules — no contradiction. Proceed."""
G_TRIO = count(G_TRIO_BLOB)

# ---------------------------------------------------------------- render costs (MODEL tokens)
# Intended: a deterministic generator turns registry.json -> prototype.html. The MODEL only
# invokes it and reads a one-line confirmation. Near-free in model tokens.
C_RENDER_DETERMINISTIC = count("/pb-build --render\n→ rendered prototype.html: 1 screen, 2 components, 17 tokens · 4.2 KB · ok")
# Anti-pattern (the plan forbids this): the MODEL hand-emits the whole HTML each render.
C_RENDER_HANDWRITTEN = count(mono)

# Diff-framing overhead the model emits around any Edit (cancels; included for realism).
F = count("Use the Edit tool on ./prototype/... old_string / new_string below; keep adjacent lines for a unique match.\n")

# ---------------------------------------------------------------- the 5 tweaks
# Each: monolith read (surgical | careful), monolith write (fair Edit-diff | pessimistic re-emit),
# registry read (the touched slice), registry write (the JSON patch), trio?
def wr(*parts): return "\n".join(parts)  # an Edit payload = old_string + new_string

screen_fn   = region("renderScreenSignIn")
button_fn   = region("renderCmpButton")
input_fn    = region("renderCmpTextInput")
organisms   = region("PB_DATA.handoff.organisms")
screens_reg = region("PB_DATA.handoff.screens")
root        = root_block()
# FAIRNESS: to edit ONE screen the monolith greps to just that screen's literal, NOT all 3.
_m = re.search(r"\{\s*id:'sign-in'.*?logicNotes:\[.*?\]\s*\},", screens_reg, re.S)
signin_literal = _m.group(0) if _m else screens_reg

# `realistic` = the read assumption a competent grep+Edit agent actually hits on the REAL
# (large, growing) monolith: "surgical" when the edit target is a UNIQUE string (grep lands
# on it, read ~3 lines), "careful" when the target is AMBIGUOUS or the edit is STRUCTURAL
# (must read the whole function/region to edit safely). This is the honest headline.
TWEAKS = [
  dict(
    name="① Resize a button", trio=False, realistic="careful",   # size:'md' recurs at every call site → must locate
    mono_read_surgical="          ${renderCmpButton({ label:'Sign in', variant:'primary', size:'md', fullWidth:true })}",
    mono_read_careful=screen_fn,
    mono_write_fair=wr("OLD: renderCmpButton({ label:'Sign in', variant:'primary', size:'md', fullWidth:true })",
                       "NEW: renderCmpButton({ label:'Sign in', variant:'primary', size:'lg', fullWidth:true })"),
    mono_write_pess=screen_fn,
    reg_read=jd(elem("sign-in", "submit")),
    reg_write='patch screens[sign-in].elements[submit]: {"props":{"size":"lg"},"sizing":{"height":"48px","width":"100%"}}',
  ),
  dict(
    name="② Change a token", trio=False, realistic="surgical",   # `--brand:` is unique → grep lands
    mono_read_surgical="      --brand:                  #1c4ed8;   /* primary accent  — change me */\n"
                       "      --brand-soft:             #eef2ff;   /* soft accent bg  — change me */\n"
                       "      --brand-strong:           #1e3aa3;   /* hover / pressed — change me */",
    mono_read_careful=root,
    mono_write_fair=wr("OLD: --brand:                  #1c4ed8;   /* primary accent  — change me */",
                       "NEW: --brand:                  #2563eb;   /* primary accent  — change me */"),
    mono_write_pess=root,
    reg_read=jd({"brand": reg["tokens"]["brand"], "brand-soft": reg["tokens"]["brand-soft"], "brand-strong": reg["tokens"]["brand-strong"]}),
    reg_write='patch tokens.brand: {"value":"#2563eb","kind":"color"}',
  ),
  dict(
    name="③ Add a field", trio=True, realistic="careful",        # structural → read the screen fn
    mono_read_surgical=screen_fn,                          # need the screen fn to insert a field
    mono_read_careful=screen_fn + "\n" + signin_literal,   # + ONLY the sign-in screen's PB_DATA entry (grep-scoped)
    mono_write_fair=wr(
      "OLD: ${renderCmpTextInput({ label:'Password', type:'password', placeholder:'••••••••' })}",
      "NEW: ${renderCmpTextInput({ label:'Password', type:'password', placeholder:'••••••••' })}",
      "     ${renderCmpTextInput({ label:'Phone', type:'tel', placeholder:'+1 555 000 1234' })}",
      "PLUS new element in PB_DATA.handoff.screens[sign-in].elements:",
      "{ id:'phone', label:'Phone', orgId:'text-input', tokens:['--pg-radius-small','--border-strong'],",
      "  sizing:{ height:'44px' }, state:'default', uiLogic:'Optional. E.164 format.' }"),
    mono_write_pess=screen_fn + "\n" + screens_reg,
    reg_read=jd(screen("sign-in")),
    reg_write='append to screens[sign-in].elements: '
              '{"id":"phone","label":"Phone","orgId":"text-input","tokens":["--pg-radius-small","--border-strong"],'
              '"sizing":{"height":"44px"},"state":"default","uiLogic":"Optional. E.164 format."}',
  ),
  dict(
    name="④ Adjust a layout", trio=True, realistic="careful",     # structural → read the section
    mono_read_surgical='        <section class="screen screen--signin"\n'
                       '                 style="max-width:380px;margin:0 auto;display:flex;flex-direction:column;gap:16px;\n'
                       '                        padding:32px;background:var(--pg-gray-0);border-radius:var(--pg-radius-medium);">',
    mono_read_careful=screen_fn,
    mono_write_fair=wr(
      'OLD: style="max-width:380px;margin:0 auto;display:flex;flex-direction:column;gap:16px;padding:32px;..."',
      'NEW: style="max-width:420px;margin:0 auto;display:flex;flex-direction:column;gap:20px;padding:28px;..."'),
    mono_write_pess=screen_fn,
    reg_read=jd(screen("sign-in")["layout"]),
    reg_write='patch screens[sign-in].layout: {"type":"stack","gap":20,"maxWidth":420,"padding":28}',
  ),
  dict(
    name="⑤ Reword copy", trio=False, realistic="surgical",       # the subtitle string is unique → grep lands
    mono_read_surgical='          <p class="screen__subtitle" style="margin:0;font-size:14px;color:var(--text-active-secondary);">\n'
                       '            Welcome back. Enter your details to continue.</p>',
    # careful = the TWO windows grep lands on (copy is duplicated: render fn + PB_DATA element) — NOT the whole fn
    mono_read_careful='          <p class="screen__subtitle" style="margin:0;font-size:14px;color:var(--text-active-secondary);">\n'
                      '            Welcome back. Enter your details to continue.</p>\n'
                      "          { id:'subtitle', label:'Welcome back. Enter your details to continue.', orgId:null,",
    mono_write_fair=wr("OLD #1 (render fn): Welcome back. Enter your details to continue.",
                       "NEW #1: Sign in to manage your listings and leads.",
                       "OLD #2 (PB_DATA):   label:'Welcome back. Enter your details to continue.'",
                       "NEW #2: label:'Sign in to manage your listings and leads.'"),
    mono_write_pess=screen_fn,
    reg_read=jd(elem("sign-in", "subtitle")),
    reg_write='patch screens[sign-in].elements[subtitle].label: "Sign in to manage your listings and leads."',
  ),
]

# ---------------------------------------------------------------- refinement A: measured recurrence
# Don't hand-classify surgical vs careful — GREP the real 3-screen monolith for each tweak's edit
# target and let the hit-count decide (1 hit → grep lands, surgical; >1 → must disambiguate, careful).
def grep_hits(pat): return len(re.findall(pat, mono))
GREP = {
  "① Resize a button": dict(pattern=r"size:'md'"),                                  # recurs at every button site
  "② Change a token":  dict(pattern=r"--brand: "),                                  # the definition line (unique)
  "③ Add a field":     dict(structural=True),                                       # insertion, not a find
  "④ Adjust a layout": dict(structural=True),                                       # insertion, not a find
  "⑤ Reword copy":     dict(pattern=r"Welcome back\. Enter your details to continue\."),  # unique string
}
for t in TWEAKS:
    g = GREP[t["name"]]
    if g.get("structural"):
        t["hits"] = "—"; t["realistic"] = "careful"
    else:
        h = grep_hits(g["pattern"]); t["hits"] = h
        t["realistic"] = "surgical" if h <= 1 else "careful"   # MEASURED, overrides the hand label

# ---------------------------------------------------------------- compute
rows = []
for t in TWEAKS:
    m_read_s = count(t["mono_read_surgical"]); m_read_c = count(t["mono_read_careful"])
    m_write_fair = count(t["mono_write_fair"]); m_write_pess = count(t["mono_write_pess"])
    r_read = count(t["reg_read"]); r_write = count(t["reg_write"])

    # core (read+write only, gate excluded, F cancels)
    mono_surgical = m_read_s + m_write_fair + F           # surgical read + fair write  (monolith's BEST case = floor)
    mono_careful  = m_read_c + m_write_fair + F           # careful read + fair write    (ceiling for registry win)
    mono_pess     = m_read_c + m_write_pess + F           # careful read + re-emit       (monolith's WORST case)
    mono_realistic = (mono_surgical if t["realistic"] == "surgical" else mono_careful)  # honest per-tweak headline
    regist        = r_read + r_write + F
    cut = lambda m: (m - regist) / m
    rows.append(dict(name=t["name"], trio=t["trio"], realistic=t["realistic"], hits=t["hits"],
                     m_read_s=m_read_s, m_read_c=m_read_c, m_write_fair=m_write_fair, m_write_pess=m_write_pess,
                     r_read=r_read, r_write=r_write,
                     mono_surgical=mono_surgical, mono_careful=mono_careful, mono_realistic=mono_realistic,
                     mono_pess=mono_pess, regist=regist,
                     cut_surgical=cut(mono_surgical), cut_careful=cut(mono_careful),
                     cut_realistic=cut(mono_realistic), cut_pess=cut(mono_pess)))

trio_n = sum(1 for t in TWEAKS if t["trio"]); n = len(TWEAKS)
# structural/ambiguous tweaks (read=careful) vs unique-cosmetic (read=surgical) — let the
# reader weight by their own build mix instead of trusting one blended mean.
structural = [r for r in rows if r["realistic"] == "careful"]
cosmetic   = [r for r in rows if r["realistic"] == "surgical"]
mean_struct   = statistics.mean(r["cut_realistic"] for r in structural)
mean_cosmetic = statistics.mean(r["cut_realistic"] for r in cosmetic)
mean_core_realistic = statistics.mean(r["cut_realistic"] for r in rows)   # HEADLINE
mean_core_surgical  = statistics.mean(r["cut_surgical"] for r in rows)    # floor (monolith best case)
mean_core_careful   = statistics.mean(r["cut_careful"] for r in rows)     # ceiling
mean_core_pess      = statistics.mean(r["cut_pess"] for r in rows)

mean_mono_realistic = statistics.mean(r["mono_realistic"] for r in rows)
mean_regist         = statistics.mean(r["regist"] for r in rows)
mean_r_write        = statistics.mean(r["r_write"] for r in rows)   # warm per-tweak patch cost

# SESSION / WORKING-SET MODEL — the honest scaling lever.
# The WHOLE registry is small enough to load ONCE and stay resident in context across the
# session; thereafter each tweak is just a warm patch (mean_r_write). The 168 KB monolith is
# too big to stay resident — every tweak re-greps + re-reads its slice (cold = mono_realistic).
# Win therefore scales with tweaks-per-session N (the one-time registry load amortizes away).
# Refinement B: only the BUILD working-set needs to stay resident during the edit loop — tokens +
# screens + each component's editable surface (props). The handoff redline metadata (anatomy/spec/
# usage) is loaded on demand by /handoff & /figma-push, NOT during build tweaks, so it doesn't
# belong in the resident set. (The monolith's per-tweak read excludes it too — fair on both sides.)
def build_view(r):
    lite = [{k: c[k] for k in ("id", "name", "renderFn", "meta", "codeLayout", "properties") if k in c}
            for c in r["components"]]
    return json.dumps({"tokens": r["tokens"], "components": lite, "screens": r["screens"]}, ensure_ascii=False)
REG_BUILD = count(build_view(reg))                                                       # resident working-set
REG_FULL  = count(open(os.path.join(HERE, "registry.json"), encoding="utf-8").read())    # whole file (incl. handoff)
def session_model(N):
    reg  = REG_BUILD / N + mean_r_write             # load the BUILD working-set once, then warm patches
    mono = mean_mono_realistic                       # cold slice read+write every tweak
    return (mono - reg) / mono, mono, reg

# full-loop: gate charged on BOTH paths for trio tweaks (cancels) + render tax on registry only.
def full_loop(c_render, N):
    gate_per_tweak = G_TRIO * trio_n / n
    mono = mean_mono_realistic + gate_per_tweak
    regi = mean_regist + gate_per_tweak + c_render / N
    return (mono - regi) / mono, mono, regi

# gate-skip upside (if v0.4.0 always-gated all tweaks but v1.1.1 gates only trio)
gate_skip_saving = G_TRIO * (n - trio_n) / n

# ---------------------------------------------------------------- render report
def pct(x): return f"{x*100:5.1f}%"
def bar(): return "─" * 92

lines = []
def P(s=""):
    lines.append(s); print(s)

P(bar())
P("PHASE 0.5 — TOKEN-VALIDATION SPIKE   (registry.json vs v0.4.0 monolith)")
P(f"tokenizer: {TOKENIZER}   pass bar: ≥ {int(PASS_BAR*100)}% mean per-tweak core cut")
if HEURISTIC:
    P("⚠  HEURISTIC MODE — install tiktoken for a real measurement; treat 50–55% as INCONCLUSIVE.")
P(bar())
P(f"{'tweak':22} {'read·greps':12} | {'mono':>6} {'registry':>9} {'REALISTIC cut':>13} | {'surg':>7} {'careful':>8} {'reemit':>8}")
P("-" * 92)
for r in rows:
    P(f"{r['name']:22} {(r['realistic']+'·'+str(r['hits'])):12} | "
      f"{r['mono_realistic']:>6} {r['regist']:>9} {pct(r['cut_realistic']):>13} | "
      f"{pct(r['cut_surgical']):>7} {pct(r['cut_careful']):>8} {pct(r['cut_pess']):>8}")
P("-" * 92)
P(f"{'MEAN CORE per-tweak cut':22}{'':9}| {mean_mono_realistic:>6.0f} {mean_regist:>9.0f} "
  f"{pct(mean_core_realistic):>13} | {pct(mean_core_surgical):>7} {pct(mean_core_careful):>8} {pct(mean_core_pess):>8}")
P(bar())

verdict = "PASS ✅" if mean_core_realistic >= PASS_BAR else "FAIL ❌"
P("HEADLINE = realistic mixed read (surgical for unique targets, careful for ambiguous/structural):")
P(f"   mean core per-tweak cut = {pct(mean_core_realistic)}   →   {verdict}  (bar ≥ {int(PASS_BAR*100)}%)")
P(f"   honest band: floor {pct(mean_core_surgical)} (monolith edited perfectly surgically)  "
  f"… ceiling {pct(mean_core_careful)} (monolith always read by function)")
P(f"   by type → structural/ambiguous ({len(structural)} tweaks): {pct(mean_struct)}  |  "
  f"unique-cosmetic ({len(cosmetic)} tweaks): {pct(mean_cosmetic)}")
P("   → registry WINS on structural/ambiguous edits (①③④); ~break-even-or-worse on unique cosmetic (②⑤).")
P("     A real build session is structural-DOMINANT (add screens/components/fields/states), so the")
P("     structural figure is the better single number for the bulk of the work.")
P("")
P(f"SESSION MODEL (the real scaling lever): the BUILD working-set ({REG_BUILD} tok — tokens+screens+")
P(f"component props; handoff metadata excluded, full file is {REG_FULL} tok) stays RESIDENT; each tweak")
P(f"= warm patch (~{mean_r_write:.0f} tok). Monolith too big to stay resident → re-reads its slice cold")
P(f"every tweak (~{mean_mono_realistic:.0f} tok). Win scales with tweaks/session N:")
sess_pass = None
for N in (5, 20, 50):
    c, mo, re_ = session_model(N)
    flag = "✅" if c >= PASS_BAR else "  "
    if N == 20: sess_pass = c
    P(f"   N={N:<2} → registry {re_:5.0f} tok/tweak vs monolith {mo:.0f}  →  cut {pct(c)} {flag}")
P(f"   (a typical build session is dozens–hundreds of tweaks; isolated cold tweaks = the ~{pct(mean_core_realistic)} floor.)")
P("")
P("FULL-LOOP (gate charged on both paths for trio tweaks → cancels; render tax on registry only):")
P(f"   gate G_trio = {G_TRIO} tok, charged on {trio_n}/{n} tweaks (both paths)")
P("   • Deterministic batched render (intended; generator does codegen, model ≈ free):")
for N in (3, 5, 10):
    c, mo, ri = full_loop(C_RENDER_DETERMINISTIC, N)
    P(f"       N={N:<2} render/tweak={C_RENDER_DETERMINISTIC/N:5.1f} tok → full-loop cut {pct(c)}  (mono {mo:.0f} vs reg {ri:.0f})")
P(f"   • Anti-pattern (model hand-emits HTML each render, C_render={C_RENDER_HANDWRITTEN} tok — the plan FORBIDS this):")
for N in (3, 5, 10):
    c, mo, ri = full_loop(C_RENDER_HANDWRITTEN, N)
    P(f"       N={N:<2} render/tweak={C_RENDER_HANDWRITTEN/N:7.0f} tok → full-loop cut {pct(c)}")
P("")
P(f"GATE-SKIP upside (separate; if v0.4.0 always-gated): registry skips {n-trio_n}/{n} gates "
  f"= {gate_skip_saving:.0f} tok/tweak saved on non-trio tweaks.")
P(bar())
P("CAVEATS: tokenizer is a proxy for Anthropic's BPE; per-turn conversation/system overhead")
P("(identical on both paths) compresses the real-world %, so the headline overstates the")
P("whole-turn cut. The registry win is CONDITIONAL on (a) deterministic batched render and")
P("(b) correct trio classification. See plan risk-flags #1–4 for Task 2.2.")
P(bar())

open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8").write(
    "# Phase 0.5 spike results\n\n```\n" + "\n".join(lines) + "\n```\n")
print("\nwrote spike/RESULTS.md")
