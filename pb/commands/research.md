---
description: Validate what the project is unsure about with real people — frame a falsifiable question from the jobs, flows and rules, write a survey or interview guide seeded from them, approve it at G-STUDY, store the fielded results as immutable evidence, synthesize verdicts with tool-computed numbers and verbatim quotes, and refill the User Insights at G-INSIGHT.
---

# /pb:research [<question or kind:id>] [--survey|--interview] [--role R] [--segment S] [--gaps] [--import <id> <file>] [--synthesize <id>]

Turn "we are not sure" into a study, run it outside pb, and (if the user wants it) bring the evidence back. **Every run
opens by asking what the user needs and what their setup is (§0).** The registry
already holds the **jobs** (`ia.jobs[]`: when / want / so), the **flows** (`flow.stories[]`) and the
**rules** (`ia.rules[]`, some marked `ASSUMPTION`). This command writes a survey or an interview guide
from them, for one role or segment, and files what comes back as evidence a later reader can check.

**The division of labour.** The tool does the arithmetic and the quote-checking. You do the
interpretation. **Two human gates, in order: ▛ G-STUDY ▟ (the instrument, before anyone is asked) and
▛ G-INSIGHT ▟ (the findings, before they touch the insights).** Each is blocking and presents the
artifact, not a summary of it (`${CLAUDE_PLUGIN_ROOT}/docs/canon.md` § *What makes a gate real*).
Silence is not approval. The evidence rules are in `${CLAUDE_PLUGIN_ROOT}/docs/canon.md` § *Research evidence*.

**pb hosts nothing.** No survey page, no recording, no panel. It writes a readable instrument and a CSV
template; the user fields it in any survey tool or runs the guide with real people, then brings the
export or transcript back. Fielding takes days: **this command is resumable** — the study's status and
files carry the state, and `list` shows where each one stopped.

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
   - **(i) Just the questions and the setup.** pb writes the instrument and says how to field it. Nothing
     comes back to pb. Scope `instrument`.
   - **(ii) Questions plus results.** The user will bring the results back to be stored as evidence, and the
     findings will refill the User Insights. Scope `collect`.
2. **"What is your setup?"** Which survey tool, panel or list of participants they have, and where results
   live today. If they have none of it, say plainly that this part is skipped and that you will not assume
   one. pb hosts nothing in this release: do not offer an online test, a link or a panel that does not exist.
3. **Record it.** A new study: pass `--scope instrument|collect` (and `--setup "<their words>"` when they gave
   one) to `$T init` in §4. Before the study exists, keep the two answers in the conversation and carry them to `init`. An existing
   study whose answer changed: `$T scope <id> --scope S [--setup T]`.
4. **On a resumed run, this is one line.** Run `$T show <id>`, state the stored scope and setup, and ask
   whether they still hold. If they do, go on. If not, run `$T scope` first.

Scope decides what the rest of the run does:

| Scope | The run covers | The run ends |
|---|---|---|
| `instrument` | §1–§4 and ▛ G-STUDY | **After G-STUDY.** The user gets the files and how to field them. Do not ask about import, synthesis or refill, and do not describe the study as unfinished: handing over the instrument is the whole job |
| `collect` | §1–§7 | After the decision-log entry (§7), with the fielding break at G-STUDY |

`import` is refused on an `instrument` study. If the user later wants their results kept, that is a change of
answer to question 1: run `$T scope <id> --scope collect`, then §5.

## 0a · Flags and entry points

Read this after §0 has been answered.

| You are given | Do |
|---|---|
| *(nothing)* or `--gaps` | `$T gaps` (add `--role R` when a role was given), show the ranked rows (`kind · id · title · roles · why`) and let the user pick. Never pick for them. `--gaps` alone stops after the pick is made and the study is framed |
| a sentence | It is the question. §1 |
| `kind:id` (`job:pay-cod`, `rule:cod-limit`) | A target. Its `why` in `gaps`, or its job's `gap`, is the question: confirm it in the user's words |
| `--survey` / `--interview` | The method is chosen; §2 only checks it fits |
| `--role R` / `--segment S` | Who is asked. A segment no role covers is fine |
| `--import <id> <file>` | Resume at §5 for study `<id>` |
| `--synthesize <id>` | Resume at §6 for study `<id>` |
| a study id with no other flag | `$T show <id>` and resume from its `status`: draft → §3/§4 · approved or fielding → §5 · fielding with evidence → §6 · analysed → G-INSIGHT · applied → §7 |

