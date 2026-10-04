---
name: think-direction
description: Fix the shared ground before N design alternatives are generated, in two outputs — a one-screen direction the user approves at G-DIRECTION (the job, the taste position, the hard constraints, the real content, which of the seven divergence axes are locked, and N one-line bets), then, only after approval, one execution plan per bet that a pb-explorer builds to with nothing else in hand. Use before every diverge step — loaded by /pb:explore (A1a/A1c and B4) — so each alternative is a grounded bet and any candidate is a drop-in. Reads the project's memory, IA and DS instead of running a questionnaire. Not for scoring the alternatives (that is ref-design-compare), single-screen logic (use think-logic), or the reuse decision (that is /pb:build §3a).
user-invocable: false
---

# think-direction

`ref-design-compare` makes alternatives differ; this runs first and fixes what they may differ on and
what they must all get right. Without it each re-guesses settled rules: in one real project's round,
two rejected options broke a tap budget and the colour contract, later home promotes renamed the
classes the scenarios addressed, and the shared rules reached the project's build notes after the fact.
The coordinator runs all of it; §5 writes it twice — a direction the user approves, then the plans.

Provenance: the design kit's direction explorer and its foundations, decision-tree, interaction and
responsive references — kept out of the DS layer by DESIGN.md, allowed at explore time only. **A locked
DS always wins**: kit defaults (radius `inner = outer − gap`, 4/8 spacing, type caps) fill only its gaps.

## 1 · Read, don't ask

| Source | Gives the brief |
|---|---|
| the manifest's `intent`; `memory/prd.md` `## Goal` (Mode B) | what this round is for, verbatim |
| `ia.jobs[]` whose `screens[]` hold the target or its host; `memory/spec.md`; `meta.userInsights` | the job, the role, the context, the one primary action |
| `memory/constitution.md` (Principles, DS Lock), `design-system/<name>/<name>.md`, the tokens | the vocabulary, and the taste position the DS already holds |
| `ia.rules[]` whose `displayedIn[]` / `readers[]` / `implementedBy[]` touch the target; `memory/decisions.md` | the rules that bind this area, and what earlier rounds taught |
| the live body, its `logicSrc` contract, the `test{}` targets in `flow.stories[]` | the behaviour, and the hooks the scenarios address |
| `meta.devices`, `meta.platform`, the registry and `erd.mock` seeds | the two widths, and the real content |

Mode B adds B3's findings: what covers the goal is a constraint, what conflicts is a decision point.
Ask only what `think-clarify`'s test says to ask (usually nothing; at most two, each with a default).

**IA input.** `ia.jobs[].screens[]`, `ia.layers[]` and `meta.navHub`, where they exist, are
constraints: the target's layer and its purpose, its parent, the hub that owns top-level navigation —
so a component target inside a hub has **navigation locked** (by `meta.navHub`). When no job's
`screens[]` holds the target or its host, say so and **stop**: `/pb:clarify` defines jobs, never this.

## 2 · Design direction — what every alternative shares

- **Job.** One `when / want / so` line per job served, its role and one primary action (`ref-blueprint` §1).
- **Taste.** The six taste axes in plain words — density (minimal ↔ rich) · boldness (quiet ↔ bold)
  · tone (serious ↔ playful) · convention (traditional ↔ experimental) · temperature (warm ↔ cool) ·
  spacing (spacious ↔ dense) — read from the DS and existing screens, each **fixed** or **open**.
- **Hard constraints.** DS Lock tokens and components (the only vocabulary) · platform · locale
  (script, casing, number/date/currency) · the a11y bar (contrast, target size, reduced motion) ·
  every binding `ia.rules[]` entry, by id ("`nav-three-tabs` — three docked tabs").
- **Real content.** The labels, figures and states to show, from the seeds and the spec — the longest
  label and the empty seed included. A value nobody has is a named gap.
- **Responsive.** What compact and large each answer: layout shape, navigation, component swaps
  (table → cards, dialog → sheet), touch vs pointer density. "The same, smaller" is not an answer.
- **Decision points.** The component-fit questions this target raises — list · table · cards (one
  focal item or comparable ones? how many attributes?) · dialog · sheet · banner · inline (must they
  act first? one field or the page?) · switch · segmented · radio · chips · select (how many, one or
  many, now or on submit?) · feedback by latency (< 100 ms state, ≤ 1 s spinner, ≤ 10 s skeleton,
  then background). Every alternative answers every point; one left open is decided by accident.

## 3 · Locked and free axes

Mark each of `ref-design-compare` §1's seven axes **locked** — by what: a nav rule, `meta.navHub` or a
host that owns navigation, a colour contract on contrast — or **free**. Locked axes are equal in every
slot, so with F free no pair differs on more than F; `explore.py check` fails any pair under 4.

