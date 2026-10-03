---
description: Explore alternatives. With a component/screen id, write a one-screen direction (job, constraints, locked/free axes, N one-line bets) and get it approved at G-DIRECTION, then write one execution plan per bet and dispatch N pb-explorer agents in parallel; show the results side by side on one compare page at /explore/<id> on the /pb:preview server, and let the user score them against a rubric before anything is promoted (registry untouched). Every stop that shows options ends with that page's browser URL, printed and checked by `explore.py link` — never a file path. With a goal sentence, run the gated discovery pipeline — clarify jobs + IA → discover → diverge (the same direction → plans → executors) → design → build+test → update the documents — stopping at every human gate (G-JTBD and G-IA inside /pb:clarify, G-DIRECTION, G-DESIGN) before anything is written.
---

# /pb:explore <id | "goal"> [--options N] [--goal] [--target]

Two modes, one verb. **Both are human-in-the-loop** — neither decides for the user.

| You pass | Mode | Diverges on | Registry |
|---|---|---|---|
| a kebab-case id that resolves | **A · target** | the render body of a thing that exists | untouched |
| a sentence / goal text | **B · goal** | the approach, before anything exists | proposed, gated |

## 0 · Pick the mode (do this first)

1. `--target` forces **A**; `--goal` forces **B**. Otherwise:
2. `$ARGUMENTS` is a **single kebab-case token** → resolve it against `screens[]` and `components[]`.
   Resolves → **Mode A**. **Does not resolve → STOP** and say the id is unknown. Never fall through to
   Mode B on an unresolved id — that turns a typo into an eight-stage pipeline.
3. `$ARGUMENTS` **contains whitespace** (a phrase or sentence) → **Mode B**.
4. Empty → ask which they want, with one example of each.

## The link — every stop that shows options ends with it

The user compares and rates in their **browser**. So every message that shows the options, asks for
scores, states a verdict, or stops at a gate over them (A3, A4, B4, G-DESIGN, and the IA round inside
`/pb:clarify`) ends with the compare page's URL. The tool produces it; you never type it from memory:
```
python3 "${CLAUDE_PLUGIN_ROOT}/tools/explore.py" --registry registry.json link <id> [--open]
```
`link` finds this project's `/pb:preview` server, which records itself in `.preview/server.json` next
to the registry. If none is running, it starts one in the background. It checks that the compare page
and every option frame load, then prints `http://127.0.0.1:<port>/explore/<id>`. Pass `--open` the
first time a round's options are shown, so the page also opens in the browser. Later stops re-run it
without `--open`.

Put the printed URL **on its own line**, just before the question you are asking. A non-zero exit is
**blocked**: say what failed, fix it, and run `link` again. Never put anything else in its place:
not a file path, not a `file://` URL, not an editor link, and not a page you wrote by hand. The rule
exists because three rounds in a row ended with an editor link to a hand-built `compare.html`, and the
user had to ask twice for something they could open.

---

# Mode A · diverge one render body

Explore design alternatives for **one** target without touching the registry. Spawn N independent
proposals, show them **side by side on one compare page**, let the **user** rate and choose. Only the
pick is promoted; everything else is thrown away. Writes no registry slice and never renders
`prototype.html`.

**The tool does the parts that must not be skipped.** `explore.py` (below, `$T` =
`"${CLAUDE_PLUGIN_ROOT}/tools/explore.py" --registry registry.json`) owns the manifest, the candidate
tree, the render check, the scoring gate, the promote, and the link. The `/pb:preview` server shows the
result at `/explore/<target>` — **the same server and port as the prototype**. There is no other way to
present an exploration: no hand-written preview or compare HTML, no second server, no score table in chat.
A subject the tool cannot render as a registry body is a **page round** (`--pages`, below), not an
exception to this.

## A0 · Resolve the target + open the exploration
```
python3 $T init <id> --options N [--files <other-id>,…] [--host <screen-id>] --intent "<the ask, verbatim>"
```
- `--options N` — how many alternatives (**default 3**). Slots are `opt-1 … opt-N`.
- `--files` — other bodies an option may change with the target (a card **and** the screens that list
  it). Each slot's `overlay` maps every real `renderSrc` to its own candidate copy under
  `render/_candidates/<id>/<slot>/…`, seeded from the live body.
