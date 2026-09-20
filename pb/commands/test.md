---
description: Check everything. By default runs the whole battery — authored scenarios, role gating, server health, the security scan, the constitution drift audit, the ranked health report, shell coherence and DS drift — and reports one verdict. Any mode flag narrows it to that one check. Read-only on the design; the only thing it writes back is each scenario's lastResult.
---

# /pb:test

Exercise the prototype the way a QA engineer would, **and** audit it the way a reviewer would.
With no flags it runs **everything** and gives you one verdict. **Read-only on the design** — the
only thing it ever writes is each scenario's `lastResult` (status + detail + `ranAt`), which the UX
tab's glyphs read.

> Absorbs the former `/pb:check-drift`. Drift was a separate command because it audits rather than
> executes — but a reviewer asking "is this sound?" wants both answers, and two commands meant one
> of them usually went unrun.

## 0 · Flags

**No flag = every check below.** A mode flag narrows the run to that one thing.

| Flag | Runs |
|---|---|
| *(none)* | **All of it** — §3 scenarios · §4 roles · §5 server · §6 security · §7 drift · §8 health · §9 shell coherence · §10 DS drift |
| `--functional` | Only the authored scenarios |
| `--roles` | Only role gating + the scenarios per role |
| `--server` | Only server health + navigation reachability |
| `--explore` | Only the exploratory crawl (no assertions) — never part of the default run |
| `--security` | Only the static security scan |
| `--drift` | Only §7–§10, the read-only audits (the old `/pb:check-drift`) |
| `--story <id\|title>` | Scope the scenario run to one story |
| `--attach [URL]` | **Transport, not a mode.** Reuse the running `/pb:preview` instead of booting a headless one. Composes with every mode |
| `--strict` | Promote the pre-flight lint to strict and **fail-closed** — stop before running anything |
| `--save` | Also write the drift report to `memory/drift-reports/<YYYY-MM-DD-HHMMSS>.md` |
| `--render` | After the run, regenerate `prototype.html` so the glyphs land in the snapshot |

`$ARGUMENTS` may also name a single principle (e.g. `principle #3`) to scope the drift audit.

## 1 · Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md`. This command writes only
`flow.stories[].lastResult`; if a pending version update touches `flow`, **stop** and print
`Blocked: run /pb:update-version --apply first, then retry.` Otherwise print the banner and continue.

## 2 · Contract check (advisory, or fail-closed with `--strict`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" registry.json
```
Advisory by default — a bad contract should not hide a test result. With `--strict`, re-run as
`--strict` and **STOP on any error**.

---

## 3 · Authored scenarios
Invoke the **sandbox-test** skill for the `test{}` vocabulary, target resolution, and the
fail-closed discipline. Then:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --functional [--attach [URL]] [--story <id|title>] [--json <out>]
```
For each scenario the tester sets `state.protoScreenId = test.start`, performs each `steps[]` action
(`fill` · `click` · `nav` · `submit` · `toggle-password` · `back`) against `#proto-frame`, then verifies
every `expect[]` item (`screen` · `text` · `errors` · `toast` · `no-console-error`), and writes
`lastResult { status, detail, ranAt }`.

A scenario declaring `test.roles` runs **once per declared role**; one declaring none runs at
`meta.defaultRole`. The role is set explicitly before every run, never inherited from the previous
scenario, and `lastResult` records which role produced each verdict. A scenario passes only when
every declared role passes. `test.seed` is applied too.

## 4 · Role gating
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --roles [--attach [URL]]
```
Walks every screen per role, asserting gated screens and elements are visible only to permitted roles
(an `isAdmin` role bypasses), then runs the authored scenarios per role. Visibility sampling alone
cannot tell you whether a role's flow works — and a role-gated write control carries no `data-roles`
attribute at all, because the render body omits it entirely. Assert those with `present` / `absent`
expects: they test **presence, not visibility**, so a CSS-hidden element still counts as present.

## 5 · Server health
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --server [--attach [URL]]
```
`GET /` returns 200, `/__pb_events` is an SSE stream, every screen renders with no console errors, and
every `data-nav` / `data-go` / `data-redirect` target resolves to a real screen id.

## 6 · Security scan
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/security_scan.py" registry.json
```
Static, stdlib-only, over the registry + render bodies: secrets, PII, `</script>` page-killers,
unescaped injection, external calls.

---

## 7 · Constitution drift (read-only)
Load `memory/constitution.md` → `## Principles`, and the **trio**: `screens[]`, `components[]`, and the
logic — `elements[].uiLogic` / `components[].uiLogic` / `screens[].logicNotes`, plus each item's
`renderSrc` body file, which is where the markup and logic actually live. Missing input → HARD FAIL with
the missing-file message. Empty Principles → `"No principles to check against."` and skip to §8.

