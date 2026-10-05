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
| `--attach [URL]` | **Transport, not a mode.** Attach to a running `/pb:preview` you name (bare `--attach` discovers it from `.claude/launch.json` or `127.0.0.1`). Composes with every mode. Since v2.2 this is no longer needed to reuse the preview — see *Transport* below |
| `--isolated` | **Transport, not a mode.** Boot a private server for this run even when the project's preview is running. Cannot be combined with `--attach` |
| `--strict` | Promote the pre-flight lint to strict and **fail-closed** — stop before running anything |
| `--no-delegate` | Answer the plan in **this** context instead of dispatching subagents (§2b) — stamps the report self-graded |
| `--save` | Also write the drift report to `memory/drift-reports/<YYYY-MM-DD-HHMMSS>.md` |
| `--render` | After the run, regenerate `prototype.html` so the glyphs land in the snapshot |

`$ARGUMENTS` may also name a single principle (e.g. `principle #3`) to scope the drift audit.

**Transport (v2.2).** `test_run.py` **reuses this project's running `/pb:preview`** when there is one
(it prints `reusing the running preview at <url>`) and boots a private server — stopped at the end of
the run — only when there is none. `--isolated` forces the private server; `--attach [URL]` is the
explicit form and behaves as it always did. **Browsers:** every one goes through `tools/browser.py`,
which allows **3 headless browsers at once on the machine** (`PB_BROWSER_SLOTS`, default 3, `0` = no limit;
`PB_BROWSER_WAIT`, default 120 s, after which it proceeds anyway with a `note:` — the limit never makes
a test fail). The default battery runs its three browser modes (§3 · §4 · §5) as **one**
`test_run.py --all`: one transport, one browser, a fresh context per mode. Canonical text:
`CLAUDE.md` § *pb bounds its own footprint*.

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

## 2a · The test plan — every check as a yes/no, written before anything runs

Before a single check executes, enumerate what this run will assert and write it to
`memory/test-plans/<YYYY-MM-DD-HHMMSS>.md`. That file is the **plan of record**: §11 reconciles the
report against it item by item, so a check cannot quietly go missing between here and the verdict.

**One item = one test case.** A scenario, a role × gate, a screen's server pass, a scan class, a
principle sweep. Never split an item per `expect[]`, nor per role — the evidence line carries which
assertion failed and which role saw what — and never bundle two test cases into one item. The
granularity test: *one item is one thing that can be separately broken.* Ten gated screens across five
roles is **ten** items, not fifty; a scenario with four expects is **one**.

**The question belongs to the lane, not the item.** Every item in a lane asks the same thing, so state
it **once** in the lane's heading and make the items rows. A plan is a handful of small tables, not a
page of repeated sentences.

```markdown
## F · Functional
**Running the steps from `test.start`, did every `expect[]` item hold?**

| # | Scenario | Answer | Evidence |
|---|---|---|---|
| F1 | Đăng nhập sai mật khẩu | | |
| F2 | Gửi KPI để duyệt | | |
```

- **`#`** — lane letter + number: `F` functional · `H` freshness · `R` roles · `S` server ·
  `X` security · `D` drift · `C` coherence. Stable for the run; the summary quotes them back.
- **the subject column** — the addressable thing under test, named the way the project names it: a
  scenario title, a screen id, a scan class, a principle. One column, no restating of the lane.
- **extra columns only when the row needs data to be self-contained** — the recorded digests for `H`,
  the declared `roles[]` for `R`. Never a column that repeats the question.
- **`Answer` / `Evidence`** — blank in the plan; the answering agent fills both.

**Evidence is one line — the observation, not a narrative.** On a `no`, what was seen instead
(`expect[1] "Mật khẩu không đúng" absent`). On a `yes`, the shortest proof it was actually looked at
(`4 expects held`). On `blocked`, the blocker (`preview 8200 refused`). Never a paragraph, never a
recap of the steps, never advice.

### A question is admissible only if
1. It opens with **Does · Did · Is · Are · Was**, and has exactly two truthful answers.
2. It names the **one observation that settles it** — a screen id, a selector, a literal string, an
   exit code, a file path, a function name.
3. It can be answered **without knowing what the product is for**. Nothing in an item may require
   `memory/spec.md`, `memory/plan.md`, `memory/decisions.md`, or this conversation.
