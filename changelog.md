# Changelog

All notable changes to Product Builder. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.4.0] — 2026-06-10

A major redesign of the prototype shell — every tab now shares one unified, two-column layout — together
with the schema-migration system, **plus the v1.4 refit** (governance validator, file-based render bodies,
CI, portability). The registry contract advances to **schema 4** (migration `0002` required; run
`/pb:migrate`).

### v1.4 refit — quality, governance, portability

*Safety net + governance + the strategic move of render bodies out of JSON into real files, + shell
hygiene + portability. The audit harness is now the permanent regression suite.*

**Safety net (Phase 0)**
- **No release ships red.** `.github/workflows/ci.yml`: a `unit` job (migrations selftest · golden render
  twice → identical SHA-256 · render-time budget · `check.py --strict` clean on golden · all seeded
  violations caught · shell hygiene lint) and an `e2e` job (Playwright chromium smoke). Fixtures committed
  under `fixtures/`; tests under `tests/`.
- **Backup-collision bug fixed.** `migrate_runner.py` no longer overwrites a backup on a same-second
  re-apply (appends `-2`, `-3`, …; `_latest_backup` sorts by mtime).
- **Friendly render errors.** `render.py` reports invalid JSON / missing files in one line, exit 2, no traceback.

**Governance (Phase 1)**
- **The contract is machine-checked.** New `pb/tools/check.py` (stdlib) validates shape, kebab/unique ids,
  the `renderFn` naming contract, `orgId` resolution, token `kind`, a `</script>` page-killer (error), raw
  hex/px (warn; `--strict` → error), the runtime-required `danger` token, and flow/erd shape. Wired
  advisory into `/pb:build` and **fail-closed** (`--strict`) before `/pb:hand-off` and `/pb:validate`.
- **Out-of-box danger gap closed.** The template seeds a `danger` token and the shell `:root` carries a
  `--danger` fallback, so a fresh project's validation border is red with zero manual token work.
- **`pbEscape` hardened** to escape `"` and `'` (names with quotes are safe in attributes/handlers).

**Render bodies are real files (Phase 2, schema 3 → 4)**
- Each component/screen carries a `renderSrc` → `render/components/<id>.js` / `render/screens/<id>.js`;
  `render.py` reads and compiles them. Lintable, diffable, no triple-escaping. **Measured:** the golden
  registry's resident state shrank **28.3%** (16,036 → 11,497 bytes); render holds at **0.7 ms** @ 50/20.
- Migration `0002_v13_to_v14` extracts/re-inlines bodies and is exactly reversible (selftest round-trip).
- **Page-killer eliminated.** All emitted bodies pass a `</` → `<\/` escape (a `</script>` body now boots).
- `serve.py` watches `render/**/*.js`; `/pb:build`, `/pb:hand-off --context`, `/pb:init --import`,
  `check-drift`, and the Figma token scan all account for the body files.

**Shell hygiene + honest contracts (Phase 3)**
- **`CHAT_PROMPTS` deduped + rewritten** against the real `/pb:*` command set; removed v0.4
  `agent-skill-set` / `USER-FLOW-GUIDE` references.
- **Dead wireflow feature deleted** (D2) — `WIREFLOW_SCREENS`/`WIREFLOW_NOTES`/`wfCardHtml` and their CSS;
  `node/status/preview` stripped from `sync-flow.md` + the playbook so command demands match the renderer 1:1.
- **View-only leak fixed** — `/pb:hand-off --people` hides every authoring CTA (sync bars, Figma panel,
  empty-state actions); unpopulated tabs render a neutral "Not included in this hand-off."
- **Truthful shell header** (no `cp template.html`, correct tab names, "do not hand-edit"); stale
  `plugin.json 1.2.0` reference in `docs/architecture.md` corrected to 1.4.0.

**Schema:** `CURRENT_SCHEMA = 4` — run `/pb:migrate` to upgrade an older registry.

