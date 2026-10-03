---
description: Capture User Insights into the Project Summary tab; the jobs each role needs done, approved at the G-JTBD gate; the information architecture — N genuinely different groupings of those jobs, authored by the coordinator, scored on the /pb:preview compare page and chosen at the G-IA gate (the screens per job, the layer purposes, the nav hub); and the rules behind contested UI decisions into UX Design -> Logic. Appends each decision to memory/decisions.md. Replaces the v0.4.0 after_clarify hook (folded into this command body).
---

# /pb:clarify [--ia-options N] [--skip-ia]

Capture **User Insights**, the **jobs** each role needs done, the **information architecture** that
places those jobs, and the **rules** a contested UI decision produces. Insights land in the
Project-Summary tab; jobs and the IA in **UX Design → Information Architecture**; each rule in **UX
Design → Logic → Rules**, carrying the decision it was made by (D-33). All of it writes the registry
and the decision log **from this body — no hook**.

**Two human gates, in order: ▛ G-JTBD ▟ (the jobs), then ▛ G-IA ▟ (the grouping).** Each is blocking
and presents the artifact, not a summary of it (`AGENTS.md` §9, *What makes a gate real*). Silence is
not approval. When `/pb:explore` Mode B runs this command at B1, the G-JTBD below is the one its B2
names — ask it once, here.

## Flags
| Flag | Effect |
|---|---|
| *(none)* | §1 → §1b → **G-JTBD** → §1c → **G-IA** → §2–§4 |
| `--ia-options N` | How many groupings §1c authors (**default 3**, at least 2) |
| `--skip-ia` | Jobs only: §1c and G-IA do not run and the chosen IA stays as it is — for when the IA was validated already and only the insights, a job's wording or the rules changed. An approved job no screen serves is printed with its one-job placement, `/pb:plan --ia <job-id> --into <screen-id>` |

## 1 · User Insights
Capture — from the user, research, or stated assumptions:
- `quantitative` — any numbers (conversion, drop-off, survey n).
- `researchSummary` — what users said / did.
- `executiveSummary` — the one-paragraph takeaway.