For each numbered principle, examine every screen, component and logic note: *does this contradict
principle N?* Record principle id · where · the exact excerpt · a one-line reason.

- **Clean** → `✅ Drift audit clean. Principles checked: N · Contradictions: 0 — the trio is in lockstep with the constitution.`
- **Contradictions** → a `⚠ DRIFT REPORT — N found` block grouped by principle, each with the excerpt and
  reason, then **Suggested fixes** naming `/pb:build` (re-derive the slice), `/pb:clarify` (revisit a
  trade-off), or editing `memory/constitution.md` (if the principle is the thing that is wrong).

## 8 · Project health (read-only, never gates)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/lint_registry.py" registry.json --report
```
**Always exits 0** — it ranks, it never fails a build. A histogram by finding code, the items carrying
the most findings, the shape metrics (registry size, oversized render bodies, the largest slice, the
decisions-log size), and a "fix first" list. Thresholds come from an optional `memory/doctor.json`.

Two lines are **information, never defects**: unreferenced tokens (a design system ships full ramps) and
a present-but-all-zero `staleness` slice (deprecated — nothing writes it). Do not propose fixes for either.

At real scale a flat finding list is unreadable — a live project emits 87 warnings — so the **ordering**
is the product here, not the detection.

## 9 · Shell coherence (advisory)
Catches the silent stale render: `prototype.html` left rendered by an older plugin shell than the one now
installed. Read `prototype.html` beside `registry.json`, parse `<!-- pb-shell v(\S+) ·`, and compare
against `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`. Report exactly one line:
- **Match** → `✅ Shell coherent — prototype.html rendered by pb vX.Y.Z (current).`
- **Mismatch** → `⚠ Shell drift: prototype.html rendered by pb vX.Y.Z; current plugin is vA.B.C — re-render (/pb:build --render) or restart /pb:preview.`
- **No stamp** → `⚠ Shell unstamped: prototype.html has no pb-shell stamp — re-render with the current plugin to enable drift detection.`
- **No `prototype.html`** → skip silently.

## 10 · DS drift — clone vs source (advisory)
Skip silently if `meta.dsSource` is null or `design-system/<name>/.source.json` is missing. Otherwise
re-resolve the current source through the same fallback ladder `/pb:pull-ds` uses (`meta.dsSource.type` +
`.ref`), normalize it to a fresh DS-export (invoke `ref-design-system`) into a temp file, then:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/clone_ds.py" --drift <fresh-export.json> registry.json
```
Exit `0` = in sync; exit `3` = drift (the tool lists each changed/added/removed token + component). Delete
the temp file. Report `✅ DS coherent — <name> clone matches source.` or the `⚠ DS DRIFT …` list followed
by *re-run `/pb:pull-ds` to re-clone, or reconcile intentionally*. If the source cannot be re-resolved,
say so and skip — do not guess.

---

## 11 · Report + exit codes
Print each tool's report verbatim (they mirror `lint_registry.py`: `<SEVERITY> [<CODE>] <where>: <msg>`,
`✓ … clean` when all pass), then **one summary line** naming which checks ran and the worst result.

Honor the exit codes across every tool: `0` = clean, `1` = warnings only, `2` = any error or failing
scenario, `3` = **could not run** (no Playwright, no reachable preview). The command's outcome is the
**worst** exit seen — but treat `3` as *unknown*, never as a pass: a check that did not happen is a
different thing from a check that succeeded.

§7–§10 are **advisory**. They report and rank; they never set a failing exit on their own.

## 12 · Render (only with `--render`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
```
Otherwise stop after the report — the written `lastResult` is picked up live by `/pb:preview`.

## NEVER
- NEVER boot a second preview server — reuse the one `/pb:preview` (`--attach`) or a single headless run.
- NEVER edit screens / components / logic to make a test pass — tests observe the design, they don't shape it.
- NEVER claim a pass without an actual run — an unexecuted scenario is `untested` (`○`), not `pass`.
- NEVER write anything but `flow.stories[].lastResult` back to the registry, and never touch
  `prototype.html` outside `--render`.
- NEVER auto-fix drift — surface it; the user decides.
- NEVER silence a contradiction because it seems minor — surface everything; the user judges severity.
- NEVER scope the drift audit to fewer than all three trio surfaces unless the user explicitly asks.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed
> with its core intent — never silently skip the step.
