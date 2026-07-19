# Changelog

All notable changes to Product Builder. Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.10.0] — 2026-07-19

*UI Design tab reworked into a Figma-style inspector — master-detail, redline anatomy/spec, a box model, and an inline component playground.*

### Changed
- **Prototype tab — full-bleed device preview.** Removed the tab title and page padding so the device
  frame fills edge-to-edge; added an app favicon (brand initial) and dropped the non-functional new-tab
  button from the browser chrome.
- **UI Design — master-detail layout.** Replaced the component card grid with a MUI-docs-style split: a
  scrollable name list (Global / Local / Screens) on the left, the selected component's detail stacked on
  the right — inline **component playground → Anatomy → Specification → Layer properties → UI Logic →
  Usage** (no per-section tab switcher).

### Added
- **Anatomy redlines.** Auto-extracted, numbered element callouts placed *outside* the component with
  single straight leaders (no corners), a fixed **Left → Right → Top → Bottom** side priority, gutters
  that hug the component so leaders stay short, and a dashed bounding-box outline for the container part.
  Every badge clears the object and box edges by ≥24px; the token list per element is typed (swatch +
  name + value).
- **Specification redlines — consistent across components.** Width dimension spans the component's outer
  box; element heights run down the left and inter-element gaps down the right (both anchored to the outer
  edge); uniform padding collapses to one chip and never overlaps content. Plain-pixel labels.
- **Layer properties — box model.** A Figma-style nested **Margin → Border → Padding → content W×H**
  diagram, measured live from the component, with a value chip per side (`–` for zero).
- **Component information — inspect list.** Variant props render as diamond-marked selects, free-text props
  as `Aa` fields — one labeled row each, all live.
- **Component playground (inline).** A preview canvas with a light/dark canvas toggle beside a controls
  panel (component props + Display / Color Mode + reset), rendered inline at the top of the detail.

## [1.9.0] — 2026-07-18

*Shell UI: the Prototype header tools collapse into one **Sandbox** control in the meta nav.*

### Changed
- **Consolidated Sandbox menu.** The per-tab Prototype header tools (Browser/App chrome toggle, device
  switcher, structure-tree toggle, sandbox ⋯ menu) **plus** the shell version move into a single
  **`Sandbox ▾`** button at the right end of the meta nav, present on all 5 tabs. Clicking it opens one
  popover:
  - **Preview** (Prototype tab only): Chrome · Device (segmented tab group, soft active token) · Structure tree.
  - **Sandbox**: Reset session (top) · Roles · Explore · Terminal testing — Roles/Explore/Terminal are
    dropdowns, disabled when the project has no data for them.
  - **Footer**: `pb v<version>` (moved out of the nav).
  On the other four tabs the menu shows just the Sandbox group + version. Reuses the shell's existing
  `.proto-shell-toggle` / `.proto-device-btn` / popover components — no new visual language.
- Tests updated to the new UI (`shell_version`, `e2e_smoke`, `test_sandbox`): version reads from the menu
  footer; roles are a dropdown; the trigger is the nav `Sandbox` button.

## [1.8.1] — 2026-07-18

### Fixed
- **Tool CLI consistency.** `clone_ds.py` and `resolve_frame.py` now accept the registry path
  **positionally** (`… --from EXPORT registry.json`), not only via `--registry`. The command docs
  (`/pb:pull-ds`, `/pb:check-drift` §5, `/pb:init --figma`) already invoked them positionally, so
  those steps would have errored at runtime. `--registry` still works as an alias. Guarded by
  `tests/tool_cli.py`.

## [1.8.0] — 2026-07-18

*R3 "Figma-frame entry": a second entry door — a project can be born from a Figma frame, not just a
PRD. Schema bumps to **7** (additive migration 0005). DS fidelity is held at entry: layers map to
components that already exist; unmapped layers are logged, never invented. Built + verified fixture-driven.*

### Added
- **`/pb:init --figma <frame>` + `pb/tools/resolve_frame.py` + the `ref-figma-frame` skill.** Read a
  Figma frame via the Figma MCP, normalize it to a **frame-export**, then deterministically map each
  layer to a known DS component — emitting a registry **screen patch** (elements → `orgId`). Sets
  `meta.entry = "figma"`.
- **`gaps.md` logging.** Every layer with no confident DS match becomes a **labeled placeholder**
  element AND a `gaps.md` entry — pb never invents a component to fill a gap. Resolve each by
  cloning/adding the component and re-resolving, or building it with `/pb:build`.