### 1a · Emphasis marks — a long text needs a hierarchy
The Project Summary renders its prose with `pbRichText` (`prototype-builder.md` → *Rich text*), so what you
write in `meta.userInsights.*` and `meta.overview.objectives` (and a principle's `body`) can carry marks.
Numbers are already bolded for you (`11,042`, `38%`, `12 ha`); add the marks a reader would underline:

| Mark | For | Limit |
|---|---|---|
| `**…**` | a key claim or the figure that carries it | about one per sentence, at most |
| `==…==` | **the one thing to remember** in the field | **at most once per field** |
| `{-…-}` | a **problem** — a pain, a risk, a gap | as the text warrants |
| `{+…+}` | an **improvement** — a gain, a fix, a result | as the text warrants |
| `*…*` | a term or a quote, in emphasis | sparingly |

- **Never change the wording.** A mark wraps words already there; it adds, rewords and drops nothing. If a
  sentence reads differently with the marks stripped, you changed it.
- **No more than about one mark per sentence.** A paragraph that is mostly marks has no emphasis left.
  Plain sentences stay plain.
- Use `{-…-}` for a problem and `{+…+}` for an improvement, never the other way round and never for
  decoration; the colours carry the meaning.
- Bullets (`· `, `- `) and a blank line between paragraphs are the other structure: write a list of three
  findings as a list, not a run-on sentence.
- A mark closes on the line it opens on; an unbalanced one prints literally.

## 1b · Jobs — what each role needs done (`ia.jobs[]`)

The Information Architecture view is only as good as its job list, and this is the step in the default
pipeline that writes it (`CLAUDE.md` names `/pb:clarify` → `ia.jobs[]`). `/pb:init` §1b may have seeded
some already; **refine those in place — never add a second job saying the same thing.**

**Source.** `memory/prd.md`, `memory/spec.md`'s user stories, and the insights above. Draft the jobs,
then confirm them with the user a few at a time. Each one is three fields, never one sentence:

```json
{ "id": "j01", "roles": ["hr"], "priority": "P1",
  "when": "a new unit is created or the previous cycle just closed",
  "want": "create a review cycle for that unit",
  "so":   "the review calendar never has a gap",
  "screens": [] }
```

- `roles[]` are `meta.roles[].id` values; with no roles declared, use one role named for the user.
- A job written as a feature name ("export to Excel") is not a job — ask for the situation and the outcome.
- **Altitude.** A job is placeable when it has a trigger (`when`), a done state (`so`), the role would
  name it unprompted, and it resolves to one place in the structure. A parent with alternative routes
  under it is a goal — split it; three jobs that land on one screen are screen names — merge them.
- Leave `screens: []`. §1c's `promote` fills them, with `ia.layers[]` and `meta.navHub`; none of the
  three is hand-written here.

## ▛ G-JTBD — human gate ▟
**STOP.** Present **every** job as `when / want / so` with its `roles[]` and `priority` — the list, not a
summary of it — and call out the duplicates (two jobs saying one thing), the jobs no existing screen
serves, any job still at feature or goal altitude, and the open questions. Ask for **approve**,
**edit** or **reject**. Silence is not approval. **Nothing below runs until this is answered.**
- **Approve** → write the approved list to `ia.jobs[]` now, refined in place by `id` — §1c's `check`
  reads the jobs from the registry. Note the approval for §4's entry.
- **Edit** → apply, re-present, ask again. An edit re-opens the gate.
- **Reject** → back to §1b. Nothing is written.

## 1c · Information Architecture — N groupings of the approved jobs
Skipped by `--skip-ia`. With an IA already promoted (`ia.layers[]` set), first ask: **re-group or
place?** A few new jobs that fit the hub as it is → place each with `/pb:plan --ia <job-id> --into
<screen-id>` and skip to §2; jobs that change what the hub is for → a new round, below.

The coordinator runs the round **itself — no sub-agents.** The groupings are small structured data,
and N agents given one job list converge on one grouping.

1. **Invoke `ref-ia`.** It carries the vocabulary, the grouping schemes, the five IA axes and their
   threshold, the constraints that lock an axis, the rubric and how to read its scores.
2. **Lock axes from the constraints** (`ref-ia` §4) — an existing `meta.navHub` or a `nav-*` rule in
   `ia.rules[]` (cite the id), the platform (`meta.platform`, `meta.devices`), a role split that
   cannot share a hub, a placement rule. List each of the five axes as locked (by what) or free.
   **Fewer than 3 free → no round clears the threshold.** Say so, and offer to lift a lock (the user's
   call, logged in §4) or to place the jobs into the IA that exists.
3. **Open the round.** `<ia-id>` is `ia-<kebab of meta.name>`, or `ia-<feature>` when the round is
   scoped to one feature; N is `--ia-options` (default 3); slots are `opt-1 … opt-N`.
   ```
   $T = python3 "${CLAUDE_PLUGIN_ROOT}/tools/explore.py" --registry registry.json
   $T init <ia-id> --ia --options N --intent "<the ask, verbatim>"
   ```
4. **Author N genuinely different groupings.** First give every slot its axis values from the free
   axes — a different `scheme` each where the locks allow, every pair ≥ 3 of 5 apart — and its bet
   (which role, how often, starting from where). Then write one file per slot,
   `memory/explore/<ia-id>/<slot>.ia.json`:
   ```
   { "label", "bet", "scheme": "task|role|object|time|frequency",
     "axes": { "scheme", "hub-shape": "bottom-tabs|sidebar|hub-spoke|stream", "depth": "flat|layered",
               "layer0", "secondary": "page|overlay|folded" },
     "hub": { "shape", "component": "<planned id or null>", "items": [ { "label", "screen" } ] },
     "screens": [ { "id", "name", "depth": 0|1|2|"overlay", "parent", "jobs": ["<job-id>"], "purpose" } ],
     "layers": [ { "depth", "name", "purpose" } ],
     "unhandled": ["<job-id>"] }
   ```
   - Every approved job sits in some screen's `jobs[]` or in `unhandled[]` — and an unhandled job is
     a decision the `bet` states, never an omission.
   - Reuse an existing `screens[].id` wherever that screen serves the job; a new screen gets a planned
     kebab id. Every `hub.items[].screen` and every `parent` resolves to a screen in the same file.
   - `hub.component` is the existing hub's id when `meta.navHub` is set; otherwise a planned id for
     the component (or, for `hub-spoke`, the home screen) that will hold the items; `null` only when
     no single body holds the top level (`stream`).
   - `layers[]` gives one sentence of purpose per depth used ("pick a scope of responsibility",
     "decide about one unit"). Never membership — the site map derives it.
   - Labels are the product's words (`content.terms[]`, never an `avoid[]` word). No "Other" / "More".
5. **Check.** `$T check <ia-id>` — every job covered or deliberately unhandled, every hub item
   resolves, every pair ≥ 3 of 5 axes apart. Non-zero → fix the files and re-run. Never present
   around a failing check.
6. **Present on the compare page.** Before sharing, edit `rubric[]` in `memory/explore/<ia-id>.json`:
   write the 2–3 probe jobs into the findability criterion's prompt (`ref-ia` §5), and swap in 1–2
   criteria for what this product said matters (`## Goal`, `meta.userInsights`, a binding rule). Then
   `$T link <ia-id> --open`. It reuses the project's `/pb:preview` server or starts one, checks that the
   page loads, opens it in the user's browser, and prints its URL. Give **exactly that URL, on its own
   line**, e.g. `http://127.0.0.1:8200/explore/<ia-id>`. Never give a file path or an editor link
   instead (`/pb:explore` → *The link*).
   Never ask "which do you like?" — a preference cannot be acted on; a pattern of scores can.

## ▛ G-IA — human gate ▟
**STOP.** Wait for the scores on the page. Silence is not approval. Every message sent while waiting,
and the verdict, ends with the URL from `$T link <ia-id>`.
1. `$T gate <ia-id>` — exit 0 only when every criterion × grouping is scored. **No verdict before it
   passes.**
2. **The verdict, from the pattern** (`ref-ia` §5), not the total: name the grouping the scores
   favour, say so when two lock for different roles or devices, and give **one sentence per rejected
   grouping** on what it taught. Then ask the user to confirm the pick — never make it for them.
3. **Coverage low on every grouping** means the jobs are wrong: `$T reject <ia-id>` and return to
   **G-JTBD**, which re-opens. A re-run of §1c re-opens G-IA; an approval does not outlive its artifact.
4. **A mixed pick** ("opt-1's tabs with opt-3's overlays") is not a pick. Add it as its own slot —
   `$T slot <ia-id> opt-merge --label "…"` — write its `.ia.json`, `check` it, and have it scored
   beside the plain pick. Only a single, scored slot is promoted.
5. **Promote the pick, or reject.**
   ```
   $T promote <ia-id> <slot>   # writes ia.jobs[].screens[], ia.layers[], meta.navHub (when hub.component is set), ia.populated
   $T reject <ia-id>           # nothing chosen; the IA stays as it was
   ```
   `promote` backs the registry up first and touches no `screens[]` / `components[]` — the planned
   screens and the hub body become `/pb:plan` §2's tasks.

Then, either way:
- **One `decisions.md` entry** in §4's shape: `Decision:` the grouping kept (label, scheme), or *none
  kept* after a reject · `Alternatives:` each rejected grouping with what it taught · `Why:` the score
  pattern · both gate approvals (G-JTBD, G-IA).
- **A choice that binds future placement** — a hub slot budget, a home rule ("each figure has one
  top-level home"), a role split — becomes one `ia.rules[]` rule through §2, with a `placement` block
  where it places things. That rule is what locks the axis in the next round.

## 2 · The rule, and the decision it was made by

There is no separate trade-off record (D-33). **A trade-off is a rule**: what you settled on is the
rule, and the question, the options and the reason are how it got settled. Capture them together.

For each contested UI decision, write one `ia.rules[]` entry:

```json
{ "id": "<kebab>", "title": "<the rule, stated — what holds>", "kind": "decision",
  "summary": "<the rule in one line — what now holds>",
  "decision": { "question": "<what was being decided>",
                "options": ["<chosen>", "<what lost>"],
                "chose": "<what won>", "why": "<the reason>",
                "affects": "<tabs / screens it reaches>" } }
```

- **`title` states the rule** — affirmative and plain: "A hub reads code first, name second",
  "Points always snap within 20 px". Never a topic ("Hub identity"), a question ("How is a hub
  identified?") or a headline with a dash ("Merge — ship it or remove it"); the question belongs in
  `decision.question`. A reader scanning the Logic list should learn the rule from the titles alone.
- **`summary` is one line** — what now holds, under ~200 characters. Everything with structure goes
  into `blocks[]` (below), and the history goes into the decision and lineage fields, which the Logic
  tab folds away. A rule written as one long paragraph is the failure this replaces.
- **`options[]` carries what LOST.** That is the one thing a rule cannot say for itself, and the
  only reason this was ever a separate record. Never drop the losing branch.
- **`kind`** is `decision` while the rule is only a decision. The moment it is expressible as a
  `state-machine`, a `matrix` or a `constraint`, change the kind and add that kind's fields — the
  decision block stays and keeps rendering. A decision that never grows into one of those is fine;
  it is still a rule.
- **Superseding** — set `decision.status: "superseded"` (and `supersededOn`) rather than deleting.
  The card dims and keeps its place. Do not write `[SUPERSEDED …]` into the title; that was the
  convention from before the field existed.
- **A rule that already exists** takes the decision block on itself. Do not create a second rule
  saying the same thing in other words.

### 2b · Give the rule its shape — `blocks[]`

Read what you are about to write. If any part of it is one of these shapes, write that part as a
block instead of a sentence. `think-logic` §Rule blocks has an example of each; the Logic tab draws
each one as a component, and `rules.md` exports it as a table.

| When the prose says… | Block | Fields |
|---|---|---|
| "if A → X; if B → Y; otherwise Z" · a status → label/colour map · empty / error branches | `cases` | `rows[{when, then, tone?}]`, `inputs?[]`, `else?` |
| "acts on X only; Y is untouched" | `scope` | `acts[]`, `untouched[]` |
| "Home holds A and B; Profile shows no money" | `placement` | `surfaces[{surface, holds[], never?[]}]` |
| who may do what · which control is enabled in which state | `matrix` | `rowLabel`, `rows[]`, `cols[]`, `cells{row:{col: true\|false\|"label"}}` |
| a refusal and its message · an invariant · an error code | `validation` | `items[{must, enforcedBy?\|enforcedIn?, when?, message?, code?}]` |
| a computed value, a rollup, money maths | `formula` | `expr`, `terms[{name, means}]`, `example?{inputs, result}` |
| "first …, then …, then …" | `steps` | `items[{label, detail?}]` |
| a threshold, a limit, a radius, a date | `params` | `items[{name, value, unit?, note?}]` |
| what it writes and which other screens change | `effects` | `writes[]`, `ripple[{screen, shows}]` |
| "assigned is green, unassigned is yellow" · whose money is which colour | `swatches` | `items[{label, meaning, value, token?, soft?, sample?}]` |
| "the label is code · name" · how an id is built | `anatomy` | `sample?`, `parts[{text, name, rule, note?, tone?}]` |
| "3862.66 shows as 3.862,66 ha" | `examples` | `items[{input?, output, note?}]` |
| anything else | `note` | `text` |

```json
{ "id": "cycle-status", "title": "Cycle status", "kind": "decision",
  "summary": "A cycle's status is derived from today's date against its configured window.",
  "blocks": [
    { "type": "cases", "rows": [
      { "when": "today < execStart − 14 days", "then": "Not started",   "tone": "neutral" },
      { "when": "today < execStart",            "then": "Starting soon", "tone": "info" },
      { "when": "today ≤ execEnd − 48 h",        "then": "In progress",   "tone": "ok" },
      { "when": "today ≤ execEnd",               "then": "Ending soon",   "tone": "warn" } ],
      "else": { "then": "Overdue", "tone": "bad" } },
    { "type": "params", "items": [ { "name": "lead-in", "value": 14, "unit": "days" },
                                   { "name": "warning", "value": 48, "unit": "hours" } ] } ],
  "decision": { "question": "…", "options": ["…"], "chose": "…", "why": "…" } }
```

**Add blocks from facts that are already there.** When a rule's prose describes colours, steps, status
mappings or concrete values and has no block for it, add the matching one — `swatches` (a colour meaning), `steps`
(a sequence), `cases` (a status → label map, an if/else), `examples` (a worked value) — **taking every value from
the rule itself or from the registry** (a token's resolved value, a screen's name, a state's label). Nothing is
invented: a colour the registry does not hold is not a swatch, and a step the rule does not state is not a step.
Give each block a **`source`** — a short note naming where its facts came from (`"tokens.color.zone-assigned"`,
`"this rule's why"`, `"screen map-editor"`); the renderer and `L-BLOCK` ignore the key, a reviewer reads it. If
the facts are not there, leave the prose as prose and say so in the hand-back.

Blocks are additive (no schema bump) and any rule kind may carry them, in any order.
`logic_check.py` checks each block against the renderer (`L-BLOCK`), and notes an unstructured rule
whose summary or why runs long (`L-PROSE`, information only).

## 3 · Write the registry (fold the sync — no hook)
- `meta.userInsights` = `{ quantitative, researchSummary, executiveSummary }` — with the §1a marks.
- `ia.jobs[]` — the jobs approved at G-JTBD (already written there); refined in place by `id`.
- `ia.jobs[].screens[]`, `ia.layers[]`, `meta.navHub` — written by §1c's `promote` only, never here.
- `ia.rules[]` — append each new rule; update in place when the decision refines one already there.
- `ia.populated: true` once either list is non-empty (`promote` sets it too).

(Replaces the v0.4.0 `after_clarify` → `sync-tab2` hook.)

## 4 · Append to the decision log

**Read before you write.** For each decision, first grep `memory/decisions*.md` for its subject.
If a past entry already decided it, show that entry and ask whether this one supersedes it —
then say so explicitly in the new entry, and set `decision.status: "superseded"` on the rule it
replaces. A log that is written by three commands and read by none accumulates contradictions
nobody notices; on a real project that produced entries marked SUPERSEDED the same day they were
written. Use `decisions*.md`, not `decisions.md`: rotation moves older entries to dated siblings
and a bare name skips them.

Then append one entry per decision in the template's shape, **field names exactly as written** so a
later grep can rely on them:

```markdown
## <date> — <title>
- **Decision:** <decision.chose>
- **Why:** <decision.why>
- **Alternatives:** <the options not chosen>
- **Affects:** <decision.affects>
- **Rule:** <ia.rules[].id>
```

The IA round's entry (§1c) uses the same fields; its `Affects:` names `meta.navHub`, `ia.layers` and
the hub component, and its `Rule:` is the placement rule's id, or `none`.

## Result
User Insights synced to Tab 2; the approved jobs and the chosen IA (each job's screens, the layer
purposes, the hub) in UX Design → Information Architecture; one rule per decision in UX Design → Logic
→ Rules; one `decisions.md` entry each, pointing back at the rule id. Next: `/pb:plan`, which turns
the chosen IA into tasks. **Do not render.**

## NEVER
- NEVER group before G-JTBD — §1c starts only on an approved job list, written to the registry.
- NEVER author an IA outside `explore.py --ia` — no grouping table in chat in place of the link, no
  hand-written compare page, no second server, and no hand-written `ia.jobs[].screens[]`,
  `ia.layers[]` or `meta.navHub`: `promote` writes them.
- NEVER write `ia.layers[]` membership, edges or overlays — they are derived from the hub and the
  render bodies.
- NEVER pick for the user, at either gate — present, then wait. Silence is not approval.
- NEVER state a G-IA verdict before `gate` passes, and NEVER promote a mixed pick.
- NEVER hand the groupings to sub-agents, and NEVER author N with one scheme, or N that differ only in
  labels.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
