# Phase B — orchestrated implementation

> **Status: complete.** Every increment in this plan shipped in v2.0.0. It is kept as the
> record of how the work was partitioned, not as outstanding work. What it produced, measured
> against the project it was planned from: [remediation-validation.md](remediation-validation.md).

The build plan derived from `remediation-decisions.md` (D-01 … D-28). Phase A is closed; nothing
here re-opens a decision. If an agent finds a decision wrong, it **stops and reports** — it does not
re-decide.

**Roles.** Sonnet sub-agents implement against a Fable-authored brief and return patches. The
coordinator (Fable) applies them **serially**, runs the wave gate, and stops the run on any red.
Mechanism: the Workflow tool. The human merges every PR.

---

## 1 · The partitioning constraint

Waves are partitioned by **file ownership, not by topic**. Two agents must never hold the same file.

Three files force the shape of the whole plan:

| File | Why it is exclusive |
|---|---|
| `pb/template/prototype.html` | 6,223 lines, one owner only. Carries the load-bearing anchor at :2536 — `    const PB_DATA = adaptRegistryToPBData(PB_REGISTRY);`, **four leading spaces**. Reindent it and every render dies. No formatter may touch this file. |
| `pb/template/runtime.js` | Lines 10–165 are **physically duplicated** into `prototype.html` at 2379–2534. Only 3 canary strings guard the copy. A helper added to one is *not* in the other. |
| `pb/tools/lint_registry.py` | Four separate decisions land in it (D-10, D-11, D-22, D-26). One owner, one pass. |

---

## 2 · Increments → PRs

**D-02: one PR per increment**, each on its own `release/vX.Y.Z` branch, human-merged. Eight
increments. Schema stays at **10** until I8, which takes **11** (D-01).

| # | Increment | Decisions | Owns | Schema |
|---|---|---|---|---|
| **I1** | Housekeeping | — | `.gitignore`, `docs/remediation-*.md` | 10 |
| **I2** | Lint + slice | D-10, D-11, D-17, D-22, D-26·1 | `lint_registry.py`, `slice.py` | 10 |
| **I3** | Role-aware sandbox (tool half) | D-27 (1–3, 5–7) | `test_run.py`, `commands/test.md` | 10 |
| **I4** | Logic extraction | D-08, D-09, D-12, D-16 (nav) | `logic_extract.py`, `logic_check.py` (both new) | 10 |
| **I5** | Render + DS site | D-13 (hook), D-20, D-26·2·3·4 | `render.py`, `design-system.html`, `render_budget.py` | 10 |
| **I6** | The shell | D-13, D-14, D-16, D-24, D-25, D-27·1 | `prototype.html` | 10 |
| **I7** | Process fixes | D-16, D-21, D-22 | `commands/*.md`, `decisions.template.md` | 10 |
| **I8** | Schema 11 | D-01, D-16, D-28 | `0009_*.py`, `manifest.py`, `runtime.js`, `prototype.html` | **11** |

---

## 3 · Waves

Five waves. A wave gate must be green before the next starts.

### Wave 1 — four agents, fully parallel (I2, I3, I4)

| Agent | Owns | Delivers |
|---|---|---|
| **W1-a** | `pb/tools/lint_registry.py` + its tests | D-10 · `orgId` may reference a **local** component; `R-NEST` ERRORs only on an unresolvable id. `R-NEST-HINT` becomes **whole-token** equality, not substring. <br> D-11 · `--sync-elements`, **append-only**: add a `screens[].elements[]` entry per composed `orgId` not yet declared (label `"(auto) composed <id>"`, `state:"default"`); **never** edit or remove an existing entry; report declared-but-not-composed instead of deleting. Not on any write path. <br> D-22 · `--report`: histogram by code, top items by finding count, size/shape metrics, ranked "fix first". **Always exit 0.** Thresholds from an optional `memory/doctor.json`, defaults built in. <br> D-26·1 · warn when a prop `default` is a collection literal inside a string (`'[]'`, `'[{…}]'`), or an `array`/`object`-typed prop carries a string default. |
| **W1-b** | `pb/tools/slice.py`, `tests/slice_cli.py` | D-17 · `get` gains `--no-prose` (drop `logicNotes`, `uiLogic`, `anatomy`, `spec`, `usage`) and `--fields a,b,c`. **Not** `--body`. |
| **W1-c** | `pb/tools/test_run.py`, `pb/commands/test.md` | D-27 · honour `test.roles` (per-role runs, default from the existing `_default_role_id`) and `test.seed`; `--server` becomes a **modifier** not a mode; `--roles` runs scenarios and gains `present`/`absent` (**presence, not visibility**); **exit 3 = cannot run**; correct the three false claims at `test.md:13,14,17`. |
| **W1-d** | `pb/tools/logic_extract.py`, `pb/tools/logic_check.py` (both new), FP corpus test | D-12 · separate tools sharing lint's `Finding`/`_report`/exit-code contract. <br> D-08 · every check is **Kind A** (derived vs derived → ERROR, or WARN when runtime-guarded) or **Kind B** (declared vs observed → prints both sides + the author's `why`; **absence of a declaration is never a finding**). No check gates on a count, ratio or baseline hash. `--explain <CODE>`. <br> D-09 · seam **cross-check** (consumed-but-never-produced, no baseline); `:has()` R1/R2 as checks, R3 as a note, R4 never; `--freeze` opt-in only. <br> D-16 · derive the nav graph (sidebar literal + `data-nav`/`data-go`/`setProtoScreen`, `activeScreenId` as fallback parent) and overlays. |