- **F ≥ 4** — a value per free axis per slot, every pair ≥ 4 apart, and a bet (whose user, what context).
- **Fewer genuine bets than N** — say so and re-open with `explore.py init <id> --force --options N′`
  (nothing is built yet); never pad a slot. N′ = 1 is not a round — take it to `/pb:build`.
- **F < 4** — no round of this target clears the threshold. Say so and offer: widen it (`--files` the
  host, or Mode B), lift a lock (the user's call, logged), or run a tune and call it one. Never record
  a difference on a locked axis to make the count.

## 4 · Logic direction — what every alternative keeps

The vocabulary is `think-logic`'s. Mode B has no live body: keep the jobs' states, reused contracts.
This lands in every plan's logical half (§5b); the direction shows only the open behaviours.

- **States table** — state · when · what is visible · **priority when two hold at once**, in the
  `cases` shape (`think-logic` §5): first match wins, so row order *is* the priority. A condition on
  any state (read-only role, offline, a save in flight) is an overlay, listed apart as the
  `state-machine` kind draws it. Empty, loading, error, disabled and each role get a row.
- **The contract** — the same `renderFn` and props; the `data-*` verbs that must still fire
  (`data-nav`, `data-action="submit"` with `data-required` / `data-validate`, `data-go`,
  `data-machine` / `data-step`, `data-preserve`); the handlers `logicSrc` and `implementedBy[]` name;
  every selector or `data-*` value a `test{}` targets — rename one and a scenario fails after promote.
- **Validation** — each input's rule and message, word for word, unless the round is about them.
- **Open behaviour** — what may change (inline vs on-submit, a step merged, undo instead of confirm),
  each named in the direction, taken by a plan, and scored. A change not named open is a defect.
- **Comments** — a body says what it does, never that it is a candidate: it is promoted as is (2026-09-29).

## 5 · Write it twice — the direction, then the plans

**5a · Direction** → `memory/explore/<id>.brief.md`, about one screen: what G-DIRECTION shows, and all
it shows. Frozen once approved — an edit re-opens the gate.

| Section | Holds |
|---|---|
| `## Intent` · `## Job` | the manifest's `intent` verbatim (Mode B: the `## Goal` line) · the `when / want / so` lines, role, primary action |
| `## Taste` · `## Constraints` | the six positions, each fixed or open · DS Lock, platform, locale, a11y bar, binding rules and IA by id, any kit default used for a DS gap |
| `## Content` · `## Responsive` | the real labels, figures and seeds · what compact and large each answer |
| `## Decision points` · `## Axes` | each question and the options it admits, open behaviours (§4) included · the seven, each locked (by what) or free |
| `## Bets` | one line per slot — `opt-2 · <whose user>, <what context> · <its free-axis values>` — or the N′ / F < 4 statement |
| `## Rules learned` | empty until the verdict |

**5b · Plans** → `memory/explore/<id>/plans/<slot>.md`, one per approved bet, written after G-DIRECTION
and never shown at it — each the **whole** brief one `pb-explorer` executes, with nothing else in hand:

- **Creative** — mental model; layout shape at compact and at large; every decision-point answer;
  component choices by DS id; hierarchy (what carries the weight); the real labels and figures; motion.
- **Logical** — the states table with collision priority; the contract (same `renderFn` / props, the
  `data-*` verbs, handlers and `test{}` targets that must survive); validation; what it **may** change.
- **Anti-brief** — the siblings' axis values, forbidden: *"opt-2 is a table, opt-3 a feed — this is neither."*

Plans differ creatively **and** logically: one that is another with the adjectives changed is a defect
— rewrite it, or the executors converge. The plan is the contract; `check --shots` and the rubric verify
the result. Mode B's creative half is the approach, written to `memory/explore/<id>/<slot>.approach.md`.

**Manifest** (at A1c) — each slot's `label`, `bet` and free `axes` (`mental-model` · `layout` ·
`navigation` · `component-set` · `motion` · `hierarchy` · `contrast`) from its Bet line. **`rubric[]`** —
the 1–2 criteria `ref-design-compare` §4 swaps in for what the direction says matters, set before the
link is shared: `{"id": "next-step", "label": "Next step is obvious", "prompt": "Can the employee…?"}`.

**After the verdict, before `promote` / `reject`** (which move the brief and `plans/` to `_closed/`),
fill `## Rules learned`: each "taught" sentence and standing-rule note, worded as a rule ("stacked,
never a carousel") with its slot; `/pb:clarify` turns them into `ia.rules[]` (`/pb:explore` §A5).

## Anti-patterns

- **A questionnaire the memory already answers** — the kit's form is for a project with no memory.
- **Diverging on a locked axis** — it loses to a rule, not on taste. **Colour-only options** — one in N coats.
- **A plan at the gate.** The user approves a direction; a plan shown there is approved unread.
- **A brief longer than the candidates** — link a rule by id. **Invented content or jobs** — name the gap.
- **States with no collision priority.** A real project shipped three state rows marked "inferred" because nothing said which wins.