- `--host` — the screen a component is seen on; defaults to the first screen that composes it.
- It records each live body's hash (`baseline`). That is what makes promote refuse a stale pick.
- `--pages` — use this when the subject is **not a registry render body**: the tool's own templates, a
  standalone mockup, or a whole-page direction. The id need not resolve, and there is no `--host` or
  `--files`. Each slot is a folder, `memory/explore/<id>/<slot>/`, holding a self-contained page. The
  slot's `page` in the manifest names the entry, `<slot>/index.html` by default. Point it at another
  file if needed; a `#hash` is allowed. Files the slots share go in `memory/explore/<id>/shared/` and
  are linked as `../shared/…`. The round runs the same steps and is shown on the same compare page:
  the brief, G-DIRECTION, plans, explorers, `check --shots`, rating, the gate and `link`. `promote`
  records the pick and archives the round. **Nothing goes live**: the pick is built into the real
  files after G-DESIGN.

## A1 · Diverge — direction, gate, plans, N executors
The model running this command is the **coordinator**: it writes the direction, gets it approved,
writes one execution plan per option, and dispatches. **N `pb-explorer` agents execute** — one plan
each. Nothing reviews their work but A2: the plan is the contract, and `check --shots` and the rubric
verify the result.

### A1a · Direction (coordinator)
Invoke **`think-direction`** §1–§3. It reads the project instead of asking — the intent, the jobs and
their IA (`ia.jobs[].screens[]`, `ia.layers[]` and `meta.navHub` are constraints; a target no job
serves → **stop** and send the user to `/pb:clarify`) — and writes the direction,
`memory/explore/<id>.brief.md`: the job, the taste position, the hard constraints by rule id, the real
content, what compact and large each answer, the decision points, the seven axes locked or free, and
**N bets, one line each** (whose user, what context, the free-axis values in a few words). Then invoke
**`ref-design-compare`** for the axis contract — the divergence threshold, the generic-tell ban list,
the score sheet and the grades→action mapping.

The bets' free-axis values must differ pairwise on **at least 4 of 7** (mental model · layout ·
navigation · component set · motion · hierarchy · contrast). Do **not** plan N options from one
undifferentiated idea and hope they diverge — independent agents converge, and the result is one
option in N colours. If two bets differ on only 2–3 axes, merge them and use the freed slot for
something genuinely different (`think-direction` §3 says what to do with fewer real bets than N).

### A1b · ▛ G-DIRECTION — human gate ▟
**STOP.** Present the brief itself, not a summary of it: the jobs, the constraints, the locked and free
axes, and the N bets. Ask for approval, edits, or rejection. Silence is not approval. An edit changes
the brief and **re-opens A1a** — the gate is asked again on the new text; a rejection returns to A1a.
No plan exists yet, and none is ever shown here: **the user approves a direction**.

### A1c · Plans (coordinator, after approval)
Write one `memory/explore/<id>/plans/<slot>.md` per approved bet (`think-direction` §5b) — the whole
brief its executor gets. The *creative* half: mental model, layout shape at compact and at large, every
decision-point answer, components by DS id, hierarchy, the real content to show, motion. The *logical*
half: the states table with collision priority, the contract (the same `renderFn` and props, the
`data-*` verbs, handlers and `test{}` targets that must survive), validation, what the slot may change.
And **the anti-brief**: the siblings' axis values, forbidden for this slot ("opt-2 is a table, opt-3 a
feed — this option is neither"). Plans differ creatively *and* logically; a plan that is another plan
with the adjectives changed is a defect — rewrite it before dispatch.

Then fill each option's `label` (one line on the take), `bet` (whose user, in what context) and `axes`
(its free-axis values) in `memory/explore/<id>.json`.

