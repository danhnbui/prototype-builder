## Breaking: 24 commands are now 12, and the old names are gone

This is the only reason 2.0.0 is a major. The retired names were **deleted, not aliased** — an old
name now reports that no such command exists.

| Retired | Run instead |
|---|---|
| `/pb:flow` · `/pb:sync-flow` | `/pb:plan --flow` |
| `/pb:data` · `/pb:sync-erd` | `/pb:plan --data` |
| `/pb:check-drift` | `/pb:test --drift` |
| `/pb:validate` | `/pb:handoff --tier=host` |
| `/pb:preview-ds` | `/pb:preview`, then the `/design-system` route |
| `/pb:build-check-design-system` | `/pb:build` — now §3a of the loop, automatic |
| `/pb:build-figma-handoff` | `/pb:handoff` → mode 3 (Figma) |
| `/pb:handoff-close` · `/pb:hand-off` | `/pb:handoff` → mode 1 (everything) |
| `/pb:handoff-dev` | `/pb:handoff` → mode 2 (engineering) |

Nothing in your project stores these names, so the move is mechanical.

### Upgrading takes about five minutes

**→ [docs/upgrade-to-2.0.md](../blob/main/docs/upgrade-to-2.0.md)** — the rename table above, plus
`/pb:update-version` (dry-run first) to bring `registry.json` to schema 12, and `/pb:build --render`
so your prototype stops showing the old shell. `--rollback` restores the pre-migration backup if
you need it — it is a file restore, so use it before building on top.

No registry field is deleted by this upgrade.

---

## What's new

**`/pb:test` plans the run, then delegates the grading.** A test run now writes a yes/no plan to
`memory/test-plans/` — one item per test case, each a binary question where *yes* means the check
held — and hands it to `pb-tester` subagents that never saw the design being built. They get the
plan and nothing else: no spec, no decisions log, no prior result, no framing from the session that
authored the thing under test. Every item is reconciled back, none can be dropped, and a returned
`no` cannot be overturned. `--no-delegate` self-grades and stamps the report as such.

**A trade-off is stored as the rule it always was** (schema 12). `meta.tradeoffs[]` entries become
`ia.rules[]` rules carrying the `decision{}` they were made by, so a trade-off lives beside the other
rules in UX Design → Logic instead of on a tab of its own. Migration `0010` does this and is
reversible.

**UX Design is five segments** — Logic · Information Architecture · User Flow · Test Cases ·
**Content**, the last a glossary over the canonical wording for every action, status and message,
including what a thing is deliberately never called.

**`/pb:build` keeps `flow` and `erd` in sync.** After a patch that touches a screen, a component or
logic, the build loop reconciles both slices in the same turn — insert, delete, re-point, never
regenerate. No Sync button, no second command. Cosmetic tweaks skip it, as they skip the gate.

**`/pb:explore` scores alternatives against a rubric** instead of asking which one you like.

**The logic contract** gets a home of its own at `logic/<kind>/<id>.json` — derived `seam`/`handlers`/
`disclosure` alongside the hand-authored `writes[]` that static analysis cannot infer.

## Fixes

- `clone_ds.py` merges and diffs tokens leaf-wise, so a nested DTCG document no longer merges
  all-or-nothing (it previously reported `+1 added` for ~110 tokens).
- `registry.runtime[]` modules are in scope for render bodies rather than undefined.
- The render-body escape is narrowed to `</script` only — a regex literal like `/</g` is no longer
  mangled.

## Known issues

- **A design system whose token `$value`s are `null` clones with a `✓`** while both resolvers
  silently drop the dead tokens, leaving a render that falls back to shell defaults and looks
  plausible. Measured at 68 tokens on a real export. Unowned.
- `staleness`, `meta.tradeoffs[]` and `meta.others` are **emptied, not removed**. This major does not
  spend itself on deleting them; a later one can.
- `--tier=hardened` (idiomatic / DS-integrated export) is still deferred.

## Install

```
/plugin marketplace add danhnbui/prototype-builder
/plugin install pb@product-builder
```

Restart Claude Code afterwards. Python 3 is the only requirement.