4. **`yes` means the check held.** An item whose natural phrasing inverts that gets re-phrased, never
   annotated — a plan with mixed polarity cannot be tallied mechanically, and a mis-tally is exactly
   the failure this plan exists to prevent.

### Never an open question
The plan is a checklist, **never a list of things to think about**. Reject and rewrite any item that:
- opens **Should · Could · Would · Consider whether · Is it correct that · Does it make sense** — the
  answer is an opinion, and an opinion is the thing delegation is here to remove;
- can truthfully be answered *it depends* · *partially* · *N/A* · *probably*;
- asks whether something is **missing, sufficient, or worth adding** — that is coverage design, and it
  belongs to `/pb:plan --flow`, not to a test run;
- joins two observations with **and** / **or** — split it into two items;
- asks the agent to **rate, rank, prioritize or recommend** anything.

A check that cannot be phrased as an admissible question produces **no item**. §8 is exactly that case:
project health ranks, it never returns a verdict, so it contributes nothing to the plan and prints
unchanged.

### `blocked` is not a third answer
An item that was never reached — no Playwright, the preview unreachable, the target screen never
rendered — is **`blocked`**, and its evidence names the blocker. It is the *absence* of an answer, not
a middle one: it never counts toward a pass, and it is never softened to `yes` because the check
"probably would have held".

### What each lane contributes
| Lane | One item per | The question (`yes` = held) |
|---|---|---|
| §3 functional | scenario carrying a `test{}` block | Running the steps from `test.start`, did **every** `expect[]` item hold? |
| §3 freshness | scenario carrying a `lastResult` | Does `itemHash` for each named screen still equal the digest quoted in this item? |
| §4 roles | gated screen or element | Did **exactly** the roles in its `roles[]` set reach it — no more, no fewer? |
| §5 server | screen, twice | Did it render with no console error? · Did every `data-nav`/`data-go`/`data-redirect` target it declares resolve to a real screen id? |
| §6 security | scan class (secrets · PII · `</script>` · injection · external call) | Did the scan finish with **no** finding in this class? |
| §7 drift | numbered principle | Is every screen, component and logic note free of any contradiction with this principle? |
| §9 shell · §10 DS | the single comparison each makes | Does the stamp · the clone match? |
| §8 health | — | **none** — it ranks, it does not judge |

### The whole file
Two header lines, then one section per lane. Nothing else — no preamble, no restatement of what
`/pb:test` is, no notes to the reader.

```markdown
# Test plan · 2026-09-20 14:32:07
atlas · 6 lanes · 41 items · not yet run

## F · Functional
**Running the steps from `test.start`, did every `expect[]` item hold?**

| # | Scenario | Answer | Evidence |
|---|---|---|---|
| F1 | Đăng nhập sai mật khẩu | | |

## H · Freshness
**Does `itemHash` still equal the digest recorded here?**

| # | Scenario | Recorded | Answer | Evidence |
|---|---|---|---|---|
| H1 | Đăng nhập sai mật khẩu | dang-nhap=a3f1c2d4 · trang-chu=9c2b7f01 | | |

## R · Roles
**Did exactly the declared roles reach it — no more, no fewer?**

| # | Gated item | Declared | Answer | Evidence |
|---|---|---|---|---|
| R4 | screen `hieu-suat-phong-ban` | manager, hr | | |

## D · Drift
**Is every screen, component and logic note free of any contradiction with this principle?**

| # | Principle | Answer | Evidence |
|---|---|---|---|
| D2 | 2 · "Every destructive action is confirmable" | | |
```

Digests are quoted to **8 hex chars** — enough to differ, short enough to read in a table.

§7 is why this command delegates at all. *"Does this contradict principle N?"* is the one genuinely
judged question in the run, and it is binary in the only way that matters: whether a contradiction was
**found**. The evidence line carries the list — file, excerpt, principle — so a `no` is a finding, not
a feeling.

The freshness lane's **`Recorded` column** exists for one reason: §2b forbids an answering agent from
opening `lastResult` at all, and an item that sent it there to fetch a digest would walk it straight
past the status it must not see. An item carries what it needs; it never sends the agent to find it.

## 2b · Delegate — sonnet subagents answer the plan; this context does not

The context that authored a design is the worst available judge of it: it already knows what every
screen is *meant* to do, so it reads the intent and scores the intent. Every item is therefore answered
by a **fresh agent that has never seen this conversation**.

