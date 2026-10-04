---
name: ref-ia
description: The vocabulary and the contract for information architecture in Product Builder — organization scheme, labeling, navigation systems, depth vs breadth, hub load, findability — and for turning one approved ia.jobs[] list into N genuinely different groupings that the user scores instead of likes. Use once the jobs pass G-JTBD and the screens, the nav hub and the layers are to be chosen — loaded by /pb:clarify §1c and read by /pb:plan §2 when it consumes the chosen IA. Covers the grouping schemes, the five IA axes and their threshold, the constraints that lock an axis, the seven-criterion rubric with the findability probe, and what promote writes versus what stays derived. Not for scoring (ref-design-compare), the direction of one target (think-direction), or screen layout (think-layout).
user-invocable: false
---

# ref-ia

The jobs say what each role needs done; the IA says where each job lives. One job list admits several
honest structures, and reflex picks the data model or the first sketch. One real project regrouped the
same jobs three times in five days — five tabs, then three, then four, each a promote and a backup.

Provenance: Rosenfeld, Morville & Arango, *Information Architecture* (4th ed.), via the IA kit's
systems, methods and governance references — use its terms, invent none. pb swaps the kit's card
sorts for the approved `ia.jobs[]`, and its tree tests for the compare page (`explore.py --ia`).

## 1 · Vocabulary

- **Organization scheme** — the principle things are grouped by (§2). → each grouping's `scheme`.
- **Labeling system** — one word per group and screen, the same on every surface. → hub labels and
  screen `name`s, from `content.terms[]`, never an `avoid[]` word.
- **Navigation system** — *hub* (global, on every top-level screen) · *local* (inside a section) ·
  *contextual* (inline, on an item). → the hub is `meta.navHub`; local and contextual are derived.
- **Depth vs breadth** — layers before the job vs items per layer. → `axes.depth`, `ia.layers[]`.
- **Hub load** — how many items the hub carries, and how many unrelated jobs sit behind each one.
- **Wayfinding** — knowing where you are, where you can go and how to get back.
- **Findability** — the role reaches the job's screen without search or guessing (§5's probe).

Only each job, each layer's `purpose` and the hub are authored. Layer membership, edges and overlays
are **derived** from the hub's body and the render bodies, and are never stored.

## 2 · Grouping schemes — many IAs for the same jobs

