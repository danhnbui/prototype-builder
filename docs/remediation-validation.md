# Remediation validation — v1.11.1 vs v1.12.0, measured on one real project

The remediation was planned against a live pb project at real scale and is validated the same way:
one registry, rendered by two trees of pb, with every number taken from a run rather than from a
claim. The project is **read-only reference** throughout — nothing here modified it, and none of its
content is reproduced in this repo. Both sides work on copies.

| | v1 | v2 |
|---|---|---|
| pb | `bfbc9b2` — v1.11.1, the last release before the remediation | `152d4c5` — v1.12.0 |
| project | untouched, schema 10 | the same copy, after adopting the new setup |
| served | `:8300` | `:8200` |

v1.11.1, not v1.11.0, is the honest baseline: **v1.11.0 rendered this project blank on both routes**
(the `</` escape mangled a `/</g` regex literal in 17 bodies — D-06/D-07). Comparing against a blank
page would flatter every number below.

**Adopting the setup is three commands**, in this order:

```
/pb:update-version --apply                 # schema 10 → 11 · 126 contracts written, ia + runtime[] seeded
lint_registry.py registry.json --sync-elements   # 66 appended, 0 removed
logic_extract.py . --contracts             # 143 contracts refreshed, 17 newly pointed at
```

Nothing was hand-edited. The project's own files were not rewritten: the migration **copies** prose
and leaves the original in place.

## What the two versions produce

| Measured on the same registry | v1 | v2 |
|---|---|---|
| Console errors, either route | 0 | 0 |
| Design-system components that cannot render a demo | **9** (12 failures) | **0** |
| Demo surface | the chrome's own dark stage | the project's surface, ink derived at WCAG AA |
| Link from the prototype to the design-system site | absent | present |
| UX Design sub-views | none | 4 — Logic · IA · User Flow · Test Cases |
| Handlers the Logic view can trace | — *(no such tool existed)* | **432**, incl. 145 shared, 8 saves |
| Store slices, with per-slice readers and writers | — | **14** |
| Navigation layers derived from the code | — | **10** |
| Reads of a DOM handle nothing produces | — | **10** |
| Data tab: search | none | one box, rendered once, repainting only the table host |
| Data tab: sortable column headers | 0 | **64** |
| Data tab: rows tinted by `origin` | 0 | **84** |
| Data tab: tables / rows | 16 / 200 | 16 / 200 *(unchanged, as intended)* |

The nine components that could not demo were all collection-taking —
`(props.people \|\| []).map is not a function` and eight more of the same shape. `defaultProps()` had
no notion of an array prop, so it handed the two-character string `'[]'` to a body that called
`.map` on it. The prototype never hit this: there a parent passes real props through `pbUse`.

## Lint: the count went UP, and that is the improvement

| Code | v1 | v2 | |
|---|---|---|---|
| `R-COMPOSE-MATCH` | 65 | 56 | `--sync-elements` cleared the screen half (9); the component half is hand-declared by design |
| `R-NEST-HINT` | 12 | 3 | 9 were noise; of the survivors, 3 previously pointed at the *wrong* component |
| `R-COMPOSE-TEXT` | 17 | 17 | untouched |
| `R-PX` | 2 | 2 | untouched |
| `R-PROPTYPE` | — | **24** | a new rule — each is a component that cannot demo and ships wrong docs |
| **total warnings** | **96** | **102** | |

Six more warnings, and the project is in better shape: 24 real defects that were invisible are now
named, and 9 wrong hints are gone. A lint count is not a score. `--report` exists because at ~100
findings a flat list is unreadable — it groups by code, ranks by item, and names what to fix first.

`logic_check.py` has no v1 equivalent at all: **0 errors, 10 warnings, 24 notes** on this project —
10 `L-DEADSEAM` (a handler reads a DOM handle no body and not the shell produces), 23 `L-HAS-R4` and
1 `L-HAS-R3`, both informational. The `:has()` rules were left alone deliberately: W1 measured **0**
R1/R2 violations across 222 uses, so the mechanism works and a verb replacing it would be a downgrade.

## Cost

| | v1 | v2 |
|---|---|---|
| Render, cold | 33 ms | 435 ms |
| Render, warm — the preview loop | 33 ms | **55 ms** |
| `prototype.html` | 4,257 KB | 4,632 KB |
| Reading one large screen slice | 80,301 B | 80,301 B → **25,220 B** with `--no-prose` |

Deriving the logic graph parses every render body, which costs 367 of those 435 ms. It depends on
exactly one thing — those files — so it is cached on their fingerprint. The preview server
re-renders on every registry save, and the common edit (a prop, a label, a token) now pays 55 ms
rather than 435. A body edit re-derives, as it must.

So the standing cost of two new derived views is **22 ms per preview reload and 375 KB of artifact**.
The budget test covers the whole pipeline at 1,500 ms.

## What the migration is worth

126 contracts written, 143 after the first refresh. The derived half —
`seam`, `handlers`, `disclosure` — is rewritten every run and cannot go stale. The authored half is
two fields, and they are the two a tool cannot supply: `writes[]`, because derivation traces reads
but the mutations happen inside store helpers, and `affordances[].why`.

The rollback is the part worth proving. `--apply` then back down to 10, and the project is
byte-for-byte what it was — `prototype.html` included on the second round trip. Two fixes were
needed to get there, both pre-existing:

- **`/pb:update-version` escaped every non-ASCII character it wrote.** On a project with
  non-English content that rewrites every line that has any: 900 KB → 1.06 MB, for a migration that
  changed 126 keys. It also made a lossless rollback impossible to demonstrate by diffing.
- **A sidecar edited since the migration is kept, not deleted.** Rolling a schema back is not a
  reason to throw away someone's `writes[]`.

The first `--apply` leaves one byte of difference: a trailing newline the runner adds and the
project's original file lacked. Every round trip after that is exact.

## What was not adopted, and why

`registry.runtime[]` is shipped and tested but **not applied to this project here**, because doing so
means moving 2,567 lines out of three fake components — a code change the project's owners make, not
a migration. The three are named in D-28. The two runtime verbs are likewise available and unused:
this project's four wizard copies keep working exactly as they did, since nothing was removed.

## Reproducing this

```
git worktree add /tmp/pb-before bfbc9b2 --detach
cp -R <project> /tmp/before && cp -R <project> /tmp/after
cd /tmp/after && python3 <pb>/pb/migrations/migrate_runner.py --apply \
  && python3 <pb>/pb/tools/lint_registry.py registry.json --sync-elements \
  && python3 <pb>/pb/tools/logic_extract.py . --contracts
python3 /tmp/pb-before/pb/tools/serve.py /tmp/before/registry.json --port 8300 --no-open
python3 <pb>/pb/tools/serve.py          /tmp/after/registry.json  --port 8200 --no-open
```

`serve.py` resolves its shells relative to its own `__file__`, so the before-tree renders through the
old templates and any difference is the change itself.

Sweep at v1.12.0: **21 pass · 3 Playwright skips · 0 fail.**
