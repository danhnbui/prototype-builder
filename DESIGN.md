# DESIGN.md — why Product Builder is shaped this way

The standing rationale for pb's architecture. [CLAUDE.md](CLAUDE.md) says **what** the system is
and [AGENTS.md](AGENTS.md) says **how you must work on it**; this file says **why it is built this
way**, so a structural change is argued against the reasoning that produced the current shape
rather than against taste.

Read this before changing the render path, the registry contract, the tool surface, or the loop.
Point changes do not need it.

**Status:** v1.12.0 · schema 11 · last reviewed 2026-09-20
**History** lives in [docs/remediation-decisions.md](docs/remediation-decisions.md) (D-1…D-30) and
per-project `memory/decisions.md`. Those are append-only; this file is edited in place.

---

## Problem

Building a clickable, design-system-faithful prototype with an LLM has one dominant cost: **the
model re-emitting markup it already wrote.** The naive shape — a single `prototype.html` the model
hand-writes and hand-edits — prices every change against the size of the *file*, not the size of
the *change*. A colour tweak on a 4,000-line prototype costs a 4,000-line round trip, and the cost
grows as the prototype gets good.

It also leaves nothing downstream can consume. Markup is not a contract: a Figma hand-off, a dev
export, a test runner and a design-system site each need structured state, and none of them can get
it from HTML written for a browser.

## Constraints

These are the non-negotiables. Each one has a source, and together they are what make the design
non-obvious.

1. **Token economics decide the architecture.** Measured at the G0.5 spike (2026-06-05, real
   tiktoken): the registry approach is **~3–5× cheaper over a build session**, with a free
   deterministic render and clean deduped state. It is *not* "17× per tweak" — isolated cosmetic
   tweaks are roughly break-even. The win is in structural edits and multi-tweak sessions, where a
   compact registry stays resident in context and an HTML monolith cannot.
2. **Python 3 stdlib is the only runtime.** No pip install on the core path — render, preview,
   check and update-version are stdlib-only. Playwright (`/pb:test`) and Node/npm (`/pb:handoff --tier=host`)
   are the two isolated exceptions, and both degrade cleanly when absent.
3. **An existing project must never break.** Renames ship an alias *and* a migration; schema
   changes are additive; removal waits for a major release.
4. **The core is design-system agnostic.** No DS is hardcoded. Tokens are neutral, icons are
   configurable, and every DS arrives through `/pb:pull-ds`'s fallback ladder.
5. **Render must be fast enough to run on every change.** `/pb:preview` re-renders in memory on each
   registry write, so the generator is on the interactive path: `build_html` budget **100 ms**
   (baseline 32 ms at 3 components / 3 screens), whole pipeline **1500 ms** at real scale. Measured
   on a real project: `json.load` 2.6 ms · `load_specs` 17.1 ms · `build_html` 9.9 ms ([D-20]).

## The design

**One registry, two projections, a cheap loop.**

The model edits *slices* of `registry.json` — the touched component, the touched screen, the touched
logic — and nothing else. A deterministic Python generator (`pb/tools/render.py`) projects the whole
registry into two sites at ~0 model tokens: the **prototype** (`prototype.html`, 4 tabs) and the
**design system** (`design-system.html`, the component workbench). Both are derived. Neither is ever
hand-edited.

The registry stays small because the bulky parts live in sidecar trees referenced by pointer, not
inlined: render bodies in `render/**/*.js` (`renderSrc`), hand-off docs in `spec/**/*.json`
(`specSrc`, schema 10), logic contracts in `logic/**/*.json` (`logicSrc`, schema 11), and the
project's own modules in `runtime/*.js`. Externalizing `anatomy`/`spec`/`usage`/`uiLogic` alone
removed roughly half the file on a real project. Small registry → stays resident in context →
constraint 1 holds.

Durable reasoning lives beside it in `memory/` — `constitution.md` for rules, `decisions.md` for the
why-log — because the model needs the rules in context, not a hook engine that enforces them
invisibly.

## The design-system layer

A prototype is only worth showing if it is faithful to the system it claims to use, and constraint 4
says the core cannot know which system that is. So the DS arrives at runtime, down one path.

`/pb:pull-ds` resolves it along a **fallback ladder** — a dedicated DS MCP, a Figma design-system
link, the project's own code library, then a bundled common DS — normalizes whatever it finds into a
single DS-export, and hands that to `clone_ds.py`. The tool merges tokens into `registry.json`
(additive; `--overwrite-tokens` is explicit), records provenance in `meta.dsSource` / `meta.platform`,
and writes two files: `design-system/<name>/<name>.md`, the reference, and `.source.json`, the
snapshot `/pb:test --drift` audits the live source against. Nothing on that path is hand-written, and
the reference is never hand-edited — re-clone to refresh it.

