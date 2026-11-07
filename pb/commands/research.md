---
description: Validate what the project is unsure about with real people — frame a falsifiable question, choose among survey, interview, usability test, tree test, card sort and first-click test, write the plan and the instrument from the jobs, flows and rules, approve it at G-STUDY, run sessions on this machine or from a kit file, store everything as immutable evidence, analyse with tool-computed numbers, synthesize verdicts, issues and a report with verbatim quotes, and refill the User Insights at G-INSIGHT.
---

# /pb:research [<question or kind:id>] [--survey|--interview|--usability|--tree-test|--card-sort|--first-click] [--role R] [--segment S] [--gaps] [--import <id> <file>] [--synthesize <id>]

Turn "we are not sure" into a study, run it, and (if the user wants it) keep the evidence. **Every run
opens by asking what the user needs and what their setup is (§0).** The registry already holds the
**jobs** (`ia.jobs[]`: when / want / so), the **flows** (`flow.stories[]`) and the **rules**
(`ia.rules[]`, some marked `ASSUMPTION`). This command follows the path a senior UX researcher follows:
frame the question, choose the method, write the plan, write the instrument from the registry, get it
approved, organise the sessions, run them, analyse, synthesize, report. It files what comes back as
evidence a later reader can check.

**The division of labour.** The tool does the arithmetic, the quote-checking and the session capture.
You do the interpretation. **Two human gates, in order: ▛ G-STUDY ▟ (the plan and the instrument, before
anyone is asked) and ▛ G-INSIGHT ▟ (the findings and the report, before they touch the insights).** Each
is blocking and presents the artifact, not a summary of it (`${CLAUDE_PLUGIN_ROOT}/docs/canon.md`
§ *What makes a gate real*). Silence is not approval. The evidence rules are in
`${CLAUDE_PLUGIN_ROOT}/docs/canon.md` § *Research evidence*.

**Nothing is hosted online.** No survey page, no panel, no public link. A survey or an interview is
fielded in a tool the user already has, and its export or transcript comes back. A usability test, tree
test, card sort or first-click test runs **on this machine** (the `/pb:preview` server, at `127.0.0.1`)
or **from one HTML kit file** the participant opens on their own disk and sends the results back from.
Fielding takes days: **this command is resumable** — the study's status and files carry the state, and
`list` shows where each one stopped.

```
T = python3 "${CLAUDE_PLUGIN_ROOT}/tools/research.py"        # run from the project folder; --registry defaults to ./registry.json
```

Exit 0 = ok · 1 = refused or a check failed · 2 = usage or missing input. Every subcommand also takes `--json`.

## 0 · Clarify what this run is for — first, at every run

**Do this before anything else, at every run, including a resumed one.** Before reading a gap list,
framing a question, seeding, or opening a study, find out what the user needs from this run and what they
have to field it with. Ask, **even when the request sounds obvious**. The only time you skip a question is
when the user's message in this conversation already answered it; then restate the answer in one line and go on.

1. **"What do you need from this study?"** Offer exactly two answers and let the user choose. Never pick for them.
   - **(i) Just the questions and the setup.** pb writes the plan and the instrument and says how to
     field them. Nothing comes back to pb. Scope `instrument`.
   - **(ii) Questions plus results.** The user will bring the results back (or run the sessions here) to be
     stored as evidence, and the findings will refill the User Insights. Scope `collect`.
2. **"What is your setup?"** Which survey tool, panel or list of participants they have, who will moderate,
   and where results live today. If they have none of it, say plainly that this part is skipped and that
   you will not assume one. **Nothing is hosted online:** do not offer an online test, a public or LAN
   link, or a panel that does not exist. For a usability test, tree test, card sort or first-click test,
   the two ways to run are on this machine (moderated) or from a kit file (unmoderated); ask which fits.
3. **Record it.** A new study: pass `--scope instrument|collect` (and `--setup "<their words>"` when they gave
   one) to `$T init` in §4. Before the study exists, keep the two answers in the conversation and carry them to `init`. An existing
   study whose answer changed: `$T scope <id> --scope S [--setup T]`.
4. **On a resumed run, this is one line.** Run `$T show <id>`, state the stored scope and setup, and ask
   whether they still hold. If they do, go on. If not, run `$T scope` first.

Scope decides what the rest of the run does:

| Scope | The run covers | The run ends |
|---|---|---|
| `instrument` | §1–§4 and ▛ G-STUDY | **After G-STUDY.** The user gets the plan, the instrument and the facilitator files (`plan.md`, `moderator-guide.md`, `tasks.md`, `consent.md`, `screener.md`, `note-taking.csv`) and how to field them. Do not ask about import, sessions, synthesis or refill, and do not describe the study as unfinished: handing over the instrument is the whole job. A rehearsal (`link --pilot`, `kit --pilot`) is still allowed |
| `collect` | §1–§9 | After the decision-log entry (§9), with the fielding break at G-STUDY |

`import` is refused on an `instrument` study, and so is a real session link or kit. If the user later wants
their results kept, that is a change of answer to question 1: run `$T scope <id> --scope collect`, then §6.

## 0a · Flags and entry points

Read this after §0 has been answered.

