---
name: ref-design-compare
description: The contract for generating genuinely different design alternatives and scoring them against a rubric instead of asking "which do you like?". Use whenever N alternatives are produced for a human to choose between — loaded by /pb:explore Mode A (A1/A2/A4) and Mode B (B4). Covers the seven divergence axes and their threshold, the generic-tell ban list, the render-and-screenshot gate, the 10-criterion score sheet, and the mapping from a low score to the thing to change. Not for picking a component (that is the DS-first check in /pb:build §3a).
---

# ref-design-compare

Two failure modes kill an exploration. **One:** the alternatives differ only in colour and spacing, so
the choice is fake. **Two:** they are presented as "which do you prefer?", so the feedback is a vibe
and nothing downstream can act on it. This contract closes both.

Provenance: distilled from the design kit's `direction-variation-checklist.md`, `taste-checklist.md`
and `specs/compare-rate-widget-spec.md`, whose rules came out of a real graded round.

## 1 · The divergence contract (before generating)

**Assign each alternative its axis values up front.** Do not launch N agents and hope they diverge —
independent agents converge, and that is exactly how a round of three "options" turns out to be one
option in three colours.

| Axis | The question | Example spread |
|---|---|---|
| Mental model | How is content primarily organised — status, time, attribute, owner? | status columns · sortable table · time-ordered feed |
| Layout | The dominant shape of the page | kanban columns · dense data table · single column of cards |
| Navigation | How the person moves between areas | top tabs + palette · icon rail + saved views · bottom tabs + FAB |
| Component set | Which controls actually appear | drag cards + drawer · inline-editable rows · swipe rows + bottom sheet |
| Motion | How much, and what kind | spatial (things travel) · near-zero · expressive (springs, undo) |
| Hierarchy | What carries the most weight, and how | status colour first · weight only on the important row · next action foregrounded |
| Contrast | How strong the value differences are | mid + elevation-driven · high black-on-white · soft neutrals, one accent |

**Threshold: an alternative must differ from every other on at least 4 of these 7.** Two that differ
on only 2–3 are too close to be a real choice — **merge them into one sharpened alternative** and
spend the freed slot on something actually different.

Each alternative is a **bet on a specific user and context**, not just a layout. Say whose bet it is.

## 2 · Generic tells — do not spend an axis on these

They read as generated regardless of how good the idea underneath is. Not permanently banned — a
brief that explicitly asks for one wins — but never a default:

- warm cream + high-contrast serif + terracotta (`#D97757`-ish) · near-black + one acid accent
- a **left accent bar** on selected or expanded rows
- every card the same rounded rectangle with the same soft grey shadow, regardless of hierarchy
- tracked-out ALL-CAPS eyebrows above every heading · `→` on every button · `01 / 02 / 03` on
  content that is not a sequence · middle-dot meta strings as identity · mono on every data label
- **a repeated filled primary on every item in a list** — a list has at most one primary, and it
  belongs to the view (a bar, a FAB, a sticky footer), never to each row
- **oversized mobile type** — page titles ≤ 24, item titles ~16 semibold on compact; a phone showing
  1–2 giant cards has failed. Aim for 3–4 task items per phone screen.

Ground every alternative in the product's **real content** — real task names, real labels. Never
lorem ipsum. And responsive means each alternative answers at compact *and* large — a large layout
that merely shrinks has not been designed responsively.

## 3 · The render gate (before presenting — not optional)

**Render each alternative and look at a screenshot at a desktop width and a phone width before
showing it to anyone.** Layout bugs are invisible in source and obvious in one image. Specifically:
a bare `1fr` grid track sizes to its content's min-content width, not the container — use
`minmax(0, 1fr)` wherever a single-track grid holds text. That exact bug pushed rows ~52px past a
phone's edge and clipped a status pill off-screen, and reading the CSS did not catch it.

Presenting something you have not rendered yourself is the most common way this goes wrong.

## 4 · The score sheet (presenting)

Ask for a **1–5 score per criterion per alternative**, plus an optional note per criterion — not
"which do you prefer?". `1` weak · `5` strong.

| # | Criterion | The prompt to ask |
|---|---|---|
| 1 | Hierarchy | Can you name the one most important thing in 3 seconds? |
| 2 | Navigation clarity | Do you know where you are and how to get to the other areas? |
| 3 | Layout and density fit | Is the amount of information per screen right for its user? |
| 4 | Component choice | Are the controls the right tool for each job? |
| 5 | Motion feel | Does motion show what changed, at the right speed, and nothing more? |
| 6 | Contrast and legibility | Can you read everything at a glance, including secondary text? |
| 7 | Breathing | Is there air where the eye rests, and grouping you can see with a squint? |
| 8 | Consistency and rhythm | Do repeated elements look and behave the same? |
| 9 | Category fit | Would its intended user recognise it as made for them? |
| 10 | Ship verdict | Would you present this as the direction? 1 no, 5 yes as is. |

**Always swap in or add 1–2 criteria matching what this brief said mattered** (trust, speed, density —
whatever it was). A rubric that ignores the stated priority is decoration. Do not pad it with
criteria nobody asked about.

**Escalate** to a dozen hand-picked rows from the design kit's deep taste checklist when the stakes
are high or the alternatives score close — pick the rows relevant to this brief, never all of them.

Collect the result as a markdown table, criteria × alternatives, notes column, ending in an
**Average** row. Unscored cells are `–`.

## 5 · Turning grades into changes

This is the half that makes a score actionable. Read the *pattern*, not the total.

| Pattern in the scores | Meaning | What to do |
|---|---|---|
| Rows 1–8 mostly ≥ 4, but Category fit low | Standards hold, the direction is wrong | change taste variables only — temperature, elevation, type expression. New direction, same structure |
| Category fit high, one of 1–8 low | Direction is right, a standard is being violated | fix that alternative against the named rule; log nothing |
| The same row low across **every** alternative | The standard itself is wrong for this product | that is a decision — record it in `memory/decisions.md` |
| Scores drop > 1 point at phone width | Desktop decoration | responsive rules and density, not taste |
| Everything mid (3s) with no 5s | Nothing is a real bet | the axes were too close — go back to §1 |

## 6 · The verdict

State the winner **from the scores and notes**, not from vibes, and not by restating the table.

Two things are mandatory. **A verdict is not always one winner** — two alternatives may each lock for
a different context, which is a real outcome, not a failure to decide. And **every rejected
alternative must yield one sentence of what it taught** — a rule broken, an axis that did not land, a
taste mismatch. A rejected alternative that teaches nothing was wasted effort twice.

Where the lesson is a standing rule rather than a one-off, it belongs in `memory/decisions.md`, and
the row names the file the rule now lives in.
