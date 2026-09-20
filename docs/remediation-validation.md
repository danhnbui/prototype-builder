# Remediation validation — v1.11.1 vs v2.0.0, measured on one real project

The remediation was planned against a live pb project at real scale and is validated the same way:
one registry, rendered by two trees of pb, with every number taken from a run rather than from a
claim. The project is **read-only reference** throughout — nothing here modified it, and none of its
content is reproduced in this repo. Both sides work on copies.

| | v1 | v2 |
|---|---|---|
| pb | `bfbc9b2` — v1.11.1, the last release before the remediation | `152d4c5` — v2.0.0 |
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

## The sharper test: does the fork become unnecessary?

Stock-vs-stock is the weaker comparison, because this project never ran on stock pb. It ran on a
hand-patched plugin cache **plus its own copy of `prototype.html`** carrying five hunks. That fork is
the best list anyone has of what pb was missing — every hunk is a capability someone needed badly
enough to maintain a fork for, and one of them says so in its own comment: *"WHY THIS IS CSS AND NOT
A SHELL EDIT."*

| The fork's hunk | v1.11.1 | v2.0.0 |
|---|---|---|
| ERD `origin` tinting — which rows carry over from the existing product | forked | **stock, and wider** — `keep` · `rename` · `adopt`, with a legend (the fork had `keep` only) |
| A flat screen: no tab strip, no synthesised URL, no window frame | forked, via CSS the project could not put in the shell | **stock** — `meta.shell: 'none'`, a third toggle option |
| SheetJS — a `<script src>` hand-edited into the shell | forked | **stock** — `registry.runtime[]` with a `url`, which is the hole D-28 was written to close |
| `test.roles` scoping the scenario list a reviewer sees | forked | **stock** |
| A Mermaid `[[subprocess]]` painted input-purple against a legend promising grey | forked | **stock** — a one-line fix |

**Five of five.** Verified against this project's own data: SheetJS declared rather than injected,
`Browser \| App \| None` in the toggle with nothing emitted under `None`, and the scenario list going
from 3 to 0 as the active role moves off `hr` — the fork's exact behaviour.

Two of these were gaps in this remediation's own work rather than pre-existing ones. `test.roles`
reached `test_run.py` in D-27 but not the shell that shows the list, so the increment was half done;
and the third chrome option was never considered at all, because the fork was read for its *data*
hunks and not its CSS. Both are fixed here. `tests/fork_parity.py` pins all five, so a regression
shows up as "a project would have to fork the shell again" rather than as a silent return to the
status quo.

### And the 1,076 lines of gates beside it

The same project kept six hand-rolled verification gates in `prototype/gates/`, for the same
reason it kept the fork. Checked one by one:

| Gate | What it proves | v2.0.0 |
|---|---|---|
| **G0** `preflight.py` (122) | three toolchain traps that silently produce a broken artifact | trap 1 (the blanket `</` escape) fixed in v1.11.1 and guarded by `tests/render_escape.py`; traps 2 and 3 exist only to police the fork, and go with it |
| **G1** `logic_freeze.py` (161) | every non-render top-level entity is byte-identical | `logic_check.py --freeze`, over `bodyHash` — and with a string/comment/template-literal-aware parser rather than column-0 anchors |
| **G2** `seam_extract.py` (133) | the producer side still emits what the handlers read | `L-DEADSEAM`, which asks the cross-check question instead of diffing a baseline, so it has strictly fewer false-positive modes — the project's own baseline gate missed all 10 of its real dead reads |
| **G3** `has_rules.py` (130) | the `:has()` reveal contract, four failure modes | `L-HAS-R1` … `R4`, ported rule for rule |
| **G4** `role_affordances.py` (325) | (screen, role, selector) → present \| absent | `test.roles` + `present`/`absent` expects, as registry scenarios. D-27 was written from this gate's own diagnosis, down to *"a control that is merely CSS-hidden PASSES `present` and should"* |
| **W0** `token_sweep.py` (148) | every `var(--x)` a body references resolves | **was the one real gap** — now `R-TOKENREF` |