### Added — unified UI shell (`pb/template/prototype.html`)
- **One page chrome for every tab** — a `pb-page-header` (title + a `?` **info dialog** documenting the
  tab's commands/skills + an optional CTA) over a `pb-content` shell: `--full` (Project Summary) or
  `--split` (left main · right aside, **320–400px**). Replaces the old `meta-tag`/`meta-sub` headers.
- **Empty-states everywhere** — an unpopulated tab renders only the header + an empty-state card that owns
  the CTA; no dead controls against empty data.
- **Prototype** — a device-framed preview (browser chrome on desktop, bezel + notch on tablet/mobile; sizes
  not in `meta.devices` are disabled) plus a screen → component **structure tree** aside.
- **UX Design** — the flow canvas (multi-flow dropdown + legend) on the left; **screen-size W×H** inputs and
  **User stories | Test cases** on the right. Test cases are authored as **QA** across five lenses
  (UX · UI · Function · Business · System-edge), with a **Coverage gaps** callout for edges the flow misses.
- **UI Design** — a **Global | Local | Screen** control + a **design-system bar** (name + design link +
  code-library link, or an "add one" affordance). Components list by `scope`, **grouped by atomic `level`**;
  clicking a component/element opens its full spec in the persistent aside. The **Push to Figma** panel now
  shows a **reuse** badge for DS-matched components and **which screens each push affects**.
- **Data** — the ERD diagram in the shared canvas wrapper + an entity legend / click-to-inspect aside with a
  **mock-data viewer** (preview Typical / Empty / Long-value sample sets against the fields).

### Added — registry contract (all optional / tolerated-absent)
- `meta.designSystem { name, designLink, codeLibrary, linked }`, `meta.devices[]`, `components[].level`
  (`atom|molecule|organism`), `flow.screen {w,h}`, `flow.flows[]`, `flow.coverageWarnings[]`, `erd.mock[]`
  — documented in `prototype-builder.md`.
- **Atomic-design principle** — constitution principle 5 + design-system rule **R0.5**; the UI groups the
  component lists by level.

### Changed — commands + docs
- `/pb:init` seeds `meta.designSystem` (from the DS Lock) + `meta.devices`.
- `/pb:build-check-design-system` tags each component's atomic `level`.
- `/pb:sync-flow` authors QA-lens test cases + `flow.coverageWarnings`, and persists `flow.screen`.
- `/pb:sync-erd` gains `--mock` to generate `erd.mock[]` edge-case sets.
- `/pb:build-figma-handoff` G-FP2 surfaces affected screens per updated component; Step 6 reports progress.
- `CLAUDE.md` tab-render section and `README.md` updated to the v1.4 UI.

### Added — schema migration system
- **One preview per project** (`pb/tools/preview_register.py`, `/pb:preview`): each project has a single
  preview source of truth — the live `/pb:preview` server over its `registry.json`; `prototype.html` is a
  derived hand-off snapshot, not a parallel preview. When an in-app preview pane is used, the new helper
  keeps exactly **one** canonical `.claude/launch.json` entry per project (`pb-preview · <folder>`):
  upsert in place, dedupe entries for that project, never touch entries it doesn't own. Stdlib-only.
- **`/pb:migrate`** — versioned schema migration command: dry-run (default), `--apply`, `--rollback`,
  `--to <N>`, `--registry <path>`. Backup-first, single-write, render-validated. Stdlib-only.
- **Migration framework** (`pb/migrations/manifest.py`, `pb/migrations/migrate_runner.py`): `CURRENT_SCHEMA`
  as the single version source; `chain(from_v, to_v)` helper; module contract (`up`, `down`, `describe`,
  `memory_notes`). Advisory memory rule: migrations never auto-edit `constitution.md`.
- **Soft compat gate** on write-path commands (`/pb:build`, `/pb:sync-flow`, `/pb:sync-erd`,
  `/pb:init --import`): prints a one-line schema-gap banner and suggests `/pb:migrate`; hard-stops only
  when the pending write touches a slice a pending migration changes.
- **`registry.template.json`** now carries `meta.schemaVersion: 3` and `meta.device: "desktop"` so fresh
  scaffolds are correctly stamped.

### Migrations
- `CURRENT_SCHEMA = 3` (first formal stamp; unstamped registries treated as schema 2).
- Migration `0001_v12_to_v13`: "v1.2 → v1.3: add meta.device, components[].scope, structured flow/erd shape (legacy html preserved)."

## [1.3.1] — 2026-06-07

Docs / packaging cleanup for publishing — no code or command changes.

### Removed
- `docs/v0.4.0/` (SpecKit-era SRS / architecture / orchestrator / execution-plan), `docs/CHANGES-from-v0.4.0.md` (superseded by this changelog), and `docs/code-to-figma-handoff-research-brief.md` (research now implemented as the `/pb:build-figma-handoff` G-FP gates) — all retained in git history.
- Leftover root `design-system/` starter — a per-project artifact regenerated by `/pb:init`, never a shipped plugin asset.

### Changed
- Bumped `docs/architecture.md` + `docs/data-flow.md` version refs to v1.3.

## [1.3.0] — 2026-06-07

A render-layer redesign: every tab in the shell (`pb/template/prototype.html`) gets richer, and the
prototype itself becomes a real, clickable flow. Data-only change to the registry contract — same generator,
no new dependencies.

### Added
- **Interactive prototype runtime** — the Prototype tab is now a live flow driven by `data-*` attributes the
  shell wires up: `data-nav="<screen-id>"` (navigate), `data-action="toggle-password"`, and
  `data-action="submit"` which validates the form (`data-required` · `data-validate="email"` ·
  `data-minlength`) then on success runs `data-go` (navigate) / `data-toast` (toast) /
  `data-redirect`+`data-redirect-ms` (auto-navigate). Clicking links/buttons moves between screens.
- **Icon-only device switcher** replaces the screen-switcher: desktop (≤1180px) / tablet (834px) /
  mobile (390px), one viewport with internal scroll. The default comes from a new registry field
  **`meta.device`** (`'desktop'|'tablet'|'mobile'`), seeded at `/pb:init`.
- **State-variant component demos** — if a component declares a `state` property (`properties[]` entry
  `id:'state'`), the UI Design demo renders one labeled variant per state. Interactive components MUST ship
  their states this way (e.g. default / error / disabled).
- **UI Design Global | Local sub-tabs** — components split by `components[].scope` (`'global'` when
  `scope==='global'` or a `dsMatch` exists, else `'local'`), via the shared `meta-subtab` component.
- **Data Diagram | Table toggle** — Diagram = the `erDiagram`; Table = one styled `<table>` per entity (a
  real table component, not text alignment) built from a new structured `erd.table[]`
  (`{entity, field, type, example, notes}`).

### Changed
- **Unified `meta-subtab`** — the Project Summary tab now uses the same sub-tab component as UI Design.
- **UX Design renders from structured data**, not a pre-baked HTML blob: `flow.mermaid` + `flow.stories[]`
  (`{title, priority, jtbd, path, scenarios[], …}`). The left sidebar now has two sub-tabs — **User stories** |
  **Test cases** — both built from `flow.stories[]`. Mermaid uses `curve:'basis'` (smooth curved connectors,
  not zig-zag step), classDef colors match the on-canvas legend palette (start/end zinc · decision sky ·
  action lavender · input pink · subprocess purple), and a legend is shown.
- Registry contract extended (data-only): `meta.device`, `components[].scope`, the `state` property
  convention, the screen `data-*` interaction runtime, and structured `flow`/`erd` shapes
  (`flow.{mermaid,stories[]}`, `erd.{table[],mermaid}`); each tab's `html` field is now a legacy fallback only.

## [1.2.0] — 2026-06-06

### Added
- **Preview dev server** (`pb/tools/serve.py`, `/pb:preview`): watches `registry.json` (+ the shell
  template + `render.py`) and live-reloads the browser on every change over Server-Sent Events. Renders
  **in memory** through the same generator as `/pb:build --render` (so the preview is byte-identical and
  costs ~0 model tokens), never clobbering the on-disk `prototype.html`. `--write` opts into also keeping
  `prototype.html` fresh; a bad registry mid-edit shows a recoverable error page instead of crashing.
  Stdlib-only — no new dependencies.
- Figma hand-off render audit (**G-FP6**): a mandatory, machine-checkable read-back after the push —
  auto-layout on every frame · 0 absolute children · 0 raw values (color/space/radius all bound to
  variables) · variants in a ComponentSet · screen elements as instances · bound-token count ≥ the
  G-FP3 union. A failing invariant HARD-FAILs and **blocks the Step 7 contract write-back**, so a
  hand-off is "done" only when the pushed result verifies — making the gated process the enforced
  path, not merely the recommended one.

### Changed
- `render.py` refactored to expose a pure `build_html(reg, shell)` (the single render truth shared by the
  CLI and the dev server) and a `RenderError`; the `render.py` CLI output is unchanged.
- `serve.py` hardened to run under a sandboxed launcher (e.g. a macOS preview pane TCC-blocked from
  `~/Desktop`): resolve all paths to absolute, then `chdir` to an accessible dir so an unreadable inherited
  cwd no longer crashes startup (`os.getcwd()` EPERM); path display + static root are cwd-free. Relative
  and absolute invocations both verified.

## [1.1.1] — 2026-06-05

A standalone, CLAUDE.md-native rebuild of the SpecKit Prototype Builder. A plumbing swap, not a rewrite —
the crown-jewel logic ported unchanged. See [docs/CHANGES-from-v0.4.0.md](docs/CHANGES-from-v0.4.0.md).

### Added
- `registry.json` as the single source of truth for prototype state.
- Deterministic render generator (`pb/tools/render.py`): `registry.json` → `prototype.html` at ~0 model tokens.
- Claude Code **plugin** packaging (`pb@product-builder`); the `/pb:*` command surface (12 commands).
- `/pb:build-check-design-system` — DS-first reuse / variant / build-local + naming contract.
- Two-mode `/pb:hand-off` — `--people` (view-only + cover) and `--context` (portable bundle).
- Memory layer: `memory/constitution.md` (Principles + Stack/DS locks) and `memory/decisions.md`.
- `config` block (`viewOnly`, `cover`, `iconCdn`) for a DS-agnostic, shareable output.

### Changed
- `scaffold` → `init`; `figma-push` → `build-figma-handoff` (DS-neutral).
- Tabs renamed: User Flow → UX Design, Design Handoff → UI Design, ERD → Data.
- Tab-2 (Project Summary) sync folded into `init` / `specify` / `clarify` command bodies (no hooks).
- Design-system-agnostic core: neutral tokens (`--neutral-*`, `--shadow-*`, `--radius-*`), configurable icons.

### Removed
- SpecKit: `extension.yml`, `preset.yml`, the `after_*` hooks, `sync-tab2`, `skills-refresh`.
- All HIVE / PropertyGuru hardcoding.

### Fixed
- Render generator: inline `registry.json` safely (`</` → `<\/`) without double-escaping JSON — fixes any
  registry value containing embedded quotes or newlines (e.g. flow/erd HTML).
- Tab 1 (Prototype) now renders `registry.screens` as the **live interactive app** (with a screen
  switcher for multi-screen prototypes) instead of a hand-edited placeholder — caught by an end-to-end
  self-test build.
- Figma handoff identity: `figma-transfer.template.json` now stores `dsMatch.figmaComponentId` (matching
  what `build-figma-handoff` and the `figma-use` skill read) — the prior `componentId` mismatch would have
  re-created components instead of updating them in place.
- Figma handoff token coverage (G-FP3): collect the **union** of declared tokens + every `var(--…)` used in
  the render bodies, so tokens that are used but not separately declared (spacing, semantic colors, shadows)
  are no longer silently skipped — caught by the dry-run test (3 → 17 tokens on the selftest fixture).

## [0.4.0] — prior baseline (SpecKit Prototype Builder)

The SpecKit preset + extension: a 5-tab single-file `template.html`, `after_*` hooks, and `figma-push`.
Retained, untouched, in its own repo (`spec-kit-extension-prototype-builder`).