| Scheme | Wins when | Fails when | e.g. |
|---|---|---|---|
| **task / job** | an operational product; jobs used together in one session are grouped together | many jobs edit one object, which then lives in three places | review tool: Create cycle · Score · Approve results |
| **role** | roles differ in kind (permissions, jobs) and never share a session | one person holds two roles, or roles share most jobs, so screens appear twice | Employee · Manager · HR workspaces |
| **object** | users think in nouns and do several jobs to each | the data model leaks: one table row, two different jobs | Programmes · Funds · Transactions |
| **lifecycle / time** | one object moves through states and the job depends on the state | one tab per internal status the user does not hold in their head | Upcoming · Ongoing · Ended |
| **frequency** | a few daily jobs dominate; the hub holds those, the rest go one layer down | frequency without trigger: a daily action that fires *inside* another job belongs inline, not on the hub | Home (today's figure + 4 actions) · Programmes · Profile |
| **hybrid** | one scheme at layer 0 and another below it (a task hub, object lists inside) — most real products | two schemes side by side at the same level, so nobody can predict which one holds a thing | task tabs over per-programme pages |

That project's same jobs, five tabs → three after an explore promote: *"Assets repeated Home and the
programmes; too many steps; too professional"* (its `decisions.md`, `nav-three-tabs`). What
came out of it — "One top-level home per figure" (`one-home-per-figure`) — is a
placement rule, and it locks an axis in every later round (§4).

## 3 · The five IA axes + threshold

| Axis (`axes.*`) | The question | Values |
|---|---|---|
| `scheme` | What is grouped with what? | task · role · object · time · frequency |
| `hub-shape` | What holds the top level? | bottom-tabs · sidebar · hub-spoke · stream |
| `depth` | How many layers before the job starts? | flat · layered |
| `layer0` | What is the first screen *for*? | one phrase: "today's money", "pick a unit", "my programmes" |
| `secondary` | Where do the less frequent jobs go? | page · overlay · folded |

**Threshold: every pair differs on at least 3 of the 5** (`explore.py check` enforces it). Fewer, and
it is one grouping twice: merge the pair into one sharper grouping and spend the slot on another
scheme. **Two groupings that differ only in labels are one IA twice.** Assign every slot its values
*before* writing any file — groupings written one after another drift toward the first. Each is a
bet: which role, how often, starting from where (a payslip, a notification, a chat).

## 4 · Hard constraints that lock an axis

| Constraint | Locks | Read from |
|---|---|---|
| an existing `meta.navHub`, or a `nav-*` rule — cite it: "`nav-four-tabs` — four docked tabs" | `hub-shape`, and the slot budget | `meta`, `ia.rules[]` |
| platform: bottom tabs ≤ 5 on a phone; a sidebar on desktop; both when `meta.devices` spans | `hub-shape` | `meta.platform`, `meta.devices` |
| a role split that cannot share a hub (permissions, a different device) | `scheme` → role, or one hub per role | `meta.roles[]`, `ia.jobs[].roles` |
| a placement rule ("one home per figure", a `placement` block) | `layer0`, `secondary` | `ia.rules[]` |

Locked axes are equal in every slot, so with F free axes no pair differs on more than F. **F < 3: no
round clears the threshold** — say so, and offer to lift a lock (the user's call, logged) or to place
the new jobs in the IA that exists (`/pb:plan --ia <job-id> --into <screen-id>`). Never record a
difference on a locked axis. Hub slots are zero-sum: adding an item names the one it demotes.

## 5 · Validation — the rubric and how to read it

The default `--ia` rubric, 1–5 per grouping, as the compare page asks it:

| Criterion | The question |
|---|---|
| Job coverage | Does every approved job have a screen that serves it, or a stated reason it is left out? |
| P1 jobs within 2 taps | Can every P1 job be started within two taps of the hub? |
| Hub load | Does the hub carry few enough items to scan at a glance — five or fewer for bottom tabs? |
| Label clarity | Would a first-time user know what is behind each label before opening it? |
| No orphan screens | Does every screen serve a job and have a way in from the hub? |
| Role fit | Does each role meet its own jobs first, without wading through another role's? |
| Findability probe | Where would `<role>` tap first to `<want>`? (the probe jobs, below) |

**The findability probe replaces tree testing.** Pick 2–3 P1 jobs (different roles where there are
several) and write them into its prompt before sharing the link. The user answers from each hub's
labels *before* reading its screens: 5 = every first tap lands, 1 = none. Report "two of three", not
percentages. Swap in 1–2 criteria for what this product said matters (`## Goal`, a binding rule).

| Pattern in the scores | Meaning | Do |
|---|---|---|
| Coverage low on **every** grouping | the jobs are wrong: too coarse, duplicated, a goal posing as a job | `reject`; back to G-JTBD |
| Hub load low on one | that hub is over-stuffed | merge two items, or fold the rarer jobs; re-`check`, re-score |
| Label clarity low while the structure rows are high | the labels are wrong, not the structure | rename in that grouping; do not regroup |
| P1 low, findability high | too deep | flatten it, or bring the P1 job up to layer 0 |
| Findability low, coverage high | the jobs are there, just not where the role looks | the scheme is what to change, not the screens |
| Two groupings each win for a different role or device | a real outcome | one merged slot: `meta.navHub` takes a list (sidebar + bottom tabs) |
| Everything mid (3s) | nothing is a real bet | the axes were too close — re-open with other schemes |

## 6 · What gets written, and what stays derived

`explore.py promote <ia-id> <slot>` is the only writer: `ia.jobs[].screens[]` (an `unhandled` job
keeps `[]`), `ia.layers[]` (`depth`, `name`, `purpose`), `meta.navHub` when `hub.component` is set,
and `ia.populated`. It backs the registry up and touches no `screens[]` or `components[]` — the
planned screens and the hub body are `/pb:plan` §2's tasks, and the slot's `hub.items[]` are the hub
body's acceptance (each `{label, screen}` a nav-item literal the site map can read). Once the bodies
exist, the derived map is the truth, not the slot's `depth` / `parent`.

**The decision entry** (`/pb:clarify` §4's shape): the grouping kept (label, scheme); each rejected
one with a sentence on what it taught; the score pattern as the why; both gate approvals. **A choice
becomes an `ia.rules[]` rule** when it binds future placement — a slot budget (`nav-*`), a home rule
(a `placement` block), a role split — and that rule locks the axis next time (§4). A one-off
("History is pushed, not a tab") stays in the entry.

## Anti-patterns

- **A card-sort questionnaire when `ia.jobs[]` exists.** The jobs are the cards; the probe is the test.
- **Grouping before G-JTBD.** Every grouping inherits the jobs' errors, and the round is spent twice.
- **N groupings with the same scheme.** One IA in N coats; `check` fails it, and it should.
- **Inventing jobs to fill a tab.** A hub item with no approved job behind it is someone's idea.
- **Storing layer membership.** It is derived, so a stored copy is wrong after the first body edit.
- **A hub of 6+ items.** Past about five, a phone hub stops being glanceable; merge or fold.
- **"Other" / "More" as a tab.** A bin admits the grouping failed; place each job or mark it unhandled.
