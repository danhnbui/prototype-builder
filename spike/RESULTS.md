# Phase 0.5 spike results

```
────────────────────────────────────────────────────────────────────────────────────────────
PHASE 0.5 — TOKEN-VALIDATION SPIKE   (registry.json vs v0.4.0 monolith)
tokenizer: tiktoken / o200k_base   pass bar: ≥ 50% mean per-tweak core cut
────────────────────────────────────────────────────────────────────────────────────────────
tweak                  read·greps   |   mono  registry REALISTIC cut |    surg  careful   reemit
--------------------------------------------------------------------------------------------
① Resize a button      careful·4    |    372       135         63.7% |  -45.2%    63.7%    78.5%
② Change a token       surgical·1   |    130       117         10.0% |   10.0%    78.3%    87.9%
③ Add a field          careful·—    |    764       584         23.6% |  -24.8%    23.6%    67.8%
④ Adjust a layout      careful·—    |    390        80         79.5% |   45.6%    79.5%    87.3%
⑤ Reword copy          careful·2    |    147       117         20.4% |    7.1%    20.4%    69.8%
--------------------------------------------------------------------------------------------
MEAN CORE per-tweak cut         |    361       207         39.4% |   -1.4%    53.1%    78.3%
────────────────────────────────────────────────────────────────────────────────────────────
HEADLINE = realistic mixed read (surgical for unique targets, careful for ambiguous/structural):
   mean core per-tweak cut =  39.4%   →   FAIL ❌  (bar ≥ 50%)
   honest band: floor  -1.4% (monolith edited perfectly surgically)  … ceiling  53.1% (monolith always read by function)
   by type → structural/ambiguous (4 tweaks):  46.8%  |  unique-cosmetic (1 tweaks):  10.0%
   → registry WINS on structural/ambiguous edits (①③④); ~break-even-or-worse on unique cosmetic (②⑤).
     A real build session is structural-DOMINANT (add screens/components/fields/states), so the
     structural figure is the better single number for the bulk of the work.

SESSION MODEL (the real scaling lever): the BUILD working-set (1882 tok — tokens+screens+
component props; handoff metadata excluded, full file is 3187 tok) stays RESIDENT; each tweak
= warm patch (~31 tok). Monolith too big to stay resident → re-reads its slice cold
every tweak (~361 tok). Win scales with tweaks/session N:
   N=5  → registry   408 tok/tweak vs monolith 361  →  cut -13.0%   
   N=20 → registry   125 tok/tweak vs monolith 361  →  cut  65.3% ✅
   N=50 → registry    69 tok/tweak vs monolith 361  →  cut  80.9% ✅
   (a typical build session is dozens–hundreds of tweaks; isolated cold tweaks = the ~ 39.4% floor.)

FULL-LOOP (gate charged on both paths for trio tweaks → cancels; render tax on registry only):
   gate G_trio = 238 tok, charged on 2/5 tweaks (both paths)
   • Deterministic batched render (intended; generator does codegen, model ≈ free):
       N=3  render/tweak= 10.0 tok → full-loop cut  31.6%  (mono 456 vs reg 312)
       N=5  render/tweak=  6.0 tok → full-loop cut  32.5%  (mono 456 vs reg 308)
       N=10 render/tweak=  3.0 tok → full-loop cut  33.1%  (mono 456 vs reg 305)
   • Anti-pattern (model hand-emits HTML each render, C_render=4510 tok — the plan FORBIDS this):
       N=3  render/tweak=   1503 tok → full-loop cut -296.0%
       N=5  render/tweak=    902 tok → full-loop cut -164.1%
       N=10 render/tweak=    451 tok → full-loop cut -65.2%

GATE-SKIP upside (separate; if v0.4.0 always-gated): registry skips 3/5 gates = 143 tok/tweak saved on non-trio tweaks.
────────────────────────────────────────────────────────────────────────────────────────────
CAVEATS: tokenizer is a proxy for Anthropic's BPE; per-turn conversation/system overhead
(identical on both paths) compresses the real-world %, so the headline overstates the
whole-turn cut. The registry win is CONDITIONAL on (a) deterministic batched render and
(b) correct trio classification. See plan risk-flags #1–4 for Task 2.2.
────────────────────────────────────────────────────────────────────────────────────────────
```