- **`tests/r3_figma_entry.py` + `fixtures/frame-export.json`.** The R3 acceptance end-to-end
  (frame → screen patch with `orgId`s ⊆ known components + unmapped layers in `gaps.md`), asserting DS
  fidelity: nothing invented, nothing silently dropped.

### Changed
- **Schema 6 → 7** via additive migration `0005_entry` (adds `meta.entry` = `"prd"` | `"figma"`, default
  `"prd"`). Registry template + golden carry it; `/pb:update-version` migrates cleanly (up→down reversible).

## [1.7.0] — 2026-07-18

*R2 "export tiers": the prototype can now emit code, not just HTML — at a tier that matches the
need. Schema bumps to **6** (additive migration 0004). The scaffold tier is built + verified
fixture-driven; the **hardened tier is deferred** (see below).*

### Added
- **`/pb:handoff-dev --tier=host|scaffold|hardened` [`--component <id>`].** Tiered engineering
  hand-off, contract-gated (fail-closed `lint_registry.py --strict`) first.
- **Scaffold tier — `pb/tools/render_react.py` + the `design-component-export` skill.** Deterministic
  registry → a self-contained **React + Vite** app: one wrapper component per registry component/screen
  (reusing its render body), `tokens.css` (`:root` vars) + a token-mapped `tailwind.config.js`, and
  `npm run dev` scaffolding. Runs and lints clean. Fulfils the long-backlogged JSX/TSX export at the
  scaffold level (NS9).
- **`tests/r2_export_tiers.py`.** The R2 acceptance: migration 0004 reversibility + the scaffold
  emits a runnable React app (valid wrappers, resolvable imports, token CSS + Tailwind theme) from the
  golden fixture, and `--component` exports a single subset.

### Changed
- **Schema 5 → 6** via additive migration `0004_export_tier` (adds `meta.outputTier` default `"host"` +
  `meta.exportTarget` null). Registry template + golden fixture carry the fields; `/pb:update-version`
  migrates cleanly (up→down reversible).
- `host` tier delegates to `/pb:validate` (unchanged behavior, now named as a tier).

### Deferred (not built — inputs missing)
- **Hardened tier** (`harden_export.py`, `design-component-harden`, `pb-hardener`): idiomatic,
  DS-integrated per-component JSX, MCP-resolved + repo-matched + `validate_code`-scored + reviewed.
  `/pb:handoff-dev --tier=hardened` **stops with a clear message** — it needs the G-B decision (target
  repo AntD vs Tailwind), `pb-full-picture.md`'s export contracts, and the DS-MCP resolution path. No
  fake idiomatic export is emitted.

## [1.6.0] — 2026-07-18

*R1 "DS truth": the design system becomes a **cloned, verifiable source** rather than a loose
label. Schema bumps to **5** (additive migration 0003). Built and verified fixture-driven — no
production DS required.*

### Added
- **`/pb:pull-ds` + `pb/tools/clone_ds.py` + the `ref-design-system` skill.** Clone a DS via the
  fallback ladder — a dedicated **DS MCP** → a **Figma design-system link** → the **current code
  library** → a **common DS** — normalized to one DS-export, then materialized deterministically:
  tokens merged into `registry.json` (additive), `design-system/<name>/<name>.md` (scannable
  reference) + `design-system/<name>/.source.json` (drift snapshot) written, and `meta.dsSource` +
  `meta.platform` recorded. `clone_ds.py --drift` compares a fresh source export against the snapshot.
- **`/pb:preview-ds` + `pb/tools/ds_serve.py`.** A storybook-style server for the cloned DS — token
  foundations as visual swatches + the component catalog. Read-only; re-reads on every refresh.
- **`/pb:init` clone step.** The DS Lock now captures `platform` + the clone source (the ladder) and
  offers to run `/pb:pull-ds`; seeds `meta.platform`, leaves `meta.dsSource` null until cloned.
- **`tests/r1_ds_truth.py` + `fixtures/ds-export.json`.** The R1 acceptance end-to-end
  (clone → `preview-ds` → change one token at source → `check-drift` reports drift), fixture-driven.

### Changed
- **`/pb:check-drift`** gains §5 — a read-only, advisory **DS-drift audit**: re-resolve the source and
  diff it against `.source.json`. Never blocks. `/pb:handoff-close` runs it as an advisory pre-flight.
- **Schema 4 → 5** via additive migration `0003_ds_source` (adds `meta.platform` default `"web"` +
  `meta.dsSource` null). Registry template + golden fixture carry the fields; `/pb:update-version`
  migrates old projects cleanly (up→down reversible).