### A1d · Dispatch N × `pb-explorer`
Launch **N `pb-explorer` subagents** via the **Task tool**, concurrently — **one message, N Task
calls**, one per plan. Hand each **only** three paths: its plan, its overlay (the slot's candidate
files, from the manifest's `overlay`; in a page round, its slot folder and `page`), and
`registry.json`. No brief, no sibling plan, no framing from this conversation — what the plan does
not say, the agent would re-guess. `/pb:test` §2b pins its
testers to sonnet at the dispatch site; here the pin is in the agent definition (`model: sonnet`,
`effort: xhigh`), so do not override it. Each edits **only its slot's candidate files**, keeping the
**same `renderFn`** and the same public props (any candidate is a drop-in), **token-only** (no raw
hex/px), lints, and hands back `slot · files touched · one line on the take` — nothing else.

## A2 · Check + look — a gate
```
python3 $T check <id> --shots [--url http://127.0.0.1:<port>] [--converge 0.85]
```
Exit 0 means every option is labelled, differs from the live body, lints, and **renders** in memory
against the real registry. In a page round, it means every option's page exists inside its round's
folder and no two are the same file. In both, every pair of options differs on **≥ 4 of the 7 axes**
(fewer is a failure, not a warning; an axis missing on either side counts as equal). `--shots` writes a desktop and
a phone screenshot per option to `memory/explore/<id>/shots/` — **open and look at every one** before
presenting (`ref-design-compare` §3) — and **fails structural convergence**: two options whose rendered
subtree (tags + classes) is ≥ `--converge` alike are the same layout in different colours. It warns
when the brief or a slot's plan is missing. Non-zero → fix and re-run: an axis failure is the bets'
(back to A1a, which re-opens G-DIRECTION); a convergence failure is the build's (sharpen that slot's
anti-brief and re-dispatch its explorer). **Never** present around a failing check, never relabel axes
to pass it, and never fall back to hand-writing HTML. Exit 3 (no Playwright) is **blocked**, not
passed: say so, and offer `pip install playwright && playwright install chromium`.

## A3 · Present on the compare page — with its link
```
python3 $T link <id> --open
```
It reuses the project's `/pb:preview` server, or starts one; there is one server per project. It checks
that the page and every option frame load, opens the page in the user's browser, and prints its URL.
Give the user **exactly that URL, on its own line**, e.g.
```
http://127.0.0.1:8200/explore/<id>
```
(see *The link*, above). It shows the N options side by side (or one at a time), each live on the
host screen at the project's devices, with its label, bet and axes, and a rating panel: the rubric × options, 1–5 per cell, a note
per criterion, an Average row, and the verdict. Ratings save straight into `memory/explore/<id>.json`.
The live prototype's **Sandbox → Explore** lists the same options.

Swap in or add **1–2 criteria** for what this target's intent said mattered (the brief names them;
edit `rubric[]` in the manifest before sharing the link). Never ask "which do you like?" — a preference cannot be acted on, a
pattern of scores can.

## A4 · The scoring gate, then the verdict
```
python3 $T gate <id>
```
Exit 0 only when every criterion × option has a score. **No verdict before the gate passes.** While
it fails, you are waiting on the user: the message that says so repeats the URL from `$T link <id>`.
The user scores the options, not you or a grader you dispatched. A grader's sheet may go in a note,
but it never fills the cells. Once the gate passes,
read the **pattern**, not the total (`ref-design-compare` §5) and state the verdict from the scores
and notes — naming the winner, noting that two options may legitimately lock for different contexts,
and giving **one sentence per rejected option on what it taught** (the page has a field for each).
End that message with the link again, since the scores behind the verdict are on that page. Do not
decide for them.

**A mixed pick** ("option 1, but improve it like option 2") is **not** a pick. Add it as its own slot —
`python3 $T slot <id> opt-merge --label "…"` — build it, `check` it, and have it rated **beside the plain
pick**. Only a single, rated slot is promoted.