**Gate:** `for f in tests/*.py; do python3 "$f"; done` → 18 pass / 3 exit-2 skips / 0 fail.
**Plus:** the FP corpus green, and `lint --report` run against `.reference/atlas/prototype` reproducing the Phase A histogram (0 errors, 96 warnings, 4 codes).

### Wave 2 — two agents (I5)

| Agent | Owns | Delivers |
|---|---|---|
| **W2-a** | `pb/tools/render.py`, `tests/render_budget.py` | D-13 · `load_logic()` mirroring `load_specs`; inline the derived graph. <br> D-26·3 · `_default_props` coerces: parse an `array`/`object` default as data, fall back to `[]`/`{}`. <br> D-20 · budget `load_specs + build_html` together, at real scale via the promoted fixture. |
| **W2-b** | `pb/template/design-system.html` | D-26·3 · a failing demo renders a card naming the **component and the prop**, not `render error: x.map is not a function`. <br> D-26·4 · paint the demo stage from the **project's** surface token, not the site's chrome token. <br> **Deferred, do not build:** lazy mounting, the filter bar, scope→level subheadings, the `MAX_CELLS` relabel. |

**Depends on:** W1-d (the extractor W2-a calls).
**Gate:** full sweep + `r5_ds_site.py` green + the real project renders on both routes with 0 mangled literals.

### Wave 3 — ONE agent, serial (I6)

**W3-a owns `pb/template/prototype.html` alone.** Four passes, in this order, each grep-verifying the
anchor before handing on:

1. **D-14 + D-13 + D-16** — UX Design gains `meta-subtab` navigation: **Information Architecture ·
   User Flow · Logic**. User Flow is the existing canvas + stories split, unchanged. Logic is
   Rules | Ripple. IA is the site map (derived layers) + JTBD job rows + coverage by screen.
   Project Summary keeps its **four** sub-tabs. A `TAB_INFO` entry is required or the `?` is dead.
2. **D-24** — Data tab: search rendered **once** into `.erd-toolbar`'s empty right slot, repainting
   only the table host (**not** focus restoration — it breaks IME); wire the existing
   `pbSortTable(th)` (:2513) to the `<th>`s; clamp the notes cell with an expand control; `origin`
   as a **row tint + legend**, not a fifth column.
3. **D-25** — the `/` → `/design-system` link. **Must not** carry `.meta-tab`. **Protocol-gated.**
4. **D-27·1** — `pbResetSandbox()` clears `state.activeRole`.

**Gate:** `e2e_smoke.py` green (`.meta-tab` count still exactly 4), anchor verified byte-for-byte,
console clean on all four tabs against the real project.

### Wave 4 — two agents (I7)

| Agent | Owns | Delivers |
|---|---|---|
| **W4-a** | `pb/commands/{build,clarify,handoff-close,init,plan,check-drift}.md`, `pb/template/decisions.template.md` | D-21 · `build.md` §3 greps `memory/decisions*.md` for the touched slice **before** appending an override; `clarify.md` the same before a trade-off; both write a consistent entry shape; **widen the hand-off glob to `memory/decisions*.md` at `handoff-close.md:18,54,72` in this same commit**. <br> D-16 · `init.md` gains the JTBD intake (three fields + one sentence per layer, with a worked example); `plan.md` maps jobs → screens; `build.md` warns on a screen no job points at. <br> D-22 · `check-drift.md` surfaces `lint --report`. |
| **W4-b** | rotation mode on an existing tool | D-21·4 · size-triggered (**500 KB** default, never calendar), whole entries only, back up first, assert the round trip is lossless, abort on mismatch. |

**Gate:** full sweep + a rotation round-trip proven lossless on a copy of the real log (818 KB, 187 entries).

### Wave 5 — one agent, serial (I8)

**W5-a owns `pb/migrations/0009_*.py`, `manifest.py`, `runtime.js`, and `prototype.html`'s duplicated
runtime block.**

- D-28 contract · sidecar `logic/{components,screens}/<id>.json` via `logicSrc`. Derived and rewritten
  each run: `seam`, `handlers`, `disclosure`. Hand-authored only: `writes[]` and `affordances[].why`.
- D-28 verbs · ship **`data-machine`/`data-step`** and **`data-preserve`**. **Do not build**
  `data-save`, `data-group`/`data-panel` (dropped) or `data-bind` (deferred).
- D-28 runtime · `registry.runtime[]` — real module files inlined before render bodies, plus declared
  CDN dependencies.
- D-16 · the `ia` slice: `jobs[]` (`id`, `roles[]`, `when`, `want`, `so`, `priority`, `screens[]`,
  `source?`, `story?`) and `layers[]` (`depth`, `name`, `purpose`). Nothing else authored.