Launch **`pb-tester` subagents** via the **Task tool** with `model: sonnet`, **all in one message** so
they run concurrently:
- **One agent per lane** that produced items — **except the three browser lanes (§3 functional · §4
  roles · §5 server), which share one agent** when each holds ≤25 items: that agent runs
  `test_run.py … --all` once (one transport, one browser) and answers all three lanes from its three
  labelled sections. Parallel browser agents are what filled a machine with headless Chromiums.
- A lane over **25 items** splits — by story (§3/§4), by screen (§5), by principle (§7) — into chunks
  of ≤25, one agent each. Chunked browser lanes each run their own single-mode command (§3–§5); all of
  them reuse the one preview, and the 3-browser limit makes the surplus wait rather than pile up.
- **Never more than 8 agents in one run.** Past that make the chunks bigger, not the fan-out wider.

`pb-tester` ships `model: inherit`, so the pin belongs at the dispatch site — it also runs
`/pb:orchestrate`'s acceptance gate, where inheriting is right. If the host cannot pin a model, dispatch
anyway and say so: sonnet is the cost choice, but the **fresh context is the load-bearing half**.

**One preview for every lane.** Testers reuse the running preview by default, so **never** hand one
`--isolated` or tell it to start a server. When no preview is running and more than one browser agent
will be dispatched (chunked lanes), start one first — `/pb:preview` §1 — so they share it instead of each
booting a private server; it stops by itself after 30 idle minutes.

**Hand each agent exactly this and nothing more:** the absolute path to the plan file and **the item
ids it owns**; the path to `registry.json` plus the preview URL when one is running (otherwise nothing:
`test_run.py` boots a private server by itself); the literal command(s) for its lane, copied from §3–§10; and the skill name `sandbox-test`.

**Never hand an agent:**
- any framing from this conversation — what changed, what was just built, what is expected to pass;
- `memory/spec.md`, `memory/plan.md`, `memory/decisions.md`, `memory/tasks.md`. A tester that reads the
  intent stops testing the product and starts confirming the plan;
- the **existing `lastResult` values** — *"it was green last time"* is the same bias arriving by a
  different door;
- any hint of the answer you expect, in the prompt or in the item text.

**Each agent returns one row per item id — `<id> · yes | no | blocked · <evidence>` — and nothing
else.** No recommendations, no proposed fixes, no summary of its own: what to do about a `no` is the
user's call informed by §11, not a tester's output.

**`--no-delegate`** answers the plan in this context instead. The tool lanes are unaffected — a
Playwright assertion holds no opinion — but every §7 item, and any item the tools could not settle, is
stamped `⚠ self-graded — answered in the context that authored the design`. Use it when subagents are
unavailable, never to save a round trip on a design this session just wrote.

---

> **§3–§10 are the lanes.** They define *what each check is and how it runs*; §2b decides *who runs it* —
> normally a delegated agent holding only its slice of the plan, not this context. Read them as the brief
> handed to that agent.

## 3 · Authored scenarios
Invoke the **sandbox-test** skill for the `test{}` vocabulary, target resolution, and the
fail-closed discipline. The default battery runs §3, §4 and §5 together:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --all [--attach [URL] | --isolated] [--story <id|title>] [--json <out>]
```
It prints each mode under `── test_run.py --all · <mode> ──`, ends with
`test_run.py --all: functional exit N · roles exit N · server exit N`, and exits with the **worst** of
the three (3 if it could not run at all). `--all` cannot be combined with a mode flag; `--json` writes
`{"mode": "all", "modes": {…}}`. A mode flag narrows the run to the single-mode commands below, whose
output and exit codes are unchanged. §3:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --functional [--attach [URL] | --isolated] [--story <id|title>] [--json <out>]
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
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --roles [--attach [URL] | --isolated]
```
Walks every screen per role, asserting gated screens and elements are visible only to permitted roles
(an `isAdmin` role bypasses), then runs the authored scenarios per role. Visibility sampling alone
cannot tell you whether a role's flow works — and a role-gated write control carries no `data-roles`
attribute at all, because the render body omits it entirely. Assert those with `present` / `absent`
expects: they test **presence, not visibility**, so a CSS-hidden element still counts as present.

## 5 · Server health
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/test_run.py" registry.json --server [--attach [URL] | --isolated]
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
decisions-log size), a **`resources` block** (the largest registry key, backups, open and closed explore
rounds, `server.log`, orphan candidate folders, whether a preview server is running and for how long it
has been idle — a crossed threshold ranks a line naming the fix, usually `/pb:clean`), and a "fix first"
list. Thresholds come from an optional `memory/doctor.json`.

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