| You are given | Do |
|---|---|
| *(nothing)* or `--gaps` | `$T gaps` (add `--role R` when a role was given), show the ranked rows (`kind · id · title · roles · why`) and let the user pick. Never pick for them. `--gaps` alone stops after the pick is made and the study is framed |
| a sentence | It is the question. §1 |
| `kind:id` (`job:pay-cod`, `rule:cod-limit`) | A target. Its `why` in `gaps`, or its job's `gap`, is the question: confirm it in the user's words |
| `--survey` / `--interview` | The method is chosen, a study asked elsewhere; §2 only checks it fits |
| `--usability` | The method is a task-based test on the prototype; §2 only checks it fits |
| `--tree-test` | The method is a text-only test of where things live in the structure; §2 only checks it fits |
| `--card-sort` | The method is a grouping exercise on cards; §2 only checks it fits |
| `--first-click` | The method is a first-click test on one screen; §2 only checks it fits |
| `--role R` / `--segment S` | Who is asked. A segment no role covers is fine |
| `--import <id> <file>` | Resume at §6 (import) for study `<id>` |
| `--synthesize <id>` | Resume at §7 (analysis) and §8 (synthesis) for study `<id>` |
| a study id with no other flag | `$T show <id>` and resume from its `status`: draft → §3/§4 · approved → §5 and §6 · fielding → §6, then §7 · analysed → the report and G-INSIGHT (§8) · applied → §9 |

To find a study that is already underway: `$T list`. A resumed study re-enters through §0 first (the one-line
check), then the row above.

## 1 · Frame — what exactly is unsure, and who is asked

1. **Restate what is unsure, verbatim.** Quote the user's sentence, or the gap row, or the rule's
   assumption text. Where your restatement and the request differ, the request wins. Do not narrow it
   ("the simple half"), widen it, or swap in what you think they really need.
2. **Name who is asked** — `--role` (a `meta.roles[].id`), `--segment` (free text: "rural, under a year
   on the job"), or both. A study with neither is refused by the tool and is not a study: "users" is not an
   audience. If the person who would answer is not the person the project calls a role, say so and use the segment.
3. **Name the decision.** Ask what will be decided from the answer, and who decides. A study that informs no
   decision is not worth the participants' time. Carry it into the plan (§2a).
4. **Run the seed.** `$T seed <kind:id> [<kind:id> …]` for each target. It returns the job's when / want /
   so, the roles, the screens, the stories that touch it (title, path, scenarios), the rules, and the
   prototype links for tasks. Everything in §3–§4 is built from that output; invent no job, screen or link.
5. Pick a study id, `rs-<kebab>`, short and about the question.

Invoke `ref-research` now. It carries the method: question-writing rules, the bias list, sample guidance,
the per-method craft and how to read results.

## 2 · Choose the method — say why

`$T methods` prints the catalog: what each method answers, when it fits, a sample-size rule of thumb, the
typical session length, what the tool computes for it and what it is **not** for. State the method and the
one-line reason. Ask only when it is not obvious. `ref-research` §1 has the decision path.

| The question is | Method |
|---|---|
| *why* or *how* people do it, or you do not know what you do not know | **interview** |
| *how many* or *how often*, or sizing something already understood from interviews | **survey** |
| whether a person can complete a flow on the prototype, and where they stumble | **usability** test |
| whether people can find where something lives in a menu structure, free of layout | **tree-test** |
| how people group and name the things in the product | **card-sort** (open, closed or hybrid) |
| whether the first click on one screen goes the right way | **first-click** |
| several of these | Interview first, then a card sort, then a tree test on the structure it produced. A survey on a question you have not understood measures your guess |

Four methods have a runner that records sessions: `usability`, `tree-test`, `card-sort`, `first-click`
(each produces **session evidence**). `survey` and `interview` are asked elsewhere. The catalog also lists
methods pb **does not run**: diary study, contextual inquiry, concept test, five-second test and A/B
preference. If one of those fits, say so, point to the nearest runnable method or say it must be fielded
elsewhere and imported as notes. Do not pretend pb runs it.

Check the sample against the user's reach now (`ref-research` §8): a survey needs near its `targetN` (30 by
default); an interview or a usability test about 5 per segment; a tree test about 50; a card sort about 15;
a first-click test about 30. If the user cannot reach that many of the audience, say so now and offer the
other method rather than a thin study.

### 2a · Plan and define

For every method, write the research plan before the instrument. It is short, and the team can disagree
with it before anyone is recruited (`ref-research` §2 and §7). Draft it as JSON and run:

```
$T brief <id> --file <scratch.json>      # {background, objectives, researchQuestions, decision, methodRationale,
                                         #  participants{criteria, exclude, n, segments}, recruitment{channel, incentive, note},
                                         #  schedule{start, end, sessionMinutes}, team{moderator, notetaker, observers},
                                         #  materials, risks[{risk, mitigation}], timeline[{milestone, date}], budget}
```

`brief` merges into `study.plan`; an unknown key is refused. **The sample target is one number:** `study.audience.targetN` is the target, and `plan.participants.n` is the same number as the plan shows it. `brief` with `participants.n` sets it; `plan --file` with `audience.targetN` sets the plan's n, and a file giving two different values is refused. Once evidence is stored the target cannot change (it was fixed before data): open a new study instead. `check` warns `W-TARGET` when an older or hand-edited study holds two different numbers. It needs `init` first (§4), so draft the plan
in the conversation now and save it right after `init`. **For a session method the plan is required:** `check`
refuses a study with no `objectives` or `researchQuestions` (`C-PLAN`) and warns when the schedule, the
recruitment or the participant criteria are missing (`W-PLAN`). On an approved study, changing the
objectives, research questions, decision, method rationale or participants **withdraws G-STUDY**; the
logistics keys (schedule, team, materials, risks, timeline, budget) do not.

## 3 · Hypotheses — written before any question

A hypothesis is a claim the answers could prove wrong. For each:

- **`statement`** — one claim, about behaviour or a fact, not about the design ("Couriers who collect cash
  settle it at the depot the same day", not "Couriers like the payment screen").
- **`targets`** — the job, story, rule, screen or component it bears on (`kind:id`). `feature` is free text
  for what the registry does not model yet.
- **`supportedIf`** and **`refutedIf`** — the observable result that settles it, written now. A survey
  states the **threshold as a number** ("at least 60% of qualified respondents choose the depot"); an
  interview states a **count of participants** ("at least 4 of 5 describe a different step"). A usability
  test states a **task criterion** ("at least 4 of 5 reach the handover screen unassisted"); a tree test,
  card sort or first-click test states the **rate or agreement** that settles it ("at least 70% choose the
  Refunds node"). A claim whose refutation cannot be written is not a hypothesis; rewrite it or drop it.
- Two to five hypotheses is a study. More means two studies.

**These thresholds are fixed here.** They are never moved after data arrives (NEVER, below).

## 4 · Write the instrument from the seed

Draft `{hypotheses, instrument, audience?, plan?}` as JSON, in the shape of a study's `hypotheses` and
`instrument` in the registry's `research` slice (`$T show <id>` prints a study once `init` has made it).
Build every question from the seed:

| From | Write |
|---|---|
| a job's `when` | "Tell me about the last time <when>." — a past episode, never "would you" |
| a job's `want` / `so` | what they did, and what they were trying to get done by doing it |
| a story's path | a **task** on the prototype: a `task` with the `screen`, `role`, `entry` (from the seed's links) and `success` (what done looks like). Say it as a goal, never as the steps |
| a rule's `ASSUMPTION` | a **behavioural** question about what people do, which the assumption predicts |
| the sitemap (`ia.sitemap[]`) | the **tree** of a tree test, and the **cards** of a card sort (from job and screen names) |

Every question in a `main` or `task` section lists the hypotheses it `tests`. Screener, warm-up and
closing questions may test none. A survey opens with a **screener** section whose answers carry
`qualifies`. An interview opens with a **warmup**. Include a plain-language `intro` and a `consent`
statement (what is recorded, who sees it, that they can stop and withdraw), a `durationMin` that is
honest, and a `closing`. Write in the language of the audience (`lang`); the surveys and guides are read
by them, not by you. Apply `ref-research` §3–§5 to every question.

### Per method

**Survey and interview** — as above. `ref-research` §6 has the building rules.

**Usability** (`ref-research` §11). Task sections hold one question per task; the questions after a task
question **in the same section** are its post-task questions. Each task:

```json
{ "id": "t1", "text": "<the scenario, read or shown to the participant, as a goal>", "tests": ["h1"],
  "task": { "screen": "<start screen id>", "role": "…?", "entry": "…?",
            "success": "<what done looks like, in plain words>",
            "criteria": [ {"screen": "handover"}, {"text": "Paid"}, {"present": "[data-done]"}, {"absent": ".field__error"} ],
            "optimalPath": ["route", "pay", "handover"], "timeLimitSec": 300 } }
```

`criteria` (optional) is a list of `screen | text | present | absent` checks; **all** must hold at one moment
for the task to count as "criteria met". `optimalPath` (optional) turns on lostness. `timeLimitSec` ends the
task as a timeout. **Write the task without the words on the buttons.** Follow each task with a post-task
`seq` template question (`W-SEQ` warns when a task has none). Set the instrument's `mode`
(`moderated|unmoderated|both`), `recording` (`{screen, voice}`: what may be *asked for*, the participant
still opts in), `device` and `thinkAloud`. A moderated test has a warmup section (`W-WARMUP` otherwise).

**Tree test** (`ref-research` §12). `instrument.tree` is the flat list of nodes `{id, label, parent}`
(parent is a node id or `null`); each task is `{"id": "tt1", "text": "Where would you go to …?", "tests":
["h1"], "tree": {"correct": ["n-refunds"]}}`. The participant sees labels only, never the answer; use the
live navigation wording and write the task without a label in it (`check` and the bias review look for
parroting).

**Card sort** (`ref-research` §13). `instrument.cards` is `[{id, label, job?}]` (4 or more; 10 to 60 is
steady), and `instrument.sort` is `{kind: open|closed|hybrid, categories: [{id, label}], tests: ["h1"]}`.
Closed and hybrid need at least 2 categories. There are no per-task questions; the sort lists the
hypotheses it tests. Card labels carry no category names.

**First-click** (`ref-research` §14). Each task is `{"id": "fc1", "text": "…", "tests": ["h1"], "click":
{"screen": "pay", "target": "[data-action=\"submit\"]", "rect": {"x": 0.1, "y": 0.8, "w": 0.3, "h": 0.1}}}`.
`target` is a selector and/or `rect` is a region (fractions of the screen); a hit is a click inside either.
The page captures the first click and never lets it navigate.

**Standard metrics.** When what the user wants to know is one of the measures below, use the template
instead of writing your own question. Say which is for what, and why you chose it (`ref-research` §15):

| Template | Use it for |
|---|---|
| `ces` | **Effort** over a whole flow: how hard it was to get the thing done |
| `seq` | **Ease** right after one task on the prototype (the post-task question of a usability test) |
| `csat` | **Satisfaction** with an experience |
| `nps` | **Recommendation** of a product people have really used. **Never of a prototype they just saw** |
| `sus` | **Overall usability** after real use; ten items |

Write the question as `{"id": "q9", "template": "ces", "subject": "<what the question is about>"}`. `plan`
expands it with the standard wording. **Do not reword a standard question**; a translated `text` is accepted
and draws warning `W-TEMPLATE-TEXT`, which you list at the gate. A **survey** is scored by `tally` and a
usability test by `analyze`. In an interview a template question is read out and is not scored. How to read
each score, and when not to use it: `ref-research` §15 and §16.

Then:

1. Save the JSON to a scratch file outside `memory/` and run `$T init <id> --method
   survey|interview|usability|tree-test|card-sort|first-click --scope instrument|collect [--setup "<text>"]
   --question "<verbatim>" [--title T] [--role R]… [--segment S] [--target kind:id]… [--target-n N]
   [--mode moderated|unmoderated|both]`. `--scope` and `--setup` are the answers from §0; `--mode` (session
   methods) is how it will be run and seeds the logistics checklist (§5). Run `init` once per study. An
   existing id, an unresolved target or an undeclared role is refused.
2. `$T brief <id> --file <plan.json>` (§2a), then `$T plan <id> --file <scratch.json>`.
3. `$T check <id>`. **Fix every error and re-run.** For each warning left, write one line saying why it
   stays ("'and' joins two words of one option, not two questions"). Never present around an error.
4. **Independent bias review.** The context that wrote the questions cannot see their bias: it already
   knows what they mean to find. A fresh agent that sees only the questions reads them cold.
   1. `$T review-plan <id>`. It writes `memory/research/<id>/instrument/bias-review.md`, which holds **only
      the questions**, each with yes/no items about bias (leading, double-barrelled, hypothetical, and so on).
      For the session methods it also covers task wording that uses a label on screen (usability and
      first-click), tree labels that parrot the task (labels are shown, never the answer) and card-sort wording.
   2. Dispatch one **`pb:pb-tester`** agent with the Task tool and `model: sonnet`, the same way `/pb:test` §2b
      dispatches (the plugin's name, `pb:pb-tester`; fall back to `pb-tester` if only the project name exists).
      If the host cannot pin a model, dispatch anyway and say so: the fresh context is the load-bearing part.
      **Hand it exactly this and nothing more:**

      > Answer every item in `<absolute path to bias-review.md>`. Return one row per item id, `<id> · yes | no | blocked · <one-line evidence>`, and nothing else.

      **Never hand it** the hypotheses, the thresholds, the question being studied, `memory/` files, the
      registry, the seed, the audience or goal, the answer keys, or any framing from this conversation (what is being
      measured, what a good answer looks like). Do not tell it to be strict or lenient.
   3. Save its rows, exactly as returned, to a scratch file outside `memory/` and run `$T review <id> --file <rows>`.
      The tool stores them and matches every item id; a missing or extra id is refused.
   4. **You cannot overturn a `no`.** Fix the question in the scratch file, then `plan`, `check`,
      `review-plan` and dispatch a **fresh** agent again, or carry the `no` up to G-STUDY and let the user decide
      there. Never re-grade it yourself, and never re-word an item.
   5. Skipping the review needs the user's stated reason: `$T approve <id> --skip-review "<their reason>"`
      (§G-STUDY). Subagents being unavailable is a reason to ask, not a reason to self-grade.
5. `$T export <id>` writes the readable instrument; a draft's files are headed `DRAFT — not approved`.

Once any evidence exists, `plan` is refused: the responses would no longer match the questions. A change
then is a new study.

## ▛ G-STUDY — human gate ▟
**STOP.** Present, in full and not summarised:

- the question, verbatim, and the audience: roles, segment, **target N**, and how the sample will be
  reached (name the channel; if the user has none, say the study cannot be fielded yet)
- the **research plan**: objectives, research questions, the decision it informs, why this method (and what
  it cannot tell), the schedule, the team, the risks. For a session method, whether it runs **moderated**
  (on this machine), **unmoderated** (a kit file) or both, and whether screen and voice recording will be asked for
- the **recruiting screener**: every screener question and which answers qualify
- every hypothesis with its `supportedIf` and `refutedIf` (the thresholds)
- **every question**, in order, with its type, its options or scale, its probes, and the hypotheses it
  tests; each task with its screen, entry, success, criteria, optimal path and time limit; the tree, the
  cards and the sort kind, or each click target, as the participant will meet them. **The correct answers of
  a tree test and the click targets stay in this gate; the participant never sees them**
- the `intro` and `consent` text as the participant will read them
- the `check` result: zero errors, and each remaining warning with your reason
- the **bias review**: every row that is `no` or `blocked`, with the reviewer's evidence, verbatim and
  next to the question it is about. Say how many rows were `yes`. A question you changed after a `no`
  is shown with the review of its new wording. If the review was skipped, say so and give the user's reason
- the scope and setup from §0, as stored

Ask for **approve**, **edit** or **reject**. Silence is not approval. **Nothing below runs until this is
answered.**

- **Approve** → `$T approve <id> [--note "<what was said>"]`. It requires a clean `check` and a current
  bias review, sets the status to `approved`, records the gate, **ticks `plan-approved` on the logistics
  checklist** and writes the instrument files. It prints the review flags again: read them back to the user.
  Two refusals are the user's to settle, not yours:
  - **No current review** (none was run, or the questions changed after it) → run §4 step 4 again. Only if
    the user states a reason for going without one: add `--skip-review "<their reason>"`.
  - **A row is `no` or `blocked`** and the user keeps the question as it is → add `--accept-review "<why it
    stands, in the user's words>"`. Never write that text for them.

  Then give the user the files under `memory/research/<id>/instrument/`:
  - a survey: `survey.md` and `responses-template.csv`; an interview: `interview-guide.md`;
  - every method also gets `plan.md`, `moderator-guide.md`, `tasks.md` (or `cards.md` for a card sort),
    `consent.md`, `screener.md` (when a screener exists) and `note-taking.csv`;
  - how to field it, plainly: **nothing is hosted online.** For a survey, paste the questions into any survey
    tool the user already uses, send it to the screened audience, and export the responses as CSV. For an
    interview, run the guide with real people, get consent first, and save a transcript or notes as text
    (a recording alone cannot be quoted: keep a transcript too). For a usability test, tree test, card sort
    or first-click test, §6 says how to run it here or from a kit. Use the setup recorded in §0 (their survey
    tool, panel or list); where they said they have none, say that part is still theirs to find;
  - **scope `collect` only:** how to come back (§5, §6), `/pb:research --import <id> <file>` for each export
    or transcript, then `/pb:research --synthesize <id>`.

  **For a survey or an interview the turn ends here.** Do not wait for answers, and do not generate any.
  **Scope `instrument`: the run is complete.** Do not mention import, sessions, synthesis, insights or
  refill, and do not call the study unfinished.
- **Edit** → apply to the scratch file, `plan` again (a changed approved study falls back to draft and the
  gate is withdrawn), `check`, run the bias review again (§4 step 4), re-present, ask again. An edit
  re-opens the gate.
- **Reject** → nothing is fielded. Say what to rework, or stop.

## 5 · Logistics — scope `collect` only

A study is lost more often in the logistics than in the questions. The tool seeds a checklist at `init`
from the method and the mode (plan approved, screener ready, consent ready, withdrawal agreed, tasks or
tree or cards checked, incentives budgeted, note-taker assigned, call link ready, **pilot run**, recording
tested, the kit opened on a clean machine for unmoderated, invites sent, evidence imported).
`ref-research` §9 says what each means.

```
$T logistics <id>                         # the checklist, the participants by status, the schedule
$T logistics <id> --done <item-id> …      # tick (also --undo <item-id>, --add "<text>")
$T participant <id> P01 [--status invited|screened|scheduled|done|no-show|withdrawn|excluded]
        [--segment S] [--role R] [--at 2026-03-02T14:30] [--incentive due|paid|none] [--pilot|--no-pilot] [--note T] [--remove]
$T pilots <id>                            # the rehearsal sessions
```

- **Pseudonyms only.** `P01`, `P02`. A real name is never asked for or stored; an email address or phone
  number in a note is refused. The tracker lives in the study, not in a spreadsheet of real people.
- **Tick what is true, not what is hoped.** Ask the user before marking an item done; a session save also
  marks its participant `done`.
- **Pilot first, always.** One run with someone who is not on the team, in the real set-up and with the real
  recording (§6). A pilot is stored under `memory/research/<id>/pilot/`, **never as evidence and never
  analysed**, whatever it showed. Fix what it shows; if the tasks change, the next sessions are the first
  real ones. A pilot is allowed on a draft or approved study and under scope `instrument`.
- Show the user what is left on the checklist before the first real session.

## 6 · Fielding

### Survey and interview — asked elsewhere

The user fields the instrument in their own tool and brings the export or transcript back. Then
**import** it (below).

### Usability test, tree test, card sort, first-click test — moderated, on this machine

The researcher and the participant are at the same computer, or on a call where the participant shares
their screen with the researcher's machine. **Nothing leaves this machine.**

```
$T link <id> [--observer] [--participant P01] [--pilot] [--open]
```

It finds or starts the `/pb:preview` server and prints `http://127.0.0.1:<port>/research/<id>/session`
(and `/observer` with `--observer`), after checking each answers 200. A real link needs the study
approved (G-STUDY) and scope `collect`; `--pilot` works on a draft. If it says the preview predates the
research routes, run `serve.py --stop`, then `link` again.

- **Print only what `link` prints.** Never offer a LAN or online link: pages and uploads answer **this
  machine only** (loopback peer and Host), whatever `--host` or `--allow-host` says. Screen capture needs a
  secure page; `127.0.0.1` qualifies and a plain-http LAN address does not, so pb offers none.
- **The participant page** asks for consent first (required). Only if the instrument asks for it, it then
  asks, as a **separate opt-in**, to record the screen and voice. Say the participant may decline the
  recording and still take part. The page shows the prototype and the tasks, never the study's title,
  hypotheses, thresholds or answer keys. It saves straight into evidence: the session file as `e<N>`, the
  recording as `e<N+1>`, both read-only, hashed and linked.
- **The observer window** (open it on the researcher's screen, not the participant's) shows the live
  events, the timer and the task, takes notes, offers **Assist** (marks the task assisted, so it does not
  count as a success) and an **outcome override**, and holds the moderator script. Run the session with
  `ref-research` §11: no help, think-aloud, probes only from the script.
- **What is recorded:** screens, clicks named by component, dead and rage clicks, field input as **length
  only (never the value)**, submits, validation errors, toasts, wizard steps, role changes, each task with
  its outcome (success, fail, abandoned, timeout, skipped; `answered` for a tree-test choice), answers and
  the facilitator's notes. Tell the participant this at consent, in plain words.
- After a session, tick the checklist and update the tracker (§5).

### Unmoderated — from a kit file

```
$T kit <id> [--out PATH] [--pilot]
```

It writes `memory/research/<id>/kit/<id>-kit.html`: **one self-contained file** (no hypotheses, success
criteria, answer keys, research slice or insights, and no network call). Send that one file to the
participant by a private channel. They open it in a current Chrome or Edge, type the code you gave them
(`P01`, never a name), consent, do the tasks, and at the end download `<id>-<P>-<session>.pbsession.json`
(and `…-screen.webm` if they agreed to record). They send both back. Run the kit yourself once on a clean
machine first (`kit --pilot`).

### Import — every kind of evidence

**Scope `collect` only.** On an `instrument` study the tool refuses `import`; do not try, and do not
suggest it. If the user brings results anyway, ask whether they now want them kept as evidence, and if so
change the scope (§0) and carry on.

Run when the user brings a file. Ask, in this order, one thing at a time if missing:

1. **Consent.** `yes` if the participant agreed to be recorded and quoted; `unknown` if you cannot tell;
   `no` is refused: do not import, and tell the user to delete their copy. `--consent` is required. A
   session file records the participant's own consent, so it is imported with `--consent yes`.
2. **Participant.** A pseudonymous id (`P01`) for an interview or a session. **Never ask for or store a real
   name.** If the file itself carries names, address the PII step below. A survey export covers many people
   and needs none.
3. **Kind** (`responses`, `transcript`, `notes`, `recording`, `session`, `other`), the **date** it was collected and,
   if the file is one participant's, their **role** and **segment**.

```
$T import <id> <file> --kind K --consent yes|unknown [--participant P] [--role R] [--segment S] [--date D] [--drop-columns A,B] [--keep-pii]
$T import <id> <p01>.pbsession.json --kind session --consent yes
$T import <id> <p01>-screen.webm --kind recording --session <sessionId> --consent yes
```

- **PII columns.** The tool refuses a CSV header that looks like an email, name, phone or address (Vietnamese
  ones too). Default to `--drop-columns` with the named headers: they are removed before anything is stored.
  Use `--keep-pii` only if the user states they need the column and why, and then say so in G-INSIGHT.
- Read the report back to the user: which columns matched which question, which were **ignored**, and any
  PII warning from the scan of a text file. Zero matched questions is a refusal: the export does not belong
  to this study, or a question was reworded; ask, do not force. A session file is validated against the
  study (its tasks, its tree, its cards); a pilot session is stored under `pilot/`, not as evidence, and a duplicate is refused.
- The file is copied to `memory/research/<id>/evidence/e<N>-<name>`, made read-only, and hashed. **Never
  edit it, and never edit a copy and call it the original.** A mistake in the file is fixed by dropping the
  evidence and importing a corrected export.
- **A recording is participant data.** It carries a voice and a face of the screen. It is stored only for a
  session whose participant opted in, and a mode 1 hand-off leaves it out unless `/pb:handoff --with-recordings` is given (`/pb:handoff` calls
  `$T bundle --out handoff/bundle [--with-recordings]`; you do not run it for a hand-off). In a received project a
  withheld recording keeps its evidence row and sha256: `verify` warns `W-WITHHELD` (not an error), the report adds a
  limitation line, and the replay plays the event log without video and says the recording was left out. If the
  sender passes the file on separately, put it at the path `memory/research/HANDOFF.md` lists and run `$T verify <id>`,
  which checks its sha256. Say all of this to the user.
- **A participant withdraws** → `$T drop-evidence <id> <eid> --reason "<their words or the user's note>"`.
  The file goes; the row stays, struck out, with its hash. **Dropping a session drops its linked recording
  too.** Any finding or observation that cited it now fails `verify`; rewrite it (§8) without that person.
- After a survey import: `$T tally <id>`. It drops respondents who fail the screener (and counts them),
  then computes n, option counts and scale and number means per question. It warns under `targetN`. Use
  `$T tally <id> --by qN` to break results down by one question. That prints a breakdown and stores
  nothing. Keep `n` per group in view, and call a difference between small groups what it is.
- **Replay** (session evidence): `/research/<id>/replay/<eid>` on the preview re-plays the session on the
  prototype, with click dots and a timeline, synced to the video when there is one. Watch the sessions
  before you analyse them; `ref-research` §17.

## 7 · Analysis — session methods

After the sessions are imported, **the tool computes the numbers**; you read them (`ref-research` §16–§17).

```
$T analyze <id>        # → study.analysis, from the stored (non-pilot, non-dropped) sessions
$T affinity <id>       # tag × participant counts over your observations (read-only)
```

What `analyze` stores, by method:

- **usability** — per task: success rate with an **adjusted-Wald 95% interval**, time on task as a
  **geometric mean with an interval** (successful attempts), lostness (with `optimalPath`), clicks, dead and
  rage clicks, errors, SEQ, the paths taken; and across the study the SUS score with its **Sauro–Lewis
  grade** (intervals clamped to the scale). An assisted success is counted apart, not as a success.
- **tree-test** — per task: success, directness (no backtracking), first click, the destinations chosen.
- **card-sort** — the similarity matrix, average-linkage clusters, category agreement.
- **first-click** — per task: success with an interval, time to click, the click points.
- Pre- and post-task answers, as in a survey.

It warns `W-DUP-PARTICIPANT` when one pseudonym appears in two sessions and `W-DIRECTIONAL` below the
method's target n. **Say both.** Do not count, average or round anything yourself.

## 8 · Synthesis — verdicts, observations, issues, report, refill

Start when the evidence is in, or when the user stops fielding. Say `n` before anything else.

1. **Read every transcript in full, and watch or replay every session** (`/research/<id>/replay/<eid>`),
   and `$T show <id>` for the state. Not an excerpt, not a summary, not the first N. If an evidence file is
   opaque (pdf, audio with no transcript) it cannot be quoted: ask the user for a text transcript.
2. **Code before concluding.** Per participant, note what happened and what was said, then group. Keep
   observation (what they did, said, got wrong) apart from interpretation (what it means). Count
   **participants**, not mentions. `ref-research` §18.
3. **Disconfirming evidence is a finding, and first-class.** For each hypothesis, look for the
   participants who contradict it and report them before the ones who agree.
4. **Every number comes from the tool** — `tally` for a survey, `analyze` for a session study. Do not count,
   add, average or round anything yourself: a number not in the tool's output is not in the finding. A
   standard metric (`ces`, `seq`, `csat`, `nps`, `sus`) is scored by the tool too: cite a survey's score as
   `{"tally":"q9","stat":"ces","value":N,"of":N}` (the `q` id of the template question, `stat` set to the
   template name, `value` and `of` copied from the tally). **A session study cites its numbers by path:**
   `{"analysis": "usability.tasks.t1.success.rate", "value": 0.8}`, copied from `analyze`. Read them with
   `ref-research` §15–§16; any benchmark you mention is context, never the pass mark, and the hypothesis's
   own threshold from §3 is what decides the verdict. A template question in an interview was read out and
   has no score: do not cite one. For an interview, a count of participants is stated as "3 of 5" and the
   `of` is the evidence you attached. **Every quote is copied verbatim** from the evidence file, in the
   language it was said; never paraphrase inside quote marks, never quote from memory. A translation goes
   outside the quote marks.
5. **Verdict per hypothesis against the thresholds set in §3, never moved:** `supported`, `refuted`,
   `mixed`, or `inconclusive`. **Inconclusive is an honest verdict**: too few people, answers that split
   the audience, an instrument that failed. Say which, and what a next study would change.
6. **Session studies: observations, themes and issues.**
   - An **observation** is one thing that happened or was said, with a `note` and one or two lowercase
     `tags` that name the thing (`total-hidden`), and it **cites its evidence**: a session `event` index, a `t`
     in milliseconds into the session or its recording, or a verbatim `quote`.
   - A **theme** groups tags into an insight, written after `affinity`.
   - An **issue** is a specific problem on a specific task and screen, with its observations, a
     recommendation and a **severity you propose** on Nielsen's scale (0 not a problem · 1 cosmetic · 2 minor
     · 3 major · 4 catastrophe). **The user approves the severities at G-INSIGHT.** The tool computes the
     participants affected, the frequency and the priority; **a typed one is refused. Never type them.**
7. Write a scratch JSON file:

```json
{ "verdicts": { "h1": { "verdict": "refuted", "why": "<one or two sentences against the threshold>" } },
  "findings": [ { "id": "f1", "text": "<observation first, then what it means>", "hypotheses": ["h1"],
                  "targets": [ { "kind": "job", "id": "<id>" } ],
                  "evidence": [ { "evidence": "e2", "quote": "<verbatim>", "participant": "P02" },
                                { "tally": "q2", "option": "Yes", "count": 18, "of": 30 },
                                { "analysis": "usability.tasks.t1.success.rate", "value": 0.8 },
                                { "issue": "u1" }, { "observation": "o1" } ] } ],
  "observations": [ { "id": "o1", "evidence": "e2", "participant": "P02", "task": "t1", "event": 41,
                      "note": "<what happened>", "tags": ["total-hidden"] } ],
  "themes": [ { "id": "th1", "title": "<…>", "tags": ["total-hidden"], "insight": "<…>" } ],
  "issues": [ { "id": "u1", "title": "<…>", "task": "t1", "screen": "pay", "severity": 3,
                "observations": ["o1"], "recommendation": "<…>", "targets": [ { "kind": "screen", "id": "pay" } ] } ],
  "report": { "summary": "<…>", "recommendations": [ { "text": "<…>", "issues": ["u1"], "route": "clarify|explore|build|none" } ],
              "nextSteps": ["<…>"], "limitations": ["<what the tool does not add itself>"] },
  "refill": { "quantitative": "<only numbers that are in a finding, the tally or the analysis>",
              "researchSummary": "<what people said and did>", "executiveSummary": "<one paragraph>" } }
```

   Use only the keys that fit the method: a survey or interview has no observations, themes, issues or
   report narrative.
8. `$T synthesize <id> --file <scratch.json>` (it runs `tally` first for a survey and `analyze` for a
   session study, then `verify`), then `$T verify <id>`. It writes even when verify fails, so errors can be
   fixed; the status becomes `analysed` only on a clean verify. **Fix every error and re-run until clean.**
   A quote not found verbatim means you altered it: re-copy it. A tally or analysis mismatch means your
   number is wrong: use the tool's. Observations draw `V-OBS`, issues `V-ISSUE`, themes `V-THEME`, the
   stored analysis `V-ANALYSIS` (recomputed fresh from the evidence; stale `inputsHash` is an error) and
   the report `V-REPORT`. **A failing verify is never presented around**, never explained away, and never
   worked around by editing the evidence.
9. The `refill` text follows `/pb:clarify` §1a's marks (`**…**`, `{-…-}`, `{+…+}`; no more than about one
   per sentence; no wording changed to fit a mark). The tool appends each field as `<text> [<id>]`, so
   leave the study id out of the text yourself.
