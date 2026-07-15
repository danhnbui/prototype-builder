---
description: Run the prototype's authored scenario tests against the live preview — functional, role, exploratory, and security modes — driving the shell's data-* runtime and honoring the check.py exit codes. Read-only on the registry (writes only each scenario's lastResult).
---

# /pb:test

Exercise the prototype the way a QA engineer would: drive the Prototype tab's declarative
`data-*` runtime through each authored `flow.stories[].scenarios[].test` block and report
pass / fail / untested. **Read-only on the design** — the only thing it writes back is each
scenario's `lastResult` (status + detail + `ranAt`), which the UX-tab glyph reads.

## 0 · Flags
- (default) — **functional**: run every scenario that has a `test` block, in the starting role.
- `--server` — reuse the **already-running `/pb:preview` server** instead of booting a headless
  one. Never start a second preview (one preview per project); if none is running, start `/pb:preview`
  first, then pass `--server`.
- `--roles` — run each scenario once **per role** in `meta.roles`, asserting role-gated screens /
  elements are visible only to permitted roles (admin bypasses).
- `--explore` — exploratory pass: crawl reachable screens from the entry, click every `data-nav` /
  `data-action`, and report dead ends, console errors, and unreachable screens (no assertions).
- `--security` — also run the static security scan (`security_scan.py`) over the registry + render
  bodies (secrets, `</script>` page-killers, unescaped injection, external calls).
- `--story <id|title>` — run only the matching story's scenarios.
- `--strict` — promote the pre-flight `check.py` to **strict** and **fail-closed**: if the contract
  isn't clean, STOP before running anything.
- `--render` — after the run, regenerate `prototype.html` via `render.py` (so the glyphs are in the
  snapshot). Default: no render (token lever NS2 — tests don't render).

## 1 · Pre-write schema check
Apply the **Schema compatibility** check from `CLAUDE.md`. `/pb:test` writes only `flow.stories[].lastResult`
(the test-status slice); if a pending version update touches `flow`, **stop** and print
`Blocked: run /pb:update-version --apply first, then retry.` Otherwise, if `meta.schemaVersion` is below
`CURRENT_SCHEMA`, print the banner and continue.

## 2 · Contract check (advisory, or fail-closed with `--strict`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/check.py" registry.json
```
Surface any `ERROR`/`WARN` lines. This is **advisory** by default (a bad contract shouldn't hide a test
result). With `--strict`, re-run as `check.py --strict registry.json` and **STOP on any error** — never
test a registry that violates the contract.

## 3 · Run the tests
Invoke the **sandbox-test** skill for the `test{}` vocabulary, target resolution, and the role / server /
fail-closed discipline. Then run the tester, mapping the flags through:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json [--functional|--roles|--explore] \
        [--server] [--story <id|title>] [--json <out>]
```
- default → `--functional`; `--roles` → per-role; `--explore` → exploratory crawl.
- `--server` passes through so the tester attaches to the running `/pb:preview` server (never a second one).
- `--story <id|title>` passes through to scope the run.

For each scenario the tester sets `state.protoScreenId = test.start`, performs each `steps[]` action
(`fill` · `click` · `nav` · `submit` · `toggle-password` · `back`) against `#proto-frame`, then verifies
every `expect[]` item (`screen` · `text` · `errors` · `toast` · `no-console-error`). It writes each
scenario's `lastResult { status, detail, ranAt }`.

### 3a · `--security`
Also run the static scanner and fold its findings into the report:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/security_scan.py" registry.json
```

## 4 · Report + exit codes
Print the tester's report verbatim (it mirrors `check.py`: `<SEVERITY> [<CODE>] <where>: <msg>`; `✓ … clean`
when all pass). **Honor the exit codes** across every tool run: `0` = clean, `1` = warnings only, `2` = any
error / failing scenario. If several tools ran, the command's outcome is the **worst** exit seen (a failing
scenario or a security error is a `2`).

## 5 · Render (only with `--render`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
```
Otherwise stop after the report — the written `lastResult` is picked up live by `/pb:preview`.

## NEVER
- NEVER boot a second preview server — reuse the one `/pb:preview` (`--server`) or a single headless run.
- NEVER edit screens / components / logic to make a test pass — tests observe the design, they don't shape it.
- NEVER claim a pass without an actual run — an unexecuted scenario is `untested` (`○`), not `pass`.
- NEVER write anything but `flow.stories[].lastResult` back to the registry.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