G4 is worth reading in full if you ever wonder whether a gate is worth writing. It opens by
naming exactly what pb could not do — *"`test_run.py --functional` runs every scenario at
`meta.defaultRole` and CANNOT switch role"* — and D-27 is, in retrospect, that paragraph turned
into an increment.

### The gap: `R-TOKENREF`

An unresolvable `var(--x)` makes a browser drop the whole declaration. No error, no console
warning, no lint hit — the element just silently keeps whatever it inherited. pb counted *unused*
tokens and never asked the question that breaks a screen.

The first draft of the rule was wrong in the way this class of rule is always wrong: it resolved
names against the project's tokens alone and reported **every component in the golden fixture and
both demo screens** — all false, because the shell declares 58 custom properties of its own. A
second pass found a third producer: component-scoped properties a body sets and reads itself
(`--pb-stat-tone-bg`), or that a parent sets on a root at runtime (`--pb-tt-max`). And a fallback
changes the question entirely — `var(--x, y)` says `--x` may be unset, so an absent name there is
the design working.

The rule that survived asks two things:

| | verdict |
|---|---|
| no fallback, and nothing sets it — not the tokens, not the shell, not any body | **finding** |
| a fallback, and the token exists but resolves to **empty** | **finding** — a fallback applies only when a property is UNSET, so the declaration is dropped anyway |
| a fallback, and the name is simply absent | not a finding, ever |
| a name composed at runtime, `var(--bg-${tone}-muted)` | counted as information |
| no shell readable | the rule does not run — blind to a producer is worse than absent |

Nine cases in `tests/lint_rules.py`, seven of them a false-positive corpus.