**The reference is an index, not a rationale, and that is deliberate.** It carries a component table
(function · `renderFn` · variants · scope · level) plus rules R0–R4 and the naming contract — exactly
what `/pb:build` §3a needs to make the reuse decision mechanical: *does something already cover this
function?* → reuse it, else add a variant, else build local. Prose about why a value is what it is
would be read on every build turn and cost context proportional to the size of the DS, while changing
none of those three answers. Constraint 1 decides this the way it decides everything else.

So the layer deliberately holds no principles justifying a value, no decision tree for when two
components both fit, no cross-cutting rules (nested radius, feedback timing, negative space), no
platform dimension, and no judgement about whether the result looks good.

## Invariants

Numbered so a commit or PR can cite one instead of re-arguing it. Each maps to an enforcement point;
an invariant with no enforcement is a wish.

- **I-1 · State lives in `registry.json`.** The loop reads and edits only the touched slice.
  `prototype.html` is never the source of truth and is never hand-edited.
  *Enforced by:* derivation itself — a hand-edit is destroyed by the next render; [AGENTS.md](AGENTS.md) §1.
- **I-2 · The render is batched and deterministic.** No model calls, no randomness: the same
  registry produces the same HTML. It runs on `/pb:build --render`, automatically at hand-off and
  validate, and in memory under `/pb:preview` — never per tweak, never by the model emitting HTML.
  *Enforced by:* `tests/render_escape.py`, `tests/render_budget.py`, `tests/e2e_smoke.py`.
- **I-3 · Non-trio tweaks skip the gate.** The drift / Stack / DS gate runs only when a change
  touches a screen, a component, or logic. A token value, a copy reword, a prop default, spacing —
  all skip it, and skip the flow/erd auto-sync with it.
  *Enforced by:* the trio classifier in `/pb:build`.
- **I-4 · Component-first / atomic law.** Only `level:atom` render bodies emit raw HTML. Molecules,
  organisms and screens are pure composition through `pbUse('<id>', props)`.
  *Enforced by:* `lint_registry.py` R-LEVEL · R-COMPOSE · R-LEVEL-ORDER (ERROR under `--strict`).
- **I-5 · Schema changes are additive.** Bump `CURRENT_SCHEMA`, ship `NNNN_<slug>.py` with a
  `describe()`, wire the runner, prove migrate *and* rollback on a copy of an old project. Never
  remove or repurpose a field in place.
  *Enforced by:* `pb/migrations/manifest.py` + `/pb:update-version --apply` / `--rollback`;
  the write-path schema check in [CLAUDE.md](CLAUDE.md).
- **I-6 · A tool is only justified when a prompt cannot do the job** ([D-23]). At least one must
  hold: (a) it runs inside the deterministic render path at ~0 model tokens, so a prompt physically
  cannot do it; (b) it needs a regression test — especially a false-positive corpus — which a prompt
  cannot have; (c) it is arithmetic over a large set, where a model is slow and non-deterministic.
  Otherwise it belongs in a command prompt or as a flag on an existing tool.
  *Enforced by:* review. Applied retroactively it cut four proposed tools to two, and one proposed
  command to none.
- **I-7 · Derived is rewritten; hand-authored is never touched.** In the logic contract,
  `seam`/`handlers`/`disclosure` are regenerated by `logic_extract.py --contracts`, while `writes[]`
  and `affordances[].why` are human-only and no tool ever writes them.
  *Enforced by:* `logic_extract.py` scope; `logic_check.py` L-* rules; `tests/logic_contract.py`.
- **I-8 · Health reporting ranks, never gates** ([D-18], [D-22]). `lint_registry.py --report` always
  exits 0 and every check carries a false-positive guard. Contract lint under `--strict` is a
  different thing and does gate.
  *Enforced by:* `lint_registry.py` exit codes; the FP corpus in `tests/`.

## Alternatives rejected

The section that stops the same debate recurring. Each carries the evidence that killed it.

**The model hand-emits HTML.** Measured ~2–3× *worse* than the registry at G0.5. This is the
single most-retried idea and the one with the hardest number against it.

**Render on every tweak.** The cost was never render time — 32 ms at baseline — it is the model
round-trip that a render implies. `/pb:preview` satisfies the real need (see it now) by running the
*same* generator in memory at ~0 model tokens, which is why it does not violate I-2.

**SpecKit as the host.** The v0.4.0 baseline ran on `extension.yml`, `preset.yml` and `after_*`
hooks with a 5-tab single-file template. Replaced by a plumbing swap, not a rewrite — the
crown-jewel logic was ported unchanged, and the Tab-2 sync the hooks performed moved directly into
the `init` / `specify` / `clarify` command bodies. A hook engine was indirection for work a command
body does in the open.

**Deleting dead fields.** `staleness` is seeded, read by the shell, and *never written by anything
in the plugin* — its gap is permanently zero. Deletion still lost to deprecation ([D-19]): it breaks
constraint 3 and any project reading the field. The shell's dead reader was removed; the field waits
for a major.

**A standalone `doctor.py`.** Became `lint_registry.py --report` ([D-22]) — lint already exposed
`check()` and `_report()`, so a new file would re-implement a CLI and add a second thing to keep in
step for a flag's worth of work. This is I-6 applied.