To find a study that is already underway: `$T list`. A resumed study re-enters through §0 first (the one-line
check), then the row above.

## 1 · Frame — what exactly is unsure, and who is asked

1. **Restate what is unsure, verbatim.** Quote the user's sentence, or the gap row, or the rule's
   assumption text. Where your restatement and the request differ, the request wins. Do not narrow it
   ("the simple half"), widen it, or swap in what you think they really need.
2. **Name who is asked** — `--role` (a `meta.roles[].id`), `--segment` (free text: "rural, under a year
   on the job"), or both. A study with neither is refused by the tool and is not a study: "users" is not an
   audience. If the person who would answer is not the person the project calls a role, say so and use the segment.
3. **Run the seed.** `$T seed <kind:id> [<kind:id> …]` for each target. It returns the job's when / want /
   so, the roles, the screens, the stories that touch it (title, path, scenarios), the rules, and the
   prototype links for tasks. Everything in §3–§4 is built from that output; invent no job, screen or link.
4. Pick a study id, `rs-<kebab>`, short and about the question.

Invoke `ref-research` now. It carries the method: question-writing rules, the bias list, sample guidance
and how to read results.

## 2 · Choose the method — say why

State the method and the one-line reason. Ask only when it is not obvious.

| The question is | Method |
|---|---|
| *why* or *how* people do it, or you do not know what you do not know | **interview** |
| whether a person can complete a flow on the prototype | **interview** with a task |
| *how many* or *how often*, or sizing something already understood from interviews | **survey** |
| both | Interview first. A survey on a question you have not understood measures your guess |

A survey needs somewhere near its `targetN` (30 by default) people; an interview study needs about 5 per
segment (`ref-research` §6). If the user cannot reach that many of the audience, say so now and offer the
other method rather than a thin survey.

## 3 · Hypotheses — written before any question

A hypothesis is a claim the answers could prove wrong. For each:

- **`statement`** — one claim, about behaviour or a fact, not about the design ("Couriers who collect cash
  settle it at the depot the same day", not "Couriers like the payment screen").
- **`targets`** — the job, story, rule, screen or component it bears on (`kind:id`). `feature` is free text
  for what the registry does not model yet.
- **`supportedIf`** and **`refutedIf`** — the observable result that settles it, written now. A survey
  states the **threshold as a number** ("at least 60% of qualified respondents choose the depot"); an
  interview states a **count of participants** ("at least 4 of 5 describe a different step"). A claim whose
  refutation cannot be written is not a hypothesis; rewrite it or drop it.
- Two to five hypotheses is a study. More means two studies.

**These thresholds are fixed here.** They are never moved after data arrives (NEVER, below).

## 4 · Write the instrument from the seed

Draft `{hypotheses, instrument, audience?}` as JSON, in the shape of a study's `hypotheses` and
`instrument` in the registry's `research` slice (`$T show <id>` prints a study once `init` has made it).
Build every question from the seed:

| From | Write |
|---|---|
| a job's `when` | "Tell me about the last time <when>." — a past episode, never "would you" |
| a job's `want` / `so` | what they did, and what they were trying to get done by doing it |
| a story's path | a **task** on the prototype: a `task` with the `screen`, `role`, `entry` (from the seed's links) and `success` (what done looks like). Say it as a goal, never as the steps |
| a rule's `ASSUMPTION` | a **behavioural** question about what people do, which the assumption predicts |

Every question in a `main` or `task` section lists the hypotheses it `tests`. Screener, warm-up and
closing questions may test none. A survey opens with a **screener** section whose answers carry
`qualifies`. An interview opens with a **warmup**. Include a plain-language `intro` and a `consent`
statement (what is recorded, who sees it, that they can stop and withdraw), a `durationMin` that is
honest, and a `closing`. Write in the language of the audience (`lang`); the surveys and guides are read
by them, not by you. Apply `ref-research` §3–§5 to every question.

**Standard metrics.** When what the user wants to know is one of the measures below, use the template
instead of writing your own question. Say which is for what, and why you chose it:

| Template | Use it for |
|---|---|
| `ces` | **Effort** over a whole flow: how hard it was to get the thing done |
| `seq` | **Ease** right after one task on the prototype |
| `csat` | **Satisfaction** with an experience |
| `nps` | **Recommendation** of a product people have really used. **Never of a prototype they just saw** |
| `sus` | **Overall usability** after real use; ten items |

Write the question as `{"id": "q9", "template": "ces", "subject": "<what the question is about>"}`. `plan`
expands it with the standard wording. **Do not reword a standard question**; a translated `text` is accepted
and draws warning `W-TEMPLATE-TEXT`, which you list at the gate. Only a **survey** is scored. In an interview a
template question is read out and is not scored. How to read each score, and when not to use it: `ref-research` §9.

Then:

1. Save the JSON to a scratch file outside `memory/` and run `$T init <id> --method survey|interview
   --scope instrument|collect [--setup "<text>"] --question "<verbatim>" [--title T] [--role R]… [--segment S]
   [--target kind:id]… [--target-n N]`. `--scope` and `--setup` are the answers from §0. Run `init` once per
   study. An existing id, an unresolved target or an undeclared role is refused.
2. `$T plan <id> --file <scratch.json>`.
3. `$T check <id>`. **Fix every error and re-run.** For each warning left, write one line saying why it
   stays ("'and' joins two words of one option, not two questions"). Never present around an error.
4. **Independent bias review.** The context that wrote the questions cannot see their bias: it already
   knows what they mean to find. A fresh agent that sees only the questions reads them cold.
   1. `$T review-plan <id>`. It writes `memory/research/<id>/instrument/bias-review.md`, which holds **only
      the questions**, each with yes/no items about bias (leading, double-barrelled, hypothetical, and so on).
   2. Dispatch one **`pb:pb-tester`** agent with the Task tool and `model: sonnet`, the same way `/pb:test` §2b
      dispatches (the plugin's name, `pb:pb-tester`; fall back to `pb-tester` if only the project name exists).
      If the host cannot pin a model, dispatch anyway and say so: the fresh context is the load-bearing part.
      **Hand it exactly this and nothing more:**

      > Answer every item in `<absolute path to bias-review.md>`. Return one row per item id, `<id> · yes | no | blocked · <one-line evidence>`, and nothing else.

      **Never hand it** the hypotheses, the thresholds, the question being studied, `memory/` files, the
      registry, the seed, the audience or goal, or any framing from this conversation (what is being
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
- the **recruiting screener**: every screener question and which answers qualify
- every hypothesis with its `supportedIf` and `refutedIf` (the thresholds)
- **every question**, in order, with its type, its options or scale, its probes, and the hypotheses it
  tests; each task with its screen, entry and success
- the `intro` and `consent` text as the participant will read them
- the `check` result: zero errors, and each remaining warning with your reason
- the **bias review**: every row that is `no` or `blocked`, with the reviewer's evidence, verbatim and
  next to the question it is about. Say how many rows were `yes`. A question you changed after a `no`
  is shown with the review of its new wording. If the review was skipped, say so and give the user's reason
- the scope and setup from §0, as stored

Ask for **approve**, **edit** or **reject**. Silence is not approval. **Nothing below runs until this is
answered.**

- **Approve** → `$T approve <id> [--note "<what was said>"]`. It requires a clean `check` and a current
  bias review, sets the status to `approved`, records the gate and writes the instrument files. It prints
  the review flags again: read them back to the user. Two refusals are the user's to settle, not yours:
  - **No current review** (none was run, or the questions changed after it) → run §4 step 4 again. Only if
    the user states a reason for going without one: add `--skip-review "<their reason>"`.
  - **A row is `no` or `blocked`** and the user keeps the question as it is → add `--accept-review "<why it
    stands, in the user's words>"`. Never write that text for them.

  Then give the user:
  - the paths, `memory/research/<id>/instrument/survey.md` and `responses-template.csv` (survey) or
    `interview-guide.md` (interview);
  - how to field it, plainly: **pb hosts nothing.** For a survey, paste the questions into any survey tool
    the user already uses, send it to the screened audience, and export the responses as CSV. For an
    interview, run the guide with real people, get consent first, and save a transcript or notes as text
    (a recording alone cannot be quoted: keep a transcript too). Use the setup recorded in §0 (their survey
    tool, panel or list); where they said they have none, say that part is still theirs to find;
  - **scope `collect` only:** how to come back, `/pb:research --import <id> <file>` for each export or
    transcript, then `/pb:research --synthesize <id>`.

  **The turn ends here.** Do not wait for answers, and do not generate any. **Scope `instrument`: the run is
  complete.** Do not mention import, synthesis, insights or refill, and do not call the study unfinished.
- **Edit** → apply to the scratch file, `plan` again (a changed approved study falls back to draft and the
  gate is withdrawn), `check`, run the bias review again (§4 step 4), re-present, ask again. An edit
  re-opens the gate.
- **Reject** → nothing is fielded. Say what to rework, or stop.

## 5 · Import the evidence

**Scope `collect` only.** On an `instrument` study the tool refuses `import`; do not try, and do not
suggest it. If the user brings results anyway, ask whether they now want them kept as evidence, and if so
change the scope (§0) and carry on.

Run when the user brings a file. Ask, in this order, one thing at a time if missing:

1. **Consent.** `yes` if the participant agreed to be recorded and quoted; `unknown` if you cannot tell;
   `no` is refused: do not import, and tell the user to delete their copy. `--consent` is required.
2. **Participant.** A pseudonymous id (`P01`) for an interview. **Never ask for or store a real name.** If
   the file itself carries names, address the PII step below. A survey export covers many people and
   needs none.
3. **Kind** (`responses`, `transcript`, `notes`, `recording`, `other`), the **date** it was collected and,
   if the file is one participant's, their **role** and **segment**.

```
$T import <id> <file> --kind K --consent yes|unknown [--participant P] [--role R] [--segment S] [--date D] [--drop-columns A,B] [--keep-pii]
```

- **PII columns.** The tool refuses a CSV header that looks like an email, name, phone or address (Vietnamese
  ones too). Default to `--drop-columns` with the named headers: they are removed before anything is stored.
  Use `--keep-pii` only if the user states they need the column and why, and then say so in G-INSIGHT.
- Read the report back to the user: which columns matched which question, which were **ignored**, and any
  PII warning from the scan of a text file. Zero matched questions is a refusal: the export does not belong
  to this study, or a question was reworded; ask, do not force.
- The file is copied to `memory/research/<id>/evidence/e<N>-<name>`, made read-only, and hashed. **Never
  edit it, and never edit a copy and call it the original.** A mistake in the file is fixed by dropping the
  evidence and importing a corrected export.
- **A participant withdraws** → `$T drop-evidence <id> <eid> --reason "<their words or the user's note>"`.
  The file goes; the row stays, struck out, with its hash. Any finding that cited it now fails `verify`;
  rewrite it (§6) without that person.
- After a survey import: `$T tally <id>`. It drops respondents who fail the screener (and counts them),
  then computes n, option counts and scale and number means per question. It warns under `targetN`. Use
  `$T tally <id> --by qN` to break results down by one question. That prints a breakdown and stores
  nothing. Keep `n` per group in view, and call a difference between small groups what it is.

## 6 · Synthesize — verdicts, findings, refill

Start when the evidence is in, or when the user stops fielding. Say `n` before anything else.

1. **Read every transcript in full**, and `$T show <id>` for the state. Not an excerpt, not a summary,
   not the first N. If an evidence file is opaque (pdf, audio) it cannot be quoted: ask the user for a
   text transcript.
2. **Code before concluding.** Per participant, note what happened and what was said, then group. Keep
   observation (what they did, said, got wrong) apart from interpretation (what it means). Count
   **participants**, not mentions. `ref-research` §7.
3. **Disconfirming evidence is a finding, and first-class.** For each hypothesis, look for the
   participants who contradict it and report them before the ones who agree.
4. **Every number comes from `tally`.** Do not count, add, average or round anything yourself: a number
   not in the tally is not in the finding. A standard metric (`ces`, `seq`, `csat`, `nps`, `sus`, §4) is
   scored by `tally` too: cite its score as `{"tally":"q9","stat":"ces","value":N,"of":N}`, with the `q`
   id of the template question, `stat` set to the template name, and `value` and `of` copied from the tally.
   Read it with `ref-research` §9; any benchmark you mention is context, never the pass mark, and the
   hypothesis's own threshold from §3 is what decides the verdict. A template question in an interview was
   read out and has no score: do not cite one. For an interview, a count of participants is stated as "3 of 5"
   and the `of` is the evidence you attached. **Every quote is copied verbatim** from the evidence file,
   in the language it was said; never paraphrase inside quote marks, never quote from memory. A translation
   goes outside the quote marks.
5. **Verdict per hypothesis against the thresholds set in §3, never moved:** `supported`, `refuted`,
   `mixed`, or `inconclusive`. **Inconclusive is an honest verdict**: too few people, answers that split
   the audience, an instrument that failed. Say which, and what a next study would change.
6. Write a scratch JSON file:

```json
{ "verdicts": { "h1": { "verdict": "refuted", "why": "<one or two sentences against the threshold>" } },
  "findings": [ { "id": "f1", "text": "<observation first, then what it means>", "hypotheses": ["h1"],
                  "targets": [ { "kind": "job", "id": "<id>" } ],
                  "evidence": [ { "evidence": "e2", "quote": "<verbatim>", "participant": "P02" },
                                { "tally": "q2", "option": "Yes", "count": 18, "of": 30 },
                                { "tally": "q5", "stat": "mean", "value": 3.8, "of": 30 } ] } ],
  "refill": { "quantitative": "<only numbers that are in a finding or the tally>",
              "researchSummary": "<what people said and did>", "executiveSummary": "<one paragraph>" } }
```

7. `$T synthesize <id> --file <scratch.json>` (it runs `tally` first for a survey and `verify`), then
   `$T verify <id>`. It writes even when verify fails, so errors can be fixed; the status becomes
   `analysed` only on a clean verify. **Fix every error and re-run until clean.** A quote not found
   verbatim means you altered it: re-copy it. A tally mismatch means your number is wrong: use the
   tally's. **A failing verify is never presented around**, never explained away, and never worked
   around by editing the evidence.
8. The `refill` text follows `/pb:clarify` §1a's marks (`**…**`, `{-…-}`, `{+…+}`; no more than about one
   per sentence; no wording changed to fit a mark). The tool appends each field as `<text> [<id>]`, so
   leave the study id out of the text yourself.

## ▛ G-INSIGHT — human gate ▟
**STOP.** Present, in full:

- the **verdict for each hypothesis**, against its threshold as written in §3, with the `why`
- **every finding** with its evidence: the quotes (with participant id and evidence id) and the tally
  numbers, **disconfirming evidence first**
- **the exact text** `refill` would append, field by field, as it will read, including the `[<id>]` suffix
- every `verify` **warning**, in plain words: below `targetN` ("directional only"), a finding that rests
  on one participant, evidence with `consent: unknown`, a PII hit in a quote, a number in the refill found
  in no finding, a very short quote
- what the study could not tell: the audience it did not reach, the question it did not ask

Ask for **approve**, **edit** or **reject**. Silence is not approval. **Nothing is appended before this
is answered.**

- **Approve** → `$T refill <id> --approved [--note "<what was said>"]`. It backs the registry up under
  `memory/backups/research-<id>-<stamp>/`, appends to `meta.userInsights.*`, and sets the status to
  `applied`. A re-run is a no-op; if someone edited the appended text since, it appends again and warns:
  say so. It never touches other text.
- **Edit** → change the scratch file, `synthesize`, `verify`, re-present. An edit re-opens the gate.
- **Reject** → nothing is appended; the evidence and the findings stay in the study. Ask whether to gather
  more or to leave the verdicts as they are.

## 7 · Close the loop

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
2. **Route, do not apply.** A verdict that says a job, a rule or the structure is wrong is a proposal.
   Print it with the finding id and send it to its owner; make none of the change here:

| The verdict says | Route |
|---|---|
| a **job** is wrong, missing or mis-stated | `/pb:clarify` §1b, citing the finding |
| a **rule** is wrong or an `ASSUMPTION` held or failed | `/pb:clarify` §2, citing the finding, which updates the rule and its `decision{}` |
| the **structure** of a screen or flow should differ | `/pb:explore`, with the finding as the reason |

   **Never edit a rule, a job or a screen from here.**
3. **Where to read it.** UX: Project Summary → Research (a study's verdicts, findings and evidence list)
   and Project Summary → Insights (the refilled text). Tell the user which preview URL shows it if a
   `/pb:preview` server is up; do not start one for this.

**Do not render.** The registry is the source of truth; `/pb:preview` shows the change without it.

## Result
A study in the registry's `research` slice with the scope and setup the user chose (§0), its instrument
(independently bias-reviewed) under `memory/research/<id>/instrument/`. For scope `instrument` that is the
whole result. For scope `collect`, also its evidence under `memory/research/<id>/evidence/` (read-only, hashed, with consent recorded), verdicts that
are checked against thresholds fixed before the data, findings whose quotes and numbers the tool has
verified, User Insights refilled with a citation back to the study, and one decision-log entry.

## NEVER
- NEVER simulate respondents, fill in answers, role-play a participant or generate "synthetic users" as
  evidence. Not as a draft, not as a placeholder, not "labelled as synthetic" in the evidence folder. An
  instrument is tested on a real person or not at all.
- NEVER edit a stored evidence file, or write one yourself. Evidence comes from `import`.
- NEVER compute a number by hand. Counts, means and percentages come from `tally`; if the tool cannot
  produce a figure, do not state it.
- NEVER move a threshold, a `supportedIf` or a `refutedIf` after seeing data. A wrong threshold is
  recorded as such in the verdict's `why`, and the next study fixes it.
- NEVER write the `research` slice by hand: `init`, `scope`, `plan`, `review`, `approve`, `import`,
  `tally`, `synthesize` and `refill` are the only writers.
- NEVER quote from memory, paraphrase inside quote marks, or fix a participant's grammar in a quote.
- NEVER present a finding from a participant who withdrew, and never present around a failing `verify`.
- NEVER ask for or store a real name; never import a `--consent no` file; never keep a PII column unless
  the user asked and gave the reason.
- NEVER hide a disconfirming result, an inconclusive verdict, a small sample or an unknown consent to make
  a gate look finished.
- NEVER apply a verdict to a job, rule or screen yourself: route it (§7).
- NEVER approve at either gate for the user, and NEVER pass `--approved` before G-INSIGHT is answered.
- NEVER skip the opening question (§0), even when the request sounds obvious or the study is being resumed.
- NEVER pick the scope for the user, or assume a survey tool, panel or participant list they did not name.
- NEVER offer an online test, a hosted link or a panel: pb hosts nothing.
- NEVER hand the bias reviewer the hypotheses, the thresholds, the question being studied or any framing
  from this conversation: the reviewer gets the path to `bias-review.md` and nothing else.
- NEVER overturn a reviewer's `no` yourself, and NEVER pass `--accept-review` or `--skip-review` with words
  the user did not give.
- NEVER reword a standard metric question, or call a benchmark a pass mark.

> **Skill degrade (NS6).** If a skill this command invokes fails to load, say so explicitly and proceed with its core intent — never silently skip the step.