10. **Session studies: the report.** With a clean verify and status `analysed`:
    `$T report <id>`. It writes `memory/research/<id>/report/report.md` and `report.html` (one
    self-contained, printable page with inline charts and number tables, carrying a **Draft banner until
    G-INSIGHT**), and prints its address on the preview, `/research/<id>/report`. It is refused while
    `verify` has errors: a report states only what verifies. The report holds participants by pseudonym only.

## ▛ G-INSIGHT — human gate ▟
**STOP.** Present, in full:

- the **verdict for each hypothesis**, against its threshold as written in §3, with the `why`
- **every finding** with its evidence: the quotes (with participant id and evidence id), the tally numbers
  and the analysis numbers, **disconfirming evidence first**
- **session studies: the report** — give the path and the address of `report.html` (`/research/<id>/report`)
  and open it for the user; and **every issue with the severity you proposed**, ranked by the tool's
  priority, so the user can change a severity before approving
- **the exact text** `refill` would append, field by field, as it will read, including the `[<id>]` suffix
- every `verify` **warning**, in plain words: below `targetN` ("directional only"), a finding that rests
  on one participant, a severity 3 or 4 issue resting on one participant (`W-ONE-PARTICIPANT`), evidence with
  `consent: unknown`, a PII hit in a quote, a number in the refill found in no finding, a very short quote
