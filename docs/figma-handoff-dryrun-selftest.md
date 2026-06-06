# Dry-run trace — `/pb:build-figma-handoff` against `selftest/`

*Non-destructive. Zero Figma writes. June 2026.*

**What this is.** A hand-executed `--dry-run` of `/pb:build-figma-handoff`, run against the real `selftest/registry.json` ("Feedback widget", DS = `calm-ds`). The slash command can't be invoked from this environment, so its documented gate logic (G-FP0→G-FP5) and the `figma-use` skill's rituals were traced by hand. A `--dry-run` "runs all gates + shows the plan, skips the actual Figma writes" — that's exactly what's below.

**Fixture facts.** 3 components (`star-rating`, `comment-box`, `primary-button`, each with a `value` property axis), 2 screens (`feedback-form`, `thank-you`), 3 declared tokens (`brand`, `brand-strong`, `danger`). No `figma-transfer.json` and no `figma-tokens.json` exist yet → this is a first-ever push.

---

## Gate-by-gate result

| Gate | Result | Detail |
|---|---|---|
| **G-FP0** Scope | needs input | `--scope` absent → would prompt. Traced as `both`. |
| **G-FP1.1** Figma reachable | ⏳ needs Figma | `whoami` — not called (won't touch your Figma account unprompted). Must pass on a live run. |
| **G-FP1.2** Registry loaded | ✅ PASS | parses; `components[]`=3, `screens[]`=2 (non-empty). |
| **G-FP1.3** Transfer contract | would seed | no `figma-transfer.json` → would prompt for the Figma file URL and seed it; `dsMatch.library = calm-ds` (from the DS Lock). |
| **G-FP1.4** Target page/frame | ⏳ needs input | `target.pageId` null → would call `get_metadata`, ask which page, create a root frame. |
| **G-FP1.5** No-op check | ✅ proceeds | no `lastPushedHash` → not a no-op. |
| **G-FP2** Identity audit | ⚠️ **STOP** | 3 `new` components, 2 `new` screens, 3 `axis-change` (the `value` axis is new on each). **Batch guard trips: 2 new screens > 1 → HARD FAIL without `--batch`.** |
| **G-FP3** Token resolution | would pause | unique tokens in scope: `--brand`, `--radius-small`, `--font-heading`. None mapped (fresh) → would propose via `search_design_system` against `calm-ds`. |
| **G-FP4** DS component match | would pause | would propose `calm-ds` matches for the 3 components; NO-MATCH → create-local with auto-layout + variants. |
| **G-FP5** Push plan | dry-run STOP | prints the plan below, writes nothing, updates no contracts. |

So with **default flags this push stops twice**: the batch guard (G-FP2) and, of course, the dry-run halt (G-FP5). Re-running would need `--batch`. That's correct, intended behavior — and the kind of thing a dry-run exists to surface.

---

## The push plan (what a real run *would* write, with `--batch`)

- **Target:** library `calm-ds` · page «you choose» · root frame «created».
- **Tokens (3):** bind `--brand`, `--radius-small`, `--font-heading` to `calm-ds` variables; any NO-MATCH → local var in the `Prototype tokens` collection (never a raw value).
- **Components (3):** each either instance-swapped to a `calm-ds` match or created-local **with auto-layout**, built as a **ComponentSet** with `value=0` / `value=4` variants via the `prop=value` naming ritual.
- **Screens (2):** one auto-layout frame each; children laid out per `screen.layout`:
  - `feedback-form` → `VERTICAL`, `itemSpacing 18`, `padding 32`; `rating`/`comment`/`submit` inserted as **instances** of the 3 components; `submit` sizing `width:100%` → fill-H.
  - `thank-you` → `VERTICAL`, `itemSpacing 12`, `padding 48`; `check`/`msg` as local text.
- **Auto-layout policy (R3):** every frame auto-layout, hug-V/fill-H default, **0 absolute children**.

**Good news on R3:** the data supports it cleanly. `screen.layout {type:stack, gap, padding}` maps one-to-one onto auto-layout, and the component→element instance wiring is intact. No restructuring needed for layout.

---

## Read-back self-check — predicted assertions

What the skill's post-write self-check would assert (and what would flag):

- ✅ both frames `layoutMode = VERTICAL` (≠ NONE), 0 absolute children — satisfiable.
- ⚠️ **0 raw px — FLAGS.** `screen.layout` gaps/paddings (`18 / 32 / 12 / 48`) are raw numbers, not token refs. Strict mode would require mapping them to the `calm-ds` spacing scale.
- ✅ each multi-state component resolved into a ComponentSet with the `value` axis — satisfiable (but see finding #3).
- n/a images / icons — none in this fixture (no `<img>`, the `✓` is a text glyph).
- ✅ `rating`/`comment`/`submit` as instances, not local copies — satisfiable.

---

## Findings (what the dry-run surfaced)

| # | Severity | Finding | Where |
|---|---|---|---|
| 1 | expected | Batch guard halts the push (2 new screens > 1) — re-run with `--batch` | G-FP2 |
| 2 | **real gap** | Screen spacing is **raw px** (`gap 18/12`, `padding 32/48`), not token refs → violates "Tokens only" (principle #1) **and** the skill's no-raw-px ritual | `screens[].layout` |
| 3 | **data smell** | `properties[].value {0,4}` is demo state modeled as a **variant axis** → would generate spurious `value=0`/`value=4` variants on all 3 components | `components[].properties` |
| 4 | expected | Fresh `figma-tokens.json` / `figma-transfer.json` → all 3 tokens unmapped; needs a live `calm-ds` query to resolve | G-FP3 |
| 5 | **carryover** | `dsMatch` field still inconsistent: command reads `figmaComponentId`, template seeds `componentId` → write-back (Step 7) won't round-trip | command vs template |
| 6 | minor | `tokens{}` defines `brand-strong` + `danger` but neither is referenced in scope; `--radius-small`/`--font-heading` are referenced but not in `tokens{}` (DS foundations) | `tokens` vs refs |

---

## To finish the test (needs you / live Figma)

The registry-driven half is done and non-destructive. The remaining half needs a live connection and is yours to greenlight:

1. **Connect the Figma MCP** + point at a throwaway Figma file → I can run the real read-only gate calls (`whoami`, `get_metadata`, the `search_design_system` proposals for tokens + components) and show the *actual* match results.
2. Then a real `--dry-run --batch` confirms the full plan with live IDs — still zero writes.
3. Only after you approve G-FP5 would anything be written to Figma.

Recommend fixing findings **#2, #3, #5** in the fixture/contracts before any live push, since they'd otherwise propagate into Figma.
