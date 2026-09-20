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
- **`writes[]` must be hand-authored.** Static derivation traces reads but not writes, because the
  mutation happens inside a store helper. It is the one contract field a human must state, and the
  Logic tab's ripple view is only as good as that statement.

## Open questions

- **The `hardened` export tier** (`/pb:handoff --tier=hardened`, idiomatic / DS-integrated) is
  deferred with no owner or date.
- **`staleness` removal** is queued behind the next major release.
- **[docs/architecture.md](docs/architecture.md) is stale** — it still describes the v1.4.2 layout
  (12 commands, no `agents/` · `skills/` · `migrations/`). Either refresh it as the codemap this
  file defers to, or fold it in and delete it.