- what the study could not tell: the audience it did not reach, the question it did not ask, the sessions with
  no recording, the assisted successes

Ask for **approve**, **edit** or **reject**. Silence is not approval. **Nothing is appended before this
is answered.**

- **Approve** → `$T refill <id> --approved [--note "<what was said>"]`. It backs the registry up under
  `memory/backups/research-<id>-<stamp>/`, appends to `meta.userInsights.*`, sets the status to `applied`,
  and **regenerates the report without the Draft banner**. A re-run is a no-op; if someone edited the
  appended text since, it appends again and warns: say so. It never touches other text.
- **Edit** → change the scratch file, `synthesize`, `verify`, `report`, re-present. An edit re-opens the gate.
- **Reject** → nothing is appended; the evidence and the findings stay in the study. Ask whether to gather
  more or to leave the verdicts as they are.

## 9 · Close the loop

1. **One `memory/decisions.md` entry**, in `/pb:clarify` §4's shape (read `decisions*.md` for the subject
   first; if an older entry decided it, show it and ask whether this supersedes it):

```markdown
## <date> — <the question, as a decision>
- **Decision:** <the verdicts, in one line: h1 refuted, h2 supported…>
- **Why:** <the evidence: n, the threshold, the finding ids>
- **Alternatives:** <what the study ruled out>
- **Affects:** <the jobs, rules or screens the targets name>
- **Rule:** <ia.rules[].id the finding bears on, or none>
```

   Add the study id and both gate approvals (G-STUDY, G-INSIGHT).