**A Sync button for flow/erd.** The trio classifier already knows when a patch touched something
structural, so `/pb:build` reconciles the `flow` and `erd` slices in the same turn ([D-29]).
Reconcile, never regenerate — regeneration would discard the `lastResult` that `/pb:test` wrote.

**Raising the render budget** to accommodate a slow step ([D-20]) — hides the gap it was built to
find. **Case-by-case judgement on new tools** ([D-23]) — that is precisely what produced four tools
where two were warranted.

## Known tensions

What the design is deliberately bad at. These are accepted, not undiscovered.

- **Single cosmetic tweaks are ~break-even.** The registry indirection does not pay for one colour
  change. The loop optimizes for sessions, and that is the honest trade.
- **One logical component spans up to four files** (registry entry · `render/` body · `spec/`
  sidecar · `logic/` contract). The cost of navigation buys the small resident registry that
  constraint 1 requires.
- **Playwright-gated tests skip green.** `e2e_smoke` · `test_inspect` · `test_sandbox` ·
  `verbs_browser` exit 2 when Playwright is absent, so a sweep without it asserts nothing about the
  shell in a browser. This is mitigated by process ([AGENTS.md](AGENTS.md) §7), not by design, and
  it has already let a deleted selector ship "all green".
- **The Figma bridge is one-way.** Code → Figma only; the MCP is a read-only context provider. No
  round-trip, by choice — a two-way sync needs a conflict model pb does not have.
- **pb clones a design system; it cannot author one, and it has no taste layer.** The ladder's
  last rung hands a project without a DS a bundled common one — no rung *builds* the missing system.
  That much follows from constraint 4: a core that authored a DS would be asserting one. The second
  gap is not defended anywhere. `/pb:test` grades correctness — scenarios, roles, security, drift —
  and nothing in the tree records whether a rendered screen looks *good*, only whether it is
  consistent, reachable and DS-faithful.
- **`writes[]` must be hand-authored.** Static derivation traces reads but not writes, because the
  mutation happens inside a store helper. It is the one contract field a human must state, and the
  Logic tab's ripple view is only as good as that statement.

## Open questions

- **The `hardened` export tier** (`/pb:handoff --tier=hardened`, idiomatic / DS-integrated) is
  deferred with no owner or date.
- **`staleness` removal** is queued behind the next major release.
- **[docs/architecture.md](docs/architecture.md) is stale** — it still describes the v1.4.2
  layout: its plugin tree omits `agents/` · `skills/` · `migrations/`, and its template list
  predates `design-system.html` and `runtime.js`. Its command count reads 12, which the 24 → 12
  merge has made *accidentally* correct — staleness that now hides itself. Either refresh it as
  the codemap this file defers to, or fold it in and delete it.
- **The 24 → 12 command merge shipped without compat aliases**, a recorded deviation from
  [AGENTS.md](AGENTS.md) §2 and a breaking change for anything invoking one of the nine retired
  names. The version is still 1.12.0; by constraint 3 and I-5 it is a 2.0.0.
- **The design-system scaffold is unconnected.** `../design-system-scaffold/` already answers both
  gaps above and pb references it nowhere. It is a routed folder tree — principles → foundations →
  atoms → molecules → organisms → templates → patterns → decision trees → governance — whose
  `01-foundations/tokens.json` is a three-tier **W3C DTCG** document, the format `clone_ds.py`
  ingests and `tokens.py` resolves, and whose `09-aesthetic/` holds what pb has no home for: a
  44-check grading rubric, generated HTML samples that hold every standard fixed and move only the
  taste variables, and a human grading log with two completed rounds. It is the authoring format for
  the thing pb can only clone. The question is which of three it becomes: **rung 0** of the ladder
  (`/pb:pull-ds` authors the DS when no source exists), a **normalizer input** that contributes
  `tokens` + `components` and drops principles, trees and taste at the boundary by the same argument
  that keeps the reference an index, or a **permanently separate tool** that hands pb a DS-export by
  hand. **Measured 2026-09-20:** a ~150-line stdlib exporter in the scaffold (`tools/export_pb.py`)
  drives the whole chain — scaffold → DS-export → `clone_ds.py` → `registry.json` → rendered
  `prototype.html` — with **zero changes to pb**, and `display_kind` bucketed the scaffold's nested
  `ds.primitive` / `ds.sem` tiering with no configuration. The seam is cheap and stable, so the
  answer is the third option: stay separate, keep the boundary executable. Two defects the run
  exposed are pb's, not the scaffold's: `clone_ds.py`'s token merge iterates top-level keys only, so
  a nested DTCG document merges all-or-nothing (it reported `+1 added` for ~110 tokens), and a DS
  whose `$value`s are `null` clones with a `✓` while both resolvers silently drop the dead tokens —
  68 of them here — leaving a render that falls back to shell defaults and looks plausible. Neither
  has an owner yet.