## [1.5.1] — 2026-07-18

*R0 groundwork: hygiene + safety so pb can sit cleanly inside a real repo. Command renames all
ship backward-compat aliases; nothing existing breaks. Schema stays v4 — no migration.*

### Added
- **`/pb:snapshot` + `pb/tools/snapshot.py`** — pb's history model: timestamped `registry.json`
  copies under `<project>/history/` (`--list` / `--restore`, with an auto-snapshot before every
  restore). Pure stdlib; it **never** branches and **never** touches the host repo's git — the
  reason snapshot (not an orphan branch) was chosen for adopt-in-place.
- **`/pb:init` adopt-in-place mode** — inside an existing git repo, pb sidecars everything under
  `.prototype/`, appends a pb block to the host `.gitignore`, and records a **read-only-outside**
  Principle in `constitution.md` (pb never edits host-repo files). `--adopt` / `--standalone` force it.
- **`pb/template/AGENTS.template.md`** — a recipient-facing orientation now written into every
  `/pb:handoff-close` (what the folder is, that `prototype.html` is derived, how to continue from `bundle/`).
- **`AGENTS.md`** (repo root) — build guardrails for anyone (human or agent) working on pb.
- **`tests/r0_hygiene.py`** — guards the R0 renames, alias resolution, the `check.py` shim, and the
  snapshot round-trip.

### Changed
- **Command renames (aliases kept):** `/pb:sync-flow` → **`/pb:flow`**, `/pb:sync-erd` →
  **`/pb:data`**, `/pb:hand-off` → **`/pb:handoff-close`**. The old command files are thin redirect
  stubs that still resolve.
- **`/pb:handoff-close`** now closes out into a single **`handoff/`** folder: a view-only
  `prototype.html` + a portable `bundle/` (ingestible by `/pb:init --import handoff/bundle`) + a
  generated `AGENTS.md`. `--people` / `--context` narrow to one piece.
- **Contract validator renamed** `pb/tools/check.py` → **`pb/tools/lint_registry.py`**; `check.py`
  stays as a compatibility shim (both `import check` and the CLI keep working).

### Deprecated
- `/pb:sync-flow`, `/pb:sync-erd`, `/pb:hand-off` command names and the `check.py` tool name — all
  kept working via alias/shim; scheduled for removal in a future major release.

## [1.5.0] — 2026-07-15

*Agent-powered testing sandbox, a multi-agent orchestrator, role-gated prototypes, and an ⌥-hover
element inspector. Every registry addition is optional/additive — schema stays v4, no migration; a
project without them behaves exactly as before. (Subsumes the terminology rename in [Unreleased].)*

### Added
- **Sandbox testing — `/pb:test`.** A Playwright-backed runner (`pb/tools/test_run.py`) drives the
  prototype's `data-*` runtime to verify authored scenarios: `--functional` (runs
  `flow.stories[].scenarios[].test` blocks and writes `lastResult` → live ✓/✗/○/☐ glyphs in the UX
  Design tab), `--roles`, `--server` (reachability), `--explore`. `--security` runs
  `pb/tools/security_scan.py` (stdlib secrets + PII scan). Playwright is the one optional dependency,
  isolated to this path like Node/npm at `/pb:validate`, and degrades gracefully if absent.
- **Multi-agent orchestration — `/pb:orchestrate`, `/pb:explore`.** Eight `pb-*` subagents
  (`pb/agents/`) + a stdlib wave scheduler (`pb/tools/orchestrate.py`) + an idempotent installer
  (`pb/tools/agents_install.py`). `/pb:plan` tasks now carry `agent` / `deps` / `slice`;
  `/pb:orchestrate` dispatches them in dependency **waves** (serial registry writes, render once per
  wave, acceptance-gated by `pb-tester` + `pb-reviewer`). `/pb:explore` fans out N `pb-builder`
  agents for parallel design options to compare and keep one.