2. **Route, do not apply.** A verdict, or a report recommendation, that says a job, a rule or the structure
   is wrong is a proposal. Print it with the finding or issue id and send it to its owner; make none of the
   change here:

| The verdict says | Route |
|---|---|
| a **job** is wrong, missing or mis-stated | `/pb:clarify` §1b, citing the finding |
| a **rule** is wrong or an `ASSUMPTION` held or failed | `/pb:clarify` §2, citing the finding, which updates the rule and its `decision{}` |
| the **structure** of a screen or flow should differ (an issue on a screen, a tree test or card sort result) | `/pb:explore`, with the finding as the reason |
| a **clear fix** to a component or screen | `/pb:build`, citing the issue |

   **Never edit a rule, a job or a screen from here.**
3. **Where to read it.** UX: Project Summary → Research (the plan, the participants, the sessions with
   their Start, Observer and Replay links when the preview serves them, the results, the issues ranked by
   priority, the themes and the report link) and Project Summary → Insights (the refilled text). Tell the
   user which preview URL shows it if a `/pb:preview` server is up; do not start one for this.

**Do not render.** The registry is the source of truth; `/pb:preview` shows the change without it.

## Result
A study in the registry's `research` slice with the scope and setup the user chose (§0), its plan and
instrument (independently bias-reviewed) under `memory/research/<id>/instrument/`. For scope `instrument`
that is the whole result. For scope `collect`, also its evidence under `memory/research/<id>/evidence/`
(read-only, hashed, with consent recorded; for session methods the sessions and their recordings), the
participant tracker and logistics checklist, verdicts that are checked against thresholds fixed before the
data, findings whose quotes and numbers the tool has verified, for session methods the observations, themes,
issues and the report under `memory/research/<id>/report/`, User Insights refilled with a citation back to
the study, and one decision-log entry.