## A5 · Promote the pick, or reject
```
python3 $T promote <id> <slot>        # the pick goes live
python3 $T reject <id>                # nothing chosen
```
`promote` refuses unless the gate passes, and refuses if any live body changed since `init` (another
session edited it — rebase onto the current file; `--force` only on the user's say-so). It backs the
live bodies up to `memory/backups/explore-<id>-<stamp>/`, copies the overlay over them, deletes the
scratch tree and archives the manifest under `memory/explore/_closed/` — the brief and the round's
folder (`plans/`, `shots/`) move beside it. `renderFn` / `renderSrc` are unchanged, so `registry.json`
needs **no** edit; a running `/pb:preview` reloads on its own.

**Either way, keep the owner's reasons — before you promote or reject**, since both move the brief.
Every rejected option's "taught" sentence, and the notes that explain a low row, are rules about this
area: write them under the brief's `## Rules learned`, then run `/pb:clarify` with them so they land
in `ia.rules[]` ("stacked, never a carousel"; "about 150px tall"). A rule written down only in the
chat is a rule the next exploration breaks.

---

# Mode B · the gated discovery pipeline

For a goal that has no component yet — a new feature, a new flow, a revamp. The canonical rules are
**`AGENTS.md` §8–§9**; this is the executable form. Stages run **in order**; sub-agents run in parallel
**within** a stage, never across. The team is the 9-role `pb-*` roster — no ad-hoc agent types.

**Restate the goal first** (§8). One or two sentences, in the user's own terms, shown before any work.
Where your restatement and their request differ, **the request wins**. Write it verbatim to
`memory/prd.md` under `## Goal` — every later stage is checked against *that text*, not against the
previous stage's output.

## B1 · Clarify JTBD + IA — `/pb:clarify` · `pb-clarifier`
Run **`/pb:clarify`** (jobs + IA, with its own two gates). It produces `ia.jobs[]` — `when` / `want` /
`so`, plus `roles[]` and `priority`, the jobs that map to no screen named — and approves them at
**G-JTBD**; then it runs N groupings of those jobs on this engine (`explore.py --ia`, rated at
`/explore/<ia-id>`) and approves one at **G-IA**, which writes `ia.jobs[].screens[]`, the
`ia.layers[]` purposes and `meta.navHub`. (`--ia-options N` sets how many groupings; `--skip-ia`
skips them when the IA is already settled.) **`/pb:clarify` now produces the jobs AND the validated
IA**; B3 and B4 read `ia.jobs[].screens[]` and `meta.navHub` as constraints.

## B2 · ▛ G-JTBD — human gate ▟
**Already passed inside `/pb:clarify`** (B1), which presents every job as `when / want / so`, the
unmapped ones called out, with the open questions, and records the approval. **Never ask the user to
approve the same jobs twice.** Re-open it — re-run `/pb:clarify` — only if the `## Goal` text changed
since it passed. Nothing downstream starts until it has passed; **no document is written yet**.

## B3 · Discover — read-only
Read the current registry slices, `memory/`, the DS reference + `.source.json`. Report what already
covers part of the goal and what conflicts with it. **Produces findings, not a patch.**

## B4 · Diverge — direction, G-DIRECTION, plans, N × `pb-explorer`
Open the exploration first — `python3 $T init <goal-id> --goal --options N --intent "<the goal>"` — or,
when each approach is **built as a page** rather than written as text (a direction for the tool's own
chrome, a whole new surface), `init <goal-id> --pages` (A0). Then run A1's four steps on the approved
jobs, each a **different approach** — which screens, which existing components reused, what is
genuinely new:
- **B4a · Direction** — **`think-direction`** writes the brief: the approved jobs and their IA, B3's
  findings as constraints, the behaviour each approach must keep, and N one-line bets whose free axes
  differ on ≥ 4 of 7 (the **`ref-design-compare`** contract applies here too).
- **B4b · ▛ G-DIRECTION — human gate ▟** — exactly as A1b: the brief, never a plan; silence is not
  approval; an edit re-opens B4a.
- **B4c · Plans** — one `plans/<slot>.md` per approved bet (`think-direction` §5b), anti-brief
  included, naming the one file its executor writes: `memory/explore/<goal-id>/<slot>.approach.md`.
- **B4d · Dispatch** — one message, N `pb-explorer` Task calls, each handed its plan path, its approach
  file path and `registry.json`. The coordinator then copies each approach into its slot's `approach`
  (plus `label`, `bet`, `axes`) — one writer for the manifest. In a page round, each explorer is handed
  its slot folder instead and builds its page there. The coordinator fills `label`, `bet` and `axes`.

The approaches are **rated by the user on the same compare page**: run `python3 $T link <goal-id> --open`
and put the URL it prints in the message. They pass the same `gate` before one is recommended. Where
a target already exists and the question is form rather than approach, use **Mode A** on it instead
of re-deriving it here.

Score the approaches rather than eyeballing them. Compare against the `## Goal` text — never against
each other — and recommend one, with a sentence on what each rejected approach taught. That sentence
is what G-DESIGN presents as "the ones rejected, with why".

## B5 · Design — `/pb:plan` · `pb-planner`
Turn the chosen approach into `memory/tasks.md`: per task **acceptance · skill · agent · deps · slice**.

## B6 · ▛ G-DESIGN — human gate ▟
**STOP.** Present the approach kept **and the ones rejected, with why**, the task breakdown, and
**exactly which documents B8 will change**. Ask for approval, edits, or rejection. This is where the
run usually ends for now, so the message **ends with the compare page's URL** (`python3 $T link
<goal-id>`). That is where the user checks the pick against its scores and the options it beat. Keep
the round open until G-DESIGN is approved, so the link still works. After approval, a page round is
closed with `promote <goal-id> <slot>`.

## B7 · Build + test — `/pb:orchestrate` → `/pb:test` · `pb-tester` → `pb-reviewer`
Dispatch the plan in dependency waves. `/pb:orchestrate` already gates each wave on `pb-tester` +
`pb-reviewer` and stops the loop on a red gate — do not re-implement that here.

## B8 · Update the documents
**Only now.** `ia.rules` (logic rules) · `memory/prd.md` · `memory/spec.md` · `logic/**` contracts · an
entry in `memory/decisions.md` recording both gate approvals · `DESIGN.md` when an invariant moved.

## NEVER
- NEVER hand-write a preview or a compare page, and NEVER start a second server or port for an
  exploration — options are rendered by `explore.py` / `serve.py` and shown at `/explore/<id>` on the
  `/pb:preview` server. Three loose HTML files is the failure this command exists to prevent. A
  subject `explore.py` cannot render goes in a page round (`init --pages`), not in a hand-built page.
- NEVER end a message that shows options, asks for scores, states a verdict or stops at G-DESIGN
  without the URL `explore.py link <id>` printed, on its own line. NEVER offer a file path, a `file://`
  URL, an editor link or a hand-built page in its place. If `link` fails, the link is blocked: say so.
- NEVER present a verdict before `explore.py gate` passes, and NEVER promote without it.
- NEVER promote a mixed pick — it becomes its own slot and is rated first.
- NEVER `--force` a promote over a concurrent edit without the user saying so.
- NEVER edit `registry.json` in Mode A — it diverges bodies only; the registry stays clean.
- NEVER change a candidate's `renderFn` or props — every option must be a drop-in for the target.
- NEVER leave `render/_candidates/<id>/` behind after a decision — `promote` / `reject` clean it, always.
- NEVER pick for the user, in either mode — present and wait.
- NEVER ask "which do you prefer?" — score against the rubric (`ref-design-compare` §4). A preference
  is not actionable; a pattern of scores names the thing to change.
- NEVER present a candidate you have not rendered and looked at, at both widths — `check --shots`, then open the images (§3 of the contract).
- NEVER launch N agents on one undifferentiated brief — assign the axes first, or they converge.
- NEVER launch the diverge step without a direction brief — `think-direction` writes
  `memory/explore/<id>.brief.md` first, or every option re-guesses the rules, content and states the
  project already settled.
- NEVER show an execution plan at G-DIRECTION — the user approves a direction.
- NEVER launch `pb-explorer` before the gate passes and a plan exists for its slot.
- NEVER add a self-check or reflection step to the executors — the plan is the contract.
- NEVER write a document in Mode B before **both** gates pass. B1–B7 may write the registry slices the
  plan calls for; they may not rewrite the documents that record intent.
- NEVER treat an unresolved id as a goal (§0.2), and never re-enter Mode B from inside B4.
- NEVER carry an approval past the artifact it approved — re-running a stage **re-opens its gate**, and a
  rejection returns to the stage that produced it, not to the start.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