On the real project: **0**. On pb's own golden fixture: **2**, both real — `--space-1` (the ramp
starts at `space-2`) and `--text-xs` (the shell's name is `font-size-xs`), so that component's
padding and error text had been rendering at inherited values the whole time. Fixed here.

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

## File size

Rendered from the same registry by each tree, so the numbers are the change and nothing else:

| | v1 | v2 | |
|---|---|---|---|
| `registry.json` | 927 KB | 946 KB | **+19 KB** — the `logicSrc` pointers and 66 synced `elements[]` |
| `prototype.html` | 4,257 KB | 4,583 KB | **+327 KB** — the derived graph, inlined |
| `design-system.html` | 3,997 KB | 4,025 KB | **+28 KB** |

The prototype carries the graph inline because a hand-off is deliberately **one self-contained file
that works over `file://`** — a side-loaded `logic.json` would not. What it must not carry is data
nothing on the page reads. Three fields were doing exactly that: `handlers[].bodyHash` (the largest
single field at 28 KB — `logic_check --freeze` compares it, the shell never looks at it),
`handlers[].localCalls` and `items[].shellVerbs`. `build_html` now inlines a projection — **50 KB
off every render and every hand-off** — while the tools still get the whole graph. A test asserts
the shell really does not read those three, so the moment it does, this is the place to fix.

New on disk, next to `spec/`:

| | | |
|---|---|---|
| `logic/` | 143 files, **733 KB** | of which **513 KB (70%) is copied prose** |
| `.pb-backups/` | 928 KB | the pre-migration registry — the runner has always kept one |

That 513 KB is the price of the lossless rollback: the migration copies prose rather than moving it,
so it now exists twice. It is also the one number here the project can take back. The advisory
`0009` prints says how: route each piece to `memory/decisions.md` as you touch its component, then
delete the copy. Do that and `logic/` settles at about 220 KB — the derived half plus the two
authored fields.

Whole project: **19.7 MB → 22.2 MB**.

### The documents

| | v1.11.1 | v2.0.0 | |
|---|---|---|---|
| `CLAUDE.md` | 136 | 164 | the router |
| `pb/commands/` | 1,510 | 1,716 | where behaviour is specified |
| `changelog.md` | 601 | 713 | |
| `docs/` | 805 | 1,903 | **+136%, and 1,093 of those lines are this remediation** |

`docs/` more than doubled, and 57% of it is now the three files about one release — the decision
log, the build plan, this validation. The decision log earns its place; it is pb's own why-log. The
build plan does not, any more: it is a plan that has been fully executed, and a completed plan
sitting in `docs/` reads as outstanding work. It now says so in its first line.

### And the log that was never rotating

The project's `memory/decisions.md` is **875 KB across 187 entries**, 20× the next memory file
(`tasks.md` at 41 KB, `constitution.md` at 15 KB). D-21 decided the fix in two halves: stop three
commands writing a file none of them reads, and rotate it by size past 500 KB.

The first half shipped. **The second did not** — while five files went on telling users their glob
must be `decisions*.md` *"because rotation moves older entries."* Documentation for a mechanism
that did not exist, which is worse than either building it or dropping the claim.

`decisions_rotate.py` now does it, and the real log shaped three decisions in the implementation:

- **By each entry's own date, never by position.** That log runs 22 August entries, then 86 July,
  then 78 August. Rotating "the tail" would have archived recent entries and kept old ones.
- **An undated heading is pinned.** Not being able to date something is a reason to leave it alone.
- **Lossless or nothing.** Every file the run touches is backed up, and afterwards the whole
  `decisions*.md` family is read back and compared entry for entry. A mismatch restores everything.

Measured: **875 KB / 187 entries → 497 KB live (89) + 378 KB archived (98)**, every entry
byte-identical. `lint --report` names the command once the log crosses the threshold.

That last property was not free. The first version compared the live file's entries *before*
against the whole family *after*, so a **second** rotation looked like entries appearing from
nowhere — and its abort path then deleted the sibling holding 98 entries it had never written. A
test written for the second-rotation case found it before a user could.

### pb's own source, and the file that holds too much of it

| | v1.11.1 | v2.0.0 | |
|---|---|---|---|
| Python | 5,680 | 8,433 | +48% — two new tools (`logic_extract` 1,067, `logic_check` 508) and `lint_registry` +86% |
| Templates | 7,048 | 8,138 | +15% |
| Commands + docs | 2,693 | 2,918 | |
| Tests | 2,377 | 3,740 | +57% |

The number that matters is not the total, it is the concentration. `prototype.html` alone was
**86% of every template line pb ships**, in one file, with a load-bearing whitespace anchor that
kills every render if a formatter touches it — top risk #1 in the plan.

291 of those lines were `runtime.js`, **pasted in a second time**. That duplication is top risk #3
in the same plan, and this release made it worse: adding the two verbs to both copies took it from
156 lines to 291. `runtime.js`'s own header said *"Kept verbatim in sync with the shell; edit HERE
(the single source)"* — a claim that was only true because a test enforced it.

Both shells now take the runtime through the `/*__PB_RUNTIME__*/` marker, which
`design-system.html` already used. The file goes **7,062 → 6,774 lines**, a whole class of drift
bug goes with it, and the test gets stronger: instead of comparing two copies it asserts the shell
carries the marker and the **rendered** page carries the runtime byte-for-byte.

Removing the duplication immediately exposed something it had been hiding. `logic_extract` learns
the shell's globals by reading `prototype.html`, so the moment `pbUse` moved out, **every composed
body in every project** reported `L-UNDEF: pbUse`. A byte-for-byte diff of the rendered output
against a pre-refactor baseline is what caught it; the test sweep was green either way. The
extractor now reads the shell and `runtime.js` together, which is what the rendered page actually is.

What is left is real: **6,774 lines** in one file, a third of it CSS. Splitting it is a bigger
change than this release should carry — it touches the anchor and every marker — but the
duplication was the part that could be removed without adding risk, so it was.

## Cost

| | v1 | v2 |
|---|---|---|
| Render, cold | 33 ms | 435 ms |
| Render, warm — the preview loop | 33 ms | **55 ms** |
| `prototype.html` | 4,257 KB | 4,583 KB |
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

Sweep at v2.0.0: **21 pass · 3 Playwright skips · 0 fail.**