## NEVER
- NEVER simulate respondents, fill in answers, role-play a participant or generate "synthetic users" as
  evidence. Not as a draft, not as a placeholder, not "labelled as synthetic" in the evidence folder. An
  instrument is tested on a real person or not at all.
- NEVER simulate a session: do not run the participant page, the kit or a runner yourself and store what
  you did as a session, as evidence, as a pilot or as a demonstration.
- NEVER edit a stored evidence file, or write one yourself. Evidence comes from `import` and from the
  session routes the tool serves.
- NEVER compute a number by hand. Counts, means, percentages and rates come from `tally` and `analyze`;
  if the tool cannot produce a figure, do not state it.
- NEVER type a computed number: an issue's frequency, participants or priority, a success rate, a time, a
  score. The tool refuses it; do not look for a way round.
- NEVER move a threshold, a `supportedIf` or a `refutedIf` after seeing data. A wrong threshold is
  recorded as such in the verdict's `why`, and the next study fixes it.
- NEVER write the `research` slice by hand: `init`, `scope`, `brief`, `plan`, `review`, `approve`,
  `participant`, `logistics`, `import`, `drop-evidence`, `tally`, `analyze`, `synthesize`, `report` and
  `refill` are the only writers.
- NEVER quote from memory, paraphrase inside quote marks, or fix a participant's grammar in a quote.
- NEVER present a finding from a participant who withdrew, and never present around a failing `verify`.
- NEVER ask for or store a real name, an email address or a phone number; never import a `--consent no`
  file; never keep a PII column unless the user asked and gave the reason.
- NEVER hide a disconfirming result, an inconclusive verdict, a small sample or an unknown consent to make
  a gate look finished.
- NEVER apply a verdict to a job, rule or screen yourself: route it (§9).
- NEVER approve at either gate for the user, and NEVER pass `--approved` before G-INSIGHT is answered.
- NEVER skip the opening question (§0), even when the request sounds obvious or the study is being resumed.
- NEVER pick the scope for the user, or assume a survey tool, panel or participant list they did not name.
- NEVER offer an online test, a hosted link, a panel, or a link on the local network: nothing is hosted
  online, and sessions run on this machine or from a kit file.
- NEVER show a participant the hypotheses, thresholds, the study's title or question, the research slice,
  the insights or an answer key (a tree test's correct nodes, a first-click target, a task's criteria).
- NEVER record the screen or voice of someone who has not opted in to it separately, and never treat a
  pilot as evidence.
- NEVER hand the bias reviewer the hypotheses, the thresholds, the question being studied or any framing
  from this conversation: the reviewer gets the path to `bias-review.md` and nothing else.
- NEVER overturn a reviewer's `no` yourself, and NEVER pass `--accept-review` or `--skip-review` with words
  the user did not give.
- NEVER reword a standard metric question, or call a benchmark a pass mark.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