- **Role-gated prototypes.** `meta.roles` / `meta.defaultRole` / `screens[].roles` + element
  `data-roles` gate the Prototype tab (an `isAdmin` role bypasses). A sandbox menu (hourglass icon)
  with a radio role list (each role's abilities / JTBD) + a Reset row rides the header; the role
  switcher + Reset stay visible to viewers even in a `--people` hand-off (only authoring controls hide).
- **Inspect mode.** Hold ⌥/Option and hover the live preview to see an element's structured id path
  (`screen › element › component`); ⌥-click copies it to paste to the AI. Best-effort derivation from
  the DOM's existing identity (`data-handoff-el` → registry label + component; else an anatomy part; else a fallback).

### Fixed
- `check.py` no longer crashes on a string (prose) `anatomy` — the `--strict` gate works on such projects.
- `orchestrate.py --json` always emits a parseable object, including IO / usage / invalid-UTF-8 error paths.
- `test_run.py` fails closed (exit 2) on server-boot failure and invalid-UTF-8 input instead of a traceback.
- `security_scan.py` handles deeply-nested JSON (RecursionError) and non-UTF-8 input cleanly.
- `--roles` leak detection now covers `display:contents`, `visibility`, and text-node-only children.

### Changed
- Reintroduces the regression suite (`tests/`) + fixtures (`golden`, `security_bad`, `violations.json`)
  consolidated into the plugin repo, and adds `test_sandbox` / `test_inspect` / `test_orchestrate` /
  `test_security` / `test_agents_install`. Version bumped to **1.5.0**.

## [Unreleased]

### Rename "migration" → "version update" — 2026-06-25

*User-facing terminology change. The `/pb:migrate` command is renamed to `/pb:update-version`, and
all docs + command prose now say "version update" / "update the version" instead of "migration" /
"migrate". No behavior change — the engine, its rules, and the registry contract are untouched.*

- Command `/pb:migrate` → **`/pb:update-version`** (`pb/commands/migrate.md` → `update-version.md`).
- Doc `docs/migrations.md` → **`docs/version-updates.md`**.
- Runner output banners reworded ("Version update plan / complete / failed …"); shell command hints
  (`pb/template/prototype.html`) and the `plugin.json` description updated.
- **Engine preserved.** Internal module/file names (`pb/migrations/`, `manifest.py`,
  `migrate_runner.py`, the `000N_*` steps), function names, and `registry.json`'s `schemaVersion` key
  are intentionally kept — no import, invocation path, or stored registry breaks. The version-update
  command and its rules are fully intact.
- Released changelog sections below are left as the historical record (they shipped under the old
  `/pb:migrate` name).

### Remove the test suite + CI — 2026-06-25

*Repo-cleanup: the regression suite and the CI workflow that ran it are removed. No
user-facing change — these were dev/CI-only and never shipped in the plugin (`./pb`).*

- Deleted `tests/` (shell-lint, skill-refs-lint, render-budget, check-violations, e2e-smoke,
  shell-version) and the committed `fixtures/` (golden registry + render bodies, violations.json).
- Deleted the version-update selftest (`pb/migrations/selftest.py` + `pb/migrations/_selftest/`).
  The runtime version-update engine (`manifest.py`, `migrate_runner.py`, the `000N_*` steps) is unchanged.
- Removed `.github/workflows/ci.yml`. The release/CD workflow (`release.yml`) is unchanged.
- `docs/version-updates.md` "Authoring a version update" now verifies via `/pb:update-version` dry-run
  instead of the deleted selftest.
### Force reuse of nested global components — 2026-06-25 (v1.4.3)

*Hand-off + validator feature. Schema-stable (4) — no migration required.*

- **`anatomy.parts[].orgId`** — a component anatomy part that IS a reused global (`badge`, `button`, …)
  now declares it via `orgId`, mirroring `screens[].elements[].orgId`. Makes nested reuse explicit and
  machine-checkable (the hand-off can't infer it from render code).
- **`/pb:build-figma-handoff`** — Step 6 now branches on `part.orgId`: a declared nested global is
  inserted as an **instance** of its `dsMatch.componentKey` (per parent variant) and recorded under
  `figma-transfer.components[<parent>].nestedInstances[<orgId>]`, never redrawn locally. New **G-FP6
  invariant #7** ("nested globals = instances") + a NEVER rule enforce it.
- **`tools/check.py`** — new rules: **R-NEST** (a part `orgId` must resolve + be `scope:global`),
  **R-NEST-HINT** (warns on a part that looks like a global but declares no `orgId` — drift detector),
  and a **`--figma` mode** (`check.py --figma registry.json figma-transfer.json` → **R-NEST-FIGMA**)
  that verifies every declared nesting has a recorded instance whose key matches the global's DS match.
  Runs offline over the two committed contracts, so CI asserts it without the Figma plugin.

### CI/CD + security hardening — 2026-06-19

*Infrastructure only — no user-facing changes, no schema bump, no migration required.*

**CI fixes (`.github/workflows/ci.yml`)**
- Push trigger restricted to `main`; PRs cover feature branches — eliminates the double-run on open PRs (was `branches: ["**"]`).
- Concurrency group fixed to `head_ref || ref` so runs from the same PR branch collapse correctly.
- Runner pinned to `ubuntu-24.04` (was `ubuntu-latest`; drifts on image updates).
- Playwright pinned to `1.60.0` (was floating `pip install playwright`). Version defined once at job level so the browser-cache key and the install pin stay in sync.
- Playwright Chromium browser cache added (keyed on OS + version).

What the CI suite checks (budget: wall-clock ≤ 6 min, no release ships red):

`unit` job (Python, stdlib-only):
- Migrations selftest — schema migration logic is internally consistent
- Shell hygiene lint — no duplicate steps, no dead code, no v0.4 strings
- Skill-reference lint — no dangling skill refs, commands are portable
- Render determinism — golden registry rendered twice, SHA-256 of both outputs must match
- Render-time budget — full render of 50 components / 20 screens must complete in ≤ 100 ms
- `check.py --strict` clean on the golden — registry passes all structural + naming-contract checks
- `check.py` catches every seeded violation — the validator rejects all known bad patterns

`e2e` job (Playwright Chromium, dev/CI-only, never shipped):
- Browser smoke across all 5 tabs: Prototype, UI Design, UX Design, Data, Project Summary
- Validates: token rendering, form validation, tab navigation, view-only hand-off mode, zero console errors

**CD: GitHub Release on version tag (`.github/workflows/release.yml`)**
- New workflow fires on `v*` tags only (the tag push is the human approval gate).
- Verifies the pushed tag matches `plugin.json` version before creating the release — a mismatched tag fails loud.
- Uses `gh release create --generate-notes --verify-tag` (no third-party action).

**Plugin publishing (`.claude-plugin/`)**
- `plugin.json` created (was missing; required for the release version-coherence check). Version `1.4.2`, name `pb`.
- `marketplace.json` unchanged — was already correct.
- README install section updated: GitHub-based remote install (`/plugin marketplace add danhnbui/prototype-builder`) added as the primary path; local install kept as a development option.

**Security: CodeQL alert remediation (`pb/tools/serve.py`)**
- CWE-22 path traversal (High, ×3): `serve_static` now uses `relative_to()` inside a try/except (raises `ValueError` on traversal) followed by a path rebuild from `root` — fully breaks the taint chain from user input. CodeQL did not recognize the previous `is_relative_to()` boolean guard.
- CWE-113 HTTP response splitting (Medium, ×1): `_send` strips `\r` and `\n` from the `Content-Type` header value before writing.
- Server was already bound to `127.0.0.1` by default; no change needed.

## [1.4.2] — 2026-06-16

### Shell version coherence — stamping + drift detection

*The rendered shell now carries the plugin version everywhere it's served or produced, so a stale render
can't hide silently. Advisory only — nothing blocks a build or preview.*

**Version-stamped shell**
- `render.py` reads the plugin SemVer from `pb/.claude-plugin/plugin.json` and fills a new
  `{{PB_SHELL_VERSION}}` placeholder — driving a small `pb vX.Y.Z` badge in the meta-nav corner.
- `render_file` (and `serve.py --write`) write a `<!-- pb-shell vX.Y.Z · rendered <ISO-8601> -->` stamp near
  the top of `prototype.html`. `build_html` stays pure/deterministic: the timestamp lives only on the disk
  artifact, never the in-memory preview.
- `/pb:preview`'s startup banner shows the rendering version (`· pb vX.Y.Z`).
- A bad/unreadable `plugin.json` degrades to `pb vunknown` rather than crashing a render.

**Drift detection (advisory, read-only)**
- `/pb:check-drift` gains a **shell-coherence** step: it compares `prototype.html`'s stamp to the installed
  plugin version and warns on a mismatch (`⚠ Shell drift…`) or a missing stamp — **never blocks**, never writes.

**Upgrade guide**
- New `docs/upgrading.md` — the **three-layer model** (plugin code · registry schema · rendered output), the
  canonical upgrade sequence, the author dev-loop, and a symptom → layer → fix table. Linked from the README;
  the matching "shell-drift detection" non-goal retired from `docs/migrations.md`.

**Schema:** unchanged (`CURRENT_SCHEMA = 4`) — no migration required.

## [1.4.1] — 2026-06-10

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

## [1.4.0] — 2026-06-10

A major redesign of the prototype shell — every tab now shares one unified, two-column layout — together
with the schema-migration system. Template + docs + commands; the registry contract gains several
**optional, tolerated-absent** fields (schema stays at **3**, no migration required).

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