- D-28 migration · **copies** prose into `notes[]` with a `source` pointer. `logicNotes` and `uiLogic`
  are **not deleted, not moved, not one character rewritten**.

**Gate:** `/pb:update-version --apply` then `--rollback` on a **copy** of the real project, diffed to
**byte-equality**. Plus the full sweep. A helper added to `runtime.js` must be verified present in
`prototype.html`'s duplicated block — the 3 canary strings are not sufficient.

---

## 4 · The agent brief template

Every Sonnet brief carries these seven sections. Anything missing means the brief is not ready.

```
GOAL         one sentence: the decision id(s) and the observable outcome
FILES        exactly the files this agent owns. Touching any other file fails the patch.
DECISIONS    the verbatim decision text from remediation-decisions.md — not a paraphrase
MEASURED     the Phase A numbers this change is sized against
DO NOT       the alternatives Phase A rejected, named, so they are not re-invented
ACCEPTANCE   the exact commands that must pass, with expected output
RETURN       a patch, plus a one-paragraph note on anything that did not match the brief
```

**Standing rules in every brief:**
- Phase A decisions are closed. Found a problem with one? **Stop and report.** Do not re-decide.
- `AGENTS.md` governs: additive schema only, every rename ships a compat alias, `render.py` stays
  deterministic, tests green before the PR.
- Never remove or repurpose a field in place — add, then deprecate (this is why D-19 deprecates
  `staleness` rather than deleting it).
- Apply **D-23** to anything new: a tool is justified only if it runs in the deterministic render path,
  needs a regression test a prompt cannot have, or is arithmetic over a large set. Otherwise it belongs
  in a command prompt or as a flag.

---

## 5 · Verification

**Every increment:** the named tests, then the full sweep —
`for f in tests/*.py; do python3 "$f"; done`. Expect **18 pass / 3 exit 2** (`e2e_smoke`,
`test_inspect`, `test_sandbox` — clean Playwright skips, not failures).

**Visual, before/after on one registry through two template trees:**

```
git worktree add ../pb-before <base-sha>
python3 pb/tools/serve.py .reference/atlas/prototype/registry.json --port 8200 --no-open
python3 ../pb-before/pb/tools/serve.py .reference/atlas/prototype/registry.json --port 8300 --no-open
```

`serve.py` resolves shells relative to its own `__file__`, so the before-tree renders the *same*
registry through the *old* templates. Any diff is purely the change.

**Schema increments:** `--apply` then `--rollback` on a copy of the real project, diffed to byte-equality.

---

## 6 · Test-break register

| Test | Hazard | Mitigation |
|---|---|---|
| `e2e_smoke.py:124,191` | asserts `.meta-tab` count `== 4` | the DS link uses its own class; Logic and IA are **sub**-tabs of UX Design |
| `r5_ds_site.py:76-81` | `State(...)` 6 positional args | add no `State` parameter; derive the DS out path |
| `r5_ds_site.py:111-117` | measures `.stage`/`.cell` at load | lazy mounting is **deferred** (D-26), so this is untouched |
| `r5_ds_site.py:66-72` | 3-canary runtime drift guard | strengthen to a full-block compare in W5 |
| `render_budget.py:17` | `BUDGET_MS = 100` on `build_html` | keep it; add a separate pipeline budget (D-20) |
| `skill_refs_lint.py:25-30` | hardcoded `SKILL_VOCAB` | keep those 14 names out of new command prose |
| `tool_cli.py:43-50` | guards the registry-positional CLI form | extend additively per tool |
| `slice_cli.py` | guards `get`/`set`/`list` | `--no-prose`/`--fields` are additive; idempotent `set` must stay byte-stable |

---

## 7 · Risks

1. **`prototype.html:2536`** — four leading spaces. Reindent and every render dies. One agent only;
   grep-verify after every edit. This is why Wave 3 is serial.
2. **`runtime.js` is duplicated into `prototype.html`** (10–165 ≡ 2379–2534), guarded by 3 canaries.
   W5 must verify both copies, not trust the canaries.
3. **Rotation + the hand-off glob** — if D-21·4 ships without the glob widening in the *same commit*,
   the first rotation silently drops history from every hand-off.
4. **Scope creep into `build_ds`** — measured at 51 ms; it is not the bottleneck. The client-side
   ~2,400 render calls are, and lazy mounting is deferred.
5. **The IA presentation is explicitly unfinished** (D-15). The data contract is settled; the visual
   design is a Phase B UI pass, not a Phase A re-open.

---

## 8 · Close-out

- **Erase `.reference/`** when the remediation ends. It is a temporary read-only clone of internal
  company data, gitignored, never committed.
- Promote `scratchpad/scale_fixture.py` → `tests/scale_fixture.py` (gitignored output) in W2.
- Delete the scratchpad W2 build (`scratchpad/w2/`) — it is a throwaway shell fork.
- The real project should reinstall once v1.11.1 is released and drop its hand-patched plugin cache;
  its own G0 gate will confirm.