## 11 · Report — reconcile against the plan, then one verdict
Fill the returned rows into the plan file **in place**, so what is left on disk is the completed
checklist rather than the blank one. Each tool's own report is printed verbatim (they mirror
`lint_registry.py`: `<SEVERITY> [<CODE>] <where>: <msg>`) **only where a lane failed** — a clean lane
is its `✓` row in the table, not a second copy of the tool's output.

**What lands in the chat is short.** One header, the failures, one verdict. The plan file on disk holds
every row; the chat does not repeat it:

```
Test plan · 2026-09-20 14:32:07 · 41 items · 38 held · 2 failed · 1 blocked

✗ F2  Gửi KPI để duyệt          expect[1] "Đã gửi" absent; frame showed "Lỗi hệ thống"
✗ R4  screen hieu-suat-phong-ban  supervisor reached it; declared manager, hr
⊘ S7  screen bao-cao-nam          preview 8200 refused

worst: functional (exit 2) · full plan: memory/test-plans/2026-09-20-143207.md
```

Held items are **not listed** — they are the count and the file. Only a `no` or a `blocked` earns a
line, because a report that prints 38 successes buries the three things worth reading.

**The reconciliation rules are what make that tally worth trusting:**
- **Every item id in the plan gets exactly one answer** in the completed file. N items, N answers —
  the counts match or the report is wrong. The chat shows the failures; the file shows all of it.
- **An item no agent answered is `blocked`**, evidence *"no agent returned a row"*. Never dropped,
  never assumed.
- **You may not overturn a `no`.** Believing an answer is wrong is not grounds to change it: add a
  **new** row to the plan, dispatch a fresh agent, and show **both**. The coordinator's disagreement is
  evidence, not an edit.
- **Do not rewrite evidence.** Quote it, or truncate it with an ellipsis — never paraphrase it into
  agreement, and never expand it into prose.

Honor the exit codes across every tool: `0` = clean, `1` = warnings only, `2` = any error or failing
scenario, `3` = **could not run** (no Playwright, no reachable preview). The command's outcome is the
**worst** exit seen — but treat `3` as *unknown*, never as a pass: a check that did not happen is a
different thing from a check that succeeded. A `no` on a §3–§6 item → **2**; no `no` but any
`blocked` → **3**.

§7–§10 are **advisory**. They report and rank; a `no` there lands in the tally but never sets a failing
exit on its own.

## 12 · Render (only with `--render`)
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/render.py" registry.json \
        "${CLAUDE_PLUGIN_ROOT}/template/prototype.html" prototype.html
```
Otherwise stop after the report — the written `lastResult` is picked up live by `/pb:preview`.

## NEVER
- NEVER boot a second preview server — `test_run.py` reuses this project's running `/pb:preview` by
  default; `--isolated` is for a run that must not touch it, and it stops its own server when done.
- NEVER hand-write a Playwright script, start `serve.py` with `&` / `nohup`, or `kill` a preview —
  `CLAUDE.md` § *pb bounds its own footprint* (`shot.py` to look, `serve.py --stop` to stop).
- NEVER edit screens / components / logic to make a test pass — tests observe the design, they don't shape it.
- NEVER claim a pass without an actual run — an unexecuted scenario is `untested` (`○`), not `pass`.
- NEVER write anything but `flow.stories[].lastResult` back to the registry, and never touch
  `prototype.html` outside `--render`.
- NEVER auto-fix drift — surface it; the user decides.
- NEVER silence a contradiction because it seems minor — surface everything; the user judges severity.
- NEVER scope the drift audit to fewer than all three trio surfaces unless the user explicitly asks.
- NEVER put an open question in the plan — no "should", no "is this sufficient", nothing answerable
  *it depends*. A checklist that asks for an opinion has stopped being a test plan.
- NEVER answer the plan from this context while subagents are available (`--no-delegate` is the
  explicit, stamped exception) — the context that wrote a design cannot independently grade it.
- NEVER hand a delegated agent the spec, the plan, the decisions log, the prior `lastResult`, or any
  expectation about how an item should come back.
- NEVER drop, merge or re-word an item between the plan and the summary, and never overturn a returned
  `no` — dispatch a fresh agent and show both answers.
- NEVER record a blocked item as a pass.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed
> with its core intent — never silently skip the step.
